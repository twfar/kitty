from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.crud import UserRepository
from app.services.rollypay_client import RollyPayClient
from app.services.subscription import SubscriptionService
from app.services.xui_client import XuiClient


class DependenciesMiddleware(BaseMiddleware):
    """Передаёт хэндлерам настройки, репозитории и сервисы."""

    def __init__(
        self,
        settings: Settings,
        http_session: aiohttp.ClientSession,
    ) -> None:
        self._settings = settings
        self._http_session = http_session

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if not isinstance(session, AsyncSession):
            raise RuntimeError(
                "DatabaseSessionMiddleware must run before DependenciesMiddleware"
            )

        xui_client = XuiClient(
            self._http_session,
            self._settings,
        )
        rollypay_client = RollyPayClient(
            self._http_session,
            self._settings,
        )
        user_repository = UserRepository(session)

        data["settings"] = self._settings
        data["xui_client"] = xui_client
        data["rollypay_client"] = rollypay_client
        data["user_repository"] = user_repository
        data["subscription_service"] = SubscriptionService(
            user_repository=user_repository,
            xui_client=xui_client,
            settings=self._settings,
        )

        return await handler(event, data)
