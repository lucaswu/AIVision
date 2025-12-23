#!/bin/bash

# AI Vision Detection System - 快速启动脚本
# ==========================================

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

# 检查Docker环境
check_docker() {
    log_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行，请先启动Docker"
        exit 1
    fi
    
    log_success "Docker环境检查通过"
}

# 检查端口占用
check_ports() {
    log_info "检查端口占用情况..."
    
    ports=(5432 8080 8001 9000 9001 11434)
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_warning "端口 $port 已被占用"
        fi
    done
}

# 创建必要的目录和文件
setup_environment() {
    log_info "设置环境..."
    
    # 确保在正确的目录
    if [ ! -f "docker-compose.yml" ]; then
        log_error "请在deploy目录下运行此脚本"
        exit 1
    fi
    
    # 创建网络（如果不存在）
    if ! docker network ls | grep -q "ai-services"; then
        log_info "创建Docker网络: ai-services"
        docker network create ai-services
    fi
}

# 启动服务
start_services() {
    local mode=$1
    
    case $mode in
        "full")
            log_info "启动完整系统..."
            docker-compose up -d
            ;;
        "step")
            log_info "分步启动系统..."
            
            log_info "1. 启动基础存储服务..."
            docker-compose up -d postgres minio minio-init
            
            log_info "等待基础服务就绪..."
            sleep 30
            
            log_info "2. 启动AI服务..."
            docker-compose up -d vision-ai deepseek-llm
            
            log_info "等待AI服务就绪..."
            sleep 60
            
            log_info "3. 启动API Gateway..."
            docker-compose up -d api-gateway
            ;;
        "basic")
            log_info "仅启动基础服务..."
            docker-compose up -d postgres minio minio-init
            ;;
        *)
            log_error "未知的启动模式: $mode"
            exit 1
            ;;
    esac
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    sleep 10
    docker-compose ps
    
    log_info "等待服务完全启动..."
    sleep 30
    
    # 检查健康状态
    log_info "检查服务健康状态..."
    
    services=(
        "http://localhost:9541/actuator/health|API Gateway"
        "http://localhost:8001/health|Vision AI"
        "http://localhost:11434/api/tags|LLM AI"
        "http://localhost:9000/minio/health/live|MinIO"
    )
    
    for service in "${services[@]}"; do
        IFS='|' read -r url name <<< "$service"
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$name 健康检查通过"
        else
            log_warning "$name 健康检查失败 ($url)"
        fi
    done
}

# 显示访问信息
show_access_info() {
    log_success "系统启动完成！"
    echo ""
    echo "🌐 访问地址："
    echo "  📊 API Gateway:     http://localhost:9541"
    echo "  📚 Swagger UI:      http://localhost:9541/swagger-ui.html"
    echo "  💾 MinIO Console:   http://localhost:9001"
    echo ""
    echo "🔑 默认凭据："
    echo "  MinIO: minioadmin / minioadmin123"
    echo "  PostgreSQL: aiuser / aipass123"
    echo ""
    echo "📝 管理命令："
    echo "  查看日志: docker-compose logs -f"
    echo "  查看状态: docker-compose ps"
    echo "  停止服务: docker-compose stop"
    echo ""
}

# 显示帮助信息
show_help() {
    echo "AI Vision Detection System - 启动脚本"
    echo ""
    echo "用法: $0 [模式] [选项]"
    echo ""
    echo "启动模式:"
    echo "  full     完整启动所有服务 (默认)"
    echo "  step     分步启动 (推荐)"
    echo "  basic    仅启动基础服务"
    echo ""
    echo "选项:"
    echo "  --with-n8n    同时启动N8N工作流引擎"
    echo "  --no-check    跳过健康检查"
    echo "  --help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整启动"
    echo "  $0 step               # 分步启动"
    echo "  $0 basic              # 仅启动基础服务"
    echo "  $0 full --with-n8n    # 启动所有服务包括N8N"
    echo ""
}

# 主函数
main() {
    local mode="full"
    local with_n8n=false
    local skip_check=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            full|step|basic)
                mode=$1
                shift
                ;;
            --with-n8n)
                with_n8n=true
                shift
                ;;
            --no-check)
                skip_check=true
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
    
    echo "🚀 AI Vision Detection System 启动脚本"
    echo "=========================================="
    
    # 执行检查
    check_docker
    check_ports
    setup_environment
    
    # 启动服务
    start_services "$mode"
    
    # 启动N8N (如果需要)
    if [ "$with_n8n" = true ]; then
        log_info "启动N8N工作流引擎..."
        docker-compose --profile n8n up -d n8n
    fi
    
    # 检查服务状态
    if [ "$skip_check" = false ]; then
        check_services
    fi
    
    # 显示访问信息
    show_access_info
}

# 错误处理
trap 'log_error "脚本执行失败！"; exit 1' ERR

# 运行主函数
main "$@" 