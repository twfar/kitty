import asyncio
import logging
import random
import time

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton, InputMediaPhoto
from aiogram.utils.formatting import Text, CustomEmoji

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    TRIAL_HOURS,
    ROLLYPAY_API_KEY,
    ROLLYPAY_TEST,
    ROLLYPAY_DEFAULT_PRICE,
    ROLLYPAY_DEFAULT_DAYS,
    MAIN_MENU_PHOTO,
    TRIAL_MENU_PHOTO,
    PREMIUM_EMOJI_ID,
)
from db import (
    init_db,
    get_user,
    create_user,
    update_user,
    get_promo,
    create_promo,
    use_promo,
    create_payment,
    get_setting,
    set_setting,
    delete_user_data,
    create_referral,
    get_referral_stats,
)
from rollypay import create_payment as rollypay_create_payment

from xui import (
    create_client,
    get_client,
    renew_client_by_sub_id,
    find_client,
    get_hwid_devices,
    delete_all_hwid_devices,
    delete_client_by_tg_id,
    disable_client,
)

dp = Dispatcher()

BOT_VERSION = "1.0.8"
TRIAL_DURATION_HOURS = 24
TEST_USER_TG_ID = 8772456974

ADMIN_URL = "https://t.me/kittyvpnoff?direct"
SUPPORT_URL = "https://t.me/kittyvpn_support_robot"
CHANNEL = "@kittyvpnoff"
PRIVACY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
OFFER_URL = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"

admin_action_waiting = {}
user_action_waiting = {}
purchase_selection = {}

MENU_PHOTOS = [
    "AgACAgIAAxkBAAIDlGq2rmZEjEOkJFoe1hsAAbSALQdmQAACRyRrG5snqUldG_wdjq9mswEAAwIAA3kAAz0E",
    "AgACAgIAAxkBAAIDlmq2rmoO0Ya8Q7GEgoThyR-QmpAoAAJIJGsbmyepSTOPgBVl5TspAQADAgADeQADPQQ",
    "AgACAgIAAxkBAAIDmmq2roCyU-GOe28I7aCWIT-7HM46AAJCJGsbmyepSREsrjLJ-WGwAQADAgADeQADPQQ",
    "AgACAgIAAxkBAAIDnGq2sBYUWU6EoG9E3Ram31uL9OVfAAIhIWsbRWO4SR_R4V2WgQ_RAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDnWq2sBaIYSyVPZ0v1DFAJAEuKYZPAAIiIWsbRWO4SUoepsfddr-bAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDoGq2sGMJ2-RcOD2QRC9pJgMG-SoqAAIlIWsbRWO4SYOKa9QqWGgLAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDoWq2sGO7ojHFIMDAYAsmAsOr36-WAAImIWsbRWO4STCPF-WzAAF3-gEAAwIAA3cAAz0E",
    "AgACAgIAAxkBAAIDpGq2sGP17POQVF0-xWtBDsKYejGqAAIqIWsbRWO4SbDklE3jGmgcAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDqWq2sGN7OLf7KZAaoG8EL0u0raYPAAIvIWsbRWO4SU7UA0JYiUo-AQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDp2q2sGM7LSR5aLCeKBS-Zyr4hnaIAAItIWsbRWO4Sci0WkubzlgjAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDpmq2sGNRuh0tJK-ocHJAxvKL1xsPAAIsIWsbRWO4SWB9UQ8akJnDAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDomq2sGPEQ1FHSK9i9jZf-FzP8LkOAAInIWsbRWO4Sb6hAZdG-15oAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDo2q2sGMSdCbgHixAF6pcfL-r97KeAAIpIWsbRWO4SYqgrfWwQG0yAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDpWq2sGO1J_ri9S_1lo9XThd8HzwtAAIrIWsbRWO4ScyxeWgmxMA4AQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDqGq2sGMNst0UwhI1a3aeSL3KBVqKAAIuIWsbRWO4SfkNU_PLtsOGAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDtGq2sIAN_7g61dgeHc4N3u2IriuOAAIxIWsbRWO4SSrhUC87lBOUAQADAgADeQADPQQ",
    "AgACAgIAAxkBAAIDtmq2sIBT_pclshfYtNY4L8ZkH3UkAAIzIWsbRWO4Sb3uPzTaQBGMAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDtWq2sICS-Ugv8VITazMLbtmRz1YdAAIyIWsbRWO4SUkhBcHjoawVAQADAgADdwADPQQ",
    "AgACAgIAAxkBAAIDt2q2sIBKcT81ak1w1I7Y1syCndemAAI0IWsbRWO4SQlhxkmxp4lnAQADAgADdwADPQQ",
]


