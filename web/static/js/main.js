/**
 * Telegram Forwarder Web管理界面主要JavaScript文件
 */

// 全局配置
const CONFIG = {
    API_BASE_URL: '',
    SOCKET_NAMESPACE: '/',
    NOTIFICATION_TIMEOUT: 3000,
    AUTO_REFRESH_INTERVAL: 30000,
    WEBSOCKET_RECONNECT_INTERVAL: 5000
};

// 全局状态管理
const AppState = {
    socket: null,
    isConnected: false,
    user: null,
    notifications: [],
    autoRefreshTimers: new Map(),
    currentPage: null
};

/**
 * 应用初始化
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

/**
 * 初始化应用
 */
function initializeApp() {
    console.log('🚀 初始化Telegram Forwarder Web应用');
    
    // 初始化Socket.IO连接
    initializeSocket();
    
    // 初始化主题
    initializeTheme();
    
    // 初始化通知系统
    initializeNotifications();
    
    // 初始化页面特定功能
    initializePageFeatures();
    
    // 初始化全局事件监听器
    initializeGlobalEventListeners();
    
    console.log('✅ 应用初始化完成');
}

/**
 * 初始化Socket.IO连接
 */
function initializeSocket() {
    try {
        AppState.socket = io(CONFIG.SOCKET_NAMESPACE);
        
        // 连接事件
        AppState.socket.on('connect', function() {
            console.log('🔌 WebSocket连接成功');
            AppState.isConnected = true;
            updateConnectionStatus(true);
            showNotification('服务器连接成功', 'success');
        });
        
        // 断开连接事件
        AppState.socket.on('disconnect', function() {
            console.log('🔌 WebSocket连接断开');
            AppState.isConnected = false;
            updateConnectionStatus(false);
            showNotification('服务器连接断开', 'warning');
            
            // 自动重连
            setTimeout(() => {
                if (!AppState.isConnected) {
                    AppState.socket.connect();
                }
            }, CONFIG.WEBSOCKET_RECONNECT_INTERVAL);
        });
        
        // 状态更新事件
        AppState.socket.on('status_update', function(data) {
            console.log('📊 收到状态更新', data);
            handleStatusUpdate(data);
        });
        
        // 通知事件
        AppState.socket.on('notification', function(data) {
            showNotification(data.message, data.type);
        });
        
    } catch (error) {
        console.error('❌ Socket.IO初始化失败:', error);
        updateConnectionStatus(false);
    }
}

/**
 * 更新连接状态显示
 */
function updateConnectionStatus(connected) {
    const statusDot = document.getElementById('connection-status');
    const statusText = document.getElementById('connection-text');
    
    if (statusDot) {
        statusDot.className = connected ? 'status-dot status-online' : 'status-dot status-offline';
    }
    
    if (statusText) {
        statusText.textContent = connected ? '已连接' : '连接断开';
    }
}

/**
 * 处理状态更新
 */
function handleStatusUpdate(data) {
    // 更新页面特定的状态
    if (typeof updateDashboard === 'function') {
        updateDashboard(data);
    }
    
    // 更新全局状态指示器
    updateGlobalStatus(data);
}

/**
 * 更新全局状态
 */
function updateGlobalStatus(data) {
    // 更新通知计数
    const notificationCount = document.getElementById('notification-count');
    if (notificationCount && data.notifications) {
        notificationCount.textContent = data.notifications.count || 0;
    }
}

/**
 * 初始化主题系统
 */
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
}

/**
 * 设置主题
 */
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // 更新主题切换按钮
    const themeButton = document.querySelector('[onclick="toggleTheme()"]');
    if (themeButton) {
        const icon = themeButton.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
}

/**
 * 切换主题
 */
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    showNotification(`已切换到${newTheme === 'dark' ? '暗色' : '亮色'}主题`, 'info');
}

/**
 * 初始化通知系统
 */
