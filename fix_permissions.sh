#!/bin/bash

# 手动修复数据分析目录权限的脚本

echo "🔧 手动修复数据分析目录权限..."

# 检查当前用户
echo "当前用户: $(whoami)"

# 创建目录
mkdir -p ./data_analysis

# 方法1: 设置宽松权限
echo "设置目录权限为 777 (所有用户可读写)..."
chmod 777 ./data_analysis

# 方法2: 如果是root用户，改变所有权
if [ "$EUID" -eq 0 ]; then
    echo "检测到root用户，设置目录所有者为 1000:1000..."
    chown -R 1000:1000 ./data_analysis
fi

# 验证权限
echo "当前目录权限:"
ls -la . | grep data_analysis

echo "✅ 权限修复完成！现在重启容器:"
echo "docker compose restart app"