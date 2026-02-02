# Telegram Social Bot - ShotShare

Telegram-бот для обмена контентом между пользователями по ежедневным заданиям.

## Возможности

- Регистрация пользователей с опциональной привязкой канала
- Ежедневные задания с автоматической рассылкой
- Загрузка фото/видео контента (до 10 секунд)
- Честное распределение постов (гарантированные показы)
- Случайные слоты для дополнительного интереса
- Система жалоб и модерации
- Проверка активности пользователей
- Веб-админка для управления заданиями и статистики

## Установка и запуск

### Требования

- Docker и Docker Compose
- Telegram Bot Token (получить у @BotFather)

### 1. Клонирование репозитория

```bash
git clone <repository_url>
cd ShotShare
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните необходимые значения:

```bash
cp .env.example .env
```

**Обязательно укажите:**
- `TELEGRAM_BOT_TOKEN` - токен вашего бота от @BotFather
- `ADMIN_USER_IDS` - ID администраторов через запятую (можно узнать у @userinfobot)
- `ADMIN_SECRET_KEY` - секретный ключ для Flask (сгенерируйте случайную строку)
- `ADMIN_PASSWORD` - пароль для входа в админку

**Пример генерации секретного ключа:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Запуск через Docker Compose

```bash
docker-compose up -d
```

Проверка логов:
```bash
docker-compose logs -f bot
docker-compose logs -f admin
```

### 4. Доступ к админке

Откройте в браузере: http://localhost:5000

**Логин:** значение из `ADMIN_USERNAME` (по умолчанию `admin`)  
**Пароль:** значение из `ADMIN_PASSWORD`

### 5. Остановка

```bash
docker-compose down
```

Для полной очистки (включая данные БД):
```bash
docker-compose down -v
```

## Структура проекта

```
ShotShare/
├── bot/              # Основной Telegram бот
├── admin/            # Веб-админка
├── database/         # Модели базы данных и миграции
├── media/            # Загруженные медиафайлы
├── docker-compose.yml
├── requirements.txt
└── config.py
```

## Разработка

### Локальная разработка без Docker

1. Установите PostgreSQL локально и создайте базу данных:
```sql
CREATE DATABASE shotshare_db;
CREATE USER shotshare WITH PASSWORD 'shotshare_password';
GRANT ALL PRIVILEGES ON DATABASE shotshare_db TO shotshare;
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте `.env` файл с локальным DATABASE_URL:
```
DATABASE_URL=postgresql://shotshare:shotshare_password@localhost:5432/shotshare_db
```

4. Инициализируйте базу данных:
```bash
python init_db.py
```

5. Запустите бота:
```bash
python -m bot.main
```

6. Запустите админку (в другом терминале):
```bash
python -m admin.app
```

## Структура базы данных

База данных автоматически создается при первом запуске через `init_db.py` или при применении миграций.

Основные таблицы:
- `users` - пользователи бота
- `tasks` - ежедневные задания
- `sessions` - сессии (дни активности)
- `posts` - загруженные посты
- `complaints` - жалобы на посты
- `post_views` - просмотры и взаимодействия
- `sanctions` - санкции к пользователям

## Первое использование

1. Запустите систему через Docker Compose
2. Войдите в админку
3. Создайте первое задание через раздел "Задания"
4. Начните использовать бота в Telegram - зарегистрируйтесь через `/register`
5. После создания задания бот автоматически отправит его всем активным пользователям в указанное время

## API документация

Админка доступна по адресу http://localhost:5000

Основные эндпоинты:
- `/` - главная страница со статистикой
- `/tasks` - управление заданиями
- `/moderation` - модерация постов с жалобами
- `/users` - список пользователей

## Лицензия

MIT

