#!/bin/bash
# Скрипт резервного копирования данных VPN сервиса

set -e

BACKUP_DIR="/var/backups/vpn-service"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/opt/vpn-service"

echo "🔄 Начало резервного копирования..."

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# Бэкап базы данных
echo "💾 Бэкап MariaDB..."
docker exec vpn-mariadb mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" vpn_service > "$BACKUP_DIR/db_$DATE.sql"

# Бэкап Redis (если есть данные)
echo "💾 Бэкап Redis..."
docker exec vpn-redis redis-cli SAVE 2>/dev/null || true
cp /var/lib/vpn-service/redis/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb" 2>/dev/null || true

# Бэкап конфигов
echo "💾 Бэкап конфигурации..."
tar -czf "$BACKUP_DIR/configs_$DATE.tar.gz" \
    "$PROJECT_DIR/docker/.env" \
    "$PROJECT_DIR/configs/" 2>/dev/null || true

# Удаление старых бэкапов (хранить 7 дней)
echo "🧹 Очистка старых бэкапов..."
find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "✅ Резервное копирование завершено: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
