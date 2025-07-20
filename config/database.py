"""
数据库操作 - 支持搬运组
"""

import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "data/forwarder.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._connection = None
        
    async def init(self):
        """初始化数据库"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        logging.info(f"数据库初始化完成: {self.db_path}")

    async def close(self):
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_tables(self):
        """创建数据库表"""
        
        # API池表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS api_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT UNIQUE NOT NULL,
                app_hash TEXT NOT NULL,
                max_accounts INTEGER DEFAULT 3,
                current_accounts INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 监听账号表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS listener_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                username TEXT,
                api_id TEXT,
                status TEXT DEFAULT 'active',
                last_active TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api_pool (app_id)
            )
        ''')

        # 发送Bot表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS sender_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                username TEXT,
                status TEXT DEFAULT 'active',
                last_used TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 搬运组表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS forwarding_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                schedule_start TEXT,
                schedule_end TEXT,
                filters TEXT,
                footer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 源频道表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS source_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                channel_username TEXT,
                channel_title TEXT,
                last_message_id INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES forwarding_groups (id) ON DELETE CASCADE
            )
        ''')

        # 目标频道表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS target_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                channel_username TEXT,
                channel_title TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES forwarding_groups (id) ON DELETE CASCADE
            )
        ''')

        # 消息记录表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                source_message_id INTEGER NOT NULL,
                target_message_id INTEGER,
                source_channel_id INTEGER NOT NULL,
                target_channel_id INTEGER NOT NULL,
                content_hash TEXT,
                status TEXT DEFAULT 'sent',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES forwarding_groups (id)
            )
        ''')

        # 统计表
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                account_phone TEXT,
                message_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES forwarding_groups (id)
            )
        ''')

        # 创建索引
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_message_history_hash ON message_history(content_hash)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_message_history_group ON message_history(group_id)')
        await self._connection.execute('CREATE INDEX IF NOT EXISTS idx_statistics_date ON statistics(date)')

        await self._connection.commit()

    # API池管理
    async def add_api(self, app_id: str, app_hash: str, max_accounts: int = 3) -> bool:
        """添加API ID到池中"""
        try:
            await self._connection.execute(
                'INSERT INTO api_pool (app_id, app_hash, max_accounts) VALUES (?, ?, ?)',
                (app_id, app_hash, max_accounts)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"添加API失败: {e}")
            return False

    async def get_available_api(self) -> Optional[Dict[str, Any]]:
        """获取可用的API ID"""
        cursor = await self._connection.execute('''
            SELECT * FROM api_pool 
            WHERE status = 'active' AND current_accounts < max_accounts
            ORDER BY current_accounts ASC, id ASC
            LIMIT 1
        ''')
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def assign_api_to_account(self, app_id: str, phone: str) -> bool:
        """将API分配给账号"""
        try:
            # 更新API使用计数
            await self._connection.execute(
                'UPDATE api_pool SET current_accounts = current_accounts + 1, updated_at = CURRENT_TIMESTAMP WHERE app_id = ?',
                (app_id,)
            )
            
            # 更新账号的API关联
            await self._connection.execute(
                'UPDATE listener_accounts SET api_id = ? WHERE phone = ?',
                (app_id, phone)
            )
            
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"分配API失败: {e}")
            return False

    async def release_api_from_account(self, phone: str) -> bool:
        """释放账号的API"""
        try:
            # 获取账号的API ID
            cursor = await self._connection.execute(
                'SELECT api_id FROM listener_accounts WHERE phone = ?',
                (phone,)
            )
            row = await cursor.fetchone()
            
            if row and row['api_id']:
                # 减少API使用计数
                await self._connection.execute(
                    'UPDATE api_pool SET current_accounts = current_accounts - 1, updated_at = CURRENT_TIMESTAMP WHERE app_id = ?',
                    (row['api_id'],)
                )
                
                # 清除账号的API关联
                await self._connection.execute(
                    'UPDATE listener_accounts SET api_id = NULL WHERE phone = ?',
                    (phone,)
                )
                
                await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"释放API失败: {e}")
            return False

    async def get_api_pool_status(self) -> List[Dict[str, Any]]:
        """获取API池状态"""
        cursor = await self._connection.execute('''
            SELECT 
                ap.*,
                GROUP_CONCAT(la.phone) as assigned_accounts
            FROM api_pool ap
            LEFT JOIN listener_accounts la ON ap.app_id = la.api_id
            GROUP BY ap.id
            ORDER BY ap.id
        ''')
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data['assigned_accounts'] = data['assigned_accounts'].split(',') if data['assigned_accounts'] else []
            result.append(data)
        return result

    # 账号管理
    async def add_listener_account(self, phone: str, user_id: int = None, username: str = None) -> bool:
        """添加监听账号"""
        try:
            await self._connection.execute(
                'INSERT OR REPLACE INTO listener_accounts (phone, user_id, username, last_active) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                (phone, user_id, username)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"添加监听账号失败: {e}")
            return False

    async def get_listener_accounts(self, status: str = 'active') -> List[Dict[str, Any]]:
        """获取监听账号列表"""
        cursor = await self._connection.execute(
            'SELECT * FROM listener_accounts WHERE status = ? ORDER BY id',
            (status,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_account_status(self, phone: str, status: str, error_count: int = None) -> bool:
        """更新账号状态"""
        try:
            if error_count is not None:
                await self._connection.execute(
                    'UPDATE listener_accounts SET status = ?, error_count = ?, last_active = CURRENT_TIMESTAMP WHERE phone = ?',
                    (status, error_count, phone)
                )
            else:
                await self._connection.execute(
                    'UPDATE listener_accounts SET status = ?, last_active = CURRENT_TIMESTAMP WHERE phone = ?',
                    (status, phone)
                )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"更新账号状态失败: {e}")
            return False

    # 搬运组管理
    async def create_forwarding_group(self, name: str, description: str = None) -> Optional[int]:
        """创建搬运组"""
        try:
            cursor = await self._connection.execute(
                'INSERT INTO forwarding_groups (name, description) VALUES (?, ?)',
                (name, description)
            )
            await self._connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logging.error(f"创建搬运组失败: {e}")
            return None

    async def get_forwarding_groups(self) -> List[Dict[str, Any]]:
        """获取所有搬运组"""
        cursor = await self._connection.execute(
            'SELECT * FROM forwarding_groups ORDER BY id'
        )
        rows = await cursor.fetchall()
        groups = []
        for row in rows:
            group = dict(row)
            # 解析过滤器JSON
            if group['filters']:
                try:
                    group['filters'] = json.loads(group['filters'])
                except:
                    group['filters'] = {}
            else:
                group['filters'] = {}
            groups.append(group)
        return groups

    async def get_forwarding_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """获取单个搬运组"""
        cursor = await self._connection.execute(
            'SELECT * FROM forwarding_groups WHERE id = ?',
            (group_id,)
        )
        row = await cursor.fetchone()
        if row:
            group = dict(row)
            if group['filters']:
                try:
                    group['filters'] = json.loads(group['filters'])
                except:
                    group['filters'] = {}
            else:
                group['filters'] = {}
            return group
        return None

    async def update_group_filters(self, group_id: int, filters: Dict[str, Any]) -> bool:
        """更新组过滤器"""
        try:
            await self._connection.execute(
                'UPDATE forwarding_groups SET filters = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (json.dumps(filters), group_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"更新组过滤器失败: {e}")
            return False

    async def set_group_schedule(self, group_id: int, start_time: str, end_time: str) -> bool:
        """设置组调度"""
        try:
            await self._connection.execute(
                'UPDATE forwarding_groups SET schedule_start = ?, schedule_end = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (start_time, end_time, group_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"设置组调度失败: {e}")
            return False

    # 频道管理
    async def add_source_channel(self, group_id: int, channel_id: int, channel_username: str = None, channel_title: str = None) -> bool:
        """添加源频道"""
        try:
            await self._connection.execute(
                'INSERT OR REPLACE INTO source_channels (group_id, channel_id, channel_username, channel_title) VALUES (?, ?, ?, ?)',
                (group_id, channel_id, channel_username, channel_title)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"添加源频道失败: {e}")
            return False

    async def add_target_channel(self, group_id: int, channel_id: int, channel_username: str = None, channel_title: str = None) -> bool:
        """添加目标频道"""
        try:
            await self._connection.execute(
                'INSERT OR REPLACE INTO target_channels (group_id, channel_id, channel_username, channel_title) VALUES (?, ?, ?, ?)',
                (group_id, channel_id, channel_username, channel_title)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"添加目标频道失败: {e}")
            return False

    async def get_group_channels(self, group_id: int) -> Tuple[List[Dict], List[Dict]]:
        """获取组的源频道和目标频道"""
        # 获取源频道
        cursor = await self._connection.execute(
            'SELECT * FROM source_channels WHERE group_id = ? AND status = "active"',
            (group_id,)
        )
        source_channels = [dict(row) for row in await cursor.fetchall()]

        # 获取目标频道
        cursor = await self._connection.execute(
            'SELECT * FROM target_channels WHERE group_id = ? AND status = "active"',
            (group_id,)
        )
        target_channels = [dict(row) for row in await cursor.fetchall()]

        return source_channels, target_channels

    async def update_last_message_id(self, group_id: int, channel_id: int, message_id: int) -> bool:
        """更新最后处理的消息ID"""
        try:
            await self._connection.execute(
                'UPDATE source_channels SET last_message_id = ? WHERE group_id = ? AND channel_id = ?',
                (message_id, group_id, channel_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"更新最后消息ID失败: {e}")
            return False

    # 消息记录
    async def is_message_forwarded(self, content_hash: str) -> bool:
        """检查消息是否已转发"""
        cursor = await self._connection.execute(
            'SELECT 1 FROM message_history WHERE content_hash = ? LIMIT 1',
            (content_hash,)
        )
        row = await cursor.fetchone()
        return row is not None

    async def add_message_record(self, group_id: int, source_message_id: int, target_message_id: int,
                               source_channel_id: int, target_channel_id: int, content_hash: str) -> bool:
        """添加消息记录"""
        try:
            await self._connection.execute(
                '''INSERT INTO message_history 
                   (group_id, source_message_id, target_message_id, source_channel_id, target_channel_id, content_hash) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (group_id, source_message_id, target_message_id, source_channel_id, target_channel_id, content_hash)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"添加消息记录失败: {e}")
            return False

    # 统计
    async def update_statistics(self, group_id: int, account_phone: str, success: bool = True) -> bool:
        """更新统计信息"""
        try:
            today = datetime.now().date()
            
            # 检查今天的记录是否存在
            cursor = await self._connection.execute(
                'SELECT id FROM statistics WHERE group_id = ? AND account_phone = ? AND date = ?',
                (group_id, account_phone, today)
            )
            row = await cursor.fetchone()
            
            if row:
                # 更新现有记录
                if success:
                    await self._connection.execute(
                        'UPDATE statistics SET message_count = message_count + 1, success_count = success_count + 1 WHERE id = ?',
                        (row['id'],)
                    )
                else:
                    await self._connection.execute(
                        'UPDATE statistics SET message_count = message_count + 1, error_count = error_count + 1 WHERE id = ?',
                        (row['id'],)
                    )
            else:
                # 创建新记录
                success_count = 1 if success else 0
                error_count = 0 if success else 1
                await self._connection.execute(
                    'INSERT INTO statistics (group_id, account_phone, message_count, success_count, error_count, date) VALUES (?, ?, 1, ?, ?, ?)',
                    (group_id, account_phone, success_count, error_count, today)
                )
            
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"更新统计失败: {e}")
            return False

    async def get_group_statistics(self, group_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """获取组统计信息"""
        start_date = (datetime.now() - timedelta(days=days)).date()
        cursor = await self._connection.execute(
            '''SELECT 
                date,
                SUM(message_count) as total_messages,
                SUM(success_count) as total_success,
                SUM(error_count) as total_errors,
                ROUND(SUM(success_count) * 100.0 / SUM(message_count), 2) as success_rate
               FROM statistics 
               WHERE group_id = ? AND date >= ?
               GROUP BY date
               ORDER BY date DESC''',
            (group_id, start_date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_account_statistics(self, account_phone: str, days: int = 7) -> List[Dict[str, Any]]:
        """获取账号统计信息"""
        start_date = (datetime.now() - timedelta(days=days)).date()
        cursor = await self._connection.execute(
            '''SELECT 
                fg.name as group_name,
                SUM(s.message_count) as total_messages,
                SUM(s.success_count) as total_success,
                SUM(s.error_count) as total_errors,
                ROUND(SUM(s.success_count) * 100.0 / SUM(s.message_count), 2) as success_rate
               FROM statistics s
               LEFT JOIN forwarding_groups fg ON s.group_id = fg.id
               WHERE s.account_phone = ? AND s.date >= ?
               GROUP BY s.group_id
               ORDER BY total_messages DESC''',
            (account_phone, start_date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # 清理
    async def cleanup_old_data(self, days: int = 30) -> bool:
        """清理旧数据"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).date()
            
            # 清理旧的消息记录
            await self._connection.execute(
                'DELETE FROM message_history WHERE sent_at < ?',
                (cutoff_date,)
            )
            
            # 清理旧的统计数据
            await self._connection.execute(
                'DELETE FROM statistics WHERE date < ?',
                (cutoff_date,)
            )
            
            await self._connection.commit()
            return True
        except Exception as e:
            logging.error(f"清理旧数据失败: {e}")
            return False