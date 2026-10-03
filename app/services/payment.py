from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.crud import (
    PaymentRepository,
    ReferralRepository,
    UserRepository,
)
from app.database.models import Payment, User
from app.services.xui_client import XuiAPIError, XuiClient


class PaymentProcessingError(RuntimeError):
    """Ошибка обработки успешного платежа."""


@dataclass(slots=True, frozen=True)
class PaymentProcessResult:
    """Результат обработки webhook-платежа."""

    status: str
    message: str


class PaymentService:
    """Касса: применяет подтверждённые платежи к подпискам и рефералам."""

    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        settings: Settings,
        xui_client: XuiClient,
    ) -> None:
        self._session = session
        self._bot = bot
        self._settings = settings
        self._xui = xui_client
        self._payments = PaymentRepository(session)
        self._users = UserRepository(session)
        self._referrals = ReferralRepository(session)

    async def process(
        self,
        *,
        payment: Payment,
        status: str,
    ) -> PaymentProcessResult:
        """Обрабатывает статус платежа, включая успешное продление."""

        if status != "paid":
            await self._payments.set_status(payment, status=status)

            if status in {"canceled", "expired"}:
                await self._safe_send(
                    payment.user_id,
                    "❌ оплата не прошла.\n\n"
                    "платёж отменён или истёк. если деньги списались, "
                    "но подписка не продлилась — напиши в поддержку.",
                )

            return PaymentProcessResult(status=status, message="ok")

        if payment.status == "paid":
            return PaymentProcessResult(
                status="already_processed",
                message="already processed",
            )

        user = await self._users.get_by_id(payment.user_id)
        if user is None:
            await self._payments.set_status(payment, status="user_not_found")
            await self._notify_admin(
                "❌ оплата получена, но пользователь не найден\n\n"
                f"💳 payment id: {payment.external_id or payment.id}\n"
                f"👤 user id: {payment.user_id}",
            )
            return PaymentProcessResult(
                status="user_not_found",
                message="user not found",
            )

        try:
            updated_client = await self._renew_or_create(user, payment)
        except (XuiAPIError, ValueError, KeyError, TypeError) as exc:
            logging.exception("failed to renew subscription after payment")
            await self._payments.set_status(
                payment,
                status="renewal_failed",
            )
            await self._notify_admin(
                "❌ оплата получена, но продление не удалось\n\n"
                f"💳 payment id: {payment.external_id or payment.id}\n"
                f"🔗 sub id: {user.sub_id or 'нет'}\n"
                f"ошибка: {exc}",
            )
            raise PaymentProcessingError("subscription renewal failed") from exc

        expiry_time = updated_client.get("expiryTime")
        if not isinstance(expiry_time, (int, float)):
            raise PaymentProcessingError(
                "3x-ui returned an invalid expiryTime"
            )

        expires_at = datetime.fromtimestamp(
            float(expiry_time) / 1000,
            tz=timezone.utc,
        )

        sub_id = updated_client.get("subId")
        email = updated_client.get("email")
        if not isinstance(sub_id, str) or not sub_id:
            raise PaymentProcessingError("3x-ui returned no subId")
        if not isinstance(email, str) or not email:
            email = user.email or f"tg_{user.tg_id}"

        await self._users.update_subscription(
            user,
            email=email,
            sub_id=sub_id,
            subscription_url=self._xui.get_subscription_url(
                sub_id,
                json_mode=True,
            ),
            status="paid",
            expires_at=expires_at,
        )
        await self._payments.set_status(
            payment,
            status="paid",
            paid_at=datetime.now(timezone.utc),
        )

        await self._process_referral_reward(payment, user)
        await self._apply_pending_rewards(user)

        await self._safe_send(
            user.tg_id,
            "✅ оплата прошла!\n\n"
            f"🔗 подписка продлена на {payment.days} дней.",
        )

        referrer_id = await self._get_referrer_id(user)
        await self._notify_admin(
            "✅ подписка продлена автоматически\n\n"
            f"👤 telegram id: {user.tg_id}\n"
            f"💳 payment id: {payment.external_id or payment.id}\n"
            f"🎁 добавлено: {payment.days} дней\n"
            f"📱 устройств: {payment.device_limit}\n"
            f"⏳ expires: {int(expires_at.timestamp())}\n"
            f"👥 реферал: "
            f"{'да — ' + str(referrer_id) if referrer_id else 'нет'}",
        )

        return PaymentProcessResult(status="paid", message="ok")

    async def _renew_or_create(
        self,
        user: User,
        payment: Payment,
    ) -> dict[str, object]:
        """Продлевает существующего клиента или создаёт его заново."""

        if user.sub_id:
            client = await self._xui.find_client_by_sub_id(user.sub_id)
            if client is not None:
                return await self._xui.renew_client_by_sub_id(
                    user.sub_id,
                    days=payment.days,
                    device_limit=payment.device_limit,
                )

        email = user.email or f"tg_{user.tg_id}"
        return await self._xui.create_client(
            tg_id=user.tg_id,
            email=email,
            expiry_hours=payment.days * 24,
            group="paid",
            hwid_limit=payment.device_limit,
        )

    async def _process_referral_reward(
        self,
        payment: Payment,
        referred_user: User,
    ) -> None:
        """Начисляет 10 дней за первый платёж или 5 за последующие."""

        referral = await self._referrals.get_by_referred_user(referred_user.id)
        if referral is None:
            return

        if await self._referrals.get_by_payment_id(payment.id) is not None:
            return

        reward_count = await self._referrals.count_rewards_for_referred_user(
            referred_user.id
        )
        reward_days = 10 if reward_count == 0 else 5
        reward = await self._referrals.create_reward(
            user_id=referral.referrer_id,
            amount=Decimal("0.00"),
            currency=payment.currency,
            reward_days=reward_days,
            referral_id=referral.id,
            payment_id=payment.id,
        )

        referrer = await self._users.get_by_id(referral.referrer_id)
        if referrer is None:
            return

        applied = False
        if (
            referrer.sub_id
            and referrer.expires_at is not None
            and referrer.expires_at > datetime.now(timezone.utc)
        ):
            try:
                updated = await self._xui.add_days_to_client_by_sub_id(
                    referrer.sub_id,
                    days=reward_days,
                )
                expiry_time = updated.get("expiryTime")
                if isinstance(expiry_time, (int, float)):
                    referrer_expires = datetime.fromtimestamp(
                        float(expiry_time) / 1000,
                        tz=timezone.utc,
                    )
                    sub_id = updated.get("subId")
                    if isinstance(sub_id, str) and sub_id:
                        await self._users.update_subscription(
                            referrer,
                            email=referrer.email,
                            sub_id=sub_id,
                            subscription_url=self._xui.get_subscription_url(
                                sub_id,
                                json_mode=True,
                            ),
                            status=referrer.status,
                            expires_at=referrer_expires,
                        )
                        await self._referrals.mark_applied(reward)
                        applied = True
            except (XuiAPIError, ValueError, TypeError, KeyError):
                logging.exception("failed to apply referral reward")

        reward_text = (
            f"🎁 реферальная награда: +{reward_days} дней"
            + (
                " к подписке."
                if applied
                else ".\n\n⚠️ активной подписки нет — дни накоплены "
                "и автоматически добавятся к следующей подписке."
            )
        )
        await self._safe_send(referrer.tg_id, reward_text)

    async def _apply_pending_rewards(self, user: User) -> None:
        """Добавляет накопленные реферальные дни после новой оплаты."""

        rewards = await self._referrals.get_pending_for_user(user.id)
        if not rewards or not user.sub_id:
            return

        total_days = sum(reward.reward_days for reward in rewards)
        if total_days <= 0:
            return

        try:
            updated = await self._xui.add_days_to_client_by_sub_id(
                user.sub_id,
                days=total_days,
            )
            expiry_time = updated.get("expiryTime")
            sub_id = updated.get("subId")
            if not isinstance(expiry_time, (int, float)):
                return
            if not isinstance(sub_id, str) or not sub_id:
                return

            expires_at = datetime.fromtimestamp(
                float(expiry_time) / 1000,
                tz=timezone.utc,
            )
            await self._users.update_subscription(
                user,
                email=user.email,
                sub_id=sub_id,
                subscription_url=self._xui.get_subscription_url(
                    sub_id,
                    json_mode=True,
                ),
                status="paid",
                expires_at=expires_at,
            )

            for reward in rewards:
                await self._referrals.mark_applied(reward)

            await self._safe_send(
                user.tg_id,
                f"🎁 накопленные реферальные дни добавлены: +{total_days} дней.",
            )
        except (XuiAPIError, ValueError, TypeError, KeyError):
            logging.exception("failed to apply pending referral rewards")

    async def _get_referrer_id(self, user: User) -> int | None:
        referral = await self._referrals.get_by_referred_user(user.id)
        return referral.referrer_id if referral is not None else None

    async def _safe_send(self, tg_id: int, text: str) -> None:
        try:
            await self._bot.send_message(tg_id, text)
        except Exception:
            logging.exception("failed to send payment notification")

    async def _notify_admin(self, text: str) -> None:
        try:
            await self._bot.send_message(self._settings.admin_id, text)
        except Exception:
            logging.exception("failed to notify admin about payment")


__all__ = [
    "PaymentProcessResult",
    "PaymentProcessingError",
    "PaymentService",
]
