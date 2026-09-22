import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

from config import BOT_TOKEN, ADMIN_ID, TRIAL_HOURS
from db import init_db, get_user, create_user, update_user, get_promo, create_promo, use_promo, get_setting, set_setting, delete_setting
from xui import (
    create_client,
    renew_client_by_sub_id,
    ban_client_by_sub_id,
    find_client,
    get_inbounds,
    get_hwid_devices,
    delete_all_hwid_devices,
)

dp = Dispatcher()


DEFAULT_SETTINGS = {
    "main_text": "🐈 главное меню",
    "main_photo": "",
    "main_button_subscription": "🔗 подписка",
    "main_button_promo": "🎟 промокод",
    "main_button_support": "🆘 поддержка",
    "main_button_about": "ℹ️ о сервисе",
    "subscription_text": "🔗 твоя подписка",
    "subscription_photo": "",
    "subscription_button_copy": "📋 скопировать ссылку",
    "subscription_button_devices": "📱 устройства",
    "subscription_button_purchase": "💳 купить / продлить",
    "subscription_button_back": "🔙 назад",
}

CUSTOM_BUTTONS = {
    "main_button_subscription": "подписка",
    "main_button_promo": "промокод",
    "main_button_support": "поддержка",
    "main_button_about": "о сервисе",
    "subscription_button_copy": "скопировать ссылку",
    "subscription_button_devices": "устройства",
    "subscription_button_purchase": "купить / продлить",
    "subscription_button_back": "назад",
}


async def get_settings():
    return {key: await get_setting(key, default) for key, default in DEFAULT_SETTINGS.items()}


