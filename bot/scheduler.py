import logging
from datetime import datetime, timedelta, time
from telegram.ext import Application
from database import SessionLocal
from database.models import User, Task, Session, Post, PostStatus, PostType
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config
import random

logger = logging.getLogger(__name__)


async def send_daily_tasks(context):
    """Отправка ежедневных заданий пользователям"""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        logger.info(f"Проверка заданий для отправки. Текущее время UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Ищем задания, которые должны были быть отправлены, но еще не отправлены
        # Проверяем задания, у которых scheduled_time уже прошло (или в ближайшие 2 минуты)
        # и которые еще не были отправлены
        time_window_end = now + timedelta(minutes=2)  # Небольшой запас на будущее
        
        # Сначала проверим все активные задания для отладки
        all_active_tasks = db.query(Task).filter(Task.is_active == True).all()
        logger.info(f"Всего активных заданий: {len(all_active_tasks)}")
        for task in all_active_tasks:
            logger.info(f"Задание #{task.id}: scheduled_time={task.scheduled_time}, sent_at={task.sent_at}, is_active={task.is_active}")
        
        tasks_to_send = db.query(Task).filter(
            Task.is_active == True,
            Task.sent_at == None,  # Еще не отправлено
            Task.scheduled_time <= time_window_end  # Время отправки уже наступило или скоро наступит
        ).all()
        
        if not tasks_to_send:
            logger.info("Нет заданий для отправки в текущее время")
            # Проверим, почему задания не найдены
            unsent_tasks = db.query(Task).filter(
                Task.is_active == True,
                Task.sent_at == None
            ).all()
            if unsent_tasks:
                logger.info(f"Найдено {len(unsent_tasks)} неотправленных заданий:")
                for task in unsent_tasks:
                    time_diff = (task.scheduled_time - now).total_seconds() / 60
                    logger.info(f"  Задание #{task.id}: scheduled_time={task.scheduled_time}, разница с текущим временем: {time_diff:.1f} минут")
            return
        
        logger.info(f"Найдено {len(tasks_to_send)} заданий для отправки")
        
        for task in tasks_to_send:
            # Проверяем еще раз, не отправили ли уже (на случай параллельных запусков)
            if task.sent_at:
                continue
        
            # Создаем сессию
            # Дедлайн устанавливаем через N минут после отправки задания
            now = datetime.utcnow()
            deadline_time = now + timedelta(minutes=config.TASK_COMPLETION_MINUTES)
            
            session = Session(
                task_id=task.id,
                date=datetime.utcnow(),
                content_submission_deadline=deadline_time
            )
            db.add(session)
            db.commit()
            
            # Получаем активных пользователей
            active_users = db.query(User).filter(User.is_active == True).all()
            
            keyboard = [
                [InlineKeyboardButton("✅ Принять задание", callback_data=f"accept_task:{task.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            sent_count = 0
            failed_count = 0
            
            logger.info(f"Обработка задания #{task.id}: '{task.text[:50]}...'")
            logger.info(f"Время отправки задания: {task.scheduled_time}, текущее время: {now}")
            
            # Форматируем дедлайн для сообщения
            deadline_str = deadline_time.strftime('%d.%m.%Y в %H:%M UTC')
            minutes_until_deadline = int((deadline_time - now).total_seconds() / 60)
            
            if minutes_until_deadline >= 60:
                time_left_str = f"{minutes_until_deadline // 60} ч. {minutes_until_deadline % 60} мин."
            else:
                time_left_str = f"{minutes_until_deadline} мин."
            
            logger.info(f"Активных пользователей для отправки: {len(active_users)}")
            
            if not active_users:
                logger.warning(f"Нет активных пользователей для отправки задания #{task.id}")
            
            for user in active_users:
                try:
                    message_text = (
                        f"📋 Сегодняшнее задание:\n\n"
                        f"{task.text}\n\n"
                        f"⏰ Дедлайн отправки контента: {deadline_str}\n"
                        f"⏳ У тебя есть {time_left_str} на выполнение задания"
                    )
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                    logger.debug(f"Задание отправлено пользователю {user.telegram_id} ({user.name})")
                except Exception as e:
                    logger.error(f"Ошибка отправки задания пользователю {user.telegram_id}: {e}", exc_info=True)
                    failed_count += 1
                    # Помечаем как неактивного, если бот заблокирован
                    if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                        user.is_active = False
                        logger.info(f"Пользователь {user.telegram_id} помечен как неактивный")
            
            task.sent_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ Задание #{task.id} обработано: {sent_count} успешно, {failed_count} ошибок")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке заданий: {e}")
    finally:
        db.close()


async def distribute_posts(context):
    """Распределение постов по слотам после дедлайна"""
    db = SessionLocal()
    try:
        # Находим сессии, где дедлайн прошел, но распределение не выполнено
        sessions = db.query(Session).filter(
            Session.content_submission_deadline < datetime.utcnow(),
            Session.distribution_completed == False
        ).all()
        
        logger.info(f"Найдено {len(sessions)} сессий с истекшим дедлайном для распределения")
        
        for session in sessions:
            logger.info(f"Обработка сессии #{session.id}, дедлайн был: {session.content_submission_deadline}")
            
            # Получаем все одобренные посты сессии
            # Посты одобряются сразу при загрузке, модерация происходит через жалобы
            posts = db.query(Post).filter(
                Post.session_id == session.id,
                Post.status == PostStatus.APPROVED  # Только одобренные посты
            ).all()
            
            logger.info(f"Найдено {len(posts)} одобренных постов для распределения в сессии #{session.id}")
            
            if not posts:
                logger.info(f"Нет постов для распределения в сессии #{session.id}")
                session.distribution_completed = True
                db.commit()
                continue
            
            # Получаем уникальных авторов
            authors = list(set([post.author_id for post in posts]))
            
            # Честные слоты: распределяем по формуле N / M
            # N - количество пользователей, M - количество авторов
            active_users = db.query(User).filter(User.is_active == True).all()
            total_users = len(active_users)
            total_authors = len(authors)
            
            if total_authors > 0:
                posts_per_author = max(1, total_users // total_authors)
                fair_slots_count = min(config.FAIR_SLOTS_PER_AUTHOR, posts_per_author)
            else:
                fair_slots_count = config.FAIR_SLOTS_PER_AUTHOR
            
            # Распределяем честные слоты
            for author_id in authors:
                author_posts = [p for p in posts if p.author_id == author_id]
                selected_posts = random.sample(
                    author_posts,
                    min(fair_slots_count, len(author_posts))
                )
                for post in selected_posts:
                    post.post_type = PostType.FAIR
            
            # Случайные слоты: выбираем 2-3 поста из всех
            remaining_posts = [p for p in posts if p.post_type is None]
            if remaining_posts:
                random_slots = random.sample(
                    remaining_posts,
                    min(config.RANDOM_SLOTS_COUNT, len(remaining_posts))
                )
                for post in random_slots:
                    post.post_type = PostType.RANDOM
            
            session.distribution_completed = True
            db.commit()
            
            logger.info(f"Распределение постов для сессии {session.id} завершено")
            
            # Отправляем посты пользователям
            await send_distributed_posts(context, session.id)
            
    except Exception as e:
        logger.error(f"Ошибка при распределении постов: {e}")
    finally:
        db.close()


async def send_distributed_posts(context, session_id):
    """
    Отправка распределенных постов пользователям.
    
    ВАЖНО: Автор поста НИКОГДА не получает свой собственный пост.
    Это гарантируется на двух уровнях:
    1. При формировании списка получателей автор исключается
    2. В функции send_post_to_users есть дополнительная проверка
    """
    from sqlalchemy.orm import joinedload
    
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            logger.warning(f"Сессия #{session_id} не найдена для отправки постов")
            return
        
        logger.info(f"Начинаем отправку распределенных постов для сессии #{session_id}")
        
        # Получаем распределенные посты с загрузкой автора и задания
        # Исключаем отклоненные посты (REJECTED) и удаленные (DELETED)
        fair_posts = db.query(Post).options(
            joinedload(Post.author),
            joinedload(Post.task)
        ).filter(
            Post.session_id == session_id,
            Post.post_type == PostType.FAIR,
            Post.status != PostStatus.REJECTED,
            Post.status != PostStatus.DELETED
        ).all()
        
        random_posts = db.query(Post).options(
            joinedload(Post.author),
            joinedload(Post.task)
        ).filter(
            Post.session_id == session_id,
            Post.post_type == PostType.RANDOM,
            Post.status != PostStatus.REJECTED,
            Post.status != PostStatus.DELETED
        ).all()
        
        logger.info(f"Найдено постов для отправки: честных слотов={len(fair_posts)}, случайных слотов={len(random_posts)}")
        
        # Получаем активных пользователей
        active_users = db.query(User).filter(User.is_active == True).all()
        logger.info(f"Активных пользователей для получения постов: {len(active_users)}")
        
        if not active_users:
            logger.warning("Нет активных пользователей для отправки постов")
            return
        
        # Отслеживаем, кто получил посты (для гарантии минимума)
        user_posts_received = {user.id: [] for user in active_users}
        
        # Отправляем случайные слоты всем (кроме авторов)
        for post in random_posts:
            # Исключаем автора из получателей (автор не должен видеть свой пост)
            recipients = [u for u in active_users if u.id != post.author_id]
            logger.info(f"Отправка случайного поста #{post.id} автора {post.author.name} {len(recipients)} пользователям")
            await send_post_to_users(context, post, recipients)
            # Отмечаем, кто получил пост
            for recipient in recipients:
                user_posts_received[recipient.id].append(post.id)
        
        # Отправляем честные слоты по распределению
        # Группируем по авторам
        posts_by_author = {}
        for post in fair_posts:
            if post.author_id not in posts_by_author:
                posts_by_author[post.author_id] = []
            posts_by_author[post.author_id].append(post)
        
        # Распределяем пользователей между авторами по формуле N/M
        # N - количество активных пользователей, M - количество авторов
        # ВАЖНО: исключаем автора из получателей его собственных постов
        if posts_by_author:
            # Получаем список всех авторов
            author_ids = list(posts_by_author.keys())
            total_authors = len(author_ids)
            total_users = len(active_users)
            
            if total_authors == 0:
                logger.warning("Нет авторов для распределения")
                return
            
            # Определяем стратегию распределения в зависимости от количества пользователей
            # При малом количестве (≤5) показываем посты всем получателям
            # При большом - используем формулу N/M
            is_small_community = total_users <= 5
            
            if is_small_community:
                logger.info(f"Малое сообщество ({total_users} пользователей): показываем посты всем получателям")
            
            # Для каждого автора распределяем его посты
            for author_id, author_posts in posts_by_author.items():
                # Получаем автора
                author = db.query(User).filter(User.id == author_id).first()
                if not author:
                    continue
                
                # Исключаем автора из списка получателей (ВАЖНО!)
                recipients = [u for u in active_users if u.id != author_id]
                
                if not recipients:
                    logger.warning(f"Нет получателей для поста автора {author_id} (все пользователи - авторы)")
                    continue
                
                if is_small_community:
                    # При малом количестве показываем всем получателям
                    slots_per_author = len(recipients)
                else:
                    # Формула N/M: количество пользователей делим на количество авторов
                    total_recipients = len(recipients)
                    slots_per_author = max(1, total_recipients // total_authors)
                
                logger.info(f"Автор {author.name} (ID: {author_id}): {len(author_posts)} постов, {len(recipients)} получателей, {slots_per_author} получателей на пост")
                
                # Распределяем посты автора между получателями
                # Используем round-robin для более равномерного распределения
                recipient_index = 0
                
                for post in author_posts:
                    if is_small_community:
                        # Показываем всем получателям
                        post_recipients = recipients
                    else:
                        # Выбираем получателей с учетом уже полученных постов
                        # Сортируем получателей по количеству уже полученных постов
                        recipients_sorted = sorted(recipients, key=lambda u: len(user_posts_received[u.id]))
                        
                        # Берем тех, кто получил меньше всего постов
                        num_recipients = min(slots_per_author, len(recipients))
                        post_recipients = recipients_sorted[:num_recipients]
                        
                        # Если нужно больше получателей, добавляем остальных
                        if len(post_recipients) < slots_per_author and len(recipients) > num_recipients:
                            remaining = [u for u in recipients if u not in post_recipients]
                            needed = slots_per_author - len(post_recipients)
                            post_recipients.extend(remaining[:needed])
                    
                    logger.info(f"Отправка честного поста #{post.id} автора {author.name} {len(post_recipients)} пользователям")
                    await send_post_to_users(context, post, post_recipients)
                    
                    # Отмечаем, кто получил пост
                    for recipient in post_recipients:
                        user_posts_received[recipient.id].append(post.id)
            
            # Проверяем, что каждый пользователь получил хотя бы 1 пост
            users_without_posts = [user for user in active_users if len(user_posts_received[user.id]) == 0]
            
            if users_without_posts:
                logger.warning(f"Найдено {len(users_without_posts)} пользователей без постов. Исправляем...")
                
                # Для каждого пользователя без постов находим подходящий пост
                for user in users_without_posts:
                    # Ищем посты, которые этот пользователь еще не получил и автором которых он не является
                    available_posts = []
                    
                    # Проверяем честные слоты
                    for post in fair_posts:
                        if post.author_id != user.id and post.id not in user_posts_received[user.id]:
                            available_posts.append(post)
                    
                    # Проверяем случайные слоты
                    for post in random_posts:
                        if post.author_id != user.id and post.id not in user_posts_received[user.id]:
                            available_posts.append(post)
                    
                    if available_posts:
                        # Выбираем случайный пост для этого пользователя
                        post_to_send = random.choice(available_posts)
                        logger.info(f"Отправка поста #{post_to_send.id} пользователю {user.name} для гарантии минимума")
                        await send_post_to_users(context, post_to_send, [user])
                        user_posts_received[user.id].append(post_to_send.id)
                    else:
                        logger.warning(f"Не удалось найти подходящий пост для пользователя {user.name}")
            
            # Логируем итоговую статистику
            for user in active_users:
                posts_count = len(user_posts_received[user.id])
                logger.info(f"Пользователь {user.name} получил {posts_count} постов")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке распределенных постов: {e}")
    finally:
        db.close()


async def send_post_to_users(context, post, users):
    """Отправка поста пользователям"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    if not users:
        return
    
    # Проверяем, что данные автора и задачи загружены
    # Если post передан из запроса с joinedload, они уже загружены
    # Если нет - загружаем явно
    if not hasattr(post, 'author') or post.author is None:
        from database import SessionLocal
        db = SessionLocal()
        try:
            from sqlalchemy.orm import joinedload
            post = db.query(Post).options(
                joinedload(Post.author),
                joinedload(Post.task)
            ).filter(Post.id == post.id).first()
            if not post:
                logger.error(f"Пост #{post.id} не найден в базе данных")
                return
        finally:
            db.close()
    
    author = post.author
    task = post.task
    
    if not author:
        logger.error(f"Автор поста #{post.id} не найден")
        return
    
    if not task:
        logger.error(f"Задание для поста #{post.id} не найдено")
        return
    
    # Фильтруем список получателей, исключая автора
    users = [u for u in users if u.id != author.id]
    
    if not users:
        logger.info(f"Нет получателей для поста {post.id} (автор исключен)")
        return
    
    logger.debug(f"Отправка поста #{post.id} автора {author.name} {len(users)} пользователям")
    logger.debug(f"Канал автора: {author.channel_link if author.channel_link else 'НЕТ КАНАЛА'}")
    
    caption = f"Автор: {author.name}\nЗадание: {task.text}"
    
    keyboard = [
        [InlineKeyboardButton(f"❤️ {post.likes_count}", callback_data=f"like:{post.id}")],
    ]
    
    # Проверяем наличие канала у автора
    if author.channel_link and author.channel_link.strip():
        logger.info(f"Добавляем кнопку подписки на канал автора {author.name}: {author.channel_link}")
        keyboard.append([InlineKeyboardButton("📢 Подписаться", callback_data=f"subscribe:{post.id}")])
    else:
        logger.warning(f"У автора {author.name} (ID: {author.id}) НЕТ канала или канал пустой")
    
    keyboard.append([InlineKeyboardButton("⚠️ Пожаловаться", callback_data=f"complaint:{post.id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent_count = 0
    failed_count = 0
    
    for user in users:
        try:
            if post.media_type == 'photo':
                await context.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=post.media_file_id,
                    caption=caption,
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_video(
                    chat_id=user.telegram_id,
                    video=post.media_file_id,
                    caption=caption,
                    reply_markup=reply_markup
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки поста {post.id} пользователю {user.telegram_id}: {e}")
            failed_count += 1
    
    logger.info(f"Пост #{post.id} отправлен: {sent_count} успешно, {failed_count} ошибок")


async def check_user_activity(context):
    """Проверка активности пользователей"""
    db = SessionLocal()
    try:
        # Отправляем уведомление всем активным пользователям
        active_users = db.query(User).filter(User.is_active == True).all()
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, участвую", callback_data="activity_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="activity_no")]
        ]
        from telegram import InlineKeyboardMarkup
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        for user in active_users:
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text="Участвуешь сегодня?",
                    reply_markup=reply_markup
                )
                user.last_activity = datetime.utcnow()
                user.inactive_days_count = 0
            except Exception as e:
                logger.error(f"Ошибка отправки проверки активности пользователю {user.telegram_id}: {e}")
                # Если бот заблокирован, помечаем как неактивного
                if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    user.is_active = False
                    user.inactive_days_count += 1
                else:
                    user.inactive_days_count += 1
        
        # Помечаем неактивных пользователей
        inactive_users = db.query(User).filter(
            User.inactive_days_count >= config.INACTIVE_DAYS_THRESHOLD
        ).all()
        
        for user in inactive_users:
            user.is_active = False
            logger.info(f"Пользователь {user.telegram_id} помечен как неактивный")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Ошибка при проверке активности: {e}")
    finally:
        db.close()


async def auto_approve_posts(context):
    """
    Автоматическое одобрение постов (устаревшая функция).
    
    Теперь посты одобряются сразу при загрузке.
    Модерация происходит через жалобы пользователей - если пост получил 3+ жалоб,
    он переходит в статус MODERATION и требует ручной проверки в админке.
    
    Эта функция оставлена для совместимости, но фактически не выполняет действий,
    так как посты уже одобрены при загрузке.
    """
    db = SessionLocal()
    try:
        # Проверяем, есть ли посты в статусе PENDING (на случай если что-то пошло не так)
        pending_posts = db.query(Post).filter(
            Post.status == PostStatus.PENDING,
            Post.complaints_count == 0
        ).all()
        
        if pending_posts:
            logger.info(f"Найдено {len(pending_posts)} постов в статусе PENDING, одобряем их")
            for post in pending_posts:
                post.status = PostStatus.APPROVED
                db.commit()
                logger.info(f"Пост {post.id} автоматически одобрен")
        else:
            logger.debug("Нет постов для автоматического одобрения (все уже одобрены)")
        
    except Exception as e:
        logger.error(f"Ошибка при автоматическом одобрении: {e}")
    finally:
        db.close()


def setup_schedulers(application: Application):
    """Настройка планировщиков задач"""
    job_queue = application.job_queue
    
    if job_queue is None:
        logger.warning("JobQueue не настроен. Планировщики задач не будут работать.")
        logger.warning("Убедитесь, что установлен python-telegram-bot[job-queue]")
        return
    
    # Отправка заданий - проверяем каждую минуту, чтобы отправлять точно в указанное время
    # Это позволяет отправлять задания в любое время, а не только в фиксированное
    job_queue.run_repeating(
        send_daily_tasks,
        interval=60,  # Каждую минуту для более точной отправки
        first=10,  # Через 10 секунд после запуска
        name="send_daily_tasks"
    )
    
    # Распределение постов (проверяем каждые 2 минуты для быстрого распределения после дедлайна)
    job_queue.run_repeating(
        distribute_posts,
        interval=120,  # Каждые 2 минуты для быстрого распределения
        first=30,  # Через 30 секунд после запуска
        name="distribute_posts"
    )
    
    # Проверка активности пользователей
    activity_hour, activity_minute = map(int, config.ACTIVITY_CHECK_TIME.split(':'))
    job_queue.run_daily(
        check_user_activity,
        time=time(activity_hour, activity_minute),
        name="check_user_activity"
    )
    
    # Автоматическое одобрение постов (каждые 30 минут)
    job_queue.run_repeating(
        auto_approve_posts,
        interval=1800,  # Каждые 30 минут
        first=30,
        name="auto_approve_posts"
    )
    
    logger.info("Планировщики задач настроены")

