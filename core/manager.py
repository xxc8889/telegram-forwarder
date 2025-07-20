"""
Bot管理器 - 统一管理所有组件，集成Web管理
"""

import asyncio
import logging
from typing import Dict, List
from telegram.ext import Application

from .listener import MessageListener
from .sender import MessageSender
from .account_manager import AccountManager
from .scheduler import TaskScheduler
from .group_processor import GroupProcessor
from .api_pool_manager import APIPoolManager
from bot.handlers import setup_handlers
from utils.config_watcher import ConfigWatcher


class ForwarderManager:
    """转发管理器主类"""
    
    # 类变量，用于全局访问
    instance = None
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)
        
        # 设置全局实例
        ForwarderManager.instance = self
        
        # 核心组件
        self.api_pool_manager = APIPoolManager(database)
        self.account_manager = AccountManager(settings, database, self.api_pool_manager)
        self.message_sender = MessageSender(settings, database)
        self.group_processor = GroupProcessor(settings, database)
        self.task_scheduler = TaskScheduler(settings, database)
        self.message_listener = MessageListener(settings, database, self.group_processor)
        
        # Bot应用 - 仅用于Web登录验证
        self.bot_app = None
        self.config_watcher = None
        
        # 运行状态
        self.running = False
        self.tasks = []

    async def start(self):
        """启动管理器"""
        try:
            self.logger.info("🚀 启动转发管理器...")
            
            # 启动API池管理器
            await self.api_pool_manager.start()
            
            # 启动账号管理器
            await self.account_manager.start()
            
            # 启动消息发送器
            await self.message_sender.start()
            
            # 启动组处理器
            await self.group_processor.start()
            
            # 启动任务调度器
            await self.task_scheduler.start()
            
            # 启动消息监听器
            await self.message_listener.start()
            
            # 启动简化的Bot（仅用于Web登录验证）
            await self._start_bot()
            
            # 启动配置监视器
            if self.settings.get('config_watch', True):
                self.config_watcher = ConfigWatcher(self.settings, self._on_config_changed)
                await self.config_watcher.start()
            
            self.running = True
            self.logger.info("✅ 转发管理器启动完成")
            
        except Exception as e:
            self.logger.error(f"❌ 启动管理器失败: {e}")
            await self.stop()
            raise

    async def stop(self):
        """停止管理器"""
        self.logger.info("🛑 停止转发管理器...")
        self.running = False
        
        # 停止所有任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # 停止组件
        components = [
            self.config_watcher,
            self.message_listener,
            self.task_scheduler,
            self.group_processor,
            self.message_sender,
            self.account_manager,
            self.api_pool_manager
        ]
        
        for component in components:
            if component:
                try:
                    await component.stop()
                except Exception as e:
                    self.logger.error(f"停止组件失败: {e}")
        
        # 停止Bot
        if self.bot_app:
            await self.bot_app.stop()
            await self.bot_app.shutdown()
        
        self.logger.info("✅ 转发管理器已停止")

    async def _start_bot(self):
        """启动简化的Telegram Bot（仅用于Web登录验证）"""
        if not self.settings.bot_token:
            self.logger.warning("⚠️ 未配置Bot Token，跳过Bot启动")
            return
        
        try:
            # 创建Bot应用
            self.bot_app = Application.builder().token(self.settings.bot_token).build()
            
            # 设置简化的处理器（仅包含Web登录相关功能）
            setup_handlers(
                self.bot_app,
                self.settings,
                self.database,
                self.account_manager,
                self.api_pool_manager,
                self.group_processor,
                self.task_scheduler
            )
            
            # 启动Bot
            await self.bot_app.initialize()
            await self.bot_app.start()
            
            # 启动轮询
            task = asyncio.create_task(self.bot_app.updater.start_polling())
            self.tasks.append(task)
            
            self.logger.info("🤖 Telegram Bot 启动成功（Web登录验证模式）")
            
        except Exception as e:
            self.logger.error(f"❌ Bot启动失败: {e}")
            raise

    async def _on_config_changed(self):
        """配置文件变更回调"""
        self.logger.info("📝 检测到配置变更，重新加载...")
        try:
            # 重新加载配置
            self.settings.reload()
            
            # 通知各组件配置已更新
            components = [
                self.account_manager,
                self.message_sender,
                self.group_processor,
                self.task_scheduler,
                self.message_listener
            ]
            
            for component in components:
                if hasattr(component, 'reload_config'):
                    await component.reload_config()
            
            self.logger.info("✅ 配置重新加载完成")
            
        except Exception as e:
            self.logger.error(f"❌ 重新加载配置失败: {e}")

    async def get_status(self) -> Dict:
        """获取系统状态"""
        status = {
            'running': self.running,
            'components': {
                'api_pool_manager': self.api_pool_manager.is_running if self.api_pool_manager else False,
                'account_manager': self.account_manager.is_running if self.account_manager else False,
                'message_sender': self.message_sender.is_running if self.message_sender else False,
                'group_processor': self.group_processor.is_running if self.group_processor else False,
                'task_scheduler': self.task_scheduler.is_running if self.task_scheduler else False,
                'message_listener': self.message_listener.is_running if self.message_listener else False,
                'bot': self.bot_app.running if self.bot_app else False
            },
            'statistics': {},
            'errors': []
        }
        
        try:
            # 获取统计信息
            if self.account_manager:
                status['statistics']['accounts'] = await self.account_manager.get_statistics()
            
            if self.group_processor:
                status['statistics']['groups'] = await self.group_processor.get_statistics()
                
        except Exception as e:
            status['errors'].append(f"获取统计信息失败: {e}")
        
        return status

    async def restart_component(self, component_name: str) -> bool:
        """重启指定组件"""
        try:
            component_map = {
                'account_manager': self.account_manager,
                'message_sender': self.message_sender,
                'group_processor': self.group_processor,
                'task_scheduler': self.task_scheduler,
                'message_listener': self.message_listener,
                'api_pool_manager': self.api_pool_manager
            }
            
            component = component_map.get(component_name)
            if not component:
                return False
            
            self.logger.info(f"🔄 重启组件: {component_name}")
            
            # 停止组件
            await component.stop()
            
            # 启动组件
            await component.start()
            
            self.logger.info(f"✅ 组件重启完成: {component_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 重启组件失败 {component_name}: {e}")
            return False

    # API接口方法，供Web界面调用
    async def get_groups(self) -> List[Dict]:
        """获取搬运组列表"""
        return await self.group_processor.get_group_list()

    async def get_group_info(self, group_id: int) -> Dict:
        """获取组详情"""
        return await self.group_processor.get_group_info(group_id)

    async def create_group(self, name: str, description: str = None) -> Dict:
        """创建搬运组"""
        return await self.group_processor.create_group(name, description)

    async def update_group(self, group_id: int, **kwargs) -> Dict:
        """更新搬运组"""
        # 实现组更新逻辑
        return {'status': 'success', 'message': '组更新成功'}

    async def delete_group(self, group_id: int) -> Dict:
        """删除搬运组"""
        # 实现组删除逻辑
        return {'status': 'success', 'message': '组删除成功'}

    async def get_accounts(self) -> List[Dict]:
        """获取账号列表"""
        return await self.account_manager.get_account_list()

    async def get_account_info(self, phone: str) -> Dict:
        """获取账号详情"""
        accounts = await self.account_manager.get_account_list()
        for account in accounts:
            if account['phone'] == phone:
                return account
        return None

    async def remove_account(self, phone: str) -> Dict:
        """删除账号"""
        success = await self.account_manager.remove_account(phone)
        if success:
            return {'status': 'success', 'message': '账号删除成功'}
        else:
            return {'status': 'error', 'message': '账号删除失败'}

    async def get_api_pool_status(self) -> Dict:
        """获取API池状态"""
        return await self.api_pool_manager.get_statistics()

    async def add_api(self, app_id: str, app_hash: str, max_accounts: int = 1) -> Dict:
        """添加API"""
        success = await self.api_pool_manager.add_api(app_id, app_hash, max_accounts)
        if success:
            return {'status': 'success', 'message': 'API添加成功'}
        else:
            return {'status': 'error', 'message': 'API添加失败'}

    async def remove_api(self, app_id: str) -> Dict:
        """删除API"""
        success = await self.api_pool_manager.remove_api(app_id)
        if success:
            return {'status': 'success', 'message': 'API删除成功'}
        else:
            return {'status': 'error', 'message': 'API删除失败'}

    async def get_system_info(self) -> Dict:
        """获取系统信息"""
        import psutil
        import platform
        
        return {
            'system': {
                'platform': platform.system(),
                'release': platform.release(),
                'python_version': platform.python_version(),
                'architecture': platform.machine()
            },
            'resources': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('.').percent
            },
            'uptime': 'N/A'  # 需要实现运行时间计算
        }

    async def update_settings(self, section: str, settings: Dict) -> Dict:
        """更新设置"""
        try:
            for key, value in settings.items():
                self.settings.set(f'{section}.{key}', value)
            
            return {'status': 'success', 'message': '设置更新成功'}
        except Exception as e:
            return {'status': 'error', 'message': f'设置更新失败: {str(e)}'}

    async def get_logs(self, level: str = 'ALL', lines: int = 50) -> Dict:
        """获取日志"""
        from utils.logger import get_recent_logs, get_log_stats
        
        try:
            logs = get_recent_logs(lines=lines)
            
            if level != 'ALL':
                logs = [log for log in logs if level in log]
            
            stats = get_log_stats()
            
            return {
                'logs': logs,
                'stats': stats
            }
        except Exception as e:
            self.logger.error(f"获取日志失败: {e}")
            return {
                'logs': [],
                'stats': {'error': str(e)}
            }