"""
监控和状态查看命令处理器
"""

import logging
import psutil
import platform
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from ..middleware import admin_required, error_handler
from utils.logger import get_log_stats, get_recent_logs


class MonitorHandlers:
    """监控处理器"""
    
    def __init__(self, settings, database, account_manager, group_processor, task_scheduler):
        self.settings = settings
        self.database = database
        self.account_manager = account_manager
        self.group_processor = group_processor
        self.task_scheduler = task_scheduler
        self.logger = logging.getLogger(__name__)

    @admin_required
    @error_handler
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看系统状态"""
        try:
            # 获取各组件状态
            account_stats = await self.account_manager.get_statistics()
            group_stats = await self.group_processor.get_statistics()
            scheduler_stats = await self.task_scheduler.get_job_statistics()
            
            status_text = f"""
🖥️ **系统状态总览**

📊 **组件状态**
• 账号管理器: {'🟢 运行中' if self.account_manager.is_running else '🔴 已停止'}
• 组处理器: {'🟢 运行中' if self.group_processor.is_running else '🔴 已停止'}
• 任务调度器: {'🟢 运行中' if self.task_scheduler.is_running else '🔴 已停止'}

👥 **账号统计**
• 总账号: {account_stats['total']}
• 活跃账号: {account_stats['active']} 
• 错误账号: {account_stats['error']}
• 使用率: {account_stats['usage_rate']}%

📋 **搬运组统计**
• 总组数: {group_stats['total_groups']}
• 活跃组: {group_stats['active_groups']}
• 源频道: {group_stats['total_source_channels']}
• 目标频道: {group_stats['total_target_channels']}

⏰ **调度任务**
• 总任务: {scheduler_stats['total_jobs']}
• 系统任务: {scheduler_stats['system_jobs']}
• 组任务: {scheduler_stats['group_jobs']}
• 调度器: {'🟢 运行中' if scheduler_stats['scheduler_running'] else '🔴 已停止'}

🔧 **全局配置**
• 发送间隔: {self.settings.min_interval}-{self.settings.max_interval}秒
• 每小时限制: {self.settings.hourly_limit}条
• 轮换策略: {self.settings.rotation_strategy}
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            await update.message.reply_text(f"❌ 获取状态失败: {str(e)}")

    @admin_required
    @error_handler
    async def system_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看系统信息"""
        try:
            # 获取系统信息
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            # 获取进程信息
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # 系统运行时间
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            system_info = f"""
💻 **系统信息**

**基本信息**
• 操作系统: {platform.system()} {platform.release()}
• Python版本: {platform.python_version()}
• 架构: {platform.machine()}
• 处理器: {platform.processor() or 'Unknown'}

**资源使用**
• CPU使用率: {cpu_percent:.1f}%
• 内存使用: {memory.percent:.1f}% ({memory.used/1024/1024/1024:.1f}GB/{memory.total/1024/1024/1024:.1f}GB)
• 磁盘使用: {disk.percent:.1f}% ({disk.used/1024/1024/1024:.1f}GB/{disk.total/1024/1024/1024:.1f}GB)

**进程信息**
• 进程内存: {process_memory.rss/1024/1024:.1f}MB
• 进程ID: {process.pid}
• 线程数: {process.num_threads()}

