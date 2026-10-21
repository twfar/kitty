import asyncio
import logging
import random
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.enums import ButtonStyle
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
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
    has_used_trial,
    mark_trial_claimed,
    create_user,
    update_user,
    get_promo,
    get_promos,
    delete_promo,
    create_promo,
    use_promo,
    create_payment,
    get_setting,
    set_setting,
    delete_user_data,
    create_referral,
    register_referral_signup_reward,
    get_referral_stats,
    get_pending_referral_rewards,
    mark_referral_rewards_applied,
    get_active_users,
    notification_was_sent,
    mark_notification_sent,
    get_device_snapshots,
    save_device_snapshot,
    is_notification_blocked,
    block_notification_user,
    unblock_notification_user,
    get_broadcast_users,
    get_user_by_username,
)
from rollypay import create_payment as rollypay_create_payment

from xui import (
    create_client,
    get_client,
    renew_client_by_sub_id,
    add_days_to_client_by_sub_id,
    find_client,
    get_hwid_devices,
    delete_all_hwid_devices,
    delete_client_by_tg_id,
    disable_client,
    DEFAULT_INBOUND_IDS,
    get_inbound_ids,
    set_inbound_ids,
)

dp = Dispatcher()

BOT_VERSION = "1.0.8"
TRIAL_DURATION_HOURS = 24
SUBSCRIPTION_DELETE_AFTER_DAYS = 3
TEST_USER_TG_ID = 8772456974

ADMIN_URL = "https://t.me/kittyvpnoff?direct"
SUPPORT_URL = "https://t.me/kittyvpn_support_robot"
CHANNEL = "@kittyvpnoff"
PRIVACY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
OFFER_URL = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"

admin_action_waiting = {}
user_action_waiting = {}
purchase_selection = {}

broadcast_queue = asyncio.Queue()
pending_broadcast = {}
pending_personal = {}
BROADCAST_DELAY = 0.06

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
        [
            InlineKeyboardButton(text="👥 рефералы", callback_data="referrals"),
            InlineKeyboardButton(text="🎟 промокод", callback_data="promo"),
        ],
        [
            InlineKeyboardButton(text="🆘 поддержка", callback_data="support"),
            InlineKeyboardButton(text="ℹ️ инфо", callback_data="about_service"),
        ],
    ])


def subscription_keyboard(subscription_page_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 подключиться",
            url=subscription_page_url,
            style=ButtonStyle.SUCCESS,
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
        [InlineKeyboardButton(text="📢 рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💬 личное сообщение", callback_data="admin_personal_message")],
        [InlineKeyboardButton(text="🎟 создать промокод", callback_data="admin_create_promo")],
        [
            InlineKeyboardButton(text="📋 промокоды", callback_data="admin_promos"),
            InlineKeyboardButton(text="🗑 удалить промокод", callback_data="admin_delete_promo"),
        ],
        [InlineKeyboardButton(text="🔧 технические работы", callback_data="admin_maintenance")],
        [InlineKeyboardButton(text="🌐 inbound IDs", callback_data="admin_inbound_ids")],
        [InlineKeyboardButton(text="🗑 удалить истёкшие подписки", callback_data="admin_expired_subscriptions")],
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

    subscription_url = f"https://kitvp.duckdns.org:2096/jsnn/{sub_id}"
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

    subscription_page_url = f"https://kitvp.duckdns.org:2096/s/{client_data.get('subId')}"
    await edit_menu(message, 
        "🔗 твоя подписка\n\n"
        "📱 устройства: "
        f"{used} / {limit}\n"
        f"⏳ осталось: {format_remaining(data['expires_at'])}\n\n"
        "📲 нажми «подключиться», чтобы открыть страницу подписки.",
        reply_markup=subscription_keyboard(subscription_page_url),
    )





async def apply_referral_days(referrer_id: int, reward_days: int) -> bool:
    referrer = await get_user(referrer_id)
    if not referrer or not referrer["sub_id"]:
        return False

    try:
        updated_client = add_days_to_client_by_sub_id(
            referrer["sub_id"],
            reward_days,
        )
        expires_at = int(updated_client.get("expiryTime", 0)) // 1000
        await update_user(
            tg_id=referrer["tg_id"],
            username=referrer["username"],
            email=referrer["email"],
            sub_id=referrer["sub_id"],
            subscription_url=(
                f"https://kitvp.duckdns.org:2096/jsnn/{referrer['sub_id']}"
            ),
            status=referrer["status"],
            created_at=referrer["created_at"],
            expires_at=expires_at,
        )
        return True
    except Exception:
        logging.exception(
            "failed to apply referral reward to referrer %s",
            referrer_id,
        )
        return False


async def apply_pending_referral_rewards(tg_id: int) -> bool:
    user = await get_user(tg_id)
    if not user or not user["sub_id"]:
        return False

    rewards = await get_pending_referral_rewards(tg_id)
    if not rewards:
        return False

    total_days = sum(int(row["reward_days"]) for row in rewards)
    try:
        updated_client = add_days_to_client_by_sub_id(
            user["sub_id"],
            total_days,
        )
        expires_at = int(updated_client.get("expiryTime", 0)) // 1000
        await update_user(
            tg_id=user["tg_id"],
            username=user["username"],
            email=user["email"],
            sub_id=user["sub_id"],
            subscription_url=(
                f"https://kitvp.duckdns.org:2096/jsnn/{user['sub_id']}"
            ),
            status=user["status"],
            created_at=user["created_at"],
            expires_at=expires_at,
        )
        await mark_referral_rewards_applied(
            [row["payment_id"] for row in rewards]
        )
        return True
    except Exception:
        logging.exception(
            "failed to apply pending referral rewards to user %s",
            tg_id,
        )
        return False


EXPIRED_SUBSCRIPTION_TEXT = (
    "твоя предыдущая подписка была удалена, потому что срок её действия истёк.\n\n"
    "ты можешь оформить новую подписку, активировать промокод или обратиться в поддержку."
)


def expired_subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 купить новую подписку",
            callback_data="purchase",
            style=ButtonStyle.PRIMARY,
        )],
        [InlineKeyboardButton(
            text="🎟 активировать промокод",
            callback_data="promo",
        )],
        [InlineKeyboardButton(
            text="🆘 поддержка",
            url=SUPPORT_URL,
        )],
    ])


