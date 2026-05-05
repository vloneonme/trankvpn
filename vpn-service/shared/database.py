"""
Модуль работы с базой данных
Асинхронные операции с MariaDB через aiomysql
"""

import os
import aiomysql
from typing import Optional, Dict, Any, List
from datetime import datetime


class DatabaseManager:
    """Управление подключениями и операциями с БД"""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self.config = {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'marzban'),
            'password': os.getenv('DB_PASS', ''),
            'db': os.getenv('DB_NAME', 'marzban'),
            'autocommit': True,
            'minsize': 5,
            'maxsize': 20,
        }
    
    async def connect(self):
        """Создание пула подключений"""
        try:
            self.pool = await aiomysql.create_pool(**self.config)
            print(f"✅ Подключение к БД: {self.config['host']}:{self.config['port']}/{self.config['db']}")
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    async def disconnect(self):
        """Закрытие пула подключений"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
    
    async def init_tables(self):
        """Создание необходимых таблиц"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Таблица пользователей бота
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL UNIQUE,
                        username VARCHAR(255),
                        used_test TINYINT(1) DEFAULT 0,
                        referral_code VARCHAR(20) UNIQUE,
                        referred_by BIGINT,
                        balance DECIMAL(10,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_telegram_id (telegram_id),
                        INDEX idx_referral (referral_code)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Таблица подписок
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        marzban_username VARCHAR(255) UNIQUE,
                        subscription_url TEXT,
                        encrypted_config TEXT,
                        plan_type ENUM('test', 'basic', 'unlimited') NOT NULL,
                        data_limit_gb INT,
                        expire_at TIMESTAMP,
                        is_active TINYINT(1) DEFAULT 1,
                        device_fingerprint VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_tg_plan (telegram_id, plan_type),
                        INDEX idx_expire (expire_at),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Таблица временных MTProto прокси
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS mtproto_proxies (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        proxy_secret VARCHAR(255) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        is_used TINYINT(1) DEFAULT 0,
                        INDEX idx_expires (expires_at),
                        INDEX idx_secret (proxy_secret),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                # Таблица платежей
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        invoice_id VARCHAR(100) UNIQUE,
                        amount DECIMAL(10,2),
                        currency VARCHAR(10),
                        status ENUM('pending', 'paid', 'failed') DEFAULT 'pending',
                        plan_type VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP NULL,
                        INDEX idx_invoice (invoice_id),
                        INDEX idx_status (status),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                print("✅ Таблицы БД созданы/обновлены")
    
    # === Пользователи ===
    
    async def add_user(self, telegram_id: int, username: str = None) -> bool:
        """Добавить пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT IGNORE INTO bot_users (telegram_id, username) VALUES (%s, %s)",
                    (telegram_id, username)
                )
                return cur.rowcount >= 0
    
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
                return await cur.fetchone()
    
    async def mark_test_used(self, telegram_id: int):
        """Отметить тест как использованный"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE bot_users SET used_test = 1 WHERE telegram_id = %s", (telegram_id,))
    
    # === Подписки ===
    
    async def add_subscription(self, telegram_id: int, marzban_username: str, 
                               sub_url: str, plan_type: str, data_limit: int = 0,
                               expire_days: int = 30) -> bool:
        """Добавить подписку"""
        from datetime import timedelta
        expire_at = datetime.now() + timedelta(days=expire_days)
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO subscriptions 
                    (telegram_id, marzban_username, subscription_url, plan_type, data_limit_gb, expire_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (telegram_id, marzban_username, sub_url, plan_type, data_limit, expire_at))
                return True
    
    async def get_user_subscriptions(self, telegram_id: int) -> List[Dict]:
        """Получить все подписки пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM subscriptions 
                    WHERE telegram_id = %s AND is_active = 1
                    ORDER BY expire_at DESC
                """, (telegram_id,))
                return await cur.fetchall()
    
    async def get_active_subscription(self, telegram_id: int) -> Optional[Dict]:
        """Получить активную подписку"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM subscriptions 
                    WHERE telegram_id = %s AND is_active = 1 AND expire_at > NOW()
                    ORDER BY expire_at DESC LIMIT 1
                """, (telegram_id,))
                return await cur.fetchone()
    
    # === MTProto прокси ===
    
    async def create_mtproto_proxy(self, telegram_id: int, secret: str, duration_minutes: int = 5) -> bool:
        """Создать временный MTProto прокси"""
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO mtproto_proxies (telegram_id, proxy_secret, expires_at)
                    VALUES (%s, %s, %s)
                """, (telegram_id, secret, expires_at))
                return True
    
    async def get_valid_mtproto_proxy(self, telegram_id: int) -> Optional[Dict]:
        """Получить действующий MTProto прокси"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM mtproto_proxies 
                    WHERE telegram_id = %s AND expires_at > NOW() AND is_used = 0
                    ORDER BY expires_at DESC LIMIT 1
                """, (telegram_id,))
                return await cur.fetchone()
    
    # === Очистка старых записей ===
    
    async def cleanup_expired_mtproto(self):
        """Удалить истекшие MTProto прокси"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM mtproto_proxies WHERE expires_at <= NOW()")
                return cur.rowcount
    
    async def cleanup_expired_subscriptions(self):
        """Деактивировать истекшие подписки"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE subscriptions SET is_active = 0 
                    WHERE expire_at <= NOW() AND is_active = 1
                """)
                return cur.rowcount


# Глобальный экземпляр
db_manager = DatabaseManager()
