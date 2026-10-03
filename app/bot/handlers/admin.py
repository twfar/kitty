from __future__ import annotations

from datetime import datetime, timezone

from aiogram import BaseMiddleware, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states.admin import AdminStates
from app.core.config import Settings
from app.database.crud import UserRepository
from app.services.admin import AdminService
from app.services.notification import NotificationService
from app.services.xui_client import XuiClient


router = Router(name="admin")


class AdminOnlyMiddleware(BaseMiddleware):
    """Пропускает административные события только владельцу бота."""

    async def __call__(self, handler, event, data):
        settings = data.get("settings")
        user = getattr(event, "from_user", None)
        if not isinstance(settings, Settings):
            return None
        if user is None or user.id != settings.admin_id:
            if isinstance(event, CallbackQuery):
                await event.answer("доступ запрещён", show_alert=True)
            return None
        return await handler(event, data)


router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyMiddleware())


def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="💬 личное сообщение", callback_data="admin:personal")],
            [InlineKeyboardButton(text="🎟 промокоды", callback_data="admin:promos")],
            [InlineKeyboardButton(text="🔧 технические работы", callback_data="admin:maintenance")],
            [InlineKeyboardButton(text="🗑 очистить тестовый аккаунт", callback_data="admin:clear_test")],
        ]
    )


def _back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin:back")]
        ]
    )


def _broadcast_groups() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 все", callback_data="admin:broadcast:all"),
                InlineKeyboardButton(text="🟢 активные", callback_data="admin:broadcast:active"),
            ],
            [
                InlineKeyboardButton(text="🧪 trial", callback_data="admin:broadcast:trial"),
                InlineKeyboardButton(text="💳 paid", callback_data="admin:broadcast:paid"),
            ],
            [InlineKeyboardButton(text="⌛ истёкшие", callback_data="admin:broadcast:expired")],
            [InlineKeyboardButton(text="🔙 назад", callback_data="admin:back")],
        ]
    )


