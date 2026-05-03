#!/bin/bash
# Скрипт для развертывания VPN бота

set -e

echo "🚀 Развертывание VPN бота"
echo "=========================="

# Проверка, что мы в правильной директории
if [ ! -f "bot.py" ]; then
    echo "❌ Ошибка: bot.py не найден. Запустите скрипт из директории с ботом"
    exit 1
fi

# Шаг 1: Создание .env файла
if [ ! -f ".env" ]; then
    echo "📝 Создание .env файла из .env.example..."
    cp .env.example .env
    echo "⚠️  ВНИМАНИЕ: Отредактируйте .env файл с вашими параметрами!"
    echo "Пример: nano .env"
    exit 1
else
    echo "✅ .env файл существует"
fi

# Шаг 2: Проверка зависимостей
echo -e "\n📦 Установка зависимостей..."
pip install -r requirements.txt

# Шаг 3: Создание лог-директории
echo -e "\n📁 Создание лог-директории..."
mkdir -p /var/log/bot
chmod 755 /var/log/bot
echo "✅ Директория /var/log/bot создана"

# Шаг 4: Проверка конфигурации
echo -e "\n🔍 Проверка конфигурации..."
bash check-config.sh

# Шаг 5: Синтаксис Python
echo -e "\n✅ Проверка синтаксиса Python..."
python3 -m py_compile bot.py
echo "✅ Синтаксис корректен"

# Шаг 6: Вывод информации о запуске
echo -e "\n📋 Информация о запуске:"
echo "========================="
echo "Для запуска бота используйте:"
echo ""
echo "Локально: python bot.py"
echo "Docker:   docker-compose up -d bot"
echo "Логи:     docker-compose logs -f bot"
echo "или:      tail -f /var/log/bot/bot.log"
echo ""
echo "✅ Развертывание завершено!"
