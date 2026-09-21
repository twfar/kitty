import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import BOT_TOKEN, ADMIN_ID, TRIAL_HOURS
from db import init_db, get_user, create_user, update_user
from xui import (
    create_client,
    create_paid_client,
    renew_client_by_sub_id,
    ban_client_by_sub_id,
    find_client,
    get_inbounds,
    get_hwid_devices,
    delete_all_hwid_devices,
)

dp = Dispatcher()

ADMIN_URL = "https://t.me/kittyvpnoff?direct"
CHANNEL = "@kittyvpnoff"
SUPPORT_URL = "https://t.me/kittyvpn_support_robot"
PRIVACY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
OFFER_URL = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"

admin_action_waiting = {}


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 подключиться",
                    callback_data="connect",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 устройства",
                    callback_data="devices",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 купить / продлить",
                    callback_data="purchase",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆘 поддержка",
                    callback_data="support",
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ о сервисе",
                    callback_data="about_service",
                )
            ],
        ]
    )


def trial_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 начать trial",
                    callback_data="start_trial",
                )
            ]
        ]
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 привязать подписку",
                    callback_data="admin_bind_subscription",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 создать оплаченного юзера",
                    callback_data="admin_create_paid",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 действия с пользователем",
                    callback_data="admin_user_actions",
                )
            ],
        ]
    )


def admin_user_actions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 продлить на 30 дней",
                    callback_data="admin_renew",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⛔ забанить",
                    callback_data="admin_ban",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 назад",
                    callback_data="admin_back",
                )
            ],
        ]
    )


def find_client_by_sub_id(sub_id):
    inbounds = get_inbounds()

    for inbound in inbounds:
        settings = inbound.get("settings", {})
        clients = settings.get("clients", [])

        for client in clients:
            if client.get("subId") == sub_id:
                return client

    return None


def format_remaining(expires_at: int) -> str:
    remaining = max(0, expires_at - int(time.time()))

    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes = remaining // 60

    parts = []

    if days:
        parts.append(f"{days} д.")

    if hours:
        parts.append(f"{hours} ч.")

    if minutes or not parts:
        parts.append(f"{minutes} мин.")

    return " ".join(parts)


async def get_subscription_data(user):
    client = find_client(user["email"])

    if not client:
        return None

    sub_id = client.get("subId")
    expiry_time = client.get("expiryTime")

    if not sub_id or not expiry_time:
        return None

    subscription_url = (
        f"https://87.121.82.175:2096/jsnn/{sub_id}"
    )

    expires_at = int(expiry_time) // 1000

    await update_user(
        tg_id=user["tg_id"],
        username=user["username"],
        email=user["email"],
        sub_id=sub_id,
        subscription_url=subscription_url,
        status=user["status"],
        created_at=user["created_at"],
        expires_at=expires_at,
    )

    return {
        "subscription_url": subscription_url,
        "expires_at": expires_at,
        "client": client,
    }


async def send_subscription_info(message: Message, user):
    data = await get_subscription_data(user)

    if not data:
        await message.answer(
            "твоя подписка не найдена в системе.\n\n"
            "если это ошибка, напиши в поддержку:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💬 написать админу",
                            url=ADMIN_URL,
                        )
                    ]
                ]
            ),
        )
        return

    client = data["client"]

    devices_limit = client.get("limitHwid", 0)

    try:
        devices = get_hwid_devices(user["email"])
        devices_used = len(devices)
    except Exception:
        devices_used = 0

    await message.answer(
        "📊 твоя подписка\n\n"
        f"📌 статус: {user['status']}\n"
        f"⏳ осталось: {format_remaining(data['expires_at'])}\n"
        f"📱 устройства: {devices_used} / {devices_limit}\n\n"
        "🔗 json-подписка:\n"
        f"{data['subscription_url']}",
        reply_markup=main_keyboard(),
    )


