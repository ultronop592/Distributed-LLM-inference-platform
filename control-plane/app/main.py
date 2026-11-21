import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .auth import ApiError, generate_key, hash_key, require_admin, require_api_key
from .ratelimit import SlidingWindowLimiter

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "65536"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))

client = httpx.AsyncClient(
    base_url=VLLM_BASE_URL,
    timeout=httpx.Timeout(120.0, connect=5.0),
)
limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MIN, 60)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield
    await client.aclose()


app = FastAPI(title="CloudScale Gateway", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s key_id=%s ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        getattr(request.state, "key_id", None),
        elapsed_ms,
    )
    return response


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


def worker_failure(exc: httpx.HTTPError) -> JSONResponse:
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return JSONResponse(
            {"error": {"message": "Worker timed out", "type": "gateway_timeout"}},
            status_code=504,
        )
    return no_worker()


async def read_body(request: Request) -> dict:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise ApiError(413, "Request body too large", "request_too_large")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise ApiError(413, "Request body too large", "request_too_large")
    try:
        body = json.loads(raw)
    except ValueError:
        raise ApiError(400, "Body must be valid JSON", "invalid_request")
    if not isinstance(body, dict):
        raise ApiError(400, "Body must be a JSON object", "invalid_request")
    return body


def parse_usage(line: bytes):
    if not line.startswith(b"data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == b"[DONE]":
        return None
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    usage = data.get("usage") if isinstance(data, dict) else None
    return usage if isinstance(usage, dict) else None


def store_usage(key_id: int, usage):
    if not usage:
        return
    db.record_usage(
        key_id,
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
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


@app.get("/api/usage", dependencies=[Depends(require_admin)])
async def usage():
    return {"usage": db.usage_summary()}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, api_key: dict = Depends(require_api_key)):
    request.state.key_id = api_key["id"]

    allowed, retry_after = limiter.check(api_key["id"])
    if not allowed:
        return JSONResponse(
            {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    body = await read_body(request)

    if not body.get("stream"):
        try:
            upstream = await client.post("/v1/chat/completions", json=body)
        except httpx.HTTPError as exc:
            return worker_failure(exc)
        payload = upstream.json()
        if upstream.status_code == 200 and isinstance(payload, dict):
            store_usage(api_key["id"], payload.get("usage"))
        return JSONResponse(payload, status_code=upstream.status_code)

    stream_options = body.get("stream_options")
    if not isinstance(stream_options, dict):
        stream_options = {}
    stream_options["include_usage"] = True
    body["stream_options"] = stream_options

    try:
        upstream_request = client.build_request("POST", "/v1/chat/completions", json=body)
        upstream = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        return worker_failure(exc)

    if upstream.status_code != 200:
        error_payload = await upstream.aread()
        await upstream.aclose()
        return JSONResponse(
            {"error": {"message": error_payload.decode(errors="replace"), "type": "upstream_error"}},
            status_code=upstream.status_code,
        )

    async def relay():
        buffer = b""
        usage = None
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
                buffer += chunk
                *lines, buffer = buffer.split(b"\n")
                for line in lines:
                    found = parse_usage(line)
                    if found:
                        usage = found
        finally:
            store_usage(api_key["id"], usage)
            await upstream.aclose()

    return StreamingResponse(relay(), media_type="text/event-stream")