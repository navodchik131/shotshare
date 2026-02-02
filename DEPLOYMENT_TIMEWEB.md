# Развертывание на Timeweb Cloud (существующий сервер)

## Ваша ситуация:
- **Сервер**: Timeweb Cloud (5.44.47.67)
- **Уже работает**: Docker + Portainer (порт 9443) + WireGuard
- **Нужно**: Добавить ShotShare Bot без конфликтов

## ✅ Безопасная стратегия:

### 1. Отдельные порты
- Админка: `5001` (вместо 5000)
- PostgreSQL: `5433` (внешний, если нужен доступ)
- Бот: не требует портов (polling)

### 2. Отдельные имена контейнеров
- `shotshare_db`, `shotshare_bot`, `shotshare_admin` (уже есть префикс)

### 3. Отдельные volumes
- `shotshare_postgres_data` (переименован)

---

## Пошаговая инструкция:

### Шаг 1: Подключение к серверу

```bash
ssh root@5.44.47.67
# или через ваш способ подключения
```

### Шаг 2: Проверка текущих контейнеров

```bash
# Проверить запущенные контейнеры
docker ps

# Проверить все контейнеры (включая остановленные)
docker ps -a

# Проверить занятые порты
netstat -tulpn | grep LISTEN
# или
ss -tulpn | grep LISTEN
```

### Шаг 3: Создание директории для проекта

```bash
# Создать отдельную директорию для проекта
mkdir -p /opt/shotshare
cd /opt/shotshare
```

### Шаг 4: Загрузка проекта на сервер

**Вариант A: Через Git (если есть репозиторий)**
```bash
git clone <your-repo-url> .
```

**Вариант B: Через SCP (с вашего ПК)**
```bash
# На вашем ПК
scp -r B:\work\ShotShare root@5.44.47.67:/opt/shotshare/
```

**Вариант C: Через SFTP/FTP клиент**

### Шаг 5: Настройка .env файла

```bash
cd /opt/shotshare
cp .env.example .env
nano .env  # или vi .env
```

**Важно изменить:**
```env
# Telegram
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# Database (внутренний порт остается 5432, внешний 5433)
DATABASE_URL=postgresql://shotshare:shotshare_password@db:5432/shotshare_db

# Admin Panel
ADMIN_SECRET_KEY=сгенерируйте_случайную_строку
ADMIN_USERNAME=admin
ADMIN_PASSWORD=сильный_пароль

# Admin User IDs (ваш Telegram ID)
ADMIN_USER_IDS=ваш_telegram_id
```

### Шаг 6: Проверка docker-compose.yml

Убедитесь, что в `docker-compose.yml`:
- Порт админки: `5001:5000`
- Порт PostgreSQL: `5433:5432` (если нужен внешний доступ)
- Volume: `shotshare_postgres_data`

### Шаг 7: Запуск проекта

```bash
cd /opt/shotshare

# Собрать и запустить
docker-compose up -d

# Проверить логи
docker-compose logs -f bot
docker-compose logs -f admin
```

### Шаг 8: Проверка работы

**Проверить контейнеры:**
```bash
docker ps | grep shotshare
```

**Проверить админку:**
Откройте в браузере: `http://5.44.47.67:5001`

**Проверить бота:**
Отправьте `/start` боту в Telegram

---

## Важные моменты:

### ✅ Безопасность:

1. **Firewall:**
   ```bash
   # Открыть только нужные порты
   ufw allow 5001/tcp  # Админка
   # PostgreSQL (5433) лучше не открывать в интернет, доступ только внутри Docker сети
   ```

2. **Сильный пароль для админки:**
   - Используйте сложный пароль в `.env`
   - Не используйте пароль по умолчанию

3. **Доступ к админке:**
   - Можно ограничить доступ по IP через firewall
   - Или использовать VPN (WireGuard уже настроен)

### ⚠️ Что НЕ будет конфликтовать:

- ✅ Portainer (порт 9443) - другой порт
- ✅ WireGuard - работает на других портах
- ✅ Другие Docker контейнеры - отдельные имена
- ✅ PostgreSQL - если есть другой, он на другом порту

### 📋 Проверка после запуска:

```bash
# Все контейнеры запущены
docker ps

# Логи без ошибок
docker-compose logs bot | tail -20
docker-compose logs admin | tail -20

# Админка отвечает
curl http://localhost:5001
```

---

## Если что-то пошло не так:

### Остановить проект:
```bash
cd /opt/shotshare
docker-compose down
```

### Перезапустить:
```bash
docker-compose restart
```

### Посмотреть логи:
```bash
docker-compose logs -f
```

### Удалить все (если нужно начать заново):
```bash
docker-compose down -v  # Удалит и volumes
```

---

## Итоговые адреса:

- **Админка**: `http://5.44.47.67:5001`
- **Portainer**: `https://5.44.47.67:9443` (как было)
- **WireGuard**: работает как раньше
- **Бот**: работает через Telegram (polling)

---

## Дополнительные рекомендации:

1. **Мониторинг:**
   - Настроить логирование
   - Проверять использование ресурсов

2. **Бэкапы:**
   - Настроить автоматические бэкапы базы данных
   - Бэкапы volumes

3. **Обновления:**
   - Регулярно обновлять зависимости
   - Следить за безопасностью

