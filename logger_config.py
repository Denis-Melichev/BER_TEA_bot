"""
Модуль настройки логирования для Telegram-бота.

Предоставляет централизованный, потокобезопасный логгер с выводом
в консоль (stdout) и в файл 'bot.log' в кодировке UTF-8.
Используется для отслеживания работы бота, ошибок, взаимодействий
с пользователями и интеграций со сторонними сервисами.

Основные особенности:
- Единый экземпляр логгера с именем 'ber_tea_bot'.
- Формат сообщений: дата, имя логгера, уровень, текст.
- Дублирование логов в консоль и файл.
- Отключено распространение логов выше по иерархии (propagate=False),
  чтобы избежать дублирования при импорте в другие модули.

Пример использования:
    from .logger import setup_logger
    logger = setup_logger()
    logger.info("Бот запущен")
"""

import logging
import sys


def setup_logger() -> logging.Logger:
    """Настраивает и возвращает единый логгер для всего приложения."""
    logger = logging.getLogger('ber_tea_bot')

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