def random_menu_photo():
    return random.choice(MENU_PHOTOS)

def menu_caption(text: str):
    if PREMIUM_EMOJI_ID:
        return Text(
            CustomEmoji("🐈", custom_emoji_id=PREMIUM_EMOJI_ID),
            " ",
            text,
        ).as_kwargs()
    return {"caption": text}


async def answer_menu(message: Message, text: str, reply_markup=None, photo: str = ""):
    kwargs = menu_caption(text)
    await message.answer_photo(
        photo=random_menu_photo(),
        reply_markup=reply_markup,
        **kwargs,
    )


async def edit_menu(message: Message, text: str, reply_markup=None):
    photo = random_menu_photo()
    kwargs = menu_caption(text)

    if message.photo:
        await message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=kwargs["caption"],
                caption_entities=kwargs.get("caption_entities"),
            ),
            reply_markup=reply_markup,
        )
        return

    await message.edit_text(
        text,
        reply_markup=reply_markup,
    )


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if event.from_user.id == ADMIN_ID:
            return await handler(event, data)

        enabled = await get_setting("maintenance_enabled", "0")
        if enabled != "1":
            return await handler(event, data)

        if isinstance(event, Message):
            text = event.text or ""
            if text.split()[0].split("@")[0] == "/start" if text else False:
                maintenance_message = await get_setting(
                    "maintenance_message",
                    "🔧 технические работы\\n\\nбот временно недоступен. попробуй позже.",
                )
                await event.answer(maintenance_message)
            return

        return


dp.message.outer_middleware(MaintenanceMiddleware())
dp.callback_query.outer_middleware(MaintenanceMiddleware())


def main_keyboard(referral_count=0):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 подписка", callback_data="subscription", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📢 наш канал", url="https://t.me/kittyvpnoff")],
        [InlineKeyboardButton(text=f"👥 рефералы — {referral_count}", callback_data="referrals")],
        [InlineKeyboardButton(text="🎟 промокод", callback_data="promo")],
        [InlineKeyboardButton(text="🆘 поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ о сервисе", callback_data="about_service")],
    ])


def subscription_keyboard(subscription_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 скопировать ссылку",
            copy_text=CopyTextButton(text=subscription_url),
            style=ButtonStyle.PRIMARY,
        )],
        [
            InlineKeyboardButton(text="📱 устройства", callback_data="devices"),
            InlineKeyboardButton(text="💳 купить / продлить", callback_data="purchase"),
        ],
        [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
    ])


def welcome_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 подписаться", url="https://t.me/kittyvpnoff", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="✅ проверить подписку", callback_data="check_trial_subscription", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="💳 купить подписку", callback_data="purchase")],
    ])


def trial_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 начать trial", callback_data="start_trial", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="🔧 технические работы", callback_data="admin_maintenance")],
        [InlineKeyboardButton(text="🗑 очистить тестовый аккаунт", callback_data="admin_clear_test_user")],
    ])

