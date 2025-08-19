#!/bin/bash

# SSL 证书配置脚本 (Cloudflare Origin 证书)
# 域名: api.ticketradar.izlx.de

set -e

DOMAIN="api.ticketradar.izlx.de"

echo "🔐 Cloudflare Origin SSL 证书配置"
echo ""
echo "⚠️  注意：本项目现在使用 Cloudflare Origin 证书"
echo "证书文件已包含在代码中，无需运行此脚本"
echo ""
echo "📋 当前配置："
echo "- 证书类型: Cloudflare Origin 证书"
echo "- 有效期: 至 2040年8月15日"
echo "- 域名: $DOMAIN"
echo ""

# 检查证书文件
if [ -f ssl/fullchain.pem ] && [ -f ssl/privkey.pem ]; then
    echo "✅ 证书文件已存在"

    # 显示证书信息
    echo ""
    echo "📜 证书信息:"
    openssl x509 -in ssl/fullchain.pem -noout -dates
    openssl x509 -in ssl/fullchain.pem -noout -subject

else
    echo "❌ 证书文件不存在"
    echo ""
    echo "请按以下步骤配置 Cloudflare Origin 证书："
    echo "1. 登录 Cloudflare 控制台"
    echo "2. 选择域名 → SSL/TLS → Origin Server"
    echo "3. 点击 'Create Certificate'"
    echo "4. 复制证书内容到 ssl/fullchain.pem"
    echo "5. 复制私钥内容到 ssl/privkey.pem"
    echo "6. 运行 ./deploy.sh 部署"
    exit 1
fi

echo ""
echo "🎉 Cloudflare Origin 证书配置完成！"
echo ""
echo "📋 下一步："
echo "1. 确保 Cloudflare DNS 记录为橙色云朵（Proxied）"
echo "2. 设置 SSL/TLS 模式为 '完全（严格）'"
echo "3. 运行 ./deploy.sh 部署应用"
echo ""
echo "🔗 访问地址: https://$DOMAIN"


