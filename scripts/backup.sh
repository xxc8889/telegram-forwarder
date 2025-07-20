#!/bin/bash

# Telegram Forwarder 备份脚本

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# 创建备份目录
create_backup_dir() {
    mkdir -p "${BACKUP_DIR}"
    if [[ ! -d "${BACKUP_DIR}" ]]; then
        log_error "无法创建备份目录: ${BACKUP_DIR}"
        exit 1
    fi
}

# 备份数据库
backup_database() {
    local db_file="${PROJECT_DIR}/data/forwarder.db"
    local backup_file="${BACKUP_DIR}/database_${TIMESTAMP}.db"
    
    if [[ -f "$db_file" ]]; then
        log_info "备份数据库..."
        cp "$db_file" "$backup_file"
        
        # 验证备份
        if [[ -f "$backup_file" ]]; then
            local original_size=$(stat -c%s "$db_file")
            local backup_size=$(stat -c%s "$backup_file")
            
            if [[ $original_size -eq $backup_size ]]; then
                log_info "数据库备份成功: $(basename "$backup_file")"
                echo "$backup_file"
            else
                log_error "数据库备份验证失败"
                rm -f "$backup_file"
                return 1
            fi
        else
            log_error "数据库备份失败"
            return 1
        fi
    else
        log_warn "数据库文件不存在: $db_file"
        return 1
    fi
}

