import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.198", username="root", password="TzB!Kal7", timeout=20, allow_agent=False, look_for_keys=False)

dockerfile = "/opt/aida/build/clawmanager/deploy/Dockerfile.claw"
trusted = "--trusted-host mirrors.aliyun.com --trusted-host files.pythonhosted.org --trusted-host pypi.org "
cmds = [
    # normalize pip/uv lines to include trusted hosts + timeout
    f"sed -i 's|pip install --no-cache-dir --index-url|pip install --no-cache-dir {trusted}--default-timeout=300 --index-url|g' {dockerfile}",
    f"sed -i 's|uv pip install --system --no-cache --index-url|uv pip install --system --no-cache {trusted}--index-url|g' {dockerfile}",
    f"grep -n 'pip install\\|uv pip install' {dockerfile}",
    "cd /opt/aida/build && nohup docker build -f clawmanager/deploy/Dockerfile.claw -t xclaw-agui:0.2 --build-arg http_proxy=http://10.143.2.250:8088/ --build-arg https_proxy=http://10.143.2.250:8088/ . > /tmp/docker-build.log 2>&1 &",
]
for cmd in cmds:
    _, stdout, stderr = c.exec_command(cmd)
    stdout.channel.recv_exit_status()
    print((stdout.read() + stderr.read()).decode("utf-8", "replace"))
    print("---")
c.close()
