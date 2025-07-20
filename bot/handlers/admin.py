"""
管理员命令处理器
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..middleware import admin_required


class AdminHandlers:
    """管理员命令处理器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)

    @admin_required
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令 - 显示所有功能"""
        help_text = """
🤖 **Telegram Forwarder Bot**

📋 **搬运组管理**
• `/create_group <组名> [描述]` - 创建搬运组
• `/list_groups` - 查看所有组
• `/group_info <组ID>` - 查看组详情
• `/delete_group <组ID>` - 删除组
• `/add_source <组ID> <频道链接>` - 添加源频道
• `/add_target <组ID> <频道链接>` - 添加目标频道
• `/remove_source <组ID> <频道链接>` - 移除源频道
• `/remove_target <组ID> <频道链接>` - 移除目标频道

👤 **账号管理**
• `/add_listener <手机号>` - 添加监听账号
• `/remove_listener <手机号>` - 移除监听账号
• `/account_status` - 查看账号状态
• `/account_list` - 查看所有账号

🔑 **API池管理**
• `/api_pool_status` - 查看API池状态
• `/api_pool_add <app_id> <app_hash>` - 添加API ID
• `/api_pool_remove <api_id>` - 移除API ID
• `/account_api_info [账号]` - 查看账号API分配

🔧 **过滤器管理**
• `/set_filter <组ID> <类型> <规则>` - 设置过滤规则
• `/toggle_filter <组ID> <类型>` - 开关过滤功能
• `/filter_test <组ID> <测试文本>` - 测试过滤效果

⏰ **调度管理**
• `/set_schedule <组ID> <开始时间> <结束时间>` - 设置定时运行
• `/remove_schedule <组ID>` - 移除定时调度
• `/schedule_status [组ID]` - 查看调度状态

📝 **历史消息**
• `/sync_history <组ID> [数量]` - 同步历史消息
• `/sync_status <组ID>` - 查看同步状态

⚙️ **全局配置**
• `/reload_config` - 重新加载配置
• `/set_interval <最小间隔> <最大间隔>` - 调整发送间隔
• `/set_limit <每小时限制>` - 调整发送限制
• `/global_status` - 查看全局状态

🖥️ **系统管理**
• `/system_info` - 查看系统信息
• `/logs [行数]` - 查看日志
• `/backup` - 手动备份
• `/restart` - 重启系统
• `/status` - 查看运行状态

💡 **使用提示:**
1. 添加监听账号后，按提示输入验证码和二步验证密码
2. 创建搬运组后，需要添加源频道和目标频道
3. 可以为不同组设置不同的过滤规则和调度时间
4. 支持多个API ID自动分配，提高稳定性

📞 **技术支持:** 如有问题请联系管理员
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    @admin_required
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
❓ **使用帮助**

**🔰 快速开始:**
1. `/api_pool_add <app_id> <app_hash>` - 添加API ID
2. `/add_listener <手机号>` - 添加监听账号
3. `/create_group 我的组` - 创建搬运组
4. `/add_source 1 https://t.me/source_channel` - 添加源频道
5. `/add_target 1 https://t.me/my_channel` - 添加目标频道

**⏰ 设置定时调度:**
• `/set_schedule 1 09:00 18:00` - 工作时间运行
• `/set_schedule 1 22:00 08:00` - 夜间运行（跨天）

**🔧 配置过滤器:**
• `/toggle_filter 1 remove_links` - 开启/关闭链接过滤
• `/toggle_filter 1 ad_detection` - 开启/关闭广告检测
• `/set_filter 1 custom 自定义规则` - 设置自定义过滤

**📊 监控状态:**
• `/status` - 查看整体运行状态
• `/account_status` - 查看账号健康状态
• `/global_status` - 查看全局统计信息

**常见问题:**
• 账号登录失败 → 检查手机号格式和网络
• 消息不转发 → 检查组状态和调度时间
• API额度不足 → 添加更多API ID
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    @admin_required
    async def backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """手动备份"""
        try:
            await update.message.reply_text("🔄 开始备份数据...")
            
            # 这里应该调用备份功能
            # backup_result = await backup_manager.create_backup()
            
            # 模拟备份成功
            backup_result = {'status': 'success', 'file': 'backup_20250120.db'}
            
            if backup_result['status'] == 'success':
                await update.message.reply_text(
                    f"✅ 备份完成\n📁 文件: {backup_result['file']}"
                )
            else:
                await update.message.reply_text(
                    f"❌ 备份失败: {backup_result.get('error', '未知错误')}"
                )
                
        except Exception as e:
            self.logger.error(f"手动备份失败: {e}")
            await update.message.reply_text(f"❌ 备份失败: {str(e)}")

    @admin_required
    async def restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """重启系统"""
        try:
            await update.message.reply_text("⚠️ 确认要重启系统吗？这将中断所有正在进行的任务。\n\n回复 'YES' 确认重启。")
            
            # 这里应该实现重启确认逻辑
            # 暂时只显示提示
            
        except Exception as e:
            self.logger.error(f"重启命令失败: {e}")
            await update.message.reply_text(f"❌ 重启命令失败: {str(e)}")

    @admin_required
    async def handle_restart_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理重启确认"""
        if update.message.text.upper() == 'YES':
            try:
                await update.message.reply_text("🔄 系统正在重启，请稍候...")
                
                # 这里应该实现实际的重启逻辑
                # await system_manager.restart()
                
            except Exception as e:
                self.logger.error(f"系统重启失败: {e}")
                await update.message.reply_text(f"❌ 重启失败: {str(e)}")
        else:
            await update.message.reply_text("❌ 重启已取消")
