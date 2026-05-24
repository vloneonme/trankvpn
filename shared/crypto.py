"""
Модуль шифрования для защиты конфигураций VPN
AES-256-GCM + HMAC-SHA256 для временных токенов
"""

import os
import base64
import hashlib
import hmac
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoManager:
    def __init__(self, secret_key: str = None):
        raw = secret_key or os.getenv('ENCRYPTION_KEY') or self._generate_key()
        self.key = hashlib.sha256(raw.encode()).digest()
        self.aesgcm = AESGCM(self.key)

    @staticmethod
    def _generate_key() -> str:
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def encrypt_config(self, config_data: str) -> str:
        nonce = os.urandom(12)
        encrypted = self.aesgcm.encrypt(nonce, config_data.encode('utf-8'), None)
        return base64.urlsafe_b64encode(nonce + encrypted).decode('utf-8')

    def decrypt_config(self, encrypted_data: str) -> str:
        try:
            combined = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            nonce, ciphertext = combined[:12], combined[12:]
            decrypted = self.aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def generate_short_lived_token(self, user_id: int, duration_minutes: int = 5) -> str:
        expiry = int(time.time()) + (duration_minutes * 60)
        payload = f"{user_id}:{expiry}"
        sig = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()

    def verify_short_lived_token(self, token: str) -> tuple[bool, int]:
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            parts = decoded.split(':')
            if len(parts) != 3:
                return False, 0

            user_id, expiry, signature = int(parts[0]), int(parts[1]), parts[2]

            if int(time.time()) > expiry:
                return False, 0

            payload = f"{user_id}:{expiry}"
            expected = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()

            if not hmac.compare_digest(signature, expected):
                return False, 0

            return True, user_id
        except Exception:
            return False, 0


crypto_manager = CryptoManager()
