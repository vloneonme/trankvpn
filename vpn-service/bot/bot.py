"""
Telegram бот для продажи VPN подписок
Архитектура как у крупных сервисов (@ShukaVPN_bot и аналоги)
"""

import os
import asyncio
import logging
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from shared.database import db_manager
from shared.crypto import crypto_manager

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN')
MARZBAN_URL = os.getenv('MARZBAN_URL', 'http://127.0.0.1:8000').rstrip('/')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'examplesupport')
WEB_APP_URL = os.getenv('WEB_APP_URL', '')  # URL для веб-приложения MTProto

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === Тарифы ===
PRODUCTS = {
    'test': {'name': '🎁 Тестовый', 'days': 3, 'gb': 5, 'price': 0, 'description': '3 дня • 5 ГБ'},
    'basic': {'name': '📱 Обычный', 'days': 30, 'gb': 100, 'price': 100, 'description': '30 дней • 100 ГБ'},
    'unlimited': {'name': '♾️ Безлимит', 'days': 30, 'gb': 0, 'price': 200, 'description': '30 дней • ∞ ГБ'}
}


# === Клавиатуры ===
def get_main_keyboard():
    """Главное меню - только кнопка подключения (минимализм)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔌 Подключиться', callback_data='connect')],
        [InlineKeyboardButton(text='💳 Купить подписку', callback_data='buy')],
        [InlineKeyboardButton(text='⏱ Продлить', callback_data='extend')],
        [InlineKeyboardButton(text='ℹ️ Поддержка', url=f'https://t.me/{SUPPORT_USERNAME}')]
    ])
    return keyboard


def get_tariffs_keyboard():
    """Выбор тарифа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🎁 Тестовый - {PRODUCTS['test']['description']} - Бесплатно",
            callback_data='pay_test'
        )],
        [InlineKeyboardButton(
            text=f"📱 Обычный - {PRODUCTS['basic']['description']} - {PRODUCTS['basic']['price']}₽",
            callback_data='pay_basic'
        )],
        [InlineKeyboardButton(
            text=f"♾️ Безлимит - {PRODUCTS['unlimited']['description']} - {PRODUCTS['unlimited']['price']}₽",
            callback_data='pay_unlimited'
        )],
        [InlineKeyboardButton(text='« Назад', callback_data='back')]
    ])
    return keyboard


def get_connect_keyboard(sub_url: str = None, has_active: bool = False):
    """Меню подключения - скрытая информация"""
    buttons = []
    
    if has_active and sub_url:
        # Кнопка для быстрого подключения
        buttons.append([InlineKeyboardButton(
            text='🚀 Подключить VPN',
            callback_data='quick_connect'
        )])
        
        # Веб-приложение для MTProto (если настроено)
        if WEB_APP_URL:
            buttons.append([InlineKeyboardButton(
                text='🌐 Временный прокси (5 мин)',
                web_app=WebAppInfo(url=WEB_APP_URL)
            )])
    
    buttons.append([InlineKeyboardButton(text='📊 Статус', callback_data='status')])
    buttons.append([InlineKeyboardButton(text='« Меню', callback_data='back')])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# === Обработчики ===

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    """Приветственное сообщение - минимализм"""
    tg_id = message.from_user.id
    
    # Регистрация пользователя
    await db_manager.add_user(tg_id, message.from_user.username)
    
    # Проверка активной подписки
    subscription = await db_manager.get_active_subscription(tg_id)
    
    if subscription:
        text = (
            "🔒 **VPN Active**\n\n"
            f"Ваша подписка активна до: {subscription['expire_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            "Нажмите 🔌 чтобы подключиться"
        )
    else:
        text = (
            "🔒 **VPN Service**\n\n"
            "Быстрое и безопасное подключение к интернету\n"
            "Оплата: TON / USDT\n\n"
            "Выберите действие:"
        )
    
    await message.answer(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    logger.info(f"👤 /start от {tg_id}")


@dp.callback_query(F.data == 'connect')
async def handle_connect(callback: types.CallbackQuery):
    """Меню подключения"""
    tg_id = callback.from_user.id
    subscription = await db_manager.get_active_subscription(tg_id)
    
    sub_url = subscription['subscription_url'] if subscription else None
    has_active = subscription is not None
    
    if has_active:
        text = (
            "🔌 **Подключение**\n\n"
            "Ваше соединение готово.\n"
            "Нажмите кнопку ниже для автоматической настройки."
        )
    else:
        text = (
            "⚠️ **Нет активной подписки**\n\n"
            "Для подключения необходимо приобрести подписку."
        )
    
    await callback.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=get_connect_keyboard(sub_url, has_active)
    )


