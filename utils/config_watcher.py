"""
配置监视器 - 监控配置文件变化
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ConfigWatcher:
    """配置文件监视器"""
    
    def __init__(self, settings, callback: Callable):
        self.settings = settings
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        self.observer = Observer()
        self.is_running = False

    async def start(self):
        """启动配置监视器"""
        try:
            event_handler = ConfigFileHandler(self.callback)
            
            # 监视配置文件
            config_file = Path(self.settings.config_file)
            if config_file.exists():
                self.observer.schedule(
                    event_handler,
                    str(config_file.parent),
                    recursive=False
                )
            
            # 监视.env文件
            env_file = Path('.env')
            if env_file.exists():
                self.observer.schedule(
                    event_handler,
                    str(env_file.parent),
                    recursive=False
                )
            
            self.observer.start()
            self.is_running = True
            self.logger.info("📁 配置文件监视器启动完成")
            
        except Exception as e:
            self.logger.error(f"❌ 启动配置监视器失败: {e}")

    async def stop(self):
        """停止配置监视器"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        self.logger.info("📁 配置文件监视器已停止")


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件事件处理器"""
    
    def __init__(self, callback):
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        self.last_modified = {}

    def on_modified(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            
            # 只监控特定文件
            if file_path.name in ['config.yaml', '.env']:
                # 防止重复触发
                import time
                current_time = time.time()
                last_time = self.last_modified.get(file_path, 0)
                
                if current_time - last_time > 1:  # 1秒内的重复事件忽略
                    self.last_modified[file_path] = current_time
                    self.logger.info(f"📝 检测到配置文件变更: {file_path.name}")
                    
                    # 异步调用回调
                    asyncio.create_task(self.callback())