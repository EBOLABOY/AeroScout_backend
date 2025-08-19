#!/bin/bash

# TicketRadar 管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 显示帮助信息
show_help() {
    echo "TicketRadar 管理脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start       启动所有服务"
    echo "  stop        停止所有服务"
    echo "  restart     重启所有服务"
    echo "  status      查看服务状态"
    echo "  logs        查看所有日志"
    echo "  logs-app    查看应用日志"
    echo "  logs-nginx  查看 Nginx 日志"
    echo "  logs-redis  查看 Redis 日志"
    echo "  update      更新并重新部署"
    echo "  backup      备份数据"
    echo "  health      健康检查"
    echo "  ssl-renew   续期 SSL 证书"
    echo "  cleanup     清理未使用的 Docker 资源"
    echo "  shell-app   进入应用容器"
    echo "  shell-redis 进入 Redis 容器"
    echo "  help        显示此帮助信息"
}

# 检查 Docker 和 Docker Compose
check_requirements() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose 未安装"
        exit 1
    fi
}

# 启动服务
start_services() {
    print_info "启动 TicketRadar 服务..."
    docker compose up -d
    print_success "服务启动完成"
}

# 停止服务
stop_services() {
    print_info "停止 TicketRadar 服务..."
    docker compose stop
    print_success "服务停止完成"
}

# 重启服务
restart_services() {
    print_info "重启 TicketRadar 服务..."
    docker compose restart
    print_success "服务重启完成"
}

# 查看服务状态
show_status() {
    print_info "TicketRadar 服务状态:"
    docker compose ps
}

# 查看日志
show_logs() {
    case $1 in
        "app")
            print_info "查看应用日志 (Ctrl+C 退出):"
            docker compose logs -f app
            ;;
        "nginx")
            print_info "查看 Nginx 日志 (Ctrl+C 退出):"
            docker compose logs -f nginx
            ;;
        "redis")
            print_info "查看 Redis 日志 (Ctrl+C 退出):"
            docker compose logs -f redis
            ;;
        *)
            print_info "查看所有日志 (Ctrl+C 退出):"
            docker compose logs -f
            ;;
    esac
}

# 更新部署
update_deployment() {
    print_info "更新 TicketRadar 部署..."
    
    # 拉取最新代码
    if [ -d ".git" ]; then
        print_info "拉取最新代码..."
        git pull
    fi
    
    # 重新构建并部署
    print_info "重新构建并部署..."
    docker compose up -d --build
    
    print_success "更新部署完成"
}

# 备份数据
backup_data() {
    print_info "备份 TicketRadar 数据..."
    
    BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份 Redis 数据
    print_info "备份 Redis 数据..."
    docker compose exec -T redis redis-cli BGSAVE
    sleep 2
    docker cp ticketradar-redis:/data/dump.rdb "$BACKUP_DIR/"
    
    # 备份配置文件
    print_info "备份配置文件..."
    cp .env "$BACKUP_DIR/"
    cp docker-compose.yml "$BACKUP_DIR/"
    cp nginx.conf "$BACKUP_DIR/"
    
    # 备份 SSL 证书
    if [ -d "ssl" ]; then
        print_info "备份 SSL 证书..."
        cp -r ssl "$BACKUP_DIR/"
    fi
    
    print_success "数据备份完成: $BACKUP_DIR"
}

# 健康检查
health_check() {
    print_info "执行健康检查..."
    
    # 检查容器状态
    print_info "检查容器状态..."
    docker compose ps
    
    # 检查应用健康端点
    print_info "检查应用健康端点..."
    if curl -f -s http://localhost/health > /dev/null; then
        print_success "应用健康检查通过"
    else
        print_error "应用健康检查失败"
    fi
    
    # 检查 Redis 连接
    print_info "检查 Redis 连接..."
    if docker compose exec -T redis redis-cli ping | grep -q PONG; then
        print_success "Redis 连接正常"
    else
        print_error "Redis 连接失败"
    fi
    
    # 显示资源使用情况
    print_info "资源使用情况:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

# SSL 证书续期
renew_ssl() {
    print_info "续期 SSL 证书..."
    if [ -f "renew-ssl.sh" ]; then
        ./renew-ssl.sh
    else
        print_error "renew-ssl.sh 脚本不存在"
        exit 1
    fi
}

# 清理 Docker 资源
cleanup_docker() {
    print_info "清理未使用的 Docker 资源..."
    docker system prune -f
    docker volume prune -f
    print_success "Docker 资源清理完成"
}

# 进入容器 shell
enter_shell() {
    case $1 in
        "app")
            print_info "进入应用容器..."
            docker compose exec app bash
            ;;
        "redis")
            print_info "进入 Redis 容器..."
            docker compose exec redis redis-cli
            ;;
        *)
            print_error "未知的容器类型: $1"
            exit 1
            ;;
    esac
}

# 主逻辑
main() {
    check_requirements
    
    case $1 in
        "start")
            start_services
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "logs-app")
            show_logs "app"
            ;;
        "logs-nginx")
            show_logs "nginx"
            ;;
        "logs-redis")
            show_logs "redis"
            ;;
        "update")
            update_deployment
            ;;
        "backup")
            backup_data
            ;;
        "health")
            health_check
            ;;
        "ssl-renew")
            renew_ssl
            ;;
        "cleanup")
            cleanup_docker
            ;;
        "shell-app")
            enter_shell "app"
            ;;
        "shell-redis")
            enter_shell "redis"
            ;;
        "help"|"")
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