def admin_subscription_keyboard(limit):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="−", callback_data="admin_sub_minus"),
            InlineKeyboardButton(text=str(limit), callback_data="admin_sub_value"),
            InlineKeyboardButton(text="+", callback_data="admin_sub_plus"),
        ],
        [InlineKeyboardButton(text="⏱ изменить срок", callback_data="admin_sub_time", style=ButtonStyle.PRIMARY)],
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
    # сначала ищем по telegram id — это надёжнее, чем старый email из базы.
    client = get_client(tg_id=user["tg_id"])

    # если по tg_id не нашли, пробуем старый email для совместимости.
    if not client:
        client = find_client(user["email"])

    if not client:
        return None

    client_data = client.get("client", client)
    email = client_data.get("email") or client.get("email") or user["email"]
    sub_id = client_data.get("subId") or client.get("subId")
    expiry_time = client_data.get("expiryTime") or client.get("expiryTime")

    if not sub_id or not expiry_time:
        return None

    subscription_url = f"https://87.121.82.175:2096/jsnn/{sub_id}"
    expires_at = int(expiry_time) // 1000

    # синхронизируем данные бота с найденным клиентом 3x-ui.
    await update_user(
        tg_id=user["tg_id"], username=user["username"], email=email,
        sub_id=sub_id, subscription_url=subscription_url, status=user["status"],
        created_at=user["created_at"], expires_at=expires_at,
    )

    return {
        "subscription_url": subscription_url,
        "expires_at": expires_at,
        "client": client,
        "email": email,
    }


async def send_subscription_info(message: Message, user):
    data = await get_subscription_data(user)
    if not data:
        await edit_menu(message, 
            "твоя подписка не найдена в системе.\n\nесли это ошибка, напиши в поддержку:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎫 открыть тикет", url=SUPPORT_URL, style=ButtonStyle.PRIMARY)],
                [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
            ]),
        )
        return

    client = data["client"]
    client_email = data["email"]
    client_info = get_client(email=client_email)
    client_data = client_info.get("client", client_info) if client_info else {}
    limit = client_data.get("limitHwid", 0)

    try:
        used = len(get_hwid_devices(client_email))
    except Exception:
        used = 0

    await edit_menu(message, 
        "🔗 твоя подписка\n\n"
        "📱 устройства: "
        f"{used} / {limit}\n"
        f"⏳ осталось: {format_remaining(data['expires_at'])}\n\n"
        "📲 как подключить в happ:\n"
        "1. нажми «скопировать ссылку» ниже\n"
        "2. открой happ и нажми «+»\n"
        "3. выбери добавление подписки / импорт из буфера\n"
        "4. вставь ссылку и сохрани\n"
        "5. выбери сервер и подключись",
        reply_markup=subscription_keyboard(data["subscription_url"]),
    )





@dp.message(CommandStart())
async def start(message: Message):
    user = await get_user(message.from_user.id)

    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1] if len(parts) > 1 else ""
    if not user and payload.startswith("ref_"):
        try:
            referrer_id = int(payload[4:])
            if referrer_id != message.from_user.id:
                await create_referral(referrer_id, message.from_user.id)
        except (TypeError, ValueError):
            logging.warning("invalid referral payload: %s", payload)

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

    if user and user["status"] != "pending":
        stats = await get_referral_stats(message.from_user.id)
        await answer_menu(
            message,
            "главное меню",
            reply_markup=main_keyboard(stats["total"]),
            photo=MAIN_MENU_PHOTO,
        )
        return

    await answer_menu(
        message,
        "привет это kitty vpn!\n\n"
        "мы имеем:\n"
        "крутые фото котиков\n"
        "интернет без блокировок\n"
        "низкую цену\n\n"
        "предлагаю выбор:\n"
        "ты подписываешься на наш канал и мы даем тебе бесплатно 1 день\n"
        "ты просто покупаешь доступ к нашему впн",
        reply_markup=welcome_keyboard(),
        photo=TRIAL_MENU_PHOTO,
    )