# 备份配置文件
backup_configs() {
    local config_backup_dir="${BACKUP_DIR}/config_${TIMESTAMP}"
    mkdir -p "$config_backup_dir"
    
    log_info "备份配置文件..."
    
    local config_files=(".env" "config.yaml" "requirements.txt")
    local backed_up_files=()
    
    for config_file in "${config_files[@]}"; do
        local file_path="${PROJECT_DIR}/${config_file}"
        if [[ -f "$file_path" ]]; then
            cp "$file_path" "$config_backup_dir/"
            backed_up_files+=("$config_file")
        fi
    done
    
    if [[ ${#backed_up_files[@]} -gt 0 ]]; then
        log_info "配置文件备份成功: ${backed_up_files[*]}"
        echo "$config_backup_dir"
    else
        log_warn "没有找到配置文件"
        rmdir "$config_backup_dir" 2>/dev/null
        return 1
    fi
}

# 备份会话文件
backup_sessions() {
    local sessions_dir="${PROJECT_DIR}/sessions"
    local sessions_backup_dir="${BACKUP_DIR}/sessions_${TIMESTAMP}"
    
    if [[ -d "$sessions_dir" ]] && [[ "$(ls -A "$sessions_dir" 2>/dev/null)" ]]; then
        log_info "备份会话文件..."
        
        mkdir -p "$sessions_backup_dir"
        cp -r "$sessions_dir"/* "$sessions_backup_dir/" 2>/dev/null
        
        local session_count=$(find "$sessions_backup_dir" -name "*.session" | wc -l)
        if [[ $session_count -gt 0 ]]; then
            log_info "会话文件备份成功: ${session_count}个文件"
            echo "$sessions_backup_dir"
        else
            log_warn "没有找到会话文件"
            rmdir "$sessions_backup_dir" 2>/dev/null
            return 1
        fi
    else
        log_warn "会话目录不存在或为空"
        return 1
    fi
}

# 备份日志文件
backup_logs() {
    local logs_dir="${PROJECT_DIR}/logs"
    local logs_backup_dir="${BACKUP_DIR}/logs_${TIMESTAMP}"
    
    if [[ -d "$logs_dir" ]] && [[ "$(ls -A "$logs_dir" 2>/dev/null)" ]]; then
        log_info "备份日志文件..."
        
        mkdir -p "$logs_backup_dir"
        
        # 只备份最近7天的日志
        find "$logs_dir" -name "*.log" -mtime -7 -exec cp {} "$logs_backup_dir/" \;
        
        local log_count=$(find "$logs_backup_dir" -name "*.log" | wc -l)
        if [[ $log_count -gt 0 ]]; then
            log_info "日志文件备份成功: ${log_count}个文件"
            echo "$logs_backup_dir"
        else
            log_warn "没有找到最近的日志文件"
            rmdir "$logs_backup_dir" 2>/dev/null
            return 1
        fi
    else
        log_warn "日志目录不存在或为空"
        return 1
    fi
}

# 创建完整备份包
create_backup_archive() {
    local archive_name="telegram_forwarder_backup_${TIMESTAMP}.tar.gz"
    local archive_path="${BACKUP_DIR}/${archive_name}"
    
    log_info "创建备份压缩包..."
    
    # 进入备份目录
    cd "${BACKUP_DIR}" || exit 1
    
    # 创建压缩包
    local backup_items=()
    
    # 查找本次备份的文件
    for item in database_${TIMESTAMP}.db config_${TIMESTAMP} sessions_${TIMESTAMP} logs_${TIMESTAMP}; do
        if [[ -e "$item" ]]; then
            backup_items+=("$item")
        fi
    done
    
    if [[ ${#backup_items[@]} -gt 0 ]]; then
        tar -czf "$archive_name" "${backup_items[@]}" 2>/dev/null
        
        if [[ -f "$archive_path" ]]; then
            local archive_size=$(stat -c%s "$archive_path" | numfmt --to=iec)
            log_info "备份压缩包创建成功: ${archive_name} (${archive_size})"
            
            # 清理临时文件
            for item in "${backup_items[@]}"; do
                rm -rf "$item"
            done
            
            echo "$archive_path"
        else
            log_error "创建备份压缩包失败"
            return 1
        fi
    else
        log_error "没有可备份的内容"
        return 1
    fi
}

# 清理旧备份
cleanup_old_backups() {
    local keep_days=${1:-7}
    
    log_info "清理 ${keep_days} 天前的备份..."
    
    local deleted_count=0
    
    # 删除旧的压缩包
    find "${BACKUP_DIR}" -name "telegram_forwarder_backup_*.tar.gz" -mtime +${keep_days} -type f | while read -r old_backup; do
        rm -f "$old_backup"
        log_info "删除旧备份: $(basename "$old_backup")"
        ((deleted_count++))
    done
    
    # 删除旧的单独备份文件
    find "${BACKUP_DIR}" -name "database_*.db" -mtime +${keep_days} -type f -delete
    find "${BACKUP_DIR}" -name "config_*" -mtime +${keep_days} -type d -exec rm -rf {} \; 2>/dev/null
    find "${BACKUP_DIR}" -name "sessions_*" -mtime +${keep_days} -type d -exec rm -rf {} \; 2>/dev/null
    find "${BACKUP_DIR}" -name "logs_*" -mtime +${keep_days} -type d -exec rm -rf {} \; 2>/dev/null
    
    if [[ $deleted_count -gt 0 ]]; then
        log_info "清理完成，删除了 ${deleted_count} 个旧备份"
    else
        log_info "没有需要清理的旧备份"
    fi
}

# 验证备份
verify_backup() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi
    
    log_info "验证备份文件..."
    
    # 测试压缩包完整性
    if tar -tzf "$backup_file" > /dev/null 2>&1; then
        log_info "备份文件验证成功"
        
        # 显示备份内容
        log_info "备份内容:"
        tar -tzf "$backup_file" | while read -r file; do
            echo "  - $file"
        done
        
        return 0
    else
        log_error "备份文件验证失败"
        return 1
    fi
}

# 恢复备份
restore_backup() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        return 1
    fi
    
    log_warn "⚠️ 恢复备份将覆盖现有数据!"
    read -p "确认恢复? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "取消恢复操作"
        return 0
    fi
    
    log_info "开始恢复备份..."
    
    # 停止服务
    if systemctl is-active --quiet telegram-forwarder; then
        log_info "停止服务..."
        sudo systemctl stop telegram-forwarder
    fi
    
    # 创建临时目录
    local temp_dir=$(mktemp -d)
    cd "$temp_dir" || exit 1
    
    # 解压备份
    if tar -xzf "$backup_file"; then
        log_info "备份解压成功"
        
        # 恢复数据库
        local db_backup=$(find . -name "database_*.db" | head -1)
        if [[ -n "$db_backup" ]]; then
            cp "$db_backup" "${PROJECT_DIR}/data/forwarder.db"
            log_info "数据库已恢复"
        fi
        
        # 恢复配置文件
        local config_dir=$(find . -name "config_*" -type d | head -1)
        if [[ -n "$config_dir" ]]; then
            cp "$config_dir"/* "${PROJECT_DIR}/" 2>/dev/null
            log_info "配置文件已恢复"
        fi
        
        # 恢复会话文件
        local sessions_dir=$(find . -name "sessions_*" -type d | head -1)
        if [[ -n "$sessions_dir" ]]; then
            rm -rf "${PROJECT_DIR}/sessions"
            mkdir -p "${PROJECT_DIR}/sessions"
            cp "$sessions_dir"/* "${PROJECT_DIR}/sessions/" 2>/dev/null
            log_info "会话文件已恢复"
        fi
        
        log_info "备份恢复完成"
        
        # 重启服务
        if systemctl is-enabled --quiet telegram-forwarder; then
            log_info "重启服务..."
            sudo systemctl start telegram-forwarder
        fi
        
    else
        log_error "备份解压失败"
        return 1
    fi
    
    # 清理临时目录
    rm -rf "$temp_dir"
}

# 列出备份
list_backups() {
    log_info "可用备份列表:"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_warn "备份目录不存在"
        return 1
    fi
    
    local backups=($(find "$BACKUP_DIR" -name "telegram_forwarder_backup_*.tar.gz" | sort -r))
    
    if [[ ${#backups[@]} -eq 0 ]]; then
        log_warn "没有找到备份文件"
        return 1
    fi
    
    echo ""
    for i in "${!backups[@]}"; do
        local backup="${backups[$i]}"
        local filename=$(basename "$backup")
        local size=$(stat -c%s "$backup" | numfmt --to=iec)
        local date=$(stat -c %y "$backup" | cut -d'.' -f1)
        
        echo "  $((i+1)). $filename ($size) - $date"
    done
    echo ""
}

# 显示帮助信息
show_help() {
    echo "Telegram Forwarder 备份脚本"
    echo ""
    echo "用法: $0 {backup|restore|list|cleanup|verify|help} [选项]"
    echo ""
    echo "命令说明:"
    echo "  backup           - 创建完整备份"
    echo "  restore <文件>   - 恢复指定备份"
    echo "  list             - 列出所有备份"
    echo "  cleanup [天数]   - 清理旧备份 (默认7天)"
    echo "  verify <文件>    - 验证备份文件"
    echo "  help             - 显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 backup                    # 创建备份"
    echo "  $0 list                      # 列出备份"
    echo "  $0 restore backup.tar.gz     # 恢复备份"
    echo "  $0 cleanup 30                # 清理30天前的备份"
}

# 主逻辑
case "${1:-backup}" in
    backup)
        log_info "开始创建备份..."
        create_backup_dir
        
        backup_success=0
        
        # 执行各项备份
        if backup_database; then ((backup_success++)); fi
        if backup_configs; then ((backup_success++)); fi
        if backup_sessions; then ((backup_success++)); fi
        if backup_logs; then ((backup_success++)); fi
        
        if [[ $backup_success -gt 0 ]]; then
            # 创建压缩包
            if archive_path=$(create_backup_archive); then
                verify_backup "$archive_path"
                log_info "🎉 备份创建完成: $(basename "$archive_path")"
            else
                log_error "创建备份压缩包失败"
                exit 1
            fi
        else
            log_error "没有成功备份任何内容"
            exit 1
        fi
        ;;
    restore)
        if [[ -z "$2" ]]; then
            log_error "请指定要恢复的备份文件"
            list_backups
            exit 1
        fi
        restore_backup "$2"
        ;;
    list)
        list_backups
        ;;
    cleanup)
        cleanup_old_backups "${2:-7}"
        ;;
    verify)
        if [[ -z "$2" ]]; then
            log_error "请指定要验证的备份文件"
            exit 1
        fi
        verify_backup "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        echo ""
        show_help
        exit 1
        ;;
esac