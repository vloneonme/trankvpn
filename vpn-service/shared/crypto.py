"""
Модуль шифрования для защиты конфигураций VPN
Использует AES-256-GCM для надежного шифрования
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoManager:
    """Управление шифрованием подписок и данных"""
    
    def __init__(self, secret_key: str = None):
        """
        Инициализация менеджера шифрования
        
        Args:
            secret_key: Секретный ключ (если нет, генерируется новый)
        """
        self.secret_key = secret_key or os.getenv('ENCRYPTION_KEY', self._generate_key())
        self.key = hashlib.sha256(self.secret_key.encode()).digest()
        self.aesgcm = AESGCM(self.key)
    
    def _generate_key(self) -> str:
        """Генерация случайного секретного ключа"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def encrypt_config(self, config_data: str) -> str:
        """
        Шифрование конфигурации VPN
        
        Args:
            config_data: Строка с конфигурацией (URL подписки или JSON)
            
        Returns:
            Зашифрованная строка в base64
        """
        nonce = os.urandom(12)
        data_bytes = config_data.encode('utf-8')
        
        encrypted = self.aesgcm.encrypt(nonce, data_bytes, None)
        
        # Объединяем nonce + encrypted данные и кодируем в base64
        combined = nonce + encrypted
        return base64.urlsafe_b64encode(combined).decode('utf-8')
    
    def decrypt_config(self, encrypted_data: str) -> str:
        """
        Расшифровка конфигурации VPN
        
        Args:
            encrypted_data: Зашифрованная строка в base64
            
        Returns:
            Оригинальная конфигурация
        """
        try:
            combined = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            nonce = combined[:12]
            ciphertext = combined[12:]
            
            decrypted = self.aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Ошибка расшифровки: {str(e)}")
    
    def generate_short_lived_token(self, user_id: int, duration_minutes: int = 5) -> str:
        """
        Генерация временного токена доступа
        
        Args:
            user_id: ID пользователя
            duration_minutes: Время жизни токена в минутах
            
        Returns:
            Временный токен
        """
        import time
        import hmac
        
        expiry = int(time.time()) + (duration_minutes * 60)
        payload = f"{user_id}:{expiry}"
        signature = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
        
        return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()
    
    def verify_short_lived_token(self, token: str) -> tuple[bool, int]:
        """
        Проверка временного токена
        
        Args:
            token: Токен для проверки
            
        Returns:
            (valid, user_id) - валидность и ID пользователя
        """
        import time
        import hmac
        
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            parts = decoded.split(':')
            
            if len(parts) != 3:
                return False, 0
            
            user_id = int(parts[0])
            expiry = int(parts[1])
            signature = parts[2]
            
            # Проверяем время
            if int(time.time()) > expiry:
                return False, 0
            
            # Проверяем подпись
            payload = f"{user_id}:{expiry}"
            expected_signature = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return False, 0
            
            return True, user_id
            
        except Exception:
            return False, 0


# Глобальный экземпляр
crypto_manager = CryptoManager()