@dp.callback_query(F.data == 'buy')
async def handle_buy(callback: types.CallbackQuery):
    """Показ тарифов"""
    text = (
        "💳 **Выберите тариф**\n\n"
        "Оплата принимается в TON или USDT\n"
        "Поддержка: @" + SUPPORT_USERNAME
    )
    
    await callback.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=get_tariffs_keyboard()
    )
    logger.info(f"💰 {callback.from_user.id} просматривает тарифы")


@dp.callback_query(F.data.startswith('pay_'))
async def handle_payment(callback: types.CallbackQuery):
    """Обработка оплаты"""
    plan = callback.data.replace('pay_', '')
    
    if plan == 'test':
        # Бесплатный тест
        tg_id = callback.from_user.id
        user = await db_manager.get_user(tg_id)
        
        if user and user.get('used_test'):
            await callback.answer("❌ Вы уже использовали тестовый период", show_alert=True)
            return
        
        await callback.message.edit_text("⏳ Создаю тестовую подписку...")
        
        # Здесь будет логика создания пользователя в Marzban
        # Для примера просто отмечаем тест как использованный
        await db_manager.mark_test_used(tg_id)
        
        await callback.message.edit_text(
            "✅ **Тест активирован!**\n\n"
            "3 дня • 5 ГБ\n"
            "Перейдите в раздел 🔌 для подключения",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        logger.info(f"✅ Тест выдан {tg_id}")
        return
    
    # Платные тарифы - создание инвойса CryptoBot
    product = PRODUCTS.get(plan)
    if not product:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    
    # TODO: Интеграция с CryptoBot
    await callback.answer("💳 Скоро будет доступна оплата через CryptoBot", show_alert=True)


@dp.callback_query(F.data == 'status')
async def handle_status(callback: types.CallbackQuery):
    """Статус подписки"""
    tg_id = callback.from_user.id
    subscription = await db_manager.get_active_subscription(tg_id)
    
    if subscription:
        days_left = (subscription['expire_at'] - __import__('datetime').datetime.now()).days
        gb_left = subscription['data_limit_gb']  # TODO: Реальный остаток из Marzban
        
        text = (
            "📊 **Ваша подписка**\n\n"
            f"Тариф: {PRODUCTS[subscription['plan_type']]['name']}\n"
            f"Истекает: через {days_left} дн.\n"
            f"Трафик: {gb_left} ГБ\n\n"
            f"Дата окончания: {subscription['expire_at'].strftime('%d.%m.%Y %H:%M')}"
        )
    else:
        text = "⚠️ **Нет активной подписки**\n\nПриобретите подписку в разделе 💳"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💳 Купить', callback_data='buy')],
        [InlineKeyboardButton(text='« Меню', callback_data='back')]
    ])
    
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=keyboard)


@dp.callback_query(F.data == 'back')
async def handle_back(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await cmd_start(callback.message)


# === Запуск ===

async def main():
    """Запуск бота"""
    # Подключение к БД
    await db_manager.connect()
    await db_manager.init_tables()
    
    logger.info("🚀 Бот запущен")
    
    # Удаление вебхука и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
