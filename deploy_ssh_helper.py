#!/usr/bin/env python3
"""SSH helper for cursor-auto-deploy - runs remote commands with password auth."""
import sys
import paramiko
import os

SERVERS = {
    "197": {"host": "10.143.2.197", "password": "Xvz!DI0g", "alt_host": "10.143.2.231"},
    "198": {"host": "10.143.2.198", "password": "TzB!Kal7", "alt_host": "141.188.1.117"},
    "231": {"host": "10.143.2.231", "password": "Xvz!DI0g", "alt_host": "141.188.1.119"},
}

USERNAMES = ["j00954996", "root", "admin", "ux", "UX"]


def run_ssh(host, password, username, command, timeout=60):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=username, password=password, timeout=15, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        client.close()


def rsync_via_sftp(local_path, remote_path, host, password, username):
    """Simple directory sync using paramiko SFTP."""
    import stat
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password, timeout=15, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()

    def ensure_remote_dir(path):
        parts = path.replace("\\", "/").split("/")
        cur = ""
        for p in parts:
            if not p:
                continue
            cur = cur + "/" + p if cur else p
            try:
                sftp.stat(cur)
            except FileNotFoundError:
                sftp.mkdir(cur)

    uploaded = 0
    for root, dirs, files in os.walk(local_path):
        rel = os.path.relpath(root, local_path).replace("\\", "/")
        remote_dir = remote_path if rel == "." else f"{remote_path.rstrip('/')}/{rel}"
        ensure_remote_dir(remote_dir)
        for f in files:
            if f.endswith(".pyc") or "__pycache__" in root:
                continue
            lp = os.path.join(root, f)
            rp = f"{remote_dir}/{f}"
            sftp.put(lp, rp)
            uploaded += 1
    sftp.close()
    client.close()
    return uploaded


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"

    if action == "test":
        for name, cfg in SERVERS.items():
            for host in [cfg["host"], cfg.get("alt_host")]:
                if not host:
                    continue
                for user in USERNAMES:
                    try:
                        code, out, err = run_ssh(host, cfg["password"], user, "hostname && echo OK")
                        if code == 0 and "OK" in out:
                            print(f"SUCCESS: {name} host={host} user={user}")
                            print(out.strip())
                            break
                    except Exception as e:
                        print(f"FAIL: {name} host={host} user={user}: {e}")
                else:
                    continue
                break

    elif action == "run":
        # usage: python deploy_ssh_helper.py run HOST PASSWORD USER COMMAND
        host, password, user = sys.argv[2], sys.argv[3], sys.argv[4]
        cmd = sys.argv[5]
        code, out, err = run_ssh(host, password, user, cmd, timeout=600)
        print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        sys.exit(code)

    elif action == "rsync":
        local, remote, host, password, user = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
        n = rsync_via_sftp(local, remote, host, password, user)
        print(f"Uploaded {n} files to {host}:{remote}")
