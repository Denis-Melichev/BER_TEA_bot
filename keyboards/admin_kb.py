"""
Модуль клавиатур для административной панели Telegram-бота.

Предназначен для управления товарами и отзывами: загрузка новых товаров,
просмотр ассортимента, редактирование и удаление существующих записей.
Все клавиатуры разделены по сценариям взаимодействия администратора с ботом.

Основные возможности:
- Главное меню администратора.
- Выбор товара для редактирования или удаления.
- Подтверждение удаления (товара или отзыва).
- Выбор конкретного поля товара для изменения.
- Управление отзывами (удаление).

Использует aiogram для создания Reply- и Inline-клавиатур.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from typing import List, Dict, Any
from config import PRODUCT_LIST

b1 = KeyboardButton(text='ℹ️ Загрузить')
b2 = KeyboardButton(text='🍵 Ассортимент')
b3 = KeyboardButton(text='🛒 Изменить')
b4 = KeyboardButton(text='⭐ Отзывы')
b5 = KeyboardButton(text='📊 Статистика')
b6 = KeyboardButton(text="🗑️ Сбросить статистику")

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [b1, b2],
        [b3, b4],
        [b5, b6]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие...'
)
"""Основная клавиатура для администратора.

Отображается как постоянное меню внизу чата.
Содержит четыре действия:
- «ℹ️ Загрузить» — добавить новый товар,
- «🍵 Ассортимент» — просмотреть список товаров,
- «🛒 Изменить» — редактировать или удалить товар,
- «⭐ Отзывы» — управлять отзывами пользователей.
"""


def get_edit_product_selection_kb(products: List[Dict[str, Any]]):
    """
    Создаёт inline-клавиатуру выбора товара для редактирования и удаления.

    Args:
        products: Список товаров. Каждый товар должен содержать 'id' и 'name'.

    Returns:
        InlineKeyboardMarkup с кнопками:
        - «✏️ {название}» → callback_data='edit_product_{id}',
        - «🗑 Удалить» → callback_data='confirm_delete_product_{id}'.
    """
    buttons = []
    for prod in products:
        name = prod.get('name', f'Товар {prod["id"]}')
        product_id = prod['id']
        buttons.append([
            InlineKeyboardButton(
                text=f'✏️ {name}',
                callback_data=f'edit_product_{product_id}'
            ),
            InlineKeyboardButton(
                text='🗑 Удалить',
                callback_data=f'confirm_delete_product_{product_id}'
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_delete_product_kb(product_id: int):
    """
    Создаёт клавиатуру подтверждения удаления товара.

    Args:
        product_id: ID товара в базе данных.

    Returns:
        InlineKeyboardMarkup с кнопками:
        - «✅ Да» → callback_data='delete_product_{product_id}',
        - «❌ Нет» → callback_data='cancel_delete_product'.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text='✅ Да',
                callback_data=f'delete_product_{product_id}'
            ),
            InlineKeyboardButton(
                text='❌ Нет',
                callback_data='cancel_delete_product'
            )
        ]
    ])


def get_edit_field_kb():
    """Создаёт клавиатуру для выбора поля, которое нужно отредактировать."""
    field_labels = {
        'photo_file_id': 'Фото',
        'name': 'Название',
        'weight': 'Вес',
        'description': 'Описание',
        'price': 'Цена',
    }

    buttons = []
    for field in PRODUCT_LIST:
        label = field_labels.get(field, field.capitalize())
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"edit_field_{field}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text='✅ Готово', callback_data='edit_done')
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_delete_kb(review_id: int):
    """Создаёт клавиатуру подтверждения удаления отзыва.

    Args:
        review_id: Уникальный идентификатор отзыва (обычно из БД).

    Returns:
        Две кнопки:
        - «✅ Да» → callback_data='delete_review_{review_id}',
        - «❌ Нет» → callback_data='cancel_delete_{review_id}'.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text='✅ Да', callback_data=f'delete_review_{review_id}'),
            InlineKeyboardButton(
                text='❌ Нет', callback_data=f'cancel_delete_{review_id}')
        ]
    ])


def get_review_delete_kb(review_id: int):
    """Клавиатура с кнопкой 'Удалить' под отзывом."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text='🗑 Удалить', callback_data=f'confirm_delete_{review_id}')]
    ])


def get_confirm_clear_stats_kb():
    """Клавиатура подтверждения удаления статистики."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, обнулить", callback_data="clear_stats_confirm"),
            InlineKeyboardButton(
                text="❌ Отмена", callback_data="clear_stats_cancel")
        ]
    ])
