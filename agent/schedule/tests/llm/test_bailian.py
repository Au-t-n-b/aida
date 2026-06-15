from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Iterable

import httpx
import pytest

SCHEDULE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent.schedule.llm.bailian import BailianChatClient, LlmCallError  # noqa: E402


def test_complete_defaults_to_stream_and_accumulates_chunks():
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return _stream_response([_sse("hello "), _sse("world"), "data: [DONE]\n\n"])

    client = _client(httpx.MockTransport(handler))

    content = client.complete([{"role": "user", "content": "hi"}])

    assert content == "hello world"
    assert payloads[0]["stream"] is True
    assert payloads[0]["model"] == "qwen3.7-max"


def test_complete_keeps_non_stream_option_available():
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "batch result"}}]},
        )

    client = _client(httpx.MockTransport(handler))

    content = client.complete([{"role": "user", "content": "hi"}], stream=False)

    assert content == "batch result"
    assert payloads[0]["stream"] is False


def test_reasoning_delta_counts_as_activity_but_is_not_accumulated():
    def handler(request: httpx.Request) -> httpx.Response:
        return _stream_response([_sse_delta({"reasoning_content": "先思考"}), _sse("final"), "data: [DONE]\n\n"])

    client = _client(httpx.MockTransport(handler), liveness_timeout_seconds=0.5)

    assert client.complete([{"role": "user", "content": "hi"}]) == "final"


def test_empty_choices_tail_frame_is_ignored():
    def handler(request: httpx.Request) -> httpx.Response:
        return _stream_response([_sse("final"), "data: {\"choices\":[]}\n\n", "data: [DONE]\n\n"])

    client = _client(httpx.MockTransport(handler))

    assert client.complete([{"role": "user", "content": "hi"}]) == "final"


def test_liveness_timeout_retries_and_then_succeeds():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _stream_response([_sse("too late")], delay_seconds=0.03)
        return _stream_response([_sse("ok"), "data: [DONE]\n\n"])

    client = _client(
        httpx.MockTransport(handler),
        liveness_timeout_seconds=0.01,
        max_retries=1,
    )

    assert client.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert calls == 2


def test_connection_error_retries_and_then_succeeds():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("network down", request=request)
        return _stream_response([_sse("recovered"), "data: [DONE]\n\n"])

    client = _client(httpx.MockTransport(handler), max_retries=1)

    assert client.complete([{"role": "user", "content": "hi"}]) == "recovered"
    assert calls == 2


def test_retry_exhaustion_raises_loud_call_error():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _stream_response(["data: [DONE]\n\n"])

    client = _client(httpx.MockTransport(handler), max_retries=2)

    with pytest.raises(LlmCallError, match="空文本"):
        client.complete([{"role": "user", "content": "hi"}])
    assert calls == 3


def test_client_error_is_not_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    client = _client(httpx.MockTransport(handler), max_retries=2)

    with pytest.raises(LlmCallError, match="401"):
        client.complete([{"role": "user", "content": "hi"}])
    assert calls == 1


def _client(
    transport: httpx.BaseTransport,
    *,
    liveness_timeout_seconds: float = 1.0,
    max_retries: int = 0,
) -> BailianChatClient:
    return BailianChatClient(
        api_key="test-key",
        timeout_seconds=5.0,
        liveness_timeout_seconds=liveness_timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=0,
        transport=transport,
    )


def _sse(content: str) -> str:
    return _sse_delta({"content": content})


def _sse_delta(delta: dict[str, str]) -> str:
    return f"data: {json.dumps({'choices': [{'delta': delta}]})}\n\n"


def _stream_response(chunks: Iterable[str], *, delay_seconds: float = 0) -> httpx.Response:
    return httpx.Response(200, stream=TextStream(chunks, delay_seconds=delay_seconds))


class TextStream(httpx.SyncByteStream):
    def __init__(self, chunks: Iterable[str], *, delay_seconds: float = 0):
        self._chunks = list(chunks)
        self._delay_seconds = delay_seconds

    def __iter__(self):
        for chunk in self._chunks:
            if self._delay_seconds:
                time.sleep(self._delay_seconds)
            yield chunk.encode("utf-8")
