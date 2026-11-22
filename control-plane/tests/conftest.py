import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.ratelimit import SlidingWindowLimiter
from app.workers import WorkerRegistry

USAGE = {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12}

STREAM_CHUNKS = [
    b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
    b'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":5,"total_tokens":12}}\n\n',
    b"data: [DONE]\n\n",
]


class ChunkedStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        for chunk in STREAM_CHUNKS:
            yield chunk


@pytest.fixture
def vllm_mode():
    return {"mode": "ok"}


@pytest.fixture
def client(tmp_path, monkeypatch, vllm_mode):
    def handler(request):
        if vllm_mode["mode"] == "down":
            raise httpx.ConnectError("refused", request=request)
        if vllm_mode["mode"] == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if request.url.path == "/health":
            return httpx.Response(200)
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200,
                stream=ChunkedStream(),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "hi"}}], "usage": USAGE}
        )

    fake_vllm = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://vllm"
    )

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    monkeypatch.setattr(main, "limiter", SlidingWindowLimiter(3, 60))
    monkeypatch.setattr(main, "registry", WorkerRegistry())
    monkeypatch.setattr(main, "client", fake_vllm)
    with TestClient(main.app) as test_client:
        yield test_client