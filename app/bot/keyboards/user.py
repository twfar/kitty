from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

ADMIN_URL = "https://t.me/kittyvpnoff?direct"


def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню пользователя."""

    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 подключиться", callback_data="connect")
    builder.button(text="📱 устройства", callback_data="devices")
    builder.button(text="💳 купить / продлить", callback_data="purchase")
    builder.button(text="🆘 поддержка", callback_data="support")
    builder.adjust(1)
    return builder.as_markup()


def trial_keyboard() -> InlineKeyboardMarkup:
    """Кнопка получения trial."""

    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 начать trial", callback_data="start_trial")
    return builder.as_markup()


def devices_keyboard() -> InlineKeyboardMarkup:
    """Меню управления устройствами."""

    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 удалить все устройства",
        callback_data="delete_all_hwid",
    )
    builder.button(text="🔙 назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def support_keyboard() -> InlineKeyboardMarkup:
    """Кнопка связи с администратором."""

    builder = InlineKeyboardBuilder()
    builder.button(text="💬 написать админу", url=ADMIN_URL)
    return builder.as_markup()
