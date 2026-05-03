import asyncio
import logging
import time
import os
import httpx
import aiomysql
from datetime import datetime, timedelta
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from aiocryptopay import AioCryptoPay, Networks

# --- Загрузка конфигурации ---
load_dotenv()

# Создание директории для логов если её нет
LOG_DIR = Path('/var/log/bot')
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Проверяем, что директория действительно существует и доступна для записи
    if not LOG_DIR.exists():
        raise PermissionError(f"Директория {LOG_DIR} не существует после попытки создания")
    # Пробуем создать тестовый файл для проверки прав доступа
    test_file = LOG_DIR / '.write_test'
    test_file.touch()
    test_file.unlink()
except Exception as e:
    print(f"⚠️  Не удалось создать директорию логов: {e}")
    # Используем текущую директорию как fallback
    LOG_DIR = Path('.')

LOG_FILE = LOG_DIR / 'bot.log'

# Настройка логирования - используем delay=True для отложенного открытия файла
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), delay=True),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
MARZBAN_URL = os.getenv("MARZBAN_URL", "").rstrip('/')
MARZBAN_USER = os.getenv("MARZBAN_USER")
MARZBAN_PASS = os.getenv("MARZBAN_PASS")
SUBSCRIPTION_URL = os.getenv("SUBSCRIPTION_URL", "").rstrip('/')
INBOUND_TAG = os.getenv("INBOUND_TAG", "VLESS TCP REALITY")

# Проверка обязательных переменных
required_vars = ["BOT_TOKEN", "CRYPTO_BOT_TOKEN", "MARZBAN_URL", "MARZBAN_USER", "MARZBAN_PASS"]
for var in required_vars:
    if not globals().get(var):
        logger.error(f"Отсутствует переменная окружения: {var}")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "marzban"),
    "password": os.getenv("DB_PASS", "cfPnN4SvTyzcIt6vyN8e"),
    "db": os.getenv("DB_NAME", "marzban"),
    "autocommit": True
}

# Структура продуктов (тестовая, базовая, улучшенная)
PRODUCTS = {
    "test": {"name": "🎁 Тестовый период", "days": 3, "gb": 5, "price": 0},
    "basic": {"name": "📱 Basic", "days": 30, "gb": 50, "price": 290},
    "premium": {"name": "⭐ Premium", "days": 90, "gb": 200, "price": 790}
}

# --- Глобальные объекты ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
crypto = AioCryptoPay(token=CRYPTO_BOT_TOKEN, network=Networks.MAIN_NET)
db_pool = None  # Пул будет инициализирован в main()

# --- Функции БД (Асинхронные и эффективные) ---
async def init_db():
    global db_pool
    try:
        db_pool = await aiomysql.create_pool(**DB_CONFIG)
        logger.info("✅ Подключение к БД установлено")
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL UNIQUE,
                        username VARCHAR(255),
                        used_test TINYINT(1) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_telegram_id (telegram_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                logger.info("✅ Таблица bot_users готова")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}", exc_info=True)
        raise

async def add_user_to_db(tg_id, username):
    """Добавить пользователя в БД"""
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT IGNORE INTO bot_users (telegram_id, username) VALUES (%s, %s)", 
                    (tg_id, username)
                )
                logger.info(f"👤 Пользователь {tg_id} добавлен/обновлен в БД")
    except Exception as e:
        logger.error(f"❌ Ошибка добавления пользователя {tg_id}: {e}", exc_info=True)

async def check_test_used(tg_id):
    """Проверить, использовал ли пользователь тестовый период"""
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT used_test FROM bot_users WHERE telegram_id = %s", (tg_id,))
                result = await cur.fetchone()
                if result:
                    return result[0] == 1
                return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки теста для {tg_id}: {e}", exc_info=True)
        return False

async def mark_test_used(tg_id):
    """Отметить тест как использованный"""
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE bot_users SET used_test = 1 WHERE telegram_id = %s", (tg_id,))
                logger.info(f"✅ Тест отмечен как использованный для {tg_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отметки теста для {tg_id}: {e}", exc_info=True)

