"""
Административный маршрутизатор Telegram-бота.

Обеспечивает полный функционал управления товарами:
— добавление новых товаров (с фото, названием, весом, описанием, ценой),
— редактирование существующих (поля редактируются по одному),
— удаление товаров и связанных с ними отзывов,
— просмотр и удаление отзывов от пользователей.

Также обрабатывает команду /start с разграничением ролей:
администратор получает расширенную панель, клиент — базовую клавиатуру.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from logger_config import setup_logger
from config import is_admin, PRODUCT_LIST
from states.admin_states import FSMAdmin, FSMAdminEdit
from utils.validators import is_positive_number
from database import (
    save_product,
    load_products,
    get_reviews_for_admin,
    delete_review_by_id,
    delete_product,
    add_user,
    get_statistics,
    clear_statistics
)
from keyboards.admin_kb import (
    admin_kb,
    get_edit_product_selection_kb,
    get_edit_field_kb,
    get_confirm_delete_kb,
    get_review_delete_kb,
    get_confirm_delete_product_kb,
    get_confirm_clear_stats_kb
)
from keyboards.client_kb import kb_client
from notifications import send_product_notification

logger = setup_logger()
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обрабатывает команду /start.

    Сохраняет user_id в базу (если ещё не сохранён),
    проверяет роль пользователя и отправляет соответствующее приветствие
    с клавиатурой.
    """
    user_id = message.from_user.id
    add_user(user_id)

    if is_admin(user_id):
        await message.answer(
            'Добро пожаловать в панель администратора!',
            reply_markup=admin_kb
        )
    else:
        await message.answer(
            'Привет! Выберите действие:',
            reply_markup=kb_client
        )


@router.message(
        F.text == "📊 Статистика",
        lambda message: is_admin(message.from_user.id)
)
async def handle_stats(message: Message):
    stats = get_statistics()
    text = "📊 <b>Статистика</b>\n\n"
    text += f"👥 Активных пользователей: <code>{stats['active_users']}</code>\n"
    text += f"💰 Выручка: <code>{stats['total_revenue']:,.2f} ₽</code>\n\n"
    if stats['sold_products']:
        text += "📦 Проданные товары:\n"
        for name, qty in stats['sold_products']:
            text += f"  • {name}: <code>{qty}</code> шт.\n"
    else:
        text += "📦 Продаж пока нет."

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == 'ℹ️ Загрузить')
async def cm_download(message: Message, state: FSMContext):
    """Инициирует процесс добавления нового товара.

    Доступно только администратору.
    Переводит FSM в состояние ожидания фото товара.
    """
    if not is_admin(message.from_user.id):
        await message.reply('Эта команда доступна только администратору.')
        return
    await state.set_state(FSMAdmin.photo)
    await message.reply('Загрузи фото')


@router.message(F.photo, FSMAdmin.photo)
async def load_photo(message: Message, state: FSMContext):
    """Сохраняет file_id фото и переходит к вводу названия товара."""
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(FSMAdmin.name)
    await message.reply('Теперь введите название товара')


@router.message(FSMAdmin.name)
async def load_name(message: Message, state: FSMContext):
    """Сохраняет название товара и переходит к вводу веса."""
    await state.update_data(name=message.text.strip())
    await state.set_state(FSMAdmin.weight)
    await message.reply('Введите вес товара, в граммах.')


@router.message(FSMAdmin.weight)
async def load_weight(message: Message, state: FSMContext):
    """Сохраняет вес товара после валидации.

    Вес должен быть положительным числом. При ошибке отправляет подсказку.
    """
    if not is_positive_number(message.text):
        await message.reply(
            '❌ Вес должен быть положительным числом (например: 500).\n'
            'Пожалуйста, введите корректное значение.'
        )
        return
    await state.update_data(weight=float(message.text))
    await state.set_state(FSMAdmin.description)
    await message.reply('Расскажите о товаре (описание).')


@router.message(FSMAdmin.description)
async def load_description(message: Message, state: FSMContext):
    """Сохраняет описание товара и переходит к вводу цены."""
    await state.update_data(description=message.text.strip())
    await state.set_state(FSMAdmin.price)
    await message.reply('Укажите цену товара (в рублях)')


