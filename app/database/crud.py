from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BotSetting, DeviceSnapshot, NotificationLog, Payment,
    PromoCode, PromoUse, Referral, ReferralReward, User,
)


class UserRepository:
    """Репозиторий пользователей."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_sub_id(self, sub_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.sub_id == sub_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        tg_id: int,
        username: str | None,
        email: str | None = None,
        sub_id: str | None = None,
        subscription_url: str | None = None,
        status: str = "new",
        expires_at: datetime | None = None,
    ) -> User:
        user = User(
            tg_id=tg_id, username=username, email=email, sub_id=sub_id,
            subscription_url=subscription_url, status=status,
            expires_at=expires_at,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_subscription(
        self,
        user: User,
        *,
        email: str | None,
        sub_id: str | None,
        subscription_url: str | None,
        status: str,
        expires_at: datetime | None,
    ) -> User:
        user.email = email
        user.sub_id = sub_id
        user.subscription_url = subscription_url
        user.status = status
        user.expires_at = expires_at
        await self.session.flush()
        return user

    async def set_status(self, user: User, status: str) -> User:
        user.status = status
        await self.session.flush()
        return user

    async def list_active_subscriptions(self) -> list[User]:
        statement = select(User).where(
            User.status.in_(("trial", "paid")),
            User.expires_at.is_not(None),
            User.is_blocked.is_(False),
        )
        result = await self.session.execute(
            statement.order_by(User.tg_id)
        )
        return list(result.scalars().all())

    async def list_for_broadcast(self, group: str) -> list[User]:
        now = datetime.now()
        statement = select(User).where(User.is_blocked.is_(False))
        if group == "active":
            statement = statement.where(
                User.status.in_(("trial", "paid")),
                User.expires_at.is_not(None),
                User.expires_at > now,
            )
        elif group == "trial":
            statement = statement.where(
                User.status == "trial",
                User.expires_at.is_not(None),
                User.expires_at > now,
            )
        elif group == "paid":
            statement = statement.where(
                User.status == "paid",
                User.expires_at.is_not(None),
                User.expires_at > now,
            )
        elif group == "expired":
            statement = statement.where(
                User.expires_at.is_not(None),
                User.expires_at <= now,
            )
        result = await self.session.execute(statement.order_by(User.tg_id))
        return list(result.scalars().all())

    async def get_by_username(self, username: str) -> User | None:
        normalized = username.removeprefix("@").lower()
        result = await self.session.execute(
            select(User).where(func.lower(User.username) == normalized)
        )
        return result.scalar_one_or_none()

    async def delete_by_tg_id(self, tg_id: int) -> None:
        user = await self.get_by_tg_id(tg_id)
        if user is not None:
            await self.session.delete(user)
            await self.session.flush()

    async def list_expiring(
        self,
        *,
        before: datetime,
        after: datetime | None = None,
    ) -> list[User]:
        statement = select(User).where(
            User.expires_at.is_not(None),
            User.expires_at <= before,
            User.status.not_in(("banned", "expired")),
        )
        if after is not None:
            statement = statement.where(User.expires_at > after)
        result = await self.session.execute(statement)
        return list(result.scalars().all())


class PromoCodeRepository:
    """Репозиторий промокодов."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> list[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).order_by(PromoCode.code)
        )
        return list(result.scalars().all())

    async def delete(self, promo: PromoCode) -> None:
        await self.session.delete(promo)
        await self.session.flush()

    async def get_by_code(self, code: str) -> PromoCode | None:
        result = await self.session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        code: str,
        discount_percent: int | None = None,
        discount_amount: Decimal | None = None,
        reward_days: int = 0,
        max_uses: int | None = None,
        expires_at: datetime | None = None,
    ) -> PromoCode:
        promo = PromoCode(
            code=code,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            reward_days=reward_days,
            max_uses=max_uses,
            expires_at=expires_at,
        )
        self.session.add(promo)
        await self.session.flush()
        return promo

    async def create_use(
        self,
        *,
        promo_code: PromoCode,
        user: User,
        payment: Payment | None = None,
    ) -> PromoUse:
        usage = PromoUse(
            promo_code_id=promo_code.id,
            user_id=user.id,
            payment_id=payment.id if payment else None,
        )
        promo_code.uses_count += 1
        self.session.add(usage)
        await self.session.flush()
        return usage


