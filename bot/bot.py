"""
TrankVPN Telegram Bot
Управление VPN-подписками: тарифы, оплата через CryptoPay (USDT/TON), Marzban
"""

import os
import asyncio
import logging
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from shared.database import db_manager
from shared.marzban import marzban_api
from shared.cryptopay import cryptopay

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'support')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === Тарифы ===

PLANS = {
    'test': {
        'name': 'Тестовый',
        'days': 3,
        'gb': 5,
        'price_usdt': 0.0,
        'emoji': '🎁',
        'desc': '3 дня · 5 ГБ · Бесплатно',
    },
    'basic': {
        'name': 'Базовый',
        'days': 30,
        'gb': 100,
        'price_usdt': 1.5,
        'emoji': '📱',
        'desc': '30 дней · 100 ГБ · 1.5 USDT',
    },
    'unlimited': {
        'name': 'Безлимит',
        'days': 30,
        'gb': 0,
        'price_usdt': 3.0,
        'emoji': '♾️',
        'desc': '30 дней · ∞ трафик · 3 USDT',
    },
}


# === Клавиатуры ===

def kb_main(has_sub: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if has_sub:
        rows.append([InlineKeyboardButton(text='🔌 Мой VPN', callback_data='my_vpn')])
        rows.append([InlineKeyboardButton(text='⏱ Продлить подписку', callback_data='extend')])
    else:
        rows.append([InlineKeyboardButton(text='🎁 Попробовать бесплатно (3 дня)', callback_data='pay_test')])
        rows.append([InlineKeyboardButton(text='💳 Купить подписку', callback_data='buy')])
    rows.append([InlineKeyboardButton(text='📊 Статус', callback_data='status')])
    rows.append([InlineKeyboardButton(text='❓ Поддержка', url=f'https://t.me/{SUPPORT_USERNAME}')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_plans(action: str = 'pay') -> InlineKeyboardMarkup:
    rows = []
    for plan_id, p in PLANS.items():
        if plan_id == 'test' and action == 'extend':
            continue
        rows.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['name']} — {p['desc']}",
            callback_data=f'{action}_{plan_id}'
        )])
    rows.append([InlineKeyboardButton(text='« Назад', callback_data='back')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_payment(invoice_id: int, pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💳 Оплатить в CryptoBot', url=pay_url)],
        [InlineKeyboardButton(text='✅ Я оплатил — проверить', callback_data=f'check_{invoice_id}')],
        [InlineKeyboardButton(text='❌ Отменить', callback_data='back')],
    ])


def kb_vpn() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📱 Как подключиться?', callback_data='howto')],
        [InlineKeyboardButton(text='📊 Статус', callback_data='status')],
        [InlineKeyboardButton(text='« Меню', callback_data='back')],
    ])


def kb_back(to: str = 'back') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='« Назад', callback_data=to)]
    ])


# === Вспомогательные функции ===

def _days_word(n: int) -> str:
    if 11 <= n % 100 <= 14:
        return 'дней'
    r = n % 10
    if r == 1:
        return 'день'
    if 2 <= r <= 4:
        return 'дня'
    return 'дней'


async def _main_text(tg_id: int) -> tuple[str, bool]:
    """Возвращает (текст, has_sub) для главного меню"""
    sub = await db_manager.get_active_subscription(tg_id)
    if sub:
        expire = sub['expire_at']
        days = max(0, (expire - datetime.datetime.now()).days)
        text = (
            "🔒 *TrankVPN*\n\n"
            f"✅ Подписка активна\n"
            f"📅 Истекает через *{days} {_days_word(days)}* "
            f"({expire.strftime('%d.%m.%Y')})\n\n"
            "Нажмите *🔌 Мой VPN* чтобы получить ссылку для подключения"
        )
        return text, True
    text = (
        "🔒 *TrankVPN*\n\n"
        "Быстрый и безопасный VPN-сервис\n\n"
        "• Работает во всех странах\n"
        "• Android, iOS, Windows, Mac\n"
        "• Оплата в USDT и TON через CryptoBot\n"
        "• Поддержка 24/7\n\n"
        "Выберите действие:"
    )
    return text, False


