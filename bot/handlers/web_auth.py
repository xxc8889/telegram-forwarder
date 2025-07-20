"""
Web认证命令处理器 - 简化的Bot处理器，专注于Web登录验证
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..middleware import admin_required, error_handler


class WebAuthHandlers:
    """Web认证处理器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)

    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令 - 显示Web管理界面入口"""
        
        welcome_text = """
🚀 **欢迎使用 Telegram Forwarder**

这是一个功能强大的消息搬运工具，支持：
• 多账号监听
• 智能过滤
• 定时调度
• 搬运组管理

现在所有管理功能都通过Web界面进行，请点击下方按钮进入管理后台。

💡 **使用提示**
1. 点击"打开管理后台"按钮
2. 在网页中获取登录码
3. 将登录码发送给我进行验证
4. 完成登录后即可使用Web管理界面
        """
        
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🌐 打开管理后台", url=self._get_web_url())],
            [InlineKeyboardButton("📊 查看系统状态", callback_data="status")],
            [InlineKeyboardButton("❓ 获取帮助", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    @admin_required
    @error_handler
    async def web_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Web管理界面命令"""
        
        web_text = """
🌐 **Web管理界面**

通过Web界面，您可以：
• 📋 管理搬运组和频道
• 👥 管理监听账号
• 🔧 配置过滤器和调度
• 📊 查看统计和日志
• ⚙️ 系统设置

请点击下方按钮访问管理界面：
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 进入管理后台", url=self._get_web_url())],
            [InlineKeyboardButton("🔑 登录帮助", callback_data="login_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            web_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    @admin_required
    @error_handler
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """系统状态命令"""
        try:
            # 获取系统状态（简化版）
            from core.manager import ForwarderManager
            
            if ForwarderManager.instance:
                status = await ForwarderManager.instance.get_status()
                
                status_text = f"""
📊 **系统状态总览**

🔧 **核心组件**
• 账号管理器: {'🟢 运行中' if status['components']['account_manager'] else '🔴 已停止'}
• 组处理器: {'🟢 运行中' if status['components']['group_processor'] else '🔴 已停止'}
• 消息监听器: {'🟢 运行中' if status['components']['message_listener'] else '🔴 已停止'}
• 任务调度器: {'🟢 运行中' if status['components']['task_scheduler'] else '🔴 已停止'}

📈 **统计信息**
• 总账号: {status['statistics'].get('accounts', {}).get('total', 0)}
• 活跃账号: {status['statistics'].get('accounts', {}).get('active', 0)}
• 搬运组: {status['statistics'].get('groups', {}).get('total_groups', 0)}

🌐 **Web管理界面**: [点击访问]({self._get_web_url()})
                """
            else:
                status_text = "❌ 系统未完全启动，请稍后重试"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            await update.message.reply_text("❌ 获取系统状态失败，请检查系统运行状态")

    @error_handler
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
❓ **使用帮助**

**🌐 Web管理**
本Bot已升级为Web管理模式，所有功能都通过Web界面操作：

**📱 Bot命令**
• `/start` - 开始使用，查看欢迎信息
• `/web` - 打开Web管理界面
• `/status` - 查看系统运行状态
• `/help` - 查看帮助信息

**🔑 Web登录流程**
1. 点击按钮或访问Web界面
2. 在登录页面点击"获取登录码"
3. 将6位数字登录码发送给我
4. 验证成功后自动跳转到管理界面

**💡 功能亮点**
• 搬运组管理：创建和配置不同的搬运任务
• 账号管理：添加和管理监听账号
• 智能过滤：多种过滤规则和广告检测
• 定时调度：设置搬运组的工作时间
• 实时监控：查看系统状态和日志

**🆘 需要帮助？**
• 访问Web界面获得完整功能
• 遇到问题请检查日志
• 确保网络连接正常
        """
        
        keyboard = [
            [InlineKeyboardButton("🌐 打开Web界面", url=self._get_web_url())],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    @error_handler
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理消息 - 主要用于Web登录验证"""
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        # 检查是否为管理员
        if user_id not in self.settings.admin_users:
            await update.message.reply_text(
                "❌ 您没有权限使用此Bot\n\n"
                "如需获得访问权限，请联系管理员"
            )
            return
        
        # 检查是否为6位数字登录码
        if len(message_text) == 6 and message_text.isdigit():
            await self._handle_web_login_code(update, message_text, user_id)
            return
        
        # 其他消息的默认回复
        await update.message.reply_text(
            "💡 **提示**\n\n"
            "请使用 /start 查看可用功能，或访问Web管理界面进行完整操作。\n\n"
            "如果您要进行Web登录，请发送6位数字登录码。",
            parse_mode='Markdown'
        )

    async def _handle_web_login_code(self, update: Update, login_code: str, user_id: int):
        """处理Web登录码"""
        try:
            # 导入Web认证管理器
            from web.auth import get_auth_manager
            
            auth_manager = get_auth_manager()
            if not auth_manager:
                await update.message.reply_text("❌ Web服务未启用")
                return
            
            # 验证登录码
            if auth_manager.verify_login_code_from_bot(login_code, user_id):
                await update.message.reply_text(
                    "✅ **Web登录验证成功！**\n\n"
                    "🌐 您现在可以在浏览器中访问管理后台了\n"
                    "📱 页面将自动跳转到仪表板\n\n"
                    "🔒 为了安全，建议完成操作后及时退出登录",
                    parse_mode='Markdown'
                )
                
                self.logger.info(f"Web登录验证成功: 用户{user_id}, 登录码{login_code}")
                
            else:
                await update.message.reply_text(
                    "❌ **登录码验证失败**\n\n"
                    "可能原因：\n"
                    "• 登录码已过期（5分钟有效期）\n"
                    "• 登录码不正确\n"
                    "• 登录码已使用过\n\n"
                    "💡 请重新在网页上获取新的登录码"
                )
                
        except Exception as e:
            self.logger.error(f"Web登录码处理失败: {e}")
            await update.message.reply_text(
                "❌ 处理登录码时发生错误\n\n"
                "请稍后重试或联系管理员"
            )

    def _get_web_url(self) -> str:
        """获取Web界面URL"""
        host = os.getenv('WEB_HOST', '0.0.0.0')
        port = os.getenv('WEB_PORT', '8080')
        
        # 如果host是0.0.0.0，替换为localhost或实际IP
        if host == '0.0.0.0':
            host = 'localhost'
        
        return f"http://{host}:{port}"

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "status":
            await self.status_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "login_help":
            await self._show_login_help(update)

    async def _show_login_help(self, update: Update):
        """显示登录帮助"""
        help_text = """
🔑 **Web登录帮助**

**登录步骤：**
1. 点击"进入管理后台"按钮或直接访问Web地址
2. 在登录页面点击"获取登录码"
3. 复制显示的6位数字登录码
4. 在这个对话中直接发送登录码（只发数字即可）
5. 验证成功后，网页会自动跳转到管理界面

**注意事项：**
• 登录码有效期为5分钟
• 每个登录码只能使用一次
• 确保您有管理员权限
• 建议使用Chrome或Firefox浏览器

**常见问题：**
• 如果页面无法打开，请检查网络连接
• 登录码过期请重新获取
• 验证失败请确认登录码正确

**Web地址：** {self._get_web_url()}
        """
        
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode='Markdown'
        )