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

BOT_VERSION = "1.0.6"

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
        f"⚙️ админ-панель\n\nверсия бота: {BOT_VERSION}\n\n"
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
    user = await get_user(callback.from_user.id)

    if not user:
        await callback.answer(
            "подписка не найдена",
            show_alert=True,
        )
        return

    await callback.answer("удаляю устройства...")

    try:
        delete_all_hwid_devices(user["email"])
    except Exception:
        logging.exception("failed to delete hwids")

        await callback.message.answer(
            "❌ не удалось удалить устройства.",
            reply_markup=main_keyboard(),
        )
        return

    await callback.message.answer(
        "✅ все зарегистрированные устройства удалены.\n\n"
        "теперь можно подключить устройство заново.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(lambda callback: callback.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)

    if not user:
        await callback.answer()
        return

    await callback.answer()

    await send_subscription_info(
        callback.message,
        user,
    )


@dp.callback_query(lambda callback: callback.data == "purchase")
async def purchase(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "💳 подписка\n\n"
        "3 устройства — 80 ₽ / месяц.\n\n"
        "для покупки или продления напиши админу:",
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


@dp.callback_query(lambda callback: callback.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "🆘 поддержка\n\n"
        "если что-то не работает или есть вопрос — "
        "напиши админу:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 написать в поддержку",
                        url=SUPPORT_URL,
                    )
                ]
            ]
        ),
    )


