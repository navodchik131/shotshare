import asyncio
import logging
from telegram import Update
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import SessionLocal, init_db
from database.models import User, Task, Session, Post, PostStatus, PostType, Complaint, PostView
from datetime import datetime, timedelta
import config
from bot.handlers import (
    start_handler,
    register_handler,
    set_channel_handler,
    help_handler,
    about_handler,
    rules_handler,
    handle_media,
    handle_onboarding_callback,
    handle_trial_media,
    handle_task_accept,
    handle_resubmit,
    handle_complaint,
    handle_like,
    handle_subscribe,
    handle_view_post,
    handle_text_message,
    handle_skip_channel,
    handle_activity_response,
    handle_confirm_channel,
    handle_remove_channel,
    handle_cancel_channel,
    handle_channel_link_detection
)
from bot.scheduler import setup_schedulers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок бота"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    # Обработка сетевых ошибок
    if isinstance(context.error, NetworkError):
        logger.warning(f"NetworkError: {context.error}. Бот продолжит работу.")
        return
    
    # Обработка ошибок rate limit
    if isinstance(context.error, RetryAfter):
        logger.warning(f"Rate limit: нужно подождать {context.error.retry_after} секунд")
        return
    
    # Обработка таймаутов
    if isinstance(context.error, TimedOut):
        logger.warning(f"Timeout error: {context.error}. Бот продолжит работу.")
        return
    
    # Для других ошибок пытаемся уведомить пользователя, если это возможно
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Произошла ошибка. Попробуй еще раз или обратись к администратору."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def setup_bot_commands(application: Application):
    """Настройка меню команд бота"""
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Главное меню и информация о боте"),
        BotCommand("register", "Регистрация в системе"),
        BotCommand("setchannel", "Добавить или изменить канал"),
        BotCommand("about", "Что это и как работает"),
        BotCommand("rules", "Правила и ограничения"),
        BotCommand("help", "Помощь и список команд"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Меню команд настроено")


def main():
    # Инициализация БД
    init_db()
    
    # Создание приложения с JobQueue
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).job_queue().build()
    
    # Настройка меню команд (выполнится после инициализации бота)
    application.post_init = setup_bot_commands
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("register", register_handler))
    application.add_handler(CommandHandler("setchannel", set_channel_handler))
    application.add_handler(CommandHandler("channel", set_channel_handler))
    application.add_handler(CommandHandler("about", about_handler))
    application.add_handler(CommandHandler("rules", rules_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern="^onboarding:"))
    application.add_handler(CallbackQueryHandler(handle_task_accept, pattern="^accept_task:"))
    application.add_handler(CallbackQueryHandler(handle_resubmit, pattern="^resubmit:"))
    application.add_handler(CallbackQueryHandler(handle_skip_channel, pattern="^skip_channel"))
    application.add_handler(CallbackQueryHandler(handle_confirm_channel, pattern="^confirm_channel:"))
    application.add_handler(CallbackQueryHandler(handle_remove_channel, pattern="^remove_channel"))
    application.add_handler(CallbackQueryHandler(handle_cancel_channel, pattern="^cancel_channel"))
    application.add_handler(CallbackQueryHandler(handle_activity_response, pattern="^activity_"))
    application.add_handler(CallbackQueryHandler(handle_complaint, pattern="^complaint:"))
    application.add_handler(CallbackQueryHandler(handle_like, pattern="^like:"))
    application.add_handler(CallbackQueryHandler(handle_subscribe, pattern="^subscribe:"))
    application.add_handler(CallbackQueryHandler(handle_view_post, pattern="^view_post:"))
    
    # Обработка медиа (фото/видео) - должен быть перед текстовыми сообщениями
    application.add_handler(MessageHandler(filters.PHOTO, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media))
    
    # Обработка текстовых сообщений (для регистрации)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Регистрация обработчика ошибок (должен быть после всех обработчиков)
    application.add_error_handler(error_handler)
    
    # Настройка планировщиков
    setup_schedulers(application)
    
    # Проверяем, что планировщик настроен
    if application.job_queue:
        jobs = application.job_queue.jobs()
        logger.info(f"Планировщик задач настроен. Количество задач: {len(jobs)}")
        for job in jobs:
            try:
                next_run = getattr(job.job, 'next_run_time', None) if hasattr(job, 'job') else None
                if next_run:
                    logger.info(f"  - {job.name}: следующий запуск в {next_run}")
                else:
                    logger.info(f"  - {job.name}: запланировано")
            except Exception as e:
                logger.info(f"  - {job.name}: запланировано")
    else:
        logger.error("Планировщик задач НЕ настроен!")
    
    # Запуск бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

