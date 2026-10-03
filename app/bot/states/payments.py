from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    """Состояния пошаговых сценариев покупки подписки."""

    waiting_promo_code = State()
    waiting_payment_confirmation = State()
