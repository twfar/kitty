from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
from app.services.notification import NotificationService
from app.services.referral import ReferralService
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
        self._referral_service = ReferralService(
            user_repository=self._users,
            referral_repository=ReferralRepository(session),
            xui_client=xui_client,
            notification_service=NotificationService(
                session=session,
                bot=bot,
            ),
        )

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

        await self._referral_service.process_payment_reward(
            payment=payment,
            referred_user=user,
        )
        await self._referral_service.apply_pending_rewards(
            user,
            status="paid",
        )

        await self._safe_send(
            user.tg_id,
            "✅ оплата прошла!\n\n"
            f"🔗 подписка продлена на {payment.days} дней.",
        )

        referrer_id = await self._referral_service.get_referrer_id(
            user.id
        )
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