async def show_expired_subscription_menu(message: Message) -> None:
    await answer_menu(
        message,
        EXPIRED_SUBSCRIPTION_TEXT,
        reply_markup=expired_subscription_keyboard(),
    )


async def edit_expired_subscription_menu(message: Message) -> None:
    await edit_menu(
        message,
        EXPIRED_SUBSCRIPTION_TEXT,
        reply_markup=expired_subscription_keyboard(),
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
                created_referral = await create_referral(
                    referrer_id,
                    message.from_user.id,
                )
                if created_referral:
                    reward_created = await register_referral_signup_reward(
                        referrer_id,
                        message.from_user.id,
                    )
                    if reward_created:
                        await apply_referral_days(referrer_id, 1)
                        try:
                            await message.bot.send_message(
                                referrer_id,
                                "👥 твой друг перешел по ссылке!\n"
                                "🎁 тебе начислен +1 день к подписке.",
                            )
                        except Exception:
                            logging.exception(
                                "failed to notify referrer about referral click"
                            )
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

    trial_claimed = await has_used_trial(message.from_user.id)
    has_subscription_history = trial_claimed or bool(
        user and user["status"] in ("trial", "paid")
    )
    has_working_subscription = bool(
        user
        and user["subscription_class"] == "active"
        and user["sub_id"]
        and int(user["expires_at"] or 0) > int(time.time())
    )

    if has_subscription_history and not has_working_subscription:
        await show_expired_subscription_menu(message)
        return

    if user and user["status"] != "pending":
        stats = await get_referral_stats(message.from_user.id)
        await answer_menu(
            message,
            "главное меню kitty vpn\n\n"
            "наш канал — @kittyvpnoff",
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
    if await has_used_trial(tg_id):
        await callback.answer("ты уже использовал trial", show_alert=True)
        if user and user["sub_id"]:
            await send_subscription_info(callback.message, user)
        else:
            await edit_expired_subscription_menu(callback.message)
        return

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

    await mark_trial_claimed(tg_id, created_at)
    await apply_pending_referral_rewards(tg_id)

    await callback.bot.send_message(
        ADMIN_ID,
        "🎁 подключён trial\n\n"
        f"👤 username: {username}\n"
        f"🆔 telegram id: {tg_id}\n"
        f"🔗 sub id: {client['sub_id']}",
    )

    trial_page_url = f"https://kitvp.duckdns.org:2096/s/{client['sub_id']}"
    await edit_menu(
        callback.message,
        "🎁 trial активирован на 24 часа!\n\n"
        "нажми «подключиться», чтобы открыть страницу подписки.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 подключиться",
                url=trial_page_url,
                style=ButtonStyle.SUCCESS,
            )],
            [InlineKeyboardButton(
                text="🔙 главное меню",
                callback_data="back_to_menu",
                style=ButtonStyle.PRIMARY,
            )],
        ]),
    )


@dp.callback_query(lambda c: c.data == "check_trial_subscription")
async def check_trial_subscription(callback: CallbackQuery):
    if await has_used_trial(callback.from_user.id):
        await callback.answer("ты уже использовал trial", show_alert=True)
        await edit_expired_subscription_menu(callback.message)
        return

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
    if await has_used_trial(callback.from_user.id):
        await callback.answer("ты уже использовал trial", show_alert=True)
        await edit_expired_subscription_menu(callback.message)
        return

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
        if await has_used_trial(callback.from_user.id) or (
            user and user["status"] in ("trial", "paid")
        ):
            await callback.answer()
            await edit_expired_subscription_menu(callback.message)
            return

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
    if (await has_used_trial(callback.from_user.id) or (
        user and user["status"] in ("trial", "paid")
    )) and (not user or not user["sub_id"]):
        await callback.answer()
        await edit_expired_subscription_menu(callback.message)
        return

    if not user:
        await callback.answer("сначала оформи подписку", show_alert=True)
        return

    await callback.answer()
    await send_subscription_info(callback.message, user)


@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user_action_waiting.pop(callback.from_user.id, None)
    user = await get_user(callback.from_user.id)
    if (await has_used_trial(callback.from_user.id) or (
        user and user["status"] in ("trial", "paid")
    )) and (not user or not user["sub_id"]):
        await callback.answer()
        await edit_expired_subscription_menu(callback.message)
        return

    await callback.answer()
    await edit_menu(
        callback.message,
        "главное меню kitty vpn\n\n"
        "наш канал — @kittyvpnoff",
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
        f"💤 ожидает подписки: {stats['pending_days']} дней\n\n"
        "🎁 +1 день к подписке — сразу за каждого приглашённого друга!\n"
        "🎁 +5 дней к подписке — за каждый месяц, оплаченный другом "
        "(например, если друг берет 3 месяца — ты получаешь +15 дней!).\n"
        "⚡ дни добавляются к твоей подписке моментально, даже если она сейчас закончилась.\n\n"
        f"твоя ссылка:\n{link}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 скопировать ссылку", copy_text=CopyTextButton(text=link), style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "purchase")
async def purchase(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)

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


def calculate_monthly_price(devices: int) -> int:
    if not 3 <= devices <= 10:
        raise ValueError("device count must be between 3 and 10")
    return 80 + (devices - 3) * 30


def purchase_selection_keyboard(devices: int):
    monthly_price = calculate_monthly_price(devices)
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
            InlineKeyboardButton(text="3 месяца · −10%", callback_data="purchase_months_3"),
        ],
        [InlineKeyboardButton(text=f"✅ подтвердить · {format_price(total)} ₽", callback_data="purchase_confirm", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔙 назад", callback_data="purchase_back_devices")],
    ])


