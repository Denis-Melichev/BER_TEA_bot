"""Конфигурации проекта,Ссылки,Константы."""
import os
import re
from typing import Union
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONTACT_SKIP_VALUES = ['нет', '-', '.', 'пропустить', '']

BASE_DIR = Path(__file__).parent
CENZ_FILE = BASE_DIR / 'cenz.json'


DATABASE_URL = os.getenv("DATABASE_URL")

WB = 'http://www.wildberries.ru/catalog/609169456/detail.aspx?size=828389701'

PRODUCT_LIST = ['photo_file_id', 'name', 'weight', 'description', 'price']

CDEK_BASE_URL = 'https://api.cdek.ru/v2'.strip()

ADMIN_ID = os.getenv("ADMIN_ID")
if not ADMIN_ID:
    raise ValueError("Переменная окружения ADMIN_ID не установлена.")
try:
    int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID должен быть числовым ID Telegram-пользователя")


def is_admin(user_id: Union[int, str]) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return str(user_id) == ADMIN_ID


PHONE_PATTERN = re.compile(
    r'^(\+?7|8)?[\s\-]?\(?[0-9]{3}\)?[\s\-]?'
    r'[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
)
