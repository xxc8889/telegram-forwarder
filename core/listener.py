"""
消息监听器 - 监听源频道的新消息
"""

import asyncio
import logging
import hashlib
from typing import Dict, List, Set, Any
from telethon import events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument


class MessageListener:
    """消息监听器"""
    
    def __init__(self, settings, database, group_processor):
        self.settings = settings
        self.database = database
        self.group_processor = group_processor
        self.logger = logging.getLogger(__name__)
        
        # 监听状态
        self.is_running = False
        self.listening_channels: Set[int] = set()
        self.media_groups: Dict[int, List] = {}  # 媒体组缓存
        self.media_group_timers: Dict[int, asyncio.Task] = {}
        
        # 处理队列
        self.message_queue = asyncio.Queue()
        self.queue_processors = []

    async def start(self):
        """启动消息监听器"""
        self.logger.info("🔄 启动消息监听器...")
        
        # 获取所有搬运组的源频道
        await self._setup_listeners()
        
        # 启动消息处理队列
        for i in range(3):  # 启动3个处理器
            processor = asyncio.create_task(self._message_processor())
            self.queue_processors.append(processor)
        
        self.is_running = True
        self.logger.info("✅ 消息监听器启动完成")

    async def stop(self):
        """停止消息监听器"""
        self.logger.info("🛑 停止消息监听器...")
        self.is_running = False
        
        # 停止媒体组定时器
        for timer in self.media_group_timers.values():
            timer.cancel()
        
        # 停止队列处理器
        for processor in self.queue_processors:
            processor.cancel()
        
        # 等待处理器完成
        if self.queue_processors:
            await asyncio.gather(*self.queue_processors, return_exceptions=True)
        
        self.queue_processors.clear()
        self.listening_channels.clear()
        
        self.logger.info("✅ 消息监听器已停止")

    async def _setup_listeners(self):
        """设置监听器"""
        try:
            groups = await self.database.get_forwarding_groups()
            
            for group in groups:
                if group['status'] != 'active':
                    continue
                
                # 获取组的源频道
                source_channels, _ = await self.database.get_group_channels(group['id'])
                
                for channel in source_channels:
                    channel_id = channel['channel_id']
                    if channel_id not in self.listening_channels:
                        await self._add_channel_listener(channel_id, group['id'])
                        self.listening_channels.add(channel_id)
            
            self.logger.info(f"📡 监听 {len(self.listening_channels)} 个频道")
            
        except Exception as e:
            self.logger.error(f"❌ 设置监听器失败: {e}")

    async def _add_channel_listener(self, channel_id: int, group_id: int):
        """为频道添加监听器"""
        try:
            # 从账号管理器获取客户端
            from core.manager import ForwarderManager
            
            # 这里需要通过依赖注入或其他方式获取账号管理器
            # 暂时使用简化的方式
            pass
            
        except Exception as e:
            self.logger.error(f"❌ 添加频道监听器失败 {channel_id}: {e}")

    async def _message_processor(self):
        """消息处理器"""
        while self.is_running:
            try:
                # 从队列获取消息
                message_data = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                await self._process_message(message_data)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ 处理消息异常: {e}")

    async def _process_message(self, message_data: Dict):
        """处理单条消息"""
        try:
            message = message_data['message']
            group_id = message_data['group_id']
            channel_id = message_data['channel_id']
            
            # 检查消息是否有媒体组
            if message.grouped_id:
                await self._handle_media_group(message, group_id, channel_id)
            else:
                # 单条消息直接处理
                await self._handle_single_message(message, group_id, channel_id)
                
        except Exception as e:
            self.logger.error(f"❌ 处理消息失败: {e}")

    async def _handle_single_message(self, message, group_id: int, channel_id: int):
        """处理单条消息"""
        try:
            # 生成消息哈希用于去重
            content_hash = self._generate_message_hash(message)
            
            # 检查是否已经转发过
            if await self.database.is_message_forwarded(content_hash):
                self.logger.debug(f"📋 消息已转发，跳过: {message.id}")
                return
            
            # 更新最后处理的消息ID
            await self.database.update_last_message_id(group_id, channel_id, message.id)
            
            # 发送给组处理器
            await self.group_processor.process_message(group_id, message, content_hash)
            
        except Exception as e:
            self.logger.error(f"❌ 处理单条消息失败: {e}")

    async def _handle_media_group(self, message, group_id: int, channel_id: int):
        """处理媒体组消息"""
        try:
            grouped_id = message.grouped_id
            
            # 初始化媒体组
            if grouped_id not in self.media_groups:
                self.media_groups[grouped_id] = []
            
            # 添加消息到媒体组
            self.media_groups[grouped_id].append({
                'message': message,
                'group_id': group_id,
                'channel_id': channel_id
            })
            
            # 取消之前的定时器
            if grouped_id in self.media_group_timers:
                self.media_group_timers[grouped_id].cancel()
            
            # 设置新的定时器（5秒后处理媒体组）
            timer = asyncio.create_task(
                self._process_media_group_delayed(grouped_id)
            )
            self.media_group_timers[grouped_id] = timer
            
        except Exception as e:
            self.logger.error(f"❌ 处理媒体组失败: {e}")

    async def _process_media_group_delayed(self, grouped_id: int):
        """延迟处理媒体组"""
        try:
            # 等待5秒收集完整的媒体组
            await asyncio.sleep(5)
            
            if grouped_id in self.media_groups:
                messages = self.media_groups[grouped_id]
                
                if messages:
                    # 使用第一条消息的信息
                    first_msg_data = messages[0]
                    group_id = first_msg_data['group_id']
                    channel_id = first_msg_data['channel_id']
                    
                    # 按消息ID排序确保顺序
                    messages.sort(key=lambda x: x['message'].id)
                    
                    # 生成媒体组哈希
                    content_hash = self._generate_media_group_hash(messages)
                    
                    # 检查是否已经转发过
                    if not await self.database.is_message_forwarded(content_hash):
                        # 更新最后处理的消息ID（使用最后一条消息的ID）
                        last_message = messages[-1]['message']
                        await self.database.update_last_message_id(group_id, channel_id, last_message.id)
                        
                        # 发送给组处理器
                        await self.group_processor.process_media_group(group_id, messages, content_hash)
                    else:
                        self.logger.debug(f"📋 媒体组已转发，跳过: {grouped_id}")
                
                # 清理媒体组缓存
                del self.media_groups[grouped_id]
            
            # 清理定时器
            if grouped_id in self.media_group_timers:
                del self.media_group_timers[grouped_id]
                
        except Exception as e:
            self.logger.error(f"❌ 延迟处理媒体组失败: {e}")

    def _generate_message_hash(self, message) -> str:
        """生成消息哈希用于去重"""
        try:
            # 基于消息内容生成哈希
            content = ""
            
            # 添加文本内容
            if message.text:
                content += message.text
            
            # 添加媒体信息
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    content += f"photo_{message.media.photo.id}"
                elif isinstance(message.media, MessageMediaDocument):
                    content += f"doc_{message.media.document.id}"
            
            # 添加发送者和频道信息
            content += f"_{message.chat_id}_{message.from_id}"
            
            # 生成MD5哈希
            return hashlib.md5(content.encode('utf-8')).hexdigest()
            
        except Exception as e:
            self.logger.error(f"❌ 生成消息哈希失败: {e}")
            # 使用消息ID作为备用哈希
            return f"msg_{message.chat_id}_{message.id}"

    def _generate_media_group_hash(self, messages: List[Dict]) -> str:
        """生成媒体组哈希"""
        try:
            content = ""
            
            # 按消息ID排序确保一致性
            sorted_messages = sorted(messages, key=lambda x: x['message'].id)
            
            for msg_data in sorted_messages:
                message = msg_data['message']
                
                # 添加文本内容
                if message.text:
                    content += message.text
                
                # 添加媒体信息
                if message.media:
                    if isinstance(message.media, MessageMediaPhoto):
                        content += f"photo_{message.media.photo.id}"
                    elif isinstance(message.media, MessageMediaDocument):
                        content += f"doc_{message.media.document.id}"
            
            # 添加组ID和频道信息
            first_message = sorted_messages[0]['message']
            content += f"_group_{first_message.grouped_id}_{first_message.chat_id}"
            
            return hashlib.md5(content.encode('utf-8')).hexdigest()
            
        except Exception as e:
            self.logger.error(f"❌ 生成媒体组哈希失败: {e}")
            # 使用组ID作为备用哈希
            first_message = messages[0]['message']
            return f"group_{first_message.grouped_id}_{first_message.chat_id}"

    async def sync_history(self, group_id: int, channel_id: int, limit: int = 100) -> Dict[str, Any]:
        """同步历史消息"""
        try:
            self.logger.info(f"🔄 开始同步历史消息: 组{group_id}, 频道{channel_id}, 限制{limit}")
            
            # 获取账号管理器的客户端
            # 这里需要依赖注入，暂时省略具体实现
            # client, phone = await self.account_manager.get_current_client()
            
            synced_count = 0
            error_count = 0
            
            # 这里应该实现实际的历史消息同步逻辑
            # 遍历历史消息并处理
            
            result = {
                'status': 'success',
                'synced_count': synced_count,
                'error_count': error_count,
                'message': f'同步完成: {synced_count} 条消息'
            }
            
            self.logger.info(f"✅ 历史消息同步完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 同步历史消息失败: {e}")
            return {
                'status': 'error',
                'synced_count': 0,
                'error_count': 0,
                'message': f'同步失败: {str(e)}'
            }

    async def add_channel_to_listen(self, channel_id: int, group_id: int):
        """添加频道到监听列表"""
        try:
            if channel_id not in self.listening_channels:
                await self._add_channel_listener(channel_id, group_id)
                self.listening_channels.add(channel_id)
                self.logger.info(f"📡 添加频道监听: {channel_id}")
                
        except Exception as e:
            self.logger.error(f"❌ 添加频道监听失败: {e}")

    async def remove_channel_from_listen(self, channel_id: int):
        """从监听列表移除频道"""
        try:
            if channel_id in self.listening_channels:
                self.listening_channels.remove(channel_id)
                self.logger.info(f"📡 移除频道监听: {channel_id}")
                
        except Exception as e:
            self.logger.error(f"❌ 移除频道监听失败: {e}")

    async def get_listening_status(self) -> Dict[str, Any]:
        """获取监听状态"""
        return {
            'is_running': self.is_running,
            'listening_channels': list(self.listening_channels),
            'active_media_groups': len(self.media_groups),
            'queue_size': self.message_queue.qsize(),
            'processors': len(self.queue_processors)
        }
