import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.198", username="root", password="TzB!Kal7", timeout=20, allow_agent=False, look_for_keys=False)

dockerfile = "/opt/aida/build/clawmanager/deploy/Dockerfile.claw"
cmds = [
    f"sed -i 's|uv pip install --system --no-cache|uv pip install --system --no-cache --index-url https://mirrors.aliyun.com/pypi/simple/|g' {dockerfile}",
    f"sed -i 's|pip install --no-cache-dir /app/shared|pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ /app/shared|g' {dockerfile}",
    f"sed -i 's|pip install --no-cache-dir -r agent-requirements.txt|pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r agent-requirements.txt|g' {dockerfile}",
    f"grep -n 'index-url\\|uv pip install\\|pip install' {dockerfile}",
    "cd /opt/aida/build && nohup docker build -f clawmanager/deploy/Dockerfile.claw -t xclaw-agui:0.2 --network host --build-arg http_proxy=http://10.143.2.250:8088/ --build-arg https_proxy=http://10.143.2.250:8088/ . > /tmp/docker-build.log 2>&1 &",
]
for cmd in cmds:
    _, stdout, stderr = c.exec_command(cmd)
    stdout.channel.recv_exit_status()
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    print(out)
    print("---")
c.close()
print("rebuild started")
