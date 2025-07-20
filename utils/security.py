"""
安全工具 - 数据加密和安全相关功能
"""

import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecurityUtils:
    """安全工具类"""
    
    def __init__(self, encryption_key: str = None):
        self.logger = logging.getLogger(__name__)
        self._fernet = None
        
        if encryption_key:
            self._setup_encryption(encryption_key)

    def _setup_encryption(self, encryption_key: str):
        """设置加密"""
        try:
            # 使用提供的密钥生成Fernet密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'telegram_forwarder_salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
            self._fernet = Fernet(key)
            
        except Exception as e:
            self.logger.error(f"❌ 设置加密失败: {e}")

    def encrypt_data(self, data: str) -> str:
        """加密数据"""
        if not self._fernet:
            return data
        
        try:
            encrypted = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"❌ 加密数据失败: {e}")
            return data

    def decrypt_data(self, encrypted_data: str) -> str:
        """解密数据"""
        if not self._fernet:
            return encrypted_data
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"❌ 解密数据失败: {e}")
            return encrypted_data

    def hash_password(self, password: str) -> str:
        """哈希密码"""
        try:
            salt = os.urandom(32)
            pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return base64.b64encode(salt + pwdhash).decode()
        except Exception as e:
            self.logger.error(f"❌ 哈希密码失败: {e}")
            return password

    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        try:
            decoded = base64.b64decode(hashed.encode())
            salt = decoded[:32]
            stored_hash = decoded[32:]
            pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return pwdhash == stored_hash
        except Exception as e:
            self.logger.error(f"❌ 验证密码失败: {e}")
            return False

    @staticmethod
    def generate_random_key(length: int = 32) -> str:
        """生成随机密钥"""
        return base64.urlsafe_b64encode(os.urandom(length)).decode()

    @staticmethod
    def sanitize_input(text: str) -> str:
        """清理用户输入"""
        if not text:
            return ""
        
        # 移除危险字符
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
        for char in dangerous_chars:
            text = text.replace(char, '')
        
        # 限制长度
        if len(text) > 1000:
            text = text[:1000]
        
        return text.strip()