#!/bin/bash

# Telegram Forwarder 监控脚本

SERVICE_NAME="telegram-forwarder"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取当前时间
get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 检查服务状态
check_service_status() {
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo -e "${GREEN}✅ 服务状态: 运行中${NC}"
        return 0
    else
        echo -e "${RED}❌ 服务状态: 未运行${NC}"
        return 1
    fi
}

# 检查进程状态
check_process_status() {
    local pid=$(systemctl show "${SERVICE_NAME}" --property=MainPID --value 2>/dev/null)
    
    if [[ -n "$pid" && "$pid" != "0" ]]; then
        local cpu_usage=$(ps -p "$pid" -o %cpu --no-headers 2>/dev/null | tr -d ' ')
        local mem_usage=$(ps -p "$pid" -o %mem --no-headers 2>/dev/null | tr -d ' ')
        local elapsed=$(ps -p "$pid" -o etime --no-headers 2>/dev/null | tr -d ' ')
        
        echo -e "${GREEN}✅ 进程状态: 运行中 (PID: $pid)${NC}"
        echo -e "   CPU使用率: ${cpu_usage}%"
        echo -e "   内存使用率: ${mem_usage}%"
        echo -e "   运行时间: ${elapsed}"
        return 0
    else
        echo -e "${RED}❌ 进程状态: 未找到进程${NC}"
        return 1
    fi
}

# 检查系统资源
check_system_resources() {
    echo -e "${BLUE}📊 系统资源使用情况${NC}"
    
    # CPU使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    echo -e "   CPU使用率: ${cpu_usage}%"
    
    # 内存使用情况
    local mem_info=$(free -m | grep Mem)
    local total_mem=$(echo $mem_info | awk '{print $2}')
    local used_mem=$(echo $mem_info | awk '{print $3}')
    local mem_percent=$((used_mem * 100 / total_mem))
    echo -e "   内存使用: ${used_mem}MB/${total_mem}MB (${mem_percent}%)"
    
    # 磁盘使用情况
    local disk_usage=$(df -h "${PROJECT_DIR}" | tail -1 | awk '{print $5}' | sed 's/%//')
    echo -e "   磁盘使用率: ${disk_usage}%"
    
    # 负载平均值
    local load_avg=$(uptime | awk -F'load average:' '{print $2}')
    echo -e "   负载平均值:${load_avg}"
}

# 检查日志文件
check_log_files() {
    echo -e "${BLUE}📝 日志文件状态${NC}"
    
    local log_files=("${PROJECT_DIR}/logs/forwarder.log" "${PROJECT_DIR}/logs/service.log" "${PROJECT_DIR}/logs/service_error.log")
    
    for log_file in "${log_files[@]}"; do
        if [[ -f "$log_file" ]]; then
            local size=$(stat -c%s "$log_file" 2>/dev/null)
            local size_mb=$((size / 1024 / 1024))
            local last_modified=$(stat -c %y "$log_file" 2>/dev/null | cut -d'.' -f1)
            
            echo -e "   $(basename "$log_file"): ${size_mb}MB (${last_modified})"
            
            # 检查最近错误
            if [[ "$log_file" == *"error"* ]] && [[ -s "$log_file" ]]; then
                local error_count=$(tail -100 "$log_file" | grep -c "ERROR\|CRITICAL" 2>/dev/null || echo "0")
                if [[ $error_count -gt 0 ]]; then
                    echo -e "     ${YELLOW}⚠️ 最近100行中发现 ${error_count} 个错误${NC}"
                fi
            fi
        else
            echo -e "   $(basename "$log_file"): ${RED}不存在${NC}"
        fi
    done
}

# 检查配置文件
check_config_files() {
    echo -e "${BLUE}⚙️ 配置文件状态${NC}"
    
    local config_files=(".env" "config.yaml" "requirements.txt")
    
    for config_file in "${config_files[@]}"; do
        local file_path="${PROJECT_DIR}/${config_file}"
        if [[ -f "$file_path" ]]; then
            local last_modified=$(stat -c %y "$file_path" 2>/dev/null | cut -d'.' -f1)
            echo -e "   ${config_file}: ${GREEN}存在${NC} (${last_modified})"
        else
            echo -e "   ${config_file}: ${RED}不存在${NC}"
        fi
    done
}

