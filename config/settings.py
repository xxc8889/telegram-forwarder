"""
配置管理 - 支持热更新
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv


class Settings:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config_path = Path(config_file)
        self._config = {}
        self._load_env()
        self._load_config()
        
    def _load_env(self):
        """加载环境变量"""
        load_dotenv()
        
    def _load_config(self):
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                logging.warning(f"加载配置文件失败: {e}")
                self._config = {}
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            'global_settings': {
                'min_interval': 3,
                'max_interval': 30,
                'hourly_limit': 50,
                'retry_attempts': 3,
                'media_timeout': 300
            },
            'rotation': {
                'strategy': 'message',  # message/time/smart
                'messages_per_rotation': 1,
                'time_per_rotation': 30,
                'rest_time': 30
            },
            'filters': {
                'remove_links': True,
                'remove_emojis': True,
                'remove_special_chars': True,
                'ad_detection': True,
                'smart_filter': True
            },
            'security': {
                'session_encryption': True,
                'backup_enabled': True,
                'log_retention_days': 30
            }
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            self._config = default_config
            logging.info(f"创建默认配置文件: {self.config_path}")
        except Exception as e:
            logging.error(f"创建配置文件失败: {e}")
            self._config = default_config

    def reload(self):
        """重新加载配置"""
        self._load_env()
        self._load_config()
        logging.info("配置已重新加载")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号路径"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save_config()

    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")

    # 环境变量属性
    @property
    def bot_token(self) -> str:
        return os.getenv('BOT_TOKEN', '')

    @property
    def admin_users(self) -> List[int]:
        users_str = os.getenv('ADMIN_USERS', '')
        if users_str:
            try:
                return [int(u.strip()) for u in users_str.split(',') if u.strip()]
            except ValueError:
                return []
        return []

    @property
    def database_url(self) -> str:
        return os.getenv('DATABASE_URL', 'sqlite:///data/forwarder.db')

    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO')

    @property
    def log_file(self) -> str:
        return os.getenv('LOG_FILE', 'logs/forwarder.log')

    @property
    def encryption_key(self) -> Optional[str]:
        return os.getenv('ENCRYPTION_KEY')

    # 全局设置属性
    @property
    def min_interval(self) -> int:
        env_val = os.getenv('MIN_INTERVAL')
        if env_val:
            return int(env_val)
        return self.get('global_settings.min_interval', 3)

    @property
    def max_interval(self) -> int:
        env_val = os.getenv('MAX_INTERVAL')
        if env_val:
            return int(env_val)
        return self.get('global_settings.max_interval', 30)

    @property
    def hourly_limit(self) -> int:
        env_val = os.getenv('HOURLY_LIMIT')
        if env_val:
            return int(env_val)
        return self.get('global_settings.hourly_limit', 50)

    @property
    def retry_attempts(self) -> int:
        return self.get('global_settings.retry_attempts', 3)

    @property
    def media_timeout(self) -> int:
        return self.get('global_settings.media_timeout', 300)

    # 轮换设置
    @property
    def rotation_strategy(self) -> str:
        return self.get('rotation.strategy', 'message')

    @property
    def messages_per_rotation(self) -> int:
        return self.get('rotation.messages_per_rotation', 1)

    @property
    def time_per_rotation(self) -> int:
        return self.get('rotation.time_per_rotation', 30)

    @property
    def rest_time(self) -> int:
        return self.get('rotation.rest_time', 30)

    # 过滤设置
    @property
    def remove_links(self) -> bool:
        return self.get('filters.remove_links', True)

    @property
    def remove_emojis(self) -> bool:
        return self.get('filters.remove_emojis', True)

    @property
    def remove_special_chars(self) -> bool:
        return self.get('filters.remove_special_chars', True)

    @property
    def ad_detection(self) -> bool:
        return self.get('filters.ad_detection', True)

    @property
    def smart_filter(self) -> bool:
        return self.get('filters.smart_filter', True)

    # 安全设置
    @property
    def session_encryption(self) -> bool:
        return self.get('security.session_encryption', True)

    @property
    def backup_enabled(self) -> bool:
        env_val = os.getenv('BACKUP_ENABLED')
        if env_val:
            return env_val.lower() == 'true'
        return self.get('security.backup_enabled', True)

    @property
    def log_retention_days(self) -> int:
        return self.get('security.log_retention_days', 30)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'bot_token': self.bot_token[:10] + '...' if self.bot_token else '',
            'admin_users': self.admin_users,
            'database_url': self.database_url,
            'min_interval': self.min_interval,
            'max_interval': self.max_interval,
            'hourly_limit': self.hourly_limit,
            'rotation_strategy': self.rotation_strategy,
            'config': self._config
        }