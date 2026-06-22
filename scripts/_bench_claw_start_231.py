#!/usr/bin/env python3
"""Measure claw cold start on 231."""
import time
import paramiko

CMD = r"""
export DOCKER_API_VERSION=1.42
docker rm -f claw-bench 2>/dev/null || true
echo '=== cold start timing ==='
t0=$(date +%s)
docker run -d --name claw-bench \
  -p 17699:7401 \
  -v /opt/aida/aida-data/skill/org:/app/agent/skills:rw \
  -v /opt/aida/aida-data/runtime/checkpoints:/opt/aida/aida-data/runtime/checkpoints:rw \
  -v /opt/aida_liwen/skills/software_deployment:/app/skills/software_deployment:rw \
  --env-file /opt/aida_liwen/agent/.env \
  -e AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business \
  -e AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/claw-bench.db \
  --add-host=host.docker.internal:host-gateway \
  aida/claw_liwen:dev >/dev/null
echo docker_run_done +$(( $(date +%s) - t0 ))s
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:17699/healthz/ready >/dev/null 2>&1; then
    echo ready_after ${i}s
    break
  fi
  sleep 1
done
echo '=== bootstrap log ==='
docker logs claw-bench 2>&1 | head -30
echo '=== wait-nanobot lines ==='
docker logs claw-bench 2>&1 | grep -E 'wait-nanobot|claw-bootstrap|Started server' | head -15
docker rm -f claw-bench >/dev/null
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.231", username="root", password="Xvz!DI0g", timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(CMD, timeout=180)
print(o.read().decode("utf-8", errors="replace").encode("ascii", errors="backslashreplace").decode("ascii"))
c.close()
