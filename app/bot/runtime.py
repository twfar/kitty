from __future__ import annotations

from dataclasses import dataclass

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings


@dataclass(slots=True)
class BotRuntime:
    """Ресурсы приложения, которыми пользуется Telegram-бот."""

    settings: Settings
    http_session: aiohttp.ClientSession
    session_factory: async_sessionmaker[AsyncSession]
