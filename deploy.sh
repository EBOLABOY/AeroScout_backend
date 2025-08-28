#!/bin/bash

# TicketRadar Docker 部署脚本
# 域名: https://apiticketradar.izlx.de/

set -e

echo "🚀 开始部署 TicketRadar 系统..."

# 检查必要的命令
command -v docker >/dev/null 2>&1 || { echo "❌ Docker 未安装"; exit 1; }
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose 未安装"; exit 1; }

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs/nginx
mkdir -p ssl
mkdir -p data_analysis  # 添加数据分析目录

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在，请先配置环境变量"
    exit 1
fi

# 检查 SSL 证书 (Cloudflare Origin 证书)
if [ ! -f ssl/fullchain.pem ] || [ ! -f ssl/privkey.pem ]; then
    echo "❌ Cloudflare Origin SSL 证书不存在"
    echo "请确保 ssl/fullchain.pem 和 ssl/privkey.pem 文件存在"
    echo "这些文件应该从 Cloudflare Origin Server 证书页面获取"
    exit 1
fi

echo "✅ 检测到 Cloudflare Origin SSL 证书"

# 停止现有容器
echo "🛑 停止现有容器..."
docker compose down --remove-orphans || true

# 构建并启动服务
echo "🔨 构建并启动服务..."
docker compose up -d --build

# 设置数据分析目录权限（确保容器可以写入）
echo "🔐 设置数据分析目录权限..."
chmod 755 data_analysis 2>/dev/null || echo "⚠️  权限设置跳过 (可能是Windows环境)"

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "🔍 检查服务状态..."
docker compose ps

# 检查健康状态
echo "🏥 检查应用健康状态..."
for i in {1..10}; do
    if curl -f -k https://localhost/health >/dev/null 2>&1; then
        echo "✅ 应用健康检查通过 (HTTPS)"
        break
    elif curl -f http://localhost/health >/dev/null 2>&1; then
        echo "✅ 应用健康检查通过 (HTTP)"
        break
    fi
    echo "⏳ 等待应用启动... ($i/10)"
    sleep 10
done

echo "🎉 部署完成！"
echo "📍 访问地址: https://apiticketradar.izlx.de"
echo "🔒 SSL证书: Cloudflare Origin 证书"
echo "📊 查看日志: docker compose logs -f"
echo "📂 数据分析文件: ./data_analysis/"
echo "🔧 管理服务: docker compose [start|stop|restart]"
echo "💡 管理工具: ./manage.sh [status|health|logs]"
echo ""
echo "✅ 数据保存功能已就绪！每次航班搜索后，对比数据将自动保存到 ./data_analysis/ 目录"