@dp.message(Command("getid"))
async def get_id(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    admin_action_waiting[message.from_user.id] = "get_id"
    await message.answer(
        "отправь premium emoji или фото.\n\n"
        "для premium emoji бот вернёт custom_emoji_id.\n"
        "для фото бот вернёт file_id."
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


async def grant_trial(callback: CallbackQuery):
    tg_id = callback.from_user.id
    username = callback.from_user.username or "unknown"
    user = await get_user(tg_id)

    if user and user["status"] in ("trial", "paid"):
        await callback.answer("у тебя уже есть подписка", show_alert=True)
        if user["sub_id"]:
            await send_subscription_info(callback.message, user)
        return

    if user and user["status"] == "pending":
        try:
            delete_client_by_tg_id(tg_id)
        except Exception:
            logging.exception("failed to remove pending client before trial")
        await delete_user_data(tg_id)
        user = None

    email = f"tg_{tg_id}"
    if find_client(email):
        await callback.answer("trial уже был создан", show_alert=True)
        return

    await callback.answer("создаю trial...")
    client = create_client(
        tg_id=tg_id,
        email=email,
        expiry_hours=TRIAL_DURATION_HOURS,
        group="trial",
    )

    created_at = int(time.time())
    expires_at = client["expiry_time"] // 1000
    values = dict(
        tg_id=tg_id,
        username=username,
        email=email,
        sub_id=client["sub_id"],
        subscription_url=client["subscription_url"],
        status="trial",
        created_at=created_at,
        expires_at=expires_at,
    )

    if user:
        await update_user(**values)
    else:
        await create_user(**values)

    await callback.bot.send_message(
        ADMIN_ID,
        "🎁 подключён trial\n\n"
        f"👤 username: {username}\n"
        f"🆔 telegram id: {tg_id}\n"
        f"🔗 sub id: {client['sub_id']}",
    )

    await edit_menu(
        callback.message,
        "🎁 trial активирован на 24 часа!\n\n"
        "🔗 json-подписка:\n"
        f"{client['subscription_url']}\n\n"
        "добавь эту ссылку в happ или другой поддерживаемый vpn-клиент.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "check_trial_subscription")
async def check_trial_subscription(callback: CallbackQuery):
    try:
        member = await callback.bot.get_chat_member(CHANNEL, callback.from_user.id)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        logging.exception("failed to check channel subscription")
        subscribed = False

    if not subscribed:
        await callback.answer("ты ещё не подписан на канал", show_alert=True)
        return

    await grant_trial(callback)


@dp.callback_query(lambda c: c.data == "start_trial")
async def start_trial(callback: CallbackQuery):
    try:
        member = await callback.bot.get_chat_member(CHANNEL, callback.from_user.id)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        logging.exception("failed to check channel subscription")
        subscribed = False

    if not subscribed:
        await callback.answer("сначала подпишись на канал", show_alert=True)
        return

    await grant_trial(callback)


@dp.callback_query(lambda c: c.data == "subscription")
async def subscription(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user or not user["sub_id"]:
        await callback.answer()
        await edit_menu(
            callback.message,
            "привет это kitty vpn!\n\n"
            "мы имеем:\n"
            "крутые фото котиков\n"
            "интернет без блокировок\n"
            "низкую цену\n\n"
            "предлагаю выбор:\n"
            "ты подписываешься на наш канал и мы даем тебе бесплатно 1 день\n"
            "ты просто покупаешь доступ к нашему впн",
            reply_markup=welcome_keyboard(),
        )
        return
    await callback.answer()
    await send_subscription_info(callback.message, user)


@dp.callback_query(lambda c: c.data == "devices")
async def devices(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("сначала получи trial", show_alert=True)
        return
    client = get_client(tg_id=callback.from_user.id) or find_client(user["email"])
    if not client:
        await callback.answer("подписка не найдена", show_alert=True)
        return
    client_data = client.get("client", client)
    client_email = client_data.get("email") or client.get("email") or user["email"]
    try:
        device_list = get_hwid_devices(client_email)
    except Exception:
        logging.exception("failed to get hwid devices")
        await callback.answer("ошибка получения устройств", show_alert=True)
        return
    client_info = get_client(email=client_email)
    client_data = client_info.get("client", client_info) if client_info else {}
    limit = client_data.get("limitHwid", 0)
    text = "\n".join(f"• {d.get('deviceModel') or 'неизвестное устройство'}" for d in device_list) if device_list else "нет зарегистрированных устройств"
    await callback.answer()
    await edit_menu(callback.message, 
        "📱 устройства\n\n"
        f"используется: {len(device_list)} / {limit}\n\n{text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 удалить все устройства", callback_data="delete_all_hwid", style=ButtonStyle.PRIMARY)],
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
        await edit_menu(callback.message, "❌ не удалось удалить устройства.", reply_markup=main_keyboard())
        return
    await edit_menu(callback.message, 
        "✅ все зарегистрированные устройства удалены.\n\nтеперь можно подключить устройство заново.",
        reply_markup=main_keyboard(),
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
    await edit_menu(callback.message, 
        "🐈 главное меню",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "referrals")
async def referrals(callback: CallbackQuery):
    stats = await get_referral_stats(callback.from_user.id)
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"

    await callback.answer()
    await edit_menu(
        callback.message,
        "👥 реферальная система\n\n"
        f"👤 приглашено: {stats['total']}\n"
        f"💳 оплатили: {stats['paid']}\n"
        f"🎁 получено дней: {stats['earned_days']}\n"
        f"💤 накоплено: {stats['pending_days']} дней\n\n"
        "🎁 первая оплата друга: +10 дней\n"
        "🎁 каждая следующая оплата: +5 дней\n\n"
        "⚠️ без активной подписки дни не сгорают — они копятся и автоматически добавятся к следующей подписке.\n\n"
        f"твоя ссылка:\n{link}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 скопировать ссылку", copy_text=CopyTextButton(text=link), style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "purchase")
async def purchase(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)

    if user and user["status"] in ("trial", "paid") and not user["sub_id"]:
        await callback.answer("профиль повреждён, напиши в поддержку", show_alert=True)
        return

    purchase_selection[callback.from_user.id] = {
        "devices": 3,
        "months": 1,
    }

    await callback.answer()
    await edit_menu(callback.message, 
        "💳 покупка подписки\n\n"
        "📱 количество устройств: 3\n"
        "📅 срок: 1 месяц\n\n"
        "выбери параметры:",
        reply_markup=purchase_selection_keyboard(3),
    )


def purchase_selection_keyboard(devices: int):
    monthly_price = 80 + (devices - 3) * 50
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚫" if devices == 3 else "−", callback_data="purchase_device_value" if devices == 3 else "purchase_device_minus"),
            InlineKeyboardButton(text=str(devices), callback_data="purchase_device_value"),
            InlineKeyboardButton(text="🚫" if devices == 10 else "+", callback_data="purchase_device_value" if devices == 10 else "purchase_device_plus"),
        ],
        [InlineKeyboardButton(text=f"✅ далее · {monthly_price} ₽/мес", callback_data="purchase_to_months", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_subscription")],
    ])


def purchase_months_keyboard(devices: int, months: int):
    total = purchase_price(devices, months)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 месяц", callback_data="purchase_months_1"),
            InlineKeyboardButton(text="3 месяца", callback_data="purchase_months_3"),
        ],
        [InlineKeyboardButton(text=f"✅ подтвердить · {format_price(total)} ₽", callback_data="purchase_confirm", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔙 назад", callback_data="purchase_back_devices")],
    ])


async def update_purchase_selection(callback: CallbackQuery, devices: int, months: int = 0):
    purchase_selection[callback.from_user.id] = {"devices": devices, "months": months}
    monthly_price = 80 + (devices - 3) * 50
    if months == 0:
        await edit_menu(callback.message, 
            "💳 покупка подписки\n\n"
            f"📱 устройств: {devices}\n"
            f"💰 цена: {monthly_price} ₽ / месяц\n\n"
            "выбери количество устройств:",
            reply_markup=purchase_selection_keyboard(devices),
        )
        return
    total = purchase_price(devices, months)
    await edit_menu(callback.message, 
        "💳 покупка подписки\n\n"
        f"📱 устройств: {devices}\n"
        f"📅 срок: {months} {'месяц' if months == 1 else 'месяца'}\n"
        f"💰 цена: {format_price(total)} ₽\n\n"
        "выбери срок:",
        reply_markup=purchase_months_keyboard(devices, months),
    )


@dp.callback_query(lambda c: c.data == "purchase_device_minus")
async def purchase_device_minus(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id, {"devices": 3, "months": 0})
    await callback.answer()
    await update_purchase_selection(callback, max(3, current["devices"] - 1), 0)


@dp.callback_query(lambda c: c.data == "purchase_device_plus")
async def purchase_device_plus(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id, {"devices": 3, "months": 0})
    await callback.answer()
    await update_purchase_selection(callback, min(10, current["devices"] + 1), 0)


@dp.callback_query(lambda c: c.data == "purchase_device_value")
async def purchase_device_value(callback: CallbackQuery):
    await callback.answer("доступно от 3 до 10 устройств", show_alert=True)


@dp.callback_query(lambda c: c.data == "purchase_to_months")
async def purchase_to_months(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id, {"devices": 3, "months": 0})
    await callback.answer()
    await update_purchase_selection(callback, current["devices"], 1)


@dp.callback_query(lambda c: c.data.startswith("purchase_months_"))
async def purchase_months(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id, {"devices": 3, "months": 0})
    months = int(callback.data.rsplit("_", 1)[1])
    await callback.answer()
    await update_purchase_selection(callback, current["devices"], months)


@dp.callback_query(lambda c: c.data == "purchase_back_devices")
async def purchase_back_devices(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id, {"devices": 3, "months": 0})
    await callback.answer()
    await update_purchase_selection(callback, current["devices"], 0)


def purchase_price(devices: int, months: int) -> float:
    monthly_price = 80 + (devices - 3) * 50
    if months == 1:
        return float(monthly_price)
    if months == 3:
        return monthly_price * 3 * 70 / 80
    raise ValueError("unsupported subscription period")


def format_price(amount: float) -> str:
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


@dp.callback_query(lambda c: c.data == "purchase_confirm")
async def purchase_confirm(callback: CallbackQuery):
    current = purchase_selection.get(callback.from_user.id)
    if not current:
        await callback.answer("выбери параметры заново", show_alert=True)
        return

    devices = int(current["devices"])
    months = int(current["months"])

    if months not in (1, 3):
        await callback.answer("сначала выбери срок", show_alert=True)
        return

    amount = purchase_price(devices, months)
    days = months * 30
    user = await get_user(callback.from_user.id)

    await callback.answer("создаю платёж...")

    try:
        if not user:
            tg_id = callback.from_user.id
            username = callback.from_user.username or "unknown"
            email = f"tg_{tg_id}"
            client = find_client(email)

            if not client:
                created = create_client(
                    tg_id=tg_id,
                    email=email,
                    expiry_hours=1,
                    group="paid",
                )
                disable_client(email)
                client = find_client(email) or created

            client_data = client.get("client", client)
            sub_id = client_data.get("subId") or client.get("sub_id")
            subscription_url = f"https://87.121.82.175:2096/jsnn/{sub_id}"

            await create_user(
                tg_id=tg_id,
                username=username,
                email=email,
                sub_id=sub_id,
                subscription_url=subscription_url,
                status="pending",
                created_at=int(time.time()),
                expires_at=int(client_data.get("expiryTime") or 0) // 1000,
            )
            user = await get_user(tg_id)

        payment = await rollypay_create_payment(
            api_key=ROLLYPAY_API_KEY,
            amount=amount,
            tg_id=callback.from_user.id,
            days=days,
            test=ROLLYPAY_TEST,
            devices=devices,
            months=months,
        )

        await create_payment(
            payment_id=payment["payment_id"],
            order_id=payment["order_id"],
            tg_id=callback.from_user.id,
            amount=f"{amount:.2f}",
            currency="RUB",
            days=days,
            test=ROLLYPAY_TEST,
            device_limit=devices,
            months=months,
        )
    except Exception:
        logging.exception("failed to create rollypay payment")
        await edit_menu(callback.message, 
            "❌ не удалось создать платёж.\n\n"
            "попробуй ещё раз или напиши в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_subscription")],
            ]),
        )
        return

    await edit_menu(callback.message, 
        "💳 платёж создан\n\n"
        f"📱 устройств: {devices}\n"
        f"📅 срок: {months} {'месяц' if months == 1 else 'месяца'}\n"
        f"💰 сумма: {format_price(amount)} ₽\n\n"
        "после успешной оплаты подписка выдастся автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 оплатить", url=payment["pay_url"], style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_subscription")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    await edit_menu(callback.message, 
        "🆘 поддержка\n\nесли что-то не работает или есть вопрос — создай обращение в тикет-системе:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎫 открыть тикет", url=SUPPORT_URL, style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "about_service")
