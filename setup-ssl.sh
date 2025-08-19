#!/bin/bash

# SSL 证书配置脚本 (Let's Encrypt)
# 域名: api.ticketradar.izlx.de

set -e

DOMAIN="api.ticketradar.izlx.de"
EMAIL="your-email@example.com"  # 请修改为你的邮箱

echo "🔐 开始配置 SSL 证书..."

# 检查必要的命令
command -v docker >/dev/null 2>&1 || { echo "❌ Docker 未安装"; exit 1; }

# 创建必要的目录
mkdir -p ssl
mkdir -p certbot/www

echo "📧 请确认邮箱地址: $EMAIL"
read -p "是否正确？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请修改脚本中的 EMAIL 变量"
    exit 1
fi

# 检查域名解析
echo "🌐 检查域名解析..."
if ! nslookup $DOMAIN >/dev/null 2>&1; then
    echo "⚠️  域名 $DOMAIN 解析失败，请确保域名已正确解析到此服务器"
    read -p "是否继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 临时启动 HTTP 服务用于验证
echo "🚀 启动临时 HTTP 服务用于域名验证..."

# 创建临时 docker-compose 文件
cat > docker-compose.ssl.yml << EOF
version: '3.8'
services:
  nginx-temp:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./certbot/www:/var/www/certbot:ro
      - ./nginx-temp.conf:/etc/nginx/nginx.conf:ro
    networks:
      - ssl-network

  certbot:
    image: certbot/certbot
    volumes:
      - ./ssl:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    networks:
      - ssl-network

networks:
  ssl-network:
    driver: bridge
EOF

# 创建临时 nginx 配置
cat > nginx-temp.conf << EOF
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name $DOMAIN;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 200 'SSL setup in progress...';
            add_header Content-Type text/plain;
        }
    }
}
EOF

# 启动临时服务
docker compose -f docker-compose.ssl.yml up -d nginx-temp

# 等待服务启动
sleep 5

# 获取证书
echo "📜 获取 SSL 证书..."
docker compose -f docker-compose.ssl.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

# 检查证书是否成功获取
if [ -f "ssl/live/$DOMAIN/fullchain.pem" ] && [ -f "ssl/live/$DOMAIN/privkey.pem" ]; then
    echo "✅ SSL 证书获取成功"
    
    # 复制证书到 ssl 目录
    cp ssl/live/$DOMAIN/fullchain.pem ssl/
    cp ssl/live/$DOMAIN/privkey.pem ssl/
    
    # 设置正确的权限
    chmod 644 ssl/fullchain.pem
    chmod 600 ssl/privkey.pem
    
    echo "📋 证书信息:"
    openssl x509 -in ssl/fullchain.pem -text -noout | grep -E "(Subject:|Not After)"
    
else
    echo "❌ SSL 证书获取失败"
    exit 1
fi

# 清理临时服务
echo "🧹 清理临时服务..."
docker compose -f docker-compose.ssl.yml down
rm -f docker-compose.ssl.yml nginx-temp.conf

# 恢复原始 nginx 配置
if [ -f nginx.conf.backup ]; then
    mv nginx.conf.backup nginx.conf
    echo "✅ 已恢复 HTTPS nginx 配置"
fi

# 创建证书续期脚本
cat > renew-ssl.sh << 'EOF'
#!/bin/bash
echo "🔄 续期 SSL 证书..."
docker run --rm \
    -v $(pwd)/ssl:/etc/letsencrypt \
    -v $(pwd)/certbot/www:/var/www/certbot \
    certbot/certbot renew --webroot --webroot-path=/var/www/certbot

if [ $? -eq 0 ]; then
    echo "✅ 证书续期成功，重新加载 nginx..."
    cp ssl/live/api.ticketradar.izlx.de/fullchain.pem ssl/
    cp ssl/live/api.ticketradar.izlx.de/privkey.pem ssl/
    docker compose exec nginx nginx -s reload
else
    echo "❌ 证书续期失败"
fi
EOF

chmod +x renew-ssl.sh

echo "🎉 SSL 配置完成！"
echo "📍 证书位置: ssl/fullchain.pem, ssl/privkey.pem"
echo "🔄 续期命令: ./renew-ssl.sh"
echo "⏰ 建议设置 crontab 自动续期: 0 3 * * * /path/to/renew-ssl.sh"
echo ""
echo "现在可以运行 ./deploy.sh 来启动 HTTPS 服务"