async def update_purchase_selection(callback: CallbackQuery, devices: int, months: int = 0):
    purchase_selection[callback.from_user.id] = {"devices": devices, "months": months}
    monthly_price = calculate_monthly_price(devices)
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
        f"💰 цена: {format_price(total)} ₽\n"
        + ("🏷 скидка 10% за 3 месяца уже учтена.\n\n" if months == 3 else "\n")
        + "выбери срок:",
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
    monthly_price = calculate_monthly_price(devices)
    if months == 1:
        return float(monthly_price)
    if months == 3:
        return monthly_price * 3 * 0.9
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
        if not user or not user["sub_id"]:
            tg_id = callback.from_user.id
            username = callback.from_user.username or "unknown"
            email = (user["email"] if user and user["email"] else f"tg_{tg_id}")
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
            if not sub_id:
                raise RuntimeError("new payment client has no subscription id")
            subscription_url = f"https://kitvp.duckdns.org:2096/jsnn/{sub_id}"
            expires_at = int(
                client_data.get("expiryTime") or client.get("expiry_time") or 0
            ) // 1000
            created_at = int(user["created_at"]) if user else int(time.time())

            if user:
                await update_user(
                    tg_id=tg_id,
                    username=username,
                    email=email,
                    sub_id=sub_id,
                    subscription_url=subscription_url,
                    status="pending",
                    created_at=created_at,
                    expires_at=expires_at,
                )
            else:
                await create_user(
                    tg_id=tg_id,
                    username=username,
                    email=email,
                    sub_id=sub_id,
                    subscription_url=subscription_url,
                    status="pending",
                    created_at=created_at,
                    expires_at=expires_at,
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
    has_trial_history = await has_used_trial(callback.from_user.id)
    expired_user = (
        bool(has_trial_history and (not user or not user["sub_id"]))
        or bool(user and user["status"] in ("trial", "paid") and not user["sub_id"])
    )

    if not user and not has_trial_history:
        await callback.answer("сначала оформи подписку", show_alert=True)
        return
    if user and not user["sub_id"] and not expired_user:
        await callback.answer("сначала оформи подписку", show_alert=True)
        return

    user_action_waiting[callback.from_user.id] = "promo"
    await callback.answer()
    await edit_menu(
        callback.message,
        "🎟 промокод\n\nотправь промокод одним сообщением.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="back_to_menu")],
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


@dp.callback_query(lambda c: c.data == "admin_expired_subscriptions")
async def admin_expired_subscriptions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    users = await get_active_users()
    cutoff = int(time.time()) - SUBSCRIPTION_DELETE_AFTER_DAYS * 24 * 3600
    expired_count = sum(
        1 for user in users
        if user["sub_id"] and int(user["expires_at"] or 0) <= cutoff
    )
    await callback.answer()
    if expired_count == 0:
        await edit_menu(
            callback.message,
            "🗑 старых подписок для удаления нет.\n\n"
            f"удаляются только подписки, истёкшие более {SUBSCRIPTION_DELETE_AFTER_DAYS} дней назад.",
            reply_markup=admin_keyboard(),
        )
        return

    await edit_menu(
        callback.message,
        "⚠️ удаление истёкших подписок\n\n"
        f"найдено в базе: {expired_count}\n"
        f"к удалению: подписки, истёкшие более {SUBSCRIPTION_DELETE_AFTER_DAYS} дней назад.\n\n"
        "перед удалением бот повторно проверит срок в 3x-ui. "
        "продлённые подписки останутся нетронутыми. записи пользователей и история оплат сохранятся.\n\n"
        "продолжить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 подтвердить удаление", callback_data="admin_expired_subscriptions_confirm", style=ButtonStyle.DANGER)],
            [InlineKeyboardButton(text="🔙 отмена", callback_data="admin_back")],
        ]),
    )


async def cleanup_expired_subscriptions() -> tuple[int, int, int]:
    """Delete 3x-ui clients whose subscription expired more than three days ago."""
    users = await get_active_users()
    now = int(time.time())
    cutoff = now - SUBSCRIPTION_DELETE_AFTER_DAYS * 24 * 3600
    deleted = skipped = failed = 0

    for user in users:
        tg_id = int(user["tg_id"])
        sub_id = user["sub_id"]
        if not sub_id or int(user["expires_at"] or 0) > cutoff:
            continue

        try:
            latest_user = await get_user(tg_id)
            if (
                not latest_user
                or latest_user["sub_id"] != sub_id
                or int(latest_user["expires_at"] or 0) > cutoff
            ):
                skipped += 1
                continue

            client = get_client(tg_id=tg_id)
            if client:
                client_data = client.get("client", client)
                raw_expiry = client_data.get("expiryTime")
                if not raw_expiry or int(raw_expiry) // 1000 > cutoff:
                    skipped += 1
                    continue
                if not delete_client_by_tg_id(tg_id):
                    skipped += 1
                    continue

            latest_user = await get_user(tg_id)
            if (
                latest_user
                and latest_user["sub_id"] == sub_id
                and int(latest_user["expires_at"] or 0) <= cutoff
            ):
                await update_user(
                    tg_id=tg_id,
                    username=latest_user["username"],
                    email=latest_user["email"],
                    sub_id=None,
                    subscription_url=None,
                    status=latest_user["status"],
                    created_at=latest_user["created_at"],
                    expires_at=int(latest_user["expires_at"] or 0),
                )
                deleted += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
            logging.exception("automatic expired-subscription cleanup failed for user %s", tg_id)

    return deleted, skipped, failed


