"""
WebSearchTool · 搜索互联网并返回摘要结果。

使用 DuckDuckGo Lite HTML（无需 API Key，内网可经代理访问）。
返回 Top-N 结果的标题 + 链接 + 摘要文本，供 LLM 进一步分析。
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote_plus

from .base import Tool, ToolError

_DDG_URL = "https://lite.duckduckgo.com/lite/?q={query}&kl=cn-zh"


class WebSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "在互联网上搜索关键词，返回 Top-N 结果（标题 + URL + 摘要）。"
            "适合查询公开资讯、技术文档、政策文件等。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（支持中英文）",
                    "minLength": 2,
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量（默认 5，最多 10）",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str, max_results: int = 5, **_: Any) -> str:  # noqa: ANN401
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

        url = _DDG_URL.format(query=quote_plus(query))
        try:
            kwargs: dict[str, Any] = {"timeout": 15.0, "follow_redirects": True, "verify": verify}
            if proxy:
                kwargs["proxy"] = proxy
            with httpx.Client(**kwargs) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AIDA-Agent/1.0)",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                })
                resp.raise_for_status()
                html = resp.text
        except Exception as e:  # noqa: BLE001
            return ToolError(f"搜索请求失败：{e}")

        results = _parse_ddg_lite(html, max_results)
        if not results:
            return f"未找到与「{query}」相关的结果。"

        lines = [f"搜索「{query}」的结果：\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**")
            lines.append(f"   {r['url']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
            lines.append("")
        return "\n".join(lines)


def _parse_ddg_lite(html: str, max_results: int) -> list[dict[str, str]]:
    """从 DuckDuckGo Lite HTML 提取搜索结果。"""
    results: list[dict[str, str]] = []

    # 标题 + 链接：<a class="result-link" href="...">TITLE</a>
    link_pat = re.compile(r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
    # 摘要：<td class="result-snippet">...</td>
    snip_pat = re.compile(r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>', re.S | re.I)

    links = link_pat.findall(html)
    snips = snip_pat.findall(html)

    for i, (url, title) in enumerate(links[:max_results]):
        snippet = ""
        if i < len(snips):
            snippet = re.sub(r"<[^>]+>", "", snips[i]).strip()
            snippet = re.sub(r"\s+", " ", snippet)
        results.append({
            "title": re.sub(r"<[^>]+>", "", title).strip(),
            "url": url,
            "snippet": snippet[:200],
        })
    return results
