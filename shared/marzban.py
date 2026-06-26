"""
Клиент Marzban API
Управление VPN-пользователями через REST API панели Marzban
"""

import httpx
import os
import re
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def _rewrite_sub_url(marzban_sub_url: str) -> str:
    """
    Заменяет хост Marzban на наш домен в ссылке подписки.
    Например: https://panel.myserver.com:8000/sub/TOKEN → https://vpn.mydomain.com/sub/TOKEN
    Если DOMAIN не задан — возвращает оригинальный URL.
    """
    domain = os.getenv('DOMAIN', '').strip()
    if not domain:
        return marzban_sub_url
    match = re.search(r'/sub/([a-zA-Z0-9_\-]+)', marzban_sub_url)
    if not match:
        return marzban_sub_url
    token = match.group(1)
    return f"https://{domain}/sub/{token}"


class MarzbanAPI:
    def __init__(self):
        self.base_url = os.getenv('MARZBAN_URL', 'http://marzban:8000').rstrip('/')
        self.username = os.getenv('MARZBAN_ADMIN', 'admin')
        self.password = os.getenv('MARZBAN_PASS', '')
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.post(
                f"{self.base_url}/api/admin/token",
                data={"username": self.username, "password": self.password},
            )
            resp.raise_for_status()
            self._token = resp.json()['access_token']
            self._token_expiry = time.time() + 3500
            return self._token

    async def _headers(self) -> Dict:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def create_user(self, telegram_id: int, plan_type: str,
                          gb: int = 0, days: int = 30) -> Optional[Dict]:
        try:
            username = f"tg{telegram_id}_{plan_type}"
            expire_ts = int(time.time()) + (days * 86400)
            data_limit = gb * 1024 * 1024 * 1024 if gb > 0 else 0

            payload = {
                "username": username,
                "proxies": {"vless": {"flow": ""}},
                "inbounds": {
                    "vless": ["VLESS TCP REALITY", "VLESS GRPC REALITY"]
                },
                "expire": expire_ts,
                "data_limit": data_limit,
                "data_limit_reset_strategy": "no_reset",
                "status": "active"
            }

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.post(
                    f"{self.base_url}/api/user",
                    json=payload,
                    headers=await self._headers(),
                )
                if resp.status_code == 409:
                    # Пользователь уже существует — обновляем его
                    result = await self._reset_and_get_user(username, expire_ts, data_limit)
                else:
                    resp.raise_for_status()
                    result = resp.json()

                if result and result.get('subscription_url'):
                    result['subscription_url'] = _rewrite_sub_url(result['subscription_url'])
                return result
        except Exception as e:
            logger.error(f"Marzban create_user error for tg{telegram_id}: {e}")
            return None

    async def _reset_and_get_user(self, username: str,
                                   expire_ts: int, data_limit: int) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.put(
                    f"{self.base_url}/api/user/{username}",
                    json={"expire": expire_ts, "data_limit": data_limit, "status": "active"},
                    headers=await self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Marzban reset_user error {username}: {e}")
            return None

    async def get_user(self, username: str) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(
                    f"{self.base_url}/api/user/{username}",
                    headers=await self._headers(),
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Marzban get_user error {username}: {e}")
            return None

    async def extend_user(self, username: str, additional_days: int) -> Optional[Dict]:
        try:
            user = await self.get_user(username)
            if not user:
                return None

            current_expire = user.get('expire') or int(time.time())
            new_expire = max(int(time.time()), current_expire) + (additional_days * 86400)

            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.put(
                    f"{self.base_url}/api/user/{username}",
                    json={"expire": new_expire, "status": "active"},
                    headers=await self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Marzban extend_user error {username}: {e}")
            return None

    async def get_user_traffic(self, username: str) -> Dict:
        """Возвращает использованный трафик в ГБ"""
        user = await self.get_user(username)
        if not user:
            return {'used_gb': 0, 'limit_gb': 0}
        used = user.get('used_traffic', 0) / (1024 ** 3)
        limit = user.get('data_limit', 0) / (1024 ** 3)
        return {'used_gb': round(used, 2), 'limit_gb': round(limit, 2)}


marzban_api = MarzbanAPI()
