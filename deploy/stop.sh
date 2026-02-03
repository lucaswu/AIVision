#!/bin/bash

# AI Vision Detection System - 停止脚本
# =====================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "AI Vision Detection System - 停止脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --force       强制停止并删除容器"
    echo "  --clean       停止服务并清理数据卷 (⚠️ 会删除数据库和文件数据)"
    echo "  --network     同时删除Docker网络"
    echo "  --help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 正常停止服务"
    echo "  $0 --force          # 强制停止并删除容器"
    echo "  $0 --clean          # 完全清理（包括数据）"
    echo ""
}

# 停止服务
stop_services() {
    local force=$1
    local clean=$2
    
    if [ ! -f "docker-compose.yml" ]; then
        log_error "请在deploy目录下运行此脚本"
        exit 1
    fi
    
    log_info "检查运行中的服务..."
    docker compose ps
    
    if [ "$clean" = true ]; then
        log_warning "⚠️  即将删除所有数据，包括PostgreSQL数据库、文件存储和推理结果！"
        echo -n "确认继续？(输入 'yes' 确认): "
        read confirmation
        if [ "$confirmation" != "yes" ]; then
            log_info "操作已取消"
            exit 0
        fi
        
        log_info "停止并删除所有容器和数据卷..."
        docker compose down -v --remove-orphans
        log_success "所有服务和数据已清理"
        
    elif [ "$force" = true ]; then
        log_info "强制停止并删除所有容器..."
        docker compose down --remove-orphans
        log_success "所有容器已删除"
        
    else
        log_info "正常停止所有服务..."
        docker compose stop
        log_success "所有服务已停止"
    fi
}

# 清理网络
clean_network() {
    log_info "检查Docker网络..."
    if docker network ls | grep -q "ai-services"; then
        log_info "删除Docker网络: ai-services"
        docker network rm ai-services || log_warning "网络删除失败，可能仍有容器在使用"
        log_success "网络已删除"
    else
        log_info "网络 ai-services 不存在"
    fi
}

# 显示清理后状态
show_status() {
    log_info "当前状态："
    echo ""
    echo "📊 容器状态："
    docker compose ps 2>/dev/null || echo "  无运行中的服务"
    echo ""
    echo "💾 数据卷："
    docker volume ls | grep ai-detection || echo "  无AI Vision相关数据卷"
    echo ""
    echo "🌐 网络："
    docker network ls | grep ai-services || echo "  ai-services网络已删除"
    echo ""
}

# 主函数
main() {
    local force=false
    local clean=false
    local remove_network=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                force=true
                shift
                ;;
            --clean)
                clean=true
                force=true  # clean 包含 force
                shift
                ;;
            --network)
                remove_network=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "🛑 AI Vision Detection System 停止脚本"
    echo "========================================="
    
    # 停止服务
    stop_services "$force" "$clean"
    
    # 清理网络
    if [ "$remove_network" = true ] || [ "$clean" = true ]; then
        clean_network
    fi
    
    # 显示状态
    show_status
    
    if [ "$clean" = true ]; then
        log_success "系统已完全清理！"
        echo ""
        echo "📝 重新启动命令："
        echo "  ./start.sh step"
    else
        log_success "系统已停止！"
        echo ""
        echo "📝 重新启动命令："
        echo "  docker compose up -d"
        echo "  ./start.sh"
    fi
}

# 错误处理
trap 'log_error "脚本执行失败！"; exit 1' ERR

# 运行主函数
main "$@" 