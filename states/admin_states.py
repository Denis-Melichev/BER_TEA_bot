"""Состояния для меню администратора."""
from aiogram.fsm.state import State, StatesGroup


class FSMAdmin(StatesGroup):
    """Состояние добавления нового товара."""

    photo = State()
    name = State()
    weight = State()
    description = State()
    price = State()


class FSMAdminEdit(StatesGroup):
    """Состояние редактирования товара."""

    waiting_for_field = State()
    editing_photo = State()
    editing_name = State()
    editing_weight = State()
    editing_description = State()
    editing_price = State()
