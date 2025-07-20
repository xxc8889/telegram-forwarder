#!/bin/bash

# Telegram Forwarder 服务管理脚本

SERVICE_NAME="telegram-forwarder"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root权限
check_root() {
    if [[ $EUID -ne 0 ]] && [[ "$1" == "install" || "$1" == "uninstall" ]]; then
        log_error "需要root权限执行此操作"
        echo "请使用: sudo $0 $1"
        exit 1
    fi
}

# 创建系统服务文件
create_service_file() {
    log_info "创建系统服务文件..."
    
    cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Telegram Channel Forwarder
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=$(whoami)
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${PROJECT_DIR}/venv/bin
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/main.py
StandardOutput=append:${PROJECT_DIR}/logs/service.log
StandardError=append:${PROJECT_DIR}/logs/service_error.log

# 资源限制
MemoryMax=1G
TasksMax=100

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${PROJECT_DIR}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    log_info "系统服务文件创建完成"
}

# 安装服务
install_service() {
    check_root "$1"
    
    log_info "安装 ${SERVICE_NAME} 服务..."
    
    # 检查项目目录
    if [[ ! -f "${PROJECT_DIR}/main.py" ]]; then
        log_error "项目目录不正确或main.py不存在"
        exit 1
    fi
    
    # 检查虚拟环境
    if [[ ! -f "${PROJECT_DIR}/venv/bin/python" ]]; then
        log_error "虚拟环境不存在，请先运行 ./install.sh"
        exit 1
    fi
    
    # 创建日志目录
    mkdir -p "${PROJECT_DIR}/logs"
    chown $(whoami):$(whoami) "${PROJECT_DIR}/logs"
    
    # 创建服务文件
    create_service_file
    
    # 启用服务
    systemctl enable "${SERVICE_NAME}"
    
    log_info "服务安装完成"
    log_info "使用以下命令管理服务:"
    echo "  启动: $0 start"
    echo "  停止: $0 stop"
    echo "  重启: $0 restart"
    echo "  状态: $0 status"
    echo "  日志: $0 logs"
}

# 卸载服务
uninstall_service() {
    check_root "$1"
    
    log_info "卸载 ${SERVICE_NAME} 服务..."
    
    # 停止并禁用服务
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    
    # 删除服务文件
    if [[ -f "${SERVICE_FILE}" ]]; then
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
    fi
    
    log_info "服务卸载完成"
}

# 启动服务
start_service() {
    log_info "启动 ${SERVICE_NAME} 服务..."
    
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_warn "服务已在运行"
        return
    fi
    
    systemctl start "${SERVICE_NAME}"
    
    # 等待启动
    sleep 2
    
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_info "服务启动成功"
    else
        log_error "服务启动失败"
        echo "查看错误日志: $0 logs"
        exit 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止 ${SERVICE_NAME} 服务..."
    
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_warn "服务未运行"
        return
    fi
    
    systemctl stop "${SERVICE_NAME}"
    
    # 等待停止
    sleep 2
    
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_info "服务停止成功"
    else
        log_error "服务停止失败"
        exit 1
    fi
}

# 重启服务
restart_service() {
    log_info "重启 ${SERVICE_NAME} 服务..."
    
    systemctl restart "${SERVICE_NAME}"
    
    # 等待重启
    sleep 3
    
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_info "服务重启成功"
    else
        log_error "服务重启失败"
        echo "查看错误日志: $0 logs"
        exit 1
    fi
}

# 查看服务状态
show_status() {
    echo -e "${BLUE}=== ${SERVICE_NAME} 服务状态 ===${NC}"
    
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        echo -e "开机启动: ${GREEN}已启用${NC}"
    else
        echo -e "开机启动: ${RED}未启用${NC}"
    fi
    
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo -e "运行状态: ${GREEN}运行中${NC}"
    else
        echo -e "运行状态: ${RED}未运行${NC}"
    fi
    
    echo
    echo -e "${BLUE}=== 详细状态 ===${NC}"
    systemctl status "${SERVICE_NAME}" --no-pager -l
    
    echo
    echo -e "${BLUE}=== 资源使用 ===${NC}"
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl show "${SERVICE_NAME}" --property=MainPID --value | xargs -I {} ps -p {} -o pid,ppid,%cpu,%mem,etime,cmd --no-headers 2>/dev/null || echo "无法获取进程信息"
    else
        echo "服务未运行"
    fi
}

