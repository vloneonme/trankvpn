#!/bin/bash
# Синхронизация файлов на удаленный сервер (безопасно через temp)

REMOTE_USER="zxc"
REMOTE_HOST="dev-nl1"
REMOTE_TEMP="/tmp/trankvpn_update"

echo "🚀 Безопасная синхронизация файлов на $REMOTE_HOST"
echo "======================================================"

# Проверка доступа
echo "🔍 Проверка доступа к серверу..."
if ! ssh "$REMOTE_USER@$REMOTE_HOST" "test -d /opt/marzban && test -d /opt/ton-bot"; then
    echo "❌ Ошибка доступа к серверу или директории не существуют"
    exit 1
fi
echo "✅ Доступ успешен"

# Создание временной директории на сервере
echo "📁 Создание временной директории..."
ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_TEMP"

# Копирование всех файлов
echo -e "\n📋 Копирование файлов..."
scp ton-bot/bot.py "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/Dockerfile "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/.env.example "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/README.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/CHANGELOG.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/SUMMARY.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/check-config.sh "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp ton-bot/deploy.sh "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp marzban/Caddyfile "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"
scp marzban/docker-compose.yml "$REMOTE_USER@$REMOTE_HOST:$REMOTE_TEMP/"

echo -e "\n✅ Файлы скопированы во временную директорию: $REMOTE_TEMP"

# Инструкция для пользователя
echo ""
echo "📝 ДАЛЬШЕ НА СЕРВЕРЕ ВЫПОЛНИТЕ:"
echo "================================"
echo "ssh $REMOTE_USER@$REMOTE_HOST"
echo ""
echo "# Посмотрите скопированные файлы"
echo "ls -lh $REMOTE_TEMP/"
echo ""
echo "# Установите права и переместите файлы БОТ"
echo "sudo chmod +x $REMOTE_TEMP/check-config.sh $REMOTE_TEMP/deploy.sh"
echo "sudo cp $REMOTE_TEMP/bot.py /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/requirements.txt /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/Dockerfile /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/.env.example /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/README.md /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/CHANGELOG.md /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/SUMMARY.md /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/check-config.sh /opt/ton-bot/"
echo "sudo cp $REMOTE_TEMP/deploy.sh /opt/ton-bot/"
echo "sudo chmod +x /opt/ton-bot/check-config.sh /opt/ton-bot/deploy.sh"
echo ""
echo "# Установите права и переместите MARZBAN конфиги"
echo "cd /opt/marzban"
echo "sudo cp Caddyfile Caddyfile.backup.\$(date +%s)"
echo "sudo cp docker-compose.yml docker-compose.yml.backup.\$(date +%s)"
echo "sudo cp $REMOTE_TEMP/Caddyfile ."
echo "sudo cp $REMOTE_TEMP/docker-compose.yml ."
echo ""
echo "# Обновите .env если нужно"
echo "sudo nano /opt/ton-bot/.env"
echo ""
echo "# Перезагрузите сервисы"
echo "sudo docker-compose down"
echo "sudo docker-compose up -d"
echo ""
echo "# Проверьте логи"
echo "sudo docker-compose logs -f bot"
echo ""
echo "# Очистка"
echo "rm -rf $REMOTE_TEMP"
