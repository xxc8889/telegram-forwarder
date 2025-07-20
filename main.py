#!/usr/bin/env python3
"""
Telegram Forwarder - 主程序入口
多账号、多API池、搬运组管理的Telegram频道转发工具
支持Web管理界面
"""

import asyncio
import signal
import sys
import os
import logging
import threading
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from config.database import Database
from core.manager import ForwarderManager
from utils.logger import setup_logging
from web.app import WebApp
from web.auth import set_auth_manager, AuthManager


class TelegramForwarder:
    def __init__(self):
        self.settings = Settings()
        self.database = Database()
        self.manager = None
        self.web_app = None
        self.running = False
        self.web_thread = None

    async def start(self):
        """启动转发程序"""
        try:
            # 设置日志
            setup_logging(self.settings.log_level, self.settings.log_file)
            logger = logging.getLogger(__name__)
            
            logger.info("🚀 Telegram Forwarder 启动中...")
            
            # 创建必要的目录
            self._create_directories()
            
            # 初始化数据库
            await self.database.init()
            logger.info("✅ 数据库初始化完成")
            
            # 初始化核心管理器
            self.manager = ForwarderManager(self.settings, self.database)
            await self.manager.start()
            
            # 启动Web管理界面
            await self._start_web_interface()
            
            self.running = True
            logger.info("🎉 Telegram Forwarder 启动成功!")
            logger.info(f"📊 管理员用户: {self.settings.admin_users}")
            logger.info(f"📁 数据目录: {Path('data').absolute()}")
            logger.info(f"🌐 Web管理界面: http://0.0.0.0:8080")
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logging.error(f"❌ 启动失败: {e}")
            sys.exit(1)

    async def _start_web_interface(self):
        """启动Web管理界面"""
        try:
            # 创建认证管理器
            auth_manager = AuthManager(self.settings)
            set_auth_manager(auth_manager)
            
            # 创建Web应用
            self.web_app = WebApp(self.settings, self.database)
            
            # 在单独线程中运行Web应用
            def run_web():
                self.web_app.run(
                    host=os.getenv('WEB_HOST', '0.0.0.0'),
                    port=int(os.getenv('WEB_PORT', 8080)),
                    debug=os.getenv('WEB_DEBUG', 'False').lower() == 'true'
                )
            
            self.web_thread = threading.Thread(target=run_web, daemon=True)
            self.web_thread.start()
            
            logging.info("🌐 Web管理界面启动成功")
            
        except Exception as e:
            logging.error(f"❌ Web界面启动失败: {e}")

    async def stop(self):
        """停止转发程序"""
        logger = logging.getLogger(__name__)
        logger.info("🛑 正在停止 Telegram Forwarder...")
        
        self.running = False
        
        if self.manager:
            await self.manager.stop()
            
        await self.database.close()
        logger.info("👋 Telegram Forwarder 已停止")

    def _create_directories(self):
        """创建必要的目录"""
        directories = ['data', 'logs', 'sessions', 'backup', 'web/static', 'web/templates']
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def signal_handler(self, signum, frame):
        """信号处理器"""
        print(f"\n收到信号 {signum}, 正在安全退出...")
        asyncio.create_task(self.stop())


async def main():
    """主函数"""
    forwarder = TelegramForwarder()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, forwarder.signal_handler)
    signal.signal(signal.SIGTERM, forwarder.signal_handler)
    
    try:
        await forwarder.start()
    except KeyboardInterrupt:
        await forwarder.stop()
    except Exception as e:
        logging.error(f"程序异常退出: {e}")
        await forwarder.stop()
        sys.exit(1)


if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 程序异常: {e}")
        sys.exit(1)