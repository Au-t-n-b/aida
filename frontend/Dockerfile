# ============================================================
# AIDA 前端 · Node 20 构建 → Nginx 托管
# ============================================================
# 构建：docker build -f frontend/Dockerfile -t aida/frontend:latest .
# 运行（配合 docker-compose）：docker run -d -p 80:80 aida/frontend:latest
# ============================================================

# ── Stage 1: 构建 ──────────────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/node:20-bookworm-slim AS builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry http://mirrors.tools.huawei.com/npm/ && \
    npm config set strict-ssl false && \
    npm config set fetch-retries 5 && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm install --include=dev --no-audit --no-fund

COPY frontend/ ./
# 镜像构建跳过 prebuild 类型检查，直接 vite 打包（CI 类型检查可另开 Job）
RUN npx vite build

# ── Stage 2: Nginx 托管 ───────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/nginx:latest

# 自定义 Nginx 配置（含 Agent/Manager API 反向代理）
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 拷入前端构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 5401

CMD ["nginx", "-g", "daemon off;"]
