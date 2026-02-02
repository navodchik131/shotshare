from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import SessionLocal, init_db
from database.models import (
    User, Task, Session, Post, PostStatus, PostType, Complaint,
    Sanction, SanctionType
)
from datetime import datetime, timedelta
import config
import os
import requests

app = Flask(__name__)
app.secret_key = config.ADMIN_SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class AdminUser:
    def __init__(self, username):
        self.username = username
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return self.username


@login_manager.user_loader
def load_user(username):
    if username == config.ADMIN_USERNAME:
        return AdminUser(username)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            user = AdminUser(username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    db = SessionLocal()
    try:
        # Статистика
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_posts = db.query(Post).count()
        pending_posts = db.query(Post).filter(Post.status == PostStatus.PENDING).count()
        moderation_posts = db.query(Post).filter(Post.status == PostStatus.MODERATION).count()
        total_tasks = db.query(Task).count()
        active_tasks = db.query(Task).filter(Task.is_active == True).count()
        
        # Последние посты
        recent_posts = db.query(Post).order_by(Post.created_at.desc()).limit(10).all()
        
        # Последние задания
        recent_tasks = db.query(Task).order_by(Task.created_at.desc()).limit(5).all()
        
        return render_template('index.html',
                             total_users=total_users,
                             active_users=active_users,
                             total_posts=total_posts,
                             pending_posts=pending_posts,
                             moderation_posts=moderation_posts,
                             total_tasks=total_tasks,
                             active_tasks=active_tasks,
                             recent_posts=recent_posts,
                             recent_tasks=recent_tasks)
    finally:
        db.close()


@app.route('/tasks')
@login_required
def tasks():
    db = SessionLocal()
    try:
        all_tasks = db.query(Task).order_by(Task.created_at.desc()).all()
        return render_template('tasks.html', tasks=all_tasks)
    finally:
        db.close()


@app.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        db = SessionLocal()
        try:
            text = request.form.get('text')
            scheduled_date = request.form.get('scheduled_date')
            scheduled_time = request.form.get('scheduled_time')
            
            if not text or not scheduled_date or not scheduled_time:
                flash('Заполните все поля', 'error')
                return redirect(url_for('create_task'))
            
            # Парсим дату и время (предполагаем UTC)
            scheduled_datetime = datetime.strptime(
                f"{scheduled_date} {scheduled_time}",
                "%Y-%m-%d %H:%M"
            )
            # Явно указываем, что это UTC время (naive datetime будет интерпретирован как UTC)
            
            task = Task(
                text=text,
                scheduled_time=scheduled_datetime,
                is_active=True
            )
            db.add(task)
            db.commit()
            
            flash('Задание создано успешно', 'success')
            return redirect(url_for('tasks'))
        finally:
            db.close()
    
    return render_template('create_task.html')


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            flash('Задание не найдено', 'error')
            return redirect(url_for('tasks'))
        
        if request.method == 'POST':
            task.text = request.form.get('text')
            scheduled_date = request.form.get('scheduled_date')
            scheduled_time = request.form.get('scheduled_time')
            
            if scheduled_date and scheduled_time:
                task.scheduled_time = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}",
                    "%Y-%m-%d %H:%M"
                )
            
            task.is_active = request.form.get('is_active') == 'on'
            db.commit()
            
            flash('Задание обновлено', 'success')
            return redirect(url_for('tasks'))
        
        return render_template('edit_task.html', task=task)
    finally:
        db.close()


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.is_active = False
            db.commit()
            flash('Задание деактивировано', 'success')
        return redirect(url_for('tasks'))
    finally:
        db.close()


@app.route('/moderation')
@login_required
def moderation():
    db = SessionLocal()
    try:
        # Посты на модерации
        moderation_posts = db.query(Post).filter(
            Post.status == PostStatus.MODERATION
        ).order_by(Post.complaints_count.desc(), Post.created_at.desc()).all()
        
        # Посты с жалобами (но еще не на модерации)
        complaint_posts = db.query(Post).filter(
            Post.complaints_count > 0,
            Post.status != PostStatus.MODERATION,
            Post.status != PostStatus.DELETED
        ).order_by(Post.complaints_count.desc()).all()
        
        return render_template('moderation.html',
                             moderation_posts=moderation_posts,
                             complaint_posts=complaint_posts)
    finally:
        db.close()


@app.route('/media/<file_id>')
@login_required
def get_media(file_id):
    """Получение медиа файла из Telegram по file_id"""
    from flask import Response
    try:
        # Получаем информацию о файле через Telegram Bot API
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile"
        response = requests.get(url, params={'file_id': file_id}, timeout=10)
        response.raise_for_status()
        
        file_info = response.json()
        if not file_info.get('ok'):
            return "Файл не найден", 404
        
        file_path = file_info['result']['file_path']
        
        # Получаем файл из Telegram
        telegram_file_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
        file_response = requests.get(telegram_file_url, stream=True, timeout=30)
        file_response.raise_for_status()
        
        # Определяем content-type
        content_type = 'image/jpeg'  # По умолчанию
        if file_path.endswith('.mp4') or file_path.endswith('.mov'):
            content_type = 'video/mp4'
        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif file_path.endswith('.png'):
            content_type = 'image/png'
        elif file_path.endswith('.gif'):
            content_type = 'image/gif'
        
        # Проксируем файл через админку
        return Response(
            file_response.iter_content(chunk_size=8192),
            content_type=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{file_path.split("/")[-1]}"',
                'Cache-Control': 'public, max-age=3600'
            }
        )
    except Exception as e:
        print(f"Ошибка получения медиа: {e}")
        return f"Ошибка загрузки медиа: {str(e)}", 500