async def activate_subscription(tg_id: int, invoice: dict) -> bool:
    """Активирует подписку после подтверждения оплаты"""
    payload = invoice.get('payload', '')
    parts = payload.split(':')
    if len(parts) < 3:
        logger.error(f"Invalid invoice payload: {payload}")
        return False

    _, plan_id, action = parts[0], parts[1], parts[2]
    plan = PLANS.get(plan_id)
    if not plan:
        logger.error(f"Unknown plan in payload: {plan_id}")
        return False

    invoice_id_str = str(invoice['invoice_id'])

    # Идемпотентность — не активируем дважды
    payment = await db_manager.get_payment_by_invoice(invoice_id_str)
    if payment and payment['status'] == 'paid':
        return True

    if action == 'extend':
        sub = await db_manager.get_active_subscription(tg_id)
        if sub and sub.get('marzban_username'):
            await marzban_api.extend_user(sub['marzban_username'], plan['days'])
        await db_manager.extend_subscription(tg_id, plan['days'])
    else:
        marzban_user = await marzban_api.create_user(
            tg_id, plan_id, gb=plan['gb'], days=plan['days']
        )
        if not marzban_user:
            logger.error(f"Marzban failed for tg{tg_id}")
            return False
        sub_url = marzban_user.get('subscription_url', '')
        await db_manager.add_subscription(
            tg_id, marzban_user['username'], sub_url,
            plan_id, data_limit=plan['gb'], expire_days=plan['days']
        )

    await db_manager.mark_payment_paid(invoice_id_str)
    logger.info(f"✅ Sub activated: tg{tg_id} plan={plan_id} action={action}")
    return True


# === Обработчики ===

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    await db_manager.add_user(tg_id, message.from_user.username)
    text, has_sub = await _main_text(tg_id)
    await message.answer(text, parse_mode='Markdown', reply_markup=kb_main(has_sub))
    logger.info(f"/start tg{tg_id} (@{message.from_user.username})")


@dp.callback_query(F.data == 'back')
async def handle_back(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    await db_manager.add_user(tg_id, callback.from_user.username)
    text, has_sub = await _main_text(tg_id)
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb_main(has_sub))


@dp.callback_query(F.data == 'buy')
async def handle_buy(callback: types.CallbackQuery):
    text = (
        "💳 *Выберите тариф*\n\n"
        "Оплата через @CryptoBot в USDT или TON\n"
        "Подписка активируется автоматически после оплаты"
    )
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb_plans('pay'))


@dp.callback_query(F.data == 'extend')
async def handle_extend(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    sub = await db_manager.get_active_subscription(tg_id)
    if not sub:
        await callback.answer("⚠️ Нет активной подписки для продления", show_alert=True)
        return
    expire = sub['expire_at']
    text = (
        "⏱ *Продление подписки*\n\n"
        f"Текущая подписка истекает: {expire.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Выберите тариф для продления:"
    )
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb_plans('extend'))


@dp.callback_query(F.data.startswith('pay_') | F.data.startswith('extend_'))
async def handle_plan_select(callback: types.CallbackQuery):
    data = callback.data
    if data.startswith('extend_'):
        action, plan_id = 'extend', data[len('extend_'):]
    else:
        action, plan_id = 'pay', data[len('pay_'):]

    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    tg_id = callback.from_user.id

    # === Бесплатный тест ===
    if plan_id == 'test':
        user = await db_manager.get_user(tg_id)
        if user and user.get('used_test'):
            await callback.answer("❌ Тестовый период уже был использован", show_alert=True)
            return

        await callback.message.edit_text("⏳ Создаю тестовую подписку...")

        marzban_user = await marzban_api.create_user(tg_id, 'test', gb=5, days=3)
        if not marzban_user:
            await callback.message.edit_text(
                "❌ Не удалось создать подписку.\nОбратитесь в поддержку.",
                reply_markup=kb_back()
            )
            return

        sub_url = marzban_user.get('subscription_url', '')
        await db_manager.add_subscription(tg_id, marzban_user['username'],
                                          sub_url, 'test', data_limit=5, expire_days=3)
        await db_manager.mark_test_used(tg_id)

        await callback.message.edit_text(
            "✅ *Тестовая подписка активирована!*\n\n"
            "🕐 3 дня · 📦 5 ГБ\n\n"
            "Нажмите *🔌 Мой VPN* чтобы получить ссылку для подключения",
            parse_mode='Markdown',
            reply_markup=kb_main(has_sub=True)
        )
        logger.info(f"🎁 Test sub: tg{tg_id}")
        return

    # === Платный тариф — создаём инвойс CryptoPay ===
    await callback.message.edit_text("⏳ Создаю счёт на оплату...")

    payload = f"{tg_id}:{plan_id}:{action}"
    description = f"TrankVPN — {plan['emoji']} {plan['name']} ({plan['desc']})"

    invoice = await cryptopay.create_invoice(
        amount=plan['price_usdt'],
        currency="USDT",
        payload=payload,
        description=description,
        expires_in=3600
    )

    if not invoice:
        await callback.message.edit_text(
            "❌ Ошибка создания счёта.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=kb_back()
        )
        return

    invoice_id = invoice['invoice_id']
    pay_url = invoice['pay_url']

    await db_manager.create_payment(
        tg_id, str(invoice_id), plan['price_usdt'], 'USDT', plan_id, action
    )

    action_text = "продления" if action == 'extend' else "покупки"
    text = (
        f"💳 *Счёт на оплату*\n\n"
        f"Тариф: {plan['emoji']} {plan['name']}\n"
        f"Сумма: *{plan['price_usdt']} USDT*\n"
        f"Номер счёта: `{invoice_id}`\n\n"
        f"1\\. Нажмите *Оплатить в CryptoBot*\n"
        f"2\\. Оплатите через @CryptoBot\n"
        f"3\\. Вернитесь и нажмите *Я оплатил*\n\n"
        f"⏱ Счёт действителен 1 час"
    )
    await callback.message.edit_text(
        text, parse_mode='MarkdownV2',
        reply_markup=kb_payment(invoice_id, pay_url)
    )
    logger.info(f"💰 Invoice #{invoice_id} created for tg{tg_id} plan={plan_id}")


