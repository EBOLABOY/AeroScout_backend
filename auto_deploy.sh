#!/bin/bash

# 机票监控系统 - 一键自动化部署脚本
# 功能：自动拉取GitHub最新代码、清理Docker缓存、重新构建部署
# 使用方法：在Ubuntu服务器上运行 ./auto_deploy.sh

set -e  # 遇到错误立即退出

# 项目配置
PROJECT_NAME="机票监控系统"
GITHUB_REPO="https://github.com/EBOLABOY/AeroScout_backend.git"
DOMAIN="apiticketradar.izlx.de"
PROJECT_DIR="/opt/aeroscout"  # 默认项目目录

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查并创建项目目录
setup_project_directory() {
    log_info "设置项目目录..."

    # 如果当前不在项目目录中，则切换到项目目录
    if [ ! -f "docker-compose.yml" ] && [ ! -f "main_fastapi.py" ]; then
        log_info "当前目录不是项目目录，检查 $PROJECT_DIR"

        if [ ! -d "$PROJECT_DIR" ]; then
            log_info "项目目录不存在，创建并克隆仓库..."
            sudo mkdir -p "$PROJECT_DIR"
            sudo chown $USER:$USER "$PROJECT_DIR"
            git clone "$GITHUB_REPO" "$PROJECT_DIR"
            log_success "项目克隆完成"
        fi

        cd "$PROJECT_DIR"
        log_success "切换到项目目录: $PROJECT_DIR"
    else
        log_success "当前目录是项目目录"
    fi
}

# 检查是否为root用户或有sudo权限
check_permissions() {
    log_info "检查用户权限..."
    if [[ $EUID -eq 0 ]]; then
        log_success "以root用户运行"
        SUDO=""
    elif sudo -n true 2>/dev/null; then
        log_success "检测到sudo权限"
        SUDO="sudo"
    else
        log_error "需要root权限或sudo权限来运行此脚本"
        exit 1
    fi
}

# 检查Docker是否安装
check_docker() {
    log_info "检查Docker环境..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    log_success "Docker环境检查通过"
}

# 备份当前配置
backup_config() {
    log_info "备份当前配置..."
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份重要配置文件
    if [ -f ".env" ]; then
        cp .env "$BACKUP_DIR/"
        log_success "已备份 .env 文件"
    fi
    
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "$BACKUP_DIR/"
        log_success "已备份 docker-compose.yml 文件"
    fi
    
    log_success "配置备份完成: $BACKUP_DIR"
}

# 停止现有服务
stop_services() {
    log_info "停止现有服务..."
    
    # 尝试使用新版docker compose命令
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    if [ -f "docker-compose.yml" ]; then
        $COMPOSE_CMD down --remove-orphans || log_warning "停止服务时出现警告"
        log_success "服务已停止"
    else
        log_warning "未找到docker-compose.yml文件"
    fi
}

# 拉取最新代码
pull_latest_code() {
    log_info "从GitHub拉取最新代码..."

    # 检查是否为git仓库
    if [ ! -d ".git" ]; then
        log_error "当前目录不是git仓库"
        exit 1
    fi

    # 显示当前分支和提交
    log_info "当前分支: $(git branch --show-current)"
    log_info "当前提交: $(git rev-parse --short HEAD)"

    # 保存本地修改
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_warning "检测到本地修改，正在保存..."
        git stash push -m "Auto-deploy backup $(date '+%Y-%m-%d %H:%M:%S')"
        log_success "本地修改已保存到stash"
    fi

    # 拉取最新代码
    log_info "正在拉取远程更新..."
    git fetch origin

    # 检查是否有更新
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/master)

    if [ "$LOCAL" = "$REMOTE" ]; then
        log_info "代码已是最新版本，无需更新"
        return 0
    fi

    log_info "发现新版本，正在更新..."
    git pull origin master

    log_success "代码更新完成"
    log_info "新版本提交: $(git rev-parse --short HEAD)"
}

