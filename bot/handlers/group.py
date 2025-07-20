"""
搬运组管理命令处理器
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from ..middleware import admin_required, error_handler


class GroupHandlers:
    """搬运组管理处理器"""
    
    def __init__(self, settings, database, group_processor):
        self.settings = settings
        self.database = database
        self.group_processor = group_processor
        self.logger = logging.getLogger(__name__)

    @admin_required
    @error_handler
    async def create_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """创建搬运组"""
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ 请提供组名\n\n用法: `/create_group 新闻组 搬运新闻内容`",
                parse_mode='Markdown'
            )
            return
        
        name = args[0]
        description = ' '.join(args[1:]) if len(args) > 1 else None
        
        try:
            result = await self.group_processor.create_group(name, description)
            
            if result['status'] == 'success':
                await update.message.reply_text(
                    f"✅ {result['message']}\n\n"
                    f"组ID: {result['group_id']}\n"
                    f"下一步: 添加源频道和目标频道\n"
                    f"`/add_source {result['group_id']} 频道链接`\n"
                    f"`/add_target {result['group_id']} 频道链接`",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except Exception as e:
            self.logger.error(f"创建搬运组失败: {e}")
            await update.message.reply_text(f"❌ 创建失败: {str(e)}")

    @admin_required
    @error_handler
    async def list_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看所有搬运组"""
        try:
            groups = await self.group_processor.get_group_list()
            
            if not groups:
                await update.message.reply_text("📋 暂无搬运组")
                return
            
            groups_text = "📋 **搬运组列表**\n\n"
            
            for group in groups:
                status_emoji = "🟢" if group['status'] == 'active' else "🔴"
                groups_text += f"{status_emoji} **{group['name']}** (ID: {group['id']})\n"
                
                if group['description']:
                    groups_text += f"   📝 {group['description']}\n"
                
                groups_text += f"   📡 源频道: {group['channels']['source_count']}\n"
                groups_text += f"   📤 目标频道: {group['channels']['target_count']}\n"
                
                if group['schedule']['start']:
                    groups_text += f"   ⏰ 调度: {group['schedule']['start']}-{group['schedule']['end']}\n"
                
                stats = group['today_stats']
                groups_text += f"   📊 今日: {stats['messages']}条消息, {stats['success_rate']}%成功率\n\n"
            
            await update.message.reply_text(groups_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取搬运组列表失败: {e}")
            await update.message.reply_text(f"❌ 获取列表失败: {str(e)}")

    @admin_required
    @error_handler
    async def group_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看组详情"""
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ 请提供组ID\n\n用法: `/group_info 1`",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            group_info = await self.group_processor.get_group_info(group_id)
            
            if not group_info:
                await update.message.reply_text(f"❌ 组ID {group_id} 不存在")
                return
            
            info_text = f"📋 **搬运组详情**\n\n"
            info_text += f"**基本信息**\n"
            info_text += f"• 组名: {group_info['name']}\n"
            info_text += f"• 组ID: {group_info['id']}\n"
            info_text += f"• 状态: {group_info['status']}\n"
            
            if group_info['description']:
                info_text += f"• 描述: {group_info['description']}\n"
            
            # 调度信息
            if group_info['schedule']['start']:
                info_text += f"• 调度: {group_info['schedule']['start']}-{group_info['schedule']['end']}\n"
            else:
                info_text += f"• 调度: 全天运行\n"
            
            # 源频道
            info_text += f"\n**源频道 ({len(group_info['source_channels'])}个)**\n"
            for channel in group_info['source_channels']:
                info_text += f"• {channel.get('channel_title', channel['channel_id'])}\n"
            
            # 目标频道
            info_text += f"\n**目标频道 ({len(group_info['target_channels'])}个)**\n"
            for channel in group_info['target_channels']:
                info_text += f"• {channel.get('channel_title', channel['channel_id'])}\n"
            
            # 过滤设置
            filters = group_info['filters']
            info_text += f"\n**过滤设置**\n"
            info_text += f"• 删除链接: {'✅' if filters.get('remove_links') else '❌'}\n"
            info_text += f"• 删除表情: {'✅' if filters.get('remove_emojis') else '❌'}\n"
            info_text += f"• 删除特殊符号: {'✅' if filters.get('remove_special_chars') else '❌'}\n"
            info_text += f"• 广告检测: {'✅' if filters.get('ad_detection') else '❌'}\n"
            info_text += f"• 智能过滤: {'✅' if filters.get('smart_filter') else '❌'}\n"
            
            if group_info['footer']:
                info_text += f"\n**小尾巴**\n{group_info['footer']}\n"
            
            await update.message.reply_text(info_text, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"获取组详情失败: {e}")
            await update.message.reply_text(f"❌ 获取详情失败: {str(e)}")

    @admin_required
    @error_handler
    async def add_source(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """添加源频道"""
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ 请提供组ID和频道链接\n\n用法: `/add_source 1 https://t.me/news_channel`",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            channel_link = args[1]
            
            # 解析频道链接获取ID
            channel_id, channel_username = self._parse_channel_link(channel_link)
            
            if not channel_id:
                await update.message.reply_text("❌ 无效的频道链接")
                return
            
            result = await self.group_processor.add_source_channel(
                group_id, channel_id, channel_username
            )
            
            if result['status'] == 'success':
                await update.message.reply_text(f"✅ {result['message']}")
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"添加源频道失败: {e}")
            await update.message.reply_text(f"❌ 添加失败: {str(e)}")

    @admin_required
    @error_handler
    async def add_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """添加目标频道"""
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ 请提供组ID和频道链接\n\n用法: `/add_target 1 https://t.me/my_channel`",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            channel_link = args[1]
            
            # 解析频道链接获取ID
            channel_id, channel_username = self._parse_channel_link(channel_link)
            
            if not channel_id:
                await update.message.reply_text("❌ 无效的频道链接")
                return
            
            result = await self.group_processor.add_target_channel(
                group_id, channel_id, channel_username
            )
            
            if result['status'] == 'success':
                await update.message.reply_text(f"✅ {result['message']}")
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"添加目标频道失败: {e}")
            await update.message.reply_text(f"❌ 添加失败: {str(e)}")

    @admin_required
    @error_handler
    async def set_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置过滤规则"""
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ 请提供组ID和过滤类型\n\n"
                "用法: `/set_filter 1 remove_links true`\n"
                "过滤类型: remove_links, remove_emojis, remove_special_chars, ad_detection, smart_filter",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            filter_type = args[1]
            enabled = args[2].lower() == 'true' if len(args) > 2 else True
            
            valid_filters = ['remove_links', 'remove_emojis', 'remove_special_chars', 'ad_detection', 'smart_filter']
            
            if filter_type not in valid_filters:
                await update.message.reply_text(f"❌ 无效的过滤类型，支持: {', '.join(valid_filters)}")
                return
            
            result = await self.group_processor.set_group_filter(group_id, filter_type, enabled)
            
            if result['status'] == 'success':
                status = "开启" if enabled else "关闭"
                await update.message.reply_text(f"✅ 已{status}过滤器: {filter_type}")
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"设置过滤器失败: {e}")
            await update.message.reply_text(f"❌ 设置失败: {str(e)}")

    @admin_required
    @error_handler
    async def toggle_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开关过滤功能"""
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ 请提供组ID和过滤类型\n\n用法: `/toggle_filter 1 ad_detection`",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            filter_type = args[1]
            
            # 获取当前状态
            group_info = await self.group_processor.get_group_info(group_id)
            if not group_info:
                await update.message.reply_text(f"❌ 组ID {group_id} 不存在")
                return
            
            current_status = group_info['filters'].get(filter_type, False)
            new_status = not current_status
            
            result = await self.group_processor.set_group_filter(group_id, filter_type, new_status)
            
            if result['status'] == 'success':
                status = "开启" if new_status else "关闭"
                await update.message.reply_text(f"✅ 已{status}过滤器: {filter_type}")
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"切换过滤器失败: {e}")
            await update.message.reply_text(f"❌ 切换失败: {str(e)}")

    @admin_required
    @error_handler
    async def set_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置组调度"""
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "❌ 请提供组ID、开始时间和结束时间\n\n"
                "用法: `/set_schedule 1 09:00 18:00`\n"
                "跨天: `/set_schedule 1 22:00 08:00`",
                parse_mode='Markdown'
            )
            return
        
        try:
            group_id = int(args[0])
            start_time = args[1]
            end_time = args[2]
            
            # 验证时间格式
            time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
            if not time_pattern.match(start_time) or not time_pattern.match(end_time):
                await update.message.reply_text("❌ 时间格式错误，请使用 HH:MM 格式")
                return
            
            result = await self.group_processor.set_group_schedule(group_id, start_time, end_time)
            
            if result['status'] == 'success':
                await update.message.reply_text(f"✅ {result['message']}")
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"设置调度失败: {e}")
            await update.message.reply_text(f"❌ 设置失败: {str(e)}")

    def _parse_channel_link(self, link: str) -> tuple:
        """解析频道链接"""
        try:
            # 支持的格式:
            # https://t.me/channel_name
            # https://t.me/joinchat/xxx
            # @channel_name
            # channel_name
            # -100123456789
            
            if link.startswith('-100'):
                # 直接是频道ID
                return int(link), None
            
            if link.startswith('@'):
                # @channel_name 格式
                return None, link[1:]
            
            if 'joinchat' in link:
                # 私有频道链接，暂时不支持自动解析
                return None, None
            
            if 't.me/' in link:
                # https://t.me/channel_name 格式
                username = link.split('t.me/')[-1]
                return None, username
            
            # 直接是用户名
            return None, link
            
        except Exception as e:
            self.logger.error(f"解析频道链接失败: {e}")
            return None, None

    # 其他方法的实现...
    async def remove_source(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """移除源频道"""
        # 实现移除源频道逻辑
        pass

    async def remove_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """移除目标频道"""
        # 实现移除目标频道逻辑
        pass

    async def delete_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """删除搬运组"""
        # 实现删除组逻辑
        pass

    async def filter_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """测试过滤效果"""
        # 实现过滤测试逻辑
        pass

    async def sync_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """同步历史消息"""
        # 实现历史消息同步逻辑
        pass

    async def sync_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看同步状态"""
        # 实现同步状态查看逻辑
        pass

    async def remove_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """移除调度"""
        # 实现移除调度逻辑
        pass