async def trial_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 начать trial", callback_data="start_trial", style="primary")],
        [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 привязать подписку", callback_data="admin_bind_subscription", style="primary")],
        [InlineKeyboardButton(text="🔄 продлить подписку", callback_data="admin_renew")],
        [InlineKeyboardButton(text="🎟 создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="🎨 кастомизация", callback_data="customization")],
        [InlineKeyboardButton(text="👤 действия с пользователем", callback_data="admin_user_actions")],
    ])


def admin_user_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 продлить на 30 дней", callback_data="admin_renew", style="primary")],
        [InlineKeyboardButton(text="⛔ забанить", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
    ])


def find_client_by_sub_id(sub_id):
    for inbound in get_inbounds():
        for client in inbound.get("settings", {}).get("clients", []):
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
    subscription_url = f"https://87.121.82.175:2096/jsnn/{sub_id}"
    expires_at = int(expiry_time) // 1000
    await update_user(
        tg_id=user["tg_id"], username=user["username"], email=user["email"],
        sub_id=sub_id, subscription_url=subscription_url, status=user["status"],
        created_at=user["created_at"], expires_at=expires_at,
    )
    return {"subscription_url": subscription_url, "expires_at": expires_at, "client": client}


async def send_subscription_info(message: Message, user):
    await render_subscription_menu(message, user, replace=False)


@dp.message(CommandStart())
async def start(message: Message):
    user = await get_user(message.from_user.id)
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    sub_id = user["sub_id"] if user else "—"
    if message.from_user.id != ADMIN_ID:
        try:
            await message.bot.send_message(
                ADMIN_ID,
                "🚀 новый /start\n\n"
                f"👤 username: {username}\n"
                f"🆔 telegram id: `{message.from_user.id}`\n"
                f"🔗 sub id: `{sub_id}`",
            )
        except Exception:
            logging.exception("failed to notify admin about /start")

    if user:
        await render_main_menu(message)
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
        username = f"@{message.from_user.username}" if message.from_user.username else "—"
        await message.bot.send_message(
            ADMIN_ID,
            "⚠️ кто-то вызвал /kittyadmin\n\n"
            f"👤 username: {username}\n"
            f"🆔 telegram id: `{message.from_user.id}`",
        )
        return
    await message.answer("⚙️ админ-панель\n\nвыбери действие:", reply_markup=admin_keyboard())


@dp.callback_query(lambda c: c.data == "start_trial")
async def start_trial(callback: CallbackQuery):
    tg_id = callback.from_user.id
    username = callback.from_user.username or "unknown"
    user = await get_user(tg_id)
    if user and find_client(user["email"]):
        await callback.answer("у тебя уже есть активная подписка", show_alert=True)
        await render_subscription_menu(callback.message, user, replace=True)
        return
    await callback.answer("создаю trial...")
    email = f"tg_{tg_id}"
    client = create_client(tg_id=tg_id, email=email, expiry_hours=TRIAL_HOURS, group="trial")
    created_at = int(time.time())
    expires_at = client["expiry_time"] // 1000
    values = dict(
        tg_id=tg_id, username=username, email=email, sub_id=client["sub_id"],
        subscription_url=client["subscription_url"], status="trial",
        created_at=created_at, expires_at=expires_at,
    )
    if user:
        await update_user(**values)
    else:
        await create_user(**values)
    admin_username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    await callback.bot.send_message(
        ADMIN_ID,
        "🎁 подключён trial\n\n"
        f"👤 username: {admin_username}\n"
        f"🆔 telegram id: `{tg_id}`\n"
        f"🔗 sub id: `{client['sub_id']}`",
    )
    await callback.message.edit_text(
        "🎁 trial активирован!\n\n"
        "🔗 json-подписка:\n"
        f"{client['subscription_url']}\n\n"
        "добавь эту ссылку в happ или другой поддерживаемый vpn-клиент.",
        reply_markup=await main_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "subscription")
async def subscription(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("сначала получи trial", show_alert=True)
        return
    await callback.answer()
    await send_subscription_info(callback.message, user)


@dp.callback_query(lambda c: c.data == "devices")
async def devices(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("сначала получи trial", show_alert=True)
        return
    client = find_client(user["email"])
    if not client:
        await callback.answer("подписка не найдена", show_alert=True)
        return
    try:
        device_list = get_hwid_devices(user["email"])
    except Exception:
        logging.exception("failed to get hwid devices")
        await callback.answer("ошибка получения устройств", show_alert=True)
        return
    limit = client.get("limitHwid", 0)
    text = "\n".join(f"• {d.get('deviceModel') or 'неизвестное устройство'}" for d in device_list) if device_list else "нет зарегистрированных устройств"
    await callback.answer()
    await callback.message.edit_text(
        "📱 устройства\n\n"
        f"используется: {len(device_list)} / {limit}\n\n{text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 удалить все устройства", callback_data="delete_all_hwid", style="primary")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_subscription")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "delete_all_hwid")
async def delete_all_hwid(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("подписка не найдена", show_alert=True)
        return
    await callback.answer("удаляю устройства...")
    try:
        delete_all_hwid_devices(user["email"])
    except Exception:
        logging.exception("failed to delete hwids")
        await callback.message.edit_text("❌ не удалось удалить устройства.", reply_markup=await main_keyboard())
        return
    await callback.message.edit_text(
        "✅ все зарегистрированные устройства удалены.\n\nтеперь можно подключить устройство заново.",
        reply_markup=await main_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "back_to_subscription")
async def back_to_subscription(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("сначала получи trial", show_alert=True)
        return
    await callback.answer()
    await send_subscription_info(callback.message, user)


@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    await render_main_menu(callback.message, replace=True)


@dp.callback_query(lambda c: c.data == "purchase")
async def purchase(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "💳 подписка\n\n3 устройства — 80 ₽ / месяц.\n\nдля покупки или продления напиши админу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 написать админу", url=ADMIN_URL, style="primary")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_subscription")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🆘 поддержка\n\nесли что-то не работает или есть вопрос — создай обращение в тикет-системе:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎫 открыть тикет", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "about_service")
async def about_service(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ о сервисе\n\nознакомиться с документами сервиса:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 политика конфиденциальности", url=PRIVACY_URL, style="primary")],
            [InlineKeyboardButton(text="📄 пользовательское соглашение", url=OFFER_URL)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
        ]),
    )



@dp.callback_query(lambda c: c.data == "promo")
async def promo(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("сначала получи trial", show_alert=True)
        return

    user_action_waiting[callback.from_user.id] = "promo"
    await callback.answer()
    await callback.message.edit_text(
        "🎟 промокод\n\nотправь промокод одним сообщением.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")]
        ]),
    )




