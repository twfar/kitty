from __future__ import annotations

from datetime import datetime, timezone

from aiogram import BaseMiddleware, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states.admin import AdminStates
from app.core.config import Settings
from app.services.admin import AdminService
from app.services.xui_client import XuiClient


router = Router(name="admin")


class AdminOnlyMiddleware(BaseMiddleware):
    """Пропускает административные события только владельцу бота."""

    async def __call__(self, handler, event, data):
        settings = data["settings"]
        if not isinstance(settings, Settings):
            return None
        user = getattr(event, "from_user", None)
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
    user_repository,
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
    settings: Settings,
    xui_client: XuiClient,
    user_repository,
) -> None:
    session = message.bot.get_current?  # type: ignore[attr-defined]
