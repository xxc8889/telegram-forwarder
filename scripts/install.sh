#!/bin/bash

# Telegram Forwarder 一键安装脚本
# 支持 Ubuntu 20.04+ / CentOS 7+ / Debian 10+

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

log_blue() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "检测到root用户，建议使用普通用户运行"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
        log_info "检测到操作系统: $PRETTY_NAME"
    else
        log_error "无法检测操作系统"
        exit 1
    fi
}

# 检查Python版本
check_python() {
    log_info "检查Python环境..."
    
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
    elif command -v python3.10 &> /dev/null; then
        PYTHON_CMD=python3.10
    elif command -v python3.9 &> /dev/null; then
        PYTHON_CMD=python3.9
    elif command -v python3.8 &> /dev/null; then
        PYTHON_CMD=python3.8
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
        # 检查版本
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
        if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
            log_error "Python版本过低: $PYTHON_VERSION，需要Python 3.8+"
            install_python
        fi
    else
        log_warn "未找到Python3，开始安装..."
        install_python
    fi
    
    log_info "使用Python: $($PYTHON_CMD --version)"
}

# 安装Python
install_python() {
    case $OS in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv python3-dev
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                sudo dnf install -y python3 python3-pip python3-venv python3-devel
            else
                sudo yum install -y python3 python3-pip python3-venv python3-devel
            fi
            ;;
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac
    
    PYTHON_CMD=python3
}

# 安装系统依赖
install_dependencies() {
    log_info "安装系统依赖..."
    
    case $OS in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y \
                build-essential \
                libssl-dev \
                libffi-dev \
                git \
                curl \
                wget \
                unzip \
                sqlite3 \
                cron
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                sudo dnf groupinstall -y "Development Tools"
                sudo dnf install -y \
                    openssl-devel \
                    libffi-devel \
                    git \
                    curl \
                    wget \
                    unzip \
                    sqlite \
                    cronie
            else
                sudo yum groupinstall -y "Development Tools"
                sudo yum install -y \
                    openssl-devel \
                    libffi-devel \
                    git \
                    curl \
                    wget \
                    unzip \
                    sqlite \
                    cronie
            fi
            ;;
    esac
}

# 创建虚拟环境
create_venv() {
    log_info "创建Python虚拟环境..."
    
    if [[ ! -d "venv" ]]; then
        $PYTHON_CMD -m venv venv
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    log_info "虚拟环境创建完成"
}

# 安装Python依赖
install_python_deps() {
    log_info "安装Python依赖包..."
    
    source venv/bin/activate
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_info "依赖包安装完成"
    else
        log_error "未找到requirements.txt文件"
        exit 1
    fi
}

# 创建目录结构
create_directories() {
    log_info "创建目录结构..."
    
    mkdir -p data logs sessions backup
    chmod 755 data logs sessions backup
    
    log_info "目录创建完成"
}

# 复制配置文件
setup_config() {
    log_info "设置配置文件..."
    
    if [[ ! -f ".env" ]] && [[ -f ".env.example" ]]; then
        cp .env.example .env
        log_warn "已创建.env配置文件，请编辑填入真实值"
    fi
    
    if [[ -f "examples/config.yaml.example" ]] && [[ ! -f "config.yaml" ]]; then
        cp examples/config.yaml.example config.yaml
        log_info "已创建config.yaml配置文件"
    fi
}

# 设置系统服务
setup_service() {
    log_info "设置系统服务..."
    
    if [[ -f "examples/systemd.service.example" ]]; then
        SERVICE_FILE="/etc/systemd/system/telegram-forwarder.service"
        
        # 替换路径变量
        sed "s|/path/to/telegram-forwarder|$(pwd)|g" examples/systemd.service.example > /tmp/telegram-forwarder.service
        sed -i "s|User=ubuntu|User=$(whoami)|g" /tmp/telegram-forwarder.service
        
        sudo mv /tmp/telegram-forwarder.service $SERVICE_FILE
        sudo systemctl daemon-reload
        sudo systemctl enable telegram-forwarder
        
        log_info "系统服务已设置"
    fi
}

# 设置权限
set_permissions() {
    log_info "设置文件权限..."
    
    chmod +x scripts/*.sh
    chmod 600 .env 2>/dev/null || true
    chmod 755 main.py
    
    log_info "权限设置完成"
}

# 运行测试
run_tests() {
    log_info "运行环境测试..."
    
    source venv/bin/activate
    
    # 测试Python导入
    $PYTHON_CMD -c "
import sys
print(f'Python版本: {sys.version}')

try:
    import telethon
    import telegram
    import asyncio
    import sqlite3
    print('✅ 核心依赖导入成功')
except ImportError as e:
    print(f'❌ 依赖导入失败: {e}')
    sys.exit(1)

print('✅ 环境测试通过')
"
}

# 显示完成信息
show_completion() {
    log_info "🎉 安装完成！"
    echo
    log_blue "下一步操作:"
    echo "现在将运行设置向导帮助您完成配置..."
    echo
    
    # 询问是否运行设置向导
    read -p "是否运行设置向导? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        log_info "启动设置向导..."
        ./scripts/setup_wizard.sh
    else
        log_blue "手动配置步骤:"
        echo "1. 复制配置文件: cp .env.example .env"
        echo "2. 编辑配置文件: vim .env"
        echo "3. 填入Bot Token和管理员ID"
        echo "4. 启动服务: ./scripts/service.sh start"
        echo "5. 访问Web界面: http://YOUR_SERVER_IP:8080"
        echo
        log_blue "配置示例:"
        echo "BOT_TOKEN=your_bot_token_here"
        echo "ADMIN_USERS=123456789,987654321"
        echo "ENCRYPTION_KEY=$(openssl rand -hex 16)"
        echo
    fi
    
    log_warn "⚠️  配置完成后建议将GitHub仓库设为私有!"
    echo

# 主函数
main() {
    echo -e "${BLUE}"
    echo "================================================"
    echo "    Telegram Forwarder 一键安装脚本"
    echo "================================================"
    echo -e "${NC}"
    
    check_root
    detect_os
    check_python
    install_dependencies
    create_venv
    install_python_deps
    create_directories
    setup_config
    setup_service
    set_permissions
    run_tests
    show_completion
}

# 错误处理
trap 'log_error "安装过程中发生错误，退出代码: $?"' ERR

# 运行主函数
main "$@"