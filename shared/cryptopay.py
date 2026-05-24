"""
CryptoPay API клиент
Интеграция с @CryptoBot для приёма платежей в USDT/TON
Документация: https://help.crypt.bot/crypto-pay-api
"""

import httpx
import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class CryptoPay:
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self):
        self.token = os.getenv('CRYPTO_BOT_TOKEN', '')

    def _headers(self) -> Dict:
        return {"Crypto-Pay-API-Token": self.token}

    async def create_invoice(self, amount: float, currency: str = "USDT",
                              payload: str = "", description: str = "",
                              expires_in: int = 3600) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/createInvoice",
                    headers=self._headers(),
                    json={
                        "asset": currency,
                        "amount": str(amount),
                        "payload": payload,
                        "description": description,
                        "expires_in": expires_in,
                        "allow_comments": False,
                        "allow_anonymous": False,
                    },
                )
                data = resp.json()
                if data.get('ok'):
                    return data['result']
                logger.error(f"CryptoPay createInvoice error: {data.get('error')}")
                return None
        except Exception as e:
            logger.error(f"CryptoPay createInvoice exception: {e}")
            return None

    async def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/getInvoices",
                    headers=self._headers(),
                    params={"invoice_ids": str(invoice_id)},
                )
                data = resp.json()
                if data.get('ok') and data['result']['items']:
                    return data['result']['items'][0]
                return None
        except Exception as e:
            logger.error(f"CryptoPay get_invoice exception: {e}")
            return None

    async def get_paid_invoices(self, offset: int = 0, count: int = 100) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/getInvoices",
                    headers=self._headers(),
                    params={"status": "paid", "offset": offset, "count": count},
                )
                data = resp.json()
                if data.get('ok'):
                    return data['result']['items']
                return []
        except Exception as e:
            logger.error(f"CryptoPay get_paid_invoices exception: {e}")
            return []

    async def check_token(self) -> bool:
        """Проверка валидности токена"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/getMe",
                    headers=self._headers(),
                )
                return resp.json().get('ok', False)
        except Exception:
            return False


cryptopay = CryptoPay()
