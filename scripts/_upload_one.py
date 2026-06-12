#!/usr/bin/env python3
import base64
import sys
from pathlib import Path

import paramiko

local = Path(sys.argv[1])
remote = sys.argv[2]
host = sys.argv[3]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username="root", password="Xvz!DI0g", timeout=20)
c.exec_command(f"rm -rf {remote}")[1].read()
data = local.read_bytes()
b64 = base64.b64encode(data).decode("ascii")
chunk = 60000
with c.open_sftp() as sftp:
    with sftp.file(remote, "wb") as f:
        f.write(data)
print(f"uploaded {local} -> {remote} ({len(data)} bytes)")
c.close()
