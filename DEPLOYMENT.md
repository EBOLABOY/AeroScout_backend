# 🚀 机票监控系统 - Ubuntu服务器一键部署指南

## 📋 部署前准备

### 1. 服务器要求
- **操作系统**: Ubuntu 18.04+ 
- **内存**: 最少2GB，推荐4GB+
- **存储**: 最少10GB可用空间
- **网络**: 需要访问GitHub和Docker Hub

### 2. 必需软件
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Git**: 2.0+
- **Curl**: 用于健康检查

## 🎯 一键部署步骤

### 方法一：直接下载脚本部署（推荐）

```bash
# 1. 下载部署脚本
wget https://raw.githubusercontent.com/EBOLABOY/AeroScout_backend/master/auto_deploy.sh

# 2. 添加执行权限
chmod +x auto_deploy.sh

# 3. 运行部署脚本
./auto_deploy.sh
```

### 方法二：克隆仓库后部署

```bash
# 1. 克隆项目
git clone https://github.com/EBOLABOY/AeroScout_backend.git
cd AeroScout_backend

# 2. 运行部署脚本
chmod +x auto_deploy.sh
./auto_deploy.sh
```

## ⚙️ 部署选项

### 标准部署（推荐）
```bash
./auto_deploy.sh
```
- 完整的部署流程
- 包含缓存清理和配置备份
- 适合生产环境

### 强制重新部署
```bash
./auto_deploy.sh --force
```
- 清理所有Docker缓存
- 强制重新构建镜像
- 适合解决部署问题

### 快速部署
```bash
./auto_deploy.sh --quick
```
- 跳过缓存清理
- 更快的部署速度
- 适合频繁更新

### 查看帮助
```bash
./auto_deploy.sh --help
```

## 🔍 部署验证

部署完成后，脚本会自动进行以下验证：

1. **容器状态检查**: 确保所有容器正常运行
2. **健康检查**: 访问 `/health` 端点
3. **AI功能测试**: 测试AI搜索接口
4. **SSL证书验证**: 检查HTTPS访问

### 手动验证命令

```bash
# 检查容器状态
docker compose ps

# 查看应用日志
docker compose logs -f app

# 测试健康检查
curl -k https://apiticketradar.izlx.de/health

# 测试AI搜索
curl -k -X POST "https://apiticketradar.izlx.de/api/flights/search/ai-enhanced/async?departure_code=PEK&destination_code=SZX&depart_date=2025-11-20&user_preferences=测试"
```

## 🔧 常用管理命令

### 应用管理
```bash
# 重启应用
docker compose restart app

# 停止应用
docker compose down

# 启动应用
docker compose up -d

# 查看实时日志
docker compose logs -f app

# 进入应用容器
docker compose exec app bash
```

### 数据库管理
```bash
# 查看数据库日志
docker compose logs -f db

# 连接数据库
docker compose exec db mysql -u root -p

# 备份数据库
docker compose exec db mysqldump -u root -p aeroscout > backup.sql
```

### 系统监控
```bash
# 查看系统资源使用
docker stats

# 查看磁盘使用
df -h

# 查看内存使用
free -h

# 查看网络连接
netstat -tlnp
```

## 🆘 故障排除

### 常见问题

#### 1. 端口被占用
```bash
# 查看端口占用
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# 停止占用端口的进程
sudo kill -9 <PID>
```

#### 2. Docker空间不足
```bash
# 清理Docker缓存
docker system prune -a -f

# 清理未使用的卷
docker volume prune -f
```

#### 3. SSL证书问题
```bash
# 重新生成SSL证书
./setup-ssl.sh

# 检查证书状态
openssl x509 -in /etc/letsencrypt/live/apiticketradar.izlx.de/fullchain.pem -text -noout
```

#### 4. 应用无法启动
```bash
# 查看详细日志
docker compose logs app

# 检查配置文件
cat .env

# 重新构建镜像
docker compose build --no-cache app
```

### 日志位置
- **应用日志**: `docker compose logs app`
- **数据库日志**: `docker compose logs db`
- **Nginx日志**: `docker compose logs nginx`
- **系统日志**: `/var/log/syslog`

## 📞 技术支持

如果遇到问题，请：

1. **查看日志**: 使用上述命令查看相关日志
2. **检查状态**: 确认所有容器正常运行
3. **重新部署**: 尝试使用 `--force` 选项重新部署
4. **联系支持**: 提供详细的错误日志和系统信息

## 🔄 更新部署

当有新版本发布时，只需重新运行部署脚本：

```bash
./auto_deploy.sh
```

脚本会自动：
- 拉取最新代码
- 备份当前配置
- 重新构建和部署
- 验证部署结果

## 🎉 部署成功

部署成功后，您可以访问：

- **主页**: https://apiticketradar.izlx.de
- **API文档**: https://apiticketradar.izlx.de/docs
- **健康检查**: https://apiticketradar.izlx.de/health

恭喜！您的机票监控系统已成功部署！🎊
