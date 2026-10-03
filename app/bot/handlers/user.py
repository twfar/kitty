from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import (
    devices_keyboard,
    main_keyboard,
    support_keyboard,
    trial_keyboard,
)
from app.database.models import User
from app.services.subscription import SubscriptionError, SubscriptionService

router = Router(name="user")


def _format_remaining(expires_at: datetime) -> str:
    """Форматирует оставшееся время подписки."""

    remaining = max(
        0,
        int((expires_at - datetime.now(timezone.utc)).total_seconds()),
    )

    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    parts: list[str] = []
    if days:
        parts.append(f"{days} д.")
    if hours:
        parts.append(f"{hours} ч.")
    if minutes or not parts:
        parts.append(f"{minutes} мин.")

    return " ".join(parts)


def _username(user: User) -> str:
    return f"@{user.username}" if user.username else "—"


async def _send_subscription_info(
    message: Message,
    user: User,
    service: SubscriptionService,
) -> None:
    data = await service.get_subscription_info(user)

    if data is None:
        await message.answer(
            "твоя подписка не найдена в системе.\n\n"
            "если это ошибка, напиши в поддержку:",
            reply_markup=support_keyboard(),
        )
        return

    expires_at = data["expires_at"]
    if not isinstance(expires_at, datetime):
        await message.answer(
            "не удалось получить срок действия подписки.",
            reply_markup=main_keyboard(),
        )
        return

    devices = data["devices"]
    device_limit = data["device_limit"]
    if not isinstance(devices, list) or not isinstance(device_limit, int):
        await message.answer(
            "не удалось получить информацию об устройствах.",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        "📊 твоя подписка\n\n"
        f"📌 статус: {data['status']}\n"
        f"⏳ осталось: {_format_remaining(expires_at)}\n"
        f"📱 устройства: {len(devices)} / {device_limit}\n\n"
        "🔗 json-подписка:\n"
        f"{data['subscription_url']}",
        reply_markup=main_keyboard(),
    )


@router.message(CommandStart())
async def start(
    message: Message,
    subscription_service: SubscriptionService,
) -> None:
    user = await subscription_service.get_user(
        message.from_user.id
    )

    if user is not None:
        await _send_subscription_info(
            message,
            user,
            subscription_service,
        )
        return

    await message.answer(
        "привет 👋\n\n"
        "добро пожаловать в kitty vpn 🐈\n\n"
        "получи тестовый доступ и попробуй vpn.",
        reply_markup=trial_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "start_trial")
async def start_trial(
    callback: CallbackQuery,
    subscription_service: SubscriptionService,
) -> None:
    await callback.answer("создаю trial...")

    try:
        user = await subscription_service.grant_trial(
            tg_id=callback.from_user.id,
            username=callback.from_user.username,
        )
    except SubscriptionError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.message.answer(
        "🎁 trial активирован!\n\n"
        "🔗 json-подписка:\n"
        f"{user.subscription_url}\n\n"
        "добавь эту ссылку в happ или другой "
        "поддерживаемый vpn-клиент.",
        reply_markup=main_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "connect")
async def connect(
    callback: CallbackQuery,
    subscription_service: SubscriptionService,
) -> None:
    await callback.answer()

    user = await subscription_service.get_user(
        callback.from_user.id
    )
    if user is None:
        await callback.answer(
            "сначала получи trial",
            show_alert=True,
        )
        return

    await _send_subscription_info(
        callback.message,
        user,
        subscription_service,
    )


@router.callback_query(lambda callback: callback.data == "devices")
async def devices(
    callback: CallbackQuery,
    subscription_service: SubscriptionService,
) -> None:
    await callback.answer()

    user = await subscription_service.get_user(
        callback.from_user.id
    )
    if user is None:
        await callback.answer(
            "сначала получи trial",
            show_alert=True,
        )
        return

    data = await subscription_service.get_devices(user)
    if data is None:
        await callback.answer(
            "подписка не найдена",
            show_alert=True,
        )
        return

    devices_list, limit = data
    if devices_list:
        device_text = "\n".join(
            f"• {device.get('deviceModel') or 'неизвестное устройство'}"
            for device in devices_list
        )
    else:
        device_text = "нет зарегистрированных устройств"

    await callback.message.answer(
        "📱 устройства\n\n"
        f"используется: {len(devices_list)} / {limit}\n\n"
        f"{device_text}",
        reply_markup=devices_keyboard(),
    )


@router.callback_query(
    lambda callback: callback.data == "delete_all_hwid"
)
async def delete_all_hwid(
    callback: CallbackQuery,
    subscription_service: SubscriptionService,
) -> None:
    await callback.answer("удаляю устройства...")

    user = await subscription_service.get_user(
        callback.from_user.id
    )
    if user is None:
        await callback.answer(
            "подписка не найдена",
            show_alert=True,
        )
        return

    deleted = await subscription_service.delete_all_devices(user)
    if not deleted:
        await callback.message.answer(
            "❌ подписка не найдена.",
            reply_markup=main_keyboard(),
        )
        return

    await callback.message.answer(
        "✅ все зарегистрированные устройства удалены.\n\n"
        "теперь можно подключить устройство заново.",
        reply_markup=main_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "back_to_menu")
async def back_to_menu(
    callback: CallbackQuery,
    subscription_service: SubscriptionService,
) -> None:
    await callback.answer()

    user = await subscription_service.get_user(
        callback.from_user.id
    )
    if user is None:
        return

    await _send_subscription_info(
        callback.message,
        user,
        subscription_service,
    )


@router.callback_query(lambda callback: callback.data == "purchase")
async def purchase(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "💳 подписка\n\n"
        "3 устройства — 80 ₽ / месяц.\n\n"
        "для покупки или продления напиши админу:",
        reply_markup=support_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "support")
async def support(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "🆘 поддержка\n\n"
        "если что-то не работает или есть вопрос — "
        "напиши админу:",
        reply_markup=support_keyboard(),
    )