async def expired_subscription_cleanup_worker() -> None:
    """Run expired subscription cleanup hourly without blocking bot startup."""
    while True:
        try:
            deleted, skipped, failed = await cleanup_expired_subscriptions()
            if deleted or failed:
                logging.info(
                    "expired subscription cleanup: deleted=%s skipped=%s failed=%s",
                    deleted, skipped, failed,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("expired subscription cleanup worker failed")
        await asyncio.sleep(3600)


@dp.callback_query(lambda c: c.data == "admin_expired_subscriptions_confirm")
async def admin_expired_subscriptions_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    await callback.answer("проверяю подписки...")
    users = await get_active_users()
    now = int(time.time())
    cutoff = now - SUBSCRIPTION_DELETE_AFTER_DAYS * 24 * 3600
    deleted = 0
    skipped = 0
    failed = 0

    for user in users:
        tg_id = int(user["tg_id"])
        db_expiry = int(user["expires_at"] or 0)
        sub_id = user["sub_id"]
        if not sub_id or db_expiry > cutoff:
            continue

        try:
            latest_user = await get_user(tg_id)
            if (
                not latest_user
                or not latest_user["sub_id"]
                or latest_user["sub_id"] != sub_id
                or int(latest_user["expires_at"] or 0) > cutoff
            ):
                skipped += 1
                continue

            client = get_client(tg_id=tg_id)
            if client:
                client_data = client.get("client", client)
                raw_panel_expiry = client_data.get("expiryTime")
                if not raw_panel_expiry:
                    skipped += 1
                    logging.warning(
                        "skip expired-subscription cleanup for user %s: "
                        "3x-ui expiry is missing",
                        tg_id,
                    )
                    continue
                panel_expiry = int(raw_panel_expiry) // 1000
                if panel_expiry > cutoff:
                    skipped += 1
                    continue
                if not delete_client_by_tg_id(tg_id):
                    skipped += 1
                    continue

            latest_user = await get_user(tg_id)
            if (
                latest_user
                and latest_user["sub_id"] == sub_id
                and int(latest_user["expires_at"] or 0) <= cutoff
            ):
                await update_user(
                    tg_id=tg_id,
                    username=latest_user["username"],
                    email=latest_user["email"],
                    sub_id=None,
                    subscription_url=None,
                    status=latest_user["status"],
                    created_at=latest_user["created_at"],
                    expires_at=int(latest_user["expires_at"] or 0),
                )
                deleted += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
            logging.exception("failed to delete expired subscription for user %s", tg_id)

    await edit_menu(
        callback.message,
        "🗑 обработка истёкших подписок завершена\n\n"
        f"✅ очищено: {deleted}\n"
        f"⏭ пропущено (срок изменился или клиент не найден): {skipped}\n"
        f"❌ ошибок: {failed}\n\n"
        "данные пользователей и история платежей сохранены.",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(lambda c: c.data.startswith("unblock_notifications:"))
async def unblock_notifications(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    try:
        tg_id = int(callback.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("некорректный telegram id", show_alert=True)
        return

    await unblock_notification_user(tg_id)
    await callback.answer("уведомления разблокированы")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🔓 уведомления разблокированы\n\n"
        f"🆔 telegram id: {tg_id}\n\n"
        "бот снова будет пытаться отправлять этому пользователю уведомления."
    )


def broadcast_group_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 все", callback_data="admin_broadcast_group:all"),
            InlineKeyboardButton(text="🟢 активные", callback_data="admin_broadcast_group:active"),
        ],
        [
            InlineKeyboardButton(text="🧪 trial", callback_data="admin_broadcast_group:trial"),
            InlineKeyboardButton(text="💳 paid", callback_data="admin_broadcast_group:paid"),
        ],
        [InlineKeyboardButton(text="⌛ истёкшие", callback_data="admin_broadcast_group:expired")],
        [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
    ])


def admin_confirm_keyboard(kind):
    prefix = "admin_broadcast" if kind == "broadcast" else "admin_personal"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ отправить", callback_data=f"{prefix}_confirm"),
            InlineKeyboardButton(text="❌ отмена", callback_data=f"{prefix}_cancel"),
        ],
    ])


@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    admin_action_waiting.pop(ADMIN_ID, None)
    pending_broadcast.pop(ADMIN_ID, None)
    await callback.answer()
    await edit_menu(
        callback.message,
        "📢 рассылка\n\nвыбери группу пользователей:",
        reply_markup=broadcast_group_keyboard(),
    )


