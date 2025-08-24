#!/bin/bash

# 初始化日志目录脚本
# 用于Docker容器启动时确保日志目录存在且权限正确

set -e

echo "初始化日志目录..."

# 创建日志目录
mkdir -p /app/logs

# 设置权限（如果当前用户有权限）
if [ -w /app/logs ] || [ "$(id -u)" = "0" ]; then
    chmod 755 /app/logs 2>/dev/null || echo "权限设置跳过（只读文件系统）"
    echo "日志目录初始化完成"
else
    echo "日志目录已存在，权限检查跳过"
fi

echo "日志目录准备就绪"