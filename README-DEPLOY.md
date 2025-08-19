# TicketRadar Docker 部署指南

## 🚀 快速部署

### 系统要求

- **操作系统**: Ubuntu 20.04+ 
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **内存**: 最少 2GB
- **磁盘**: 最少 10GB
- **域名**: api.ticketradar.izlx.de (需要解析到服务器 IP)

### 1. 安装 Docker 和 Docker Compose

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 重新登录以应用组权限
exit
```

### 2. 部署应用

```bash
# 克隆项目
git clone <your-repo-url>
cd 机票监控

# 配置环境变量
cp .env.example .env
nano .env  # 编辑配置

# 设置脚本权限
chmod +x deploy.sh setup-ssl.sh

# 部署应用 (HTTP 模式)
./deploy.sh
```

### 3. 配置 HTTPS (推荐)

```bash
# 修改 setup-ssl.sh 中的邮箱地址
nano setup-ssl.sh

# 配置 SSL 证书
./setup-ssl.sh

# 重新部署启用 HTTPS
./deploy.sh
```

## 📋 服务架构

```
Internet
    ↓
Nginx (Port 80/443)
    ↓
FastAPI App (Port 8000)
    ↓
Redis (Port 6379)
```

### 服务组件

- **nginx**: 反向代理 + SSL 终止
- **app**: FastAPI 应用 (机票监控系统)
- **redis**: 缓存服务

## 🔧 管理命令

### 基本操作

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
docker compose logs -f app    # 只看应用日志
docker compose logs -f nginx  # 只看 nginx 日志

# 重启服务
docker compose restart
docker compose restart app    # 只重启应用

# 停止服务
docker compose stop

# 启动服务
docker compose start

# 完全停止并删除容器
docker compose down
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并部署
docker compose up -d --build

# 或使用部署脚本
./deploy.sh
```

### 数据备份

```bash
# 备份 Redis 数据
docker compose exec redis redis-cli BGSAVE
docker cp ticketradar-redis:/data/dump.rdb ./backup/

# 查看 Redis 状态
docker compose exec redis redis-cli info
```

## 🔐 SSL 证书管理

### 自动续期

```bash
# 手动续期
./renew-ssl.sh

# 设置自动续期 (crontab)
crontab -e
# 添加以下行 (每天凌晨3点检查续期)
0 3 * * * /path/to/your/project/renew-ssl.sh >> /var/log/ssl-renew.log 2>&1
```

### 证书信息查看

```bash
# 查看证书详情
openssl x509 -in ssl/fullchain.pem -text -noout

# 查看证书过期时间
openssl x509 -in ssl/fullchain.pem -noout -dates
```

## 📊 监控和日志

### 日志位置

- **应用日志**: `logs/`
- **Nginx 日志**: `logs/nginx/`
- **Docker 日志**: `docker compose logs`

### 健康检查

```bash
# 检查应用健康状态
curl https://api.ticketradar.izlx.de/health

# 检查各服务状态
docker compose ps
```

### 性能监控

```bash
# 查看资源使用情况
docker stats

# 查看 Redis 内存使用
docker compose exec redis redis-cli info memory
```

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   sudo netstat -tlnp | grep :80
   sudo netstat -tlnp | grep :443
   ```

2. **SSL 证书获取失败**
   - 检查域名解析: `nslookup api.ticketradar.izlx.de`
   - 检查防火墙: `sudo ufw status`
   - 查看 certbot 日志: `docker compose -f docker-compose.ssl.yml logs certbot`

3. **应用启动失败**
   ```bash
   # 查看详细日志
   docker compose logs app

   # 检查配置
   docker compose config
   ```

4. **Redis 连接失败**
   ```bash
   # 检查 Redis 状态
   docker compose exec redis redis-cli ping

   # 查看 Redis 日志
   docker compose logs redis
   ```

### 重置部署

```bash
# 完全清理并重新部署
docker compose down -v
docker system prune -f
./deploy.sh
```

## 🔒 安全建议

1. **防火墙配置**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 80
   sudo ufw allow 443
   ```

2. **定期更新**
   ```bash
   # 更新系统
   sudo apt update && sudo apt upgrade -y
   
   # 更新 Docker 镜像
   docker compose pull
   docker compose up -d
   ```

3. **备份策略**
   - 定期备份 `.env` 文件
   - 备份 SSL 证书
   - 备份 Redis 数据

## 📞 支持

如有问题，请查看：
- 应用日志: `docker compose logs app`
- Nginx 日志: `docker compose logs nginx`
- 系统日志: `journalctl -u docker`