@dp.callback_query(lambda c: c.data.startswith("admin_broadcast_group:"))
async def admin_broadcast_group(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    group = callback.data.split(":", 1)[1]
    names = {
        "all": "всем",
        "active": "активным",
        "trial": "trial",
        "paid": "paid",
        "expired": "истёкшим",
    }
    admin_action_waiting[ADMIN_ID] = f"broadcast_message:{group}"
    pending_broadcast.pop(ADMIN_ID, None)
    await callback.answer()
    await edit_menu(
        callback.message,
        f"📢 рассылка: {names.get(group, group)}\n\n"
        "отправь одно сообщение для рассылки.\n"
        "можно отправлять текст, фото, видео, документ и другие поддерживаемые telegram-сообщения.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_broadcast")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    job = pending_broadcast.pop(ADMIN_ID, None)
    admin_action_waiting.pop(ADMIN_ID, None)
    if not job:
        await callback.answer("рассылка не найдена", show_alert=True)
        return

    await broadcast_queue.put(job)
    await callback.answer("рассылка поставлена в очередь")
    await callback.message.answer(
        "📢 рассылка поставлена в очередь.\n\n"
        f"👥 получатели: {job['group_name']}\n"
        "я сообщу результат после завершения."
    )


@dp.callback_query(lambda c: c.data == "admin_broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    pending_broadcast.pop(ADMIN_ID, None)
    admin_action_waiting.pop(ADMIN_ID, None)
    await callback.answer("рассылка отменена")
    await edit_menu(callback.message, "⚙️ админ-панель\n\nвыбери действие:", reply_markup=admin_keyboard())


@dp.callback_query(lambda c: c.data == "admin_personal_message")
async def admin_personal_message(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    pending_personal.pop(ADMIN_ID, None)
    admin_action_waiting[ADMIN_ID] = "personal_target"
    await callback.answer()
    await edit_menu(
        callback.message,
        "💬 личное сообщение\n\n"
        "отправь telegram id или @username пользователя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")]
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_personal_confirm")
async def admin_personal_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return
    job = pending_personal.pop(ADMIN_ID, None)
    admin_action_waiting.pop(ADMIN_ID, None)
    if not job:
        await callback.answer("сообщение не найдено", show_alert=True)
        return

    try:
        await callback.bot.copy_message(
            chat_id=job["target_id"],
            from_chat_id=job["source_chat_id"],
            message_id=job["message_id"],
        )
        await callback.answer("сообщение отправлено")
        await callback.message.answer("✅ личное сообщение отправлено.", reply_markup=admin_keyboard())
    except TelegramForbiddenError:
        await callback.answer("пользователь заблокировал бота", show_alert=True)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await callback.bot.copy_message(
                chat_id=job["target_id"],
                from_chat_id=job["source_chat_id"],
                message_id=job["message_id"],
            )
            await callback.message.answer("✅ личное сообщение отправлено.", reply_markup=admin_keyboard())
        except Exception as e2:
            await callback.message.answer(f"❌ не удалось отправить: {e2}", reply_markup=admin_keyboard())
    except Exception as e:
        logging.exception("personal message failed")
        await callback.answer("ошибка отправки", show_alert=True)
        await callback.message.answer(f"❌ не удалось отправить: {e}", reply_markup=admin_keyboard())


@dp.callback_query(lambda c: c.data == "admin_personal_cancel")
async def admin_personal_cancel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    pending_personal.pop(ADMIN_ID, None)
    admin_action_waiting.pop(ADMIN_ID, None)
    await callback.answer("отменено")
    await edit_menu(callback.message, "⚙️ админ-панель\n\nвыбери действие:", reply_markup=admin_keyboard())


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


def format_promo_expiry(expires_at):
    if not expires_at:
        return "без срока"
    return datetime.fromtimestamp(int(expires_at)).strftime("%d.%m.%Y %H:%M")


def promo_status_text(promo):
    now = int(time.time())
    if not promo["enabled"]:
        return "выключен"
    if promo["expires_at"] and promo["expires_at"] < now:
        return "истёк"
    if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
        return "лимит исчерпан"
    return "активен"


@dp.callback_query(lambda c: c.data == "admin_promos")
async def admin_promos(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    promos = await get_promos()
    await callback.answer()

    if not promos:
        await edit_menu(
            callback.message,
            "📋 промокоды\n\nпромокодов пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
            ]),
        )
        return

    lines = ["📋 промокоды", ""]
    for promo in promos:
        limit = "∞" if promo["max_uses"] == 0 else str(promo["max_uses"])
        lines.append(
            f"🎟 {promo['code']} — +{promo['reward_days']} д.\n"
            f"   использований: {promo['used_count']} / {limit}\n"
            f"   срок: {format_promo_expiry(promo['expires_at'])}\n"
            f"   статус: {promo_status_text(promo)}"
        )

    await edit_menu(
        callback.message,
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 удалить промокод", callback_data="admin_delete_promo")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
        ]),
    )


@dp.callback_query(lambda c: c.data == "admin_delete_promo")
async def admin_delete_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    admin_action_waiting[ADMIN_ID] = "delete_promo"
    await callback.answer()
    await edit_menu(
        callback.message,
        "🗑 удаление промокода\n\n"
        "отправь код промокода, который нужно удалить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 посмотреть промокоды", callback_data="admin_promos")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")],
        ]),
    )


@dp.callback_query(lambda c: c.data.startswith("admin_delete_promo_confirm:"))
async def admin_delete_promo_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    code = callback.data.split(":", 1)[1]
    promo = await get_promo(code)
    if not promo:
        await callback.answer("промокод уже удалён", show_alert=True)
        await admin_promos(callback)
        return

    deleted = await delete_promo(code)
    if deleted:
        await callback.answer("промокод удалён")
        await edit_menu(
            callback.message,
            f"✅ промокод {code} удалён.",
            reply_markup=admin_keyboard(),
        )
    else:
        await callback.answer("не удалось удалить промокод", show_alert=True)


@dp.callback_query(lambda c: c.data == "admin_create_promo")
async def admin_create_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    user_action_waiting.pop(callback.from_user.id, None)
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