# 检查网络连接
check_network() {
    echo -e "${BLUE}🌐 网络连接检查${NC}"
    
    # 检查Telegram API连接
    if timeout 5 curl -s https://api.telegram.org > /dev/null; then
        echo -e "   Telegram API: ${GREEN}连接正常${NC}"
    else
        echo -e "   Telegram API: ${RED}连接失败${NC}"
    fi
    
    # 检查DNS解析
    if timeout 3 nslookup google.com > /dev/null 2>&1; then
        echo -e "   DNS解析: ${GREEN}正常${NC}"
    else
        echo -e "   DNS解析: ${RED}异常${NC}"
    fi
}

# 检查数据库
check_database() {
    echo -e "${BLUE}🗄️ 数据库状态${NC}"
    
    local db_file="${PROJECT_DIR}/data/forwarder.db"
    
    if [[ -f "$db_file" ]]; then
        local size=$(stat -c%s "$db_file" 2>/dev/null)
        local size_mb=$((size / 1024 / 1024))
        echo -e "   数据库文件: ${GREEN}存在${NC} (${size_mb}MB)"
        
        # 检查数据库是否可访问
        if command -v sqlite3 &> /dev/null; then
            if sqlite3 "$db_file" "SELECT COUNT(*) FROM sqlite_master;" > /dev/null 2>&1; then
                echo -e "   数据库连接: ${GREEN}正常${NC}"
            else
                echo -e "   数据库连接: ${RED}异常${NC}"
            fi
        fi
    else
        echo -e "   数据库文件: ${RED}不存在${NC}"
    fi
}

# 性能统计
show_performance_stats() {
    echo -e "${BLUE}📈 性能统计${NC}"
    
    # 最近1小时的日志统计
    local log_file="${PROJECT_DIR}/logs/forwarder.log"
    if [[ -f "$log_file" ]]; then
        local one_hour_ago=$(date -d '1 hour ago' '+%Y-%m-%d %H:%M:%S')
        local recent_logs=$(awk -v start="$one_hour_ago" '$0 >= start' "$log_file" 2>/dev/null)
        
        if [[ -n "$recent_logs" ]]; then
            local info_count=$(echo "$recent_logs" | grep -c "INFO" || echo "0")
            local warn_count=$(echo "$recent_logs" | grep -c "WARNING" || echo "0")
            local error_count=$(echo "$recent_logs" | grep -c "ERROR" || echo "0")
            
            echo -e "   最近1小时日志:"
            echo -e "     INFO: ${info_count}"
            echo -e "     WARNING: ${warn_count}"
            echo -e "     ERROR: ${error_count}"
        fi
    fi
}

# 生成监控报告
generate_report() {
    local report_file="${PROJECT_DIR}/logs/monitor_$(date +%Y%m%d_%H%M%S).log"
    
    {
        echo "=== Telegram Forwarder 监控报告 ==="
        echo "生成时间: $(get_timestamp)"
        echo ""
        
        echo "=== 服务状态 ==="
        check_service_status
        check_process_status
        echo ""
        
        echo "=== 系统资源 ==="
        check_system_resources
        echo ""
        
        echo "=== 文件状态 ==="
        check_log_files
        check_config_files
        check_database
        echo ""
        
        echo "=== 网络状态 ==="
        check_network
        echo ""
        
        echo "=== 性能统计 ==="
        show_performance_stats
        echo ""
        
    } | tee "$report_file"
    
    echo -e "${GREEN}监控报告已保存到: $report_file${NC}"
}

# 实时监控
real_time_monitor() {
    echo -e "${BLUE}=== 实时监控模式 (Ctrl+C 退出) ===${NC}"
    
    while true; do
        clear
        echo -e "${BLUE}Telegram Forwarder 实时监控 - $(get_timestamp)${NC}"
        echo "========================================"
        
        check_service_status
        echo ""
        check_process_status
        echo ""
        check_system_resources
        echo ""
        
        # 显示最近的日志
        local log_file="${PROJECT_DIR}/logs/forwarder.log"
        if [[ -f "$log_file" ]]; then
            echo -e "${BLUE}📝 最近日志 (最后5行)${NC}"
            tail -5 "$log_file" 2>/dev/null | while read line; do
                echo "   $line"
            done
        fi
        
        echo ""
        echo "下次刷新: 30秒后 (Ctrl+C 退出)"
        sleep 30
    done
}