@dp.message(CommandStart())
async def start(message: Message):
    user = await get_user(message.from_user.id)

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "—"
    )

    sub_id = user["sub_id"] if user else "—"

    await message.bot.send_message(
        ADMIN_ID,
        "🚀 новый /start\n\n"
        f"👤 username: {username}\n"
        f"🆔 telegram id: `{message.from_user.id}`\n"
        f"🔗 sub id: `{sub_id}`",
    )

    if user:
        await send_subscription_info(message, user)
        return

    await message.answer(
        "привет 👋\n\n"
        "добро пожаловать в kitty vpn 🐈\n\n"
        f"📢 канал: {CHANNEL}\n\n"
        f"🎁 тестовый доступ на {TRIAL_HOURS} часов.",
        reply_markup=trial_keyboard(),
    )


@dp.message(Command("kittyadmin"))
async def kitty_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "—"
        )

        await message.bot.send_message(
            ADMIN_ID,
            "⚠️ кто-то вызвал /kittyadmin\n\n"
            f"👤 username: {username}\n"
            f"🆔 telegram id: `{message.from_user.id}`",
        )

        return

    await message.answer(
        "⚙️ админ-панель\n\n"
        "выбери действие:",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(lambda callback: callback.data == "start_trial")
async def start_trial(callback: CallbackQuery):
    tg_id = callback.from_user.id
    username = callback.from_user.username or "unknown"

    user = await get_user(tg_id)

    if user:
        existing_client = find_client(user["email"])

        if existing_client:
            await callback.answer(
                "у тебя уже есть активная подписка",
                show_alert=True,
            )

            await send_subscription_info(
                callback.message,
                user,
            )
            return

    await callback.answer("создаю trial...")

    email = f"tg_{tg_id}"

    client = create_client(
        tg_id=tg_id,
        email=email,
        expiry_hours=TRIAL_HOURS,
        group="trial",
    )

    created_at = int(time.time())
    expires_at = client["expiry_time"] // 1000

    if user:
        await update_user(
            tg_id=tg_id,
            username=username,
            email=email,
            sub_id=client["sub_id"],
            subscription_url=client["subscription_url"],
            status="trial",
            created_at=created_at,
            expires_at=expires_at,
        )
    else:
        await create_user(
            tg_id=tg_id,
            username=username,
            email=email,
            sub_id=client["sub_id"],
            subscription_url=client["subscription_url"],
            status="trial",
            created_at=created_at,
            expires_at=expires_at,
        )

    admin_username = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else "—"
    )

    await callback.bot.send_message(
        ADMIN_ID,
        "🎁 подключён trial\n\n"
        f"👤 username: {admin_username}\n"
        f"🆔 telegram id: `{tg_id}`\n"
        f"🔗 sub id: `{client['sub_id']}`",
    )

    await callback.message.answer(
        "🎁 trial активирован!\n\n"
        "🔗 json-подписка:\n"
        f"{client['subscription_url']}\n\n"
        "добавь эту ссылку в happ или другой "
        "поддерживаемый vpn-клиент.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(lambda callback: callback.data == "connect")
async def connect(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)

    if not user:
        await callback.answer(
            "сначала получи trial",
            show_alert=True,
        )
        return

    await callback.answer()

    await send_subscription_info(
        callback.message,
        user,
    )


@dp.callback_query(lambda callback: callback.data == "devices")
async def devices(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)

    if not user:
        await callback.answer(
            "сначала получи trial",
            show_alert=True,
        )
        return

    client = find_client(user["email"])

    if not client:
        await callback.answer(
            "подписка не найдена",
            show_alert=True,
        )
        return

    try:
        devices = get_hwid_devices(user["email"])
    except Exception:
        logging.exception("failed to get hwid devices")

        await callback.answer(
            "ошибка получения устройств",
            show_alert=True,
        )
        return

    limit = client.get("limitHwid", 0)

    await callback.answer()

    if devices:
        device_text = "\n".join(
            f"• {device.get('deviceModel') or 'неизвестное устройство'}"
            for device in devices
        )
    else:
        device_text = "нет зарегистрированных устройств"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 удалить все устройства",
                    callback_data="delete_all_hwid",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 назад",
                    callback_data="back_to_menu",
                )
            ],
        ]
    )

    await callback.message.answer(
        "📱 устройства\n\n"
        f"используется: {len(devices)} / {limit}\n\n"
        f"{device_text}",
        reply_markup=keyboard,
    )


@dp.callback_query(lambda callback: callback.data == "delete_all_hwid")
async def delete_all_hwid(callback: CallbackQuery):
    user = await get_user(callback.from