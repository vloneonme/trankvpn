"""
Модуль работы с базой данных
Асинхронные операции с MariaDB через aiomysql
"""

import os
import aiomysql
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self.config = {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'vpn_user'),
            'password': os.getenv('DB_PASS', ''),
            'db': os.getenv('DB_NAME', 'vpn_service'),
            'autocommit': True,
            'minsize': 2,
            'maxsize': 20,
            'charset': 'utf8mb4',
        }

    async def connect(self):
        self.pool = await aiomysql.create_pool(**self.config)
        print(f"✅ DB connected: {self.config['host']}:{self.config['port']}/{self.config['db']}")

    async def disconnect(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL UNIQUE,
                        username VARCHAR(255),
                        used_test TINYINT(1) DEFAULT 0,
                        balance DECIMAL(10,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_telegram_id (telegram_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        marzban_username VARCHAR(255),
                        subscription_url TEXT,
                        plan_type ENUM('test', 'basic', 'unlimited') NOT NULL,
                        data_limit_gb INT DEFAULT 0,
                        expire_at TIMESTAMP NOT NULL,
                        is_active TINYINT(1) DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_tg_active (telegram_id, is_active),
                        INDEX idx_expire (expire_at),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        invoice_id VARCHAR(100) NOT NULL UNIQUE,
                        amount DECIMAL(10,4),
                        currency VARCHAR(10) DEFAULT 'USDT',
                        status ENUM('pending', 'paid', 'expired', 'failed') DEFAULT 'pending',
                        plan_type VARCHAR(50),
                        action ENUM('buy', 'extend') DEFAULT 'buy',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP NULL,
                        INDEX idx_invoice (invoice_id),
                        INDEX idx_status (status),
                        INDEX idx_tg (telegram_id),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS mtproto_proxies (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        proxy_secret VARCHAR(255) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        INDEX idx_expires (expires_at),
                        FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

        print("✅ Tables ready")

    # === Пользователи ===

    async def add_user(self, telegram_id: int, username: str = None) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT IGNORE INTO bot_users (telegram_id, username) VALUES (%s, %s)",
                    (telegram_id, username)
                )
                return cur.rowcount >= 0

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,)
                )
                return await cur.fetchone()

    async def mark_test_used(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE bot_users SET used_test = 1 WHERE telegram_id = %s", (telegram_id,)
                )

    async def get_users_count(self) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM bot_users")
                row = await cur.fetchone()
                return row[0] if row else 0

    async def get_all_users(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT telegram_id, username FROM bot_users")
                return await cur.fetchall()

    # === Подписки ===

    async def add_subscription(self, telegram_id: int, marzban_username: str,
                               sub_url: str, plan_type: str,
                               data_limit: int = 0, expire_days: int = 30) -> bool:
        expire_at = datetime.now() + timedelta(days=expire_days)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Деактивируем старые подписки того же типа
                await cur.execute("""
                    UPDATE subscriptions SET is_active = 0
                    WHERE telegram_id = %s AND plan_type = %s
                """, (telegram_id, plan_type))

                await cur.execute("""
                    INSERT INTO subscriptions
                    (telegram_id, marzban_username, subscription_url, plan_type, data_limit_gb, expire_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (telegram_id, marzban_username, sub_url, plan_type, data_limit, expire_at))
                return True

    async def get_active_subscription(self, telegram_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM subscriptions
                    WHERE telegram_id = %s AND is_active = 1 AND expire_at > NOW()
                    ORDER BY expire_at DESC LIMIT 1
                """, (telegram_id,))
                return await cur.fetchone()

    async def extend_subscription(self, telegram_id: int, additional_days: int) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE subscriptions
                    SET expire_at = DATE_ADD(GREATEST(expire_at, NOW()), INTERVAL %s DAY)
                    WHERE telegram_id = %s AND is_active = 1 AND expire_at > NOW()
                    ORDER BY expire_at DESC LIMIT 1
                """, (additional_days, telegram_id))
                return cur.rowcount > 0

    async def get_active_subs_count(self) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM subscriptions WHERE is_active = 1 AND expire_at > NOW()"
                )
                row = await cur.fetchone()
                return row[0] if row else 0

    async def get_expiring_subscriptions(self, hours: int = 24) -> List[Dict]:
        """Подписки, истекающие через `hours` часов (для уведомлений)"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT s.*, u.telegram_id
                    FROM subscriptions s
                    JOIN bot_users u ON s.telegram_id = u.telegram_id
                    WHERE s.is_active = 1
                      AND s.expire_at > NOW()
                      AND s.expire_at <= DATE_ADD(NOW(), INTERVAL %s HOUR)
                """, (hours,))
                return await cur.fetchall()

    async def deactivate_expired_subscriptions(self) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE subscriptions SET is_active = 0
                    WHERE expire_at <= NOW() AND is_active = 1
                """)
                return cur.rowcount

    # === Платежи ===

    async def create_payment(self, telegram_id: int, invoice_id: str,
                             amount: float, currency: str, plan_type: str,
                             action: str = 'buy') -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT IGNORE INTO payments
                    (telegram_id, invoice_id, amount, currency, plan_type, action)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (telegram_id, invoice_id, amount, currency, plan_type, action))
                return cur.rowcount > 0

    async def get_payment_by_invoice(self, invoice_id: str) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT * FROM payments WHERE invoice_id = %s", (invoice_id,)
                )
                return await cur.fetchone()

    async def mark_payment_paid(self, invoice_id: str) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE payments SET status = 'paid', paid_at = NOW()
                    WHERE invoice_id = %s AND status = 'pending'
                """, (invoice_id,))
                return cur.rowcount > 0

    async def get_pending_payments(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM payments
                    WHERE status = 'pending'
                      AND created_at > DATE_SUB(NOW(), INTERVAL 2 HOUR)
                    ORDER BY created_at ASC
                """)
                return await cur.fetchall()

    # === MTProto прокси ===

    async def cleanup_expired_mtproto(self) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM mtproto_proxies WHERE expires_at <= NOW()")
                return cur.rowcount


db_manager = DatabaseManager()
