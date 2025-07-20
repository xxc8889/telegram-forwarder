"""
Web认证管理器
"""

import time
import random
import string
import logging
from typing import Dict, Optional


class AuthManager:
    """Web认证管理器"""
    
    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # 登录码存储 {code: {user_id, expires_at, verified}}
        self.login_codes: Dict[str, Dict] = {}
        
        # 清理过期登录码的间隔
        self.last_cleanup = time.time()

    def generate_login_code(self) -> str:
        """生成6位登录码"""
        # 清理过期的登录码
        self._cleanup_expired_codes()
        
        # 生成6位数字登录码
        code = ''.join(random.choices(string.digits, k=6))
        
        # 确保不重复
        while code in self.login_codes:
            code = ''.join(random.choices(string.digits, k=6))
        
        # 存储登录码（5分钟有效期）
        self.login_codes[code] = {
            'user_id': None,
            'expires_at': time.time() + 300,  # 5分钟
            'verified': False,
            'created_at': time.time()
        }
        
        self.logger.info(f"生成Web登录码: {code}")
        return code

    def verify_login_code_from_bot(self, code: str, user_id: int) -> bool:
        """Bot验证登录码"""
        if code not in self.login_codes:
            return False
        
        login_info = self.login_codes[code]
        
        # 检查是否过期
        if time.time() > login_info['expires_at']:
            del self.login_codes[code]
            return False
        
        # 检查用户是否为管理员
        if user_id not in self.settings.admin_users:
            return False
        
        # 标记为已验证
        login_info['user_id'] = user_id
        login_info['verified'] = True
        
        self.logger.info(f"Bot验证登录码成功: {code}, 用户: {user_id}")
        return True

    def verify_login_code(self, code: str) -> bool:
        """Web端验证登录码"""
        if code not in self.login_codes:
            return False
        
        login_info = self.login_codes[code]
        
        # 检查是否过期
        if time.time() > login_info['expires_at']:
            del self.login_codes[code]
            return False
        
        # 检查是否已通过Bot验证
        if not login_info['verified'] or not login_info['user_id']:
            return False
        
        self.logger.info(f"Web登录成功: {code}, 用户: {login_info['user_id']}")
        return True

    def get_user_by_code(self, code: str) -> Optional[Dict]:
        """根据登录码获取用户信息"""
        if code not in self.login_codes:
            return None
        
        login_info = self.login_codes[code]
        if not login_info['verified']:
            return None
        
        user_id = login_info['user_id']
        
        # 清理已使用的登录码
        del self.login_codes[code]
        
        return {
            'user_id': user_id,
            'is_admin': user_id in self.settings.admin_users,
            'login_time': time.time()
        }

    def get_pending_codes(self) -> Dict[str, Dict]:
        """获取待验证的登录码列表（用于Bot显示）"""
        pending = {}
        current_time = time.time()
        
        for code, info in self.login_codes.items():
            if not info['verified'] and current_time < info['expires_at']:
                pending[code] = {
                    'created_at': info['created_at'],
                    'expires_at': info['expires_at'],
                    'remaining_time': int(info['expires_at'] - current_time)
                }
        
        return pending

    def _cleanup_expired_codes(self):
        """清理过期的登录码"""
        current_time = time.time()
        
        # 每分钟清理一次
        if current_time - self.last_cleanup < 60:
            return
        
        expired_codes = []
        for code, info in self.login_codes.items():
            if current_time > info['expires_at']:
                expired_codes.append(code)
        
        for code in expired_codes:
            del self.login_codes[code]
            self.logger.debug(f"清理过期登录码: {code}")
        
        self.last_cleanup = current_time

    def revoke_all_codes(self):
        """撤销所有登录码"""
        count = len(self.login_codes)
        self.login_codes.clear()
        self.logger.info(f"撤销了 {count} 个登录码")

    def get_active_sessions_count(self) -> int:
        """获取活跃会话数量"""
        return len([info for info in self.login_codes.values() if info['verified']])

    def is_code_pending(self, code: str) -> bool:
        """检查登录码是否在等待验证"""
        if code not in self.login_codes:
            return False
        
        login_info = self.login_codes[code]
        return (not login_info['verified'] and 
                time.time() < login_info['expires_at'])


# 全局认证管理器实例
auth_manager_instance = None

def get_auth_manager():
    """获取认证管理器实例"""
    return auth_manager_instance

def set_auth_manager(auth_manager):
    """设置认证管理器实例"""
    global auth_manager_instance
    auth_manager_instance = auth_manager