# 清理Docker缓存
clean_docker_cache() {
    log_info "清理Docker缓存..."
    
    # 停止所有容器
    if [ "$(docker ps -q)" ]; then
        log_info "停止运行中的容器..."
        docker stop $(docker ps -q) || log_warning "停止容器时出现警告"
    fi
    
    # 清理未使用的镜像
    log_info "清理未使用的镜像..."
    docker image prune -a -f || log_warning "清理镜像时出现警告"
    
    # 清理未使用的容器
    log_info "清理未使用的容器..."
    docker container prune -f || log_warning "清理容器时出现警告"
    
    # 清理未使用的网络
    log_info "清理未使用的网络..."
    docker network prune -f || log_warning "清理网络时出现警告"
    
    # 清理未使用的卷（谨慎操作）
    read -p "是否清理未使用的Docker卷？这可能会删除数据库数据 (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_warning "清理Docker卷..."
        docker volume prune -f || log_warning "清理卷时出现警告"
    else
        log_info "跳过卷清理"
    fi
    
    # 显示清理后的空间
    log_info "Docker空间使用情况:"
    docker system df
    
    log_success "Docker缓存清理完成"
}

# 构建和部署
deploy_application() {
    log_info "开始构建和部署应用..."

    # 确定docker compose命令
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # 确保部署脚本有执行权限
    if [ -f "deploy.sh" ]; then
        chmod +x deploy.sh
        log_info "使用项目部署脚本..."
        ./deploy.sh
    else
        log_info "使用docker-compose直接部署..."

        # 构建镜像（无缓存）
        log_info "构建Docker镜像..."
        $COMPOSE_CMD build --no-cache

        # 启动服务
        log_info "启动服务..."
        $COMPOSE_CMD up -d

        # 如果有SSL设置脚本，执行它
        if [ -f "setup-ssl.sh" ]; then
            chmod +x setup-ssl.sh
            log_info "设置SSL证书..."
            ./setup-ssl.sh || log_warning "SSL设置失败，请手动检查"
        fi
    fi

    log_success "应用部署完成"
}

# 验证部署
verify_deployment() {
    log_info "验证部署状态..."

    # 确定docker compose命令
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # 等待服务启动
    log_info "等待服务启动（60秒）..."
    sleep 60

    # 检查容器状态
    log_info "检查容器状态:"
    $COMPOSE_CMD ps

    # 检查应用容器是否运行
    if $COMPOSE_CMD ps | grep -q "Up"; then
        log_success "容器运行正常"
    else
        log_error "容器未正常运行"
        log_info "容器日志:"
        $COMPOSE_CMD logs --tail=50
        return 1
    fi

    # 检查健康状态
    log_info "检查应用健康状态..."

    # 多次尝试健康检查
    for i in {1..5}; do
        log_info "健康检查尝试 $i/5..."

        if command -v curl &> /dev/null; then
            if curl -f -s -k "https://$DOMAIN/health" > /dev/null 2>&1; then
                log_success "✅ 应用健康检查通过"
                break
            elif curl -f -s "http://localhost:8000/health" > /dev/null 2>&1; then
                log_success "✅ 应用健康检查通过（HTTP）"
                break
            else
                log_warning "健康检查失败，等待10秒后重试..."
                sleep 10
            fi
        else
            log_warning "curl未安装，跳过健康检查"
            break
        fi

        if [ $i -eq 5 ]; then
            log_warning "健康检查失败，请手动检查应用状态"
        fi
    done

    # 测试AI搜索功能
    log_info "测试AI搜索功能..."
    if command -v curl &> /dev/null; then
        TEST_URL="https://$DOMAIN/api/flights/search/ai-enhanced/async?departure_code=PEK&destination_code=SZX&depart_date=2025-11-20&user_preferences=测试"
        if curl -f -s -k -X POST "$TEST_URL" > /dev/null 2>&1; then
            log_success "✅ AI搜索功能测试通过"
        else
            log_warning "AI搜索功能测试失败"
        fi
    fi

    # 显示最近日志
    log_info "最近的应用日志:"
    $COMPOSE_CMD logs --tail=30 app 2>/dev/null || log_warning "无法获取应用日志"

    # 显示部署信息
    echo ""
    log_success "🎉 部署验证完成！"
    log_info "📱 应用地址: https://$DOMAIN"
    log_info "🔍 健康检查: https://$DOMAIN/health"
    log_info "📚 API文档: https://$DOMAIN/docs"
    log_info "📊 查看日志: docker compose logs -f app"
    log_info "🔄 重启应用: docker compose restart app"
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理旧备份..."
    
    # 保留最近5个备份
    BACKUP_COUNT=$(ls -d backup_* 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 5 ]; then
        log_info "发现 $BACKUP_COUNT 个备份，清理旧备份..."
        ls -dt backup_* | tail -n +6 | xargs rm -rf
        log_success "旧备份清理完成"
    else
        log_info "备份数量合理，无需清理"
    fi
}

