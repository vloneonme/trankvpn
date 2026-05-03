#!/bin/bash
# Синхронизация файлов на удаленный сервер через SCP

REMOTE_USER="zxc"
REMOTE_HOST="dev-nl1"
REMOTE_MARZBAN="/opt/marzban"
REMOTE_BOT="/opt/ton-bot"

echo "🚀 Синхронизация файлов на $REMOTE_HOST"
echo "=========================================="

# Проверка доступа
echo "🔍 Проверка доступа к серверу..."
if ! ssh "$REMOTE_USER@$REMOTE_HOST" "test -d $REMOTE_MARZBAN && test -d $REMOTE_BOT"; then
    echo "❌ Ошибка доступа к серверу или директории не существуют"
    exit 1
fi
echo "✅ Доступ успешен"

# Синхронизация Marzban файлов
echo -e "\n📁 Копирование Marzban файлов..."
scp -p marzban/Caddyfile "$REMOTE_USER@$REMOTE_HOST:$REMOTE_MARZBAN/Caddyfile.new"
scp -p marzban/docker-compose.yml "$REMOTE_USER@$REMOTE_HOST:$REMOTE_MARZBAN/docker-compose.yml.new"

# Синхронизация Bot файлов
echo -e "\n🤖 Копирование Bot файлов..."
scp -p ton-bot/bot.py "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/Dockerfile "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/.env.example "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/README.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/CHANGELOG.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/SUMMARY.md "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/check-config.sh "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"
scp -p ton-bot/deploy.sh "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"

# Установка прав на скрипты
echo -e "\n🔧 Установка прав на скрипты..."
ssh "$REMOTE_USER@$REMOTE_HOST" "chmod +x $REMOTE_BOT/check-config.sh $REMOTE_BOT/deploy.sh"

echo -e "\n✅ Копирование завершено!"
echo ""
echo "📝 Важно: На сервере выполните вручную:"
echo "  ssh $REMOTE_USER@$REMOTE_HOST"
echo ""
echo "Проверьте НОВЫЕ файлы:"
echo "  ls -lh $REMOTE_MARZBAN/*.new"
echo "  ls -lh $REMOTE_BOT/"
echo ""
echo "После проверки замените старые на новые:"
echo "  cd $REMOTE_MARZBAN"
echo "  cp Caddyfile Caddyfile.old"
echo "  mv Caddyfile.new Caddyfile"
echo "  cp docker-compose.yml docker-compose.yml.old"  
echo "  mv docker-compose.yml.new docker-compose.yml"
echo ""
echo "Затем перезагрузите сервисы:"
echo "  docker-compose down"
echo "  docker-compose up -d"
echo ""
echo "Проверьте логи бота:"
echo "  docker-compose logs -f bot"