def _admin_service(
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> AdminService:
    from app.database.crud import BotSettingRepository, PromoCodeRepository

    return AdminService(
        settings=settings,
        user_repository=user_repository,
        promo_repository=PromoCodeRepository(session),
        setting_repository=BotSettingRepository(session),
        xui_client=xui_client,
    )


@router.message(Command("kittyadmin"))
async def kitty_admin(message: Message) -> None:
    await message.answer(
        "⚙️ кабинет директора\n\nвыбери действие:",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "⚙️ кабинет директора\n\nвыбери действие:",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "📢 выбери группу получателей:",
        reply_markup=_broadcast_groups(),
    )


@router.callback_query(lambda callback: callback.data.startswith("admin:broadcast:"))
async def broadcast_group(callback: CallbackQuery, state: FSMContext) -> None:
    group = callback.data.rsplit(":", 1)[1]
    await state.set_state(AdminStates.waiting_broadcast_text)
    await state.update_data(group=group)
    await callback.answer()
    await callback.message.edit_text(
        "📢 теперь отправь одно сообщение для рассылки.\n\n"
        "поддерживаются обычные telegram-сообщения.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_broadcast_text)
async def broadcast_message(
    message: Message,
    state: FSMContext,
) -> None:
    from app.tasks.broadcast import broadcast_task

    data = await state.get_data()
    group = str(data.get("group", "all"))

    await broadcast_task.kiq(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        group=group,
    )
    await state.clear()
    await message.answer(
        "📢 рассылка поставлена в надёжную очередь Redis.\n\n"
        "воркер отправит сообщения с задержкой и повторит задачу после сбоя.",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:personal")
async def personal_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_personal_target)
    await callback.answer()
    await callback.message.edit_text(
        "💬 личное сообщение\n\n"
        "отправь telegram id или @username пользователя.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_personal_target)
async def personal_target(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    target = (message.text or "").strip()
    service = AdminService(
        settings=message.bot.get("settings") if False else None,  # type: ignore[arg-type]
        user_repository=UserRepository(session),
        promo_repository=None,  # type: ignore[arg-type]
        setting_repository=None,  # type: ignore[arg-type]
        xui_client=None,  # type: ignore[arg-type]
    )
    user = await service.find_user(target)
    if user is None:
        await message.answer("❌ пользователь не найден.", reply_markup=_back())
        return

    await state.set_state(AdminStates.waiting_personal_message)
    await state.update_data(target_tg_id=user.tg_id)
    await message.answer(
        f"👤 пользователь: @{user.username or '—'}\n"
        f"🆔 id: {user.tg_id}\n\n"
        "теперь отправь сообщение.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_personal_message)
async def personal_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    if not isinstance(target_tg_id, int):
        await state.clear()
        await message.answer("❌ цель сообщения потеряна.", reply_markup=_keyboard())
        return

    user = await UserRepository(session).get_by_tg_id(target_tg_id)
    if user is None:
        await state.clear()
        await message.answer("❌ пользователь не найден.", reply_markup=_keyboard())
        return

    service = NotificationService(session=session, bot=message.bot)
    delivered = await service.copy(
        user=user,
        notification_type="admin_personal",
        marker=str(message.message_id),
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
    )
    await session.commit()
    await state.clear()
    await message.answer(
        "✅ сообщение отправлено." if delivered else "❌ сообщение не отправлено.",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:promos")
async def promos_menu(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    promos = await _admin_service_from_callback(callback, session)
    items = await promos.list_promos()
    await callback.answer()

    if not items:
        text = "🎟 промокоды\n\nпромокодов пока нет."
    else:
        lines = ["🎟 промокоды", ""]
        now = datetime.now(timezone.utc)
        for promo in items:
            limit = "∞" if promo.max_uses is None else str(promo.max_uses)
            expires = (
                "без срока"
                if promo.expires_at is None
                else promo.expires_at.astimezone(timezone.utc).strftime(
                    "%d.%m.%Y %H:%M"
                )
            )
            status = "активен"
            if not promo.is_active:
                status = "выключен"
            elif promo.expires_at is not None and promo.expires_at <= now:
                status = "истёк"
            elif promo.max_uses is not None and promo.uses_count >= promo.max_uses:
                status = "лимит исчерпан"
            lines.append(
                f"🎟 {promo.code} — +{promo.reward_days} д.\n"
                f"использований: {promo.uses_count} / {limit}\n"
                f"срок: {expires}\n"
                f"статус: {status}"
            )
        text = "\n\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ создать", callback_data="admin:promo:create")],
                [InlineKeyboardButton(text="🗑 удалить", callback_data="admin:promo:delete")],
                [InlineKeyboardButton(text="🔙 назад", callback_data="admin:back")],
            ]
        ),
    )


async def _admin_service_from_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> AdminService:
    from app.database.crud import BotSettingRepository, PromoCodeRepository

    settings = callback.bot.get("settings") if False else None
    del settings
    raise RuntimeError("use injected admin_service")


@router.callback_query(lambda callback: callback.data == "admin:promo:create")
async def promo_create_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_create_promo)
    await callback.answer()
    await callback.message.edit_text(
        "🎟 создание промокода\n\n"
        "отправь одной строкой:\n"
        "КОД ДНИ ЛИМИТ СРОК_В_ДНЯХ\n\n"
        "пример: KITTY7 7 10 30\n"
        "лимит 0 — без ограничений\n"
        "срок 0 — бессрочно.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_create_promo)
async def promo_create(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 4:
        await message.answer("❌ формат: КОД ДНИ ЛИМИТ СРОК_В_ДНЯХ")
        return

    try:
        code, days_raw, limit_raw, expiry_raw = parts
        service = _admin_service(
            session,
            settings,
            xui_client,
            user_repository,
        )
        promo = await service.create_promo(
            code=code,
            reward_days=int(days_raw),
            max_uses=int(limit_raw),
            expires_in_days=int(expiry_raw) or None,
        )
        await session.commit()
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.clear()
    await message.answer(
        f"✅ промокод {promo.code} создан.\n"
        f"дни: {promo.reward_days}\n"
        f"лимит: {promo.max_uses or '∞'}",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:promo:delete")
async def promo_delete_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_delete_promo)
    await callback.answer()
    await callback.message.edit_text(
        "🗑 отправь код промокода, который нужно удалить.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_delete_promo)
async def promo_delete(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    service = _admin_service(session, settings, xui_client, user_repository)
    deleted = await service.delete_promo(message.text or "")
    await session.commit()
    await state.clear()
    await message.answer(
        "✅ промокод удалён." if deleted else "❌ промокод не найден.",
        reply_markup=_keyboard(),
    )


@router.callback_query(lambda callback: callback.data == "admin:maintenance")
async def maintenance_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    service = _admin_service(session, settings, xui_client, user_repository)
    enabled, text = await service.get_maintenance()
    await callback.answer()
    await callback.message.edit_text(
        "🔧 технические работы\n\n"
        f"статус: {'включены' if enabled else 'выключены'}\n\n"
        f"сообщение:\n{text}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔴 выключить" if enabled else "🟢 включить",
                        callback_data="admin:maintenance:toggle",
                    )
                ],
                [InlineKeyboardButton(text="✏️ изменить сообщение", callback_data="admin:maintenance:text")],
                [InlineKeyboardButton(text="🔙 назад", callback_data="admin:back")],
            ]
        ),
    )


@router.callback_query(lambda callback: callback.data == "admin:maintenance:toggle")
async def maintenance_toggle(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    service = _admin_service(session, settings, xui_client, user_repository)
    enabled, _ = await service.get_maintenance()
    await service.set_maintenance(enabled=not enabled)
    await session.commit()
    await callback.answer("режим обновлён")
    await maintenance_menu(
        callback,
        session,
        settings,
        xui_client,
        user_repository,
    )


@router.callback_query(lambda callback: callback.data == "admin:maintenance:text")
async def maintenance_text_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_maintenance_message)
    await callback.answer()
    await callback.message.edit_text(
        "✏️ отправь новое сообщение технических работ.",
        reply_markup=_back(),
    )


@router.message(AdminStates.waiting_maintenance_message)
async def maintenance_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    service = _admin_service(session, settings, xui_client, user_repository)
    await service.set_maintenance(enabled=(await service.get_maintenance())[0], message=message.text or "")
    await session.commit()
    await state.clear()
    await message.answer("✅ сообщение технических работ обновлено.", reply_markup=_keyboard())


@router.callback_query(lambda callback: callback.data == "admin:clear_test")
async def clear_test(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    xui_client: XuiClient,
    user_repository: UserRepository,
) -> None:
    service = _admin_service(session, settings, xui_client, user_repository)
    await service.clear_test_account(settings.test_user_tg_id)
    await session.commit()
    await callback.answer("тестовый аккаунт очищен")
    await callback.message.edit_text(
        f"✅ тестовый аккаунт {settings.test_user_tg_id} очищен.",
        reply_markup=_keyboard(),
    )


__all__ = ["router"]