# 显示使用说明
show_usage() {
    echo "机票监控系统 - 一键自动化部署脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -f, --force    强制重新部署（清理所有缓存）"
    echo "  -q, --quick    快速部署（跳过缓存清理）"
    echo "  --no-backup    跳过配置备份"
    echo ""
    echo "示例:"
    echo "  $0              # 标准部署"
    echo "  $0 --force      # 强制重新部署"
    echo "  $0 --quick      # 快速部署"
    echo ""
}

# 主函数
main() {
    # 解析命令行参数
    FORCE_DEPLOY=false
    QUICK_DEPLOY=false
    SKIP_BACKUP=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -f|--force)
                FORCE_DEPLOY=true
                shift
                ;;
            -q|--quick)
                QUICK_DEPLOY=true
                shift
                ;;
            --no-backup)
                SKIP_BACKUP=true
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # 显示部署信息
    echo "🚀 $PROJECT_NAME - 自动化部署脚本"
    echo "📅 部署时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "🌐 目标域名: $DOMAIN"
    echo "📁 项目目录: $PROJECT_DIR"
    echo "⚙️  部署模式: $([ "$FORCE_DEPLOY" = true ] && echo "强制部署" || ([ "$QUICK_DEPLOY" = true ] && echo "快速部署" || echo "标准部署"))"
    echo "=================================="

    # 检查权限
    check_permissions

    # 设置项目目录
    setup_project_directory

    # 检查Docker环境
    check_docker

    # 备份配置
    if [ "$SKIP_BACKUP" != true ]; then
        backup_config
    else
        log_info "跳过配置备份"
    fi

    # 停止服务
    stop_services

    # 拉取最新代码
    pull_latest_code

    # 清理Docker缓存
    if [ "$QUICK_DEPLOY" != true ]; then
        clean_docker_cache
    else
        log_info "快速部署模式，跳过缓存清理"
    fi

    # 部署应用
    deploy_application

    # 验证部署
    verify_deployment

    # 清理旧备份
    if [ "$SKIP_BACKUP" != true ]; then
        cleanup_old_backups
    fi

    echo "=================================="
    log_success "🎉 $PROJECT_NAME 自动化部署完成！"
    echo ""
    log_info "📱 应用访问地址:"
    log_info "   主页: https://$DOMAIN"
    log_info "   API文档: https://$DOMAIN/docs"
    log_info "   健康检查: https://$DOMAIN/health"
    echo ""
    log_info "🔧 常用管理命令:"
    log_info "   查看日志: docker compose logs -f app"
    log_info "   重启应用: docker compose restart app"
    log_info "   停止应用: docker compose down"
    log_info "   查看状态: docker compose ps"
    echo ""
    log_info "🆘 如有问题，请检查日志或联系技术支持"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