function initializeNotifications() {
    // 创建通知容器
    if (!document.getElementById('notification-container')) {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            max-width: 20rem;
        `;
        document.body.appendChild(container);
    }
}

/**
 * 显示通知
 */
function showNotification(message, type = 'info', timeout = CONFIG.NOTIFICATION_TIMEOUT) {
    const container = document.getElementById('notification-container');
    if (!container) return;
    
    const notification = document.createElement('div');
    const notificationId = Date.now().toString();
    
    notification.id = `notification-${notificationId}`;
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex items-center">
                <i class="fas fa-${getNotificationIcon(type)} mr-2"></i>
                <span>${message}</span>
            </div>
            <button onclick="closeNotification('${notificationId}')" class="ml-3 text-white hover:text-gray-200">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    container.appendChild(notification);
    AppState.notifications.push({ id: notificationId, element: notification });
    
    // 添加进入动画
    requestAnimationFrame(() => {
        notification.style.animation = 'slideInRight 0.3s ease-out';
    });
    
    // 自动关闭
    if (timeout > 0) {
        setTimeout(() => {
            closeNotification(notificationId);
        }, timeout);
    }
    
    return notificationId;
}

/**
 * 获取通知图标
 */
function getNotificationIcon(type) {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

/**
 * 关闭通知
 */
function closeNotification(notificationId) {
    const notification = document.getElementById(`notification-${notificationId}`);
    if (notification) {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            notification.remove();
            AppState.notifications = AppState.notifications.filter(n => n.id !== notificationId);
        }, 300);
    }
}

/**
 * 初始化页面特定功能
 */
function initializePageFeatures() {
    const pageName = getPageName();
    AppState.currentPage = pageName;
    
    console.log(`📄 初始化页面功能: ${pageName}`);
    
    switch (pageName) {
        case 'dashboard':
            initializeDashboard();
            break;
        case 'groups':
            initializeGroups();
            break;
        case 'accounts':
            initializeAccounts();
            break;
        case 'settings':
            initializeSettings();
            break;
        case 'logs':
            initializeLogs();
            break;
    }
}

/**
 * 获取当前页面名称
 */
function getPageName() {
    const path = window.location.pathname;
    if (path === '/' || path === '/dashboard') return 'dashboard';
    if (path.startsWith('/groups')) return 'groups';
    if (path.startsWith('/accounts')) return 'accounts';
    if (path.startsWith('/settings')) return 'settings';
    if (path.startsWith('/logs')) return 'logs';
    return 'unknown';
}

/**
 * 初始化仪表板
 */
function initializeDashboard() {
    // 启动自动刷新
    startAutoRefresh('dashboard', loadDashboardData, CONFIG.AUTO_REFRESH_INTERVAL);
    
    // 请求初始状态更新
    if (AppState.socket && AppState.isConnected) {
        AppState.socket.emit('request_status');
    }
}

/**
 * 初始化搬运组页面
 */
function initializeGroups() {
    // 加载搬运组数据
    if (typeof loadGroups === 'function') {
        loadGroups();
    }
}

/**
 * 初始化账号页面
 */
function initializeAccounts() {
    // 加载账号数据
    if (typeof loadAccounts === 'function') {
        loadAccounts();
    }
    
    // 启动自动刷新
    startAutoRefresh('accounts', loadAccounts, CONFIG.AUTO_REFRESH_INTERVAL);
}

/**
 * 初始化设置页面
 */
function initializeSettings() {
    // 加载设置数据
    if (typeof loadSettings === 'function') {
        loadSettings();
    }
}

/**
 * 初始化日志页面
 */
function initializeLogs() {
    // 加载日志数据
    if (typeof loadLogs === 'function') {
        loadLogs();
    }
}

/**
 * 启动自动刷新
 */
function startAutoRefresh(name, callback, interval) {
    stopAutoRefresh(name);
    
    const timerId = setInterval(() => {
        if (typeof callback === 'function') {
            try {
                callback();
            } catch (error) {
                console.error(`❌ 自动刷新执行失败 (${name}):`, error);
            }
        }
    }, interval);
    
    AppState.autoRefreshTimers.set(name, timerId);
    console.log(`🔄 启动自动刷新: ${name} (${interval}ms)`);
}

/**
 * 停止自动刷新
 */
function stopAutoRefresh(name) {
    const timerId = AppState.autoRefreshTimers.get(name);
    if (timerId) {
        clearInterval(timerId);
        AppState.autoRefreshTimers.delete(name);
        console.log(`⏹️ 停止自动刷新: ${name}`);
    }
}

/**
 * 加载仪表板数据
 */
async function loadDashboardData() {
    try {
        const status = await apiRequest('/api/status');
        handleStatusUpdate(status);
    } catch (error) {
        console.error('❌ 加载仪表板数据失败:', error);
    }
}

/**
 * 初始化全局事件监听器
 */
function initializeGlobalEventListeners() {
    // 页面可见性变化
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            // 页面隐藏时暂停自动刷新
            console.log('⏸️ 页面隐藏，暂停自动刷新');
        } else {
            // 页面显示时恢复自动刷新
            console.log('▶️ 页面显示，恢复自动刷新');
            if (AppState.currentPage === 'dashboard') {
                loadDashboardData();
            }
        }
    });
    
    // 窗口聚焦/失焦
    window.addEventListener('focus', function() {
        // 重新连接WebSocket（如果断开）
        if (!AppState.isConnected && AppState.socket) {
            AppState.socket.connect();
        }
    });
    
    // 键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl+K 或 Cmd+K 打开搜索
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            openGlobalSearch();
        }
        
        // ESC 关闭模态框
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
}

/**
 * 打开全局搜索
 */
function openGlobalSearch() {
    console.log('🔍 打开全局搜索');
    showNotification('全局搜索功能将在未来版本中实现', 'info');
}

/**
 * 关闭所有模态框
 */
function closeAllModals() {
    const modals = document.querySelectorAll('.modal:not(.hidden)');
    modals.forEach(modal => {
        modal.classList.add('hidden');
    });
}

/**
 * 通用API请求函数
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    };
    
    try {
        const response = await fetch(CONFIG.API_BASE_URL + url, defaultOptions);
        
        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            
            try {
                const errorData = JSON.parse(errorText);
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                // 如果不是JSON，使用默认错误消息
            }
            
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        return data;
        
    } catch (error) {
        console.error('❌ API请求失败:', error);
        
        // 根据错误类型显示不同的提示
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showNotification('网络连接失败，请检查网络状态', 'error');
        } else if (error.message.includes('401')) {
            showNotification('登录已过期，请重新登录', 'warning');
            // 可以添加重定向到登录页面的逻辑
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
        } else {
            showNotification(`请求失败: ${error.message}`, 'error');
        }
        
        throw error;
    }
}

/**
 * 格式化时间
 */
function formatTime(timestamp) {
    if (!timestamp) return '--:--:--';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) {
        return '刚刚';
    } else if (diffInMinutes < 60) {
        return `${diffInMinutes}分钟前`;
    } else if (diffInMinutes < 24 * 60) {
        const hours = Math.floor(diffInMinutes / 60);
        return `${hours}小时前`;
    } else {
        return date.toLocaleString('zh-CN');
    }
}

/**
 * 格式化文件大小
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化数字
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * 防抖函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 切换侧边栏（移动端）
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    
    if (sidebar && overlay) {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('hidden');
    }
}

/**
 * 复制文本到剪贴板
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('已复制到剪贴板', 'success');
        return true;
    } catch (error) {
        console.error('❌ 复制失败:', error);
        
        // 降级方案
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showNotification('已复制到剪贴板', 'success');
            return true;
        } catch (fallbackError) {
            showNotification('复制失败', 'error');
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

/**
 * 下载文件
 */
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showNotification('文件下载已开始', 'info');
}

/**
 * 确认对话框
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        if (typeof callback === 'function') {
            callback();
        }
        return true;
    }
    return false;
}

/**
 * 加载状态管理
 */
const LoadingState = {
    elements: new Map(),
    
    start(element, text = '加载中...') {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        const originalContent = element.innerHTML;
        this.elements.set(element, originalContent);
        
        element.innerHTML = `
            <div class="flex items-center justify-center">
                <div class="spinner mr-2"></div>
                <span>${text}</span>
            </div>
        `;
        element.disabled = true;
    },
    
    stop(element) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (!element) return;
        
        const originalContent = this.elements.get(element);
        if (originalContent) {
            element.innerHTML = originalContent;
            this.elements.delete(element);
        }
        
        element.disabled = false;
    }
};

/**
 * 页面离开时的清理工作
 */
window.addEventListener('beforeunload', function() {
    // 清理所有自动刷新定时器
    AppState.autoRefreshTimers.forEach((timerId, name) => {
        clearInterval(timerId);
        console.log(`🧹 清理自动刷新定时器: ${name}`);
    });
    
    // 断开Socket连接
    if (AppState.socket) {
        AppState.socket.disconnect();
    }
});

// 导出全局函数供模板使用
window.showNotification = showNotification;
window.closeNotification = closeNotification;
window.apiRequest = apiRequest;
window.formatTime = formatTime;
window.formatBytes = formatBytes;
window.formatNumber = formatNumber;
window.toggleTheme = toggleTheme;
window.toggleSidebar = toggleSidebar;
window.copyToClipboard = copyToClipboard;
window.downloadFile = downloadFile;
window.confirmAction = confirmAction;
window.LoadingState = LoadingState;

console.log('📦 主要JavaScript文件加载完成');
