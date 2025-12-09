"""
Модуль для управления клавиатурами клиента для Telegram-бота.

Содержит все Reply- и Inline-клавиатуры, используемые в клиентской части бота,
а также вспомогательные функции для форматирования адресов ПВЗ и построения
пагинированных интерфейсов.

Основные функции:
- Отображение главного меню и навигации.
- Выбор товара для отзыва или заказа.
- Пагинация отзывов и списка пунктов выдачи (ПВЗ).
- Подтверждение заказа и отправка предложений.
- Обработка и сокращение адресов ПВЗ с удалением названия города.

Клавиатуры разделены по сценариям использования:
  • Общие (главное меню, ссылка на магазин),
  • Отзывы,
  • Оформление заказа (выбор товара → выбор ПВЗ → подтверждение).

Вспомогательные утилиты:
  • `clean_address_label` — удаляет префиксы вроде 'Адрес:', 'ПВЗ:'.
  • `extract_street_address` — извлекает уличную часть адреса, исключая город.

"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import WB
import re

b1 = KeyboardButton(text='ℹ️ Что умеет бот')
b2 = KeyboardButton(text='🍵 Ассортимент')
b3 = KeyboardButton(text='🛒 Ссылка на магазин')
b4 = KeyboardButton(text='⭐ Оставить отзыв')
b5 = KeyboardButton(text='🛒 Оформить заказ')
b6 = KeyboardButton(text='✅ Предложения')
kb_client = ReplyKeyboardMarkup(
    keyboard=[
        [b1, b2],
        [b3, b4],
        [b5, b6]
        ],
    resize_keyboard=True
)
"""Основная клавиатура для клиентов.

Отображается внизу чата и содержит шесть основных функций бота:
— справка о возможностях,
— просмотр ассортимента,
— переход к магазину на Wildberries,
— оставить отзыв,
— оформить заказ,
— отправить предложения.
"""
kb_inline = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text=' Wildberries', url=WB)
    ],
])
"""Inline-клавиатура с прямой ссылкой на магазин.

Используется при запросе «Ссылка на магазин».
Содержит одну кнопку, ведущую на страницу магазина Wildberries.
"""
reviews_choice_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text='✏️ Оставить отзыв', callback_data='review:start'
        )
    ]
])
"""Inline-клавиатура для инициации процесса оставления отзыва.

Появляется после нажатия кнопки «⭐ Оставить отзыв» в главном меню.
Содержит одну кнопку для запуска FSM-сценария отзыва.
"""
suggestions_choice_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text='✏️ Предложения', callback_data='suggestions:start'
        )
    ]
])
"""Inline-клавиатура для инициации отправки предложения или обращения.

Появляется после нажатия кнопки «✅ Предложения» в главном меню.
Содержит одну кнопку для запуска FSM-сценария предложения.
"""
skip_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(
        text="Пропустить", callback_data="skip_photo"
        )]]
)
"""Inline-клавиатура для пропуска добавления фото."""


def get_review_product_selection_kb(products: list[dict]):
    """Создаёт inline-клавиатуру для выбора товара при отзыве."""
    buttons = [
        [InlineKeyboardButton(
            text=prod['name'],
            callback_data=f"review_product_{prod['id']}"
        )]
        for prod in products
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_review_button(product_id: int):
    """Создаёт inline-клавиатуру с кнопкой «Отзывы» для конкретного товара.

    Args:
        product_id: Идентификатор товара.

    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой,
                              callback_data: 'show_reviews_{product_id}'.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text='⭐ Отзывы',
                callback_data=f'show_reviews_{product_id}'
            )
        ]
    ])


