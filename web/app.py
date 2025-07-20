"""
Web管理界面 - Flask应用主文件 (增强版)
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import secrets
import time

# 导入项目模块
import sys
sys.path.append('..')
from config.settings import Settings
from config.database import Database
from web.auth import AuthManager
from utils.logger import get_recent_logs, get_log_stats


class WebApp:
    """Web应用管理器"""
    
    def __init__(self, settings, database):
        self.settings = settings
        self.database = database
        self.logger = logging.getLogger(__name__)
        
        # 创建Flask应用
        self.app = Flask(__name__)
        self.app.secret_key = os.getenv('WEB_SECRET_KEY', secrets.token_hex(32))
        
        # 配置SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 认证管理器
        self.auth_manager = AuthManager(settings)
        
        # 注册路由
        self._register_routes()
        self._register_socketio_events()
        
        # Web配置
        self.app.config.update({
            'SECRET_KEY': self.app.secret_key,
            'SESSION_TIMEOUT': 3600,  # 1小时
            'WEB_HOST': os.getenv('WEB_HOST', '0.0.0.0'),
            'WEB_PORT': int(os.getenv('WEB_PORT', 8080)),
            'WEB_DEBUG': os.getenv('WEB_DEBUG', 'False').lower() == 'true'
        })

    def _register_routes(self):
        """注册Web路由"""
        
        @self.app.route('/')
        def index():
            """首页 - 重定向到仪表板"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            return redirect(url_for('dashboard'))

        @self.app.route('/login')
        def login():
            """登录页面"""
            return render_template('login.html')

        @self.app.route('/api/request-login-code', methods=['POST'])
        def request_login_code():
            """请求登录码"""
            try:
                login_code = self.auth_manager.generate_login_code()
                return jsonify({
                    'success': True,
                    'login_code': login_code,
                    'expires_in': 300,  # 5分钟
                    'message': f'登录码: {login_code}，请发送给Bot进行验证'
                })
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})

        @self.app.route('/api/check-login/<login_code>')
        def check_login(login_code):
            """检查登录状态"""
            try:
                if self.auth_manager.verify_login_code(login_code):
                    # 设置session
                    session['authenticated'] = True
                    session['login_time'] = time.time()
                    session['admin_user'] = self.auth_manager.get_user_by_code(login_code)
                    
                    return jsonify({
                        'success': True,
                        'redirect': url_for('dashboard')
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': '登录码无效或已过期'
                    })
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})

        @self.app.route('/dashboard')
        def dashboard():
            """仪表板"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            
            return render_template('dashboard.html', 
                                 user=session.get('admin_user'),
                                 page_title='仪表板')

        @self.app.route('/groups')
        def groups():
            """搬运组管理"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            
            return render_template('groups.html',
                                 user=session.get('admin_user'),
                                 page_title='搬运组管理')

        @self.app.route('/accounts')
        def accounts():
            """账号管理"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            
            return render_template('accounts.html',
                                 user=session.get('admin_user'),
                                 page_title='账号管理')

        @self.app.route('/settings')
        def settings():
            """系统设置"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            
            return render_template('settings.html',
                                 user=session.get('admin_user'),
                                 page_title='系统设置')

        @self.app.route('/logs')
        def logs():
            """日志查看"""
            if not self._is_authenticated():
                return redirect(url_for('login'))
            
            return render_template('logs.html',
                                 user=session.get('admin_user'),
                                 page_title='系统日志')

        @self.app.route('/logout')
        def logout():
            """退出登录"""
            session.clear()
            flash('已退出登录', 'info')
            return redirect(url_for('login'))

        # API路由
        self._register_api_routes()

    def _register_api_routes(self):
        """注册API路由"""
        
        @self.app.route('/api/status')
        def api_status():
            """获取系统状态"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    status = asyncio.run(ForwarderManager.instance.get_status())
                    return jsonify(status)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/groups')
        def api_groups():
            """获取搬运组列表"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    groups = asyncio.run(ForwarderManager.instance.get_groups())
                    return jsonify(groups)
                else:
                    return jsonify([])
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/groups/<int:group_id>')
        def api_group_info(group_id):
            """获取组详情"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    group = asyncio.run(ForwarderManager.instance.get_group_info(group_id))
                    if group:
                        return jsonify(group)
                    else:
                        return jsonify({'error': 'Group not found'}), 404
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/groups', methods=['POST'])
        def api_create_group():
            """创建搬运组"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                data = request.get_json()
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.create_group(
                        data['name'], 
                        data.get('description')
                    ))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/groups/<int:group_id>', methods=['PUT'])
        def api_update_group(group_id):
            """更新搬运组"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                data = request.get_json()
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.update_group(group_id, **data))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/groups/<int:group_id>', methods=['DELETE'])
        def api_delete_group(group_id):
            """删除搬运组"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.delete_group(group_id))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/accounts')
        def api_accounts():
            """获取账号列表"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    accounts = asyncio.run(ForwarderManager.instance.get_accounts())
                    return jsonify(accounts)
                else:
                    return jsonify([])
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/accounts/<path:phone>')
        def api_account_info(phone):
            """获取账号详情"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    account = asyncio.run(ForwarderManager.instance.get_account_info(phone))
                    if account:
                        return jsonify(account)
                    else:
                        return jsonify({'error': 'Account not found'}), 404
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/accounts/<path:phone>', methods=['DELETE'])
        def api_delete_account(phone):
            """删除账号"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.remove_account(phone))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/api-pool')
        def api_api_pool():
            """获取API池状态"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    status = asyncio.run(ForwarderManager.instance.get_api_pool_status())
                    return jsonify(status)
                else:
                    return jsonify({'apis': [], 'total_apis': 0})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/api-pool', methods=['POST'])
        def api_add_api():
            """添加API"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                data = request.get_json()
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.add_api(
                        data['app_id'],
                        data['app_hash'],
                        data.get('max_accounts', 1)
                    ))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/api-pool/<app_id>', methods=['DELETE'])
        def api_delete_api(app_id):
            """删除API"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.remove_api(app_id))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/logs')
        def api_logs():
            """获取系统日志"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                lines = request.args.get('lines', 50, type=int)
                level = request.args.get('level', 'ALL')
                
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.get_logs(level, lines))
                    return jsonify(result)
                else:
                    return jsonify({'logs': [], 'stats': {}})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/settings')
        def api_get_settings():
            """获取系统设置"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                settings = {
                    'min_interval': self.settings.min_interval,
                    'max_interval': self.settings.max_interval,
                    'hourly_limit': self.settings.hourly_limit,
                    'retry_attempts': self.settings.retry_attempts,
                    'media_timeout': self.settings.media_timeout,
                    'rotation_strategy': self.settings.rotation_strategy,
                    'remove_links': self.settings.remove_links,
                    'remove_emojis': self.settings.remove_emojis,
                    'remove_special_chars': self.settings.remove_special_chars,
                    'ad_detection': self.settings.ad_detection,
                    'smart_filter': self.settings.smart_filter,
                    'session_encryption': self.settings.session_encryption,
                    'log_retention_days': self.settings.log_retention_days,
                    'backup_enabled': self.settings.backup_enabled
                }
                return jsonify(settings)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/settings/<section>', methods=['PUT'])
        def api_update_settings(section):
            """更新系统设置"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                data = request.get_json()
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    result = asyncio.run(ForwarderManager.instance.update_settings(section, data))
                    return jsonify(result)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/system-info')
        def api_system_info():
            """获取系统信息"""
            if not self._is_authenticated():
                return jsonify({'error': 'Unauthorized'}), 401
            
            try:
                from core.manager import ForwarderManager
                
                if ForwarderManager.instance:
                    info = asyncio.run(ForwarderManager.instance.get_system_info())
                    return jsonify(info)
                else:
                    return jsonify({'error': 'System not initialized'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def _register_socketio_events(self):
        """注册SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接"""
            if not self._is_authenticated():
                return False
            
            emit('status', {'message': '连接成功'})
            self.logger.info(f"Web客户端连接: {request.sid}")

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开"""
            self.logger.info(f"Web客户端断开: {request.sid}")

        @self.socketio.on('request_status')
        def handle_status_request():
            """请求状态更新"""
            if not self._is_authenticated():
                return
            
            # 获取实时状态并发送
            status = self._get_real_time_status()
            emit('status_update', status)

    def _is_authenticated(self):
        """检查用户是否已认证"""
        if not session.get('authenticated'):
            return False
        
        # 检查session是否过期
        login_time = session.get('login_time', 0)
        if time.time() - login_time > self.app.config['SESSION_TIMEOUT']:
            session.clear()
            return False
        
        return True

    def _get_real_time_status(self):
        """获取实时状态"""
        try:
            from core.manager import ForwarderManager
            
            if ForwarderManager.instance:
                status = asyncio.run(ForwarderManager.instance.get_status())
                return {
                    'timestamp': datetime.now().isoformat(),
                    'system_running': status['running'],
                    'components': status['components'],
                    'statistics': status['statistics']
                }
            else:
                return {'error': 'System not initialized'}
        except Exception as e:
            self.logger.error(f"获取实时状态失败: {e}")
            return {'error': str(e)}

    def run(self, host=None, port=None, debug=None):
        """启动Web应用"""
        host = host or self.app.config['WEB_HOST']
        port = port or self.app.config['WEB_PORT']
        debug = debug if debug is not None else self.app.config['WEB_DEBUG']
        
        self.logger.info(f"🌐 启动Web管理界面: http://{host}:{port}")
        
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )


# 全局变量，用于与Bot交互
web_app_instance = None

def get_web_app():
    """获取Web应用实例"""
    return web_app_instance

def set_web_app(app):
    """设置Web应用实例"""
    global web_app_instance
    web_app_instance = app