"""
WebFetchTool · 抓取指定 URL 的网页正文（纯文本）。

使用 httpx 同步客户端（已是 llm.py 依赖，无需新增包）。
内网代理环境下自动读取 HTTP_PROXY/HTTPS_PROXY 环境变量。
"""
from __future__ import annotations

import os
import re
from typing import Any

from .base import Tool, ToolError

_MAX_CHARS = 8_000  # 截断防止 token 溢出


class WebFetchTool(Tool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "抓取一个 URL 的网页内容并返回纯文本（自动去除 HTML 标签）。"
            "适合获取文档、公告、产品页面等网络内容。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的完整 URL（包含 http:// 或 https://）",
                    "minLength": 7,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "返回文本最大字符数（默认 8000）",
                    "minimum": 100,
                    "maximum": 30_000,
                },
            },
            "required": ["url"],
        }

    def execute(self, url: str, max_chars: int = _MAX_CHARS, **_: Any) -> str:  # noqa: ANN401
        try:
            import httpx
        except ImportError:
            return ToolError("httpx 未安装，请 pip install httpx")

        proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("http_proxy")
        )
        verify = os.environ.get("ZHIPU_SSL_VERIFY", "").strip().lower() not in ("0", "false", "no")

        try:
            kwargs: dict[str, Any] = {"timeout": 20.0, "follow_redirects": True, "verify": verify}
            if proxy:
                kwargs["proxy"] = proxy
            with httpx.Client(**kwargs) as client:
                resp = client.get(url, headers={"User-Agent": "AIDA-Agent/1.0"})
                resp.raise_for_status()
                raw = resp.text
        except httpx.HTTPStatusError as e:
            return ToolError(f"HTTP {e.response.status_code} · {url}")
        except Exception as e:  # noqa: BLE001
            return ToolError(f"抓取失败：{e}")

        text = _strip_html(raw)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[内容已截断，共 {len(text)} 字符]"
        return text or ToolError("页面内容为空")


def _strip_html(html: str) -> str:
    """粗粒度 HTML → 纯文本（不引入 BeautifulSoup 依赖）。"""
    # 去 <script> / <style> 块
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # 换行类标签
    html = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.I)
    # 其余标签
    html = re.sub(r"<[^>]+>", "", html)
    # HTML 实体
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    # 压缩连续空白行
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()