@app.route('/moderation/<int:post_id>')
@login_required
def moderation_post(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            flash('Пост не найден', 'error')
            return redirect(url_for('moderation'))
        
        complaints = db.query(Complaint).filter(Complaint.post_id == post_id).all()
        
        return render_template('moderation_post.html', post=post, complaints=complaints, bot_token=config.TELEGRAM_BOT_TOKEN)
    finally:
        db.close()


@app.route('/moderation/<int:post_id>/approve', methods=['POST'])
@login_required
def approve_post(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.status = PostStatus.APPROVED
            post.complaints_count = 0
            # Удаляем жалобы
            db.query(Complaint).filter(Complaint.post_id == post_id).delete()
            db.commit()
            flash('Пост одобрен', 'success')
        return redirect(url_for('moderation'))
    finally:
        db.close()


@app.route('/moderation/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.status = PostStatus.DELETED
            db.commit()
            flash('Пост удален', 'success')
        return redirect(url_for('moderation'))
    finally:
        db.close()


@app.route('/moderation/<int:post_id>/sanction', methods=['POST'])
@login_required
def sanction_user(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            flash('Пост не найден', 'error')
            return redirect(url_for('moderation'))
        
        sanction_type = request.form.get('sanction_type')
        reason = request.form.get('reason', '')
        
        if sanction_type == 'day_ban':
            expires_at = datetime.utcnow() + timedelta(days=1)
        elif sanction_type == 'session_ban':
            expires_at = datetime.utcnow() + timedelta(days=7)
        else:
            expires_at = None  # Постоянный бан
        
        sanction = Sanction(
            user_id=post.author_id,
            sanction_type=SanctionType(sanction_type),
            reason=reason,
            expires_at=expires_at
        )
        db.add(sanction)
        
        post.status = PostStatus.DELETED
        db.commit()
        
        flash('Санкция применена', 'success')
        return redirect(url_for('moderation'))
    finally:
        db.close()


@app.route('/posts')
@login_required
def posts():
    db = SessionLocal()
    try:
        status_filter = request.args.get('status')
        
        query = db.query(Post).join(User).join(Task).order_by(Post.created_at.desc())
        
        if status_filter:
            try:
                status = PostStatus(status_filter)
                query = query.filter(Post.status == status)
            except ValueError:
                pass
        
        all_posts = query.all()
        return render_template('posts.html', posts=all_posts)
    finally:
        db.close()


@app.route('/posts/<int:post_id>')
@login_required
def view_post(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            flash('Материал не найден', 'error')
            return redirect(url_for('posts'))
        
        # Получаем URL медиа для отображения
        media_url = url_for('get_media', file_id=post.media_file_id)
        return render_template('view_post.html', post=post, bot_token=config.TELEGRAM_BOT_TOKEN, media_url=media_url)
    finally:
        db.close()


def send_telegram_message(chat_id, text, reply_markup=None):
    """Отправка сообщения пользователю через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        data['reply_markup'] = reply_markup
    
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Ошибка отправки сообщения в Telegram: {e}")
        return False


@app.route('/posts/<int:post_id>/reject', methods=['POST'])
@login_required
def reject_post(post_id):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            flash('Материал не найден', 'error')
            return redirect(url_for('posts'))
        
        if post.status != PostStatus.PENDING:
            flash('Можно отклонять только материалы со статусом "Ожидает"', 'error')
            return redirect(url_for('view_post', post_id=post_id))
        
        # Меняем статус на REJECTED
        post.status = PostStatus.REJECTED
        db.commit()
        
        # Отправляем уведомление пользователю
        import json
        
        # Формируем inline keyboard для Telegram API
        keyboard = {
            "inline_keyboard": [
                [{"text": "📤 Прислать новый материал", "callback_data": f"resubmit:{post.task_id}"}]
            ]
        }
        reply_markup_json = json.dumps(keyboard)
        
        message_text = (
            f"❌ <b>Материал не подошел</b>\n\n"
            f"Твой материал по заданию \"{post.task.text[:50]}{'...' if len(post.task.text) > 50 else ''}\" был отклонен модератором.\n\n"
            f"Пожалуйста, пришли новый материал, соответствующий заданию."
        )
        
        success = send_telegram_message(
            post.author.telegram_id,
            message_text,
            reply_markup_json
        )
        
        if success:
            flash('Материал отклонен. Пользователю отправлено уведомление.', 'success')
        else:
            flash('Материал отклонен, но не удалось отправить уведомление пользователю.', 'warning')
        
        return redirect(url_for('view_post', post_id=post_id))
    finally:
        db.close()


@app.route('/users')
@login_required
def users():
    db = SessionLocal()
    try:
        all_users = db.query(User).order_by(User.created_at.desc()).all()
        return render_template('users.html', users=all_users)
    finally:
        db.close()


@app.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = not user.is_active
            db.commit()
            flash(f'Пользователь {"активирован" if user.is_active else "деактивирован"}', 'success')
        return redirect(url_for('users'))
    finally:
        db.close()


@app.route('/api/stats')
@login_required
def api_stats():
    db = SessionLocal()
    try:
        stats = {
            'total_users': db.query(User).count(),
            'active_users': db.query(User).filter(User.is_active == True).count(),
            'total_posts': db.query(Post).count(),
            'pending_posts': db.query(Post).filter(Post.status == PostStatus.PENDING).count(),
            'moderation_posts': db.query(Post).filter(Post.status == PostStatus.MODERATION).count(),
        }
        return jsonify(stats)
    finally:
        db.close()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)

