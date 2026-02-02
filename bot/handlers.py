import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import SessionLocal
from database.models import (
    User, Task, Session, Post, PostStatus, PostType, Complaint, PostView,
    Sanction, SanctionType
)
from datetime import datetime, timedelta
import config
import re

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - многоэтапный онбординг"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        
        # Проверяем, зарегистрирован ли пользователь
        user = db.query(User).filter(User.telegram_id == user_id).first()
        
        if user:
            # Пользователь уже зарегистрирован
            channel_info = ""
            if user.channel_link:
                channel_info = f"\n📢 Твой канал: {user.channel_link}"
            else:
                channel_info = "\n💡 У тебя нет канала. Добавь его командой /setchannel"
            
            await update.message.reply_text(
                f"Привет, {user.name}! 👋\n\n"
                "Ты уже зарегистрирован. Используй команды бота для работы.\n\n"
                "Доступные команды:\n"
                "/setchannel - добавить/изменить канал\n"
                "/register - перерегистрация\n"
                "/start - это сообщение"
                + channel_info
            )
        else:
            # Новый пользователь - начинаем онбординг с экрана 0
            await show_onboarding_screen_0(update, context)
    finally:
        db.close()


async def show_onboarding_screen_0(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран 0 - До старта"""
    keyboard = [
        [InlineKeyboardButton("🚀 Начать", callback_data="onboarding:screen1")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "📸 <b>Все получают одно задание</b>\n"
        "Покажи свой момент — смотри чужие\n\n"
        "<i>Не блог. Не конкурс.\n"
        "Фото и видео из реальной жизни по заданиям.</i>"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_onboarding_screen_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран 1 - Суть за 7 секунд"""
    keyboard = [
        [InlineKeyboardButton("Понятно, дальше →", callback_data="onboarding:screen2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⏰ <b>1–3 раза в день</b>\n"
        "всем приходит одно неожиданное задание\n\n"
        "<i>Примеры заданий:</i>\n"
        "«Покажи, где ты прямо сейчас»\n"
        "«Самый яркий момент за неделю»\n"
        "«Что тебя вдохновляет»\n\n"
        "📸 Задания могут быть разными — "
        "от \"здесь и сейчас\" до \"лучший момент за месяц\""
    )
    
    await update.callback_query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_onboarding_screen_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран 2 - Зачем мне это?"""
    keyboard = [
        [InlineKeyboardButton("Хочу попробовать →", callback_data="onboarding:screen3")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🔍 Смотреть, как живут другие\n"
        "🎯 Ловить живые моменты\n"
        "🌱 Развивать личный блог — если хочешь\n\n"
        "<i>Канал необязателен. Можно просто участвовать.</i>"
    )
    
    await update.callback_query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_onboarding_screen_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран 3 - Не жди, попробуй сейчас"""
    keyboard = [
        [InlineKeyboardButton("📸 Отправить фото", callback_data="onboarding:trial_photo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🎯 <b>Пробное задание</b>\n"
        "Покажи что-то, что соответствует заданию\n\n"
        "<i>Это не публикуется в общей сессии\n"
        "Просто чтобы понять формат</i>"
    )
    
    await update.callback_query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Устанавливаем флаг ожидания пробного фото
    context.user_data['waiting_trial_photo'] = True


async def handle_trial_photo_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса на пробное фото"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "📸 <b>Отправь фото</b>\n\n"
        "Покажи что-то, что соответствует заданию.\n\n"
        "<i>Это пробное задание — оно не будет опубликовано в общей сессии.</i>"
    )
    
    await query.edit_message_text(
        text,
        parse_mode='HTML'
    )
    
    # Устанавливаем флаг ожидания пробного фото
    context.user_data['waiting_trial_photo'] = True


async def handle_trial_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пробного фото/видео (не сохраняется в БД)"""
    if not context.user_data.get('waiting_trial_photo'):
        return  # Не пробное фото, обрабатываем как обычное
    
    # Проверяем формат
    if update.message.video:
        video = update.message.video
        if video.duration and video.duration > 10:
            await update.message.reply_text(
                "❌ Видео должно быть не длиннее 10 секунд.\n\n"
                "Попробуй еще раз с более коротким видео."
            )
            return
        media_type = 'video'
    elif update.message.photo:
        media_type = 'photo'
    else:
        await update.message.reply_text(
            "Отправь фото или видео (до 10 секунд)."
        )
        return
    
    # Убираем флаг ожидания
    context.user_data.pop('waiting_trial_photo', None)
    
    # Отправляем подтверждение
    await update.message.reply_text(
        "✅ <b>Фото принято</b>\n\n"
        "Так выглядят задания в ShotShare",
        parse_mode='HTML'
    )
    
    # Показываем примеры постов из прошлых сессий
    await show_example_posts(update, context)
    
    # После показа примеров предлагаем зарегистрироваться
    keyboard = [
        [InlineKeyboardButton("🚀 Зарегистрироваться", callback_data="onboarding:register")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⏳ <b>Ожидай следующего задания</b>\n\n"
        "Теперь ты понимаешь формат. Готов начать?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_example_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ примеров постов из прошлых сессий"""
    db = SessionLocal()
    try:
        # Получаем 5-10 постов из завершенных сессий
        example_posts = db.query(Post).join(Session).filter(
            Post.status == PostStatus.APPROVED,
            Session.distribution_completed == True
        ).order_by(Post.created_at.desc()).limit(10).all()
        
        if not example_posts:
            # Если нет примеров, просто сообщаем
            await update.message.reply_text(
                "📸 Примеры постов появятся после первых сессий!"
            )
            return
        
        # Группируем по заданиям
        posts_by_task = {}
        for post in example_posts:
            task_id = post.task_id
            if task_id not in posts_by_task:
                posts_by_task[task_id] = []
            posts_by_task[task_id].append(post)
        
        # Показываем по 1-2 поста из каждого задания
        shown_count = 0
        max_posts = min(5, len(example_posts))
        
        for task_id, posts in list(posts_by_task.items())[:3]:  # Максимум 3 разных задания
            if shown_count >= max_posts:
                break
            
            task = posts[0].task
            posts_to_show = posts[:2]  # По 1-2 поста из каждого задания
            
            # Отправляем текст задания
            await update.message.reply_text(
                f"📋 <b>Задание:</b> {task.text}",
                parse_mode='HTML'
            )
            
            # Отправляем посты
            for post in posts_to_show:
                if shown_count >= max_posts:
                    break
                
                author = post.author
                caption = f"Автор: {author.name}"
                
                try:
                    if post.media_type == 'photo':
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=post.media_file_id,
                            caption=caption
                        )
                    else:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=post.media_file_id,
                            caption=caption
                        )
                    shown_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки примера поста {post.id}: {e}")
                    continue
            
            # Небольшая пауза между заданиями
            if shown_count < max_posts and len(posts_by_task) > 1:
                import asyncio
                await asyncio.sleep(0.5)
        
    finally:
        db.close()


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик колбэков онбординга"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(':')[1]
    
    if action == 'screen1':
        await show_onboarding_screen_1(update, context)
    elif action == 'screen2':
        await show_onboarding_screen_2(update, context)
    elif action == 'screen3':
        await show_onboarding_screen_3(update, context)
    elif action == 'trial_photo':
        await handle_trial_photo_request(update, context)
    elif action == 'register':
        # Переходим к регистрации - отправляем сообщение с инструкцией
        await query.edit_message_text(
            "🚀 <b>Регистрация</b>\n\n"
            "Используй команду /register для начала регистрации.",
            parse_mode='HTML'
        )


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик регистрации пользователя"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # Проверяем, не зарегистрирован ли уже
        existing_user = db.query(User).filter(User.telegram_id == user_id).first()
        if existing_user:
            await update.message.reply_text("Ты уже зарегистрирован! ✅")
            return
        
        # Запрашиваем имя
        context.user_data['registration_step'] = 'name'
        await update.message.reply_text(
            "📝 Регистрация в ShotShare\n\n"
            "Для участия нужно всего несколько шагов:\n\n"
            "1️⃣ Отправь свое имя или никнейм (как тебя будут видеть другие пользователи)\n\n"
            "Отправь свое имя или никнейм:"
        )
    finally:
        db.close()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (для регистрации и обновления канала)"""
    registration_step = context.user_data.get('registration_step')
    
    if registration_step == 'name':
        await handle_registration_name(update, context)
    elif registration_step == 'channel':
        await handle_registration_channel(update, context)
    elif registration_step == 'update_channel':
        await handle_update_channel(update, context)
    else:
        # Проверяем, не является ли сообщение ссылкой на канал
        text = update.message.text.strip()
        if (text.startswith('https://t.me/') or text.startswith('@')) and len(text) > 5:
            # Возможно, пользователь хочет обновить канал
            await handle_channel_link_detection(update, context)


async def handle_registration_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени при регистрации"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("Имя слишком короткое. Попробуй еще раз:")
            return
        
        context.user_data['registration_name'] = name
        context.user_data['registration_step'] = 'channel'
        
        keyboard = [
            [InlineKeyboardButton("Пропустить", callback_data="skip_channel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Отлично, {name}! ✅\n\n"
            "2️⃣ Теперь про канал (необязательно):\n\n"
            "Если у тебя есть Telegram канал, отправь ссылку на него.\n"
            "Другие пользователи смогут подписаться на твой канал, просматривая твои посты.\n\n"
            "📝 Формат ссылки:\n"
            "• https://t.me/твой_канал\n"
            "• @твой_канал\n\n"
            "Или нажми кнопку 'Пропустить', если канала нет (можно добавить позже).",
            reply_markup=reply_markup
        )
    finally:
        db.close()


async def handle_registration_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода канала при регистрации"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        channel_link = update.message.text.strip()
        
        # Простая валидация ссылки
        if not (channel_link.startswith('https://t.me/') or channel_link.startswith('@')):
            await update.message.reply_text(
                "Неверный формат ссылки. Отправь ссылку вида https://t.me/channel_name или @channel_name\n"
                "Или используй кнопку 'Пропустить'"
            )
            return
        
        # Сохраняем пользователя
        name = context.user_data.get('registration_name')
        username = update.effective_user.username
        
        user = User(
            telegram_id=user_id,
            username=username,
            name=name,
            channel_link=channel_link,
            is_active=True
        )
        db.add(user)
        db.commit()
        
        context.user_data.pop('registration_step', None)
        context.user_data.pop('registration_name', None)
        
        await update.message.reply_text(
            f"🎉 Регистрация завершена, {name}!\n\n"
            "✅ Теперь ты зарегистрирован в ShotShare!\n\n"
            "📋 Что дальше?\n"
            "• Каждый день ты будешь получать задания\n"
            "• Отправляй фото или видео (до 10 секунд) по заданиям\n"
            "• Твой контент будет показан другим пользователям\n"
            "• Просматривай и оценивай контент других участников\n\n"
            "💡 Совет: можешь добавить канал позже, отправив ссылку боту"
        )
    finally:
        db.close()


async def handle_skip_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пропуска канала при регистрации"""
    db = SessionLocal()
    try:
        query = update.callback_query
        await query.answer("Канал пропущен")
        
        user_id = query.from_user.id
        name = context.user_data.get('registration_name')
        username = query.from_user.username
        
        # Проверяем, что имя было сохранено
        if not name:
            await query.edit_message_text(
                "❌ Ошибка: имя не найдено. Начни регистрацию заново командой /register"
            )
            return
        
        # Проверяем, не зарегистрирован ли уже
        existing_user = db.query(User).filter(User.telegram_id == user_id).first()
        if existing_user:
            await query.edit_message_text(
                "✅ Ты уже зарегистрирован!"
            )
            return
        
        # Создаем пользователя
        user = User(
            telegram_id=user_id,
            username=username,
            name=name,
            channel_link=None,
            is_active=True
        )
        db.add(user)
        db.commit()
        
        # Очищаем данные регистрации
        context.user_data.pop('registration_step', None)
        context.user_data.pop('registration_name', None)
        
        await query.edit_message_text(
            f"🎉 Регистрация завершена, {name}!\n\n"
            "✅ Теперь ты зарегистрирован в ShotShare!\n\n"
            "📋 Что дальше?\n"
            "• Каждый день ты будешь получать задания\n"
            "• Отправляй фото или видео (до 10 секунд) по заданиям\n"
            "• Твой контент будет показан другим пользователям\n"
            "• Просматривай и оценивай контент других участников\n\n"
            "💡 Совет: можешь добавить канал позже, отправив ссылку боту"
        )
    except Exception as e:
        logger.error(f"Ошибка при пропуске канала: {e}")
        try:
            await query.edit_message_text(
                "❌ Произошла ошибка при регистрации. Попробуй еще раз командой /register"
            )
        except:
            pass
    finally:
        db.close()


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки медиа (фото/видео)"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        
        # Проверяем, не пробное ли это фото
        if context.user_data.get('waiting_trial_photo'):
            await handle_trial_media(update, context)
            return
        
        # Проверяем регистрацию
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            # Предлагаем пройти онбординг
            keyboard = [
                [InlineKeyboardButton("🚀 Начать", callback_data="onboarding:screen1")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Сначала нужно зарегистрироваться. Пройди быстрый онбординг:",
                reply_markup=reply_markup
            )
            return
        
        # Проверяем активность
        if not user.is_active:
            await update.message.reply_text(
                "Твой аккаунт неактивен. Обратись к администратору."
            )
            return
        
        # Проверяем активные санкции (только баны, предупреждения не блокируют)
        active_bans = db.query(Sanction).filter(
            Sanction.user_id == user.id,
            Sanction.is_active == True,
            Sanction.sanction_type != SanctionType.WARNING,  # Предупреждения не блокируют
            (Sanction.expires_at == None) | (Sanction.expires_at > datetime.utcnow())
        ).all()
        
        if active_bans:
            # Определяем тип бана для более информативного сообщения
            ban_types = [ban.sanction_type for ban in active_bans]
            if SanctionType.ACCOUNT_BAN in ban_types:
                ban_message = "❌ Твой аккаунт заблокирован. Обратись к администратору."
            elif SanctionType.SESSION_BAN in ban_types:
                ban_message = "❌ Твой аккаунт заблокирован на сессию. Обратись к администратору."
            elif SanctionType.DAY_BAN in ban_types:
                ban_message = "❌ Твой аккаунт заблокирован на 1 день. Обратись к администратору."
            else:
                ban_message = "❌ Твой аккаунт заблокирован. Обратись к администратору."
            
            await update.message.reply_text(ban_message)
            return
        
        # Проверяем предупреждения (информативно, но не блокируют)
        active_warnings = db.query(Sanction).filter(
            Sanction.user_id == user.id,
            Sanction.is_active == True,
            Sanction.sanction_type == SanctionType.WARNING,
            (Sanction.expires_at == None) | (Sanction.expires_at > datetime.utcnow())
        ).count()
        
        if active_warnings > 0:
            # Можно показать предупреждение, но не блокировать
            logger.info(f"Пользователь {user.name} имеет {active_warnings} активных предупреждений")
        
        # Проверяем, есть ли активное задание
        active_task = db.query(Task).filter(
            Task.is_active == True,
            Task.scheduled_time <= datetime.utcnow()
        ).order_by(Task.scheduled_time.desc()).first()
        
        if not active_task:
            await update.message.reply_text(
                "Сейчас нет активных заданий. Дождись нового задания от бота."
            )
            return
        
        # Проверяем, есть ли активная сессия
        today = datetime.utcnow().date()
        session = db.query(Session).filter(
            Session.task_id == active_task.id,
            Session.date >= datetime.combine(today, datetime.min.time())
        ).first()
        
        if not session:
            await update.message.reply_text(
                "Сессия еще не началась. Дождись уведомления о задании."
            )
            return
        
        # Проверяем дедлайн
        now = datetime.utcnow()
        if now > session.content_submission_deadline:
            deadline_str = session.content_submission_deadline.strftime('%d.%m.%Y в %H:%M UTC')
            await update.message.reply_text(
                f"⏰ Время отправки контента истекло.\n\n"
                f"Дедлайн был: {deadline_str}\n"
                f"Дождись следующего задания."
            )
            return
        
        # Показываем сколько времени осталось до дедлайна
        time_left = session.content_submission_deadline - now
        hours_left = int(time_left.total_seconds() / 3600)
        minutes_left = int((time_left.total_seconds() % 3600) / 60)
        
        if hours_left > 0:
            time_left_str = f"{hours_left} ч. {minutes_left} мин."
        else:
            time_left_str = f"{minutes_left} мин."
        
        # Проверяем, не отправил ли уже контент в эту сессию (кроме отклоненных)
        existing_post = db.query(Post).filter(
            Post.author_id == user.id,
            Post.session_id == session.id,
            Post.status != PostStatus.REJECTED
        ).first()
        
        if existing_post:
            await update.message.reply_text(
                "Ты уже отправил контент для этого задания. Дождись следующего задания."
            )
            return
        
        # Если есть отклоненный пост, удаляем его перед созданием нового
        rejected_post = db.query(Post).filter(
            Post.author_id == user.id,
            Post.task_id == active_task.id,
            Post.status == PostStatus.REJECTED
        ).first()
        
        if rejected_post:
            db.delete(rejected_post)
            db.commit()
        
        # Обработка видео
        if update.message.video:
            video = update.message.video
            if video.duration and video.duration > 10:
                await update.message.reply_text(
                    "❌ Видео должно быть не длиннее 10 секунд."
                )
                return
            
            media_file_id = video.file_id
            media_type = 'video'
        
        # Обработка фото
        elif update.message.photo:
            photo = update.message.photo[-1]  # Берем фото наибольшего размера
            media_file_id = photo.file_id
            media_type = 'photo'
        else:
            await update.message.reply_text(
                "Отправь фото или видео (до 10 секунд)."
            )
            return
        
        # Сохраняем пост
        # Одобряем сразу при загрузке - модерация будет через жалобы пользователей
        post = Post(
            author_id=user.id,
            task_id=active_task.id,
            session_id=session.id,
            media_file_id=media_file_id,
            media_type=media_type,
            status=PostStatus.APPROVED  # Одобряем сразу, модерация через жалобы
        )
        db.add(post)
        user.posts_count += 1
        db.commit()
        
        await update.message.reply_text(
            f"✅ Контент успешно загружен!\n\n"
            f"Он будет распределен для показа другим пользователям после дедлайна.\n\n"
            f"⏰ До дедлайна осталось: {time_left_str}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке медиа: {e}")
        await update.message.reply_text(
            "Произошла ошибка при загрузке контента. Попробуй еще раз."
        )
    finally:
        db.close()


async def handle_resubmit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Прислать новый материал' после отклонения"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        task_id = int(query.data.split(':')[1])
        user_id = query.from_user.id
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await query.edit_message_text("Пользователь не найден")
            return
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("Задание не найдено")
            return
        
        # Проверяем, есть ли уже отклоненный пост по этому заданию
        rejected_post = db.query(Post).filter(
            Post.author_id == user.id,
            Post.task_id == task_id,
            Post.status == PostStatus.REJECTED
        ).first()
        
        if rejected_post:
            # Удаляем старый отклоненный пост
            db.delete(rejected_post)
            db.commit()
        
        await query.edit_message_text(
            f"📤 <b>Пришли новый материал</b>\n\n"
            f"Задание: {task.text}\n\n"
            f"Отправь фото или видео (до 10 секунд), соответствующее заданию.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке повторной отправки: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуй еще раз.")
    finally:
        db.close()


async def handle_task_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка принятия задания"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        task_id = int(query.data.split(':')[1])
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await query.edit_message_text("Сначала зарегистрируйся: /register")
            return
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await query.edit_message_text("Задание не найдено.")
            return
        
        # Находим сессию для этого задания
        session = db.query(Session).filter(Session.task_id == task_id).order_by(Session.date.desc()).first()
        
        # Обновляем активность
        user.last_activity = datetime.utcnow()
        user.inactive_days_count = 0
        db.commit()
        
        if session:
            # Показываем информацию о дедлайне
            now = datetime.utcnow()
            deadline_str = session.content_submission_deadline.strftime('%d.%m.%Y в %H:%M UTC')
            time_left = session.content_submission_deadline - now
            
            if time_left.total_seconds() > 0:
                hours_left = int(time_left.total_seconds() / 3600)
                minutes_left = int((time_left.total_seconds() % 3600) / 60)
                if hours_left > 0:
                    time_left_str = f"{hours_left} ч. {minutes_left} мин."
                else:
                    time_left_str = f"{minutes_left} мин."
                
                message = (
                    f"✅ Задание принято!\n\n"
                    f"📋 {task.text}\n\n"
                    f"⏰ Дедлайн отправки: {deadline_str}\n"
                    f"⏳ Осталось времени: {time_left_str}\n\n"
                    f"Отправь фото или видео (до 10 секунд) по заданию."
                )
            else:
                message = (
                    f"✅ Задание принято!\n\n"
                    f"📋 {task.text}\n\n"
                    f"⏰ Дедлайн уже прошел: {deadline_str}\n"
                    f"К сожалению, время на отправку контента истекло."
                )
        else:
            message = (
                f"✅ Задание принято!\n\n"
                f"📋 {task.text}\n\n"
                f"Отправь фото или видео (до 10 секунд) по заданию."
            )
        
        await query.edit_message_text(message)
    finally:
        db.close()


async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка жалобы на пост"""
    query = update.callback_query
    await query.answer("Жалоба отправлена на модерацию")
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        post_id = int(query.data.split(':')[1])
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        
        # Проверяем, не жаловался ли уже
        existing_complaint = db.query(Complaint).filter(
            Complaint.post_id == post_id,
            Complaint.complainer_id == user.id
        ).first()
        
        if existing_complaint:
            await query.answer("Ты уже жаловался на этот пост", show_alert=True)
            return
        
        # Создаем жалобу
        complaint = Complaint(
            post_id=post_id,
            complainer_id=user.id
        )
        db.add(complaint)
        post.complaints_count += 1
        
        # Проверяем порог жалоб
        if post.complaints_count >= config.COMPLAINTS_THRESHOLD:
            post.status = PostStatus.MODERATION
        
        db.commit()
        
    finally:
        db.close()


async def handle_like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка лайка поста"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        post_id = int(query.data.split(':')[1])
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        
        # Проверяем, лайкал ли уже
        view = db.query(PostView).filter(
            PostView.post_id == post_id,
            PostView.viewer_id == user.id
        ).first()
        
        if view:
            if view.liked:
                view.liked = False
                post.likes_count -= 1
                post.author.likes_received -= 1
            else:
                view.liked = True
                post.likes_count += 1
                post.author.likes_received += 1
        else:
            view = PostView(
                post_id=post_id,
                viewer_id=user.id,
                liked=True
            )
            db.add(view)
            post.views_count += 1
            post.likes_count += 1
            post.author.views_received += 1
            post.author.likes_received += 1
        
        db.commit()
        
        # Обновляем кнопку
        keyboard = [
            [InlineKeyboardButton(f"❤️ {post.likes_count}", callback_data=f"like:{post_id}")],
        ]
        if post.author.channel_link:
            keyboard.append([InlineKeyboardButton("📢 Подписаться", callback_data=f"subscribe:{post_id}")])
        keyboard.append([InlineKeyboardButton("⚠️ Пожаловаться", callback_data=f"complaint:{post_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except:
            pass  # Сообщение могло быть изменено
        
    finally:
        db.close()


async def handle_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подписки на канал"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        post_id = int(query.data.split(':')[1])
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post or not post.author.channel_link:
            await query.answer("У автора нет канала", show_alert=True)
            return
        
        # Отмечаем подписку
        view = db.query(PostView).filter(
            PostView.post_id == post_id,
            PostView.viewer_id == user.id
        ).first()
        
        if not view:
            view = PostView(
                post_id=post_id,
                viewer_id=user.id,
                subscribed=True
            )
            db.add(view)
            post.views_count += 1
        else:
            view.subscribed = True
        
        post.author.subscribers_gained += 1
        db.commit()
        
        await query.answer("Спасибо за подписку! 🎉", show_alert=True)
        
        # Отправляем ссылку на канал
        await query.message.reply_text(
            f"📢 Канал автора: {post.author.channel_link}"
        )
        
    finally:
        db.close()


async def handle_view_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка просмотра поста"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        post_id = int(query.data.split(':')[1])
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        
        # Отмечаем просмотр
        view = db.query(PostView).filter(
            PostView.post_id == post_id,
            PostView.viewer_id == user.id
        ).first()
        
        if not view:
            view = PostView(
                post_id=post_id,
                viewer_id=user.id
            )
            db.add(view)
            post.views_count += 1
            post.author.views_received += 1
            db.commit()
        
        # Отправляем пост
        caption = f"Автор: {post.author.name}\nЗадание: {post.task.text}"
        
        keyboard = [
            [InlineKeyboardButton(f"❤️ {post.likes_count}", callback_data=f"like:{post_id}")],
        ]
        if post.author.channel_link:
            keyboard.append([InlineKeyboardButton("📢 Подписаться", callback_data=f"subscribe:{post_id}")])
        keyboard.append([InlineKeyboardButton("⚠️ Пожаловаться", callback_data=f"complaint:{post_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if post.media_type == 'photo':
            await query.message.reply_photo(
                photo=post.media_file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await query.message.reply_video(
                video=post.media_file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        
    finally:
        db.close()


async def about_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /about - подробное описание системы"""
    text = (
        "📸 <b>Что такое ShotShare?</b>\n\n"
        "ShotShare — это социальная сеть внутри Telegram, где пользователи делятся "
        "живыми моментами из своей жизни по ежедневным заданиям.\n\n"
        
        "🎯 <b>Как это работает?</b>\n\n"
        "<b>1. Ежедневные задания</b>\n"
        "Каждый день (1-3 раза) всем активным пользователям приходит одно неожиданное задание. "
        "Например: \"Покажи, где ты прямо сейчас\" или \"Сфотографируй что-то синее\".\n\n"
        
        "<b>2. Отправка контента</b>\n"
        "У тебя есть ограниченное время (обычно 10 минут) на выполнение задания. "
        "Отправь фото или видео (до 10 секунд), соответствующее заданию. "
        "Задания могут быть разными: от \"здесь и сейчас\" до \"лучший момент за месяц\" — "
        "важно, чтобы контент соответствовал заданию!\n\n"
        
        "<b>3. Распределение постов</b>\n"
        "После дедлайна твой контент распределяется другим пользователям:\n"
        "• <b>Честные слоты</b> — гарантированные показы по формуле N/M "
        "(количество пользователей / количество авторов)\n"
        "• <b>Случайные слоты</b> — 2-3 поста показываются всем для дополнительного интереса\n\n"
        
        "<b>4. Просмотр и взаимодействие</b>\n"
        "Ты просматриваешь контент других участников, можешь:\n"
        "• ❤️ Ставить лайки\n"
        "• 📢 Подписываться на каналы авторов (если у них есть канал)\n"
        "• ⚠️ Пожаловаться, если контент не соответствует заданию\n\n"
        
        "🔍 <b>Зачем это нужно?</b>\n\n"
        "• Смотреть, как живут другие люди в реальном времени\n"
        "• Ловить живые моменты и делиться ими\n"
        "• Развивать личный блог — если хочешь (канал необязателен)\n"
        "• Получать обратную связь и подписчиков\n\n"
        
        "✨ <b>Особенности системы</b>\n\n"
        "• <b>Честное распределение</b> — каждый автор получает гарантированные показы\n"
        "• <b>Случайность</b> — элемент неожиданности через случайные слоты\n"
        "• <b>Модерация</b> — система жалоб и автоматическая проверка контента\n"
        "• <b>Активность</b> — проверка активности пользователей для поддержания качества\n"
        "• <b>Канал необязателен</b> — можно просто участвовать без канала\n\n"
        
        "💡 <b>Внутренняя логика</b>\n\n"
        "Система работает по принципу обмена контентом:\n"
        "• Все получают одно задание одновременно\n"
        "• Контент должен соответствовать заданию (может быть как свежим, так и из архива)\n"
        "• Автор никогда не видит свой собственный пост\n"
        "• Распределение гарантирует, что каждый получит хотя бы 1 пост\n"
        "• При малом количестве пользователей (≤5) посты показываются всем\n\n"
        
        "🚀 <b>Начни прямо сейчас!</b>\n"
        "Используй /register для регистрации или /start для онбординга."
    )
    
    await update.message.reply_text(text, parse_mode='HTML')


async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rules - правила и ограничения"""
    text = (
        "📋 <b>Правила и ограничения ShotShare</b>\n\n"
        
        "🚫 <b>Запрещенный контент</b>\n\n"
        "Строго запрещается публиковать любой контент, который:\n\n"
        
        "• <b>Нарушает законы</b>\n"
        "  - Контент, нарушающий законодательство вашей страны\n"
        "  - Пропаганда насилия, экстремизма, терроризма\n"
        "  - Призывы к незаконным действиям\n\n"
        
        "• <b>Содержит неприемлемые материалы</b>\n"
        "  - Порнографический контент\n"
        "  - Материалы с насилием или жестокостью\n"
        "  - Контент, оскорбляющий достоинство людей\n"
        "  - Дискриминация по любым признакам\n\n"
        
        "• <b>Нарушает права других</b>\n"
        "  - Контент без согласия изображенных лиц\n"
        "  - Нарушение авторских прав\n"
        "  - Клевета и оскорбления\n"
        "  - Распространение личных данных без согласия\n\n"
        
        "• <b>Не соответствует заданию</b>\n"
        "  - Контент, не имеющий отношения к заданию\n"
        "  - Спам или реклама\n"
        "  - Контент, не соответствующий требованиям задания\n\n"
        
        "⚖️ <b>Система модерации</b>\n\n"
        "• <b>Автоматическая проверка</b>\n"
        "  Система автоматически проверяет контент на соответствие правилам\n\n"
        
        "• <b>Жалобы пользователей</b>\n"
        "  Если пост получил 3+ жалоб, он отправляется на модерацию\n"
        "  Модератор принимает решение: одобрить, удалить или применить санкцию\n\n"
        
        "• <b>Административная модерация</b>\n"
        "  Администраторы могут просматривать и модерировать контент вручную\n\n"
        
        "⚠️ <b>Санкции за нарушения</b>\n\n"
        "За нарушение правил могут быть применены следующие санкции:\n\n"
        
        "• <b>Предупреждение</b>\n"
        "  Первое нарушение — предупреждение\n"
        "  При накоплении 3+ предупреждений — автоматический бан\n\n"
        
        "• <b>Блок на 1 день</b>\n"
        "  Временная блокировка аккаунта на 24 часа\n\n"
        
        "• <b>Блок на сессию</b>\n"
        "  Блокировка на 7 дней (одну сессию)\n\n"
        
        "• <b>Блок аккаунта</b>\n"
        "  Постоянная блокировка аккаунта за серьезные нарушения\n\n"
        
        "📏 <b>Технические ограничения</b>\n\n"
        "• Видео должно быть не длиннее 10 секунд\n"
        "• Контент должен быть отправлен в течение дедлайна задания\n"
        "• Один пост на задание (повторная отправка заменяет предыдущий)\n"
        "• Контент должен соответствовать формату (фото или видео)\n\n"
        
        "✅ <b>Что разрешено</b>\n\n"
        "• Любой контент, соответствующий заданию\n"
        "• Фото и видео из реальной жизни\n"
        "• Творческий подход к выполнению заданий\n"
        "• Участие без канала (канал необязателен)\n"
        "• Лайки и подписки на каналы авторов\n\n"
        
        "🛡️ <b>Безопасность</b>\n\n"
        "• Не публикуйте личную информацию (адреса, телефоны, документы)\n"
        "• Уважайте приватность других людей\n"
        "• Сообщайте о нарушениях через систему жалоб\n\n"
        
        "📞 <b>Обратная связь</b>\n\n"
        "Если у тебя есть вопросы или предложения, используй команду /help\n"
        "Для жалоб на контент используй кнопку \"⚠️ Пожаловаться\" под постом.\n\n"
        
        "⚠️ <b>Важно</b>\n"
        "Нарушение правил может привести к блокировке аккаунта. "
        "Будь ответственным и уважай других участников!"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        user = db.query(User).filter(User.telegram_id == user_id).first()
        
        help_text = (
            "📋 <b>Доступные команды:</b>\n\n"
            "/start - Главное меню и информация о боте\n"
            "/register - Регистрация в системе\n"
            "/setchannel - Добавить или изменить канал\n"
            "/about - Что это и как работает (подробное описание)\n"
            "/rules - Правила и ограничения\n"
            "/help - Показать это сообщение\n\n"
        )
        
        if user:
            help_text += (
                f"👤 <b>Твой профиль:</b>\n"
                f"Имя: {user.name}\n"
            )
            if user.channel_link:
                help_text += f"Канал: {user.channel_link}\n"
            else:
                help_text += "Канал: не указан\n"
            
            help_text += (
                f"\n📊 <b>Статистика:</b>\n"
                f"Постов отправлено: {user.posts_count}\n"
                f"Просмотров получено: {user.views_received}\n"
                f"Лайков получено: {user.likes_received}\n"
                f"Подписчиков получено: {user.subscribers_gained}\n"
            )
        else:
            help_text += (
                "💡 <b>Начни с регистрации:</b>\n"
                "Используй команду /register для регистрации в системе."
            )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    finally:
        db.close()


async def set_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды для установки/обновления канала"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await update.message.reply_text(
                "Сначала нужно зарегистрироваться. Используй /register"
            )
            return
        
        # Запрашиваем ссылку на канал
        context.user_data['registration_step'] = 'update_channel'
        
        keyboard = [
            [InlineKeyboardButton("Удалить канал", callback_data="remove_channel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if user.channel_link:
            await update.message.reply_text(
                f"Твой текущий канал: {user.channel_link}\n\n"
                "Отправь новую ссылку на канал для обновления:\n\n"
                "Формат: https://t.me/channel_name или @channel_name\n\n"
                "Или нажми кнопку, чтобы удалить канал.",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Отправь ссылку на свой Telegram канал:\n\n"
                "Формат: https://t.me/channel_name или @channel_name",
                reply_markup=reply_markup
            )
    finally:
        db.close()


async def handle_update_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обновления канала"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        channel_link = update.message.text.strip()
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await update.message.reply_text("Пользователь не найден")
            return
        
        # Простая валидация ссылки
        if not (channel_link.startswith('https://t.me/') or channel_link.startswith('@')):
            await update.message.reply_text(
                "Неверный формат ссылки. Отправь ссылку вида:\n"
                "• https://t.me/channel_name\n"
                "• @channel_name"
            )
            return
        
        # Обновляем канал
        user.channel_link = channel_link
        db.commit()
        
        context.user_data.pop('registration_step', None)
        
        await update.message.reply_text(
            f"✅ Канал обновлен!\n\n"
            f"Твой канал: {channel_link}\n\n"
            "Теперь другие пользователи смогут подписаться на твой канал, просматривая твои посты."
        )
    finally:
        db.close()


async def handle_channel_link_detection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автоматическое определение ссылки на канал в сообщении"""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return  # Не зарегистрирован, игнорируем
        
        # Проверяем, является ли текст ссылкой на канал
        if (text.startswith('https://t.me/') or text.startswith('@')) and len(text) > 5:
            # Предлагаем обновить канал
            keyboard = [
                [InlineKeyboardButton("✅ Да, это мой канал", callback_data=f"confirm_channel:{text}")],
                [InlineKeyboardButton("❌ Нет", callback_data="cancel_channel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Обнаружена ссылка на канал: {text}\n\n"
                "Хочешь добавить/обновить свой канал?",
                reply_markup=reply_markup
            )
    finally:
        db.close()


async def handle_confirm_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение добавления канала"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        channel_link = query.data.split(':', 1)[1]
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await query.edit_message_text("Пользователь не найден")
            return
        
        user.channel_link = channel_link
        db.commit()
        
        await query.edit_message_text(
            f"✅ Канал добавлен!\n\n"
            f"Твой канал: {channel_link}\n\n"
            "Теперь другие пользователи смогут подписаться на твой канал."
        )
    finally:
        db.close()


async def handle_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление канала"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await query.edit_message_text("Пользователь не найден")
            return
        
        user.channel_link = None
        db.commit()
        
        context.user_data.pop('registration_step', None)
        
        await query.edit_message_text(
            "✅ Канал удален.\n\n"
            "Ты можешь добавить канал позже командой /setchannel"
        )
    finally:
        db.close()


async def handle_cancel_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления канала"""
    query = update.callback_query
    await query.answer("Отменено")
    
    context.user_data.pop('registration_step', None)
    await query.edit_message_text("Ок, канал не добавлен.")


async def handle_activity_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на проверку активности"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        user_id = query.from_user.id
        response = query.data
        
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return
        
        if response == "activity_yes":
            user.last_activity = datetime.utcnow()
            user.inactive_days_count = 0
            await query.edit_message_text("Отлично! Ждем твоего контента! 🎉")
        elif response == "activity_no":
            user.inactive_days_count += 1
            await query.edit_message_text("Понятно. Увидимся в следующий раз! 👋")
        
        db.commit()
    finally:
        db.close()

