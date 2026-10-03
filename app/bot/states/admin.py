from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния пошаговых административных сценариев."""

    waiting_broadcast_text = State()
    waiting_personal_target = State()
    waiting_personal_message = State()
    waiting_create_promo = State()
    waiting_delete_promo = State()
    waiting_maintenance_message = State()
    waiting_bind_subscription = State()
    waiting_create_paid_user = State()
    waiting_renew_subscription = State()
    waiting_ban_user = State()