@router.message(FSMAdmin.price)
async def load_price(message: Message, state: FSMContext, bot: Bot):
    """Сохраняет цену, создаёт новый товар и уведомляет админа.

    Цена округляется до 2 знаков. Товар сохраняется в базу.
    Отправляется подтверждение в чат и уведомление другому админу.
    """
    if not is_positive_number(message.text):
        await message.reply(
            '❌ Цена должна быть положительным числом (например: 299.50).\n'
            'Пожалуйста, введите корректную цену.'
        )
        return
    price = round(float(message.text), 2)
    await state.update_data(price=price)
    data = await state.get_data()

    save_product(data)

    await bot.send_photo(
        chat_id=message.chat.id,
        photo=data['photo_file_id'],
        caption=(
            f"✅ Товар добавлен!\n"
            f"Название: {data['name']}\n"
            f"Вес: {data['weight']} г\n"
            f"Описание: {data['description']}\n"
            f"Цена: {data['price']} ₽"
        ),
    )
    await send_product_notification(bot, data)
    await state.clear()


@router.message(F.text == '🛒 Изменить')
async def edit_product_start(message: Message, state: FSMContext):
    """Запускает процесс редактирования товара.

    Отображает список товаров с inline-кнопками выбора.
    Доступно только администратору.
    """
    if not is_admin(message.from_user.id):
        await message.reply('Доступ только для админа.')
        return

    products = load_products()
    if not products:
        await message.reply('Нет товаров для редактирования.')
        return

    keyboard = get_edit_product_selection_kb(products)
    await message.reply(
        'Выберите товар для редактирования:', reply_markup=keyboard
    )


@router.callback_query(F.data.startswith('edit_product_'))
async def process_edit_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split('_')[-1])
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        await callback.answer('Товар не найден.', show_alert=True)
        return
    await state.update_data(
        product_id=product_id, current_product=dict(product)
    )
    await callback.message.edit_text(
        f"Редактирование: {product['name']}\nВыберите поле:",
        reply_markup=get_edit_field_kb()
    )
    await callback.answer()


field_to_state = {
    'photo_file_id': FSMAdminEdit.editing_photo,
    'name': FSMAdminEdit.editing_name,
    'weight': FSMAdminEdit.editing_weight,
    'description': FSMAdminEdit.editing_description,
    'price': FSMAdminEdit.editing_price,
}

field_prompts = {
    'photo_file_id': 'Отправьте новое фото товара.',
    'name': 'Введите новое название.',
    'weight': 'Введите новый вес в граммах.',
    'description': 'Введите новое описание.',
    'price': 'Введите новую цену в рублях.',
}