@dp.callback_query(lambda c: c.data == "customization")
async def customization(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting.pop(callback.from_user.id, None)
    await callback.answer()
    await callback.message.edit_text("🎨 кастомизация\n\nвыбери меню:", reply_markup=customization_keyboard())


@dp.callback_query(lambda c: c.data in ("custom_main", "custom_subscription"))
async def custom_section(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main" else "subscription"
    await callback.answer()
    await callback.message.edit_text(
        f"🎨 {'главное меню' if section == 'main' else 'меню подписки'}\n\nвыбери, что изменить:",
        reply_markup=custom_section_keyboard(section),
    )


@dp.callback_query(lambda c: c.data in ("custom_main_text", "custom_subscription_text"))
async def custom_text_start(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main_text" else "subscription"
    admin_action_waiting[callback.from_user.id] = f"custom_text:{section}"
    current = (await get_settings())[f"{section}_text"]
    await callback.answer()
    await callback.message.edit_text(
        f"✏️ текст {'главного меню' if section == 'main' else 'меню подписки'}\n\nтекущий:\n{current}\n\nотправь новый текст.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ вернуть стандартный", callback_data=f"custom_{section}_reset_text")],
            [InlineKeyboardButton(text="🔙 назад", callback_data=f"custom_{section}")],
        ]),
    )


@dp.callback_query(lambda c: c.data in ("custom_main_photo", "custom_subscription_photo"))
async def custom_photo_start(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main_photo" else "subscription"
    admin_action_waiting[callback.from_user.id] = f"custom_photo:{section}"
    await callback.answer()
    await callback.message.edit_text(
        "🖼 отправь новое фото одним сообщением.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 удалить фото", callback_data=f"custom_{section}_delete_photo")],
            [InlineKeyboardButton(text="🔙 назад", callback_data=f"custom_{section}")],
        ]),
    )


@dp.callback_query(lambda c: c.data in ("custom_main_delete_photo", "custom_subscription_delete_photo"))
async def custom_delete_photo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main_delete_photo" else "subscription"
    await delete_setting(f"{section}_photo")
    admin_action_waiting.pop(callback.from_user.id, None)
    await callback.answer("фото удалено")
    await callback.message.edit_text("🧹 фото удалено.", reply_markup=custom_section_keyboard(section))


@dp.callback_query(lambda c: c.data in ("custom_main_buttons", "custom_subscription_buttons"))
async def custom_buttons(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main_buttons" else "subscription"
    await callback.answer()
    await callback.message.edit_text("🔘 выбери кнопку для переименования:", reply_markup=custom_buttons_keyboard(section))


@dp.callback_query(lambda c: c.data.startswith("custom_button:"))
async def custom_button_start(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    if key not in CUSTOM_BUTTONS:
        await callback.answer("неизвестная кнопка", show_alert=True)
        return
    admin_action_waiting[callback.from_user.id] = f"custom_button:{key}"
    current = (await get_settings())[key]
    await callback.answer()
    section = "main" if key.startswith("main_") else "subscription"
    await callback.message.edit_text(
        f"🔘 текущий текст:\n{current}\n\nотправь новый текст.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ вернуть стандартный", callback_data=f"custom_reset_button:{key}")],
            [InlineKeyboardButton(text="🔙 назад", callback_data=f"custom_{section}_buttons")],
        ]),
    )


