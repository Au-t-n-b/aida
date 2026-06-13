# ============================================================
# AIDA Agent 后端 · Python 3.11 + FastAPI/Uvicorn
# ============================================================
# 构建：docker build -f agent/Dockerfile -t aida-agent:latest .
# 运行：docker run -d -p 7401:7401 --env-file .env -v /data/aida:/app/.data aida-agent:latest
# ============================================================

FROM harbor.aie.rnd.huawei.com/library/python:3.12.13-slim

# 内网 apt 源（Jenkins Agent 无法直连 deb.debian.org）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|http://mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
      sed -i 's|http://deb.debian.org/debian-security|http://mirrors.tools.huawei.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list; \
    fi

# 系统依赖（pandas/openpyxl 需要的 libxml 等）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖（-r 保留行内注释；排除 Windows 专用 pywin32）
COPY agent/requirements.txt ./agent/requirements.txt
RUN grep -v 'pywin32' agent/requirements.txt > /tmp/requirements-docker.txt && \
    pip install --no-cache-dir \
    -i http://mirrors.tools.huawei.com/pypi/simple \
    --trusted-host mirrors.tools.huawei.com \
    -r /tmp/requirements-docker.txt

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
