"""
消息发送器 - 负责将处理后的消息发送到目标频道
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, Forbidden


class MessageSender:
    """消息发送器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)
        
        # Bot管理
        self.bots: List[Bot] = []
        self.current_bot_index = 0
        self.bot_status: Dict[str, Dict] = {}
        
        # 发送限制
        self.send_queue = asyncio.Queue()
        self.hourly_count = 0
        self.last_hour_reset = time.time()
        self.last_send_time = 0
        
        # 运行状态
        self.is_running = False
        self.sender_tasks = []

    async def start(self):
        """启动消息发送器"""
        self.logger.info("🔄 启动消息发送器...")
        
        # 加载Bot
        await self._load_bots()
        
        # 启动发送队列处理器
        for i in range(2):  # 启动2个发送器
            task = asyncio.create_task(self._send_processor())
            self.sender_tasks.append(task)
        
        # 启动限制重置任务
        reset_task = asyncio.create_task(self._hourly_reset_task())
        self.sender_tasks.append(reset_task)
        
        self.is_running = True
        self.logger.info("✅ 消息发送器启动完成")

    async def stop(self):
        """停止消息发送器"""
        self.logger.info("🛑 停止消息发送器...")
        self.is_running = False
        
        # 停止所有发送任务
        for task in self.sender_tasks:
            task.cancel()
        
        # 等待任务完成
        if self.sender_tasks:
            await asyncio.gather(*self.sender_tasks, return_exceptions=True)
        
        self.sender_tasks.clear()
        self.bots.clear()
        
        self.logger.info("✅ 消息发送器已停止")

    async def _load_bots(self):
        """加载发送Bot"""
        try:
            # 从数据库获取Bot列表
            cursor = await self.database._connection.execute(
                'SELECT * FROM sender_bots WHERE status = "active"'
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                bot_data = dict(row)
                try:
                    bot = Bot(token=bot_data['token'])
                    # 验证Bot
                    bot_info = await bot.get_me()
                    
                    self.bots.append(bot)
                    self.bot_status[bot_data['token']] = {
                        'username': bot_info.username,
                        'status': 'active',
                        'error_count': 0,
                        'last_used': 0
                    }
                    
                    self.logger.info(f"🤖 Bot加载成功: @{bot_info.username}")
                    
                except Exception as e:
                    self.logger.error(f"❌ Bot加载失败 {bot_data['token'][:10]}...: {e}")
            
            if not self.bots:
                self.logger.warning("⚠️ 没有可用的发送Bot")
            else:
                self.logger.info(f"🤖 成功加载 {len(self.bots)} 个Bot")
                
        except Exception as e:
            self.logger.error(f"❌ 加载Bot失败: {e}")

    async def add_bot(self, token: str) -> Dict[str, str]:
        """添加发送Bot"""
        try:
            # 验证Bot
            bot = Bot(token=token)
            bot_info = await bot.get_me()
            
            # 添加到数据库
            await self.database._connection.execute(
                'INSERT OR REPLACE INTO sender_bots (token, username) VALUES (?, ?)',
                (token, bot_info.username)
            )
            await self.database._connection.commit()
            
            # 添加到内存
            self.bots.append(bot)
            self.bot_status[token] = {
                'username': bot_info.username,
                'status': 'active',
                'error_count': 0,
                'last_used': 0
            }
            
            self.logger.info(f"✅ 成功添加Bot: @{bot_info.username}")
            return {'status': 'success', 'message': f'Bot @{bot_info.username} 添加成功'}
            
        except Exception as e:
            self.logger.error(f"❌ 添加Bot失败: {e}")
            return {'status': 'error', 'message': f'添加失败: {str(e)}'}

    async def send_message(self, chat_id: int, content: str, parse_mode: str = ParseMode.HTML) -> Dict[str, Any]:
        """发送文本消息"""
        message_data = {
            'type': 'text',
            'chat_id': chat_id,
            'content': content,
            'parse_mode': parse_mode
        }
        
        await self.send_queue.put(message_data)
        
        return {'status': 'queued', 'message': '消息已加入发送队列'}

    async def send_media_group(self, chat_id: int, media_list: List[Dict], caption: str = None) -> Dict[str, Any]:
        """发送媒体组"""
        message_data = {
            'type': 'media_group',
            'chat_id': chat_id,
            'media_list': media_list,
            'caption': caption
        }
        
        await self.send_queue.put(message_data)
        
        return {'status': 'queued', 'message': '媒体组已加入发送队列'}

    async def _send_processor(self):
        """发送处理器"""
        while self.is_running:
            try:
                # 从队列获取消息
                message_data = await asyncio.wait_for(
                    self.send_queue.get(),
                    timeout=1.0
                )
                
                await self._process_send_message(message_data)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ 发送处理器异常: {e}")

    async def _process_send_message(self, message_data: Dict):
        """处理发送消息"""
        try:
            # 检查发送限制
            if not await self._check_send_limits():
                await asyncio.sleep(60)  # 等待1分钟
                return
            
            # 等待发送间隔
            await self._wait_send_interval()
            
            # 获取可用Bot
            bot = self._get_current_bot()
            if not bot:
                self.logger.error("❌ 没有可用的发送Bot")
                return
            
            # 发送消息
            result = await self._send_with_bot(bot, message_data)
            
            if result['status'] == 'success':
                # 更新统计
                self.hourly_count += 1
                self.last_send_time = time.time()
                
                # 轮换Bot
                self._rotate_bot()
                
            else:
                # 处理发送失败
                await self._handle_send_error(bot, result['error'])
                
        except Exception as e:
            self.logger.error(f"❌ 处理发送消息失败: {e}")

    async def _send_with_bot(self, bot: Bot, message_data: Dict) -> Dict[str, Any]:
        """使用指定Bot发送消息"""
        try:
            message_type = message_data['type']
            chat_id = message_data['chat_id']
            
            if message_type == 'text':
                # 发送文本消息
                content = message_data['content']
                parse_mode = message_data.get('parse_mode', ParseMode.HTML)
                
                message = await bot.send_message(
                    chat_id=chat_id,
                    text=content,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
                
                return {
                    'status': 'success',
                    'message_id': message.message_id,
                    'bot': bot
                }
                
            elif message_type == 'media_group':
                # 发送媒体组
                media_list = message_data['media_list']
                caption = message_data.get('caption')
                
                messages = await bot.send_media_group(
                    chat_id=chat_id,
                    media=media_list,
                    caption=caption
                )
                
                return {
                    'status': 'success',
                    'message_ids': [msg.message_id for msg in messages],
                    'bot': bot
                }
                
        except RetryAfter as e:
            # 遇到频率限制
            self.logger.warning(f"⚠️ 遇到频率限制，等待 {e.retry_after} 秒")
            await asyncio.sleep(e.retry_after)
            return {'status': 'retry', 'error': str(e)}
            
        except Forbidden as e:
            # Bot被禁止
            self.logger.error(f"❌ Bot被禁止发送消息: {e}")
            return {'status': 'forbidden', 'error': str(e)}
            
        except TelegramError as e:
            # 其他Telegram错误
            self.logger.error(f"❌ Telegram错误: {e}")
            return {'status': 'error', 'error': str(e)}
            
        except Exception as e:
            # 其他异常
            self.logger.error(f"❌ 发送消息异常: {e}")
            return {'status': 'error', 'error': str(e)}

    async def _check_send_limits(self) -> bool:
        """检查发送限制"""
        # 检查每小时限制
        if self.hourly_count >= self.settings.hourly_limit:
            return False
        
        return True

    async def _wait_send_interval(self):
        """等待发送间隔"""
        current_time = time.time()
        elapsed = current_time - self.last_send_time
        
        # 计算随机间隔
        min_interval = self.settings.min_interval
        max_interval = self.settings.max_interval
        interval = random.uniform(min_interval, max_interval)
        
        if elapsed < interval:
            wait_time = interval - elapsed
            await asyncio.sleep(wait_time)

    def _get_current_bot(self) -> Optional[Bot]:
        """获取当前Bot"""
        if not self.bots:
            return None
        
        # 过滤可用Bot
        available_bots = []
        for i, bot in enumerate(self.bots):
            token = bot.token
            if self.bot_status.get(token, {}).get('status') == 'active':
                available_bots.append((i, bot))
        
        if not available_bots:
            return None
        
        # 返回当前轮换的Bot
        bot_index = self.current_bot_index % len(available_bots)
        return available_bots[bot_index][1]

    def _rotate_bot(self):
        """轮换Bot"""
        if self.bots:
            self.current_bot_index = (self.current_bot_index + 1) % len(self.bots)

    async def _handle_send_error(self, bot: Bot, error: str):
        """处理发送错误"""
        token = bot.token
        
        if token in self.bot_status:
            self.bot_status[token]['error_count'] += 1
            error_count = self.bot_status[token]['error_count']
            
            # 更新数据库
            await self.database._connection.execute(
                'UPDATE sender_bots SET error_count = ? WHERE token = ?',
                (error_count, token)
            )
            await self.database._connection.commit()
            
            # 如果错误次数过多，暂停Bot
            if error_count >= 5:
                self.bot_status[token]['status'] = 'suspended'
                self.logger.warning(f"⚠️ Bot {token[:10]}... 错误次数过多，已暂停使用")

    async def _hourly_reset_task(self):
        """每小时重置任务"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # 每小时重置计数
                if current_time - self.last_hour_reset >= 3600:
                    self.hourly_count = 0
                    self.last_hour_reset = current_time
                    self.logger.info("🔄 每小时发送计数已重置")
                
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ 每小时重置任务异常: {e}")

    async def get_send_statistics(self) -> Dict[str, Any]:
        """获取发送统计"""
        try:
            # 获取Bot状态
            bot_stats = []
            for bot in self.bots:
                token = bot.token
                status = self.bot_status.get(token, {})
                bot_stats.append({
                    'username': status.get('username', 'Unknown'),
                    'status': status.get('status', 'unknown'),
                    'error_count': status.get('error_count', 0),
                    'last_used': status.get('last_used', 0)
                })
            
            return {
                'total_bots': len(self.bots),
                'active_bots': len([b for b in bot_stats if b['status'] == 'active']),
                'hourly_count': self.hourly_count,
                'hourly_limit': self.settings.hourly_limit,
                'queue_size': self.send_queue.qsize(),
                'bots': bot_stats
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取发送统计失败: {e}")
            return {
                'total_bots': 0,
                'active_bots': 0,
                'hourly_count': 0,
                'hourly_limit': 0,
                'queue_size': 0,
                'bots': []
            }

    async def reload_config(self):
        """重新加载配置"""
        self.logger.info("📝 消息发送器重新加载配置")
        # 这里可以重新加载发送限制等配置