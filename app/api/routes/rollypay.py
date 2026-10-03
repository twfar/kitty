from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation

from aiogram import Bot
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.crud import PaymentRepository
from app.database.database import async_session_factory
from app.services.payment import PaymentProcessingError, PaymentService
from app.services.xui_client import XuiClient

router = APIRouter()


class RollyPayWebhookEvent(BaseModel):
    """Минимальная схема входящего webhook RollyPay."""

    model_config = ConfigDict(extra="allow")

    payment_id: str
    status: str
    amount: Decimal
    currency: str
    test: bool | None = None
    event_type: str | None = None


def _verify_signature(
    *,
    raw_body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    secret = settings.rollypay_signing_secret
    if not timestamp or not signature or secret is None:
        return False

    expected = hmac.new(
        secret.get_secret_value().encode(),
        timestamp.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def _notify_admin(bot: Bot, text: str) -> None:
    try:
        await bot.send_message(settings.admin_id, text)
    except Exception:
        return


@router.post(
    settings.rollypay_webhook_path,
    response_class=PlainTextResponse,
)
async def rollypay_webhook(
    request: Request,
) -> PlainTextResponse:
    """Принимает и валидирует webhook RollyPay."""

    raw_body = await request.body()

    if not _verify_signature(
        raw_body=raw_body,
        timestamp=request.headers.get("X-Timestamp", ""),
        signature=request.headers.get("X-Signature", ""),
    ):
        return PlainTextResponse(
            "invalid signature",
            status_code=403,
        )

    try:
        event = RollyPayWebhookEvent.model_validate_json(raw_body)
    except ValueError:
        return PlainTextResponse(
            "invalid json",
            status_code=400,
        )

    async with async_session_factory() as session:
        payments = PaymentRepository(session)
        payment = await payments.get_by_external_id_for_update(
            event.payment_id
        )

        bot = request.app.state.bot
        if not isinstance(bot, Bot):
            raise RuntimeError("bot is not initialized")

        if payment is None:
            await _notify_admin(
                bot,
                "⚠️ неизвестный платёж\n\n"
                f"🆔 payment id: {event.payment_id}",
            )
            return PlainTextResponse("ignored", status_code=200)

        if event.test is not None and event.test != payment.test:
            await _notify_admin(
                bot,
                "⚠️ несовпадение test-режима\n\n"
                f"🆔 payment id: {event.payment_id}",
            )
            return PlainTextResponse(
                "test mode mismatch",
                status_code=400,
            )

        try:
            event_amount = event.amount.quantize(Decimal("0.01"))
            stored_amount = payment.amount.quantize(Decimal("0.01"))
        except InvalidOperation:
            return PlainTextResponse(
                "invalid amount",
                status_code=400,
            )

        if event_amount != stored_amount:
            await _notify_admin(
                bot,
                "⚠️ несовпадение суммы\n\n"
                f"🆔 payment id: {event.payment_id}",
            )
            return PlainTextResponse(
                "amount mismatch",
                status_code=400,
            )

        if event.currency != payment.currency:
            return PlainTextResponse(
                "currency mismatch",
                status_code=400,
            )

        xui_client = XuiClient(
            request.app.state.http_session,
            settings,
        )
        service = PaymentService(
            session=session,
            bot=bot,
            settings=settings,
            xui_client=xui_client,
        )

        try:
            result = await service.process(
                payment=payment,
                status=event.status,
            )
            await session.commit()
        except PaymentProcessingError:
            await session.commit()
            return PlainTextResponse(
                "renewal failed",
                status_code=500,
            )
        except Exception:
            await session.rollback()
            raise

        return PlainTextResponse(
            result.message,
            status_code=200,
        )
