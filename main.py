"""
Точка входа Telegram-бота с поддержкой webhook и polling.

Режим запуска определяется переменными окружения:
- Если заданы WEBHOOK_DOMAIN и WEBHOOK_PATH — запускается webhook.
- Иначе — запускается polling (удобно для локальной разработки).

Требуемые переменные окружения:
- TOKEN — обязательный токен бота.
- WEBHOOK_DOMAIN — домен (например, example.com), опционально.
- WEBHOOK_PATH — путь (например, /webhook), опционально.
- WEBHOOK_SECRET — секрет для проверки подлинности запросов (рекомендуется).
- (опционально) SSL_CERT и SSL_PRIV — пути к сертификатам,
 если не используете reverse proxy.

Пример webhook-URL: https://example.com/webhook
"""

import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application
)
from aiohttp import web
from logger_config import setup_logger
from database import init_db
from dotenv import load_dotenv

from handlers.client import router as client_router
from handlers.common import router as common_router
from handlers.admin import router as admin_router
from handlers.client_order_handlers import router as order_router
from handlers.suggestions import router as suggestions_router
from config import ADMIN_ID
load_dotenv()

logger = setup_logger()

TOKEN = os.getenv('TOKEN')
if not TOKEN:
    raise ValueError('Токен не найден! Установите переменную окружения TOKEN.')


WEBHOOK_DOMAIN = os.getenv('WEBHOOK_DOMAIN')
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH') or '/webhook'
if not WEBHOOK_PATH.startswith('/'):
    WEBHOOK_PATH = '/' + WEBHOOK_PATH
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8080))


SSL_CERT = os.getenv('SSL_CERT')
SSL_PRIV = os.getenv('SSL_PRIV')

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(admin_router)
dp.include_router(client_router)
dp.include_router(order_router)
dp.include_router(suggestions_router)
dp.include_router(common_router)


async def on_startup(bot: Bot) -> None:
    """Выполняется при запуске бота (в обоих режимах)."""
    init_db()
    logger.info('База данных инициализирована.')
    if WEBHOOK_DOMAIN:
        webhook_url = f'https://{WEBHOOK_DOMAIN}{WEBHOOK_PATH}'
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
        )
        logger.info(f'Webhook установлен: {webhook_url}')
    else:
        logger.info('Запуск в режиме polling.')


async def on_error(exception: Exception):
    """
    Отправляет уведомление об исключении администратору бота.

    Используется для мониторинга критических ошибок в production.
    Обрезает сообщение об ошибке до 1000 символов, чтобы избежать
    превышения лимита длины сообщения в Telegram.
    """
    await bot.send_message(ADMIN_ID, f"❗ Ошибка: {str(exception)[:1000]}")


async def on_shutdown(bot: Bot) -> None:
    """Выполняется при остановке."""
    if WEBHOOK_DOMAIN:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info('Webhook удалён.')
    await bot.session.close()


async def main():
    """Запуск бота в webhook- или polling-режиме."""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    if WEBHOOK_DOMAIN:
        app = web.Application()
        SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=WEBHOOK_SECRET,
        ).register(app, path=WEBHOOK_PATH)

        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        ssl_context = None
        if SSL_CERT and SSL_PRIV:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(SSL_CERT, SSL_PRIV)

        site = web.TCPSite(
            runner, host='0.0.0.0', port=WEBHOOK_PORT, ssl_context=ssl_context
        )
        logger.info(f'Запуск webhook-сервера на порту {WEBHOOK_PORT}...')
        await site.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info('Получен сигнал завершения (webhook).')
        finally:
            await runner.cleanup()
    else:
        logger.info('Запуск в режиме polling...')
        try:
            await dp.start_polling(bot, skip_updates=True)
        except Exception as e:
            logger.critical(
                f'Критическая ошибка в polling: {e}', exc_info=True
            )
            raise
        finally:
            await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Бот остановлен вручную.')
    except Exception as e:
        logger.critical(f'Необработанное исключение: {e}', exc_info=True)
