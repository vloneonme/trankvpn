"""
Worker - фоновые задачи для очистки и обслуживания
Запускается постоянно и выполняет периодические задачи
"""

import asyncio
import logging
import os
from datetime import datetime

from shared.database import db_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_task():
    """Периодическая очистка устаревших данных"""
    while True:
        try:
            # Очистка истекших MTProto прокси
            deleted_mtproto = await db_manager.cleanup_expired_mtproto()
            if deleted_mtproto > 0:
                logger.info(f"🧹 Удалено {deleted_mtproto} истекших MTProto прокси")
            
            # Деактивация истекших подписок
            deactivated = await db_manager.cleanup_expired_subscriptions()
            if deactivated > 0:
                logger.info(f"🧹 Деактивировано {deactivated} истекших подписок")
            
            # Запуск каждые 5 минут
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче очистки: {e}")
            await asyncio.sleep(60)


async def notification_task():
    """Напоминания об истечении подписки (за 24 часа)"""
    # TODO: Интеграция с ботом для отправки уведомлений
    while True:
        try:
            # Логика поиска подписок, истекающих через 24 часа
            # и отправка уведомлений пользователям
            
            await asyncio.sleep(3600)  # Проверка каждый час
            
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче уведомлений: {e}")
            await asyncio.sleep(3600)


async def main():
    """Запуск воркера"""
    logger.info("🚀 Worker запущен")
    
    # Подключение к БД
    await db_manager.connect()
    
    # Запуск задач
    tasks = [
        asyncio.create_task(cleanup_task()),
        asyncio.create_task(notification_task())
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("🛑 Worker остановлен")
    finally:
        await db_manager.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
