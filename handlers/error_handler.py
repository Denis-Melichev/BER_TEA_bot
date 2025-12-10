from aiogram import Router
from aiogram.types import ErrorEvent
from logger_config import setup_logger

logger = setup_logger()
router = Router()


@router.errors()
async def error_handler(event: ErrorEvent):
    logger.exception(
        "Обработка обновления вызвала исключение: %s",
        event.exception,
        exc_info=event.exception
    )
    update = event.update
    if update.message:
        await update.message.answer(
            '❌ Произошла внутренняя ошибка. Попробуйте позже.'
        )
    elif update.callback_query:
        await update.callback_query.answer('❌ Ошибка!', show_alert=True)
