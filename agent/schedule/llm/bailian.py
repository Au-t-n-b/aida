from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from dotenv import load_dotenv

DEFAULT_BAILIAN_MODEL = "qwen3.7-max"
DEFAULT_BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
# 收口实测（2026-06-14 调度台真打 qwen3.7-max）：报告总结这类结构化生成单次约 43s。
# 总超时继续容忍长生成；活性超时只判断模型是否及时返回任意增量。
DEFAULT_TIMEOUT_SECONDS = 90.0
DEFAULT_LIVENESS_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5

ChatMessage = dict[str, str]


class LlmConfigurationError(RuntimeError):
    """模型调用配置不可用。"""


class LlmTimeoutError(RuntimeError):
    """模型调用超时。"""


class LlmCallError(RuntimeError):
    """模型调用失败或响应不可用。"""


class ReportSummaryClient(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str = DEFAULT_BAILIAN_MODEL,
        stream: bool = True,
    ) -> str:
        """Return assistant text for the given chat messages."""


@dataclass(frozen=True)
class BailianChatClient:
    api_key: str
    base_url: str = DEFAULT_BAILIAN_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    liveness_timeout_seconds: float = DEFAULT_LIVENESS_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS
    transport: httpx.BaseTransport | None = None

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "BailianChatClient":
        load_dotenv(env_path or DEFAULT_ENV_PATH, override=False)
        api_key = os.environ.get("BAILIAN_API_KEY", "").strip()
        if not api_key:
            raise LlmConfigurationError("BAILIAN_API_KEY 未配置。")
        base_url = os.environ.get("BAILIAN_BASE_URL", DEFAULT_BAILIAN_BASE_URL).strip() or DEFAULT_BAILIAN_BASE_URL
        timeout_seconds = _env_float("BAILIAN_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, minimum=1.0)
        liveness_timeout_seconds = _env_float(
            "BAILIAN_LIVENESS_TIMEOUT_SECONDS",
            DEFAULT_LIVENESS_TIMEOUT_SECONDS,
            minimum=0.1,
        )
        max_retries = _env_int("BAILIAN_MAX_RETRIES", DEFAULT_MAX_RETRIES, minimum=0)
        retry_backoff_seconds = _env_float(
            "BAILIAN_RETRY_BACKOFF_SECONDS",
            DEFAULT_RETRY_BACKOFF_SECONDS,
            minimum=0.0,
        )
        return cls(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            liveness_timeout_seconds=liveness_timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str = DEFAULT_BAILIAN_MODEL,
        stream: bool = True,
    ) -> str:
        attempts = self.max_retries + 1
        last_retryable_error: LlmCallError | LlmTimeoutError | None = None
        for attempt_index in range(attempts):
            try:
                return self._complete_once(messages, model=model, stream=stream)
            except (_RetryableLlmCallError, _RetryableLlmTimeoutError) as exc:
                last_retryable_error = exc
                if attempt_index >= self.max_retries:
                    break
                self._sleep_before_retry(attempt_index)

        if isinstance(last_retryable_error, LlmTimeoutError):
            raise LlmTimeoutError(str(last_retryable_error)) from last_retryable_error
        if isinstance(last_retryable_error, LlmCallError):
            raise LlmCallError(str(last_retryable_error)) from last_retryable_error
        raise LlmCallError("模型服务响应不可用。")

    def _complete_once(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        stream: bool,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1200,
            "temperature": 0.2,
            "stream": stream,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if stream:
            return self._complete_stream(url, payload, headers)
        return self._complete_json(url, payload, headers)

    def _complete_json(self, url: str, payload: dict[str, object], headers: dict[str, str]) -> str:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise _RetryableLlmTimeoutError("模型调用超时。") from exc
        except httpx.HTTPStatusError as exc:
            detail = _response_detail(exc.response)
            if exc.response.status_code >= 500:
                raise _RetryableLlmCallError(f"模型服务返回 {exc.response.status_code}: {detail}") from exc
            raise LlmCallError(f"模型服务返回 {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise _RetryableLlmCallError(f"模型服务不可达: {exc}") from exc
        except ValueError as exc:
            raise LlmCallError("模型服务响应不是合法 JSON。") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmCallError("模型服务响应缺少 choices[0].message.content。") from exc
        if not isinstance(content, str) or not content.strip():
            raise _RetryableLlmCallError("模型服务返回空文本。")
        return content

    def _complete_stream(self, url: str, payload: dict[str, object], headers: dict[str, str]) -> str:
        timeout = httpx.Timeout(
            self.timeout_seconds,
            read=min(self.liveness_timeout_seconds, self.timeout_seconds),
        )
        started_at = time.monotonic()
        first_activity_at: float | None = None
        chunks: list[str] = []

        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        now = time.monotonic()
                        if now - started_at > self.timeout_seconds:
                            raise LlmTimeoutError("模型调用总超时。")

                        content, is_activity = _stream_content_from_line(line)
                        if content is None:
                            if first_activity_at is None and now - started_at > self.liveness_timeout_seconds:
                                raise _RetryableLlmTimeoutError("模型调用无反馈，活性超时。")
                            continue
                        if first_activity_at is None:
                            if now - started_at > self.liveness_timeout_seconds:
                                raise _RetryableLlmTimeoutError("模型调用无反馈，活性超时。")
                            if is_activity:
                                first_activity_at = now
                        if content == "":
                            continue
                        chunks.append(content)
        except httpx.TimeoutException as exc:
            if first_activity_at is None:
                raise _RetryableLlmTimeoutError("模型调用无反馈，活性超时。") from exc
            raise _RetryableLlmTimeoutError("模型流式响应中断，活性超时。") from exc
        except httpx.HTTPStatusError as exc:
            detail = _response_detail(exc.response)
            if exc.response.status_code >= 500:
                raise _RetryableLlmCallError(f"模型服务返回 {exc.response.status_code}: {detail}") from exc
            raise LlmCallError(f"模型服务返回 {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise _RetryableLlmCallError(f"模型服务不可达: {exc}") from exc

        content = "".join(chunks)
        if not content.strip():
            raise _RetryableLlmCallError("模型服务返回空文本。")
        return content

    def _sleep_before_retry(self, attempt_index: int) -> None:
        delay = self.retry_backoff_seconds * (2**attempt_index)
        if delay > 0:
            time.sleep(delay)


def _response_detail(response: httpx.Response) -> str:
    try:
        if not response.is_closed:
            response.read()
    except httpx.HTTPError:
        return ""
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    return str(data)[:300]


def _stream_content_from_line(line: str) -> tuple[str | None, bool]:
    text = line.strip()
    if not text or text.startswith(":"):
        return None, False
    if text.startswith("data:"):
        text = text[5:].strip()
    if text == "[DONE]":
        return None, False
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LlmCallError("模型服务流式响应不是合法 JSON。") from exc
    choices = data.get("choices")
    if choices == []:
        return None, False
    if not isinstance(choices, list):
        raise LlmCallError("模型服务流式响应 choices 不是数组。")
    try:
        delta = choices[0].get("delta", {})
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LlmCallError("模型服务流式响应缺少 choices[0].delta。") from exc
    if not isinstance(delta, dict):
        raise LlmCallError("模型服务流式响应 delta 不是对象。")
    content = delta.get("content", "")
    reasoning_content = delta.get("reasoning_content", "")
    is_activity = bool(content) or bool(reasoning_content)
    if content is None:
        return "", is_activity
    if not isinstance(content, str):
        raise LlmCallError("模型服务流式响应 content 不是文本。")
    return content, is_activity


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return max(minimum, float(raw))
    except ValueError:
        return default


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


class _RetryableLlmTimeoutError(LlmTimeoutError):
    pass


class _RetryableLlmCallError(LlmCallError):
    pass
