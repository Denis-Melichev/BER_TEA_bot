"""
Остальные хендлеры бота.

- Проверка не цензурных выражений.
- Отвечает на нажатие кнопки Ассортимент.
- Отвечает на нажатие кнопки Ссылка на магазин.
- Отвечает на нажатие кнопки Что умеет бот.
- Эхохендлер отвечает на нажатие кнопки Что умеет бот,
отвечает на привет,проверяет сообщение пользователя.
"""
import json
import string
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from keyboards.client_kb import kb_inline, get_product_review_button
from database import load_products
from logger_config import setup_logger
from config import WB, CENZ_FILE

router = Router()
logger = setup_logger()


def get_censored_words():
    """Возвращает множество запрещённых слов, загружая их один раз."""
    if not hasattr(get_censored_words, '_cache'):
        try:
            with open(CENZ_FILE, 'r', encoding='utf-8') as f:
                words = json.load(f)
                get_censored_words._cache = set(
                    word.strip().lower() for word in words
                )
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f'Не удалось загрузить cenz.json: {e}')
            get_censored_words._cache = set()
    return get_censored_words._cache


def contains_censorship(text: str) -> bool:
    """
    Проверяет, содержит ли текст запрещённые (нецензурные) слова.

    Текст нормализуется:
    приводится к нижнему регистру и удаляются знаки препинания.
    Сравнивается с заранее загруженным множеством запрещённых слов.
    """
    censored = get_censored_words()
    if not censored:
        return False
    words = set()
    for word in text.split():
        clean = word.lower().translate(
            str.maketrans('', '', string.punctuation)
        )
        if clean:
            words.add(clean)
    return bool(words & censored)


@router.message(F.text == '🍵 Ассортимент')
async def show_assortment(message: Message):
    """
    Отображает текущий ассортимент товаров.

    Загружает список товаров из базы данных и отправляет
    каждому пользователю карточки с фото, названием, размером и ценой.
    Если ассортимент пуст — уведомляет об этом.
    """
    products = load_products()
    if not products:
        await message.answer('Ассортимент пуст.')
        return

    for product in products:
        review_kb = get_product_review_button(product['id'])
        await message.answer_photo(
            photo=product['photo'],
            caption=(
                f"Название: {product['name']}\n"
                f"Вес: {product['weight']} г\n"
                f"Описание: {product['description']}\n"
                f"Цена: {product['price']} ₽"
            ),
            reply_markup=review_kb
        )


@router.message(F.text == '🛒 Ссылка на магазин')
async def shop_link(message: Message):
    """
    Обрабатывает запрос на получение ссылок на магазины.

    Отправляет пользователю inline-кнопку: Wildberries.
    """
    await message.answer(
        'А через бот заказать выгоднее', reply_markup=kb_inline
    )


@router.message()
async def echo_handler(message: Message):
    """
    Универсальный обработчик текстовых сообщений.

    Выполняет следующие действия:
    - Игнорирует сообщения без текста (например, стикеры, голосовые).
    - Проверяет текст на наличие запрещённых слов и
    удаляет сообщение при обнаружении.
    - Обрабатывает команды вроде «привет» и «ℹ️ Что умеет бот».
    - Удаляет служебные сообщения (например, запросы о функционале бота).
    """
    if message.text is None:
        return

    if contains_censorship(message.text):
        await message.reply('Маты запрещены')
        try:
            await message.delete()
        except TelegramAPIError as e:
            logger.warning(
                f'Не удалось удалить сообщение {message.message_id}: {e}'
            )
        return

    text = message.text.strip()
    if text.lower() == 'привет':
        name = message.from_user.first_name
        await message.answer(
            f'И тебе привет, {name}!\n'
            'У меня есть ссылка на отличный магазин чая:\n'
            f'На WB — {WB}'
        )
    elif text == 'ℹ️ Что умеет бот':
        await message.answer(
            'Я могу показать товары)\n'
            'Подсказать где можно их приобрести\n'
            'Могу сам оформить заказ\n'
            'Могу научить заваривать, разные сорта чая\n'
            'Помочь оставить отзыв\n'
            'И еще многое другое, пиши — я отвечу'
        )
    else:
        await message.answer(
            'Извините, я не понимаю эту команду. Нажмите на кнопки в меню.'
            )
