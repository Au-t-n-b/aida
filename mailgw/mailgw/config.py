"""配置加载：config.yaml（非敏感）+ .env（敏感信息）。见 spec §8。"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class SmtpConfig:
    host: str
    port: int
    ssl: bool
    username: str
    from_addr: str
    password: str
    display_name: str = ""


@dataclass
class Pop3Config:
    host: str
    port: int
    ssl: bool
    username: str
    password: str
    poll_interval: int = 0


@dataclass
class PolicyConfig:
    whitelist_domains: list[str] = field(default_factory=list)
    whitelist_addresses: list[str] = field(default_factory=list)
    hourly_limit: int = 20
    daily_limit: int = 100
    max_attachment_mb: int = 25
    max_recipients: int = 20


@dataclass
class AppConfig:
    smtp: SmtpConfig
    pop3: Pop3Config
    policy: PolicyConfig
    data_dir: Path
    tokens: dict[str, str]  # caller 名（小写）-> token
    admin_password: str


def load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig:
    load_dotenv(env_path, override=True)
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))

    tokens = {
        key.removeprefix("MAILGW_TOKEN_").lower(): value
        for key, value in os.environ.items()
        if key.startswith("MAILGW_TOKEN_") and value
    }
    return AppConfig(
        smtp=SmtpConfig(password=os.environ["MAILGW_SMTP_PASSWORD"], **raw["smtp"]),
        pop3=Pop3Config(password=os.environ["MAILGW_POP3_PASSWORD"], **raw["pop3"]),
        policy=PolicyConfig(**raw.get("policy", {})),
        data_dir=Path(raw.get("data_dir", "./data")),
        tokens=tokens,
        admin_password=os.environ["MAILGW_ADMIN_PASSWORD"],
    )
