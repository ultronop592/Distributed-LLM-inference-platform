import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .auth import ApiError, generate_key, hash_key, require_admin, require_api_key

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

client = httpx.AsyncClient(
    base_url=VLLM_BASE_URL,
    timeout=httpx.Timeout(120.0, connect=5.0),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield
    await client.aclose()


app = FastAPI(title="CloudScale Gateway", lifespan=lifespan)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        {"error": {"message": exc.message, "type": exc.error_type}},
        status_code=exc.status_code,
    )


class KeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


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


@app.post("/api/keys", dependencies=[Depends(require_admin)])
async def create_key(payload: KeyCreate):
    raw_key = generate_key()
    key_id = db.insert_key(payload.name, hash_key(raw_key), raw_key[:8])
    return {"id": key_id, "name": payload.name, "key": raw_key}


@app.get("/api/keys", dependencies=[Depends(require_admin)])
async def list_keys():
    return {"keys": db.list_keys()}


@app.delete("/api/keys/{key_id}", dependencies=[Depends(require_admin)])
async def revoke_key(key_id: int):
    if not db.revoke_key(key_id):
        raise ApiError(404, "Key not found or already revoked", "not_found")
    return {"id": key_id, "revoked": True}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, api_key: dict = Depends(require_api_key)):
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