"""Состояния для заказа товара и отправки отзывов клиентом."""
from aiogram.fsm.state import State, StatesGroup


class FSMReview(StatesGroup):
    """Состояния для процесса отправки отзыва пользователем."""

    select_product = State()
    text = State()
    photo = State()
    contact = State()


class FSMOrder(StatesGroup):
    """Состояние для заказа товара на пункт выдачи CDEK."""

    select_product = State()
    select_quantity = State()
    enter_city = State()
    select_pvz = State()
    request_contact = State()
    confirm = State()


class FSMSuggestions(StatesGroup):
    """Состояние для жалоб и предложений."""

    text = State()
    photo = State()
    contact = State()
