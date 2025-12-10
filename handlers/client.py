"""
Маршрутизатор для обработки отзывов пользователей в Telegram-боте.

Реализует полный цикл оставления отзыва (с фото и контактом),
просмотр отзывов (общих и по товарам), пагинацию,
а также уведомление администратора.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.client_states import FSMReview, FSMReviewEdit
from database import (
    load_products,
    get_reviews_for_client,
    add_review,
    get_reviews_for_product_paginated,
    get_review_by_id
)
from keyboards.client_kb import (
    skip_kb,
    get_review_product_selection_kb,
    get_reviews_pagination_kb,
    get_review_actions_kb
)
from utils.suggestion_review_helpers import (
    handle_photo_step,
    handle_contact_step,
    handle_skip_photo
)
router = Router()


def save_review_to_db(data, contact, user_id):
    """Функция добавления отзывов в BD."""
    add_review(
        text=data['text'],
        contact=contact,
        user_id=user_id,
        photo_file_id=data.get('photo'),
        product_id=data['product_id']
    )


@router.message(F.text == '⭐ Оставить отзыв')
async def handle_reviews_button(message: Message):
    """
    Обрабатывает нажатие кнопки «Оставить отзыв».

    Предлагает пользователю оставить отзыв.
    """
    user_id = message.from_user.id
    await message.answer(
        'Что вы хотите сделать?',
        reply_markup=get_review_actions_kb(user_id)
    )


@router.message(FSMReview.text)
async def load_review_text(message: Message, state: FSMContext):
    """
    Сохраняет текст отзыва в FSM-контекст и запрашивает фото (опционально).

    Переходит к состоянию ожидания фото или пропуска шага.
    """
    await state.update_data(text=message.text)
    await message.answer(
        'Пришлите фото (опционально) или нажмите «Пропустить»:',
        reply_markup=skip_kb
    )
    await state.set_state(FSMReview.photo)


@router.message(FSMReview.photo)
async def load_review_photo(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение на шаге добавления фото к отзыву.

    Если получено фото — сохраняет file_id самого большого варианта.
    Если получено не фото (например, текст) —
    считает, что фото не прикрепляется.
    Переходит к состоянию запроса контактных данных (опционально).
    """
    await handle_photo_step(message, state, FSMReview.contact)


@router.message(FSMReview.contact)
async def load_review_contact(message: Message, state: FSMContext):
    """
    Сохраняет контактные данные и завершает процесс отправки отзыва.

    Добавляет отзыв в базу данных.
    Отправляет уведомление администратору (с фото или без).
    Подтверждает пользователю успешную отправку.
    Сбрасывает состояние FSM.
    """
    await handle_contact_step(
        message,
        state,
        contact_required=False,
        save_to_db_func=save_review_to_db,
        entity_name='отзыв'
    )


@router.callback_query(F.data == 'skip_photo', FSMReview.photo)
async def skip_review_photo(callback: CallbackQuery, state: FSMContext):
    """Обработчик пропуска добавления фото."""
    await handle_skip_photo(callback, state, FSMReview.contact)


@router.callback_query(F.data == 'review:start')
async def start_review(callback: CallbackQuery, state: FSMContext):
    """
    Запускает процесс оставления отзыва.

    Загружает список товаров и предлагает пользователю выбрать товар,
    к которому будет привязан отзыв.
    Если товаров нет — отправляет соответствующее сообщение.
    """
    products = load_products()
    if not products:
        await callback.message.answer('Нет товаров для отзыва.')
        return

    kb = get_review_product_selection_kb(products)
    await callback.message.edit_text(
        'Выберите товар для отзыва:', reply_markup=kb
    )
    await state.set_state(FSMReview.select_product)
    await callback.answer()


