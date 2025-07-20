"""
API池管理器 - 管理多个API ID的分配和使用
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any


class APIPoolManager:
    """API池管理器"""
    
    def __init__(self, database):
        self.database = database
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self._lock = asyncio.Lock()

    async def start(self):
        """启动API池管理器"""
        self.logger.info("🔄 启动API池管理器...")
        self.is_running = True
        
        # 检查是否有可用的API
        apis = await self.get_pool_status()
        if not apis:
            self.logger.warning("⚠️ 未发现任何API ID，请通过Bot添加")
        else:
            self.logger.info(f"📊 发现 {len(apis)} 个API ID")
        
        self.logger.info("✅ API池管理器启动完成")

    async def stop(self):
        """停止API池管理器"""
        self.logger.info("🛑 停止API池管理器...")
        self.is_running = False
        self.logger.info("✅ API池管理器已停止")

    async def add_api(self, app_id: str, app_hash: str, max_accounts: int = 1) -> bool:
        """添加API ID到池中"""
        async with self._lock:
            try:
                # 验证API格式
                if not app_id.isdigit():
                    self.logger.error(f"❌ 无效的API ID格式: {app_id}")
                    return False
                
                if not app_hash or len(app_hash) != 32:
                    self.logger.error(f"❌ 无效的API Hash格式: {app_hash}")
                    return False
                
                # 添加到数据库
                success = await self.database.add_api(app_id, app_hash, max_accounts)
                
                if success:
                    self.logger.info(f"✅ 成功添加API ID: {app_id}")
                    return True
                else:
                    self.logger.error(f"❌ 添加API ID失败: {app_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"❌ 添加API异常: {e}")
                return False

    async def remove_api(self, app_id: str) -> bool:
        """移除API ID"""
        async with self._lock:
            try:
                # 检查是否有账号正在使用
                status = await self.get_api_status(app_id)
                if status and status.get('assigned_accounts'):
                    self.logger.error(f"❌ API {app_id} 正在被使用，无法删除")
                    return False
                
                # 从数据库删除
                await self.database._connection.execute(
                    'DELETE FROM api_pool WHERE app_id = ?',
                    (app_id,)
                )
                await self.database._connection.commit()
                
                self.logger.info(f"✅ 成功移除API ID: {app_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"❌ 移除API异常: {e}")
                return False

    async def get_available_api(self) -> Optional[Dict[str, Any]]:
        """获取可用的API ID"""
        try:
            api = await self.database.get_available_api()
            
            if api:
                self.logger.debug(f"🎯 分配可用API: {api['app_id']}")
                return api
            else:
                self.logger.warning("⚠️ 没有可用的API ID")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取可用API异常: {e}")
            return None

    async def assign_api_to_account(self, phone: str) -> Optional[Dict[str, Any]]:
        """为账号分配API"""
        async with self._lock:
            try:
                # 检查账号是否已分配API
                existing_api = await self.get_account_api(phone)
                if existing_api:
                    self.logger.info(f"📱 账号 {phone} 已分配API: {existing_api['app_id']}")
                    return existing_api
                
                # 获取可用API
                api = await self.get_available_api()
                if not api:
                    self.logger.error(f"❌ 无可用API分配给账号: {phone}")
                    return None
                
                # 分配API给账号
                success = await self.database.assign_api_to_account(api['app_id'], phone)
                
                if success:
                    self.logger.info(f"✅ 成功为账号 {phone} 分配API: {api['app_id']}")
                    return api
                else:
                    self.logger.error(f"❌ 分配API失败: {phone}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"❌ 分配API异常: {e}")
                return None

    async def release_api_from_account(self, phone: str) -> bool:
        """释放账号的API"""
        async with self._lock:
            try:
                success = await self.database.release_api_from_account(phone)
                
                if success:
                    self.logger.info(f"✅ 成功释放账号 {phone} 的API")
                else:
                    self.logger.warning(f"⚠️ 释放账号API失败: {phone}")
                
                return success
                
            except Exception as e:
                self.logger.error(f"❌ 释放API异常: {e}")
                return False

    async def get_account_api(self, phone: str) -> Optional[Dict[str, Any]]:
        """获取账号分配的API"""
        try:
            cursor = await self.database._connection.execute('''
                SELECT ap.* FROM api_pool ap
                JOIN listener_accounts la ON ap.app_id = la.api_id
                WHERE la.phone = ?
            ''', (phone,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            self.logger.error(f"❌ 获取账号API异常: {e}")
            return None

    async def get_api_status(self, app_id: str) -> Optional[Dict[str, Any]]:
        """获取指定API状态"""
        try:
            cursor = await self.database._connection.execute('''
                SELECT 
                    ap.*,
                    GROUP_CONCAT(la.phone) as assigned_accounts
                FROM api_pool ap
                LEFT JOIN listener_accounts la ON ap.app_id = la.api_id
                WHERE ap.app_id = ?
                GROUP BY ap.id
            ''', (app_id,))
            
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                data['assigned_accounts'] = data['assigned_accounts'].split(',') if data['assigned_accounts'] else []
                return data
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 获取API状态异常: {e}")
            return None

    async def get_pool_status(self) -> List[Dict[str, Any]]:
        """获取整个API池状态"""
        try:
            return await self.database.get_api_pool_status()
        except Exception as e:
            self.logger.error(f"❌ 获取API池状态异常: {e}")
            return []

    async def rebalance_apis(self) -> bool:
        """重新平衡API分配"""
        async with self._lock:
            try:
                self.logger.info("🔄 开始重新平衡API分配...")
                
                # 获取所有API和账号
                apis = await self.get_pool_status()
                accounts = await self.database.get_listener_accounts()
                
                if not apis:
                    self.logger.warning("⚠️ 没有可用的API")
                    return False
                
                # 计算理想分配
                total_accounts = len(accounts)
                accounts_per_api = total_accounts // len(apis)
                extra_accounts = total_accounts % len(apis)
                
                # 重新分配
                account_index = 0
                for i, api in enumerate(apis):
                    # 计算这个API应该分配的账号数
                    target_count = accounts_per_api + (1 if i < extra_accounts else 0)
                    
                    # 清除当前分配
                    await self.database._connection.execute(
                        'UPDATE listener_accounts SET api_id = NULL WHERE api_id = ?',
                        (api['app_id'],)
                    )
                    
                    # 重新分配账号
                    for j in range(target_count):
                        if account_index < total_accounts:
                            account = accounts[account_index]
                            await self.database.assign_api_to_account(api['app_id'], account['phone'])
                            account_index += 1
                
                # 更新API使用计数
                for api in apis:
                    cursor = await self.database._connection.execute(
                        'SELECT COUNT(*) as count FROM listener_accounts WHERE api_id = ?',
                        (api['app_id'],)
                    )
                    row = await cursor.fetchone()
                    count = row['count'] if row else 0
                    
                    await self.database._connection.execute(
                        'UPDATE api_pool SET current_accounts = ?, updated_at = CURRENT_TIMESTAMP WHERE app_id = ?',
                        (count, api['app_id'])
                    )
                
                await self.database._connection.commit()
                self.logger.info("✅ API重新平衡完成")
                return True
                
            except Exception as e:
                self.logger.error(f"❌ API重新平衡异常: {e}")
                return False

    async def get_statistics(self) -> Dict[str, Any]:
        """获取API池统计信息"""
        try:
            apis = await self.get_pool_status()
            
            total_apis = len(apis)
            total_capacity = sum(api['max_accounts'] for api in apis)
            total_used = sum(api['current_accounts'] for api in apis)
            usage_rate = (total_used / total_capacity * 100) if total_capacity > 0 else 0
            
            return {
                'total_apis': total_apis,
                'total_capacity': total_capacity,
                'total_used': total_used,
                'available': total_capacity - total_used,
                'usage_rate': round(usage_rate, 2),
                'apis': apis
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取API统计异常: {e}")
            return {
                'total_apis': 0,
                'total_capacity': 0,
                'total_used': 0,
                'available': 0,
                'usage_rate': 0,
                'apis': []
            }