async def about_service(callback: CallbackQuery):
    await callback.answer()
    await edit_menu(callback.message, 
        "ℹ️ о сервисе\n\nознакомиться с документами сервиса:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 политика конфиденциальности", url=PRIVACY_URL, style=ButtonStyle.PRIMARY)],
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
    await edit_menu(callback.message, 
        "🎟 промокод\n\nотправь промокод одним сообщением.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_clear_test_user")
async def admin_clear_test_user(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    await callback.answer("очищаю аккаунт...")

    try:
        delete_client_by_tg_id(TEST_USER_TG_ID)
    except Exception:
        logging.exception("failed to delete test user's 3x-ui client")
        await edit_menu(
            callback.message,
            "❌ не удалось удалить VPN-подписку тестового аккаунта.",
            reply_markup=admin_keyboard(),
        )
        return

    await delete_user_data(TEST_USER_TG_ID)

    await edit_menu(
        callback.message,
        "✅ тестовый аккаунт очищен.\n\n"
        f"telegram id: {TEST_USER_TG_ID}\n"
        "данные бота, платежи и VPN-подписка удалены.",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    enabled = await get_setting("maintenance_enabled", "0")
    maintenance_message = await get_setting(
        "maintenance_message",
        "🔧 технические работы\n\nбот временно недоступен. попробуй позже.",
    )
    status = "включены" if enabled == "1" else "выключены"

    await callback.answer()
    await edit_menu(callback.message, 
        "🔧 технические работы\n\n"
        f"статус: {status}\n\n"
        f"сообщение:\n{maintenance_message}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔴 выключить" if enabled == "1" else "🟢 включить",
                callback_data="admin_maintenance_toggle",
            )],
            [InlineKeyboardButton(text="✏️ изменить сообщение", callback_data="admin_maintenance_message", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_maintenance_toggle")
async def admin_maintenance_toggle(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    enabled = await get_setting("maintenance_enabled", "0")
    new_value = "0" if enabled == "1" else "1"
    await set_setting("maintenance_enabled", new_value)
    await callback.answer("тех. работы включены" if new_value == "1" else "тех. работы выключены")

    await admin_maintenance(callback)


@dp.callback_query(lambda c: c.data == "admin_maintenance_message")
async def admin_maintenance_message(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    admin_action_waiting[callback.from_user.id] = "maintenance_message"
    await callback.answer()
    await edit_menu(callback.message, 
        "✏️ сообщение тех. работ\n\n"
        "отправь новое сообщение одним сообщением.\n"
        "оно будет отправляться пользователям при /start.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_maintenance")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_create_promo")
async def admin_create_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    admin_action_waiting[callback.from_user.id] = "create_promo"
    await callback.answer()
    await edit_menu(callback.message, 
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


@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting.pop(callback.from_user.id, None)
    await callback.answer()
    await edit_menu(callback.message, "⚙️ админ-панель\n\nвыбери действие:", reply_markup=admin_keyboard())


@dp.message()
async def admin_message_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        if not message.text:
            return
    else:
        action = admin_action_waiting.get(message.from_user.id)

        if action == "get_id":
            if message.photo:
                file_id = message.photo[-1].file_id
                await message.answer(f"photo_file_id:\n{file_id}")
                return

            if message.entities:
                custom = [
                    entity.custom_emoji_id
                    for entity in message.entities
                    if entity.type == "custom_emoji" and entity.custom_emoji_id
                ]
                if custom:
                    await message.answer(
                        "custom_emoji_id:\n" + "\n".join(custom)
                    )
                    return

            if not message.text:
                return

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
            reply_markup=main_keyboard(),
        )
        return
    if message.from_user.id != ADMIN_ID:
        return

    action = admin_action_waiting.get(message.from_user.id)
    if not action:
        return

    if action == "maintenance_message":
        await set_setting("maintenance_message", text)
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer(
            "✅ сообщение тех. работ обновлено.",
            reply_markup=admin_keyboard(),
        )
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
