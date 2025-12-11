"""
Хендлеры для оформления заказа клиентом.

Содержит обработчики FSM-машины для:
- выбора товара,
- указания количества,
- выбора города и ПВЗ СДЭК,
- ввода контактов и подтверждения заказа.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_ID
from states.client_states import FSMOrder
from aiogram.filters import StateFilter
from database import load_products, save_order
from keyboards.client_kb import (
    kb_client,
    get_product_selection_kb,
    get_pvz_pagination_kb,
    get_order_confirmation_kb
)
from utils.cdek_api import CDEKClient
from utils.validators import is_positive_number, is_valid_phone
from logger_config import setup_logger

router = Router()
cdek = CDEKClient()
logger = setup_logger()


@router.message(F.text == '🛒 Оформить заказ')
async def start_order(message: Message, state: FSMContext):
    """
    Начало оформления заказа.

    Показывает список доступных товаров.
    """
    products = load_products()
    if not products:
        await message.answer('Нет доступных товаров.')
        return
    await state.set_state(FSMOrder.select_product)
    await message.answer(
        'Выберите товар:',
        reply_markup=get_product_selection_kb(products)
    )


@router.callback_query(
        FSMOrder.select_product, F.data.startswith('order_prod_')
    )
async def select_product(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор товара пользователем.

    Извлекает ID товара из callback_data, сохраняет его в состояние FSM
    и переходит к запросу количества.

    Args:
        callback: Callback-запрос от нажатия кнопки.
        state: Контекст конечного автомата.
    """
    product_id = int(callback.data.split('_')[-1])
    await state.update_data(product_id=product_id)
    await state.set_state(FSMOrder.select_quantity)
    await callback.message.edit_text('Укажите количество штук:')
    await callback.answer()


@router.message(FSMOrder.select_quantity)
async def select_quantity(message: Message, state: FSMContext):
    """
    Обрабатывает ввод количества товара.

    Проверяет, что введено положительное число с помощью валидатора.
    При успехе сохраняет количество и переходит к запросу города доставки.

    Args:
        message: Входящее сообщение с количеством.
        state: Контекст конечного автомата.
    """
    text = message.text.strip()

    if not is_positive_number(text) or not text.replace('.', '').isdigit():
        await message.answer('❌ Укажите целое количество (например: 1, 2, 3):')
        return

    qty = int(text)
    await state.update_data(quantity=qty)
    await state.set_state(FSMOrder.enter_city)
    await message.answer('🏙️ Введите город доставки (например: Москва):')


@router.message(FSMOrder.enter_city)
async def enter_city(message: Message, state: FSMContext):
    """
    Обрабатывает ввод города доставки.

    Использует API СДЭК для поиска кода города и получения списка ПВЗ.
    При успехе сохраняет список ПВЗ и переходит к выбору пункта выдачи.

    Args:
        message: Входящее сообщение с названием города.
        state: Контекст конечного автомата.
    """
    city_name = message.text.strip()
    if not city_name:
        await message.answer('Пожалуйста, введите название города.')
        return
    await message.answer('🔍 Ищу город...')
    try:
        city_code = await cdek.get_city_code_by_name(city_name)
        if city_code is None:
            await message.answer(
                f'Город «{city_name}» не найден.\n'
                'Попробуйте указать полное название'
                '(например: Санкт-Петербург).'
            )
            return
        await message.answer('📦 Ищу пункты выдачи...')
        pvz_list = await cdek.get_pvz_by_city_code(city_code)
        if not pvz_list:
            await message.answer(f'В городе «{city_name}» нет ПВЗ СДЭК.')
            return
        await state.update_data(pvz_list=pvz_list, city=city_name)
        await state.set_state(FSMOrder.select_pvz)
        await message.answer(
            f'Найдено {len(pvz_list)} ПВЗ. Выберите:',
            reply_markup=get_pvz_pagination_kb(
                pvz_list, city_name=city_name, page=0
            )
        )

    except Exception as e:
        logger.error(f'Ошибка СДЭК: {e}', exc_info=True)
        await message.answer(
            'Произошла ошибка при поиске ПВЗ. Попробуйте позже.'
        )