# 查看日志
show_logs() {
    lines=${1:-50}
    
    echo -e "${BLUE}=== 最近 ${lines} 行日志 ===${NC}"
    
    if [[ -f "${PROJECT_DIR}/logs/service.log" ]]; then
        tail -n "${lines}" "${PROJECT_DIR}/logs/service.log"
    else
        echo "日志文件不存在"
    fi
    
    echo
    echo -e "${BLUE}=== 错误日志 ===${NC}"
    
    if [[ -f "${PROJECT_DIR}/logs/service_error.log" ]]; then
        tail -n "${lines}" "${PROJECT_DIR}/logs/service_error.log"
    else
        echo "错误日志文件不存在"
    fi
    
    echo
    echo -e "${BLUE}=== 系统日志 ===${NC}"
    journalctl -u "${SERVICE_NAME}" -n "${lines}" --no-pager
}

# 实时查看日志
follow_logs() {
    echo -e "${BLUE}=== 实时日志 (Ctrl+C 退出) ===${NC}"
    
    if [[ -f "${PROJECT_DIR}/logs/service.log" ]]; then
        tail -f "${PROJECT_DIR}/logs/service.log"
    else
        echo "日志文件不存在，查看系统日志:"
        journalctl -u "${SERVICE_NAME}" -f
    fi
}

# 检查服务健康状态
health_check() {
    echo -e "${BLUE}=== 健康检查 ===${NC}"
    
    # 检查服务状态
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo -e "✅ 服务状态: ${GREEN}正常${NC}"
    else
        echo -e "❌ 服务状态: ${RED}异常${NC}"
        return 1
    fi
    
    # 检查进程
    pid=$(systemctl show "${SERVICE_NAME}" --property=MainPID --value)
    if [[ -n "$pid" && "$pid" != "0" ]]; then
        echo -e "✅ 进程状态: ${GREEN}正常 (PID: $pid)${NC}"
    else
        echo -e "❌ 进程状态: ${RED}异常${NC}"
        return 1
    fi
    
    # 检查日志文件
    if [[ -f "${PROJECT_DIR}/logs/service.log" ]]; then
        log_size=$(stat -c%s "${PROJECT_DIR}/logs/service.log")
        echo -e "✅ 日志文件: ${GREEN}正常 (${log_size} bytes)${NC}"
    else
        echo -e "⚠️  日志文件: ${YELLOW}不存在${NC}"
    fi
    
    # 检查配置文件
    if [[ -f "${PROJECT_DIR}/.env" ]]; then
        echo -e "✅ 配置文件: ${GREEN}存在${NC}"
    else
        echo -e "❌ 配置文件: ${RED}不存在${NC}"
        return 1
    fi
    
    echo -e "\n${GREEN}健康检查完成${NC}"
}

# 显示帮助信息
show_help() {
    echo "Telegram Forwarder 服务管理脚本"
    echo
    echo "用法: $0 {install|uninstall|start|stop|restart|status|logs|follow|health|help}"
    echo
    echo "命令说明:"
    echo "  install   - 安装系统服务 (需要root权限)"
    echo "  uninstall - 卸载系统服务 (需要root权限)"
    echo "  start     - 启动服务"
    echo "  stop      - 停止服务"
    echo "  restart   - 重启服务"
    echo "  status    - 查看服务状态"
    echo "  logs [行数] - 查看日志 (默认50行)"
    echo "  follow    - 实时查看日志"
    echo "  health    - 健康检查"
    echo "  help      - 显示帮助信息"
    echo
    echo "示例:"
    echo "  $0 install     # 安装服务"
    echo "  $0 start       # 启动服务"
    echo "  $0 logs 100    # 查看最近100行日志"
    echo "  $0 follow      # 实时查看日志"
}

# 主逻辑
case "${1:-help}" in
    install)
        install_service "$1"
        ;;
    uninstall)
        uninstall_service "$1"
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    follow)
        follow_logs
        ;;
    health)
        health_check
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        echo
        show_help
        exit 1
        ;;
esac