@dp.callback_query(lambda c: c.data == "admin_inbound_ids")
async def admin_inbound_ids(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("доступ запрещён", show_alert=True)
        return

    current_ids = get_inbound_ids()
    admin_action_waiting[ADMIN_ID] = "inbound_ids"
    await callback.answer()
    await edit_menu(
        callback.message,
        "🌐 inbound IDs для новых клиентов\n\n"
        f"сейчас подключаются inbound: {', '.join(map(str, current_ids))}\n\n"
        "отправь новые ID через запятую или пробел.\n"
        "пример: 8, 31, 35, 41, 54\n\n"
        "изменение повлияет только на новых клиентов. существующие подписки не изменятся.",
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

    if message.from_user.id == ADMIN_ID:
        action = admin_action_waiting.get(message.from_user.id)

        if action and action.startswith("broadcast_message:"):
            group = action.split(":", 1)[1]
            users = await get_broadcast_users(group)
            if not users:
                admin_action_waiting.pop(ADMIN_ID, None)
                await message.answer("❌ в выбранной группе нет пользователей.", reply_markup=admin_keyboard())
                return

            names = {
                "all": "всем",
                "active": "активным",
                "trial": "trial",
                "paid": "paid",
                "expired": "истёкшим",
            }
            pending_broadcast[ADMIN_ID] = {
                "source_chat_id": message.chat.id,
                "message_id": message.message_id,
                "user_ids": [int(user["tg_id"]) for user in users],
                "group_name": names.get(group, group),
            }
            admin_action_waiting.pop(ADMIN_ID, None)

            try:
                await message.copy_to(ADMIN_ID)
            except Exception:
                pass
            await message.answer(
                "👆 сообщение для предпросмотра\n\n"
                f"👥 получателей: {len(users)}\n\n"
                "отправить?",
                reply_markup=admin_confirm_keyboard("broadcast"),
            )
            return

        if action == "personal_target":
            target = (message.text or "").strip()
            if target.startswith("@"):
                user = await get_user_by_username(target[1:])
            else:
                try:
                    user = await get_user(int(target))
                except ValueError:
                    user = None

            if not user:
                await message.answer("❌ пользователь не найден в базе.")
                return

            pending_personal[ADMIN_ID] = {"target_id": int(user["tg_id"])}
            admin_action_waiting[ADMIN_ID] = "personal_message"
            await message.answer(
                f"👤 пользователь: @{user['username'] or '—'}\n"
                f"🆔 id: {user['tg_id']}\n\n"
                "теперь отправь сообщение.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 назад", callback_data="admin_back")]
                ]),
            )
            return

        if action == "personal_message":
            job = pending_personal.get(ADMIN_ID)
            if not job:
                admin_action_waiting.pop(ADMIN_ID, None)
                return

            job.update({
                "source_chat_id": message.chat.id,
                "message_id": message.message_id,
            })
            admin_action_waiting.pop(ADMIN_ID, None)

            try:
                await message.copy_to(ADMIN_ID)
            except Exception:
                pass
            await message.answer(
                "👆 сообщение для предпросмотра\n\nотправить?",
                reply_markup=admin_confirm_keyboard("personal"),
            )
            return

    if not message.text:
        return
    text = message.text.strip()

    user_action = user_action_waiting.get(message.from_user.id)
    # Admin input must be handled by the admin state, never by the user's promo flow.
    if message.from_user.id != ADMIN_ID and user_action == "promo":
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
        has_trial_history = await has_used_trial(message.from_user.id)
        expired_user = (
            bool(has_trial_history and (not user or not user["sub_id"]))
            or bool(user and user["status"] in ("trial", "paid") and not user["sub_id"])
        )

        if not user or not user["sub_id"]:
            if not expired_user:
                await message.answer("❌ сначала оформи подписку.")
                user_action_waiting.pop(message.from_user.id, None)
                return

            email = user["email"] if user and user["email"] else f"tg_{message.from_user.id}"
            created_at = int(user["created_at"]) if user else now
            username = message.from_user.username or "unknown"
            try:
                client = create_client(
                    tg_id=message.from_user.id,
                    email=email,
                    expiry_hours=int(promo["reward_days"]) * 24,
                    group="paid",
                )
                sub_id = client["sub_id"]
                expires_at = int(client["expiry_time"]) // 1000
            except Exception as e:
                logging.exception("failed to create promo subscription")
                await message.answer(f"❌ не удалось активировать промокод: {e}")
                return

            if not await use_promo(code, message.from_user.id, now):
                try:
                    delete_client_by_tg_id(message.from_user.id)
                except Exception:
                    logging.exception("failed to clean up client after rejected promo")
                await message.answer("❌ промокод уже использован тобой или больше недоступен.")
                return

            values = dict(
                tg_id=message.from_user.id,
                username=username,
                email=email,
                sub_id=sub_id,
                subscription_url=client["subscription_url"],
                status="paid",
                created_at=created_at,
                expires_at=expires_at,
            )
            if user:
                await update_user(**values)
            else:
                await create_user(**values)

            user_action_waiting.pop(message.from_user.id, None)
            try:
                await message.bot.send_message(
                    ADMIN_ID,
                    "🎟 активирован промокод и создана подписка\n\n"
                    f"🎟 промокод: {code}\n"
                    f"🎁 срок: +{promo['reward_days']} дней\n"
                    f"👤 кому: @{username if username != 'unknown' else '—'}\n"
                    f"🆔 telegram id: {message.from_user.id}",
                )
            except Exception:
                logging.exception("failed to notify admin about promo activation")

            await message.answer(
                "✅ промокод применён!\n\n"
                f"🎁 создана подписка на {promo['reward_days']} дней.\n"
                f"⏳ осталось: {format_remaining(expires_at)}\n\n"
                "теперь можешь подключиться к vpn.",
                reply_markup=subscription_keyboard(
                    f"https://kitvp.duckdns.org:2096/s/{sub_id}"
                ),
            )
            return

        try:
            updated = add_days_to_client_by_sub_id(
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
            subscription_url=f"https://kitvp.duckdns.org:2096/jsnn/{user['sub_id']}",
            status=user["status"],
            created_at=user["created_at"],
            expires_at=expires_at,
        )

        user_action_waiting.pop(message.from_user.id, None)

        promo_after = await get_promo(code)
        if promo_after and promo_after["max_uses"] > 0:
            promo_remaining = max(
                0,
                promo_after["max_uses"] - promo_after["used_count"],
            )
            remaining_text = str(promo_remaining)
        else:
            remaining_text = "без ограничений"

        username = f"@{message.from_user.username}" if message.from_user.username else "—"
        try:
            await message.bot.send_message(
                ADMIN_ID,
                "🎟 активирован промокод\n\n"
                f"🎟 промокод: {code}\n"
                f"🎁 добавлено: +{promo['reward_days']} дней\n"
                f"👤 кому: {username}\n"
                f"🆔 telegram id: {message.from_user.id}\n"
                f"📦 остаток использований: {remaining_text}",
            )
        except Exception:
            logging.exception("failed to notify admin about promo activation")

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

    if action == "inbound_ids":
        try:
            inbound_ids = [
                int(value)
                for value in text.replace(",", " ").split()
            ]
            if not inbound_ids:
                raise ValueError("укажи хотя бы один inbound ID")
            if any(inbound_id <= 0 for inbound_id in inbound_ids):
                raise ValueError("ID должны быть положительными числами")
            if len(inbound_ids) != len(set(inbound_ids)):
                raise ValueError("повторяющиеся ID не допускаются")
        except ValueError as error:
            await message.answer(
                f"❌ некорректный список: {error}\n\n"
                "пример: 8, 31, 35, 41, 54"
            )
            return

        await set_setting(
            "xui_inbound_ids",
            ",".join(map(str, inbound_ids)),
        )
        set_inbound_ids(inbound_ids)
        admin_action_waiting.pop(ADMIN_ID, None)
        await message.answer(
            "✅ список inbound IDs сохранён.\n\n"
            f"новые клиенты будут создаваться в inbound: {', '.join(map(str, inbound_ids))}\n\n"
            "уже созданные подписки не затронуты.",
            reply_markup=admin_keyboard(),
        )
        return

    if action == "maintenance_message":
        await set_setting("maintenance_message", text)
        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer(
            "✅ сообщение тех. работ обновлено.",
            reply_markup=admin_keyboard(),
        )
        return

    if action == "delete_promo":
        code = text.upper()
        promo = await get_promo(code)
        if not promo:
            await message.answer(
                "❌ промокод не найден.",
                reply_markup=admin_keyboard(),
            )
            admin_action_waiting.pop(message.from_user.id, None)
            return

        admin_action_waiting.pop(message.from_user.id, None)
        await message.answer(
            "⚠️ удалить промокод?\n\n"
            f"🎟 код: {promo['code']}\n"
            f"🎁 дней: {promo['reward_days']}\n"
            f"👥 использований: {promo['used_count']} / "
            f"{'∞' if promo['max_uses'] == 0 else promo['max_uses']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🗑 удалить",
                    callback_data=f"admin_delete_promo_confirm:{code}",
                )],
                [InlineKeyboardButton(text="❌ отмена", callback_data="admin_back")],
            ]),
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







