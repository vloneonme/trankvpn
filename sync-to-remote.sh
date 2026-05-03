#!/bin/bash
# Синхронизация файлов на удаленный сервер

REMOTE_USER="zxc"
REMOTE_HOST="dev-nl1"
REMOTE_MARZBAN="/opt/marzban"
REMOTE_BOT="/opt/ton-bot"

echo "🚀 Синхронизация файлов на $REMOTE_HOST"
echo "=========================================="

# Синхронизация Marzban файлов
echo -e "\n📁 Синхронизация /opt/marzban..."
rsync -avz \
    --exclude='docker-compose.yml.base' \
    --exclude='.env*' \
    marzban/Caddyfile \
    marzban/docker-compose.yml \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_MARZBAN/"

# Синхронизация Bot файлов (кроме .env)
echo -e "\n🤖 Синхронизация /opt/ton-bot..."
rsync -avz \
    --exclude='.env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    ton-bot/bot.py \
    ton-bot/requirements.txt \
    ton-bot/Dockerfile \
    ton-bot/.env.example \
    ton-bot/README.md \
    ton-bot/CHANGELOG.md \
    ton-bot/SUMMARY.md \
    ton-bot/check-config.sh \
    ton-bot/deploy.sh \
    "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BOT/"

# Установка прав на скрипты
echo -e "\n🔧 Установка прав на скрипты..."
ssh "$REMOTE_USER@$REMOTE_HOST" "chmod +x $REMOTE_BOT/check-config.sh $REMOTE_BOT/deploy.sh"

echo -e "\n✅ Синхронизация завершена!"
echo ""
echo "Дальше на сервере выполните:"
echo "  ssh $REMOTE_USER@$REMOTE_HOST"
echo "  cd $REMOTE_BOT"
echo "  bash check-config.sh"
echo "  docker-compose -f $REMOTE_MARZBAN/docker-compose.yml restart bot"
