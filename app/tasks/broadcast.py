from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from taskiq_redis import RedisStreamBroker
from app.core.config import settings
from app.database.crud import UserRepository
from app.database.database import async_session_factory
from app.services.notification import NotificationService

broker = RedisStreamBroker(
    settings.redis_url,
    queue_name=settings.taskiq_queue_name,
    consumer_group_name="kitty-broadcast-workers",
    idle_timeout=600_000,
    unacknowledged_lock_timeout=30_000,
)


@broker.task(ack_type="when_executed")
async def broadcast_task(
    *,
    source_chat_id: int,
    source_message_id: int,
    group: str,
) -> int:
    """Надёжная массовая рассылка через Redis Stream."""

    bot = Bot(token=settings.bot_token.get_secret_value())
    try:
        async with async_session_factory() as session:
            users = await UserRepository(session).list_for_broadcast(group)
            notifications = NotificationService(
                session=session,
                bot=bot,
            )

            sent = 0
            marker = str(source_message_id)
            for user in users:
                delivered = await notifications.copy(
                    user=user,
                    notification_type=f"broadcast:{group}",
                    marker=marker,
                    source_chat_id=source_chat_id,
                    source_message_id=source_message_id,
                )
                if delivered:
                    sent += 1
                await asyncio.sleep(settings.broadcast_delay)

            await session.commit()

        try:
            await bot.send_message(
                settings.admin_id,
                "📢 рассылка завершена.\n\n"
                f"группа: {group}\n"
                f"успешно: {sent}\n"
                f"получателей: {len(users)}",
            )
        except Exception:
            logging.exception("failed to send broadcast completion message")

        return sent
    finally:
        await bot.session.close()


__all__ = ["broker", "broadcast_task"]
