"""
Bot中间件 - 权限验证等
"""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes


def admin_required(func):
    """管理员权限装饰器"""
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # 检查是否为管理员
        if user_id not in self.settings.admin_users:
            await update.message.reply_text(
                "❌ 权限不足\n只有管理员可以使用此功能"
            )
            logging.warning(f"非管理员用户尝试访问: {user_id}")
            return
        
        # 记录管理员操作
        command = update.message.text.split()[0] if update.message.text else "unknown"
        logging.info(f"管理员操作: {user_id} - {command}")
        
        # 执行原函数
        return await func(self, update, context)
    
    return wrapper


def error_handler(func):
    """错误处理装饰器"""
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            return await func(self, update, context)
        except Exception as e:
            logging.error(f"命令处理错误: {e}")
            await update.message.reply_text(
                f"❌ 处理命令时发生错误:\n{str(e)}"
            )
    
    return wrapper


def rate_limit(max_calls: int = 10, window: int = 60):
    """速率限制装饰器"""
    call_times = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            import time
            
            user_id = update.effective_user.id
            current_time = time.time()
            
            # 清理过期记录
            if user_id in call_times:
                call_times[user_id] = [
                    call_time for call_time in call_times[user_id]
                    if current_time - call_time < window
                ]
            else:
                call_times[user_id] = []
            
            # 检查速率限制
            if len(call_times[user_id]) >= max_calls:
                await update.message.reply_text(
                    f"⚠️ 操作过于频繁\n请等待 {window} 秒后再试"
                )
                return
            
            # 记录调用时间
            call_times[user_id].append(current_time)
            
            # 执行原函数
            return await func(self, update, context)
        
        return wrapper
    return decorator