class PaymentRepository:
    """Репозиторий платежей."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, payment_id: int) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self, external_id: str
    ) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user: User,
        amount: Decimal,
        currency: str,
        plan: str | None,
        days: int = 30,
        device_limit: int = 3,
        months: int = 1,
        test: bool = False,
        external_id: str | None = None,
        payment_url: str | None = None,
        raw_payload: dict[str, object] | None = None,
    ) -> Payment:
        payment = Payment(
            user_id=user.id,
            amount=amount,
            currency=currency,
            plan=plan,
            days=days,
            device_limit=device_limit,
            months=months,
            test=test,
            external_id=external_id,
            payment_url=payment_url,
            raw_payload=raw_payload,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_by_external_id_for_update(
        self, external_id: str
    ) -> Payment | None:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.external_id == external_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def set_status(
        self,
        payment: Payment,
        *,
        status: str,
        paid_at: datetime | None = None,
    ) -> Payment:
        payment.status = status
        if paid_at is not None:
            payment.paid_at = paid_at
        await self.session.flush()
        return payment


class ReferralRepository:
    """Репозиторий реферальной системы."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_payment_id(
        self, payment_id: int
    ) -> ReferralReward | None:
        result = await self.session.execute(
            select(ReferralReward).where(ReferralReward.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def count_rewards_for_referred_user(
        self, referred_user_id: int
    ) -> int:
        statement = (
            select(func.count(ReferralReward.id))
            .join(Referral, ReferralReward.referral_id == Referral.id)
            .where(Referral.referred_user_id == referred_user_id)
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def get_pending_for_user(
        self, user_id: int
    ) -> list[ReferralReward]:
        result = await self.session.execute(
            select(ReferralReward)
            .where(
                ReferralReward.user_id == user_id,
                ReferralReward.status == "pending",
            )
            .order_by(ReferralReward.created_at)
        )
        return list(result.scalars().all())

    async def mark_applied(
        self, reward: ReferralReward
    ) -> ReferralReward:
        reward.status = "applied"
        await self.session.flush()
        return reward

    async def get_by_referred_user(
        self, user_id: int
    ) -> Referral | None:
        result = await self.session.execute(
            select(Referral).where(Referral.referred_user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, *, referrer_id: int, referred_user_id: int
    ) -> Referral:
        referral = Referral(
            referrer_id=referrer_id,
            referred_user_id=referred_user_id,
        )
        self.session.add(referral)
        await self.session.flush()
        return referral

    async def create_reward(
        self,
        *,
        user_id: int,
        amount: Decimal,
        currency: str = "RUB",
        reward_days: int = 0,
        referral_id: int | None = None,
        payment_id: int | None = None,
    ) -> ReferralReward:
        reward = ReferralReward(
            user_id=user_id,
            referral_id=referral_id,
            payment_id=payment_id,
            amount=amount,
            currency=currency,
            reward_days=reward_days,
        )
        self.session.add(reward)
        await self.session.flush()
        return reward


class BotSettingRepository:
    """Репозиторий динамических настроек."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> BotSetting | None:
        result = await self.session.execute(
            select(BotSetting).where(BotSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_value(
        self, key: str, default: str | None = None
    ) -> str | None:
        setting = await self.get(key)
        return default if setting is None else setting.value

    async def set(
        self,
        key: str,
        value: str,
        description: str | None = None,
    ) -> BotSetting:
        setting = await self.get(key)
        if setting is None:
            setting = BotSetting(
                key=key, value=value, description=description
            )
            self.session.add(setting)
        else:
            setting.value = value
            if description is not None:
                setting.description = description
        await self.session.flush()
        return setting


class DeviceSnapshotRepository:
    """Репозиторий снимков устройств."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_known_device_keys(self, user_id: int) -> set[str]:
        result = await self.session.execute(
            select(DeviceSnapshot.devices).where(
                DeviceSnapshot.user_id == user_id
            )
        )
        known: set[str] = set()
        for snapshot in result.scalars():
            for device in snapshot:
                value = (
                    device.get("fingerprint")
                    or device.get("hwid")
                    or device.get("id")
                    or ""
                )
                if value:
                    known.add(str(value))
        return known

    async def create(
        self,
        *,
        user_id: int,
        device_count: int,
        devices: list[dict[str, object]],
    ) -> DeviceSnapshot:
        snapshot = DeviceSnapshot(
            user_id=user_id,
            device_count=device_count,
            devices=devices,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot


class NotificationLogRepository:
    """Репозиторий истории уведомлений."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def was_sent(
        self,
        *,
        user_id: int,
        notification_type: str,
        marker: str,
    ) -> bool:
        result = await self.session.execute(
            select(NotificationLog.id).where(
                NotificationLog.user_id == user_id,
                NotificationLog.notification_type == notification_type,
                NotificationLog.marker == marker,
                NotificationLog.status == "sent",
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        *,
        user_id: int | None,
        notification_type: str,
        marker: str,
        status: str,
        telegram_message_id: int | None = None,
        error_message: str | None = None,
        sent_at: datetime | None = None,
    ) -> NotificationLog:
        log = NotificationLog(
            user_id=user_id,
            notification_type=notification_type,
            marker=marker,
            status=status,
            telegram_message_id=telegram_message_id,
            error_message=error_message,
            sent_at=sent_at,
        )
        self.session.add(log)
        await self.session.flush()
        return log
