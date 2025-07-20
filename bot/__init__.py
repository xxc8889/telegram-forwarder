"""
Bot命令处理器 - 简化版，仅用于Web登录验证
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import BotCommand

from .handlers.web_auth import WebAuthHandlers
from .middleware import admin_required


def setup_handlers(app: Application, settings, database, account_manager, 
                  api_pool_manager, group_processor, task_scheduler):
    """设置Bot处理器 - 简化版"""
    
    # 初始化Web认证处理器
    web_auth_handler = WebAuthHandlers(settings, database)
    
    # 添加命令处理器
    app.add_handler(CommandHandler("start", web_auth_handler.start_command))
    app.add_handler(CommandHandler("help", web_auth_handler.help_command))
    app.add_handler(CommandHandler("web", web_auth_handler.web_command))
    app.add_handler(CommandHandler("status", web_auth_handler.status_command))
    
    # Web登录验证相关 - 处理所有非命令消息
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        web_auth_handler.handle_message
    ))
    
    # 设置Bot菜单
    setup_bot_menu(app)


async def setup_bot_menu(app: Application):
    """设置Bot命令菜单"""
    commands = [
        BotCommand("start", "开始使用"),
        BotCommand("web", "打开Web管理界面"),
        BotCommand("status", "查看系统状态"),
        BotCommand("help", "获取帮助信息"),
    ]
    
    try:
        await app.bot.set_my_commands(commands)
    except Exception as e:
        print(f"设置Bot菜单失败: {e}")