**运行时间**
• 系统启动: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}
• 系统运行: {str(uptime).split('.')[0]}
            """
            
            await update.message.reply_text(system_info, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取系统信息失败: {e}")
            await update.message.reply_text(f"❌ 获取信息失败: {str(e)}")

    @admin_required
    @error_handler
    async def global_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看全局状态"""
        try:
            # 获取详细统计
            account_stats = await self.account_manager.get_statistics()
            group_stats = await self.group_processor.get_statistics()
            
            # 获取今日统计
            today_stats = {}
            try:
                # 这里应该从数据库获取今日统计
                today_stats = {
                    'total_messages': 0,
                    'success_messages': 0,
                    'error_messages': 0,
                    'success_rate': 0
                }
            except:
                pass
            
            global_status = f"""
📊 **全局状态详情**

**今日统计** (截至 {datetime.now().strftime('%H:%M')})
• 处理消息: {today_stats.get('total_messages', 0)}条
• 成功转发: {today_stats.get('success_messages', 0)}条
• 失败消息: {today_stats.get('error_messages', 0)}条
• 成功率: {today_stats.get('success_rate', 0):.1f}%

**账号详情**
• 活跃账号: {account_stats['active']}/{account_stats['total']}
• 账号健康度: {account_stats['usage_rate']:.1f}%
• 错误账号: {account_stats['error']}个
• 离线账号: {account_stats['offline']}个

**频道详情**
• 监听频道: {group_stats['total_source_channels']}个
• 目标频道: {group_stats['total_target_channels']}个
• 活跃搬运组: {group_stats['active_groups']}/{group_stats['total_groups']}

**性能指标**
• 发送间隔: {self.settings.min_interval}-{self.settings.max_interval}秒
• 每小时限制: {self.settings.hourly_limit}条
• 重试次数: {self.settings.retry_attempts}次
• 轮换策略: {self.settings.rotation_strategy}

**系统健康**
• 内存使用: {psutil.virtual_memory().percent:.1f}%
• CPU使用: {psutil.cpu_percent():.1f}%
• 磁盘使用: {psutil.disk_usage('.').percent:.1f}%
            """
            
            await update.message.reply_text(global_status, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取全局状态失败: {e}")
            await update.message.reply_text(f"❌ 获取状态失败: {str(e)}")

    @admin_required
    @error_handler
    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看日志"""
        try:
            lines = int(context.args[0]) if context.args else 20
            
            if lines > 100:
                await update.message.reply_text("❌ 日志行数不能超过100行")
                return
            
            # 获取最近日志
            recent_logs = get_recent_logs(lines=lines)
            
            if not recent_logs:
                await update.message.reply_text("📝 暂无日志记录")
                return
            
            # 格式化日志
            log_text = f"📝 **最近 {len(recent_logs)} 行日志**\n\n```\n"
            
            for log_line in recent_logs[-20:]:  # 只显示最后20行避免消息过长
                # 简化日志格式
                if len(log_line) > 100:
                    log_line = log_line[:100] + "..."
                log_text += log_line + "\n"
            
            log_text += "```"
            
            # 如果日志太长，分割发送
            if len(log_text) > 4000:
                log_text = log_text[:4000] + "...\n```\n\n使用 `/logs 10` 获取更少日志"
            
            await update.message.reply_text(log_text, parse_mode='Markdown')
            
            # 获取日志统计
            log_stats = get_log_stats()
            if 'error' not in log_stats:
                stats_text = f"""
📊 **日志统计**
• 总行数: {log_stats['total_lines']}
• ERROR: {log_stats['ERROR']}
• WARNING: {log_stats['WARNING']}
• INFO: {log_stats['INFO']}
• 文件大小: {log_stats['file_size']/1024:.1f}KB
                """
                await update.message.reply_text(stats_text)
            
        except ValueError:
            await update.message.reply_text("❌ 日志行数必须是数字")
        except Exception as e:
            self.logger.error(f"获取日志失败: {e}")
            await update.message.reply_text(f"❌ 获取日志失败: {str(e)}")

    @admin_required
    @error_handler
    async def schedule_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看调度状态"""
        try:
            group_id = int(context.args[0]) if context.args else None
            
            schedule_status = await self.task_scheduler.get_schedule_status(group_id)
            
            if group_id:
                # 查看指定组的调度状态
                if schedule_status.get('scheduled'):
                    status_text = f"""
⏰ **组{group_id} 调度状态**

• 调度状态: ✅ 已设置
• 开始时间: {schedule_status['start_time']}
• 结束时间: {schedule_status['end_time']}
• 当前状态: {schedule_status['current_status']}
• 最后更新: {schedule_status.get('last_updated', '未知')}
                    """
                else:
                    status_text = f"⏰ 组{group_id} 未设置调度，全天运行"
            else:
                # 查看所有调度状态
                schedules = schedule_status.get('schedules', [])
                
                status_text = f"""
⏰ **调度状态总览**

• 总调度任务: {schedule_status['total_scheduled']}
• 调度器状态: {'🟢 运行中' if schedule_status['scheduler_running'] else '🔴 已停止'}

**调度详情**
                """
                
                for schedule in schedules:
                    status_text += f"""
• **组{schedule['group_id']}**
  时间: {schedule['start_time']}-{schedule['end_time']}
  状态: {schedule['current_status']}
                    """
                
                if not schedules:
                    status_text += "\n暂无调度任务"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ 组ID必须是数字")
        except Exception as e:
            self.logger.error(f"获取调度状态失败: {e}")
            await update.message.reply_text(f"❌ 获取状态失败: {str(e)}")

    @admin_required
    @error_handler
    async def performance_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看性能统计"""
        try:
            # 获取系统性能指标
            cpu_times = psutil.cpu_times()
            memory_info = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            net_io = psutil.net_io_counters()
            
            perf_text = f"""
📈 **性能统计**

**CPU信息**
• 用户时间: {cpu_times.user:.1f}s
• 系统时间: {cpu_times.system:.1f}s
• 空闲时间: {cpu_times.idle:.1f}s

**内存信息**
• 总内存: {memory_info.total/1024/1024/1024:.1f}GB
• 可用内存: {memory_info.available/1024/1024/1024:.1f}GB
• 使用率: {memory_info.percent:.1f}%
• 缓存: {memory_info.cached/1024/1024/1024:.1f}GB

**磁盘IO**
• 读取: {disk_io.read_bytes/1024/1024:.1f}MB
• 写入: {disk_io.write_bytes/1024/1024:.1f}MB
• 读取次数: {disk_io.read_count}
• 写入次数: {disk_io.write_count}

**网络IO**
• 接收: {net_io.bytes_recv/1024/1024:.1f}MB
• 发送: {net_io.bytes_sent/1024/1024:.1f}MB
• 接收包: {net_io.packets_recv}
• 发送包: {net_io.packets_sent}
            """
            
            await update.message.reply_text(perf_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"获取性能统计失败: {e}")
            await update.message.reply_text(f"❌ 获取统计失败: {str(e)}")

    @admin_required
    @error_handler
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """系统健康检查"""
        try:
            health_status = []
            
            # 检查组件状态
            if self.account_manager.is_running:
                health_status.append("✅ 账号管理器: 正常")
            else:
                health_status.append("❌ 账号管理器: 异常")
            
            if self.group_processor.is_running:
                health_status.append("✅ 组处理器: 正常")
            else:
                health_status.append("❌ 组处理器: 异常")
            
            if self.task_scheduler.is_running:
                health_status.append("✅ 任务调度器: 正常")
            else:
                health_status.append("❌ 任务调度器: 异常")
            
            # 检查资源使用
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('.').percent
            
            if cpu_percent < 80:
                health_status.append(f"✅ CPU使用率: {cpu_percent:.1f}% (正常)")
            else:
                health_status.append(f"⚠️ CPU使用率: {cpu_percent:.1f}% (偏高)")
            
            if memory_percent < 80:
                health_status.append(f"✅ 内存使用率: {memory_percent:.1f}% (正常)")
            else:
                health_status.append(f"⚠️ 内存使用率: {memory_percent:.1f}% (偏高)")
            
            if disk_percent < 90:
                health_status.append(f"✅ 磁盘使用率: {disk_percent:.1f}% (正常)")
            else:
                health_status.append(f"⚠️ 磁盘使用率: {disk_percent:.1f}% (偏高)")
            
            # 检查配置文件
            from pathlib import Path
            if Path('.env').exists():
                health_status.append("✅ 配置文件: 正常")
            else:
                health_status.append("❌ 配置文件: 缺失")
            
            health_text = f"""
🏥 **系统健康检查**

{chr(10).join(health_status)}

**检查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            await update.message.reply_text(health_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            await update.message.reply_text(f"❌ 健康检查失败: {str(e)}")