@dp.callback_query(lambda c: c.data.startswith("custom_reset_button:"))
async def custom_reset_button(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    await set_setting(key, DEFAULT_SETTINGS[key])
    admin_action_waiting.pop(callback.from_user.id, None)
    section = "main" if key.startswith("main_") else "subscription"
    await callback.answer("стандарт восстановлен")
    await callback.message.edit_text("↩️ стандартный текст восстановлен.", reply_markup=custom_buttons_keyboard(section))


@dp.callback_query(lambda c: c.data in ("custom_main_reset_text", "custom_subscription_reset_text"))
async def custom_reset_text(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    section = "main" if callback.data == "custom_main_reset_text" else "subscription"
    await set_setting(f"{section}_text", DEFAULT_SETTINGS[f"{section}_text"])
    admin_action_waiting.pop(callback.from_user.id, None)
    await callback.answer("стандарт восстановлен")
    await callback.message.edit_text("↩️ стандартный текст восстановлен.", reply_markup=custom_section_keyboard(section))


@dp.callback_query(lambda c: c.data == "custom_preview")
async def custom_preview(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    await callback.answer()
    s = await get_settings()
    await callback.message.edit_text(
        f"👀 предпросмотр\n\nглавное меню: {'🖼 есть фото' if s['main_photo'] else 'без фото'}\nтекст: {s['main_text']}\n\n"
        f"меню подписки: {'🖼 есть фото' if s['subscription_photo'] else 'без фото'}\nтекст: {s['subscription_text']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 показать главное", callback_data="custom_preview_main")],
            [InlineKeyboardButton(text="🔗 показать подписку", callback_data="custom_preview_sub")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="customization")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "custom_preview_main")
async def custom_preview_main(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    await callback.answer()
    await render_main_menu(callback.message, replace=True)


@dp.callback_query(lambda c: c.data == "custom_preview_sub")
async def custom_preview_sub(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("у админа нет привязанной подписки для предпросмотра", show_alert=True)
        return
    await callback.answer()
    await render_subscription_menu(callback.message, user, replace=True)


@dp.callback_query(lambda c: c.data == "admin_create_promo")
async def admin_create_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    admin_action_waiting[callback.from_user.id] = "create_promo"
    await callback.answer()
    await callback.message.edit_text(
        "🎟 создание промокода\n\n"
        "отправь одной строкой:\n"
        "`код дни лимит`\n\n"
        "пример:\n"
        "`KITTY7 7 10`\n\n"
        "лимит 0 = без ограничений.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_bind_subscription")
async def admin_bind_subscription(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting[callback.from_user.id] = "bind"
    await callback.answer()
    await callback.message.edit_text(
        "🔗 привязка подписки\n\nотправь одной строкой:\n`telegram_id sub_id`\n\nпример:\n`6682540155 99e9195c-75ce-4fa8-b313-a2eb3ebf7940`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_user_actions")
async def admin_user_actions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text("👤 действия с пользователем\n\nвыбери действие:", reply_markup=admin_user_actions_keyboard())


@dp.callback_query(lambda c: c.data == "admin_renew")
async def admin_renew(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting[callback.from_user.id] = "renew"
    await callback.answer()
    await callback.message.edit_text(
        "🔄 продление\n\n"
        "отправь одной строкой:\n"
        "`sub_id дни`\n\n"
        "например:\n"
        "`99e9195c-75ce-4fa8-b313-a2eb3ebf7940 30`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_user_actions")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_ban")
async def admin_ban(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting[callback.from_user.id] = "ban"
    await callback.answer()
    await callback.message.edit_text(
        "⛔ бан пользователя\n\nотправь sub_id пользователя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_user_actions")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting.pop(callback.from_user.id, None)
    await callback.answer()
    await callback.message.edit_text("⚙️ админ-панель\n\nвыбери действие:", reply_markup=admin_keyboard())


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.photo)
async def admin_custom_photo_message(message: Message):
    action = admin_action_waiting.get(message.from_user.id)
    if not action or not action.startswith("custom_photo:"):
        return
    section = action.split(":", 1)[1]
    await set_setting(f"{section}_photo", message.photo[-1].file_id)
    admin_action_waiting.pop(message.from_user.id, None)
    await message.answer("✅ фото сохранено.", reply_markup=custom_section_keyboard(section))


@dp.message()
async def admin_message_handler(message: Message):
    if not message.text:
        return
    text = message.text.strip()

    user_action = user_action_waiting.get(message.from_user.id)
    if user_action == "promo":
        code = text.upper()
        promo = await get_promo(code)
        now = int(time.time())

        if not promo or not promo["enabled"]:
            await message.answer("❌ промокод не найден или отключён.")
            return

        if promo["expires_at"] and promo["expires_at"] < now:
            await message.answer("❌ срок действия промокода истёк.")
            return

        if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
            await message.answer("❌ лимит использований промокода исчерпан.")
            return

        user = await get_user(message.from_user.id)
        if not user or not user["sub_id"]:
            await message.answer("❌ подписка не найдена.")
            user_action_waiting.pop(message.from_user.id, None)
            return

        try:
            updated = renew_client_by_sub_id(
                sub_id=user["sub_id"],
                days=promo["reward_days"],
            )
        except Exception as e:
            logging.exception("failed to apply promo")
            await message.answer(f"❌ ошибка применения промокода:\n`{e}`")
            return

        if not await use_promo(code, message.from_user.id, now):
            await message.answer("❌ промокод уже использован тобой или больше недоступен.")
            return

        expires_at = int(updated.get("expiryTime", 0)) // 1000
        await update_user(
            tg_id=user["tg_id"],
            username=user["username"],
            email=user["email"],
            sub_id=user["sub_id"],
            subscription_url=f"https://87.121.82.175:2096/jsnn/{user['sub_id']}",
            status=user["status"],
            created_at=user["created_at"],
            expires_at=expires_at,
        )

        user_action_waiting.pop(message.from_user.id, None)
        await message.answer(
            f"✅ промокод применён!\n\n"
            f"🎁 начислено: +{promo['reward_days']} дней\n"
            f"⏳ осталось: {format_remaining(expires_at)}",
            reply_markup=await main_keyboard(),
        )
        return
    if message.from_user.id != ADMIN_ID:
        return

    action = admin_action_waiting.get(message.from_user.id)
    if not action:
        return

    if action.startswith("custom_text:"):
        section = action.split(":", 1)[1]
        await set_setting(f"{section}_text", text)
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer("✅ текст сохранён.", reply_markup=custom_section_keyboard(section))
        return

    if action.startswith("custom_button:"):
        key = action.split(":", 1)[1]
        if key in CUSTOM_BUTTONS:
            await set_setting(key, text)
            admin_action_waiting.pop(message.from_user.id, None)
            section = "main" if key.startswith("main_") else "subscription"
            await message.answer("✅ название кнопки сохранено.", reply_markup=custom_buttons_keyboard(section))
        return

    if action == "create_promo":
        parts = text.split()

        if len(parts) != 3:
            await message.answer("❌ формат: `код дни лимит`")
            return

        code = parts[0].upper()

        try:
            reward_days = int(parts[1])
            max_uses = int(parts[2])

            if not code or reward_days <= 0 or max_uses < 0:
                raise ValueError

            await create_promo(
                code=code,
                reward_days=reward_days,
                max_uses=max_uses,
            )
        except ValueError:
            await message.answer("❌ дни должны быть больше 0, лимит — 0 или больше.")
            return
        except Exception as e:
            logging.exception("failed to create promo")
            await message.answer(f"❌ ошибка создания промокода:\n`{e}`")
            return

        admin_action_waiting.pop(message.from_user.id, None)
        limit_text = "без ограничений" if max_uses == 0 else str(max_uses)

        await message.answer(
            "✅ промокод создан\n\n"
            f"🎟 код: `{code}`\n"
            f"🎁 дней: {reward_days}\n"
            f"👥 использований: {limit_text}",
            reply_markup=admin_keyboard(),
        )
        return

    if action == "bind":
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ формат неправильный.\n\nнужно: `telegram_id sub_id`")
            return
        try:
            tg_id = int(parts[0])
        except ValueError:
            await message.answer("❌ telegram id должен быть числом.")
            return
        sub_id = parts[1]
        client = find_client_by_sub_id(sub_id)
        if not client:
            await message.answer("❌ подписка с таким sub_id не найдена в 3x-ui.")
            return
        email = client.get("email")
        expires_at = int(client.get("expiryTime", 0)) // 1000
        url = f"https://87.121.82.175:2096/jsnn/{sub_id}"
        old = await get_user(tg_id)
        values = dict(tg_id=tg_id, username=old["username"] if old else "unknown", email=email, sub_id=sub_id, subscription_url=url, status="paid", created_at=old["created_at"] if old else int(time.time()), expires_at=expires_at)
        if old:
            await update_user(**values)
        else:
            await create_user(**values)
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer("✅ подписка привязана\n\n" f"👤 telegram id: `{tg_id}`\n" f"📧 email: `{email}`\n" f"🔗 sub_id: `{sub_id}`\n" f"⏳ осталось: {format_remaining(expires_at)}", reply_markup=admin_keyboard())
        return

    if action == "renew":
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ формат: `sub_id дни`")
            return

        sub_id = parts[0]
        try:
            days = int(parts[1])
            if days <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ количество дней должно быть целым числом больше 0.")
            return

        if not find_client_by_sub_id(sub_id):
            await message.answer("❌ подписка с таким sub_id не найдена.")
            return

        try:
            updated = renew_client_by_sub_id(sub_id=sub_id, days=days)
        except Exception as e:
            logging.exception("failed to renew client")
            await message.answer(f"❌ ошибка продления:\n`{e}`")
            return
        expires_at = int(updated.get("expiryTime", 0)) // 1000
        email = updated.get("email")
        if email:
            tg_id_value = updated.get("tgId")
            if tg_id_value:
                try:
                    tg_id = int(tg_id_value)
                    user = await get_user(tg_id)
                    if user:
                        await update_user(tg_id=tg_id, username=user["username"], email=email, sub_id=sub_id, subscription_url=f"https://87.121.82.175:2096/jsnn/{sub_id}", status="paid", created_at=user["created_at"], expires_at=expires_at)
                except (TypeError, ValueError):
                    pass
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer("✅ подписка продлена\n\n" f"🔗 sub_id: `{sub_id}`\n" f"🎁 добавлено: {days} дней\n" f"⏳ осталось: {format_remaining(expires_at)}", reply_markup=admin_keyboard())
        return

    if action == "ban":
        sub_id = text
        client = find_client_by_sub_id(sub_id)
        if not client:
            await message.answer("❌ подписка с таким sub_id не найдена.")
            return
        try:
            ban_client_by_sub_id(sub_id=sub_id)
        except Exception as e:
            logging.exception("failed to ban client")
            await message.answer(f"❌ ошибка бана:\n`{e}`")
            return
        email = client.get("email")
        if email and client.get("tgId"):
            try:
                tg_id = int(client["tgId"])
                user = await get_user(tg_id)
                if user:
                    await update_user(tg_id=tg_id, username=user["username"], email=user["email"], sub_id=user["sub_id"], subscription_url=user["subscription_url"], status="banned", created_at=user["created_at"], expires_at=user["expires_at"])
            except (TypeError, ValueError):
                pass
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer("⛔ пользователь забанен\n\n" f"🔗 sub_id: `{sub_id}`", reply_markup=admin_keyboard())


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
