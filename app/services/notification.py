from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import NotificationLogRepository, UserRepository
from app.database.models import User


class NotificationService:
    """Безопасная доставка Telegram-уведомлений с дедупликацией."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        bot: Bot,
    ) -> None:
        self._bot = bot
        self._users = UserRepository(session)
        self._logs = NotificationLogRepository(session)

    async def send(
        self,
        *,
        user: User,
        notification_type: str,
        marker: str,
        text: str,
        reply_markup: object | None = None,
    ) -> bool:
        if user.is_blocked:
            return False

        if await self._logs.was_sent(
            user_id=user.id,
            notification_type=notification_type,
            marker=marker,
        ):
            return False

        try:
            message = await self._send_with_retry(
                user.tg_id,
                text,
                reply_markup,
            )
        except TelegramForbiddenError as exc:
            user.is_blocked = True
            await self._users.set_status(user, "blocked")
            await self._logs.create(
                user_id=user.id,
                notification_type=notification_type,
                marker=marker,
                status="blocked",
                error_message=str(exc),
            )
            return False
        except Exception as exc:
            await self._logs.create(
                user_id=user.id,
                notification_type=notification_type,
                marker=marker,
                status="failed",
                error_message=str(exc),
            )
            logging.exception(
                "notification delivery failed for tg_id=%s",
                user.tg_id,
            )
            return False

        await self._logs.create(
            user_id=user.id,
            notification_type=notification_type,
            marker=marker,
            status="sent",
            telegram_message_id=message.message_id,
            sent_at=datetime.now(timezone.utc),
        )
        return True

    async def copy(
        self,
        *,
        user: User,
        notification_type: str,
        marker: str,
        source_chat_id: int,
        source_message_id: int,
    ) -> bool:
        if user.is_blocked:
            return False

        if await self._logs.was_sent(
            user_id=user.id,
            notification_type=notification_type,
            marker=marker,
        ):
            return False

        try:
            message = await self._copy_with_retry(
                user.tg_id,
                source_chat_id,
                source_message_id,
            )
        except TelegramForbiddenError as exc:
            user.is_blocked = True
            await self._users.set_status(user, "blocked")
            await self._logs.create(
                user_id=user.id,
                notification_type=notification_type,
                marker=marker,
                status="blocked",
                error_message=str(exc),
            )
            return False
        except Exception as exc:
            await self._logs.create(
                user_id=user.id,
                notification_type=notification_type,
                marker=marker,
                status="failed",
                error_message=str(exc),
            )
            logging.exception(
                "broadcast delivery failed for tg_id=%s",
                user.tg_id,
            )
            return False

        await self._logs.create(
            user_id=user.id,
            notification_type=notification_type,
            marker=marker,
            status="sent",
            telegram_message_id=message.message_id,
            sent_at=datetime.now(timezone.utc),
        )
        return True

    async def _send_with_retry(
        self,
        tg_id: int,
        text: str,
        reply_markup: object | None,
    ) -> Message:
        for attempt in range(3):
            try:
                return await self._bot.send_message(
                    tg_id,
                    text,
                    reply_markup=reply_markup,
                )
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(exc.retry_after)
        raise RuntimeError("telegram send retry loop exhausted")

    async def _copy_with_retry(
        self,
        tg_id: int,
        source_chat_id: int,
        source_message_id: int,
    ) -> Message:
        for attempt in range(3):
            try:
                return await self._bot.copy_message(
                    chat_id=tg_id,
                    from_chat_id=source_chat_id,
                    message_id=source_message_id,
                )
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(exc.retry_after)
        raise RuntimeError("telegram copy retry loop exhausted")


__all__ = ["NotificationService"]
