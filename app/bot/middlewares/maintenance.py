from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.crud import BotSettingRepository


class MaintenanceMiddleware(BaseMiddleware):
    """Закрывает пользовательский интерфейс во время технических работ."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        settings = data.get("settings")
        session = data.get("session")
        user = getattr(event, "from_user", None)

        if not isinstance(settings, Settings):
            return await handler(event, data)
        if user is not None and user.id == settings.admin_id:
            return await handler(event, data)
        if not isinstance(session, AsyncSession):
            return await handler(event, data)

        enabled = await BotSettingRepository(session).get_value(
            "maintenance_enabled",
            "0",
        )
        if enabled != "1":
            return await handler(event, data)

        if isinstance(event, Message):
            command = (event.text or "").split(maxsplit=1)[0]
            if command.split("@", 1)[0] == "/start":
                message = await BotSettingRepository(session).get_value(
                    "maintenance_message",
                    "🔧 технические работы\n\nбот временно недоступен. попробуй позже.",
                )
                await event.answer(message or "бот временно недоступен.")
            return None

        if isinstance(event, CallbackQuery):
            await event.answer(
                "🔧 бот временно находится на технических работах.",
                show_alert=True,
            )
            return None

        return None
