"""
配置管理命令处理器
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..middleware import admin_required, error_handler


class ConfigHandlers:
    """配置管理处理器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)

    @admin_required
    @error_handler
    async def reload_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """重新加载配置"""
        try:
            # 重新加载配置
            self.settings.reload()
            
            await update.message.reply_text(
                "✅ 配置已重新加载\n\n"
                "所有组件将在下次操作时使用新配置"
            )
            
        except Exception as e:
            self.logger.error(f"重新加载配置失败: {e}")
            await update.message.reply_text(f"❌ 重新加载失败: {str(e)}")

    @admin_required
    @error_handler
    async def set_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置发送间隔"""
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ 请提供最小和最大间隔时间\n\n"
                "用法: `/set_interval 3 30`\n"
                "单位: 秒",
                parse_mode='Markdown'
            )
            return
        
        try:
            min_interval = int(args[0])
            max_interval = int(args[1])
            
            if min_interval <= 0 or max_interval <= 0:
                await update.message.reply_text("❌ 间隔时间必须大于0")
                return
            
            if min_interval > max_interval:
                await update.message.reply_text("❌ 最小间隔不能大于最大间隔")
                return
            
            # 更新配置
            self.settings.set('global_settings.min_interval', min_interval)
            self.settings.set('global_settings.max_interval', max_interval)
            
            await update.message.reply_text(
                f"✅ 发送间隔已更新\n\n"
                f"最小间隔: {min_interval}秒\n"
                f"最大间隔: {max_interval}秒"
            )
            
        except ValueError:
            await update.message.reply_text("❌ 间隔时间必须是数字")
        except Exception as e:
            self.logger.error(f"设置发送间隔失败: {e}")
            await update.message.reply_text(f"❌ 设置失败: {str(e)}")

    @admin_required
    @error_handler
    async def set_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置每小时发送限制"""
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ 请提供每小时发送限制\n\n"
                "用法: `/set_limit 50`",
                parse_mode='Markdown'
            )
            return
        
        try:
            hourly_limit = int(args[0])
            
            if hourly_limit <= 0:
                await update.message.reply_text("❌ 发送限制必须大于0")
                return
            
            if hourly_limit > 1000:
                await update.message.reply_text("❌ 发送限制不建议超过1000")
                return
            
            # 更新配置
            self.settings.set('global_settings.hourly_limit', hourly_limit)
            
            await update.message.reply_text(
                f"✅ 每小时发送限制已更新: {hourly_limit}条"
            )
            
        except ValueError:
            await update.message.reply_text("❌ 发送限制必须是数字")
        except Exception as e:
            self.logger.error(f"设置发送限制失败: {e}")
            await update.message.reply_text(f"❌ 设置失败: {str(e)}")

    @admin_required
    @error_handler
    async def show_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示当前配置"""
        try:
            config_info = f"""
⚙️ **当前配置**

**全局设置**
• 最小间隔: {self.settings.min_interval}秒
• 最大间隔: {self.settings.max_interval}秒
• 每小时限制: {self.settings.hourly_limit}条
• 重试次数: {self.settings.retry_attempts}

**轮换策略**
• 策略: {self.settings.rotation_strategy}
• 消息轮换数: {self.settings.messages_per_rotation}
• 时间轮换间隔: {self.settings.time_per_rotation}分钟

**过滤设置**
• 删除链接: {'✅' if self.settings.remove_links else '❌'}
• 删除表情: {'✅' if self.settings.remove_emojis else '❌'}
• 删除特殊符号: {'✅' if self.settings.remove_special_chars else '❌'}
• 广告检测: {'✅' if self.settings.ad_detection else '❌'}
• 智能过滤: {'✅' if self.settings.smart_filter else '❌'}

**安全设置**
• Session加密: {'✅' if self.settings.session_encryption else '❌'}
• 自动备份: {'✅' if self.settings.backup_enabled else '❌'}
• 日志保留: {self.settings.log_retention_days}天
            """
            
            await update.message.reply_text(config_info, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"显示配置失败: {e}")
            await update.message.reply_text(f"❌ 获取配置失败: {str(e)}")

    @admin_required
    @error_handler
    async def set_rotation_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置轮换策略"""
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ 请提供轮换策略\n\n"
                "用法: `/set_rotation_strategy message`\n"
                "策略: message, time, smart",
                parse_mode='Markdown'
            )
            return
        
        try:
            strategy = args[0].lower()
            valid_strategies = ['message', 'time', 'smart']
            
            if strategy not in valid_strategies:
                await update.message.reply_text(
                    f"❌ 无效的轮换策略\n支持: {', '.join(valid_strategies)}"
                )
                return
            
            # 更新配置
            self.settings.set('rotation.strategy', strategy)
            
            strategy_desc = {
                'message': '每条消息轮换',
                'time': '按时间间隔轮换',
                'smart': '智能轮换'
            }
            
            await update.message.reply_text(
                f"✅ 轮换策略已更新: {strategy_desc[strategy]}"
            )
            
        except Exception as e:
            self.logger.error(f"设置轮换策略失败: {e}")
            await update.message.reply_text(f"❌ 设置失败: {str(e)}")

    @admin_required
    @error_handler
    async def backup_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """备份配置"""
        try:
            import shutil
            import datetime
            from pathlib import Path
            
            # 创建备份目录
            backup_dir = Path('backup/config')
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成备份文件名
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 备份配置文件
            config_files = ['.env', 'config.yaml']
            backed_up = []
            
            for config_file in config_files:
                if Path(config_file).exists():
                    backup_file = backup_dir / f'{config_file}.{timestamp}'
                    shutil.copy2(config_file, backup_file)
                    backed_up.append(config_file)
            
            if backed_up:
                await update.message.reply_text(
                    f"✅ 配置备份完成\n\n"
                    f"备份文件: {', '.join(backed_up)}\n"
                    f"备份时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                await update.message.reply_text("❌ 没有找到配置文件")
                
        except Exception as e:
            self.logger.error(f"备份配置失败: {e}")
            await update.message.reply_text(f"❌ 备份失败: {str(e)}")

    @admin_required
    @error_handler
    async def reset_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """重置配置为默认值"""
        try:
            await update.message.reply_text(
                "⚠️ **警告**\n\n"
                "此操作将重置所有配置为默认值，无法撤销！\n\n"
                "回复 'YES' 确认重置配置",
                parse_mode='Markdown'
            )
            
            # 这里应该实现确认机制
            # 暂时只显示警告
            
        except Exception as e:
            self.logger.error(f"重置配置失败: {e}")
            await update.message.reply_text(f"❌ 重置失败: {str(e)}")