#!/bin/bash

# Telegram Forwarder 设置向导

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 显示欢迎信息
show_welcome() {
    clear
    echo -e "${BLUE}"
    echo "================================================"
    echo "    Telegram Forwarder 设置向导"
    echo "    Welcome to Telegram Forwarder Setup Wizard"
    echo "================================================"
    echo -e "${NC}"
    echo
    echo "此向导将帮助您完成初始配置"
    echo "This wizard will help you complete the initial configuration"
    echo
    read -p "按Enter键继续... (Press Enter to continue...)" -r
}

# 配置Bot Token
setup_bot_token() {
    echo
    log_blue "=== 配置Telegram Bot ==="
    echo
    echo "请访问 https://t.me/BotFather 创建一个新的Bot"
    echo "Please visit https://t.me/BotFather to create a new Bot"
    echo
    echo "步骤:"
    echo "1. 发送 /newbot 给 @BotFather"
    echo "2. 设置Bot名称和用户名"
    echo "3. 复制获得的Token"
    echo
    
    while true; do
        read -p "请输入Bot Token: " bot_token
        if [[ $bot_token =~ ^[0-9]+:[a-zA-Z0-9_-]+$ ]]; then
            BOT_TOKEN=$bot_token
            break
        else
            log_error "Token格式不正确，请重新输入"
        fi
    done
    
    log_info "Bot Token配置完成"
}

# 配置管理员
setup_admin_users() {
    echo
    log_blue "=== 配置管理员用户 ==="
    echo
    echo "您需要获取Telegram用户ID作为管理员"
    echo "You need to get Telegram user ID as administrator"
    echo
    echo "获取用户ID的方法:"
    echo "1. 发送消息给 @userinfobot"
    echo "2. 或发送消息给 @getidsbot"
    echo "3. 复制返回的数字ID"
    echo
    
    admin_users=()
    
    while true; do
        read -p "请输入管理员用户ID (Enter admin user ID): " user_id
        if [[ $user_id =~ ^[0-9]+$ ]]; then
            admin_users+=($user_id)
            read -p "是否添加更多管理员? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                break
            fi
        else
            log_error "用户ID必须是数字"
        fi
    done
    
    # 用逗号连接数组元素
    ADMIN_USERS=$(IFS=,; echo "${admin_users[*]}")
    log_info "管理员配置完成: $ADMIN_USERS"
}

# 生成加密密钥
generate_encryption_key() {
    echo
    log_blue "=== 生成加密密钥 ==="
    echo
    
    ENCRYPTION_KEY=$(openssl rand -hex 16)
    log_info "加密密钥已生成: ${ENCRYPTION_KEY:0:8}..."
}

# 配置Web界面
setup_web_config() {
    echo
    log_blue "=== 配置Web管理界面 ==="
    echo
    
    # Web端口
    read -p "Web界面端口 (默认8080): " web_port
    WEB_PORT=${web_port:-8080}
    
    # Web密钥
    WEB_SECRET_KEY=$(openssl rand -hex 32)
    
    log_info "Web界面配置完成"
    log_info "访问地址: http://YOUR_SERVER_IP:$WEB_PORT"
}

# 创建配置文件
create_config_files() {
    echo
    log_blue "=== 创建配置文件 ==="
    echo
    
    # 创建.env文件
    cat > .env << EOF
# Telegram Bot配置
BOT_TOKEN=$BOT_TOKEN

# 管理员用户ID
ADMIN_USERS=$ADMIN_USERS

# 加密密钥
ENCRYPTION_KEY=$ENCRYPTION_KEY

# 数据库配置
DATABASE_URL=sqlite:///data/forwarder.db

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/forwarder.log

# Web界面配置
WEB_HOST=0.0.0.0
WEB_PORT=$WEB_PORT
WEB_DEBUG=False
WEB_SECRET_KEY=$WEB_SECRET_KEY

# 全局设置
MIN_INTERVAL=3
MAX_INTERVAL=30
HOURLY_LIMIT=50

# 备份设置
BACKUP_ENABLED=True
EOF
    
    # 设置权限
    chmod 600 .env
    
    log_info ".env 配置文件已创建"
    
    # 创建config.yaml文件
    if [[ ! -f "config.yaml" ]]; then
        cp examples/config.yaml.example config.yaml
        log_info "config.yaml 配置文件已创建"
    fi
}

# 测试配置
test_configuration() {
    echo
    log_blue "=== 测试配置 ==="
    echo
    
    log_info "正在测试Bot Token..."
    
    # 测试Bot Token
    response=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe")
    if echo "$response" | grep -q '"ok":true'; then
        bot_username=$(echo "$response" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        log_info "✅ Bot连接成功: @$bot_username"
    else
        log_error "❌ Bot Token测试失败"
        log_error "请检查Token是否正确"
        return 1
    fi
    
    log_info "✅ 配置测试通过"
}

# 显示完成信息
show_completion() {
    echo
    log_info "🎉 设置向导完成！"
    echo
    log_blue "下一步操作:"
    echo "1. 启动服务: ./scripts/service.sh start"
    echo "2. 查看状态: ./scripts/service.sh status"
    echo "3. 访问Web界面: http://YOUR_SERVER_IP:$WEB_PORT"
    echo "4. 在Bot中发送 /start 开始使用"
    echo
    log_blue "重要提醒:"
    echo "• 确保服务器防火墙已开放端口 $WEB_PORT"
    echo "• 建议定期备份数据库和配置文件"
    echo "• 如需修改配置，请编辑 .env 文件"
    echo
    log_warn "⚠️  请妥善保管 .env 文件，其中包含敏感信息！"
    echo
}

# 主函数
main() {
    show_welcome
    setup_bot_token
    setup_admin_users
    generate_encryption_key
    setup_web_config
    create_config_files
    
    if test_configuration; then
        show_completion
    else
        log_error "配置测试失败，请检查设置"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    for cmd in curl openssl; do
        if ! command -v $cmd &> /dev/null; then
            log_error "$cmd 未安装，请先安装必要的依赖"
            exit 1
        fi
    done
}

# 运行设置向导
check_dependencies
main "$@"