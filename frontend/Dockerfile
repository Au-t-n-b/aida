# ============================================================
# AIDA 前端 · Node 20 构建 → Nginx 托管
# ============================================================
# 构建：DOCKER_BUILDKIT=1 docker build -f frontend/Dockerfile -t harbor.aie.rnd.huawei.com/aida/frontend:latest .
# ============================================================

# ── Stage 1: 构建 ──────────────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/node:20-bookworm-slim AS builder

WORKDIR /build
ENV NODE_ENV=development

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm install --include=dev --no-audit --no-fund

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
