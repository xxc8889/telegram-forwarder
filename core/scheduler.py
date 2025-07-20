"""
任务调度器 - 管理定时任务和调度
"""

import asyncio
import logging
from datetime import datetime, time as dt_time
from typing import Dict, List, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)
        
        # 调度器
        self.scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')
        self.is_running = False
        
        # 任务状态
        self.scheduled_jobs = {}
        self.job_status = {}

    async def start(self):
        """启动任务调度器"""
        self.logger.info("🔄 启动任务调度器...")
        
        # 启动调度器
        self.scheduler.start()
        
        # 添加系统任务
        await self._add_system_jobs()
        
        # 加载组调度任务
        await self._load_group_schedules()
        
        self.is_running = True
        self.logger.info("✅ 任务调度器启动完成")

    async def stop(self):
        """停止任务调度器"""
        self.logger.info("🛑 停止任务调度器...")
        self.is_running = False
        
        # 停止调度器
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
        
        self.scheduled_jobs.clear()
        self.job_status.clear()
        
        self.logger.info("✅ 任务调度器已停止")

    async def _add_system_jobs(self):
        """添加系统任务"""
        try:
            # 每日数据清理任务 (凌晨2点)
            self.scheduler.add_job(
                self._cleanup_daily_task,
                CronTrigger(hour=2, minute=0),
                id='daily_cleanup',
                name='每日数据清理',
                max_instances=1
            )
            
            # 每小时状态检查任务
            self.scheduler.add_job(
                self._hourly_check_task,
                CronTrigger(minute=0),
                id='hourly_check',
                name='每小时状态检查',
                max_instances=1
            )
            
            # 每10分钟配置同步任务
            self.scheduler.add_job(
                self._config_sync_task,
                CronTrigger(minute='*/10'),
                id='config_sync',
                name='配置同步检查',
                max_instances=1
            )
            
            self.logger.info("📅 系统任务添加完成")
            
        except Exception as e:
            self.logger.error(f"❌ 添加系统任务失败: {e}")

    async def _load_group_schedules(self):
        """加载组调度任务"""
        try:
            groups = await self.database.get_forwarding_groups()
            
            for group in groups:
                if group['schedule_start'] and group['schedule_end']:
                    await self._add_group_schedule(
                        group['id'],
                        group['schedule_start'],
                        group['schedule_end']
                    )
            
            self.logger.info(f"📅 加载 {len([g for g in groups if g['schedule_start']])} 个组调度任务")
            
        except Exception as e:
            self.logger.error(f"❌ 加载组调度任务失败: {e}")

    async def _add_group_schedule(self, group_id: int, start_time: str, end_time: str):
        """添加组调度任务"""
        try:
            # 解析时间
            start_hour, start_minute = map(int, start_time.split(':'))
            end_hour, end_minute = map(int, end_time.split(':'))
            
            # 启动任务
            start_job_id = f'group_{group_id}_start'
            self.scheduler.add_job(
                self._activate_group,
                CronTrigger(hour=start_hour, minute=start_minute),
                args=[group_id],
                id=start_job_id,
                name=f'启动组{group_id}',
                max_instances=1,
                replace_existing=True
            )
            
            # 停止任务
            end_job_id = f'group_{group_id}_end'
            self.scheduler.add_job(
                self._deactivate_group,
                CronTrigger(hour=end_hour, minute=end_minute),
                args=[group_id],
                id=end_job_id,
                name=f'停止组{group_id}',
                max_instances=1,
                replace_existing=True
            )
            
            # 记录任务
            self.scheduled_jobs[group_id] = {
                'start_job_id': start_job_id,
                'end_job_id': end_job_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            # 检查当前是否在调度时间内
            await self._check_current_schedule_status(group_id, start_time, end_time)
            
            self.logger.info(f"📅 添加组调度: 组{group_id} ({start_time}-{end_time})")
            
        except Exception as e:
            self.logger.error(f"❌ 添加组调度失败: {e}")

    async def _check_current_schedule_status(self, group_id: int, start_time: str, end_time: str):
        """检查当前调度状态"""
        try:
            now = datetime.now().time()
            start = dt_time.fromisoformat(start_time)
            end = dt_time.fromisoformat(end_time)
            
            is_active = False
            if start <= end:
                # 同一天的时间段
                is_active = start <= now <= end
            else:
                # 跨天的时间段
                is_active = now >= start or now <= end
            
            # 更新组状态
            status = 'active' if is_active else 'scheduled'
            await self._update_group_status(group_id, status)
            
        except Exception as e:
            self.logger.error(f"❌ 检查当前调度状态失败: {e}")

    async def _activate_group(self, group_id: int):
        """激活组"""
        try:
            await self._update_group_status(group_id, 'active')
            self.logger.info(f"🟢 组{group_id} 已按调度激活")
            
        except Exception as e:
            self.logger.error(f"❌ 激活组失败: {e}")

    async def _deactivate_group(self, group_id: int):
        """停用组"""
        try:
            await self._update_group_status(group_id, 'scheduled')
            self.logger.info(f"🔴 组{group_id} 已按调度停用")
            
        except Exception as e:
            self.logger.error(f"❌ 停用组失败: {e}")

    async def _update_group_status(self, group_id: int, status: str):
        """更新组状态"""
        try:
            await self.database._connection.execute(
                'UPDATE forwarding_groups SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (status, group_id)
            )
            await self.database._connection.commit()
            
            # 更新任务状态
            self.job_status[group_id] = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ 更新组状态失败: {e}")

    async def _cleanup_daily_task(self):
        """每日清理任务"""
        try:
            self.logger.info("🧹 开始每日数据清理...")
            
            # 清理旧数据
            retention_days = self.settings.log_retention_days
            await self.database.cleanup_old_data(retention_days)
            
            # 清理旧日志文件
            await self._cleanup_old_logs()
            
            # 备份数据
            if self.settings.backup_enabled:
                await self._backup_data()
            
            self.logger.info("✅ 每日数据清理完成")
            
        except Exception as e:
            self.logger.error(f"❌ 每日清理任务失败: {e}")

    async def _hourly_check_task(self):
        """每小时检查任务"""
        try:
            self.logger.debug("🔍 开始每小时状态检查...")
            
            # 检查系统状态
            # 这里可以添加系统健康检查逻辑
            
            self.logger.debug("✅ 每小时状态检查完成")
            
        except Exception as e:
            self.logger.error(f"❌ 每小时检查任务失败: {e}")

    async def _config_sync_task(self):
        """配置同步任务"""
        try:
            self.logger.debug("🔄 开始配置同步检查...")
            
            # 检查是否有新的组调度需要加载
            current_groups = await self.database.get_forwarding_groups()
            
            for group in current_groups:
                group_id = group['id']
                
                # 检查是否有调度但未添加任务
                if group['schedule_start'] and group['schedule_end']:
                    if group_id not in self.scheduled_jobs:
                        await self._add_group_schedule(
                            group_id,
                            group['schedule_start'],
                            group['schedule_end']
                        )
                        self.logger.info(f"📅 自动添加新的组调度: 组{group_id}")
                
                # 检查是否取消了调度
                elif group_id in self.scheduled_jobs:
                    await self._remove_group_schedule(group_id)
                    self.logger.info(f"📅 自动移除组调度: 组{group_id}")
            
            self.logger.debug("✅ 配置同步检查完成")
            
        except Exception as e:
            self.logger.error(f"❌ 配置同步任务失败: {e}")

    async def _cleanup_old_logs(self):
        """清理旧日志文件"""
        try:
            import os
            from pathlib import Path
            from datetime import datetime, timedelta
            
            log_dir = Path('logs')
            if not log_dir.exists():
                return
            
            # 删除超过保留期的日志文件
            cutoff_date = datetime.now() - timedelta(days=self.settings.log_retention_days)
            
            for log_file in log_dir.glob('*.log*'):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    self.logger.info(f"🗑️ 删除旧日志文件: {log_file}")
            
        except Exception as e:
            self.logger.error(f"❌ 清理日志文件失败: {e}")

    async def _backup_data(self):
        """备份数据"""
        try:
            import shutil
            from pathlib import Path
            from datetime import datetime
            
            backup_dir = Path('backup')
            backup_dir.mkdir(exist_ok=True)
            
            # 备份数据库
            db_file = Path('data/forwarder.db')
            if db_file.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = backup_dir / f'forwarder_{timestamp}.db'
                shutil.copy2(db_file, backup_file)
                self.logger.info(f"💾 数据库备份完成: {backup_file}")
            
            # 清理旧备份
            backup_files = sorted(backup_dir.glob('forwarder_*.db'))
            if len(backup_files) > 7:  # 保留最近7个备份
                for old_backup in backup_files[:-7]:
                    old_backup.unlink()
                    self.logger.info(f"🗑️ 删除旧备份: {old_backup}")
            
        except Exception as e:
            self.logger.error(f"❌ 备份数据失败: {e}")

    async def add_group_schedule(self, group_id: int, start_time: str, end_time: str) -> Dict[str, Any]:
        """添加组调度"""
        try:
            # 验证时间格式
            try:
                dt_time.fromisoformat(start_time)
                dt_time.fromisoformat(end_time)
            except ValueError:
                return {'status': 'error', 'message': '时间格式错误，请使用 HH:MM 格式'}
            
            # 添加到调度器
            await self._add_group_schedule(group_id, start_time, end_time)
            
            # 更新数据库
            await self.database.set_group_schedule(group_id, start_time, end_time)
            
            return {
                'status': 'success',
                'message': f'调度设置成功: {start_time}-{end_time}'
            }
            
        except Exception as e:
            self.logger.error(f"❌ 添加组调度失败: {e}")
            return {'status': 'error', 'message': f'设置失败: {str(e)}'}

    async def remove_group_schedule(self, group_id: int) -> Dict[str, Any]:
        """移除组调度"""
        try:
            await self._remove_group_schedule(group_id)
            
            # 更新数据库
            await self.database.set_group_schedule(group_id, None, None)
            
            return {'status': 'success', 'message': '调度已移除'}
            
        except Exception as e:
            self.logger.error(f"❌ 移除组调度失败: {e}")
            return {'status': 'error', 'message': f'移除失败: {str(e)}'}

    async def _remove_group_schedule(self, group_id: int):
        """移除组调度任务"""
        try:
            if group_id in self.scheduled_jobs:
                job_info = self.scheduled_jobs[group_id]
                
                # 移除调度任务
                try:
                    self.scheduler.remove_job(job_info['start_job_id'])
                    self.scheduler.remove_job(job_info['end_job_id'])
                except:
                    pass  # 任务可能已经不存在
                
                # 清理记录
                del self.scheduled_jobs[group_id]
                if group_id in self.job_status:
                    del self.job_status[group_id]
                
                self.logger.info(f"📅 移除组调度: 组{group_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 移除组调度任务失败: {e}")

    async def get_schedule_status(self, group_id: int = None) -> Dict[str, Any]:
        """获取调度状态"""
        try:
            if group_id:
                # 获取指定组的调度状态
                if group_id in self.scheduled_jobs:
                    job_info = self.scheduled_jobs[group_id]
                    status = self.job_status.get(group_id, {})
                    
                    return {
                        'group_id': group_id,
                        'scheduled': True,
                        'start_time': job_info['start_time'],
                        'end_time': job_info['end_time'],
                        'current_status': status.get('status', 'unknown'),
                        'last_updated': status.get('updated_at')
                    }
                else:
                    return {
                        'group_id': group_id,
                        'scheduled': False,
                        'message': '该组未设置调度'
                    }
            else:
                # 获取所有调度状态
                all_schedules = []
                
                for group_id, job_info in self.scheduled_jobs.items():
                    status = self.job_status.get(group_id, {})
                    all_schedules.append({
                        'group_id': group_id,
                        'start_time': job_info['start_time'],
                        'end_time': job_info['end_time'],
                        'current_status': status.get('status', 'unknown'),
                        'last_updated': status.get('updated_at')
                    })
                
                return {
                    'total_scheduled': len(all_schedules),
                    'scheduler_running': self.scheduler.running,
                    'schedules': all_schedules
                }
                
        except Exception as e:
            self.logger.error(f"❌ 获取调度状态失败: {e}")
            return {'error': f'获取状态失败: {str(e)}'}

    async def get_job_statistics(self) -> Dict[str, Any]:
        """获取任务统计"""
        try:
            jobs = self.scheduler.get_jobs()
            
            system_jobs = [j for j in jobs if j.id in ['daily_cleanup', 'hourly_check', 'config_sync']]
            group_jobs = [j for j in jobs if j.id not in ['daily_cleanup', 'hourly_check', 'config_sync']]
            
            return {
                'total_jobs': len(jobs),
                'system_jobs': len(system_jobs),
                'group_jobs': len(group_jobs),
                'scheduled_groups': len(self.scheduled_jobs),
                'scheduler_running': self.scheduler.running,
                'is_running': self.is_running
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取任务统计失败: {e}")
            return {
                'total_jobs': 0,
                'system_jobs': 0,
                'group_jobs': 0,
                'scheduled_groups': 0,
                'scheduler_running': False,
                'is_running': False
            }

    async def reload_config(self):
        """重新加载配置"""
        self.logger.info("📝 任务调度器重新加载配置")
        # 重新加载组调度
        await self._load_group_schedules()