async def broadcast_worker(bot: Bot):
    while True:
        job = await broadcast_queue.get()
        sent = 0
        failed = 0
        blocked = 0
        total = len(job["user_ids"])

        try:
            for target_id in job["user_ids"]:
                while True:
                    try:
                        await bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=job["source_chat_id"],
                            message_id=job["message_id"],
                        )
                        sent += 1
                        break
                    except TelegramForbiddenError:
                        blocked += 1
                        break
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        continue
                    except Exception:
                        failed += 1
                        logging.exception(
                            "broadcast send failed: tg_id=%s",
                            target_id,
                        )
                        break

                await asyncio.sleep(BROADCAST_DELAY)

            await bot.send_message(
                ADMIN_ID,
                "✅ рассылка завершена\n\n"
                f"👥 группа: {job['group_name']}\n"
                f"📨 всего: {total}\n"
                f"✅ отправлено: {sent}\n"
                f"🚫 заблокировали бота: {blocked}\n"
                f"❌ ошибок: {failed}",
                reply_markup=admin_keyboard(),
            )
        except Exception:
            logging.exception("broadcast worker failed")
            try:
                await bot.send_message(
                    ADMIN_ID,
                    "❌ рассылка аварийно остановлена. подробности в логе.",
                    reply_markup=admin_keyboard(),
                )
            except Exception:
                logging.exception("failed to notify admin about broadcast failure")
        finally:
            broadcast_queue.task_done()


async def send_notification(bot: Bot, user, text: str, reply_markup=None) -> bool:
    tg_id = user["tg_id"]

    try:
        await bot.send_message(tg_id, text, reply_markup=reply_markup)
        return True
    except TelegramForbiddenError:
        username = user["username"] or "—"
        is_new_block = await block_notification_user(tg_id, username)

        logging.warning(
            "user blocked bot: tg_id=%s username=%s",
            tg_id,
            username,
        )

        if is_new_block:
            try:
                await bot.send_message(
                    ADMIN_ID,
                    "🚫 пользователь заблокировал бота\n\n"
                    f"👤 username: {username}\n"
                    f"🆔 telegram id: {tg_id}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔓 разблокировать уведомления",
                            callback_data=f"unblock_notifications:{tg_id}",
                        )],
                    ]),
                )
            except Exception:
                logging.exception("failed to notify admin about blocked user")

        return False

