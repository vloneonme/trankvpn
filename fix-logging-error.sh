#!/bin/bash
# Быстрое исправление ошибки логирования на dev-nl1

echo "🔧 Быстрое исправление ошибки логирования"
echo "=========================================="

# Шаг 1: Копирование файлов
echo "📁 Копирование обновленных файлов..."
sudo cp /tmp/trankvpn_update/bot.py /opt/ton-bot/
sudo cp /tmp/trankvpn_update/Dockerfile /opt/ton-bot/
sudo cp /tmp/trankvpn_update/docker-compose.yml /opt/marzban/

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при копировании файлов"
    exit 1
fi

# Шаг 2: Остановка сервисов
echo -e "\n⛔ Остановка сервисов..."
cd /opt/marzban
sudo docker-compose down

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при остановке сервисов"
    exit 1
fi

# Шаг 3: Пересборка образа
echo -e "\n🔨 Пересборка Docker образа (может занять время)..."
sudo docker-compose build --no-cache

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при сборке образа"
    exit 1
fi

# Шаг 4: Запуск сервисов
echo -e "\n🚀 Запуск сервисов..."
sudo docker-compose up -d

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при запуске сервисов"
    exit 1
fi

# Шаг 5: Проверка статуса
echo -e "\n✅ Проверка статуса сервисов..."
sleep 3
sudo docker-compose ps

# Шаг 6: Вывод логов
echo -e "\n📊 Последние логи бота:"
echo "================================"
sudo docker-compose logs bot | tail -20
echo ""
echo "✅ Исправление завершено!"
echo ""
echo "Для просмотра полных логов используйте:"
echo "  sudo docker-compose logs -f bot"
echo "  или"
echo "  tail -f /var/log/bot/bot.log"