def get_reviews_pagination_kb(
        product_id: int, page: int, total_reviews: int, per_page: int = 3
):
    """Создаёт клавиатуру пагинации для отображения отзывов о товаре.

    Args:
        product_id: Идентификатор товара.
        page: Текущая страница (начинается с 1).
        total_reviews: Общее количество отзывов.
        per_page: Количество отзывов на одной странице (по умолчанию 3).

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками навигации:
                              - "← Назад" (если не первая страница),
                              - номер текущей страницы / общее число страниц,
                              - "Вперёд →" (если не последняя страница).
                              Недостающие кнопки заменяются пустыми.
    """
    total_pages = (total_reviews + per_page - 1) // per_page or 1
    page = max(1, min(page, total_pages))

    buttons = []
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text='← Назад', callback_data=f'reviews_page_{product_id}_{page-1}'
        ))
    else:
        nav_buttons.append(InlineKeyboardButton(
            text=' ', callback_data='noop'))

    nav_buttons.append(InlineKeyboardButton(
        text=f'{page} / {total_pages}', callback_data='noop'))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(
            text='Вперёд →',
            callback_data=f'reviews_page_{product_id}_{page+1}'
        )
        )
    else:
        nav_buttons.append(InlineKeyboardButton(
            text=' ', callback_data='noop'))

    buttons.append(nav_buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_selection_kb(products):
    """Создаёт inline-клавиатуру для выбора товара при оформлении заказа.

    Args:
        products: Список словарей с ключами 'id' и 'name'.

    Returns:
        InlineKeyboardMarkup: Вертикальный список кнопок,
                              каждая соответствует одному товару.
                              Callback_data: 'order_prod_{id}'.
    """
    kb = []
    for p in products:
        kb.append(
            [InlineKeyboardButton(
                text=p['name'], callback_data=f'order_prod_{p['id']}'
                )]
        )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_pvz_inline_kb(pvz_list: list[dict]):
    """Создаёт inline-клавиатуру со списком всех ПВЗ (пунктов выдачи заказов).

    Args:
        pvz_list: Список словарей с ключами 'name', 'address', 'code'.

    Returns:
        Каждая кнопка содержит усечённое название и адрес ПВЗ
            (макс. 40 символов + "...").
            Последняя кнопка — «❌ Отменить» с callback_data 'order_cancel'.
    """
    kb = []
    for pvz in pvz_list:
        text = f"{pvz['name']} — {pvz['address']}"
        kb.append(
            [InlineKeyboardButton(
                text=text[:40] + '...', callback_data=f"pvz_{pvz['code']}"
                )]
        )
    kb.append(
        [InlineKeyboardButton(
            text='❌ Отменить', callback_data='order_cancel')]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_order_confirmation_kb():
    """Возвращает клавиатуру для подтверждения или отмены заказа.

    Returns:
        Две кнопки:
            - «✅ Подтвердить» → callback_data 'order_confirm',
            - «❌ Отменить» → callback_data 'order_cancel'.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='✅ Подтвердить', callback_data='order_confirm'
                )
            ],
            [
                InlineKeyboardButton(
                    text='❌ Отменить', callback_data='order_cancel'
                )
            ]
        ]
    )


def clean_address_label(text: str):
    """Убирает 'Как добраться:', 'Адрес:' и подобные префиксы."""
    if not text:
        return ""
    patterns = [
        r"как добраться\s*[:\-]?\s*",
        r"пункт выдачи\s*[:\-]?\s*",
        r"пвз\s*[:\-]?\s*",
    ]
    cleaned = text.strip()
    for p in patterns:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_street_address(full_address: str, city_name: str):
    """Извлекает улицу и дом из полного адреса, удаляя название города.

    Args:
        full_address: Полный адрес, возможно включающий город.
        city_name: Название города, которое нужно удалить из адреса.

    Returns:
        str: Адрес без города. Если результат пуст — возвращается исходный.
    """
    if not full_address or not city_name:
        return full_address
    patterns = [
        rf'г\.?\s*{re.escape(city_name)}',
        rf'город\s+{re.escape(city_name)}',
        rf'{re.escape(city_name)}',
        rf'{re.escape(city_name)},?\s*',
    ]
    cleaned = full_address
    for p in patterns:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^[,\s\.]+', '', cleaned)
    cleaned = re.sub(r'[,\s\.]+$', '', cleaned)
    cleaned = re.sub(r'[,\s]{2,}', ', ', cleaned)
    return cleaned.strip() or full_address


def get_pvz_pagination_kb(
        pvz_list: list[dict],
        city_name: str,
        page: int = 0,
        items_per_page: int = 5):
    """Создаёт пагинированную inline-клавиатуру для выбора ПВЗ в городе.

    Args:
        pvz_list: Список ПВЗ (словари с ключами 'code', 'address', 'name').
        city_name: Название города (используется для обрезки адреса).
        page: Номер страницы (начинается с 0).
        items_per_page: Количество ПВЗ на одной странице (по умолчанию 5).

    Returns:
        Кнопки с улицами ПВЗ (без названия города, до 60 символов).
        Внизу — кнопки навигации «⬅️ Назад» / «➡️ Вперёд»,
        если применимо.
        Callback_data для ПВЗ: 'pvz_{code}',
        для навигации: 'pvz_page_{page_number}'.
    """
    start = page * items_per_page
    end = start + items_per_page
    current_page = pvz_list[start:end]
    buttons = []
    for i, pvz in enumerate(current_page):
        address = (pvz.get('address') or '').strip()
        if address:
            street = extract_street_address(address, city_name or "")
        else:
            name = (pvz.get('name') or '').strip()
            if name:
                name_clean = re.sub(r'^[A-Z0-9]+,\s*', '', name)
                street = extract_street_address(name_clean, city_name or "")
            else:
                street = f"ПВЗ {pvz['code']}"
        street = street.strip()
        if not street:
            street = f"ПВЗ {pvz['code']}"
        if len(street) > 60:
            street = street[:57] + '...'
        buttons.append([
            InlineKeyboardButton(
                text=street,
                callback_data=f"pvz_{pvz['code']}"
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text='⬅️ Назад', callback_data=f'pvz_page_{page-1}')
        )
    if end < len(pvz_list):
        nav.append(InlineKeyboardButton(
            text='➡️ Вперёд', callback_data=f'pvz_page_{page+1}')
        )
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)
