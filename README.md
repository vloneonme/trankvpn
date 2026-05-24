# TrankVPN

Сервис продажи VPN-подписок через Telegram-бота. Приём оплаты в USDT/TON через [@CryptoBot](https://t.me/CryptoBot), автоматическая выдача подписок через панель [Marzban](https://github.com/Gozargah/Marzban), развёртывание через Docker Compose.

---

## Содержание

- [Как это работает](#как-это-работает)
- [Структура проекта](#структура-проекта)
- [Компоненты](#компоненты)
- [Telegram-бот: все функции](#telegram-бот-все-функции)
- [Система оплаты](#система-оплаты)
- [База данных](#база-данных)
- [Переменные окружения](#переменные-окружения)
- [Установка и запуск](#установка-и-запуск)
- [Ansible-деплой](#ansible-деплой)
- [Резервное копирование](#резервное-копирование)
- [Часто задаваемые вопросы](#часто-задаваемые-вопросы)

---

## Как это работает

```
Пользователь в Telegram
        │
        ▼
  Telegram Bot (aiogram 3)
        │
        ├── Бесплатный тест ──────────────► Marzban API ──► VPN-конфиг
        │
        ├── Купить/Продлить ──► CryptoBot ──► Пользователь оплачивает
        │                            │
        │                            ▼
        │                    Worker проверяет оплату (каждые 2 мин)
        │                            │
        │                            ▼
        └── Активация ───────────── Marzban API ──► VPN-конфиг ──► Уведомление
```

**Полный путь покупки:**
1. Пользователь выбирает тариф в боте
2. Бот создаёт инвойс в CryptoPay и отправляет ссылку
3. Пользователь оплачивает через @CryptoBot в USDT или TON
4. Пользователь нажимает «Я оплатил» **или** Worker автоматически обнаруживает оплату
5. Бот создаёт пользователя в Marzban и сохраняет ссылку подписки в БД
6. Пользователь получает ссылку, добавляет в приложение (v2rayNG, Hiddify и др.)

---

## Структура проекта

```
trankvpn/
├── bot/
│   ├── bot.py              # Telegram-бот (все хендлеры, логика)
│   ├── Dockerfile          # Образ бота
│   └── requirements.txt
│
├── web/
│   ├── main.py             # FastAPI лендинг + /health
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker/
│   ├── worker.py           # Фоновые задачи (платежи, уведомления, очистка)
│   ├── Dockerfile
│   └── requirements.txt
│
├── shared/                 # Общий код, используется всеми сервисами
│   ├── __init__.py
│   ├── database.py         # Асинхронный менеджер MariaDB (aiomysql)
│   ├── marzban.py          # HTTP-клиент Marzban API
│   ├── cryptopay.py        # HTTP-клиент CryptoPay API
│   └── crypto.py           # AES-256-GCM шифрование + HMAC токены
│
├── docker/
│   ├── docker-compose.yml  # Оркестрация всех сервисов
│   └── .env.example        # Шаблон переменных окружения
│
├── configs/
│   └── Caddyfile           # Конфигурация reverse-proxy (HTTPS, заголовки)
│
├── scripts/
│   └── backup.sh           # Скрипт резервного копирования БД + конфигов
│
└── ansible/
    └── deploy.yml          # Playbook для деплоя на чистый сервер
```

---

## Компоненты

### bot — Telegram-бот
**Стек:** Python 3.12, aiogram 3.x, aiomysql, httpx

Основной сервис. Принимает команды от пользователей, создаёт инвойсы, получает ссылки из Marzban, хранит подписки в БД.

При старте:
- Подключается к MariaDB и создаёт таблицы если их нет
- Проверяет токен CryptoPay (`/api/getMe`)
- Удаляет вебхук и запускает long polling

### web — Лендинг
**Стек:** Python 3.12, FastAPI, uvicorn

Простая HTML-страница с описанием сервиса и кнопкой «Открыть в Telegram». Доступна через Caddy по домену. Отдаёт `/health` для мониторинга.

### worker — Фоновые задачи
**Стек:** Python 3.12, aiomysql, httpx

Три параллельные задачи в одном процессе:

| Задача | Интервал | Что делает |
|--------|----------|-----------|
| `check_payments_task` | каждые 2 мин | Опрашивает CryptoPay на предмет оплаченных инвойсов, активирует подписки автоматически |
| `notify_expiring_task` | каждый час | Находит подписки с остатком < 24 часов, отправляет уведомление пользователю |
| `cleanup_task` | каждые 10 мин | Деактивирует просроченные подписки в БД, удаляет старые MTProto-записи |

### shared — Общие модули

**`database.py`** — пул соединений aiomysql, все SQL-запросы инкапсулированы в методы:
- `add_user`, `get_user`, `mark_test_used`
- `add_subscription`, `get_active_subscription`, `extend_subscription`
- `create_payment`, `get_payment_by_invoice`, `mark_payment_paid`, `get_pending_payments`
- `get_expiring_subscriptions`, `deactivate_expired_subscriptions`
- `get_users_count`, `get_active_subs_count`, `get_all_users`

**`marzban.py`** — клиент REST API Marzban:
- Авторизация и автообновление JWT-токена (раз в ~час)
- `create_user(telegram_id, plan, gb, days)` — создаёт пользователя с VLESS+VMess
- `extend_user(username, days)` — продлевает, учитывая текущий срок
- `get_user_traffic(username)` — использованный и лимитный трафик в ГБ
- При конфликте (пользователь уже есть) — обновляет через PUT вместо POST

**`cryptopay.py`** — клиент CryptoPay API:
- `create_invoice(amount, currency, payload, description)` — создаёт счёт
- `get_invoice(invoice_id)` — статус конкретного счёта
- `get_paid_invoices()` — все оплаченные счета (для воркера)
- `check_token()` — проверка что токен валиден при старте

**`crypto.py`** — утилиты шифрования:
- `encrypt_config` / `decrypt_config` — AES-256-GCM для хранения конфигов
- `generate_short_lived_token` / `verify_short_lived_token` — HMAC-SHA256 временные токены

### docker — инфраструктура

**docker-compose.yml** запускает 5 сервисов:

| Контейнер | Образ | Назначение |
|-----------|-------|-----------|
| `vpn-mariadb` | mariadb:lts | База данных |
| `vpn-redis` | redis:7-alpine | Кэш (зарезервировано под сессии) |
| `vpn-bot` | build | Telegram-бот |
| `vpn-web` | build | Лендинг, слушает 127.0.0.1:8080 |
| `vpn-worker` | build | Фоновые задачи |
| `vpn-caddy` | caddy:latest | HTTPS reverse-proxy, `network_mode: host` |

Данные хранятся в `/var/lib/vpn-service/` на хосте (mysql, redis, caddy).

> **Важно:** Build context всех образов — корень проекта (`..` от `docker/`), чтобы `shared/` был доступен внутри каждого контейнера.

---

## Telegram-бот: все функции

### Пользовательские команды

#### `/start`
Приветственное сообщение. Автоматически регистрирует пользователя в БД (`INSERT IGNORE`).
- Если есть активная подписка — показывает дату истечения и кнопку «Мой VPN»
- Если нет — показывает описание и кнопки «Попробовать бесплатно» и «Купить»

#### 🎁 Попробовать бесплатно
Тестовая подписка: **3 дня, 5 ГБ, бесплатно**.
- Проверяет флаг `used_test` — выдаётся только один раз
- Создаёт реального пользователя в Marzban
- Записывает подписку в БД

#### 💳 Купить подписку
Показывает три тарифа. При выборе платного:
1. Бот создаёт инвойс через CryptoPay API (USDT)
2. Сохраняет `invoice_id` в таблице `payments` со статусом `pending`
3. Отправляет кнопку «Оплатить в CryptoBot» (внешняя ссылка) и «Я оплатил» (колбэк)

#### ✅ Я оплатил (кнопка проверки)
Немедленно запрашивает статус инвойса у CryptoPay.
- Если `status == paid` — активирует подписку прямо сейчас
- Если нет — сообщает текущий статус (не оплачен / истёк)
- **Идемпотентно:** повторное нажатие не создаёт дублей

#### ⏱ Продлить подписку
Доступно только при наличии активной подписки. Показывает тарифы без «Тестового».
- При оплате: в Marzban продлевается `expire` (от текущего максимума), в БД обновляется дата

#### 🔌 Мой VPN
Показывает ссылку подписки (`subscription_url` из Marzban) в формате для копирования.
- Тариф, остаток дней, лимит трафика
- Кнопки: «Как подключиться?», «Статус», «Меню»

#### 📊 Статус
Полная информация о подписке:
- Тариф и лимит трафика
- Использованный трафик (запрос к Marzban API в реальном времени)
- Точная дата и время истечения
- При отсутствии подписки — предложение купить

#### 📱 Как подключиться?
Инструкция по приложениям для всех платформ:
- **Android:** v2rayNG, Hiddify
- **iOS:** Streisand, Hiddify
- **Windows:** Hiddify Next, Nekoray
- **Mac:** Hiddify Next, FoXray

### Административные команды

#### `/admin`
Доступно только пользователям из `ADMIN_IDS`.
Показывает:
- Общее количество пользователей
- Количество активных подписок

#### `/broadcast <текст>`
Рассылка сообщения всем пользователям из БД.
- Соблюдает rate limit (50 мс между сообщениями)
- По итогу сообщает сколько доставлено / ошибок

### Тарифы

| Тариф | Цена | Срок | Трафик |
|-------|------|------|--------|
| 🎁 Тестовый | Бесплатно | 3 дня | 5 ГБ |
| 📱 Базовый | 1.5 USDT | 30 дней | 100 ГБ |
| ♾️ Безлимит | 3.0 USDT | 30 дней | ∞ |

Тарифы задаются прямо в `bot/bot.py` в словаре `PLANS` — можно менять цены и условия без изменения логики.

---

## Система оплаты

### CryptoPay (@CryptoBot)

CryptoPay — официальный платёжный бот Telegram. Принимает USDT, TON, BTC и другие криптовалюты. Для подключения:
1. Напишите [@CryptoBot](https://t.me/CryptoBot) → `/pay` → Create App
2. Скопируйте API-токен в `CRYPTO_BOT_TOKEN`

**Поток оплаты:**

```
Бот создаёт инвойс
    │  CryptoPay возвращает invoice_id + pay_url
    ▼
Пользователь переходит по pay_url в @CryptoBot
    │  Оплачивает
    ▼
Два способа подтверждения (работают параллельно):
    ├── Пользователь нажимает «Я оплатил» → мгновенная проверка
    └── Worker опрашивает /getInvoices каждые 2 мин → авто-активация
```

**Идемпотентность:** перед активацией всегда проверяется `payment.status == 'paid'`. Дважды активировать нельзя.

**Payload инвойса** хранит всю нужную информацию: `{telegram_id}:{plan_id}:{action}` (например `123456789:basic:buy`). Это позволяет Worker'у активировать подписку без дополнительных запросов к БД.

---

## База данных

MariaDB, движок InnoDB, кодировка utf8mb4. Таблицы создаются автоматически при запуске бота и воркера.

### `bot_users`
| Поле | Тип | Описание |
|------|-----|---------|
| `telegram_id` | BIGINT UNIQUE | ID пользователя в Telegram |
| `username` | VARCHAR(255) | @username (может меняться) |
| `used_test` | TINYINT(1) | Флаг использования бесплатного теста |
| `balance` | DECIMAL(10,2) | Зарезервировано для будущего внутреннего баланса |
| `created_at` | TIMESTAMP | Дата регистрации |

### `subscriptions`
| Поле | Тип | Описание |
|------|-----|---------|
| `telegram_id` | BIGINT | Владелец подписки |
| `marzban_username` | VARCHAR(255) | Username в Marzban (`tg{id}_{plan}`) |
| `subscription_url` | TEXT | Ссылка для импорта в приложение |
| `plan_type` | ENUM | `test`, `basic`, `unlimited` |
| `data_limit_gb` | INT | Лимит ГБ (0 = безлимит) |
| `expire_at` | TIMESTAMP | Дата истечения |
| `is_active` | TINYINT(1) | 0 если деактивирована воркером |

### `payments`
| Поле | Тип | Описание |
|------|-----|---------|
| `invoice_id` | VARCHAR(100) UNIQUE | ID инвойса в CryptoPay |
| `amount` | DECIMAL(10,4) | Сумма (USDT) |
| `status` | ENUM | `pending`, `paid`, `expired`, `failed` |
| `plan_type` | VARCHAR(50) | Тариф |
| `action` | ENUM | `buy` или `extend` |
| `paid_at` | TIMESTAMP | Время подтверждения оплаты |

### `mtproto_proxies`
Зарезервировано для будущей функции временных MTProto-прокси (5 мин). Воркер чистит истёкшие записи каждые 10 минут.

---

## Переменные окружения

Файл: `docker/.env` (скопируйте из `docker/.env.example`)

### Обязательные

| Переменная | Где взять | Описание |
|-----------|-----------|---------|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → /newbot | Токен Telegram-бота |
| `CRYPTO_BOT_TOKEN` | [@CryptoBot](https://t.me/CryptoBot) → /pay → Create App | Токен приёма платежей |
| `DB_PASS` | Придумайте | Пароль пользователя БД |
| `MYSQL_ROOT_PASSWORD` | Придумайте | Пароль root MariaDB |
| `MARZBAN_URL` | URL вашей Marzban | Например: `http://1.2.3.4:8000` |
| `MARZBAN_ADMIN` | Логин в Marzban | Обычно `admin` |
| `MARZBAN_PASS` | Пароль в Marzban | Пароль от панели |
| `ENCRYPTION_KEY` | Генерация ниже | 32-байтный ключ в base64 |

### Опциональные

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `DB_NAME` | `vpn_service` | Имя базы данных |
| `DB_USER` | `vpn_user` | Пользователь БД |
| `DB_HOST` | `mariadb` | Хост БД (в Docker — имя контейнера) |
| `SUPPORT_USERNAME` | `support` | @username поддержки (без @) |
| `ADMIN_IDS` | *(пусто)* | Telegram ID администраторов через запятую |
| `BOT_USERNAME` | `TrankVPNbot` | Username бота (для лендинга) |
| `DOMAIN` | — | Ваш домен для Caddyfile |

### Генерация ENCRYPTION_KEY

```bash
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

---

## Установка и запуск

### Требования к серверу
- Ubuntu 22.04 / Debian 12
- 1 ГБ RAM минимум (рекомендуется 2 ГБ)
- Docker + Docker Compose
- Отдельно работающая панель Marzban (может быть на этом же или другом сервере)

### Шаг 1. Клонируйте репозиторий

```bash
git clone <ваш-репозиторий> /opt/trankvpn
cd /opt/trankvpn
```

### Шаг 2. Настройте переменные окружения

```bash
cp docker/.env.example docker/.env
nano docker/.env
```

Заполните как минимум: `BOT_TOKEN`, `CRYPTO_BOT_TOKEN`, `DB_PASS`, `MYSQL_ROOT_PASSWORD`, `MARZBAN_URL`, `MARZBAN_ADMIN`, `MARZBAN_PASS`, `ENCRYPTION_KEY`.

### Шаг 3. Настройте домен (опционально)

Откройте `configs/Caddyfile` и замените `your-domain.com` на ваш домен:

```
your-domain.com {
    reverse_proxy vpn-web:8080
    ...
}
```

Направьте A-запись домена на IP сервера. Caddy автоматически выпустит SSL-сертификат Let's Encrypt.

### Шаг 4. Создайте директории для данных

```bash
mkdir -p /var/lib/vpn-service/{mysql,redis,caddy,caddy-config}
mkdir -p /var/log/vpn-service/bot
```

### Шаг 5. Запустите

```bash
cd docker
docker compose up -d
```

### Шаг 6. Проверьте статус

```bash
# Статус всех контейнеров
docker compose ps

# Логи бота
docker compose logs -f bot

# Логи воркера
docker compose logs -f worker
```

### Шаг 7. Проверьте Marzban

В боте напишите `/start`. Нажмите «Попробовать бесплатно». Если в Marzban появился новый пользователь `tg{ваш_id}_test` — всё работает.

---

## Ansible-деплой

Для деплоя на чистый сервер одной командой:

```bash
# Установите Ansible
pip install ansible

# Создайте файл инвентаря
cat > inventory.ini << EOF
[vpn_servers]
1.2.3.4 ansible_user=root
EOF

# Запустите деплой
ansible-playbook -i inventory.ini ansible/deploy.yml \
  -e "repo_url=https://github.com/your/trankvpn.git" \
  -e "setup_backup=true"
```

Что делает playbook:
1. Устанавливает Docker, git, curl
2. Клонирует репозиторий в `/opt/vpn-service`
3. Генерирует `ENCRYPTION_KEY` через `openssl rand`
4. Создаёт необходимые директории
5. Запускает `docker compose up -d --build`
6. Настраивает cron для резервного копирования (если `setup_backup=true`)

> **Примечание:** Playbook использует шаблон `templates/env.j2` для генерации `.env`. Создайте его на основе `docker/.env.example` с переменными Ansible.

---

## Резервное копирование

Скрипт `scripts/backup.sh` сохраняет:
- Дамп MariaDB (`mysqldump`)
- Снимок Redis (`SAVE` → `dump.rdb`)
- Архив конфигов (`docker/.env` + `configs/`)

Хранит 7 последних бэкапов, старые удаляет. Запись в `/var/backups/vpn-service/`.

**Ручной запуск:**
```bash
MYSQL_ROOT_PASSWORD=ваш_пароль bash scripts/backup.sh
```

**Автоматический (cron каждый день в 3:00):**
```bash
echo "0 3 * * * root MYSQL_ROOT_PASSWORD=xxx /opt/trankvpn/scripts/backup.sh" \
  >> /etc/cron.d/trankvpn-backup
```

---

## Часто задаваемые вопросы

**Q: Пользователь оплатил, но подписка не активировалась**
A: Worker проверяет каждые 2 минуты — подождите до 2 мин. Если дольше — проверьте `docker compose logs worker` на ошибки. Убедитесь что `CRYPTO_BOT_TOKEN` валиден.

**Q: «Ошибка создания подписки» при тесте**
A: Бот не может достучаться до Marzban. Проверьте `MARZBAN_URL`, `MARZBAN_ADMIN`, `MARZBAN_PASS`. Убедитесь что Marzban доступен из контейнера `vpn-bot` (проверьте `docker exec vpn-bot curl $MARZBAN_URL`).

**Q: Как изменить цены?**
A: В `bot/bot.py`, словарь `PLANS`. Поменяйте `price_usdt`, `days`, `gb`, `desc`. После изменения: `docker compose up -d --build bot`.

**Q: Как добавить нового администратора?**
A: В `docker/.env` добавьте его Telegram ID в `ADMIN_IDS=123456789,987654321`. Перезапустите бот: `docker compose restart bot`.

**Q: Как посмотреть логи платежей?**
A: `docker compose logs worker | grep -E "invoice|payment|activated"` или запрос к БД:
```sql
SELECT * FROM payments ORDER BY created_at DESC LIMIT 20;
```

**Q: Можно ли добавить рублёвую оплату?**
A: Да — через Telegram Stars (`InputInvoiceMessageContent`) или Юкассу (нужен доп. модуль). CryptoPay — самый простой вариант без юридических сложностей.

**Q: Что будет при перезапуске если пользователь уже есть в Marzban?**
A: `marzban.py` обрабатывает HTTP 409 (Conflict) — вместо создания обновляет существующего пользователя через PUT.

**Q: Как масштабировать на несколько серверов?**
A: Запустите несколько инстансов Marzban, добавьте балансировку на уровне Marzban API. Бот и воркер работают с одной БД — можно поднять несколько реплик бота (они stateless).
