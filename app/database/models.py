from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей."""


class TimestampMixin:
    """Общие временные метки."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    """Пользователь Telegram."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    sub_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    subscription_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), default="new", server_default="new", index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    referral_code: Mapped[str | None] = mapped_column(
        String(64), unique=True
    )
    referred_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    payments: Mapped[list[Payment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    promo_uses: Mapped[list[PromoUse]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    referral_rewards: Mapped[list[ReferralReward]] = relationship(
        back_populates="user", foreign_keys="ReferralReward.user_id",
        cascade="all, delete-orphan"
    )
    referrals: Mapped[list[Referral]] = relationship(
        back_populates="referrer", foreign_keys="Referral.referrer_id",
        cascade="all, delete-orphan"
    )
    referred_users: Mapped[list[Referral]] = relationship(
        back_populates="referred_user",
        foreign_keys="Referral.referred_user_id",
        cascade="all, delete-orphan"
    )
    device_snapshots: Mapped[list[DeviceSnapshot]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_logs: Mapped[list[NotificationLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PromoCode(TimestampMixin, Base):
    """Промокод."""

    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    discount_percent: Mapped[int | None] = mapped_column(Integer)
    discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    reward_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    uses: Mapped[list[PromoUse]] = relationship(
        back_populates="promo_code", cascade="all, delete-orphan"
    )


class PromoUse(Base):
    """Факт использования промокода."""

    __tablename__ = "promo_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL")
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    promo_code: Mapped[PromoCode] = relationship(back_populates="uses")
    user: Mapped[User] = relationship(back_populates="promo_uses")
    payment: Mapped[Payment | None] = relationship(back_populates="promo_use")

    __table_args__ = (
        UniqueConstraint(
            "promo_code_id", "user_id", name="uq_promo_use_code_user"
        ),
    )


class Payment(TimestampMixin, Base):
    """Платёж пользователя."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(8), default="RUB", server_default="RUB", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", index=True
    )
    plan: Mapped[str | None] = mapped_column(String(64))
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    months: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    payment_url: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="payments")
    promo_use: Mapped[PromoUse | None] = relationship(
        back_populates="payment", uselist=False
    )


class Referral(TimestampMixin, Base):
    """Реферальная связь."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="active", server_default="active"
    )

    referrer: Mapped[User] = relationship(
        back_populates="referrals", foreign_keys=[referrer_id]
    )
    referred_user: Mapped[User] = relationship(
        back_populates="referred_users", foreign_keys=[referred_user_id]
    )


class ReferralReward(TimestampMixin, Base):
    """Реферальная награда."""

    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referral_id: Mapped[int | None] = mapped_column(
        ForeignKey("referrals.id", ondelete="SET NULL")
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL")
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(8), default="RUB", server_default="RUB", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending"
    )
    reward_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    user: Mapped[User] = relationship(back_populates="referral_rewards")


class BotSetting(TimestampMixin, Base):
    """Динамическая настройка бота."""

    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class DeviceSnapshot(Base):
    """Снимок HWID-устройств."""

    __tablename__ = "device_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_count: Mapped[int] = mapped_column(Integer, nullable=False)
    devices: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, index=True
    )

    user: Mapped[User] = relationship(back_populates="device_snapshots")


class NotificationLog(Base):
    """История отправки уведомлений."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    notification_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    marker: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=""
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user: Mapped[User | None] = relationship(
        back_populates="notification_logs"
    )


Index("ix_users_status_expires_at", User.status, User.expires_at)
Index("ix_payments_status_created_at", Payment.status, Payment.created_at)
