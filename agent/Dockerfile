# ============================================================
# AIDA Agent 后端 · Python 3.11 + FastAPI/Uvicorn
# ============================================================
# 构建：docker build -f agent/Dockerfile --build-arg REGISTRY=harbor.aie.rnd.huawei.com/library -t aida-agent:latest .
# 运行：docker run -d -p 7401:7401 --env-file .env -v /data/aida:/app/.data aida-agent:latest
# ============================================================

ARG REGISTRY=docker.io/library
FROM ${REGISTRY}/python:3.11-slim

# 系统依赖（pandas/openpyxl 需要的 libxml 等）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖（先拷 requirements 利用缓存层）
COPY agent/requirements.txt ./agent/requirements.txt
RUN pip install --no-cache-dir \
    -i http://mirrors.tools.huawei.com/pypi/simple \
    --trusted-host mirrors.tools.huawei.com \
    $(grep -vE 'pywin32|^#|^$' agent/requirements.txt)

# 拷入后端代码
COPY agent/ ./agent/

# 拷入 skills（A 层 SKILL.md 源）+ 部署到运行时位置
COPY skills/ ./skills/
RUN mkdir -p /root/.claude/skills && \
    cp -r skills/. /root/.claude/skills/

# 拷入文档（守门 lint / 开发者文档站需要）
COPY docs/ ./docs/
COPY CLAUDE.md AGENTS.md ROADMAP.md README.md ./

# 业务数据目录（运行时挂载点）
RUN mkdir -p /app/.data
ENV AIDA_BUSINESS_ROOT=/app/.data

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:7401/healthz || exit 1

EXPOSE 7401

CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "7401"]
