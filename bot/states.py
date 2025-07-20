"""
用户状态管理 - 简化版，主要用于Web登录
"""

from enum import Enum
from typing import Dict, Any


class UserState(Enum):
    """用户状态枚举"""
    NORMAL = "normal"
    WEB_LOGIN_PENDING = "web_login_pending"


class StateManager:
    """状态管理器"""
    
    def __init__(self):
        self.user_states: Dict[int, UserState] = {}
        self.user_data: Dict[int, Dict[str, Any]] = {}

    def set_user_state(self, user_id: int, state: UserState, data: Dict[str, Any] = None):
        """设置用户状态"""
        self.user_states[user_id] = state
        if data:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            self.user_data[user_id].update(data)

    def get_user_state(self, user_id: int) -> UserState:
        """获取用户状态"""
        return self.user_states.get(user_id, UserState.NORMAL)

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """获取用户数据"""
        return self.user_data.get(user_id, {})

    def clear_user_state(self, user_id: int):
        """清除用户状态"""
        self.user_states.pop(user_id, None)
        self.user_data.pop(user_id, None)

    def is_user_in_process(self, user_id: int) -> bool:
        """检查用户是否在某个流程中"""
        state = self.get_user_state(user_id)
        return state != UserState.NORMAL


# 全局状态管理器实例
state_manager = StateManager()
