#!/usr/bin/env bash
set -euo pipefail

# 快速回滚到上一个或指定的 Docker 镜像版本

if [ -z "${1:-}" ]; then
  echo "错误: 请提供要回滚到的镜像标签 (Git SHA)。"
  echo "用法: ./rollback.sh sha-abcdef1"
  echo "你可以从 GitHub Actions 的构建日志中找到之前的成功部署的 SHA 标签。"
  exit 1
fi

IMAGE_TAG="$1"

# 仓库镜像名（默认与本仓库一致，可通过环境变量覆盖）
# 注意大小写需与 CI 推送时保持一致
DOCKER_IMAGE_NAME=${DOCKER_IMAGE_NAME:-"ghcr.io/EBOLABOY/AeroScout_backend"}
FULL_IMAGE_NAME="${DOCKER_IMAGE_NAME}:${IMAGE_TAG}"

echo "🚀 准备回滚到镜像: ${FULL_IMAGE_NAME}"

# 设置 APP_IMAGE 环境变量，以便 compose overlay 使用
export APP_IMAGE="${FULL_IMAGE_NAME}"

echo "1. 登录 GHCR 以确保可以拉取镜像..."
if [ -z "${GHCR_PAT:-}" ]; then
  echo "警告: 环境变量 GHCR_PAT 未设置。如果镜像是私有的，拉取可能会失败。"
  read -p "是否输入 GHCR Personal Access Token (PAT) 进行登录? [y/N]: " yn
  if [[ "$yn" =~ ^[Yy]$ ]]; then
    read -s -p "请输入 GHCR PAT: " GHCR_PAT_INPUT
    echo
    echo "${GHCR_PAT_INPUT}" | docker login ghcr.io -u "${USER}" --password-stdin
  else
    echo "跳过登录，尝试直接拉取（需要公共镜像）。"
  fi
else
  echo "${GHCR_PAT}" | docker login ghcr.io -u "${USER}" --password-stdin
fi

echo "2. 拉取指定版本的镜像..."
docker pull "${FULL_IMAGE_NAME}"

echo "3. 使用旧版本镜像重启服务..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "4. 等待服务启动并进行健康检查..."
sleep 5

for i in {1..10}; do
  if docker compose exec -T app curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ 回滚成功！服务已恢复健康状态。"
    echo "当前运行的镜像: ${FULL_IMAGE_NAME}"
    exit 0
  fi
  echo "等待健康检查... ($i/10)"
  sleep 2
done

echo "❌ 回滚后健康检查失败！请手动检查服务状态。"
docker compose logs app --tail 100 || true
exit 1

