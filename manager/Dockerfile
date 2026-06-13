# ============================================================
# AIDA Manager · 鉴权 / 项目协调层
# ============================================================
# 构建：docker build -f manager/Dockerfile -t harbor.aie.rnd.huawei.com/aida/manager:latest .
# ============================================================

FROM harbor.aie.rnd.huawei.com/library/python:3.12.13-slim

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|http://mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
      sed -i 's|http://deb.debian.org/debian-security|http://mirrors.tools.huawei.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.tools.huawei.com/debian|g' /etc/apt/sources.list; \
    fi

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY manager/requirements.txt ./manager/requirements.txt
RUN pip install \
    -i http://mirrors.tools.huawei.com/pypi/simple \
    --trusted-host mirrors.tools.huawei.com \
    -r manager/requirements.txt

COPY manager/ ./manager/
COPY shared/ ./shared/

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/healthz || exit 1

EXPOSE 8000

CMD ["uvicorn", "manager.main:app", "--host", "0.0.0.0", "--port", "8000"]
