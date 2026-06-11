"""Probe SMTP connectivity — tries common Huawei mail servers."""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

USER = os.environ.get("SMTP_USER", "jintao32@huawei.com")
PWD = os.environ.get("SMTP_PASSWORD", "").strip()

CANDIDATES = [
    ("smtp.huawei.com", 465, "ssl"),
    ("smtp.huawei.com", 587, "starttls"),
    ("mail.huawei.com", 465, "ssl"),
    ("mail.huawei.com", 587, "starttls"),
    ("smtp.sparkspace.huaweicloud.com", 465, "ssl"),
]


def try_one(host: str, port: int, mode: str) -> str:
    ctx = ssl.create_default_context()
    if os.environ.get("SMTP_SSL_VERIFY", "true").strip().lower() in ("0", "false", "no"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        if mode == "ssl":
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=12) as s:
                s.ehlo()
                if PWD:
                    s.login(USER, PWD)
                    return "PASS login"
                return "PASS connect (no password set)"
        with smtplib.SMTP(host, port, timeout=12) as s:
            s.ehlo()
            if mode == "starttls":
                s.starttls(context=ctx)
                s.ehlo()
            if PWD:
                s.login(USER, PWD)
                return "PASS login"
            return "PASS connect (no password set)"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {e}"


def main() -> int:
    print(f"SMTP_USER={USER!r}  password={'set' if PWD else 'MISSING'}")
    for host, port, mode in CANDIDATES:
        print(f"  {host}:{port} ({mode}) -> {try_one(host, port, mode)}")
    if not PWD:
        print("\nSet SMTP_PASSWORD in agent/.env then re-run.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
