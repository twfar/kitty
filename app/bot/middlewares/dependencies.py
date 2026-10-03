from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
from aiogram import BaseMiddleware

from app.core.config import Settings
from app.services.rollypay_client import RollyPayClient
from app.services.xui_client import XuiClient


class DependenciesMiddleware(BaseMiddleware):
    """Передаёт Telegram-хэндлерам настройки и внешние API-клиенты."""

    def __init__(self, settings: Settings, http_session: aiohttp.ClientSession) -> None:
        self._settings = settings
        self._http_session = http_session

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self._settings
        data["xui_client"] = XuiClient(self._http_session, self._settings)
        data["rollypay_client"] = RollyPayClient(self._http_session, self._settings)
        return await handler(event, data)