# --- Асинхронные функции Marzban API ---
async def get_marzban_token():
    """Получить токен авторизации Marzban"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{MARZBAN_URL}/api/admin/token",
                data={"grant_type": "password", "username": MARZBAN_USER, "password": MARZBAN_PASS}
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                logger.info("✅ Токен Marzban получен")
                return token
            else:
                logger.error(f"❌ Ошибка авторизации Marzban: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена Marzban: {e}", exc_info=True)
    return None

async def create_vpn_user(tg_id, product_key):
    """Создать VPN пользователя"""
    if product_key not in PRODUCTS:
        logger.error(f"❌ Неизвестный продукт: {product_key}")
        return None
    
    token = await get_marzban_token()
    if not token:
        logger.error(f"❌ Не удалось получить токен для создания пользователя {tg_id}")
        return None
    
    product = PRODUCTS[product_key]
    username = f"tg_{tg_id}_{int(time.time())}"
    expiry = int((datetime.now() + timedelta(days=product['days'])).timestamp())
    
    async with httpx.AsyncClient(timeout=10) as client:
        headers = {"Authorization": f"Bearer {token}"}
        user_data = {
            "username": username,
            "data_limit": product['gb'] * 1024**3,
            "expire": expiry,
            "inbounds": {INBOUND_TAG: [INBOUND_TAG]},
            "proxies": {"vless": {"flow": "xtls-rprx-vision", "id": ""}},
            "note": f"TG:{tg_id} Plan:{product_key}"
        }
        try:
            resp = await client.post(f"{MARZBAN_URL}/api/user", json=user_data, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                sub = data.get('subscription_url', '')
                if sub.startswith('http'):
                    logger.info(f"✅ VPN пользователь создан для {tg_id} (план: {product_key})")
                    return sub
                result_url = f"{SUBSCRIPTION_URL}/sub/{sub.lstrip('/')}"
                logger.info(f"✅ VPN пользователь создан для {tg_id} (план: {product_key})")
                return result_url
            else:
                logger.error(f"❌ Ошибка создания пользователя {tg_id}: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"❌ Ошибка при запросе к Marzban для {tg_id}: {e}", exc_info=True)
    return None

# --- Обработчики (Handlers) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Стартовая команда"""
    try:
        await add_user_to_db(message.from_user.id, message.from_user.username or "Unknown")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
            [InlineKeyboardButton(text="🎁 Тестовый период", callback_data="test")],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ])
        await message.answer(
            "🔒 *VPN Service*\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=kb
        )
        logger.info(f"📧 /start от пользователя {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в /start для {message.from_user.id}: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@dp.callback_query(F.data == "buy")
async def show_products(callback: types.CallbackQuery):
    """Показать доступные тарифы"""
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{PRODUCTS['basic']['name']} - {PRODUCTS['basic']['price']}₽", callback_data="pay_basic")],
            [InlineKeyboardButton(text=f"{PRODUCTS['premium']['name']} - {PRODUCTS['premium']['price']}₽", callback_data="pay_premium")],
            [InlineKeyboardButton(text="« Назад", callback_data="back")]
        ])
        await callback.message.edit_text("💳 *Выберите тариф:*", parse_mode="Markdown", reply_markup=kb)
        logger.info(f"🛒 Пользователь {callback.from_user.id} просматривает тарифы")
    except Exception as e:
        logger.error(f"❌ Ошибка при показе тарифов для {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке тарифов", show_alert=True)

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery):
    """Обработка платежа"""
    try:
        parts = callback.data.split("_")
        if len(parts) < 2:
            logger.error(f"❌ Неверный формат данных платежа: {callback.data}")
            await callback.answer("❌ Ошибка платежа", show_alert=True)
            return
        
        pk = parts[1]  # ИСПРАВЛЕНО: было [9], должно быть [1]
        
        if pk not in PRODUCTS or PRODUCTS[pk]['price'] == 0:
            logger.error(f"❌ Невозможно оплатить {pk}")
            await callback.answer("❌ Этот тариф нельзя оплатить", show_alert=True)
            return
        
        product = PRODUCTS[pk]
        try:
            invoice = await crypto.create_invoice(
                amount=str(product['price']),
                currency_type='fiat',
                fiat='RUB',
                accepted_assets='TON,USDT',
                description=f"VPN {product['name']}"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка создания счета: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при создании счета. Попробуйте позже.", show_alert=True)
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice.bot_invoice_url)],
            [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_{invoice.invoice_id}_{pk}")],
            [InlineKeyboardButton(text="« Отмена", callback_data="back")]
        ])
        await callback.message.edit_text(
            f"💎 *{product['name']}*\nСумма: {product['price']}₽",
            parse_mode="Markdown",
            reply_markup=kb
        )
        logger.info(f"💰 Счет создан для {callback.from_user.id}: {invoice.invoice_id} ({pk})")
    except Exception as e:
        logger.error(f"❌ Ошибка в process_payment для {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при обработке платежа", show_alert=True)

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: types.CallbackQuery):
    """Проверить статус платежа"""
    try:
        parts = callback.data.split("_")
        if len(parts) < 3:
            logger.error(f"❌ Неверный формат данных проверки: {callback.data}")
            await callback.answer("❌ Ошибка проверки", show_alert=True)
            return
        
        inv_id = parts[1]
        pk = parts[2]
        
        try:
            invoices = await crypto.get_invoices(invoice_ids=[int(inv_id)])
        except Exception as e:
            logger.error(f"❌ Ошибка проверки платежа: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при проверке платежа", show_alert=True)
            return
        
        # ИСПРАВЛЕНО: было invoices.status, должно быть invoices[0].status
        if invoices and len(invoices) > 0 and invoices[0].status == 'paid':
            await callback.message.edit_text("⏳ Оплата подтверждена! Создаю подписку...")
            logger.info(f"✅ Оплата подтверждена для {callback.from_user.id} (счет: {inv_id})")
            
            sub_url = await create_vpn_user(callback.from_user.id, pk)
            if sub_url:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="« В меню", callback_data="back")]
                ])
                await callback.message.edit_text(
                    f"✅ *Готово!*\nВаша ссылка подписки:\n`{sub_url}`",
                    parse_mode="Markdown",
                    reply_markup=kb
                )
                logger.info(f"🎉 Подписка выдана пользователю {callback.from_user.id}")
            else:
                await callback.message.edit_text("❌ Ошибка при создании подписки. Обратитесь к администратору.")
                logger.error(f"❌ Ошибка создания подписки для {callback.from_user.id} (счет: {inv_id})")
        else:
            await callback.answer("⏳ Оплата еще не подтверждена. Попробуйте позже.", show_alert=True)
            logger.info(f"⏳ Платеж еще не подтвержден для {callback.from_user.id} (счет: {inv_id})")
    except Exception as e:
        logger.error(f"❌ Ошибка в check_payment для {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при проверке платежа", show_alert=True)