@dp.callback_query(lambda callback: callback.data == "about_service")
async def about_service(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "ℹ️ о сервисе\\n\\n"
        "🐈 kitty vpn — сервис для безопасного подключения к интернету.\\n\\n"
        "📄 политика конфиденциальности:\\n"
        f"{PRIVACY_URL}\\n\\n"
        "📜 пользовательское соглашение:\\n"
        f"{OFFER_URL}",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_bind_subscription"
)
async def admin_bind_subscription(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    admin_action_waiting[callback.from_user.id] = "bind"

    await callback.answer()

    await callback.message.answer(
        "🔗 привязка подписки\n\n"
        "отправь одной строкой:\n"
        "`telegram_id sub_id`\n\n"
        "пример:\n"
        "`6682540155 "
        "99e9195c-75ce-4fa8-b313-a2eb3ebf7940`"
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_create_paid"
)
async def admin_create_paid(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    admin_action_waiting[callback.from_user.id] = "create_paid"

    await callback.answer()

    await callback.message.answer(
        "💳 создание оплаченного пользователя\n\n"
        "отправь telegram id пользователя.\n\n"
        "пример:\n"
        "`6682540155`"
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_user_actions"
)
async def admin_user_actions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    await callback.answer()

    await callback.message.answer(
        "👤 действия с пользователем\n\n"
        "выбери действие:",
        reply_markup=admin_user_actions_keyboard(),
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_renew"
)
async def admin_renew(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    admin_action_waiting[callback.from_user.id] = "renew"

    await callback.answer()

    await callback.message.answer(
        "🔄 продление\n\n"
        "отправь sub_id пользователя.\n\n"
        "пример:\n"
        "`99e9195c-75ce-4fa8-b313-a2eb3ebf7940`"
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_ban"
)
async def admin_ban(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    admin_action_waiting[callback.from_user.id] = "ban"

    await callback.answer()

    await callback.message.answer(
        "⛔ бан пользователя\n\n"
        "отправь sub_id пользователя.\n\n"
        "пример:\n"
        "`99e9195c-75ce-4fa8-b313-a2eb3ebf7940`"
    )


@dp.callback_query(
    lambda callback: callback.data == "admin_back"
)
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "доступ запрещён",
            show_alert=True,
        )
        return

    admin_action_waiting.pop(
        callback.from_user.id,
        None,
    )

    await callback.answer()

    await callback.message.answer(
        "⚙️ админ-панель\n\n"
        "выбери действие:",
        reply_markup=admin_keyboard(),
    )


@dp.message()
async def admin_message_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    action = admin_action_waiting.get(
        message.from_user.id
    )

    if not action:
        return

    if not message.text:
        return

    text = message.text.strip()

    if action == "bind":
        parts = text.split()

        if len(parts) != 2:
            await message.answer(
                "❌ формат неправильный.\n\n"
                "нужно:\n"
                "`telegram_id sub_id`"
            )
            return

        try:
            tg_id = int(parts[0])
        except ValueError:
            await message.answer(
                "❌ telegram id должен быть числом."
            )
            return

        sub_id = parts[1]

        client = find_client_by_sub_id(sub_id)

        if not client:
            await message.answer(
                "❌ подписка с таким sub_id "
                "не найдена в 3x-ui."
            )
            return

        email = client.get("email")

        if not email:
            await message.answer(
                "❌ у подписки отсутствует email."
            )
            return

        expires_at = (
            int(client.get("expiryTime", 0))
            // 1000
        )

        subscription_url = (
            f"https://87.121.82.175:2096/jsnn/{sub_id}"
        )

        existing_user = await get_user(tg_id)

        if existing_user:
            await update_user(
                tg_id=tg_id,
                username=existing_user["username"],
                email=email,
                sub_id=sub_id,
                subscription_url=subscription_url,
                status="paid",
                created_at=existing_user["created_at"],
                expires_at=expires_at,
            )
        else:
            await create_user(
                tg_id=tg_id,
                username="unknown",
                email=email,
                sub_id=sub_id,
                subscription_url=subscription_url,
                status="paid",
                created_at=int(time.time()),
                expires_at=expires_at,
            )

        admin_action_waiting.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "✅ подписка привязана\n\n"
            f"👤 telegram id: `{tg_id}`\n"
            f"📧 email: `{email}`\n"
            f"🔗 sub_id: `{sub_id}`\n"
            f"⏳ осталось: {format_remaining(expires_at)}",
            reply_markup=admin_keyboard(),
        )

        return

    if action == "create_paid":
        try:
            tg_id = int(text)
        except ValueError:
            await message.answer(
                "❌ telegram id должен быть числом."
            )
            return

        existing_user = await get_user(tg_id)

        if existing_user:
            await message.answer(
                "❌ этот telegram id уже есть "
                "в базе."
            )
            return

        email = f"tg_{tg_id}"

        existing_client = find_client(email)

        if existing_client:
            await message.answer(
                "❌ клиент с таким telegram id "
                "уже существует в 3x-ui."
            )
            return

        try:
            client = create_paid_client(
                tg_id=tg_id,
                days=30,
            )
        except Exception as e:
            logging.exception(
                "failed to create paid client"
            )

            await message.answer(
                f"❌ ошибка создания пользователя:\n"
                f"`{e}`"
            )
            return

        created_at = int(time.time())
        expires_at = (
            client["expiry_time"] // 1000
        )

        subscription_url = client[
            "subscription_url"
        ]

        await create_user(
            tg_id=tg_id,
            username="unknown",
            email=client["email"],
            sub_id=client["sub_id"],
            subscription_url=subscription_url,
            status="paid",
            created_at=created_at,
            expires_at=expires_at,
        )

        admin_action_waiting.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "✅ оплаченный пользователь создан\n\n"
            f"👤 telegram id: `{tg_id}`\n"
            f"📧 email: `{client['email']}`\n"
            f"🔗 sub_id: `{client['sub_id']}`\n"
            f"📱 устройств: 3\n"
            f"⏳ срок: 30 дней\n\n"
            "🔗 json-подписка:\n"
            f"{subscription_url}",
            reply_markup=admin_keyboard(),
        )

        return

    if action == "renew":
        sub_id = text

        client = find_client_by_sub_id(sub_id)

        if not client:
            await message.answer(
                "❌ подписка с таким sub_id "
                "не найдена."
            )
            return

        try:
            updated_client = renew_client_by_sub_id(
                sub_id=sub_id,
                days=30,
            )
        except Exception as e:
            logging.exception(
                "failed to renew client"
            )

            await message.answer(
                f"❌ ошибка продления:\n"
                f"`{e}`"
            )
            return

        expires_at = (
            int(updated_client.get("expiryTime", 0))
            // 1000
        )

        email = updated_client.get("email")

        if email:
            tg_id_value = None

            inbounds = get_inbounds()

            for inbound in inbounds:
                settings = inbound.get(
                    "settings",
                    {},
                )

                for xui_client in settings.get(
                    "clients",
                    [],
                ):
                    if xui_client.get(
                        "email"
                    ) == email:
                        tg_id_value = xui_client.get(
                            "tgId"
                        )
                        break

                if tg_id_value:
                    break

            if tg_id_value:
                try:
                    for_tg = int(tg_id_value)
                except (
                    TypeError,
                    ValueError,
                ):
                    for_tg = None

                if for_tg:
                    user = await get_user(for_tg)

                    if user:
                        await update_user(
                            tg_id=for_tg,
                            username=user["username"],
                            email=email,
                            sub_id=sub_id,
                            subscription_url=(
                                f"https://87.121.82.175:2096/"
                                f"jsnn/{sub_id}"
                            ),
                            status="paid",
                            created_at=user[
                                "created_at"
                            ],
                            expires_at=expires_at,
                        )

        admin_action_waiting.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "✅ подписка продлена на 30 дней\n\n"
            f"🔗 sub_id: `{sub_id}`\n"
            f"⏳ осталось: "
            f"{format_remaining(expires_at)}",
            reply_markup=admin_keyboard(),
        )

        return

    if action == "ban":
        sub_id = text

        client = find_client_by_sub_id(sub_id)

        if not client:
            await message.answer(
                "❌ подписка с таким sub_id "
                "не найдена."
            )
            return

        try:
            ban_client_by_sub_id(
                sub_id=sub_id,
            )
        except Exception as e:
            logging.exception(
                "failed to ban client"
            )

            await message.answer(
                f"❌ ошибка бана:\n"
                f"`{e}`"
            )
            return

        email = client.get("email")

        if email:
            inbounds = get_inbounds()

            tg_id_value = None

            for inbound in inbounds:
                settings = inbound.get(
                    "settings",
                    {},
                )

                for xui_client in settings.get(
                    "clients",
                    [],
                ):
                    if xui_client.get(
                        "email"
                    ) == email:
                        tg_id_value = xui_client.get(
                            "tgId"
                        )
                        break

                if tg_id_value:
                    break

            if tg_id_value:
                try:
                    tg_id = int(tg_id_value)
                    user = await get_user(tg_id)

                    if user:
                        await update_user(
                            tg_id=tg_id,
                            username=user["username"],
                            email=user["email"],
                            sub_id=user["sub_id"],
                            subscription_url=user[
                                "subscription_url"
                            ],
                            status="banned",
                            created_at=user[
                                "created_at"
                            ],
                            expires_at=user[
                                "expires_at"
                            ],
                        )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

        admin_action_waiting.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "⛔ пользователь забанен\n\n"
            f"🔗 sub_id: `{sub_id}`",
            reply_markup=admin_keyboard(),
        )

        return


async def main():
    logging.basicConfig(
        level=logging.INFO
    )

    await init_db()

    bot = Bot(
        token=BOT_TOKEN
    )

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
