#!/usr/bin/env python3
"""Serve a Vite/React build with index.html fallback for client-side routes."""
from __future__ import annotations

import argparse
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


class SPARequestHandler(SimpleHTTPRequestHandler):
    """Static files when present; otherwise index.html for SPA deep links / refresh."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def _resolved_path(self) -> Path:
        url_path = unquote(urlparse(self.path).path)
        rel = url_path.lstrip("/")
        base = Path(self.directory or os.getcwd())
        return (base / rel).resolve()

    def _should_fallback_to_index(self) -> bool:
        target = self._resolved_path()
        if target.is_file():
            return False
        if target.is_dir() and (target / "index.html").is_file():
            return False
        url_path = urlparse(self.path).path
        basename = os.path.basename(url_path.rstrip("/"))
        # Missing asset files (e.g. /assets/foo.js) should 404, not SPA shell.
        if "." in basename:
            return False
        return True

    def do_GET(self) -> None:
        if self._should_fallback_to_index():
            self.path = "/index.html"
        super().do_GET()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SPA-aware static file server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", required=True, help="Static root (e.g. frontend/dist)")
    args = parser.parse_args(argv)

    dist = Path(args.directory).resolve()
    if not dist.is_dir():
        print(f"[spa_static_server] directory not found: {dist}", file=sys.stderr)
        return 1
    index = dist / "index.html"
    if not index.is_file():
        print(f"[spa_static_server] index.html not found in {dist}", file=sys.stderr)
        return 1

    handler = lambda *h_args, **h_kwargs: SPARequestHandler(  # noqa: E731
        *h_args,
        directory=str(dist),
        **h_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[spa_static_server] {dist} -> http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[spa_static_server] stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
