import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.websockets import WebSocketDisconnect

ADMIN = {"Authorization": "Bearer test-admin"}
WORKER_AUTH = {"Authorization": "Bearer test-worker"}
CHAT = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
USAGE = {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12}

STREAM_CHUNKS = [
    'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
    'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":5,"total_tokens":12}}\n\n',
    "data: [DONE]\n\n",
]


@pytest.fixture(autouse=True)
def worker_token(monkeypatch):
    monkeypatch.setenv("WORKER_TOKEN", "test-worker")


def make_key(client):
    return client.post("/api/keys", headers=ADMIN, json={"name": "t"}).json()["key"]


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def say_hello(ws, models=("m",), max_concurrency=2):
    ws.send_json(
        {
            "type": "hello",
            "worker_name": "w1",
            "models": list(models),
            "max_concurrency": max_concurrency,
            "agent_version": "test",
        }
    )
    return ws.receive_json()


def worker_names(client):
    return [w["name"] for w in client.get("/api/workers", headers=ADMIN).json()["workers"]]


def test_bad_worker_token_is_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/workers/connect", headers={"Authorization": "Bearer wrong"}
        ):
            pass


def test_worker_registers_and_is_removed_on_disconnect(client):
    with client.websocket_connect("/workers/connect", headers=WORKER_AUTH) as ws:
        welcome = say_hello(ws)
        assert welcome["type"] == "welcome"
        assert welcome["heartbeat_interval"] == 5
        assert worker_names(client) == ["w1"]
    deadline = time.time() + 3
    while worker_names(client) and time.time() < deadline:
        time.sleep(0.05)
    assert worker_names(client) == []


def test_request_is_routed_through_worker(client, vllm_mode):
    vllm_mode["mode"] = "down"
    key = make_key(client)
    with client.websocket_connect("/workers/connect", headers=WORKER_AUTH) as ws:
        say_hello(ws)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                client.post, "/v1/chat/completions", headers=auth(key), json=CHAT
            )
            request = ws.receive_json()
            assert request["type"] == "request"
            request_id = request["request_id"]
            ws.send_json({"type": "response_start", "request_id": request_id, "status": 200})
            ws.send_json(
                {
                    "type": "response_chunk",
                    "request_id": request_id,
                    "data": json.dumps(
                        {"choices": [{"message": {"content": "hi"}}], "usage": USAGE}
                    ),
                }
            )
            ws.send_json({"type": "response_end", "request_id": request_id})
            response = future.result(timeout=5)
    assert response.status_code == 200
    row = client.get("/api/usage", headers=ADMIN).json()["usage"][0]
    assert row["prompt_tokens"] == 7
    assert row["completion_tokens"] == 5


def test_stream_is_routed_through_worker_and_usage_counted(client, vllm_mode):
    vllm_mode["mode"] = "down"
    key = make_key(client)
    with client.websocket_connect("/workers/connect", headers=WORKER_AUTH) as ws:
        say_hello(ws)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                client.post,
                "/v1/chat/completions",
                headers=auth(key),
                json={**CHAT, "stream": True},
            )
            request = ws.receive_json()
            assert request["body"]["stream_options"]["include_usage"] is True
            request_id = request["request_id"]
            ws.send_json({"type": "response_start", "request_id": request_id, "status": 200})
            for chunk in STREAM_CHUNKS:
                ws.send_json({"type": "response_chunk", "request_id": request_id, "data": chunk})
            ws.send_json({"type": "response_end", "request_id": request_id})
            response = future.result(timeout=5)
    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    row = client.get("/api/usage", headers=ADMIN).json()["usage"][0]
    assert row["prompt_tokens"] == 7
    assert row["completion_tokens"] == 5


def test_worker_without_requested_model_is_skipped(client):
    key = make_key(client)
    with client.websocket_connect("/workers/connect", headers=WORKER_AUTH) as ws:
        say_hello(ws, models=("other",))
        response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 200


def test_worker_disconnect_mid_request_is_502(client):
    key = make_key(client)
    pool = ThreadPoolExecutor(max_workers=1)
    with client.websocket_connect("/workers/connect", headers=WORKER_AUTH) as ws:
        say_hello(ws)
        future = pool.submit(client.post, "/v1/chat/completions", headers=auth(key), json=CHAT)
        ws.receive_json()
    response = future.result(timeout=5)
    pool.shutdown()
    assert response.status_code == 502


def test_no_worker_and_no_fallback_is_503(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "DIRECT_FALLBACK", False)
    key = make_key(client)
    response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 503