@router.callback_query(F.data.startswith('review_product_'))
async def select_review_product(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор товара для отзыва.

    Проверяет, что FSM находится в состоянии выбора товара.
    Извлекает product_id из callback-данных.
    При некорректном формате — показывает ошибку.
    В противном случае — сохраняет ID и переходит к вводу текста отзыва.
    """
    if await state.get_state() != FSMReview.select_product.state:
        await callback.answer()
        return
    try:
        product_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer('Некорректный выбор товара.', show_alert=True)
        return

    await state.update_data(product_id=product_id)
    await state.set_state(FSMReview.text)
    await callback.message.answer('Напишите ваш отзыв:')
    await callback.answer()


@router.callback_query(F.data == 'review:show')
async def get_reviews(callback: CallbackQuery):
    """
    Отображает последние 5 отзывов.

    Загружает отзывы из базы данных и отправляет их пользователю.
    Поддерживает как отзывы с фото, так и без.
    Если отзывов нет — отправляет соответствующее уведомление.
    """
    await callback.answer()
    reviews = get_reviews_for_client(limit=5)
    if not reviews:
        await callback.message.answer('Пока нет отзывов.')
        return

    for review in reviews:
        text, contact, photo_id = review
        contact_str = contact or 'Аноним'
        caption = f'💬 {text}\n— {contact_str}'
        if photo_id:
            await callback.message.answer_photo(
                photo=photo_id, caption=caption
            )
        else:
            await callback.message.answer(caption)


@router.callback_query(F.data.startswith('show_reviews_'))
async def show_reviews_for_product(callback: CallbackQuery):
    """
    Отображает отзывы по конкретному товару (первая страница).

    Загружает товар по ID и первые отзывы (страница 1).
    Если товар не найден или отзывов нет — отправляет уведомление.
    Иначе — формирует текст и клавиатуру пагинации.
    """
    product_id = int(callback.data.split('_')[-1])

    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)

    if not product:
        await callback.message.answer('Товар не найден.')
        await callback.answer()
        return

    reviews, total = get_reviews_for_product_paginated(product_id, page=1)

    if not reviews:
        await callback.message.answer(
            f"Пока нет отзывов на товар «{product['name']}»."
        )
        await callback.answer()
        return
    reviews_text = f"⭐ Отзывы на «{product['name']}»:\n\n"
    for review in reviews:
        text, contact, _ = review
        contact_str = contact or 'Аноним'
        reviews_text += f"💬 {text}\n— {contact_str}\n\n"

    kb = get_reviews_pagination_kb(product_id, page=1, total_reviews=total)
    await callback.message.answer(reviews_text.strip(), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith('reviews_page_'))
async def reviews_pagination(callback: CallbackQuery):
    """
    Обрабатывает пагинацию отзывов по товару.

    Извлекает product_id и номер страницы из callback-данных.
    Загружает соответствующую страницу отзывов.
    Обновляет сообщение с новым текстом и клавиатурой.
    Если редактирование невозможно (например, текст не изменился),
    отправляет новое сообщение.
    """
    parts = callback.data.split("_")
    product_id = int(parts[2])
    page = int(parts[3])

    reviews, total = get_reviews_for_product_paginated(product_id, page=page)

    if not reviews:
        await callback.message.edit_text('Отзывы не найдены.')
        await callback.answer()
        return
    reviews_text = ''
    for review in reviews:
        text, contact, _ = review
        contact_str = contact or 'Аноним'
        reviews_text += f'💬 {text}\n— {contact_str}\n\n'

    kb = get_reviews_pagination_kb(product_id, page=page, total_reviews=total)

    try:
        await callback.message.edit_text(reviews_text.strip(), reply_markup=kb)
    except Exception:
        await callback.message.answer(reviews_text.strip(), reply_markup=kb)


@router.callback_query(F.data.startswith("edit_review_"))
async def start_edit_review(callback: CallbackQuery, state: FSMContext):
    """Запускает редактирование существующего отзыва."""
    try:
        review_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer('Неверный формат данных.', show_alert=True)
        return
    review = get_review_by_id(review_id)
    if not review:
        await callback.answer('Отзыв не найден.', show_alert=True)
        return
    if review['user_id'] != callback.from_user.id:
        await callback.answer(
            'Вы не можете редактировать чужой отзыв.', show_alert=True)
        return
    await state.set_state(FSMReviewEdit.editing_text)
    await state.update_data(review_id=review_id)
    await callback.message.answer('✏️ Введите новый текст отзыва:')
    await callback.answer()


@router.message(FSMReviewEdit.editing_text)
async def process_edit_text(message: Message, state: FSMContext):
    """Сохраняет новый текст и запрашивает контакт."""
    new_text = message.text.strip()
    if not new_text:
        await message.reply('Текст не может быть пустым. Попробуйте снова:')
        return

    await state.update_data(new_text=new_text)
    await state.set_state(FSMReviewEdit.editing_contact)
    await message.answer(
        '📞 Укажите контакт (или нажмите «Пропустить»):',
        reply_markup=skip_kb
    )


@router.message(FSMReviewEdit.editing_contact)
async def process_edit_contact(message: Message, state: FSMContext):
    """Сохраняет контакт и завершает редактирование."""
    contact = (
        message.text.strip() if message.text.strip()
        not in ['Пропустить', '/skip'] else None)
    await _apply_review_edit(message, state, contact=contact)


@router.callback_query(F.data == 'skip_photo', FSMReviewEdit.editing_contact)
async def skip_edit_contact(callback: CallbackQuery, state: FSMContext):
    """Пропуск контакта при редактировании."""
    await _apply_review_edit(callback.message, state, contact=None)
    await callback.answer()


async def _apply_review_edit(
        message: Message, state: FSMContext, contact: str = None
):
    """Применяет изменения к отзыву."""
    from database import update_review

    data = await state.get_data()
    review_id = data['review_id']
    new_text = data['new_text']

    success = update_review(review_id, new_text, contact)
    if success:
        await message.answer("✅ Отзыв успешно обновлён!")
    else:
        await message.answer("❌ Не удалось обновить отзыв.")

    await state.clear()
