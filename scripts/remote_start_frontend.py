import time
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.143.2.198", username="root", password="TzB!Kal7", timeout=20, allow_agent=False, look_for_keys=False)

start_cmd = (
    "cd /opt/aida/aida/frontend/dist && "
    "nohup python3 -m http.server 8081 >> /var/log/xclaw-frontend.log 2>&1 &"
)
_, stdout, stderr = c.exec_command(start_cmd)
stdout.channel.recv_exit_status()
time.sleep(3)

_, stdout, stderr = c.exec_command(
    "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:8081; "
    "echo; ps aux | grep 'http.server 8081' | grep -v grep"
)
print(stdout.read().decode())
print(stderr.read().decode())
c.close()
