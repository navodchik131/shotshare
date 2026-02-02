import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://shotshare:shotshare_password@db:5432/shotshare_db')

# Admin Panel
ADMIN_SECRET_KEY = os.getenv('ADMIN_SECRET_KEY', 'dev-secret-key-change-in-production')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

# Bot Settings
ADMIN_USER_IDS = [int(uid.strip()) for uid in os.getenv('ADMIN_USER_IDS', '').split(',') if uid.strip()]
DAILY_TASK_TIME = os.getenv('DAILY_TASK_TIME', '09:00')
CONTENT_SUBMISSION_DEADLINE = os.getenv('CONTENT_SUBMISSION_DEADLINE', '18:00')  # Устаревшее, используется только если TASK_COMPLETION_MINUTES не задано
TASK_COMPLETION_MINUTES = int(os.getenv('TASK_COMPLETION_MINUTES', '10'))  # Время на выполнение задания в минутах
POSTS_PER_USER = int(os.getenv('POSTS_PER_USER', '5'))
FAIR_SLOTS_PER_AUTHOR = int(os.getenv('FAIR_SLOTS_PER_AUTHOR', '2'))
RANDOM_SLOTS_COUNT = int(os.getenv('RANDOM_SLOTS_COUNT', '3'))

# Moderation
COMPLAINTS_THRESHOLD = int(os.getenv('COMPLAINTS_THRESHOLD', '3'))
WARNINGS_BEFORE_BAN = int(os.getenv('WARNINGS_BEFORE_BAN', '3'))  # Количество предупреждений перед автоматическим баном

# Activity Check
ACTIVITY_CHECK_TIME = os.getenv('ACTIVITY_CHECK_TIME', '08:00')
INACTIVE_DAYS_THRESHOLD = int(os.getenv('INACTIVE_DAYS_THRESHOLD', '3'))

# Media
MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'media')
os.makedirs(MEDIA_DIR, exist_ok=True)

