# syntax=docker/dockerfile:1
# ============================================================
# AIDA 前端 · Node 20 构建 → Nginx 托管
# ============================================================
# 构建：DOCKER_BUILDKIT=1 docker build -f frontend/Dockerfile -t aida-frontend:latest .
# ============================================================

# ── Stage 1: 构建 ──────────────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/node:20-alpine AS builder

WORKDIR /build
ENV NODE_ENV=development

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
# 常驻 Agent 宿主机 Docker 可复用 BuildKit npm 缓存（id 固定跨构建共享）
RUN --mount=type=cache,target=/root/.npm,id=aida-npm-cache \
    npm install --include=dev --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Nginx 托管 ───────────────────────────────────
FROM harbor.aie.rnd.huawei.com/library/nginx:latest

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 5401

CMD ["nginx", "-g", "daemon off;"]
