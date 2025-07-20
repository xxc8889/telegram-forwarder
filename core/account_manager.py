"""
账号管理器 - 管理监听账号的登录、轮换和状态监控
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from telethon.sessions import StringSession


class AccountManager:
    """账号管理器"""
    
    def __init__(self, settings, database, api_pool_manager):
        self.settings = settings
        self.database = database
        self.api_pool_manager = api_pool_manager
        self.logger = logging.getLogger(__name__)
        
        # 客户端管理
        self.clients: Dict[str, TelegramClient] = {}
        self.client_status: Dict[str, Dict] = {}
        self.current_client_index = 0
        self.last_rotation_time = time.time()
        
        # 登录状态管理
        self.login_sessions: Dict[str, Dict] = {}
        
        # 运行状态
        self.is_running = False
        self.rotation_task = None

    async def start(self):
        """启动账号管理器"""
        self.logger.info("🔄 启动账号管理器...")
        
        # 加载现有账号
        await self._load_accounts()
        
        # 启动轮换任务
        self.rotation_task = asyncio.create_task(self._rotation_loop())
        
        self.is_running = True
        self.logger.info("✅ 账号管理器启动完成")

    async def stop(self):
        """停止账号管理器"""
        self.logger.info("🛑 停止账号管理器...")
        self.is_running = False
        
        # 停止轮换任务
        if self.rotation_task:
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass
        
        # 断开所有客户端
        for phone, client in self.clients.items():
            try:
                if client.is_connected():
                    await client.disconnect()
                self.logger.info(f"📱 账号 {phone} 已断开连接")
            except Exception as e:
                self.logger.error(f"❌ 断开账号连接失败 {phone}: {e}")
        
        self.clients.clear()
        self.client_status.clear()
        
        self.logger.info("✅ 账号管理器已停止")

    async def _load_accounts(self):
        """加载现有账号"""
        try:
            accounts = await self.database.get_listener_accounts()
            
            for account in accounts:
                phone = account['phone']
                
                # 为账号分配API
                api = await self.api_pool_manager.assign_api_to_account(phone)
                if not api:
                    self.logger.warning(f"⚠️ 无法为账号 {phone} 分配API")
                    continue
                
                # 创建客户端
                await self._create_client(phone, api)
            
            if self.clients:
                self.logger.info(f"📱 成功加载 {len(self.clients)} 个账号")
            else:
                self.logger.warning("⚠️ 没有可用的监听账号")
                
        except Exception as e:
            self.logger.error(f"❌ 加载账号失败: {e}")

    async def _create_client(self, phone: str, api: Dict[str, Any]) -> bool:
        """创建Telegram客户端"""
        try:
            # 会话文件路径
            session_file = Path(f"sessions/{phone}.session")
            
            # 创建客户端
            client = TelegramClient(
                str(session_file),
                int(api['app_id']),
                api['app_hash'],
                device_model="Telegram Forwarder",
                system_version="1.0",
                app_version="1.0",
                lang_code="zh",
                system_lang_code="zh"
            )
            
            # 尝试连接
            await client.connect()
            
            # 检查是否已登录
            if await client.is_user_authorized():
                # 获取用户信息
                me = await client.get_me()
                
                # 更新数据库
                await self.database.add_listener_account(phone, me.id, me.username)
                await self.database.update_account_status(phone, 'active', 0)
                
                # 保存客户端
                self.clients[phone] = client
                self.client_status[phone] = {
                    'status': 'active',
                    'user_id': me.id,
                    'username': me.username,
                    'last_active': time.time(),
                    'error_count': 0,
                    'api_id': api['app_id']
                }
                
                self.logger.info(f"✅ 账号 {phone} ({me.username or me.id}) 连接成功")
                return True
            else:
                # 需要登录
                await client.disconnect()
                self.logger.warning(f"⚠️ 账号 {phone} 需要重新登录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 创建客户端失败 {phone}: {e}")
            if 'client' in locals():
                try:
                    await client.disconnect()
                except:
                    pass
            return False

    async def start_login(self, phone: str) -> Dict[str, str]:
        """开始账号登录流程"""
        try:
            # 为账号分配API
            api = await self.api_pool_manager.assign_api_to_account(phone)
            if not api:
                return {'status': 'error', 'message': '无可用API，请联系管理员添加API ID'}
            
            # 创建临时客户端
            session_file = Path(f"sessions/{phone}.session")
            client = TelegramClient(
                str(session_file),
                int(api['app_id']),
                api['app_hash']
            )
            
            await client.connect()
            
            # 发送验证码
            sent_code = await client.send_code_request(phone)
            
            # 保存登录会话
            self.login_sessions[phone] = {
                'client': client,
                'phone_code_hash': sent_code.phone_code_hash,
                'api': api,
                'step': 'code',
                'timestamp': time.time()
            }
            
            self.logger.info(f"📱 已向 {phone} 发送验证码")
            return {'status': 'success', 'message': f'验证码已发送到 {phone}，请输入验证码'}
            
        except Exception as e:
            self.logger.error(f"❌ 开始登录失败 {phone}: {e}")
            return {'status': 'error', 'message': f'发送验证码失败: {str(e)}'}

    async def submit_code(self, phone: str, code: str) -> Dict[str, str]:
        """提交验证码"""
        if phone not in self.login_sessions:
            return {'status': 'error', 'message': '未找到登录会话，请重新开始'}
        
        session = self.login_sessions[phone]
        client = session['client']
        
        try:
            # 提交验证码
            await client.sign_in(phone, code, phone_code_hash=session['phone_code_hash'])
            
            # 登录成功
            me = await client.get_me()
            
            # 添加到数据库
            await self.database.add_listener_account(phone, me.id, me.username)
            
            # 保存客户端
            self.clients[phone] = client
            self.client_status[phone] = {
                'status': 'active',
                'user_id': me.id,
                'username': me.username,
                'last_active': time.time(),
                'error_count': 0,
                'api_id': session['api']['app_id']
            }
            
            # 清理登录会话
            del self.login_sessions[phone]
            
            self.logger.info(f"✅ 账号 {phone} ({me.username or me.id}) 登录成功")
            return {'status': 'success', 'message': f'登录成功！用户: {me.username or me.id}'}
            
        except SessionPasswordNeededError:
            # 需要两步验证
            session['step'] = '2fa'
            return {'status': '2fa_required', 'message': '需要两步验证密码，请输入密码'}
            
        except PhoneCodeInvalidError:
            return {'status': 'error', 'message': '验证码错误，请重新输入'}
            
        except Exception as e:
            self.logger.error(f"❌ 提交验证码失败 {phone}: {e}")
            return {'status': 'error', 'message': f'验证失败: {str(e)}'}

    async def submit_2fa_password(self, phone: str, password: str) -> Dict[str, str]:
        """提交两步验证密码"""
        if phone not in self.login_sessions:
            return {'status': 'error', 'message': '未找到登录会话，请重新开始'}
        
        session = self.login_sessions[phone]
        client = session['client']
        
        try:
            # 提交两步验证密码
            await client.sign_in(password=password)
            
            # 登录成功
            me = await client.get_me()
            
            # 添加到数据库
            await self.database.add_listener_account(phone, me.id, me.username)
            
            # 保存客户端
            self.clients[phone] = client
            self.client_status[phone] = {
                'status': 'active',
                'user_id': me.id,
                'username': me.username,
                'last_active': time.time(),
                'error_count': 0,
                'api_id': session['api']['app_id']
            }
            
            # 清理登录会话
            del self.login_sessions[phone]
            
            self.logger.info(f"✅ 账号 {phone} ({me.username or me.id}) 两步验证成功")
            return {'status': 'success', 'message': f'登录成功！用户: {me.username or me.id}'}
            
        except PasswordHashInvalidError:
            return {'status': 'error', 'message': '两步验证密码错误，请重新输入'}
            
        except Exception as e:
            self.logger.error(f"❌ 两步验证失败 {phone}: {e}")
            return {'status': 'error', 'message': f'验证失败: {str(e)}'}

    async def remove_account(self, phone: str) -> bool:
        """移除账号"""
        try:
            # 断开客户端连接
            if phone in self.clients:
                client = self.clients[phone]
                if client.is_connected():
                    await client.disconnect()
                del self.clients[phone]
            
            # 清理状态
            if phone in self.client_status:
                del self.client_status[phone]
            
            # 释放API
            await self.api_pool_manager.release_api_from_account(phone)
            
            # 从数据库删除
            await self.database._connection.execute(
                'DELETE FROM listener_accounts WHERE phone = ?',
                (phone,)
            )
            await self.database._connection.commit()
            
            # 删除会话文件
            session_file = Path(f"sessions/{phone}.session")
            if session_file.exists():
                session_file.unlink()
            
            self.logger.info(f"✅ 账号 {phone} 已移除")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 移除账号失败 {phone}: {e}")
            return False

    async def get_current_client(self) -> Optional[TelegramClient]:
        """获取当前轮换的客户端"""
        if not self.clients:
            return None
        
        active_clients = [(phone, client) for phone, client in self.clients.items() 
                         if self.client_status.get(phone, {}).get('status') == 'active']
        
        if not active_clients:
            return None
        
        # 根据轮换策略选择客户端
        if self._should_rotate():
            self._rotate_client()
        
        phone = list(active_clients)[self.current_client_index % len(active_clients)][0]
        return self.clients[phone], phone

    def _should_rotate(self) -> bool:
        """判断是否需要轮换"""
        strategy = self.settings.rotation_strategy
        
        if strategy == 'message':
            # 每条消息轮换
            return True
        elif strategy == 'time':
            # 时间轮换
            time_per_rotation = self.settings.time_per_rotation * 60  # 转换为秒
            return time.time() - self.last_rotation_time > time_per_rotation
        elif strategy == 'smart':
            # 智能轮换（结合时间和随机）
            min_time = 10 * 60  # 最少10分钟
            max_time = self.settings.time_per_rotation * 60
            elapsed = time.time() - self.last_rotation_time
            
            if elapsed < min_time:
                return False
            elif elapsed > max_time:
                return True
            else:
                # 随机概率
                return random.random() < 0.1
        
        return False

    def _rotate_client(self):
        """轮换客户端"""
        if self.clients:
            self.current_client_index = (self.current_client_index + 1) % len(self.clients)
            self.last_rotation_time = time.time()
            
            active_phones = [phone for phone, status in self.client_status.items() 
                           if status.get('status') == 'active']
            if active_phones:
                current_phone = list(active_phones)[self.current_client_index % len(active_phones)]
                self.logger.debug(f"🔄 轮换到账号: {current_phone}")

    async def _rotation_loop(self):
        """轮换循环任务"""
        while self.is_running:
            try:
                # 检查账号状态
                await self._check_account_health()
                
                # 等待下次检查
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ 轮换循环异常: {e}")
                await asyncio.sleep(60)

    async def _check_account_health(self):
        """检查账号健康状态"""
        for phone, client in list(self.clients.items()):
            try:
                if not client.is_connected():
                    await self._reconnect_client(phone)
                else:
                    # 更新活跃时间
                    if phone in self.client_status:
                        self.client_status[phone]['last_active'] = time.time()
                        
            except Exception as e:
                self.logger.error(f"❌ 检查账号健康状态失败 {phone}: {e}")
                await self._handle_client_error(phone, str(e))

    async def _reconnect_client(self, phone: str):
        """重连客户端"""
        try:
            client = self.clients[phone]
            await client.connect()
            
            if await client.is_user_authorized():
                self.client_status[phone]['status'] = 'active'
                self.client_status[phone]['error_count'] = 0
                self.logger.info(f"✅ 账号 {phone} 重连成功")
            else:
                self.logger.warning(f"⚠️ 账号 {phone} 需要重新登录")
                self.client_status[phone]['status'] = 'unauthorized'
                
        except Exception as e:
            self.logger.error(f"❌ 重连失败 {phone}: {e}")
            await self._handle_client_error(phone, str(e))

    async def _handle_client_error(self, phone: str, error: str):
        """处理客户端错误"""
        if phone in self.client_status:
            self.client_status[phone]['error_count'] += 1
            error_count = self.client_status[phone]['error_count']
            
            # 更新数据库
            await self.database.update_account_status(phone, 'error', error_count)
            
            # 如果错误次数过多，暂停账号
            if error_count >= 5:
                self.client_status[phone]['status'] = 'suspended'
                self.logger.warning(f"⚠️ 账号 {phone} 错误次数过多，已暂停使用")

    async def get_account_list(self) -> List[Dict[str, Any]]:
        """获取账号列表"""
        try:
            accounts = await self.database.get_listener_accounts()
            
            # 添加实时状态信息
            for account in accounts:
                phone = account['phone']
                if phone in self.client_status:
                    account.update(self.client_status[phone])
                else:
                    account['status'] = 'offline'
                    account['error_count'] = 0
            
            return accounts
            
        except Exception as e:
            self.logger.error(f"❌ 获取账号列表失败: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """获取账号统计信息"""
        try:
            accounts = await self.get_account_list()
            
            total = len(accounts)
            active = len([a for a in accounts if a.get('status') == 'active'])
            error = len([a for a in accounts if a.get('status') == 'error'])
            offline = total - active - error
            
            return {
                'total': total,
                'active': active,
                'error': error,
                'offline': offline,
                'usage_rate': round(active / total * 100, 2) if total > 0 else 0,
                'accounts': accounts
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                'total': 0,
                'active': 0,
                'error': 0,
                'offline': 0,
                'usage_rate': 0,
                'accounts': []
            }

    async def reload_config(self):
        """重新加载配置"""
        self.logger.info("📝 账号管理器重新加载配置")
        # 配置重载时可以调整轮换策略等