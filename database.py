"""
Модуль работы с базой данных и файлами товаров.

Реализует:
- хранение отзывов в SQLite,
- хранение списка активных пользователей,
- загрузку/сохранение товаров в JSON-файл,
- пагинацию, удаление, выборку отзывов.

Использует:
- файл 'products.json' для товаров,
- базу 'reviews.db' для отзывов и пользователей.
"""

import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'reviews.db'
PRODUCTS_FILE = BASE_DIR / 'products.json'


def load_products():
    """
    Загружает список товаров из JSON-файла.

    Если файл существует и содержит валидный JSON — возвращает список товаров.
    В случае отсутствия файла или ошибки парсинга — возвращает пустой список.
    """
    products = []
    if PRODUCTS_FILE.exists():
        try:
            with open(PRODUCTS_FILE, 'r', encoding="utf-8") as f:
                products = json.load(f)
        except Exception:
            pass

    need_save = False
    next_id = 1
    for prod in products:
        if 'id' not in prod:
            prod['id'] = next_id
            need_save = True
        else:
            next_id = max(next_id, prod['id'] + 1)

    if need_save:
        save_products(products)

    return products


def save_products(products):
    """
    Сохраняет список товаров в JSON-файл.

    Перезаписывает файл 'products.json'
    """
    with open(PRODUCTS_FILE, 'w', encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=4)


def init_db():
    """
    Инициализирует SQLite-базу данных.

    Создаёт таблицы:
    - 'reviews' — для хранения отзывов,
    - 'users' — для хранения ID всех пользователей, запустивших бота.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                contact TEXT,
                photo_file_id TEXT,
                user_id INTEGER,
                product_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        conn.commit()


def add_user_if_not_exists(user_id: int):
    """
    Добавляет пользователя в таблицу 'users', если он ещё не записан.

    Используется для формирования списка получателей уведомлений.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR IGNORE INTO users (user_id) VALUES (?)',
            (user_id,)
        )


def get_all_active_user_ids() -> list[int]:
    """
    Возвращает список всех user_id, кто когда-либо запускал бота.

    Используется для массовой рассылки уведомлений о новых товарах.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT user_id FROM users")
        return [row[0] for row in cur.fetchall()]


def add_review(
    text: str,
    contact: str = None,
    photo_file_id: str = None,
    user_id: int = None,
    product_id: int = None
):
    """
    Добавляет новый отзыв в базу данных.

    Args:
        text: Текст отзыва (обязательный).
        contact: Контактная информация (опционально).
        photo_file_id: ID фото в Telegram (опционально).
        user_id: ID пользователя в Telegram.
        product_id: ID товара, к которому привязан отзыв.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO reviews (text, contact, photo_file_id, '
        'user_id, product_id) VALUES (?, ?, ?, ?, ?)',
        (text, contact, photo_file_id, user_id, product_id)
    )
    conn.commit()
    conn.close()


def get_reviews(limit: int = 100):
    """
    Получает отзывы из базы данных.

    Возвращает список словарей с ключами:
    id, text, contact, photo_file_id, user_id, timestamp.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, text, contact, photo_file_id, user_id, timestamp '
        'FROM reviews ORDER BY timestamp DESC LIMIT ?',
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_reviews_for_client(product_id: int, limit: int = 5):
    """
    Получает отзывы по конкретному товару для обычного пользователя.

    Args:
        product_id: ID товара.
        limit: Максимальное число отзывов.

    Returns:
        Список кортежей: (text, contact, photo_file_id).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT text, contact, photo_file_id FROM reviews WHERE product_id = ?'
        'ORDER BY timestamp DESC LIMIT ?',
        (product_id, limit)
    )
    return cursor.fetchall()


def get_reviews_for_admin(limit: int = 100):
    """
    Получает отзывы для панели администратора.

    Returns:
        Список словарей с полями отзыва (без timestamp для удобства).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, text, contact, photo_file_id,'
        'user_id FROM reviews ORDER BY timestamp DESC LIMIT ?',
        (limit,)
    )
    return [dict(row) for row in cursor.fetchall()]


def delete_review_by_id(review_id: int) -> bool:
    """
    Удаляет отзыв по ID.

    Возвращает True, если отзыв был найден и удалён, иначе False.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count > 0


def delete_reviews_by_product_id(product_id: int):
    """Удаляет все отзывы, привязанные к товару."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM reviews WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()


def get_reviews_for_product_paginated(
        product_id: int, page: int = 1, per_page: int = 3
):
    """
    Возвращает отзывы для товара с пагинацией.

    Возвращает: (список_отзывов, общее_число_отзывов)
    """
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        'SELECT COUNT(*) FROM reviews WHERE product_id = ?', (product_id,)
    )
    total = cursor.fetchone()[0]
    cursor.execute(
        '''
        SELECT text, contact, photo_file_id
        FROM reviews
        WHERE product_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        ''',
        (product_id, per_page, offset)
    )
    reviews = cursor.fetchall()
    conn.close()

    return reviews, total
