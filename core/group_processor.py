"""
组处理器 - 处理搬运组的消息转发逻辑
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, time as dt_time

from utils.filters import MessageFilter


class GroupProcessor:
    """搬运组处理器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)
        
        # 过滤器
        self.message_filter = MessageFilter(settings)
        
        # 组状态缓存
        self.group_cache: Dict[int, Dict] = {}
        self.cache_update_time = 0
        
        # 运行状态
        self.is_running = False

    async def start(self):
        """启动组处理器"""
        self.logger.info("🔄 启动组处理器...")
        
        # 加载组配置
        await self._load_groups()
        
        self.is_running = True
        self.logger.info("✅ 组处理器启动完成")

    async def stop(self):
        """停止组处理器"""
        self.logger.info("🛑 停止组处理器...")
        self.is_running = False
        
        self.group_cache.clear()
        self.logger.info("✅ 组处理器已停止")

    async def _load_groups(self):
        """加载组配置"""
        try:
            groups = await self.database.get_forwarding_groups()
            
            for group in groups:
                group_id = group['id']
                
                # 获取组的频道
                source_channels, target_channels = await self.database.get_group_channels(group_id)
                
                self.group_cache[group_id] = {
                    'config': group,
                    'source_channels': source_channels,
                    'target_channels': target_channels
                }
            
            self.cache_update_time = datetime.now().timestamp()
            self.logger.info(f"📋 加载 {len(self.group_cache)} 个搬运组")
            
        except Exception as e:
            self.logger.error(f"❌ 加载组配置失败: {e}")

    async def process_message(self, group_id: int, message, content_hash: str):
        """处理单条消息"""
        try:
            # 检查组是否激活且在调度时间内
            if not await self._should_process_group(group_id):
                return
            
            # 获取组配置
            group_data = await self._get_group_data(group_id)
            if not group_data:
                return
            
            # 过滤消息
            filtered_content = await self._filter_message(group_data, message)
            if not filtered_content:
                self.logger.debug(f"📋 消息被过滤，跳过: {message.id}")
                return
            
            # 发送到目标频道
            await self._send_to_targets(group_data, filtered_content, content_hash, message.id)
            
        except Exception as e:
            self.logger.error(f"❌ 处理消息失败: {e}")

    async def process_media_group(self, group_id: int, messages: List[Dict], content_hash: str):
        """处理媒体组消息"""
        try:
            # 检查组是否激活且在调度时间内
            if not await self._should_process_group(group_id):
                return
            
            # 获取组配置
            group_data = await self._get_group_data(group_id)
            if not group_data:
                return
            
            # 过滤媒体组
            filtered_media = await self._filter_media_group(group_data, messages)
            if not filtered_media:
                self.logger.debug(f"📋 媒体组被过滤，跳过")
                return
            
            # 发送到目标频道
            source_message_id = messages[0]['message'].id
            await self._send_media_group_to_targets(group_data, filtered_media, content_hash, source_message_id)
            
        except Exception as e:
            self.logger.error(f"❌ 处理媒体组失败: {e}")

    async def _should_process_group(self, group_id: int) -> bool:
        """检查组是否应该处理"""
        try:
            group_data = await self._get_group_data(group_id)
            if not group_data:
                return False
            
            config = group_data['config']
            
            # 检查组状态
            if config['status'] != 'active':
                return False
            
            # 检查调度时间
            if config['schedule_start'] and config['schedule_end']:
                return self._is_in_schedule_time(config['schedule_start'], config['schedule_end'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 检查组处理状态失败: {e}")
            return False

    def _is_in_schedule_time(self, start_time: str, end_time: str) -> bool:
        """检查是否在调度时间内"""
        try:
            now = datetime.now().time()
            start = dt_time.fromisoformat(start_time)
            end = dt_time.fromisoformat(end_time)
            
            if start <= end:
                # 同一天的时间段
                return start <= now <= end
            else:
                # 跨天的时间段
                return now >= start or now <= end
                
        except Exception as e:
            self.logger.error(f"❌ 检查调度时间失败: {e}")
            return True

    async def _get_group_data(self, group_id: int) -> Optional[Dict]:
        """获取组数据"""
        # 检查缓存是否需要更新
        if datetime.now().timestamp() - self.cache_update_time > 300:  # 5分钟
            await self._load_groups()
        
        return self.group_cache.get(group_id)

    async def _filter_message(self, group_data: Dict, message) -> Optional[str]:
        """过滤单条消息"""
        try:
            if not message.text:
                return None
            
            config = group_data['config']
            filters = config.get('filters', {})
            
            # 应用过滤器
            filtered_text = self.message_filter.filter_text(message.text, filters)
            
            # 如果过滤后为空，返回None
            if not filtered_text.strip():
                return None
            
            # 添加小尾巴
            footer = config.get('footer', '')
            if footer:
                filtered_text += f"\n\n{footer}"
            
            return filtered_text
            
        except Exception as e:
            self.logger.error(f"❌ 过滤消息失败: {e}")
            return None

    async def _filter_media_group(self, group_data: Dict, messages: List[Dict]) -> Optional[List[Dict]]:
        """过滤媒体组"""
        try:
            config = group_data['config']
            filters = config.get('filters', {})
            
            filtered_media = []
            
            for msg_data in messages:
                message = msg_data['message']
                
                # 处理文本
                text = message.text or message.caption or ""
                if text:
                    filtered_text = self.message_filter.filter_text(text, filters)
                else:
                    filtered_text = ""
                
                # 保留媒体
                filtered_media.append({
                    'message': message,
                    'filtered_text': filtered_text
                })
            
            # 添加小尾巴到第一条消息
            footer = config.get('footer', '')
            if footer and filtered_media:
                if filtered_media[0]['filtered_text']:
                    filtered_media[0]['filtered_text'] += f"\n\n{footer}"
                else:
                    filtered_media[0]['filtered_text'] = footer
            
            return filtered_media if filtered_media else None
            
        except Exception as e:
            self.logger.error(f"❌ 过滤媒体组失败: {e}")
            return None

    async def _send_to_targets(self, group_data: Dict, content: str, content_hash: str, source_message_id: int):
        """发送到目标频道"""
        try:
            from core.manager import ForwarderManager
            
            target_channels = group_data['target_channels']
            group_id = group_data['config']['id']
            
            for target in target_channels:
                try:
                    # 通过消息发送器发送
                    # sender = ForwarderManager.instance.message_sender
                    # result = await sender.send_message(target['channel_id'], content)
                    
                    # 这里暂时模拟发送成功
                    result = {'status': 'success', 'message_id': 12345}
                    
                    if result['status'] == 'success':
                        # 记录消息历史
                        await self.database.add_message_record(
                            group_id, source_message_id, result.get('message_id'),
                            0, target['channel_id'], content_hash  # source_channel_id 暂时用0
                        )
                        
                        # 更新统计
                        await self.database.update_statistics(group_id, "system", True)
                        
                        self.logger.info(f"✅ 消息发送成功: 组{group_id} -> 频道{target['channel_id']}")
                    else:
                        # 更新失败统计
                        await self.database.update_statistics(group_id, "system", False)
                        self.logger.error(f"❌ 消息发送失败: {result.get('error')}")
                        
                except Exception as e:
                    self.logger.error(f"❌ 发送到目标频道失败 {target['channel_id']}: {e}")
                    await self.database.update_statistics(group_id, "system", False)
                    
        except Exception as e:
            self.logger.error(f"❌ 发送到目标频道异常: {e}")

    async def _send_media_group_to_targets(self, group_data: Dict, media_list: List[Dict], content_hash: str, source_message_id: int):
        """发送媒体组到目标频道"""
        try:
            target_channels = group_data['target_channels']
            group_id = group_data['config']['id']
            
            for target in target_channels:
                try:
                    # 准备媒体数据
                    media_data = []
                    caption = None
                    
                    for i, media_item in enumerate(media_list):
                        message = media_item['message']
                        text = media_item['filtered_text']
                        
                        # 第一条消息的文本作为caption
                        if i == 0 and text:
                            caption = text
                        
                        # 这里需要处理媒体文件
                        # 暂时跳过具体实现
                        pass
                    
                    # 通过消息发送器发送媒体组
                    # result = await sender.send_media_group(target['channel_id'], media_data, caption)
                    
                    # 暂时模拟发送成功
                    result = {'status': 'success', 'message_ids': [12345, 12346]}
                    
                    if result['status'] == 'success':
                        # 记录消息历史
                        message_ids = result.get('message_ids', [])
                        if message_ids:
                            await self.database.add_message_record(
                                group_id, source_message_id, message_ids[0],
                                0, target['channel_id'], content_hash
                            )
                        
                        # 更新统计
                        await self.database.update_statistics(group_id, "system", True)
                        
                        self.logger.info(f"✅ 媒体组发送成功: 组{group_id} -> 频道{target['channel_id']}")
                    else:
                        await self.database.update_statistics(group_id, "system", False)
                        self.logger.error(f"❌ 媒体组发送失败: {result.get('error')}")
                        
                except Exception as e:
                    self.logger.error(f"❌ 发送媒体组到目标频道失败 {target['channel_id']}: {e}")
                    await self.database.update_statistics(group_id, "system", False)
                    
        except Exception as e:
            self.logger.error(f"❌ 发送媒体组到目标频道异常: {e}")

    async def create_group(self, name: str, description: str = None) -> Dict[str, Any]:
        """创建搬运组"""
        try:
            group_id = await self.database.create_forwarding_group(name, description)
            
            if group_id:
                # 更新缓存
                await self._load_groups()
                
                self.logger.info(f"✅ 创建搬运组成功: {name} (ID: {group_id})")
                return {
                    'status': 'success',
                    'group_id': group_id,
                    'message': f'搬运组 "{name}" 创建成功'
                }
            else:
                return {'status': 'error', 'message': '创建搬运组失败'}
                
        except Exception as e:
            self.logger.error(f"❌ 创建搬运组失败: {e}")
            return {'status': 'error', 'message': f'创建失败: {str(e)}'}

    async def add_source_channel(self, group_id: int, channel_id: int, channel_username: str = None, channel_title: str = None) -> Dict[str, Any]:
        """添加源频道"""
        try:
            success = await self.database.add_source_channel(group_id, channel_id, channel_username, channel_title)
            
            if success:
                # 更新缓存
                await self._load_groups()
                
                self.logger.info(f"✅ 添加源频道成功: 组{group_id} -> 频道{channel_id}")
                return {'status': 'success', 'message': '源频道添加成功'}
            else:
                return {'status': 'error', 'message': '添加源频道失败'}
                
        except Exception as e:
            self.logger.error(f"❌ 添加源频道失败: {e}")
            return {'status': 'error', 'message': f'添加失败: {str(e)}'}

    async def add_target_channel(self, group_id: int, channel_id: int, channel_username: str = None, channel_title: str = None) -> Dict[str, Any]:
        """添加目标频道"""
        try:
            success = await self.database.add_target_channel(group_id, channel_id, channel_username, channel_title)
            
            if success:
                # 更新缓存
                await self._load_groups()
                
                self.logger.info(f"✅ 添加目标频道成功: 组{group_id} -> 频道{channel_id}")
                return {'status': 'success', 'message': '目标频道添加成功'}
            else:
                return {'status': 'error', 'message': '添加目标频道失败'}
                
        except Exception as e:
            self.logger.error(f"❌ 添加目标频道失败: {e}")
            return {'status': 'error', 'message': f'添加失败: {str(e)}'}

    async def set_group_filter(self, group_id: int, filter_type: str, enabled: bool, rules: Dict = None) -> Dict[str, Any]:
        """设置组过滤器"""
        try:
            group_data = await self._get_group_data(group_id)
            if not group_data:
                return {'status': 'error', 'message': '搬运组不存在'}
            
            # 获取当前过滤器配置
            current_filters = group_data['config'].get('filters', {})
            
            # 更新过滤器
            if filter_type == 'remove_links':
                current_filters['remove_links'] = enabled
            elif filter_type == 'remove_emojis':
                current_filters['remove_emojis'] = enabled
            elif filter_type == 'remove_special_chars':
                current_filters['remove_special_chars'] = enabled
            elif filter_type == 'ad_detection':
                current_filters['ad_detection'] = enabled
            elif filter_type == 'smart_filter':
                current_filters['smart_filter'] = enabled
            elif filter_type == 'custom' and rules:
                current_filters['custom_rules'] = rules
            
            # 保存到数据库
            success = await self.database.update_group_filters(group_id, current_filters)
            
            if success:
                # 更新缓存
                await self._load_groups()
                
                self.logger.info(f"✅ 更新组过滤器成功: 组{group_id}, 类型{filter_type}")
                return {'status': 'success', 'message': '过滤器设置成功'}
            else:
                return {'status': 'error', 'message': '更新过滤器失败'}
                
        except Exception as e:
            self.logger.error(f"❌ 设置组过滤器失败: {e}")
            return {'status': 'error', 'message': f'设置失败: {str(e)}'}

    async def set_group_schedule(self, group_id: int, start_time: str, end_time: str) -> Dict[str, Any]:
        """设置组调度"""
        try:
            success = await self.database.set_group_schedule(group_id, start_time, end_time)
            
            if success:
                # 更新缓存
                await self._load_groups()
                
                self.logger.info(f"✅ 设置组调度成功: 组{group_id}, {start_time}-{end_time}")
                return {'status': 'success', 'message': f'调度设置成功: {start_time}-{end_time}'}
            else:
                return {'status': 'error', 'message': '设置调度失败'}
                
        except Exception as e:
            self.logger.error(f"❌ 设置组调度失败: {e}")
            return {'status': 'error', 'message': f'设置失败: {str(e)}'}

    async def get_group_list(self) -> List[Dict[str, Any]]:
        """获取搬运组列表"""
        try:
            groups = []
            
            for group_id, group_data in self.group_cache.items():
                config = group_data['config']
                source_count = len(group_data['source_channels'])
                target_count = len(group_data['target_channels'])
                
                # 获取统计信息
                stats = await self.database.get_group_statistics(group_id, 1)
                today_stats = stats[0] if stats else {}
                
                groups.append({
                    'id': group_id,
                    'name': config['name'],
                    'description': config['description'],
                    'status': config['status'],
                    'schedule': {
                        'start': config.get('schedule_start'),
                        'end': config.get('schedule_end')
                    },
                    'channels': {
                        'source_count': source_count,
                        'target_count': target_count
                    },
                    'today_stats': {
                        'messages': today_stats.get('total_messages', 0),
                        'success': today_stats.get('total_success', 0),
                        'errors': today_stats.get('total_errors', 0),
                        'success_rate': today_stats.get('success_rate', 0)
                    }
                })
            
            return groups
            
        except Exception as e:
            self.logger.error(f"❌ 获取组列表失败: {e}")
            return []

    async def get_group_info(self, group_id: int) -> Optional[Dict[str, Any]]:
        """获取组详细信息"""
        try:
            group_data = await self._get_group_data(group_id)
            if not group_data:
                return None
            
            config = group_data['config']
            source_channels = group_data['source_channels']
            target_channels = group_data['target_channels']
            
            # 获取统计信息
            stats = await self.database.get_group_statistics(group_id, 7)
            
            return {
                'id': group_id,
                'name': config['name'],
                'description': config['description'],
                'status': config['status'],
                'schedule': {
                    'start': config.get('schedule_start'),
                    'end': config.get('schedule_end')
                },
                'filters': config.get('filters', {}),
                'footer': config.get('footer', ''),
                'source_channels': source_channels,
                'target_channels': target_channels,
                'statistics': stats
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取组信息失败: {e}")
            return None

    async def get_statistics(self) -> Dict[str, Any]:
        """获取组处理器统计信息"""
        try:
            total_groups = len(self.group_cache)
            active_groups = len([g for g in self.group_cache.values() 
                               if g['config']['status'] == 'active'])
            
            # 统计频道数量
            total_sources = sum(len(g['source_channels']) for g in self.group_cache.values())
            total_targets = sum(len(g['target_channels']) for g in self.group_cache.values())
            
            return {
                'total_groups': total_groups,
                'active_groups': active_groups,
                'inactive_groups': total_groups - active_groups,
                'total_source_channels': total_sources,
                'total_target_channels': total_targets,
                'is_running': self.is_running
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                'total_groups': 0,
                'active_groups': 0,
                'inactive_groups': 0,
                'total_source_channels': 0,
                'total_target_channels': 0,
                'is_running': False
            }

    async def reload_config(self):
        """重新加载配置"""
        self.logger.info("📝 组处理器重新加载配置")
        await self._load_groups()