@router.callback_query(FSMOrder.select_pvz, F.data.startswith('pvz_page_'))
async def paginate_pvz_list(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает навигацию по страницам списка ПВЗ.

    Обновляет клавиатуру с новой страницей пунктов выдачи.

    Args:
        callback: Callback-запрос от кнопки пагинации.
        state: Контекст конечного автомата.
    """
    page = int(callback.data.split('_')[-1])

    data = await state.get_data()
    pvz_list = data['pvz_list']
    city_name = data['city']

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_pvz_pagination_kb(
                pvz_list, city_name=city_name, page=page
            )
        )
    except TelegramBadRequest:
        pass

    await callback.answer()


@router.callback_query(FSMOrder.select_pvz, F.data.startswith('pvz_'))
async def select_pvz_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор конкретного пункта выдачи.

    Находит ПВЗ по коду, формирует полный адрес с комментарием
    и переходит к запросу контактных данных.

    Args:
        callback: Callback-запрос от кнопки ПВЗ.
        state: Контекст конечного автомата.
    """
    pvz_code = callback.data.split('pvz_', 1)[1]
    data = await state.get_data()
    pvz_list = data['pvz_list']
    selected_pvz = next(
        (p for p in pvz_list if str(p['code']) == pvz_code), None
    )
    if not selected_pvz:
        await callback.answer('Пункт выдачи не найден.', show_alert=True)
        return
    addr = (selected_pvz.get('address') or "").strip()
    comment = (selected_pvz.get('address_comment') or "").strip()

    if addr and comment:
        full_address = f'{addr}\nℹ️ {comment}'
    elif comment:
        full_address = f'📍 {comment}'
    elif addr:
        full_address = addr
    else:
        full_address = 'Адрес не указан'
    await state.update_data(selected_pvz=selected_pvz)
    await state.set_state(FSMOrder.request_contact)
    await callback.message.edit_text(
        f"✅ Выбран пункт выдачи:\n\n"
        f"**{selected_pvz.get('name', 'ПВЗ СДЭК')}**\n"
        f"{full_address}",
        parse_mode='HTML'
    )
    await callback.message.answer('📞 Пожалуйста, введите ваш номер телефона:')

    await callback.answer()


@router.message(FSMOrder.request_contact)
async def process_contact_text(message: Message, state: FSMContext):
    """
    Обрабатывает ввод контактного номера телефона.

    Проверяет корректность номера по регулярному выражению.
    При успехе формирует сводку заказа для подтверждения.

    Args:
        message: Входящее сообщение с номером телефона.
        state: Контекст конечного автомата.
    """
    text = message.text.strip()
    if text.lower() in ('отмена', 'назад', '❌ отменить'):
        await state.clear()
        await message.answer(
            'Оформление заказа отменено.', reply_markup=kb_client
        )
        return
    if not is_valid_phone(text):
        await message.answer(
            '❗ Пожалуйста, введите корректный номер телефона'
            '(например, +7 999 123-45-67).'
        )
        return
    await state.update_data(phone=text)
    await state.set_state(FSMOrder.confirm)
    data = await state.get_data()
    if 'product_id' not in data:
        await message.answer(
            '❌ Сессия устарела. Начните заказ заново.', reply_markup=kb_client
        )
        await state.clear()
        return
    products = load_products()
    product = next(p for p in products if p['id'] == data['product_id'])
    pvz = data['selected_pvz']
    address_display = pvz.get('address') or pvz.get(
        'address_comment', 'Адрес не указан'
    )
    summary = (
        f"📦 <b>Подтверждение заказа</b>\n\n"
        f"Товар: {product['name']}\n"
        f"Количество: {data['quantity']} шт\n"
        f"Город: {data['city']}\n"
        f"Пункт выдачи: {pvz['name']}\n"
        f"Адрес: {address_display}\n"
        f"Контакт: {text}\n\n"
        f"Подтвердить заказ?"
    )
    await message.answer(
        summary,
        reply_markup=get_order_confirmation_kb(),
        parse_mode='HTML'
    )


@router.callback_query(StateFilter(FSMOrder), F.data == 'order_cancel')
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(
            'Оформление заказа отменено.',
            reply_markup=None
        )
    except TelegramBadRequest:
        await callback.message.answer('Оформление заказа отменено.')
    await callback.answer()


@router.callback_query(F.data == 'order_confirm')
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Подтверждает заказ и отправляет уведомление администратору.

    Формирует информацию о заказе и отправляет её в чат администратора.
    Завершает состояние FSM после успешного оформления.

    Args:
        callback: Callback-запрос от кнопки подтверждения.
        state: Контекст конечного автомата.
        bot: Экземпляр бота для отправки сообщения админу.
    """
    data = await state.get_data()
    products = load_products()
    phone = data.get('phone', '—')
    user = callback.from_user
    pvz = data['selected_pvz']
    try:
        product = next(
            p for p in products if str(p['id']) == str(data['product_id'])
            )
    except StopIteration:
        await callback.message.answer(
            '❌ Товар не найден. Начните заказ заново.', reply_markup=kb_client
            )
        await state.clear()
        return
    quantity = data['quantity']
    price_per_unit = float(product['price'])
    total_price = price_per_unit * quantity

    save_order(
        user_id=user.id,
        product_id=product['id'],
        product_name=product['name'],
        quantity=quantity,
        price_per_unit=price_per_unit,
        total_price=total_price
    )
    address_display = pvz.get('address') or pvz.get(
        'address_comment', 'Адрес не указан'
    )
    order_info = (
        f"🆕 <b>Новый заказ</b>\n\n"
        f"👤 Пользователь: @{user.username or '—'} (ID: {user.id})\n"
        f"Имя: {user.first_name}\n"
        f"📞 Телефон: {phone}\n\n"
        f"📦 Товар: {product['name']}\n"
        f"⚖️ Количество: {data['quantity']} шт\n"
        f"🏙️ Город: {data['city']}\n"
        f"📍 ПВЗ: {pvz['name']}\n"
        f"🏠 Адрес: {address_display}"
    )

    await bot.send_message(
        chat_id=ADMIN_ID, text=order_info, parse_mode="HTML"
    )
    await callback.message.edit_text(
        '✅ Заказ оформлен! Администратор скоро свяжется с вами.'
    )
    await state.clear()
    await callback.answer()
