#!/bin/bash

# TicketRadar Docker 部署脚本
# 域名: https://api.ticketradar.izlx.de/

set -e

echo "🚀 开始部署 TicketRadar 系统..."

# 检查必要的命令
command -v docker >/dev/null 2>&1 || { echo "❌ Docker 未安装"; exit 1; }
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose 未安装"; exit 1; }

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs/nginx
mkdir -p ssl

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在，请先配置环境变量"
    exit 1
fi

# 检查 SSL 证书
if [ ! -f ssl/fullchain.pem ] || [ ! -f ssl/privkey.pem ]; then
    echo "⚠️  SSL 证书不存在，将使用 HTTP 模式启动"
    echo "请运行 ./setup-ssl.sh 来配置 SSL 证书"
    
    # 临时修改 nginx 配置为 HTTP 模式
    cp nginx.conf nginx.conf.backup
    cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    client_max_body_size 10M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    upstream ticketradar_app {
        server app:8000;
    }

    server {
        listen 80;
        server_name api.ticketradar.izlx.de;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            proxy_pass http://ticketradar_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;
            
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        location /health {
            proxy_pass http://ticketradar_app/health;
            access_log off;
        }
    }
}
EOF
fi

# 停止现有容器
echo "🛑 停止现有容器..."
docker compose down --remove-orphans || true

# 构建并启动服务
echo "🔨 构建并启动服务..."
docker compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "🔍 检查服务状态..."
docker compose ps

# 检查健康状态
echo "🏥 检查应用健康状态..."
for i in {1..10}; do
    if curl -f http://localhost/health >/dev/null 2>&1; then
        echo "✅ 应用健康检查通过"
        break
    fi
    echo "⏳ 等待应用启动... ($i/10)"
    sleep 10
done

echo "🎉 部署完成！"
echo "📍 访问地址: http://api.ticketradar.izlx.de"
echo "📊 查看日志: docker compose logs -f"
echo "🔧 管理服务: docker compose [start|stop|restart]"

if [ -f nginx.conf.backup ]; then
    echo "⚠️  当前使用 HTTP 模式，请运行 ./setup-ssl.sh 配置 HTTPS"
fi