# 告警检查
check_alerts() {
    local alerts=()
    
    # 检查服务状态
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
        alerts+=("🔴 服务未运行")
    fi
    
    # 检查CPU使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}' | awk -F',' '{print $1}')
    if (( $(echo "$cpu_usage > 90" | bc -l) )); then
        alerts+=("⚠️ CPU使用率过高: ${cpu_usage}%")
    fi
    
    # 检查内存使用率
    local mem_percent=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$mem_percent > 90" | bc -l) )); then
        alerts+=("⚠️ 内存使用率过高: ${mem_percent}%")
    fi
    
    # 检查磁盘使用率
    local disk_usage=$(df -h "${PROJECT_DIR}" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        alerts+=("⚠️ 磁盘使用率过高: ${disk_usage}%")
    fi
    
    # 检查错误日志
    local error_log="${PROJECT_DIR}/logs/service_error.log"
    if [[ -f "$error_log" ]] && [[ -s "$error_log" ]]; then
        local recent_errors=$(tail -10 "$error_log" | grep -c "ERROR\|CRITICAL" 2>/dev/null || echo "0")
        if [[ $recent_errors -gt 5 ]]; then
            alerts+=("⚠️ 最近错误过多: ${recent_errors}个")
        fi
    fi
    
    # 输出告警
    if [[ ${#alerts[@]} -gt 0 ]]; then
        echo -e "${RED}🚨 发现 ${#alerts[@]} 个告警:${NC}"
        for alert in "${alerts[@]}"; do
            echo -e "   $alert"
        done
        return 1
    else
        echo -e "${GREEN}✅ 无告警，系统运行正常${NC}"
        return 0
    fi
}

# 快速检查
quick_check() {
    echo -e "${BLUE}=== 快速健康检查 ===${NC}"
    
    local checks_passed=0
    local total_checks=5
    
    # 服务状态
    if check_service_status > /dev/null 2>&1; then
        echo -e "✅ 服务状态检查通过"
        ((checks_passed++))
    else
        echo -e "❌ 服务状态检查失败"
    fi
    
    # 进程状态
    if check_process_status > /dev/null 2>&1; then
        echo -e "✅ 进程状态检查通过"
        ((checks_passed++))
    else
        echo -e "❌ 进程状态检查失败"
    fi
    
    # 配置文件
    if [[ -f "${PROJECT_DIR}/.env" ]]; then
        echo -e "✅ 配置文件检查通过"
        ((checks_passed++))
    else
        echo -e "❌ 配置文件检查失败"
    fi
    
    # 数据库
    if [[ -f "${PROJECT_DIR}/data/forwarder.db" ]]; then
        echo -e "✅ 数据库文件检查通过"
        ((checks_passed++))
    else
        echo -e "❌ 数据库文件检查失败"
    fi
    
    # 网络连接
    if timeout 5 curl -s https://api.telegram.org > /dev/null; then
        echo -e "✅ 网络连接检查通过"
        ((checks_passed++))
    else
        echo -e "❌ 网络连接检查失败"
    fi
    
    echo ""
    echo -e "检查结果: ${checks_passed}/${total_checks} 通过"
    
    if [[ $checks_passed -eq $total_checks ]]; then
        echo -e "${GREEN}🎉 所有检查通过，系统运行正常！${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ 部分检查失败，请检查系统状态${NC}"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "Telegram Forwarder 监控脚本"
    echo ""
    echo "用法: $0 {status|report|monitor|alerts|quick|help}"
    echo ""
    echo "命令说明:"
    echo "  status   - 显示详细状态信息"
    echo "  report   - 生成监控报告"
    echo "  monitor  - 实时监控模式"
    echo "  alerts   - 检查告警"
    echo "  quick    - 快速健康检查"
    echo "  help     - 显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 status   # 查看详细状态"
    echo "  $0 quick    # 快速检查"
    echo "  $0 monitor  # 实时监控"
}

# 主逻辑
case "${1:-status}" in
    status)
        echo -e "${BLUE}=== Telegram Forwarder 状态监控 ===${NC}"
        echo "监控时间: $(get_timestamp)"
        echo ""
        
        check_service_status
        echo ""
        check_process_status
        echo ""
        check_system_resources
        echo ""
        check_log_files
        echo ""
        check_config_files
        echo ""
        check_database
        echo ""
        check_network
        echo ""
        show_performance_stats
        echo ""
        check_alerts
        ;;
    report)
        generate_report
        ;;
    monitor)
        real_time_monitor
        ;;
    alerts)
        check_alerts
        ;;
    quick)
        quick_check
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac