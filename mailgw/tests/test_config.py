# tests/test_config.py
from pathlib import Path

from mailgw.config import load_config

CONFIG_YAML = """\
smtp:
  host: smtp.test.com
  port: 465
  ssl: true
  username: bot@test.com
  from_addr: bot@test.com
  display_name: 测试机器人
pop3:
  host: pop3.test.com
  port: 995
  ssl: true
  username: bot@test.com
  poll_interval: 0
policy:
  whitelist_domains: ["test.com"]
  whitelist_addresses: ["vip@other.com"]
  hourly_limit: 5
  daily_limit: 10
data_dir: ./data
"""

ENV = """\
MAILGW_SMTP_PASSWORD=smtp-pass
MAILGW_POP3_PASSWORD=pop3-pass
MAILGW_ADMIN_PASSWORD=admin-pass
MAILGW_TOKEN_AIDA=tok-aida
MAILGW_TOKEN_TESTER=tok-tester
"""


def test_load_config(tmp_path: Path, monkeypatch):
    # 清掉宿主机可能存在的同名环境变量，保证可重复
    for key in list(__import__("os").environ):
        if key.startswith("MAILGW_"):
            monkeypatch.delenv(key, raising=False)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(CONFIG_YAML, encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(ENV, encoding="utf-8")

    cfg = load_config(str(cfg_file), str(env_file))

    assert cfg.smtp.host == "smtp.test.com"
    assert cfg.smtp.password == "smtp-pass"
    assert cfg.smtp.display_name == "测试机器人"
    assert cfg.pop3.password == "pop3-pass"
    assert cfg.policy.hourly_limit == 5
    assert cfg.policy.max_attachment_mb == 25  # 未配置项取默认值
    assert cfg.tokens == {"aida": "tok-aida", "tester": "tok-tester"}
    assert cfg.admin_password == "admin-pass"
    assert cfg.data_dir == Path("./data")