@dp.callback_query(F.data.startswith('check_'))
async def handle_check_payment(callback: types.CallbackQuery):
    try:
        invoice_id = int(callback.data[len('check_'):])
    except ValueError:
        await callback.answer("Некорректный номер счёта", show_alert=True)
        return

    tg_id = callback.from_user.id
    await callback.answer("🔍 Проверяю оплату...")

    invoice = await cryptopay.get_invoice(invoice_id)
    if not invoice:
        await callback.answer("❌ Счёт не найден. Проверьте номер.", show_alert=True)
        return

    if invoice['status'] != 'paid':
        status_text = {
            'active': '⏳ Ещё не оплачен',
            'expired': '⌛️ Срок действия истёк',
        }.get(invoice['status'], invoice['status'])
        await callback.answer(
            f"Статус счёта: {status_text}\n\nОплатите через @CryptoBot и повторите проверку.",
            show_alert=True
        )
        return

    success = await activate_subscription(tg_id, invoice)
    if not success:
        await callback.answer(
            "❌ Ошибка активации. Обратитесь в поддержку с номером счёта.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "✅ *Оплата подтверждена!*\n\n"
        "Подписка активирована.\n"
        "Нажмите *🔌 Мой VPN* чтобы получить ссылку для подключения",
        parse_mode='Markdown',
        reply_markup=kb_main(has_sub=True)
    )
    logger.info(f"✅ Payment confirmed tg{tg_id} invoice#{invoice_id}")


@dp.callback_query(F.data == 'my_vpn')
async def handle_my_vpn(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    sub = await db_manager.get_active_subscription(tg_id)

    if not sub:
        text, has_sub = await _main_text(tg_id)
        await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb_main(False))
        return

    sub_url = sub.get('subscription_url', '')
    expire = sub['expire_at']
    days = max(0, (expire - datetime.datetime.now()).days)
    plan = PLANS.get(sub['plan_type'], {})
    gb = sub.get('data_limit_gb', 0)
    traffic = '∞' if gb == 0 else f'{gb} ГБ'

    text = (
        f"🔌 *Ваш VPN*\n\n"
        f"Тариф: {plan.get('emoji', '')} {plan.get('name', sub['plan_type'])}\n"
        f"Трафик: {traffic}\n"
        f"Активна ещё: *{days} {_days_word(days)}*\n\n"
        f"📋 *Ссылка подписки:*\n"
        f"`{sub_url}`\n\n"
        f"_Скопируйте ссылку и добавьте в приложение_"
    )
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb_vpn())


