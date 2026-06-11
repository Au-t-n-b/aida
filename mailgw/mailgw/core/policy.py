"""白名单判定（spec §5.1）：to+cc 全部命中才允许直发。"""
from dataclasses import dataclass

from mailgw.config import PolicyConfig


@dataclass
class Verdict:
    allowed: bool
    misses: list[str]  # 未命中白名单的地址（原样返回，便于提示）


def _hit(addr: str, policy: PolicyConfig) -> bool:
    addr = addr.strip().lower()
    if addr in (a.lower() for a in policy.whitelist_addresses):
        return True
    domain = addr.rsplit("@", 1)[-1]
    return domain in (d.lower().lstrip("@") for d in policy.whitelist_domains)


def check_whitelist(recipients: list[str], policy: PolicyConfig) -> Verdict:
    misses = [r for r in recipients if not _hit(r, policy)]
    return Verdict(allowed=not misses, misses=misses)
