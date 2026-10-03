from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.core.config import settings

router = APIRouter()


@router.post(
    settings.telegram_webhook_path,
    response_class=PlainTextResponse,
)
async def telegram_webhook(
    request: Request,
) -> PlainTextResponse:
    """Принимает update Telegram и передаёт его Dispatcher."""

    dispatcher = request.app.state.dispatcher
    bot = request.app.state.bot

    if not isinstance(dispatcher, Dispatcher):
        raise RuntimeError("dispatcher is not initialized")
    if not isinstance(bot, Bot):
        raise RuntimeError("bot is not initialized")

    try:
        update = Update.model_validate(await request.json())
    except ValueError:
        return PlainTextResponse("invalid update", status_code=400)

    await dispatcher.feed_webhook_update(
        bot,
        update,
    )
    return PlainTextResponse("ok", status_code=200)