@dp.callback_query(F.data == "test")
async def test_subscription(callback: types.CallbackQuery):
    """Выдать тестовую подписку"""
    try:
        user_id = callback.from_user.id
        is_used = await check_test_used(user_id)
        
        if is_used:
            await callback.answer("❌ Вы уже использовали тестовый период!", show_alert=True)
            logger.info(f"🚫 Попытка повторного использования теста пользователем {user_id}")
            return
        
        await callback.message.edit_text("⏳ Подготавливаем тестовый период...")
        logger.info(f"🔄 Создание тестовой подписки для {user_id}")
        
        sub_url = await create_vpn_user(user_id, "test")
        
        if sub_url:
            await mark_test_used(user_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« В главное меню", callback_data="back")]
            ])
            await callback.message.edit_text(
                f"🎁 *Тестовый период активирован!*\n"
                f"Период: 3 дня\n"
                f"Трафик: 5 GB\n"
                f"Ваша ссылка подписки:\n`{sub_url}`",
                parse_mode="Markdown",
                reply_markup=kb
            )
            logger.info(f"✅ Тестовая подписка выдана пользователю {user_id}")
        else:
            await callback.message.edit_text("❌ Ошибка при создании подписки. Попробуйте позже.")
            logger.error(f"❌ Ошибка создания тестовой подписки для {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в test_subscription для {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(F.data == "about")
async def about(callback: types.CallbackQuery):
    """О сервисе"""
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="back")]
        ])
        await callback.message.edit_text(
            "ℹ️ *О сервисе*\n"
            "• Протокол: VLESS REALITY\n"
            "• Оплата: CryptoBot (TON, USDT)\n"
            "• Поддержка: @admin\n"
            "• Тарифы: Тестовый (3д), Basic (30д), Premium (90д)",
            parse_mode="Markdown",
            reply_markup=kb
        )
        logger.info(f"📖 Пользователь {callback.from_user.id} просмотрел информацию")
    except Exception as e:
        logger.error(f"❌ Ошибка в about для {callback.from_user.id}: {e}", exc_info=True)

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    """Вернуться в главное меню"""
    try:
        # ИСПРАВЛЕНО: было callback.message, теперь используем types.Message
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
            [InlineKeyboardButton(text="🎁 Тестовый период", callback_data="test")],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ])
        await callback.message.edit_text(
            "🔒 *VPN Service*\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=kb
        )
        logger.info(f"🏠 Пользователь {callback.from_user.id} вернулся в меню")
    except Exception as e:
        logger.error(f"❌ Ошибка в back для {callback.from_user.id}: {e}", exc_info=True)

async def main():
    """Главная функция запуска бота"""
    try:
        logger.info("🚀 Запуск VPN бота...")
        await init_db()
        logger.info("✅ БД инициализирована")
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка при запуске: {e}", exc_info=True)
        raise
    finally:
        if db_pool:
            db_pool.close()
            await db_pool.wait_closed()
            logger.info("🛑 Пул БД закрыт")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)