# ============================================================
# AIDA Claw 容器 · agent + nanobot（每用户/项目实例）
# ============================================================
# 构建（仓库根目录）：
#   docker build -f deploy/claw/Dockerfile -t aida/claw_liwen:dev .
# 231 无外网 Harbor 时：
#   docker build --build-arg PYTHON_BASE=python:3.12-slim -f deploy/claw/Dockerfile -t aida/claw_liwen:dev .
# 运行（示例）：
#   docker run --rm -p 17401:7401 \
#     -v /opt/aida/aida-data:/opt/aida/aida-data:rw \
#     --env-file agent/.env \
#     -e AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business \
#     -e AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/claw-smoke.db \
#     --add-host=host.docker.internal:host-gateway \
#     aida/claw_liwen:dev
# ============================================================

ARG PYTHON_BASE=harbor.aie.rnd.huawei.com/library/python:3.12.13-slim
FROM ${PYTHON_BASE}

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|http://mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
      sed -i 's|http://deb.debian.org/debian-security|http://mirrors.tools.huawei.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list; \
    fi || true

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libxml2 \
        libxslt1.1 \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- agent 依赖 ---
COPY agent/requirements.txt ./agent/requirements.txt
RUN grep -v 'pywin32' agent/requirements.txt > /tmp/requirements-docker.txt && \
    pip install --no-cache-dir \
    -i http://mirrors.tools.huawei.com/pypi/simple \
    --trusted-host mirrors.tools.huawei.com \
    -r /tmp/requirements-docker.txt

# --- nanobot 依赖（editable 安装，CLI 入口 nanobot serve）---
COPY nanobot-main/ ./nanobot-main/
ENV NANOBOT_SKIP_WEBUI_BUILD=1
RUN pip install --no-cache-dir \
    -i http://mirrors.tools.huawei.com/pypi/simple \
    --trusted-host mirrors.tools.huawei.com \
    ./nanobot-main/

# --- 应用代码（agent/skills 运行时由宿主机 /opt/aida/aida-data/skill/org 挂载）---
COPY agent/ ./agent/
RUN rm -rf /app/agent/skills && mkdir -p /app/agent/skills
COPY shared/ ./shared/
COPY scripts/remove_nanobot_builtin_skills.py ./scripts/remove_nanobot_builtin_skills.py
RUN python scripts/remove_nanobot_builtin_skills.py

# --- Claw 运行时脚本与监督配置 ---
COPY deploy/claw/claw_bootstrap.py ./deploy/claw/claw_bootstrap.py
COPY deploy/claw/wait_nanobot_then_agent.sh ./deploy/claw/wait_nanobot_then_agent.sh
COPY deploy/claw/claw-supervisor.conf /etc/supervisor/conf.d/claw.conf
COPY deploy/claw/claw_entrypoint.sh /usr/local/bin/claw_entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/claw_entrypoint.sh /app/deploy/claw/wait_nanobot_then_agent.sh && \
    chmod +x /usr/local/bin/claw_entrypoint.sh /app/deploy/claw/wait_nanobot_then_agent.sh

# 业务数据与 checkpoint 挂载点（宿主机 /opt/aida/aida-data 同路径映射）
RUN mkdir -p \
    /opt/aida/aida-data/business \
    /opt/aida/aida-data/runtime/checkpoints \
    /opt/aida/aida-data/skill/org \
    /app/agent/skills \
    /root/.nanobot/workspace/skills \
    /root/.claude/skills

ENV PYTHONUNBUFFERED=1 \
    AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business \
    AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/claw.db \
    AIDA_USE_NANOBOT_LLM=1 \
    AIDA_CHAT_VIA_NANOBOT=1 \
    NANOBOT_API_URL=http://127.0.0.1:8900 \
    NANOBOT_CONFIG=/root/.nanobot/config.json \
    NANOBOT_WORKSPACE=/root/.nanobot/workspace \
    NO_PROXY=127.0.0.1,localhost \
    no_proxy=127.0.0.1,localhost

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -f http://127.0.0.1:7401/healthz/ready || exit 1

EXPOSE 7401 8900

ENTRYPOINT ["/usr/local/bin/claw_entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
