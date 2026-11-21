import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

app = FastAPI(title="CloudScale Gateway")
client = httpx.AsyncClient(
    base_url=VLLM_BASE_URL,
    timeout=httpx.Timeout(120.0, connect=5.0),
)


def no_worker() -> JSONResponse:
    return JSONResponse(
        {"error": {"message": "No healthy worker online", "type": "service_unavailable"}},
        status_code=503,
    )


@app.get("/healthz")
async def healthz():
    try:
        response = await client.get("/health")
    except httpx.HTTPError:
        return JSONResponse({"status": "no_worker"}, status_code=503)
    status = "ok" if response.status_code == 200 else "degraded"
    return {"status": status}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    if not body.get("stream"):
        try:
            upstream = await client.post("/v1/chat/completions", json=body)
        except httpx.HTTPError:
            return no_worker()
        return JSONResponse(upstream.json(), status_code=upstream.status_code)

    try:
        upstream_request = client.build_request("POST", "/v1/chat/completions", json=body)
        upstream = await client.send(upstream_request, stream=True)
    except httpx.HTTPError:
        return no_worker()

    if upstream.status_code != 200:
        payload = await upstream.aread()
        await upstream.aclose()
        return JSONResponse(
            {"error": {"message": payload.decode(errors="replace"), "type": "upstream_error"}},
            status_code=upstream.status_code,
        )

    async def relay():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(relay(), media_type="text/event-stream")