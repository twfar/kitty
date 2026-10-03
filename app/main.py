from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from aiogram import Bot
from fastapi import FastAPI, Request

from app.api.routes.rollypay import router as rollypay_router
from app.api.routes.telegram import router as telegram_router
from app.bot.dispatcher import create_dispatcher
from app.bot.runtime import BotRuntime
from app.core.config import settings
from app.database.database import async_session_factory, close_database
from app.services.rollypay_client import RollyPayClient
from app.services.xui_client import XuiClient


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """Управляет общими ресурсами FastAPI и Telegram-бота."""

    http_session = aiohttp.ClientSession()
    bot = Bot(token=settings.bot_token.get_secret_value())
    runtime = BotRuntime(
        settings=settings,
        http_session=http_session,
        session_factory=async_session_factory,
    )
    dispatcher = create_dispatcher(runtime)

    application.state.http_session = http_session
    application.state.bot = bot
    application.state.dispatcher = dispatcher

    try:
        webhook_kwargs: dict[str, object] = {
            "url": settings.telegram_webhook_url,
            "allowed_updates": dispatcher.resolve_used_update_types(),
        }
        if settings.telegram_webhook_secret is not None:
            webhook_kwargs["secret_token"] = (
                settings.telegram_webhook_secret.get_secret_value()
            )

        await bot.set_webhook(**webhook_kwargs)
        yield
    finally:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        finally:
            await dispatcher.storage.close()
            await bot.session.close()
            await http_session.close()
            await close_database()


def get_http_session(
    request: Request,
) -> aiohttp.ClientSession:
    """Возвращает общую HTTP-сессию приложения."""

    session = request.app.state.http_session

    if not isinstance(session, aiohttp.ClientSession):
        raise RuntimeError("HTTP session is not initialized")

    return session


def get_xui_client(request: Request) -> XuiClient:
    """Создаёт XuiClient поверх общей HTTP-сессии."""

    return XuiClient(
        session=get_http_session(request),
        settings=settings,
    )


def get_rollypay_client(
    request: Request,
) -> RollyPayClient:
    """Создаёт RollyPayClient поверх общей HTTP-сессии."""

    return RollyPayClient(
        session=get_http_session(request),
        settings=settings,
    )


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(telegram_router)
app.include_router(rollypay_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Проверяет доступность процесса."""

    return {"status": "ok"}
