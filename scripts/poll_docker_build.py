import time
import paramiko

for i in range(40):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("10.143.2.198", username="root", password="TzB!Kal7", timeout=20, allow_agent=False, look_for_keys=False)
    _, stdout, _ = c.exec_command(
        "ps aux | grep 'docker build' | grep -v grep | wc -l; "
        "tail -3 /tmp/docker-build.log; "
        "docker images --format '{{.Repository}}:{{.Tag}}' | grep xclaw || true"
    )
    out = stdout.read().decode()
    c.close()
    print(f"poll {i+1}: {out.replace(chr(10), ' | ')}")
    if "xclaw-agui:0.2" in out:
        print("BUILD DONE")
        raise SystemExit(0)
    lines = out.strip().splitlines()
    if lines and lines[0].strip() == "0":
        print("BUILD ENDED")
        raise SystemExit(1 if "xclaw-agui:0.2" not in out else 0)
    time.sleep(60)

print("TIMEOUT")
raise SystemExit(2)
