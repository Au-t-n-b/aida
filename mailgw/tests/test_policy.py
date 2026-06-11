# tests/test_policy.py
from mailgw.config import PolicyConfig
from mailgw.core.policy import check_whitelist


def _policy() -> PolicyConfig:
    return PolicyConfig(whitelist_domains=["corp.com"],
                        whitelist_addresses=["vip@other.com"])


def test_all_hit_domain_and_address():
    v = check_whitelist(["a@corp.com", "VIP@Other.com"], _policy())
    assert v.allowed is True
    assert v.misses == []


def test_one_miss_blocks_whole_mail():
    v = check_whitelist(["a@corp.com", "b@evil.com"], _policy())
    assert v.allowed is False
    assert v.misses == ["b@evil.com"]


def test_domain_match_is_suffix_safe():
    # evilcorp.com 不能蹭 corp.com 的白名单
    v = check_whitelist(["x@evilcorp.com"], _policy())
    assert v.allowed is False


def test_empty_whitelist_blocks_all():
    v = check_whitelist(["a@corp.com"], PolicyConfig())
    assert v.allowed is False