@dp.callback_query(F.data == 'status')
async def handle_status(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    sub = await db_manager.get_active_subscription(tg_id)

    if not sub:
        text = (
            "📊 *Статус подписки*\n\n"
            "❌ Активной подписки нет\n\n"
            "Приобретите подписку чтобы начать пользоваться VPN"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🎁 Попробовать бесплатно', callback_data='pay_test')],
            [InlineKeyboardButton(text='💳 Купить подписку', callback_data='buy')],
            [InlineKeyboardButton(text='« Меню', callback_data='back')],
        ])
    else:
        expire = sub['expire_at']
        days = max(0, (expire - datetime.datetime.now()).days)
        plan = PLANS.get(sub['plan_type'], {})
        gb = sub.get('data_limit_gb', 0)
        traffic = '∞' if gb == 0 else f'{gb} ГБ'

        traffic_info = ''
        if sub.get('marzban_username'):
            t = await marzban_api.get_user_traffic(sub['marzban_username'])
            if t['limit_gb'] > 0:
                traffic_info = f"\nИспользовано: {t['used_gb']} / {t['limit_gb']} ГБ"
            else:
                traffic_info = f"\nИспользовано: {t['used_gb']} ГБ"

        text = (
            "📊 *Статус подписки*\n\n"
            f"Тариф: {plan.get('emoji', '')} {plan.get('name', sub['plan_type'])}\n"
            f"Трафик: {traffic}{traffic_info}\n"
            f"Активна ещё: *{days} {_days_word(days)}*\n"
            f"Истекает: {expire.strftime('%d.%m.%Y %H:%M')}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔌 Мой VPN', callback_data='my_vpn')],
            [InlineKeyboardButton(text='⏱ Продлить', callback_data='extend')],
            [InlineKeyboardButton(text='« Меню', callback_data='back')],
        ])

    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb)


@dp.callback_query(F.data == 'howto')
async def handle_howto(callback: types.CallbackQuery):
    text = (
        "📱 *Инструкция по подключению*\n\n"
        "Скопируйте ссылку из раздела *🔌 Мой VPN* и добавьте её в приложение:\n\n"
        "*Android:*\n"
        "• v2rayNG (Play Store / APK)\n"
        "• Hiddify (Play Store)\n"
        "Нажмите «+» → «Импорт с URL» → вставьте ссылку\n\n"
        "*iOS:*\n"
        "• Streisand (App Store)\n"
        "• Hiddify (App Store)\n"
        "Нажмите «+» → «Добавить подписку» → вставьте ссылку\n\n"
        "*Windows:*\n"
        "• Hiddify Next\n"
        "• Nekoray\n\n"
        "*Mac:*\n"
        "• Hiddify Next\n"
        "• FoXray\n\n"
        "Есть вопросы? Напишите в поддержку 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❓ Поддержка', url=f'https://t.me/{SUPPORT_USERNAME}')],
        [InlineKeyboardButton(text='« Назад', callback_data='my_vpn')],
    ])
    await callback.message.edit_text(text, parse_mode='Markdown', reply_markup=kb)


# === Уведомления (вызывается воркером через HTTP или напрямую) ===

async def notify_expiring(tg_id: int, days_left: int):
    """Отправка уведомления об истечении подписки"""
    try:
        text = (
            f"⚠️ *TrankVPN — напоминание*\n\n"
            f"Ваша подписка истекает через *{days_left} {_days_word(days_left)}*!\n\n"
            f"Продлите сейчас чтобы не потерять доступ 👇"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='⏱ Продлить подписку', callback_data='extend')],
        ])
        await bot.send_message(tg_id, text, parse_mode='Markdown', reply_markup=kb)
    except Exception as e:
        logger.warning(f"Notify failed for tg{tg_id}: {e}")


# === Админские команды ===

@dp.message(Command('admin'))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = await db_manager.get_users_count()
    subs = await db_manager.get_active_subs_count()
    text = (
        "🛠 *Панель администратора*\n\n"
        f"👤 Всего пользователей: {users}\n"
        f"✅ Активных подписок: {subs}"
    )
    await message.answer(text, parse_mode='Markdown')


@dp.message(Command('broadcast'))
async def cmd_broadcast(message: types.Message):
    """Рассылка всем пользователям. Использование: /broadcast Текст"""
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.replace('/broadcast', '', 1).strip()
    if not text:
        await message.answer("Использование: /broadcast Текст сообщения")
        return
    users = await db_manager.get_all_users()
    ok, fail = 0, 0
    for user in users:
        try:
            await bot.send_message(user['telegram_id'], text)
            ok += 1
            await asyncio.sleep(0.05)  # rate limit
        except Exception:
            fail += 1
    await message.answer(f"✅ Отправлено: {ok}\n❌ Ошибок: {fail}")


# === Запуск ===

async def main():
    await db_manager.connect()
    await db_manager.init_tables()

    cp_ok = await cryptopay.check_token()
    if cp_ok:
        logger.info("✅ CryptoPay connected")
    else:
        logger.warning("⚠️  CryptoPay token not set or invalid")

    logger.info("🚀 TrankVPN Bot started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
