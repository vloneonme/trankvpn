#!/bin/bash
# Скрипт для проверки конфигурации VPN бота

echo "🔍 Проверка конфигурации VPN бота"
echo "=================================="

# Проверка Python
echo "1️⃣  Python версия:"
python3 --version

# Проверка зависимостей
echo -e "\n2️⃣  Проверка зависимостей:"
python3 -c "import aiogram; print('✅ aiogram установлен')" 2>/dev/null || echo "❌ aiogram не установлен"
python3 -c "import aiomysql; print('✅ aiomysql установлен')" 2>/dev/null || echo "❌ aiomysql не установлен"
python3 -c "import httpx; print('✅ httpx установлен')" 2>/dev/null || echo "❌ httpx не установлен"
python3 -c "import aiocryptopay; print('✅ aiocryptopay установлен')" 2>/dev/null || echo "❌ aiocryptopay не установлен"

# Проверка MySQL
echo -e "\n3️⃣  Проверка MySQL:"
if command -v mysql &> /dev/null; then
    echo "✅ MySQL клиент установлен"
else
    echo "⚠️  MySQL клиент не установлен (рекомендуется установить)"
fi

# Проверка лог-директории
echo -e "\n4️⃣  Проверка лог-директории:"
if [ -d "/var/log/bot" ]; then
    echo "✅ Директория /var/log/bot существует"
else
    echo "⚠️  Директория /var/log/bot не существует (создаю...)"
    sudo mkdir -p /var/log/bot
    sudo chmod 755 /var/log/bot
fi

# Проверка .env файла
echo -e "\n5️⃣  Проверка .env файла:"
if [ -f ".env" ]; then
    echo "✅ Файл .env существует"
    
    # Проверка обязательных переменных
    required_vars=("BOT_TOKEN" "CRYPTO_BOT_TOKEN" "MARZBAN_URL" "MARZBAN_USER" "MARZBAN_PASS")
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env; then
            value=$(grep "^${var}=" .env | cut -d'=' -f2)
            if [ -n "$value" ] && [ "$value" != "your_*" ]; then
                echo "✅ $var установлена"
            else
                echo "❌ $var не установлена или имеет значение по умолчанию"
            fi
        else
            echo "❌ $var отсутствует в .env"
        fi
    done
else
    echo "❌ Файл .env не найден (скопируйте из .env.example)"
fi

# Проверка Marzban доступности
echo -e "\n6️⃣  Проверка доступности Marzban:"
MARZBAN_URL=$(grep "MARZBAN_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
if [ -n "$MARZBAN_URL" ]; then
    if timeout 5 curl -s "$MARZBAN_URL" > /dev/null 2>&1; then
        echo "✅ Marzban доступен по адресу $MARZBAN_URL"
    else
        echo "❌ Marzban не доступен по адресу $MARZBAN_URL (проверьте URL и сеть)"
    fi
else
    echo "⚠️  MARZBAN_URL не установлена в .env"
fi

# Проверка MySQL доступности
echo -e "\n7️⃣  Проверка доступности MySQL:"
DB_HOST=$(grep "DB_HOST=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
DB_USER=$(grep "DB_USER=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
DB_PASS=$(grep "DB_PASS=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')

if [ -z "$DB_HOST" ]; then DB_HOST="127.0.0.1"; fi
if [ -z "$DB_USER" ]; then DB_USER="marzban"; fi

if command -v mysql &> /dev/null; then
    if mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "SELECT 1" > /dev/null 2>&1; then
        echo "✅ MySQL доступен на $DB_HOST"
    else
        echo "❌ MySQL не доступен на $DB_HOST (проверьте учетные данные)"
    fi
else
    echo "⚠️  MySQL клиент не установлен (не могу проверить доступность)"
fi

# Проверка Dockerfile
echo -e "\n8️⃣  Проверка Docker:"
if [ -f "Dockerfile" ]; then
    echo "✅ Dockerfile существует"
else
    echo "❌ Dockerfile не найден"
fi

echo -e "\n✅ Проверка завершена!"
echo "=================================="
