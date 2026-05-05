# 🚀 VPN Service - Полная инструкция по развертыванию

## 📋 Структура проекта

```
vpn-service/
├── bot/              # Telegram бот
├── web/              # Web-приложение для MTProto
├── worker/           # Фоновые задачи
├── shared/           # Общие модули (шифрование, БД)
├── docker/           # Docker Compose конфигурация
├── ansible/          # Playbook для автоматизации
├── configs/          # Конфигурации (Caddy и др.)
└── scripts/          # Скрипты обслуживания
```

## 🔧 Быстрый старт (локально)

### 1. Клонирование и настройка

```bash
cd /opt
git clone <your-repo-url> vpn-service
cd vpn-service/docker

# Скопируйте пример .env и заполните его
cp .env.example .env
nano .env  # Отредактируйте переменные
```

### 2. Запуск всех сервисов

```bash
docker compose up -d --build
```

### 3. Проверка статуса

```bash
docker compose ps
docker compose logs -f bot
```

## 🌐 Развертывание на сервере через Ansible

### Требования
- Ubuntu 22.04+ на целевом сервере
- Ansible на машине управления
- SSH доступ к серверу

### 1. Настройка inventory

Создайте файл `ansible/inventory.ini`:
```ini
[vpn_servers]
your.server.ip ansible_user=root ansible_ssh_private_key_file=~/.ssh/id_rsa
```

### 2. Запуск playbook

```bash
cd ansible
ansible-playbook -i inventory.ini deploy.yml \
  -e "repo_url=https://github.com/yourusername/vpn-service.git"
```

## 🔐 Генерация ключей

```bash
# Ключ шифрования
openssl rand -base64 32

# Пароли для БД
openssl rand -base64 24
```

## 📊 Мониторинг

### Логи
```bash
# Бот
docker logs -f vpn-bot

# Web
docker logs -f vpn-web

# Worker
docker logs -f vpn-worker
```

### Статус сервисов
```bash
docker compose ps
docker stats
```

## 🔄 Обновление

```bash
cd /opt/vpn-service
git pull
docker compose up -d --build
```

## 💾 Резервное копирование

Автоматический бэкап настроен через cron (ежедневно в 3:00):
```bash
/opt/vpn-service/scripts/backup.sh
```

Ручной бэкап:
```bash
./scripts/backup.sh
```

Восстановление из бэкапа:
```bash
# БД
cat backup.sql | docker exec -i vpn-mariadb mysql -u root -pPASSWORD vpn_service
```

## 🛡 Безопасность

1. **Шифрование**: Все подписки шифруются AES-256-GCM
2. **Временные прокси**: MTProto действует 5 минут
3. **Привязка**: Подписки привязаны к device fingerprint
4. **Минимализм**: Пользователь видит только кнопку подключения

## 📱 Интеграция с CryptoBot

1. Получите токен в [@CryptoBot](https://t.me/CryptoBot)
2. Добавьте в `.env`: `CRYPTO_BOT_TOKEN=ваш_токен`
3. Реализуйте обработку webhook в боте

## 🎯 Массовое использование

### Масштабирование
- Добавьте балансировщик нагрузки (HAProxy/Nginx)
- Репликация MariaDB (master-slave)
- Redis Cluster для сессий

### Производительность
- Кэширование часто запрашиваемых данных
- Connection pooling для БД
- Асинхронные операции везде

## 🆘 Troubleshooting

### Бот не запускается
```bash
docker compose logs bot
# Проверьте BOT_TOKEN в .env
```

### Ошибка подключения к БД
```bash
docker compose exec mariadb mysql -u root -p
# Проверьте учетные данные
```

### MTProto не работает
```bash
# Проверьте наличие активного сервера MTProto
# Настройте интеграцию в web/main.py
```

## 📞 Поддержка

Создайте issue в репозитории или обратитесь к разработчику.
