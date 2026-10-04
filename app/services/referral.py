from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from app.database.crud import ReferralRepository, UserRepository
from app.database.models import Payment, ReferralReward, User
from app.services.notification import NotificationService
from app.services.xui_client import XuiAPIError, XuiClient


@dataclass(slots=True, frozen=True)
class ReferralStats:
    """Статистика рефералов."""

    invited_count: int
    earned_days: int


class ReferralService:
    """Бизнес-логика реферальной системы."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        referral_repository: ReferralRepository,
        xui_client: XuiClient,
        notification_service: NotificationService,
    ) -> None:
        self._users = user_repository
        self._referrals = referral_repository
        self._xui = xui_client
        self._notifications = notification_service

    async def process_start(
        self,
        *,
        referred_user: User,
        args: str | None,
    ) -> bool:
        """Фиксирует новую реферальную связь и начисляет +1 день."""

        referrer_tg_id = self._parse_referrer_tg_id(args)
        if referrer_tg_id is None or referrer_tg_id == referred_user.tg_id:
            return False

        if await self._referrals.get_by_referred_user(
            referred_user.id
        ) is not None:
            return False

        referrer = await self._users.get_by_tg_id(referrer_tg_id)
        if referrer is None:
            return False

        referral, created = await self._referrals.get_or_create(
            referrer_id=referrer.id,
            referred_user_id=referred_user.id,
        )
        if not created:
            return False

        reward = await self._referrals.create_registration_reward(
            referral=referral,
        )
        await self._apply_reward(
            referrer=referrer,
            reward=reward,
        )

        await self._notifications.send(
            user=referrer,
            notification_type="referral_registration_reward",
            marker=str(referral.id),
            text=(
                "👥 твой друг перешел по ссылке!\n"
                "🎁 тебе начислен +1 день к подписке."
            ),
        )
        return True

    async def process_payment_reward(
        self,
        *,
        payment: Payment,
        referred_user: User,
    ) -> int:
        """Начисляет рефереру 5 дней за каждый оплаченный месяц."""

        referral = await self._referrals.get_by_referred_user(
            referred_user.id
        )
        if referral is None:
            return 0

        if payment.id <= 0 or payment.months <= 0:
            raise ValueError("invalid payment data")

        reward = await self._referrals.create_payment_reward(
            referral=referral,
            payment=payment,
        )
        reward_days = reward.reward_days

        referrer = await self._users.get_by_id(referral.referrer_id)
        if referrer is None:
            return reward_days

        await self._apply_reward(
            referrer=referrer,
            reward=reward,
        )

        await self._notifications.send(
            user=referrer,
            notification_type="referral_payment_reward",
            marker=str(payment.id),
            text=(
                f"🎉 твой реферал оплатил подписку ({payment.months} мес.)!\n"
                f"🎁 тебе начислено +{reward_days} дней к подписке."
            ),
        )
        return reward_days

    async def apply_pending_rewards(
        self,
        user: User,
        *,
        status: str | None = None,
    ) -> int:
        """Применяет ранее отложенные награды после создания клиента."""

        rewards = await self._referrals.get_pending_for_user(user.id)
        if not rewards or not user.sub_id:
            return 0

        total_days = sum(reward.reward_days for reward in rewards)
        if total_days <= 0:
            return 0

        try:
            updated = await self._xui.add_days_to_client_by_sub_id(
                user.sub_id,
                days=total_days,
            )
            expiry_time = updated.get("expiryTime")
            sub_id = updated.get("subId")
            email = updated.get("email") or user.email

            if not isinstance(expiry_time, (int, float)):
                raise XuiAPIError("invalid expiryTime")
            if not isinstance(sub_id, str) or not sub_id:
                raise XuiAPIError("invalid subId")
            if not isinstance(email, str) or not email:
                raise XuiAPIError("invalid email")

            expires_at = datetime.fromtimestamp(
                float(expiry_time) / 1000,
                tz=timezone.utc,
            )
            await self._users.update_subscription(
                user,
                email=email,
                sub_id=sub_id,
                subscription_url=self._xui.get_subscription_url(
                    sub_id,
                    json_mode=True,
                ),
                status=status or user.status,
                expires_at=expires_at,
            )

            for reward in rewards:
                await self._referrals.mark_applied(reward)

            return total_days
        except (XuiAPIError, ValueError, TypeError, KeyError):
            logging.exception(
                "failed to apply pending referral rewards"
            )
            return 0

    async def get_stats(self, user_id: int) -> ReferralStats:
        """Возвращает актуальную статистику пользователя."""

        invited_count, earned_days = (
            await self._referrals.get_stats_by_referrer_id(user_id)
        )
        return ReferralStats(
            invited_count=invited_count,
            earned_days=earned_days,
        )

    async def get_referrer_id(self, referred_user_id: int) -> int | None:
        """Возвращает внутренний ID реферера."""

        referral = await self._referrals.get_by_referred_user(
            referred_user_id
        )
        return referral.referrer_id if referral is not None else None

    async def _apply_reward(
        self,
        *,
        referrer: User,
        reward: ReferralReward,
    ) -> bool:
        if reward.status == "applied":
            return True

        if not referrer.sub_id:
            return False

        try:
            client = await self._xui.find_client_by_sub_id(
                referrer.sub_id
            )
            if client is None:
                return False

            updated = await self._xui.add_days_to_client_by_sub_id(
                referrer.sub_id,
                days=reward.reward_days,
            )

            expiry_time = updated.get("expiryTime")
            sub_id = updated.get("subId")
            email = updated.get("email") or referrer.email

            if not isinstance(expiry_time, (int, float)):
                raise XuiAPIError("invalid expiryTime")
            if not isinstance(sub_id, str) or not sub_id:
                raise XuiAPIError("invalid subId")
            if not isinstance(email, str) or not email:
                raise XuiAPIError("invalid email")

            expires_at = datetime.fromtimestamp(
                float(expiry_time) / 1000,
                tz=timezone.utc,
            )
            await self._users.update_subscription(
                referrer,
                email=email,
                sub_id=sub_id,
                subscription_url=self._xui.get_subscription_url(
                    sub_id,
                    json_mode=True,
                ),
                status=referrer.status,
                expires_at=expires_at,
            )
            await self._referrals.mark_applied(reward)
            return True
        except (XuiAPIError, ValueError, TypeError, KeyError):
            logging.exception(
                "failed to apply referral reward immediately"
            )
            return False

    @staticmethod
    def _parse_referrer_tg_id(args: str | None) -> int | None:
        if not args or not args.startswith("ref_"):
            return None

        try:
            return int(args[4:])
        except ValueError:
            return None


__all__ = ["ReferralService", "ReferralStats"]
