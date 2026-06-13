# ============================================================
# AIDA 前端 · Node 20 构建 → Nginx 托管
# ============================================================
# 构建：docker build -f frontend/Dockerfile -t aida-frontend:latest .
# 运行（配合 docker-compose）：docker run -d -p 80:80 aida-frontend:latest
# ============================================================

# ── Stage 1: 构建 ──────────────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/node:20-alpine AS builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry http://mirrors.tools.huawei.com/npm/ && \
    npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Nginx 托管 ───────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/nginx:1.27-alpine

# 自定义 Nginx 配置（含 Agent/Manager API 反向代理）
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 拷入前端构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 8081

CMD ["nginx", "-g", "daemon off;"]
