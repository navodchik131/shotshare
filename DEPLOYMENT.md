# Инструкция по развертыванию ShotShare Bot

## Подготовка к развертыванию

### 1. Системные требования

- Docker 20.10+
- Docker Compose 2.0+
- Минимум 2GB свободной RAM
- Минимум 5GB свободного места на диске

### 2. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

**Критически важные параметры:**

```env
# Обязательно измените!
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_USER_IDS=ваш_telegram_id,id_другого_админа
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку_32_символа
ADMIN_PASSWORD=надежный_пароль_для_админки

# Можно оставить по умолчанию или настроить под себя
DATABASE_URL=postgresql://shotshare:shotshare_password@db:5432/shotshare_db
DAILY_TASK_TIME=09:00
CONTENT_SUBMISSION_DEADLINE=18:00
POSTS_PER_USER=5
FAIR_SLOTS_PER_AUTHOR=2
RANDOM_SLOTS_COUNT=3
COMPLAINTS_THRESHOLD=3
ACTIVITY_CHECK_TIME=08:00
INACTIVE_DAYS_THRESHOLD=3
```

### 3. Генерация секретного ключа

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Скопируйте результат в `ADMIN_SECRET_KEY`.

## Развертывание

### Вариант 1: Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

### Вариант 2: Пошаговый запуск

```bash
# 1. Запуск базы данных
docker-compose up -d db

# 2. Ожидание готовности БД (10-15 секунд)
sleep 15

# 3. Запуск бота
docker-compose up -d bot

# 4. Запуск админки
docker-compose up -d admin
```

## Проверка работоспособности

### 1. Проверка контейнеров

```bash
docker-compose ps
```

Все сервисы должны быть в статусе "Up".

### 2. Проверка логов

```bash
# Логи бота
docker-compose logs bot

# Логи админки
docker-compose logs admin

# Логи базы данных
docker-compose logs db
```

### 3. Проверка админки

Откройте в браузере: http://localhost:5000

Должна открыться страница входа.

### 4. Проверка бота

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Бот должен ответить приветствием

## Первоначальная настройка

### 1. Вход в админку

- URL: http://localhost:5000
- Логин: `admin` (или значение из `ADMIN_USERNAME`)
- Пароль: значение из `ADMIN_PASSWORD`

### 2. Создание первого задания

1. Перейдите в раздел "Задания"
2. Нажмите "Создать задание"
3. Заполните форму:
   - Текст задания
   - Дата и время отправки
4. Сохраните

### 3. Тестирование регистрации

1. В Telegram отправьте боту `/register`
2. Следуйте инструкциям
3. После регистрации вы должны получить подтверждение

## Мониторинг и обслуживание

### Просмотр статистики

В админке на главной странице отображается:
- Количество пользователей
- Количество постов
- Посты на модерации
- Активные задания

### Резервное копирование базы данных

```bash
# Создание бэкапа
docker-compose exec db pg_dump -U shotshare shotshare_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из бэкапа
docker-compose exec -T db psql -U shotshare shotshare_db < backup_file.sql
```

### Обновление

```bash
# Остановка сервисов
docker-compose down

# Обновление кода (если используете git)
git pull

# Пересборка образов
docker-compose build

# Запуск
docker-compose up -d
```

### Очистка

```bash
# Остановка и удаление контейнеров
docker-compose down

# Удаление с данными БД (ОСТОРОЖНО!)
docker-compose down -v

# Очистка неиспользуемых образов
docker system prune -a
```

## Устранение неполадок

### Бот не отвечает

1. Проверьте токен в `.env`
2. Проверьте логи: `docker-compose logs bot`
3. Убедитесь, что бот не заблокирован в Telegram

### Админка не открывается

1. Проверьте, что контейнер запущен: `docker-compose ps`
2. Проверьте логи: `docker-compose logs admin`
3. Проверьте, что порт 5000 не занят другим приложением

### Ошибки базы данных

1. Проверьте логи БД: `docker-compose logs db`
2. Убедитесь, что БД запущена: `docker-compose ps db`
3. Попробуйте перезапустить: `docker-compose restart db`

### Посты не распределяются

1. Проверьте, что дедлайн прошел
2. Проверьте логи бота на наличие ошибок
3. Убедитесь, что есть одобренные посты в базе

## Безопасность

### Рекомендации для production

1. **Измените пароли БД** в `docker-compose.yml` и `.env`
2. **Используйте сильный `ADMIN_SECRET_KEY`**
3. **Используйте сильный `ADMIN_PASSWORD`**
4. **Ограничьте доступ к админке** (firewall, VPN)
5. **Настройте SSL** для админки (через reverse proxy)
6. **Регулярно делайте бэкапы** базы данных
7. **Обновляйте зависимости** регулярно

### Настройка reverse proxy (nginx)

Пример конфигурации для nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Масштабирование

Для увеличения нагрузки можно:

1. **Увеличить ресурсы контейнеров** в `docker-compose.yml`
2. **Использовать внешнюю БД** (изменить `DATABASE_URL`)
3. **Добавить несколько инстансов бота** (с балансировкой)
4. **Использовать Redis** для кэширования

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs`
2. Проверьте документацию в `README.md`
3. Проверьте `QUICKSTART.md` для базовой настройки