async def notifications_worker(bot: Bot):
    while True:
        try:
            now = int(time.time())
            users = await get_active_users()

            for user in users:
                tg_id = user["tg_id"]
                expires_at = int(user["expires_at"] or 0)
                remaining = expires_at - now

                # триал: уведомление за 3 часа до окончания.
                if user["status"] == "trial" and 0 < remaining <= 3 * 3600:
                    if not await notification_was_sent(tg_id, "trial_soon", expires_at):
                        try:
                            sent = await send_notification(
                                bot,
                                user,
                                "⏳ твой trial скоро закончится.\n\n"
                                "осталось меньше 3 часов.\n"
                                "хочешь продолжить пользоваться kitty vpn — купи подписку.\n\n"
                                "если не продлить, через 3 дня после окончания подписка будет удалена, "
                                "а ссылка перестанет работать.",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="💳 купить подписку", callback_data="purchase", style=ButtonStyle.PRIMARY)],
                                ]),
                            )
                            if sent:
                                await mark_notification_sent(tg_id, "trial_soon", expires_at)
                        except Exception:
                            logging.exception("failed to send trial reminder")

                if user["status"] == "paid" and remaining > 0:
                    # если до конца <= часа, отправляем и суточное, если оно ещё не ушло.
                    if remaining <= 24 * 3600:
                        if not await notification_was_sent(tg_id, "subscription_day", expires_at):
                            try:
                                sent = await send_notification(
                                    bot,
                                    user,
                                    "⏳ подписка закончится в ближайшие сутки.\n\n"
                                    "продли её заранее, чтобы не потерять доступ.\n\n"
                                    "если не продлить, через 3 дня после окончания подписка будет удалена, "
                                    "а ссылка перестанет работать.",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="💳 продлить подписку", callback_data="purchase", style=ButtonStyle.PRIMARY)],
                                    ]),
                                )
                                if sent:
                                    await mark_notification_sent(tg_id, "subscription_day", expires_at)
                            except Exception:
                                logging.exception("failed to send day subscription reminder")

                    if remaining <= 3600:
                        if not await notification_was_sent(tg_id, "subscription_hour", expires_at):
                            try:
                                sent = await send_notification(
                                    bot,
                                    user,
                                    "⚠️ подписка закончится примерно через час.\n\n"
                                    "продли её сейчас, чтобы vpn продолжил работать без перерыва.\n\n"
                                    "если не продлить, через 3 дня после окончания подписка будет удалена, "
                                    "а ссылка перестанет работать.",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="💳 продлить подписку", callback_data="purchase", style=ButtonStyle.PRIMARY)],
                                    ]),
                                )
                                if sent:
                                        await mark_notification_sent(tg_id, "subscription_hour", expires_at)
                            except Exception:
                                logging.exception("failed to send hour subscription reminder")

                if remaining <= 0:
                    if not await notification_was_sent(tg_id, "subscription_expired", expires_at):
                        try:
                            sent = await send_notification(
                                bot,
                                user,
                                "❌ срок подписки закончился.\n\n"
                                "через 3 дня без продления подписка будет удалена из системы, "
                                "а ссылка перестанет работать.\n\n"
                                "купи новую подписку, чтобы снова пользоваться kitty vpn.",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="💳 купить подписку", callback_data="purchase", style=ButtonStyle.PRIMARY)],
                                ]),
                            )
                            if sent:
                                await mark_notification_sent(tg_id, "subscription_expired", expires_at)
                        except Exception:
                            logging.exception("failed to send expiration notification")

                # удаляем просроченную подписку после пяти дней без продления.
                grace_period = SUBSCRIPTION_DELETE_AFTER_DAYS * 24 * 3600
                if remaining <= -grace_period:
                    try:
                        current_user = await get_user(tg_id)
                        current_expiry = (
                            int(current_user["expires_at"] or 0)
                            if current_user else 0
                        )
                        current_sub_id = (
                            current_user["sub_id"] if current_user else None
                        )

                        # Повторно проверяем БД, чтобы не удалить продлённую подписку
                        # по устаревшей записи из списка активных пользователей.
                        if (
                            current_user
                            and current_sub_id
                            and current_expiry == expires_at
                            and current_expiry + grace_period <= int(time.time())
                        ):
                            client = get_client(tg_id=tg_id)
                            if client:
                                client_data = client.get("client", client)
                                client_expiry = (
                                    int(client_data.get("expiryTime") or 0) // 1000
                                )
                                # Если в панели срок уже обновлён, не удаляем клиента.
                                if client_expiry + grace_period > int(time.time()):
                                    continue
                                delete_client_by_tg_id(tg_id)

                            latest_user = await get_user(tg_id)
                            if (
                                latest_user
                                and latest_user["sub_id"] == current_sub_id
                                and int(latest_user["expires_at"] or 0) == current_expiry
                            ):
                                await update_user(
                                    tg_id=tg_id,
                                    username=latest_user["username"],
                                    email=latest_user["email"],
                                    sub_id=None,
                                    subscription_url=None,
                                    status=latest_user["status"],
                                    created_at=latest_user["created_at"],
                                    expires_at=current_expiry,
                                )
                                logging.info(
                                    "deleted expired subscription for user %s",
                                    tg_id,
                                )
                    except Exception:
                        logging.exception(
                            "failed to delete expired subscription for user %s",
                            tg_id,
                        )

                # отслеживаем новые HWID-устройства.
                try:
                    client = get_client(tg_id=tg_id)
                    if client:
                        client_data = client.get("client", client)
                        email = client_data.get("email") or user["email"]
                        devices = get_hwid_devices(email)
                        snapshots = await get_device_snapshots(tg_id)
                        known = {row["device_key"] for row in snapshots}

                        for device in devices:
                            key = str(
                                device.get("fingerprint")
                                or device.get("hwid")
                                or device.get("id")
                                or ""
                            )
                            if not key or key in known:
                                continue

                            name = (
                                device.get("deviceModel")
                                or device.get("deviceOs")
                                or device.get("userAgent")
                                or "неизвестное устройство"
                            )
                            first_seen = int(
                                device.get("firstSeen")
                                or device.get("firstSeenAt")
                                or now
                            )
                            if first_seen > 10_000_000_000:
                                first_seen //= 1000

                            # первая синхронизация не должна спамить старыми устройствами.
                            if not snapshots:
                                await save_device_snapshot(tg_id, key, name, first_seen)
                                known.add(key)
                                continue

                            await save_device_snapshot(tg_id, key, name, first_seen)
                            known.add(key)

                            dt = datetime.fromtimestamp(first_seen).strftime("%d.%m.%Y %H:%M")
                            await send_notification(
                                bot,
                                user,
                                "📱 подключено новое устройство!\n\n"
                                f"устройство: {name}\n"
                                f"подключение: {dt}\n\n"
                                "если это не ты — проверь список устройств.",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="📱 открыть устройства", callback_data="devices", style=ButtonStyle.PRIMARY)],
                                ]),
                            )
                except Exception:
                    logging.exception("failed to check devices")

        except Exception:
            logging.exception("notification worker failed")

        await asyncio.sleep(60)


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    stored_inbound_ids = await get_setting("xui_inbound_ids")
    if stored_inbound_ids:
        try:
            set_inbound_ids([
                int(value)
                for value in stored_inbound_ids.replace(" ", "").split(",")
                if value
            ])
        except (TypeError, ValueError):
            logging.exception(
                "invalid xui_inbound_ids setting; using defaults %s",
                DEFAULT_INBOUND_IDS,
            )
            set_inbound_ids(DEFAULT_INBOUND_IDS)
    bot = Bot(token=BOT_TOKEN)
    try:
        started_at = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await bot.send_message(
            ADMIN_ID,
            "🟢 бот запущен\\n\\n"
            f"🕐 время запуска: {started_at}",
        )
    except Exception:
        logging.exception("failed to notify admin about bot startup")

    notification_worker_task = asyncio.create_task(notifications_worker(bot))
    broadcast_worker_task = asyncio.create_task(broadcast_worker(bot))
    expired_cleanup_task = asyncio.create_task(expired_subscription_cleanup_worker())
    try:
        await dp.start_polling(bot)
    finally:
        notification_worker_task.cancel()
        broadcast_worker_task.cancel()
        expired_cleanup_task.cancel()
        for task in (notification_worker_task, broadcast_worker_task, expired_cleanup_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
