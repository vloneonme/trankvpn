"""
TrankVPN Worker
Фоновые задачи: проверка оплат CryptoPay, уведомления об истечении подписок, очистка БД
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

from shared.database import db_manager
from shared.cryptopay import cryptopay
from shared.marzban import marzban_api

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'support')


async def _send_message(bot_token: str, chat_id: int, text: str, reply_markup: dict = None):
    """Отправка сообщения через Bot API без aiogram (воркер не держит полный бот)"""
    import httpx
    payload: dict = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
    }
    if reply_markup:
        import json
        payload['reply_markup'] = json.dumps(reply_markup)

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload
        )


def _days_word(n: int) -> str:
    if 11 <= n % 100 <= 14:
        return 'дней'
    r = n % 10
    if r == 1:
        return 'день'
    if 2 <= r <= 4:
        return 'дня'
    return 'дней'


async def check_payments_task():
    """Каждые 2 минуты проверяет оплаченные инвойсы CryptoPay и активирует подписки"""
    logger.info("💳 Payment checker started")
    while True:
        try:
            pending = await db_manager.get_pending_payments()
            if pending:
                logger.info(f"Checking {len(pending)} pending payments...")

            for payment in pending:
                try:
                    invoice = await cryptopay.get_invoice(int(payment['invoice_id']))
                    if not invoice:
                        continue

                    if invoice['status'] != 'paid':
                        continue

                    tg_id = payment['telegram_id']
                    payload = invoice.get('payload', '')
                    parts = payload.split(':')
                    if len(parts) < 3:
                        continue

                    _, plan_id, action = parts[0], parts[1], parts[2]

                    # Импортируем логику активации из бота
                    from shared.database import db_manager as db

                    # Проверяем идемпотентность
                    p = await db.get_payment_by_invoice(str(invoice['invoice_id']))
                    if p and p['status'] == 'paid':
                        continue

                    PLANS = {
                        'basic': {'days': 30, 'gb': 100},
                        'unlimited': {'days': 30, 'gb': 0},
                    }
                    plan = PLANS.get(plan_id)
                    if not plan:
                        continue

                    if action == 'extend':
                        sub = await db.get_active_subscription(tg_id)
                        if sub and sub.get('marzban_username'):
                            await marzban_api.extend_user(sub['marzban_username'], plan['days'])
                        await db.extend_subscription(tg_id, plan['days'])
                    else:
                        marzban_user = await marzban_api.create_user(
                            tg_id, plan_id, gb=plan['gb'], days=plan['days']
                        )
                        if marzban_user:
                            sub_url = marzban_user.get('subscription_url', '')
                            await db.add_subscription(
                                tg_id, marzban_user['username'], sub_url,
                                plan_id, data_limit=plan['gb'], expire_days=plan['days']
                            )

                    await db.mark_payment_paid(str(invoice['invoice_id']))

                    # Уведомляем пользователя
                    if BOT_TOKEN:
                        await _send_message(
                            BOT_TOKEN, tg_id,
                            "✅ *Оплата получена!*\n\n"
                            "Ваша подписка активирована.\n"
                            "Откройте бота и нажмите *🔌 Мой VPN* для получения ссылки подключения."
                        )
                    logger.info(f"✅ Auto-activated: tg{tg_id} plan={plan_id} invoice={invoice['invoice_id']}")

                except Exception as e:
                    logger.error(f"Error processing payment {payment.get('invoice_id')}: {e}")

        except Exception as e:
            logger.error(f"Payment check task error: {e}")

        await asyncio.sleep(120)  # проверяем каждые 2 минуты


async def notify_expiring_task():
    """Каждый час проверяет подписки, истекающие через 24 часа, и отправляет уведомления"""
    logger.info("🔔 Notification task started")
    await asyncio.sleep(60)  # небольшая задержка при старте

    while True:
        try:
            expiring = await db_manager.get_expiring_subscriptions(hours=24)
            for sub in expiring:
                tg_id = sub['telegram_id']
                expire = sub['expire_at']
                import datetime
                days_left = max(0, (expire - datetime.datetime.now()).days)
                hours_left = max(0, int((expire - datetime.datetime.now()).total_seconds() / 3600))

                if days_left == 0:
                    time_text = f"{hours_left} ч."
                else:
                    time_text = f"{days_left} {_days_word(days_left)}"

                if BOT_TOKEN:
                    kb = {
                        "inline_keyboard": [[
                            {"text": "⏱ Продлить подписку", "callback_data": "extend"}
                        ]]
                    }
                    await _send_message(
                        BOT_TOKEN, tg_id,
                        f"⚠️ *TrankVPN — истекает подписка*\n\n"
                        f"До конца подписки осталось *{time_text}*\n\n"
                        f"Продлите подписку прямо сейчас чтобы не потерять доступ к VPN 👇",
                        reply_markup=kb
                    )
                    logger.info(f"🔔 Notified tg{tg_id} — {time_text} left")
                    await asyncio.sleep(0.1)  # rate limit

        except Exception as e:
            logger.error(f"Notification task error: {e}")

        await asyncio.sleep(3600)  # проверяем каждый час


async def cleanup_task():
    """Каждые 10 минут очищает устаревшие данные"""
    logger.info("🧹 Cleanup task started")
    while True:
        try:
            deleted_mtproto = await db_manager.cleanup_expired_mtproto()
            if deleted_mtproto > 0:
                logger.info(f"🧹 Deleted {deleted_mtproto} expired MTProto proxies")

            deactivated = await db_manager.deactivate_expired_subscriptions()
            if deactivated > 0:
                logger.info(f"🧹 Deactivated {deactivated} expired subscriptions")

        except Exception as e:
            logger.error(f"Cleanup task error: {e}")

        await asyncio.sleep(600)


async def main():
    logger.info("🚀 TrankVPN Worker starting...")
    await db_manager.connect()
    await db_manager.init_tables()
    logger.info("✅ DB connected")

    tasks = [
        asyncio.create_task(check_payments_task()),
        asyncio.create_task(notify_expiring_task()),
        asyncio.create_task(cleanup_task()),
    ]

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Worker stopped")
    finally:
        await db_manager.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
