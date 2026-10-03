from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import Settings
from app.database.crud import DeviceSnapshotRepository, UserRepository
from app.database.models import User
from app.database.database import async_session_factory
from app.services.notification import NotificationService
from app.services.xui_client import XuiClient


def _purchase_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 купить / продлить",
                    callback_data="purchase",
                )
            ]
        ]
    )


async def run_notification_check(
    *,
    bot: Bot,
    http_session: aiohttp.ClientSession,
    settings: Settings,
) -> None:
    """Один проход старого notifications_worker, но без while True."""

    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        users = await UserRepository(session).list_active_subscriptions()
        notifications = NotificationService(session=session, bot=bot)
        snapshots = DeviceSnapshotRepository(session)
        xui = XuiClient(http_session, settings)

        for user in users:
            if user.expires_at is None:
                continue

            remaining = user.expires_at - now
            marker = str(int(user.expires_at.timestamp()))

            if user.status == "trial" and timedelta(
                seconds=0
            ) < remaining <= timedelta(hours=3):
                await notifications.send(
                    user=user,
                    notification_type="trial_soon",
                    marker=marker,
                    text=(
                        "⏳ твой trial скоро закончится.\n\n"
                        "осталось меньше 3 часов.\n"
                        "хочешь продолжить пользоваться kitty vpn — купи подписку."
                    ),
                    reply_markup=_purchase_keyboard(),
                )

            if user.status == "paid" and remaining > timedelta(0):
                if remaining <= timedelta(hours=24):
                    await notifications.send(
                        user=user,
                        notification_type="subscription_day",
                        marker=marker,
                        text=(
                            "⏳ подписка закончится в ближайшие сутки.\n\n"
                            "продли её заранее, чтобы не потерять доступ."
                        ),
                        reply_markup=_purchase_keyboard(),
                    )

                if remaining <= timedelta(hours=1):
                    await notifications.send(
                        user=user,
                        notification_type="subscription_hour",
                        marker=marker,
                        text=(
                            "⚠️ подписка закончится примерно через час.\n\n"
                            "продли её сейчас, чтобы vpn продолжил работать без перерыва."
                        ),
                        reply_markup=_purchase_keyboard(),
                    )

            if remaining <= timedelta(0):
                await notifications.send(
                    user=user,
                    notification_type="subscription_expired",
                    marker=marker,
                    text=(
                        "❌ срок подписки закончился.\n\n"
                        "купи новую подписку, чтобы снова пользоваться kitty vpn."
                    ),
                    reply_markup=_purchase_keyboard(),
                )

            await _check_devices(
                session=session,
                user=user,
                xui=xui,
                notifications=notifications,
                snapshots=snapshots,
            )

        await session.commit()


async def _check_devices(
    *,
    session: AsyncSession,
    user: User,
    xui: XuiClient,
    notifications: NotificationService,
    snapshots: DeviceSnapshotRepository,
) -> None:
    if not user.email:
        return

    try:
        devices = await xui.get_hwid_devices(user.email)
    except Exception:
        logging.exception("failed to read HWID devices for %s", user.tg_id)
        return

    current_keys: set[str] = set()
    for device in devices:
        key_value = (
            device.get("fingerprint")
            or device.get("hwid")
            or device.get("id")
            or ""
        )
        if key_value:
            current_keys.add(str(key_value))

    previous_keys = await snapshots.get_known_device_keys(user.id)
    has_previous_snapshot = bool(previous_keys)

    if has_previous_snapshot:
        for device in devices:
            key_value = (
                device.get("fingerprint")
                or device.get("hwid")
                or device.get("id")
                or ""
            )
            key = str(key_value) if key_value else ""
            if not key or key in previous_keys:
                continue

            name_value = (
                device.get("deviceModel")
                or device.get("deviceOs")
                or device.get("userAgent")
                or "неизвестное устройство"
            )
            name = str(name_value)
            first_seen_value = (
                device.get("firstSeen")
                or device.get("firstSeenAt")
                or int(now.timestamp())
            )
            first_seen = int(first_seen_value)
            if first_seen > 10_000_000_000:
                first_seen //= 1000
            first_seen_text = datetime.fromtimestamp(
                first_seen,
                tz=timezone.utc,
            ).strftime("%d.%m.%Y %H:%M")
            await notifications.send(
                user=user,
                notification_type="hwid_added",
                marker=key,
                text=(
                    "📱 подключено новое устройство!\n\n"
                    f"устройство: {name}\n"
                    f"подключение: {first_seen_text}\n\n"
                    "если это не ты — проверь список устройств."
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📱 открыть устройства",
                                callback_data="devices",
                            )
                        ]
                    ]
                ),
            )

    await snapshots.create(
        user_id=user.id,
        device_count=len(current_keys),
        devices=devices,
    )


def create_scheduler(
    *,
    bot: Bot,
    http_session: aiohttp.ClientSession,
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        run_notification_check,
        trigger="interval",
        minutes=1,
        id="notification_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "bot": bot,
            "http_session": http_session,
            "settings": settings,
        },
    )
    return scheduler


__all__ = ["create_scheduler", "run_notification_check"]
