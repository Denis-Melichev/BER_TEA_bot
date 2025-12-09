"""
Маршрутизатор для обработки предложений и обращений от пользователей.

Позволяет клиентам отправить текстовое предложение,
прикрепить фото (опционально) и указать контактные данные.
Все сообщения пересылаются администратору бота.
Использует FSM для пошагового сбора информации.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.client_states import FSMSuggestions
from keyboards.client_kb import suggestions_choice_kb, skip_kb
from utils.validators import is_valid_phone
from utils.suggestion_review_helpers import (
    handle_photo_step,
    handle_contact_step,
    handle_skip_photo
)
router = Router()


@router.message(F.text == '✅ Предложения')
async def handle_suggestions_button(message: Message):
    """
    Обрабатывает нажатие кнопки «Предложения».

    Предлагает пользователю описать проблему.
    """
    await message.answer(
        'Оставить предложение по улучшению?',
        reply_markup=suggestions_choice_kb
    )


@router.message(FSMSuggestions.text)
async def load_suggestions_text(message: Message, state: FSMContext):
    """
    Сохраняет текст предложения и переходит к запросу контактных данных.

    Текст сохраняется в FSM-контекст.
    Переходит к следующему состоянию.
    """
    await state.update_data(text=message.text)
    await message.answer(
        'Пришлите фото (опционально) или нажмите «Пропустить»:',
        reply_markup=skip_kb
    )
    await state.set_state(FSMSuggestions.photo)


@router.message(FSMSuggestions.photo)
async def load_suggestions_photo(message: Message, state: FSMContext):
    """
    Обрабатывает фото в предложении (или его отсутствие).

    Если пользователь прислал фото —
    сохраняет file_id самого большого варианта.
    Если прислал текст — считает, что фото не требуется.
    Переходит к следующему состоянию.
    """
    await handle_photo_step(message, state, FSMSuggestions.contact)


@router.message(FSMSuggestions.contact)
async def load_suggestions_contact(message: Message, state: FSMContext):
    """
    Сохраняет контактные данные и завершает процесс отправки предложения.

    Отправляет уведомление администратору (с фото или без).
    Подтверждает пользователю успешную отправку.
    Сбрасывает состояние FSM.
    """
    await handle_contact_step(
        message,
        state,
        contact_required=True,
        contact_validator=is_valid_phone,
        entity_name="предложение"
    )


@router.callback_query(F.data == 'skip_photo', FSMSuggestions.photo)
async def skip_suggestions_photo(callback: CallbackQuery, state: FSMContext):
    """Обработчик пропуска добавления фото."""
    await handle_skip_photo(callback, state, FSMSuggestions.contact)


@router.callback_query(F.data == 'suggestions:start')
async def start_suggestions(callback: CallbackQuery, state: FSMContext):
    """
    Запускает процесс отправки предложения от пользователя.

    Переводит FSM в состояние ожидания текстового сообщения.
    Подтверждает нажатие кнопки в интерфейсе Telegram.
    """
    await state.set_state(FSMSuggestions.text)
    await callback.message.answer('Пожалуйста, опишите ваше предложение:')
    await callback.answer()
