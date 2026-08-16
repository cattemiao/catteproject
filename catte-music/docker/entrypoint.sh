#!/usr/bin/env bash
# 单容器启动脚本：
#   证书：设置 DOMAIN + CERTBOT_EMAIL 后自动申请 Let's Encrypt 并每日自动续期；
#         未设置则生成自签名证书兜底。
#   服务：后端(127.0.0.1:8000) + 前端(127.0.0.1:5173) + nginx(80/443)
set -euo pipefail

CERT_DIR="${CERT_DIR:-/etc/nginx/certs}"
DOMAIN="${DOMAIN:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
ACME_WEBROOT="/var/www/certbot"
LE_LIVE="/etc/letsencrypt/live"

mkdir -p "$CERT_DIR" "$ACME_WEBROOT"

# ---- 1. 准备证书到固定路径（nginx 引用 /etc/nginx/certs/*.pem）----
# 已有 Let's Encrypt 证书则软链（保证续期后 nginx reload 读到最新）
if [ -n "$DOMAIN" ] && [ -f "$LE_LIVE/$DOMAIN/fullchain.pem" ]; then
    ln -sf "$LE_LIVE/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
    ln -sf "$LE_LIVE/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
    echo "[entrypoint] 使用已有 Let's Encrypt 证书: ${DOMAIN}"
else
    # 自签名占位，保证 nginx 始终能启动（若后续申请 LE 成功会被软链覆盖）
    if [ ! -f "$CERT_DIR/fullchain.pem" ] || [ ! -f "$CERT_DIR/privkey.pem" ]; then
        openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
            -keyout "$CERT_DIR/privkey.pem" \
            -out "$CERT_DIR/fullchain.pem" \
            -subj "/CN=${DOMAIN:-localhost}" \
            -addext "subjectAltName=DNS:${DOMAIN:-localhost},IP:127.0.0.1"
        echo "[entrypoint] 已生成自签名证书（占位）"
    fi
fi

# ---- 2. 启动后端（仅监听容器内部 127.0.0.1:8000）----
cd /app
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
echo "[entrypoint] 后端已启动: 127.0.0.1:8000"

# ---- 3. 启动前端 vite dev server（仅监听容器内部 127.0.0.1:5173）----
cd /app/frontend
npm run dev -- --host 127.0.0.1 --port 5173 &
echo "[entrypoint] 前端已启动: 127.0.0.1:5173"

# ---- 4. 启动 nginx（后台，先满足 ACME webroot 验证）----
nginx
echo "[entrypoint] nginx 已启动: 80/443"

# ---- 5. 首次申请 Let's Encrypt 证书（配置了域名时）----
if [ -n "$DOMAIN" ] && [ ! -f "$LE_LIVE/$DOMAIN/fullchain.pem" ]; then
    echo "[entrypoint] 申请 Let's Encrypt 证书: ${DOMAIN}"
    # 无邮箱时以 --register-unsafely-without-email 注册
    if [ -n "$CERTBOT_EMAIL" ]; then
        LE_ARGS="--email $CERTBOT_EMAIL"
    else
        LE_ARGS="--register-unsafely-without-email"
    fi
    if certbot certonly --webroot -w "$ACME_WEBROOT" \
        -d "$DOMAIN" $LE_ARGS \
        --agree-tos --non-interactive --quiet; then
        ln -sf "$LE_LIVE/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
        ln -sf "$LE_LIVE/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
        nginx -s reload
        echo "[entrypoint] Let's Encrypt 证书已生效"
    else
        echo "[entrypoint] 证书申请失败，继续使用占位证书"
    fi
fi

# ---- 6. 配置自动续期（cron 每日 03:17 / 15:17 检查，续期后重载 nginx）----
if [ -n "$DOMAIN" ]; then
    cat > /etc/cron.d/certbot-renew <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
17 3,15 * * * root certbot renew --webroot -w $ACME_WEBROOT --quiet --deploy-hook "ln -sf $LE_LIVE/$DOMAIN/fullchain.pem $CERT_DIR/fullchain.pem && ln -sf $LE_LIVE/$DOMAIN/privkey.pem $CERT_DIR/privkey.pem && nginx -s reload" >> /var/log/certbot-renew.log 2>&1
EOF
    chmod 644 /etc/cron.d/certbot-renew
    cron
    echo "[entrypoint] 已配置证书自动续期（每日检查）"
fi

# ---- 7. 前台保持容器存活 ----
tail -f /dev/null
