"""
日志工具 - 配置和管理日志系统
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import colorama
from colorama import Fore, Style


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """设置日志系统"""
    
    # 初始化颜色支持
    colorama.init()
    
    # 创建日志目录
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式器
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    
    # 输出启动信息
    logger = logging.getLogger(__name__)
    logger.info(f"🚀 日志系统初始化完成 - 级别: {level}")
    if log_file:
        logger.info(f"📁 日志文件: {log_file}")


class ColoredFormatter(logging.Formatter):
    """彩色日志格式器"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA
    }
    
    def format(self, record):
        # 保存原始颜色
        original_msg = record.getMessage()
        
        # 添加颜色
        color = self.COLORS.get(record.levelname, '')
        if color:
            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        
        # 格式化消息
        formatted = super().format(record)
        
        # 重置消息
        record.msg = original_msg
        
        return formatted


class TelegramLogHandler(logging.Handler):
    """Telegram日志处理器 - 将重要日志发送到管理员"""
    
    def __init__(self, bot_token: str, admin_chat_ids: list, level=logging.ERROR):
        super().__init__(level)
        self.bot_token = bot_token
        self.admin_chat_ids = admin_chat_ids
        self._bot = None
        
    async def _get_bot(self):
        """获取Bot实例"""
        if not self._bot:
            from telegram import Bot
            self._bot = Bot(token=self.bot_token)
        return self._bot
    
    def emit(self, record):
        """发送日志消息"""
        try:
            import asyncio
            
            # 格式化消息
            message = self.format(record)
            
            # 添加emoji
            if record.levelno >= logging.CRITICAL:
                emoji = "🔥"
            elif record.levelno >= logging.ERROR:
                emoji = "❌"
            elif record.levelno >= logging.WARNING:
                emoji = "⚠️"
            else:
                emoji = "ℹ️"
            
            # 构建Telegram消息
            telegram_message = f"{emoji} **{record.levelname}**\n\n`{message}`"
            
            # 发送消息
            asyncio.create_task(self._send_message(telegram_message))
            
        except Exception:
            self.handleError(record)
    
    async def _send_message(self, message: str):
        """发送消息到Telegram"""
        try:
            bot = await self._get_bot()
            
            for chat_id in self.admin_chat_ids:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"发送日志消息失败 {chat_id}: {e}")
                    
        except Exception as e:
            print(f"Telegram日志处理器错误: {e}")


def get_log_stats(log_file: str = None) -> dict:
    """获取日志统计信息"""
    try:
        if not log_file:
            log_file = "logs/forwarder.log"
        
        log_path = Path(log_file)
        if not log_path.exists():
            return {"error": "日志文件不存在"}
        
        # 读取日志文件
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 统计各级别日志数量
        stats = {
            'total_lines': len(lines),
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0,
            'file_size': log_path.stat().st_size,
            'last_modified': log_path.stat().st_mtime
        }
        
        for line in lines:
            for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                if f'- {level} -' in line:
                    stats[level] += 1
                    break
        
        return stats
        
    except Exception as e:
        return {"error": f"获取日志统计失败: {e}"}


def get_recent_logs(log_file: str = None, lines: int = 100) -> list:
    """获取最近的日志"""
    try:
        if not log_file:
            log_file = "logs/forwarder.log"
        
        log_path = Path(log_file)
        if not log_path.exists():
            return ["日志文件不存在"]
        
        # 读取最后N行
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # 返回最后N行
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return [line.strip() for line in recent_lines]
        
    except Exception as e:
        return [f"获取日志失败: {e}"]


def filter_logs_by_level(log_file: str = None, level: str = "ERROR", lines: int = 50) -> list:
    """按级别过滤日志"""
    try:
        if not log_file:
            log_file = "logs/forwarder.log"
        
        log_path = Path(log_file)
        if not log_path.exists():
            return ["日志文件不存在"]
        
        # 读取日志文件
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # 过滤指定级别的日志
        filtered_lines = []
        for line in all_lines:
            if f'- {level.upper()} -' in line:
                filtered_lines.append(line.strip())
        
        # 返回最后N行
        recent_filtered = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines
        
        return recent_filtered
        
    except Exception as e:
        return [f"过滤日志失败: {e}"]


def setup_telegram_log_handler(bot_token: str, admin_chat_ids: list, level: str = "ERROR"):
    """设置Telegram日志处理器"""
    try:
        # 获取根日志器
        root_logger = logging.getLogger()
        
        # 创建Telegram处理器
        telegram_handler = TelegramLogHandler(
            bot_token=bot_token,
            admin_chat_ids=admin_chat_ids,
            level=getattr(logging, level.upper(), logging.ERROR)
        )
        
        # 设置格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        telegram_handler.setFormatter(formatter)
        
        # 添加处理器
        root_logger.addHandler(telegram_handler)
        
        logger = logging.getLogger(__name__)
        logger.info("📱 Telegram日志处理器已启用")
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"❌ 设置Telegram日志处理器失败: {e}")