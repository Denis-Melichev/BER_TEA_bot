"""
Модуль работы с базой данных PostgreSQL.

Реализует:
- хранение товаров, отзывов и активных пользователей в PostgreSQL,
- пагинацию, удаление, выборку отзывов.

Использует:
- таблицу 'products' для товаров,
- таблицу 'reviews' для отзывов,
- таблицу 'users' для активных пользователей.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from utils.utils import extract_price
from config import DATABASE_URL


def get_db_connection():
    """Создаёт подключение к PostgreSQL с использованием RealDictCursor."""
    if not DATABASE_URL:
        raise ValueError("Переменная окружения DATABASE_URL не задана")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Инициализирует таблицы в базе данных, если они ещё не созданы."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                weight TEXT,
                description TEXT,
                price TEXT,
                photo_file_id TEXT
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                contact TEXT,
                photo_file_id TEXT,
                user_id BIGINT,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                price_per_unit TEXT,
                total_price TEXT,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
    finally:
        cur.close()
        conn.close()


def load_products():
    """Загружает все товары из таблицы 'products', сортируя по имени."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM products ORDER BY name")
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def save_product(product_data):
    """
    Добавляет новый товар или обновляет существующий.

    Args:
        product_data (dict): Словарь с полями товара.
            Должен содержать: 'name', 'weight', 'description', 'price'.
            Если есть 'id' — обновляет, иначе создаёт новый.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if product_data.get('id'):
            cur.execute('''
                UPDATE products
                SET name=%s, weight=%s, description=%s,
                price=%s, photo_file_id=%s
                WHERE id=%s
            ''', (
                product_data['name'],
                product_data['weight'],
                product_data['description'],
                product_data['price'],
                product_data.get('photo_file_id'),
                product_data['id']
            ))
        else:
            cur.execute('''
                INSERT INTO products
                (name, weight, description, price, photo_file_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (
                product_data['name'],
                product_data['weight'],
                product_data['description'],
                product_data['price'],
                product_data.get('photo_file_id')
            ))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def delete_product(product_id):
    """
    Удаляет товар по ID. Отзывы удалятся автоматически (ON DELETE CASCADE).

    Args:
        product_id (int): ID удаляемого товара.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def add_review(
        text, contact=None, user_id=None, photo_file_id=None, product_id=None
):
    """Добавляет новый отзыв в таблицу 'reviews'."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO reviews "
            "(text, contact, user_id, photo_file_id, product_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (text, contact, user_id, photo_file_id, product_id)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_reviews_for_client(limit: int = 5):
    """Получает отзывы для клиента."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, text, contact, photo_file_id, user_id
            FROM reviews
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def get_user_reviews(user_id: int, limit: int = 10):
    """Возвращает отзывы конкретного пользователя (для редактирования)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, text, contact, photo_file_id, user_id, product_id
            FROM reviews
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def get_reviews_for_product_paginated(product_id, page=1, per_page=3):
    """Получает отзывы для конкретного товара с пагинацией."""
    offset = (page - 1) * per_page
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, text, contact, photo_file_id
            FROM reviews
            WHERE product_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (product_id, per_page, offset))
        reviews = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) FROM reviews WHERE product_id = %s", (product_id,)
        )
        total = cur.fetchone()['count']

        return [
            (r['id'],
             r['text'],
             r['contact'],
             r['photo_file_id']) for r in reviews
        ], total
    finally:
        cur.close()
        conn.close()


def add_user(user_id):
    """
    Добавляет пользователя в таблицу 'users', если его ещё нет.

    Args:
        user_id (int): ID пользователя Telegram.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (user_id,)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_reviews_for_admin(limit: int = 100):
    """Получает отзывы для админ-панели"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, text, contact, photo_file_id, user_id, product_id
            FROM reviews
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def delete_review_by_id(review_id: int) -> bool:
    """
    Удаляет отзыв по ID. Возвращает True, если удалён.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        cur.close()
        conn.close()


def delete_reviews_by_product_id(product_id: int):
    """
    Удаляет все отзывы, привязанные к товару.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM reviews WHERE product_id = %s", (product_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_statistics():
    """
    Считает статистику, извлекая цену из текстовых значений.
    Работает даже если total_price = "1 500 ₽".
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        active_users = cur.fetchone()['count']

        cur.execute("""
            SELECT product_name, SUM(quantity) AS total_qty
            FROM orders
            GROUP BY product_name
            ORDER BY total_qty DESC
        """)
        sold_products = [
            (row['product_name'], row['total_qty']) for row in cur.fetchall()
        ]

        cur.execute("SELECT total_price FROM orders")
        rows = cur.fetchall()
        total_revenue = 0
        for row in rows:
            price = extract_price(row['total_price'])
            if price is not None:
                total_revenue += price

        return {
            'active_users': active_users,
            'sold_products': sold_products,
            'total_revenue': total_revenue
        }
    finally:
        cur.close()
        conn.close()


def get_review_by_id(review_id: int):
    """Возвращает один отзыв по ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM reviews WHERE id = %s", (review_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        conn.close()


def update_review(
    review_id: int,
    text: str,
    contact: str = None
):
    """
    Обновляет отзыв: текст, контакт, фото.
    Поля user_id и product_id НЕ изменяются.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE reviews
            SET text = %s, contact = %s
            WHERE id = %s
        """, (text, contact, review_id))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        cur.close()
        conn.close()


def get_all_active_user_ids():
    """Возвращает список всех user_id из таблицы users."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users")
        return [row['user_id'] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
