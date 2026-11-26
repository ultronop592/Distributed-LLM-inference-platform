ADMIN = {"Authorization": "Bearer test-admin"}
CHAT = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}


def make_key(client):
    response = client.post("/api/keys", headers=ADMIN, json={"name": "t"})
    return response.json()["key"]


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def usage_row(client):
    return client.get("/api/usage", headers=ADMIN).json()["usage"][0]


def test_missing_key_is_401(client):
    assert client.post("/v1/chat/completions", json=CHAT).status_code == 401


def test_invalid_key_is_401(client):
    response = client.post("/v1/chat/completions", headers=auth("csk_nope"), json=CHAT)
    assert response.status_code == 401


def test_admin_endpoints_need_admin_token(client):
    assert client.get("/api/keys").status_code == 401
    assert client.get("/api/keys", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/keys", headers=ADMIN).status_code == 200


def test_valid_key_gets_answer_and_usage_is_counted(client):
    key = make_key(client)
    response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 200
    row = usage_row(client)
    assert row["requests"] == 1
    assert row["prompt_tokens"] == 7
    assert row["completion_tokens"] == 5


def test_streaming_passes_through_and_counts_usage(client):
    key = make_key(client)
    response = client.post(
        "/v1/chat/completions", headers=auth(key), json={**CHAT, "stream": True}
    )
    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    row = usage_row(client)
    assert row["prompt_tokens"] == 7
    assert row["completion_tokens"] == 5


def test_revoked_key_is_401(client):
    key = make_key(client)
    client.delete("/api/keys/1", headers=ADMIN)
    response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 401


def test_rate_limit_returns_429_with_retry_after(client):
    key = make_key(client)
    codes = [
        client.post("/v1/chat/completions", headers=auth(key), json=CHAT).status_code
        for _ in range(5)
    ]
    assert codes == [200, 200, 200, 429, 429]
    blocked = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert int(blocked.headers["retry-after"]) >= 1


def test_oversized_body_is_413(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "MAX_BODY_BYTES", 100)
    key = make_key(client)
    big = {"model": "m", "messages": [{"role": "user", "content": "a" * 500}]}
    response = client.post("/v1/chat/completions", headers=auth(key), json=big)
    assert response.status_code == 413


def test_worker_down_is_503(client, vllm_mode):
    key = make_key(client)
    vllm_mode["mode"] = "down"
    response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 503


def test_worker_timeout_is_504(client, vllm_mode):
    key = make_key(client)
    vllm_mode["mode"] = "timeout"
    response = client.post("/v1/chat/completions", headers=auth(key), json=CHAT)
    assert response.status_code == 504


def test_healthz_reports_worker_state(client, vllm_mode):
    assert client.get("/healthz").json() == {"status": "ok"}
    vllm_mode["mode"] = "down"
    assert client.get("/healthz").status_code == 503


def test_livez_is_ok_even_when_worker_is_down(client, vllm_mode):
    vllm_mode["mode"] = "down"
    assert client.get("/livez").json() == {"status": "alive"}
