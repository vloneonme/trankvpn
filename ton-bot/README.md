# VPN Telegram Bot

Автоматизированный Telegram бот для управления VPN подписками через Marzban API с интеграцией CryptoBot для приема платежей.

## 🎯 Возможности

- **Тестовая подписка**: 3 дня, 5 GB (один раз на пользователя)
- **Basic тариф**: 30 дней, 50 GB за 290₽
- **Premium тариф**: 90 дней, 200 GB за 790₽
- **Прием платежей**: CryptoBot (TON, USDT)
- **Асинхронная база данных**: MySQL/MariaDB с aiomysql
- **Логирование**: Полное логирование всех операций
- **Обработка ошибок**: Надежная обработка исключений

## 📋 Требования

- Python 3.10+
- MySQL/MariaDB
- Marzban VPN server
- CryptoBot API токен
- Telegram Bot API токен

## 🚀 Установка

### 1. Клонирование/подготовка

```bash
cd /opt/ton-bot
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Конфигурация

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
nano .env
```

### 4. Создание лог-директории

```bash
mkdir -p /var/log/bot
```

## 🔧 Конфигурация (.env)

```
# Telegram
BOT_TOKEN=<ваш_токен_телеграм_бота>

# CryptoBot для платежей
CRYPTO_BOT_TOKEN=<токен_cryptobot>

# Marzban API
MARZBAN_URL=http://localhost:8000
MARZBAN_USER=admin
MARZBAN_PASS=<пароль>

# Подписки
SUBSCRIPTION_URL=https://trankvpn.uk
INBOUND_TAG=VLESS TCP REALITY

# База данных
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=marzban
DB_PASS=<пароль>
DB_NAME=marzban
```

## 📦 Docker (рекомендуется)

Бот уже настроен в `docker-compose.yml`. Для запуска:

```bash
cd /home/vlone/trankvpn
docker-compose up -d
```

Логи бота:
```bash
docker-compose logs -f bot
```

## 🗄️ База данных

Таблица автоматически создается при запуске:

```sql
CREATE TABLE bot_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    used_test TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
```

## 📊 Логирование

Логи записываются в `/var/log/bot/bot.log` и выводятся в stdout.

Формат: `2026-05-04 12:34:56,789 - bot - INFO - Сообщение`

### Основные события логирования:
- ✅ Успешные операции (подключение БД, создание пользователя, платежи)
- ❌ Ошибки (проблемы с API, БД)
- 📊 События пользователей (команды, платежи, проверки)
- ⚠️ Предупреждения (попытки повторного использования теста)

## 🔐 Обработка ошибок

Все критические операции имеют:
- Try-catch блоки
- Логирование исключений
- Graceful fallback сообщения

## 🎮 Команды бота

- `/start` - Главное меню
- Кнопка "Купить подписку" - Выбор тарифа
- Кнопка "Тестовый период" - Получить тест (один раз)
- Кнопка "О сервисе" - Информация

## 🐛 Исправленные ошибки

- ✅ Синтаксические ошибки (удалены `[3]`, `[4]` и т.д.)
- ✅ Логика БД (исправлена проверка `used_test`)
- ✅ Парсинг данных callback (`split("_")[1]` вместо `[9]`)
- ✅ Обработка платежей (`invoices[0].status`)
- ✅ Возврат в меню (правильное использование callback.message)
- ✅ Добавлено комплексное логирование
- ✅ Улучшена обработка исключений
- ✅ Добавлена валидация входных данных

## 🚨 Запуск вручную (для тестирования)

```bash
python bot.py
```

## 📝 Важно

- Убедитесь, что Marzban работает и доступен по URL в .env
- Проверьте доступ к MySQL на 127.0.0.1:3306
- Убедитесь, что директория `/var/log/bot` существует и имеет права на запись
- Используйте актуальный CryptoBot токен

## 🆘 Отладка

Для отладки проверьте:
1. Логи: `tail -f /var/log/bot/bot.log`
2. Доступность Marzban: `curl http://localhost:8000/api/admin/token`
3. Подключение БД: `mysql -h 127.0.0.1 -u marzban -p marzban`
4. Docker контейнер: `docker-compose ps`

## 📄 Лицензия

Для внутреннего использования
