"""启动入口：python -m mailgw [--config config.yaml] [--env .env] [--host 127.0.0.1] [--port 8025]"""
import argparse

import uvicorn

from mailgw.app import build_app
from mailgw.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="mailgw", description="AIDA 邮件网关")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--env", default=".env", help="敏感信息 .env 路径")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8025)
    args = parser.parse_args()
    app = build_app(load_config(args.config, args.env))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
