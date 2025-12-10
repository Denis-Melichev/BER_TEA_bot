"""
Модуль валидаторов пользовательского ввода.

Содержит функции для проверки корректности:
- числовых значений (положительные числа),
- телефонных номеров (на основе регулярного выражения из конфигурации).
"""

from config import PHONE_PATTERN


def is_positive_number(value: str) -> bool:
    """Проверяет, является ли строка положительным числом."""
    if not value:
        return False
    normalized = value.strip().replace(",", ".")
    try:
        num = float(normalized)
        return num > 0
    except (ValueError, TypeError):
        return False


def is_valid_phone(text: str) -> bool:
    """Проверяет коректностьввода телефона."""
    return bool(PHONE_PATTERN.match(text.strip()))