@router.callback_query(F.data.startswith('edit_field_'))
async def edit_field_selected(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор поля для редактирования.

    Переводит FSM в соответствующее состояние и запрашивает новое значение.
    """
    field = callback.data.split('_')[-1]
    if field not in field_to_state:
        await callback.answer('Недопустимое поле.', show_alert=True)
        return

    await state.set_state(field_to_state[field])
    await callback.message.answer(field_prompts[field])
    await callback.answer()


@router.message(FSMAdminEdit.editing_photo, F.photo)
async def edit_photo(message: Message, state: FSMContext):
    """Сохраняет новое фото и возвращает меню редактирования."""
    await state.update_data(new_photo_file_id=message.photo[-1].file_id)
    await _return_to_edit_menu(message, state)


@router.message(FSMAdminEdit.editing_photo)
async def edit_photo_invalid(message: Message):
    """Обрабатывает некорректный ввод при ожидании фото."""
    await message.reply('Пожалуйста, отправьте именно фото.')


@router.message(FSMAdminEdit.editing_name)
async def edit_name(message: Message, state: FSMContext):
    """Сохраняет новое название и возвращает меню редактирования."""
    await state.update_data(new_name=message.text.strip())
    await _return_to_edit_menu(message, state)


@router.message(FSMAdminEdit.editing_weight)
async def edit_weight(message: Message, state: FSMContext):
    """Сохраняет новый вес после валидации."""
    if not is_positive_number(message.text):
        await message.reply(
            '❌ Вес должен быть положительным числом. Попробуйте снова.'
        )
        return
    await state.update_data(new_weight=float(message.text))
    await _return_to_edit_menu(message, state)


@router.message(FSMAdminEdit.editing_description)
async def edit_description(message: Message, state: FSMContext):
    """Сохраняет новое описание и возвращает меню редактирования."""
    await state.update_data(new_description=message.text.strip())
    await _return_to_edit_menu(message, state)


@router.message(FSMAdminEdit.editing_price)
async def edit_price(message: Message, state: FSMContext):
    """Сохраняет новую цену после валидации."""
    if not is_positive_number(message.text):
        await message.reply(
            '❌ Цена должна быть положительным числом. Попробуйте снова.'
        )
        return
    await state.update_data(new_price=round(float(message.text), 2))
    await _return_to_edit_menu(message, state)


async def _return_to_edit_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get('product_id')

    if not product_id:
        await message.answer('Сессия устарела.')
        await state.clear()
        return

    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        await message.answer('Товар не найден.')
        await state.clear()
        return
    display = dict(product)
    for field in PRODUCT_LIST:
        new_val = data.get(f'new_{field}')
        if new_val is not None:
            display[field] = new_val

    await message.answer(
        f"Редактирование: {display['name']}"
        '\nТекущие данные обновлены.\nВыберите поле:',
        reply_markup=get_edit_field_kb()
    )


@router.callback_query(F.data == 'edit_done')
async def finish_editing(callback: CallbackQuery, state: FSMContext):
    """
    Завершает редактирование и сохраняет изменения в базу данных (PostgreSQL).

    Обновляются только те поля, которые были изменены администратором.
    """
    try:
        data = await state.get_data()
        product_id = data.get('product_id')
        if not product_id:
            await callback.answer(
                'Сессия устарела. Попробуйте снова.', show_alert=True
            )
            await state.clear()
            return
        products = load_products()
        current_product = None
        for p in products:
            if p['id'] == product_id:
                current_product = dict(p)
                break
        if not current_product:
            await callback.answer('Товар не найден в базе.', show_alert=True)
            await state.clear()
            return
        updated_data = {'id': product_id}
        updated = False

        for field in PRODUCT_LIST:
            new_value = data.get(f'new_{field}')
            if new_value is not None:
                updated_data[field] = new_value
                updated = True
            else:
                updated_data[field] = current_product[field]
        if updated:
            save_product(updated_data)
            await callback.message.answer('✅ Товар успешно обновлён!')
        else:
            await callback.message.answer('ℹ️ Изменений не было внесено.')
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f'ОШИБКА В РЕДАКТИРОВАНИИ: {e}', exc_info=True)
        await callback.answer('❌ Ошибка при сохранении.', show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith('confirm_delete_product_'))
async def confirm_delete_product(callback: CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[-1])
        products = load_products()
        product = next((p for p in products if p['id'] == product_id), None)

        if not product:
            await callback.answer('Товар не найден.', show_alert=True)
            return

        await callback.message.edit_text(
            f'❓ Точно удалить товар «{product["name"]}»?',
            reply_markup=get_confirm_delete_product_kb(product_id)
        )
        await callback.answer()
    except (ValueError, IndexError):
        await callback.answer('Неверный ID товара.', show_alert=True)


@router.callback_query(F.data.startswith('delete_product_'))
async def handle_delete_product(callback: CallbackQuery):
    """Удаляет товар и связанные с ним отзывы из базы данных (PostgreSQL)."""
    try:
        product_id = int(callback.data.split("_")[-1])
        delete_product(product_id)

        await callback.message.edit_text('✅ Товар и его отзывы удалены!')
        await callback.answer()

    except (ValueError, IndexError):
        await callback.answer('Неверный ID товара.', show_alert=True)
    except Exception as e:
        logger.error(f'Ошибка при удалении товара: {e}', exc_info=True)
        await callback.answer('❌ Не удалось удалить товар.', show_alert=True)


@router.callback_query(F.data == 'cancel_delete_product')
async def cancel_delete_product(callback: CallbackQuery):
    """Отменяет удаление и возвращает к списку товаров."""
    products = load_products()
    if not products:
        await callback.message.edit_text('Ассортимент пуст.')
        return

    await callback.message.edit_text(
        'Выберите товар для редактирования:',
        reply_markup=get_edit_product_selection_kb(products)
    )
    await callback.answer()


@router.message(F.text == '⭐ Отзывы')
async def show_reviews(message: Message):
    """Отображает все отзывы админу с кнопками удаления."""
    if not is_admin(message.from_user.id):
        await message.reply('Доступ только для админа.')
        return

    reviews = get_reviews_for_admin()
    if not reviews:
        await message.reply('Нет отзывов.')
        return

    for rev in reviews:
        user_info = f"ID: {rev['user_id']}" if rev['user_id'] else "Аноним"
        contact = f"Контакт: {rev['contact']}" if rev['contact'] else ""
        text = f"🆔 Отзыв #{rev['id']}\n👤 {user_info}\n💬 {rev['text']}"
        if contact:
            text += f"\n📞 {contact}"

        await message.answer(
            text, reply_markup=get_review_delete_kb(rev['id'])
        )


@router.callback_query(F.data.startswith('delete_review_'))
async def delete_review(callback: CallbackQuery):
    """Удаляет отзыв по ID после подтверждения."""
    try:
        review_id = int(callback.data.split("_")[-1])
        success = delete_review_by_id(review_id)
        if success:
            await callback.message.delete()
            await callback.answer('✅ Отзыв удалён.')
        else:
            await callback.answer('❌ Отзыв не найден.', show_alert=True)
    except Exception as e:
        logger.error(f'Ошибка удаления отзыва: {e}', exc_info=True)
        await callback.answer('⚠️ Ошибка при удалении.', show_alert=True)


@router.callback_query(F.data.startswith('confirm_delete_'))
async def confirm_delete_review(callback: CallbackQuery):
    """Запрашивает подтверждение удаления отзыва."""
    review_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        f'❓ Точно удалить отзыв #{review_id}?',
        reply_markup=get_confirm_delete_kb(review_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith('cancel_delete_'))
async def cancel_delete_review(callback: CallbackQuery):
    """Отменяет удаление отзыва и восстанавливает его карточку."""
    review_id = int(callback.data.split("_")[-1])
    reviews = get_reviews_for_admin(limit=1000)
    review = next((r for r in reviews if r['id'] == review_id), None)

    if review:
        user_info = (
            f"ID: {review['user_id']}" if review['user_id'] else "Аноним"
        )
        contact = f"Контакт: {review['contact']}" if review['contact'] else ""
        text = f"🆔 Отзыв #{review['id']}\n👤 {user_info}\n💬 {review['text']}"
        if contact:
            text += f"\n📞 {contact}"

        try:
            await callback.message.edit_text(
                text, reply_markup=get_review_delete_kb(review['id'])
            )
        except TelegramBadRequest as e:
            if 'message is not modified' in str(e):
                pass
            else:
                await callback.message.answer(
                    text, reply_markup=get_review_delete_kb(review['id'])
                )
    else:
        await callback.message.answer('Отзыв не найден.')

    await callback.answer()


@router.message(F.text == "🗑️ Сбросить статистику")
async def ask_clear_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "⚠️ Это удалит ВСЕ данные о продажах. Продолжить?",
        reply_markup=get_confirm_clear_stats_kb()
    )


@router.callback_query(F.data == "clear_stats_confirm")
async def do_clear_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    clear_statistics()
    await callback.message.edit_text("✅ Статистика успешно обнулена.")
    await callback.answer()


@router.callback_query(F.data == "clear_stats_cancel")
async def cancel_clear_stats(callback: CallbackQuery):
    await callback.message.edit_text("❌ Сброс отменён.")
    await callback.answer()
