# ============================================================
# AIDA 前端 · Node 20 构建 → Nginx 托管
# ============================================================
# 构建：DOCKER_BUILDKIT=1 docker build -f frontend/Dockerfile -t harbor.aie.rnd.huawei.com/aida/frontend:latest .
# ============================================================

# ── Stage 1: 构建 ──────────────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/node:20-bookworm-slim AS builder

WORKDIR /build
ENV NODE_ENV=development

# 仅 package.json：docker build 内按内网 registry 强制重建 package-lock.json
COPY frontend/package.json ./
RUN npm install --include=dev --no-audit --no-fund \
    --registry=http://mirrors.tools.huawei.com/npm/ \
    --strict-ssl=false \
    --fetch-retries=5 \
    --fetch-retry-mintimeout=20000 \
    --fetch-retry-maxtimeout=120000

# 源码（.dockerignore 排除 package-lock.json / .npmrc，保留上一步生成的 lock）
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
