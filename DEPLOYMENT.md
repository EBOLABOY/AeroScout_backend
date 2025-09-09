# 🚀 部署指南（CI/CD 驱动）

本项目使用 GitHub Actions + GHCR + Supabase CLI 完成全自动化部署。推送到 `main` 分支即自动构建与部署至生产环境。

## 前置条件（服务器）

- 操作系统：Ubuntu 20.04/22.04（建议）
- 必备软件：Docker Engine（包含 Compose v2）、Git
- 网络：可访问 GitHub 与 GHCR（ghcr.io）

首次部署时，GitHub Actions 会自动在服务器侧完成：
- 拉取项目仓库到 `/opt/aeroscout`
- 安装 Node 与 Supabase CLI（若未安装）
- 应用数据库迁移（Supabase 非交互式 `db push`）
- 拉取并启动最新应用镜像

## GitHub Actions 配置（Secrets）

在仓库的 Settings → Secrets and variables → Actions 中添加：

- `SSH_HOST`：生产服务器地址
- `SSH_USER`：SSH 登录用户
- `SSH_PRIVATE_KEY`：SSH 私钥
- `SUPABASE_DB_URL`：Supabase 数据库连接字符串（Postgres URI）
- `SUPABASE_ACCESS_TOKEN`：Supabase 访问令牌（供 CLI 使用）
- `GHCR_PAT`（可选）：服务器侧从 GHCR 拉取私有镜像使用的 PAT（具备 `read:packages`）

说明：CI 侧推送镜像使用内置 `GITHUB_TOKEN`，不需要额外配置。服务器侧若拉取公共镜像可省略 `GHCR_PAT`。

## 部署流程（自动触发）

1. 推送到 `main`
2. CI 作业：Ruff 检查与 pytest 用例
3. Build 作业：Poetry 导出锁文件、构建多架构镜像、推送到 `ghcr.io/<owner>/<repo>`（带 `sha-<shortsha>` 与 `latest` 标签）
4. Deploy 作业（SSH 到服务器）：
   - 拉取仓库最新代码（用于迁移文件）
   - 执行 `npx supabase db push`（通过环境变量 `SUPABASE_DB_URL` 非交互式连接）
   - 使用 `docker compose -f docker-compose.yml -f docker-compose.prod.yml` 拉取并重启服务
   - 两阶段健康检查：
     - 内部检查：容器内 `GET http://localhost:8000/health` 和 `GET /api/flights/airports/search?q=pek`
     - 端到端检查：`curl -sf --resolve apiticketradar.izlx.de:443:127.0.0.1 https://apiticketradar.izlx.de/health`

## 查看部署状态

- 在 GitHub → Actions 中查看 `CI-CD` 工作流运行日志
- 服务器上（`/opt/aeroscout`）：

```bash
docker compose ps
docker compose logs -f app
```

## 回滚（手动）

找到上一次成功的 SHA：

```bash
APP_IMAGE=ghcr.io/<owner>/<repo>:sha-abcdef1 \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

或使用提供的回滚脚本：

```bash
./rollback.sh sha-abcdef1
```

## 常见问题

- GHCR 拉取失败：确保镜像为公开或在 Secrets 配置 `GHCR_PAT`
- 数据库迁移失败：检查 `SUPABASE_DB_URL` 与 `SUPABASE_ACCESS_TOKEN`
- 健康检查失败：查看 `docker compose logs -f app` 输出错误详情

## 规划：Staging 环境

建议引入 `develop` → Staging → Production 的多环境流程：

- 新增一台 Staging 服务器与独立 Supabase 项目（或独立 schema）
- 复制 CI/CD 工作流为 `deploy-staging.yml`，触发分支改为 `develop`
- 生产发布由 Tag 或 Release 触发
