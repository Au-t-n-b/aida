#!/usr/bin/env python3
import paramiko
CMD = """
export DOCKER_API_VERSION=1.42
docker rm -f claw-debug 2>/dev/null || true
docker run -d --name claw-debug -p 17402:7401 \
  -v /opt/aida/aida-data:/opt/aida/aida-data:rw \
  --env-file /opt/aida_liwen/agent/.env \
  -e AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business \
  -e AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/claw-debug.db \
  --add-host=host.docker.internal:host-gateway \
  aida/claw_liwen:dev
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 6
  echo "--- t=$((i*6))s status ---"
  docker inspect claw-debug --format 'status={{.State.Status}} exit={{.State.ExitCode}}' 2>/dev/null || echo gone
  docker logs claw-debug 2>&1 | tail -15
  curl -sf http://127.0.0.1:17402/healthz && echo HEALTH_OK && break
done
docker logs claw-debug 2>&1 | tail -60
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('10.143.2.231', username='root', password='Xvz!DI0g', timeout=30, allow_agent=False, look_for_keys=False)
_, o, e = c.exec_command(CMD, timeout=120)
print(o.read().decode('utf-8', errors='replace').encode('ascii', errors='backslashreplace').decode('ascii'))
c.close()
