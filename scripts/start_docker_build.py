import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.198", username="root", password="TzB!Kal7", timeout=20, allow_agent=False, look_for_keys=False)

cmd = (
    "cd /opt/aida/build && "
    "nohup docker build "
    "-f clawmanager/deploy/Dockerfile.claw "
    "-t xclaw-agui:0.2 "
    "--build-arg http_proxy=http://10.143.2.250:8088/ "
    "--build-arg https_proxy=http://10.143.2.250:8088/ "
    ". > /tmp/docker-build.log 2>&1 &"
)
_, stdout, stderr = c.exec_command(cmd)
stdout.channel.recv_exit_status()
print("started build in background")
print(stderr.read().decode())
c.close()
