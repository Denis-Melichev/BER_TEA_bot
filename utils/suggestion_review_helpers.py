"""
Утилиты для обработки многошаговых сценариев отправки предложений и отзывов.

Содержит универсальные хелперы для FSM-состояний, обрабатывающие:
- загрузку фото (опционально),
- ввод контактных данных (с валидацией или без),
- пропуск шага добавления фото.

Используются в маршрутизаторах предложений и отзывов.
"""

from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import ADMIN_ID, CONTACT_SKIP_VALUES
from utils.validators import is_valid_phone
from logger_config import setup_logger
from keyboards.client_kb import kb_client
logger = setup_logger()


async def handle_photo_step(
    message: Message,
    state: FSMContext,
    next_state
):
    """
    Обрабатывает шаг добавления фото в рамках FSM-сценария.

    Сохраняет file_id самого большого варианта фото, если оно прикреплено.
    Если сообщение не содержит фото — сохраняет None.
    Переходит к следующему FSM-состоянию и запрашивает контактные данные.

    Args:
        message: Входящее сообщение от пользователя.
        state: Контекст FSM для хранения данных.
        next_state: Следующее состояние FSM (обычно — запрос контакта).
    """
    if message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo=photo_id)
        await message.answer(
            'Фото получено! Оставьте контакт для обратной связи:'
        )
    else:
        await state.update_data(photo=None)
        await message.answer(
            'Фото пропущено. Оставьте контакт для обратной связи:'
        )
    await state.set_state(next_state)


async def handle_contact_step(
    message: Message,
    state: FSMContext,
    contact_required: bool = True,
    contact_validator=None,
    save_to_db_func=None,
    entity_name: str = 'обращение'
):
    """
    Обрабатывает финальный шаг ввода контакта и завершает сценарий.

    Валидирует контакт при необходимости,
    сохраняет данные в БД (если требуется),
    отправляет уведомление администратору и подтверждение пользователю.
    Восстанавливает основную клавиатуру и очищает FSM-состояние.

    Args:
        message: Входящее сообщение с контактными данными.
        state: FSM-контекст с ранее собранными данными (текст, фото).
        contact_required: Обязательно ли указывать контакт (для предложений).
        contact_validator: Функция для валидации контакта.
        save_to_db_func: Опциональная функция сохранения в БД (для отзывов).
        entity_name: Сущности ('отзыв', 'предложение') для уведомлений.
    """
    contact = message.text.strip()

    if contact_required and contact_validator:
        if not is_valid_phone(contact):
            await message.answer(
                '❗ Пожалуйста, введите корректный номер телефона'
                '(например, +7 999 123-45-67).'
            )
            return

    if not contact_required and contact.lower() in CONTACT_SKIP_VALUES:
        contact = 'Не указан'
    data = await state.get_data()
    text = data.get('text')
    photo_id = data.get('photo')
    if save_to_db_func:
        try:
            save_to_db_func(
                data=data, contact=contact, user_id=message.from_user.id
            )
        except Exception as e:
            logger.error(f'Ошибка сохранения {entity_name}: {e}')
            await message.answer(
                'Произошла ошибка при сохранении. Попробуйте позже.'
            )
            return
    bot = message.bot
    admin_id = ADMIN_ID

    caption = f'📩 Новое {entity_name}:\n\n{text}\n\nКонтакт: {contact}'
    if photo_id:
        await bot.send_photo(chat_id=admin_id, photo=photo_id, caption=caption)
    else:
        await bot.send_message(
            chat_id=admin_id,
            text=f'📩 Новое {entity_name} (без фото):\n'
            f'\n{text}\n\nКонтакт: {contact}'
        )

    if entity_name == "отзыв":
        await message.answer(
            'Спасибо за ваш отзыв! ❤️', reply_markup=kb_client
        )
    else:
        await message.answer(
            'Спасибо за обратную связь!\n'
            'Мы постараемся решить ваш вопрос в ближайшее время.',
            reply_markup=kb_client
        )
    await state.clear()


async def handle_skip_photo(
    callback: CallbackQuery,
    state: FSMContext,
    next_state
):
    """
    Обрабатывает нажатие кнопки «Пропустить» на шаге добавления фото.

    Сохраняет фото как None, информирует пользователя и переходит
    к следующему состоянию (обычно — запрос контактных данных).

    Args:
        callback: Callback-запрос от нажатия inline-кнопки.
        state: FSM-контекст для обновления данных.
        next_state: Следующее состояние FSM.
    """
    await state.update_data(photo=None)
    await callback.message.answer('Фото пропущено.')
    await callback.message.answer('Оставьте контакт для обратной связи:')
    await state.set_state(next_state)
    await callback.answer()
