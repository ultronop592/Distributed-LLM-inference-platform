import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import aclosing, asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .auth import ApiError, extract_bearer, generate_key, hash_key, require_admin, require_api_key
from .ratelimit import SlidingWindowLimiter
from .workers import Worker, WorkerRegistry

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "65536"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))
DIRECT_FALLBACK = os.getenv("DIRECT_FALLBACK", "true").lower() == "true"
HEARTBEAT_INTERVAL = 5
HEARTBEAT_TIMEOUT = 15
WORKER_START_TIMEOUT = float(os.getenv("WORKER_START_TIMEOUT", "60"))
WORKER_CHUNK_TIMEOUT = float(os.getenv("WORKER_CHUNK_TIMEOUT", "60"))

client = httpx.AsyncClient(
    base_url=VLLM_BASE_URL,
    timeout=httpx.Timeout(120.0, connect=5.0),
)
limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MIN, 60)
registry = WorkerRegistry()

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


def gateway_timeout() -> JSONResponse:
    return JSONResponse(
        {"error": {"message": "Worker timed out", "type": "gateway_timeout"}},
        status_code=504,
    )


def bad_gateway(message: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "bad_gateway"}},
        status_code=502,
    )


def worker_failure(exc: httpx.HTTPError) -> JSONResponse:
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return gateway_timeout()
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


async def metered(source, key_id: int):
    buffer = b""
    usage = None
    try:
        async with aclosing(source) as chunks:
            async for chunk in chunks:
                yield chunk
                buffer += chunk
                *lines, buffer = buffer.split(b"\n")
                for line in lines:
                    found = parse_usage(line)
                    if found:
                        usage = found
    finally:
        store_usage(key_id, usage)


async def upstream_chunks(upstream):
    try:
        async for chunk in upstream.aiter_raw():
            yield chunk
    finally:
        await upstream.aclose()


async def worker_stream(worker: Worker, request_id: str, queue: asyncio.Queue):
    completed = False
    try:
        while True:
            message = await asyncio.wait_for(queue.get(), timeout=WORKER_CHUNK_TIMEOUT)
            kind = message.get("type")
            if kind == "response_chunk":
                yield str(message.get("data", "")).encode()
            else:
                completed = kind == "response_end"
                return
    except asyncio.TimeoutError:
        return
    finally:
        if completed:
            worker.finish(request_id)
        else:
            await worker.cancel(request_id)


async def collect(worker: Worker, request_id: str, queue: asyncio.Queue):
    parts = []
    try:
        while True:
            message = await asyncio.wait_for(queue.get(), timeout=WORKER_CHUNK_TIMEOUT)
            kind = message.get("type")
            if kind == "response_chunk":
                parts.append(str(message.get("data", "")))
            elif kind == "response_end":
                return "".join(parts), None
            else:
                return None, str(message.get("message", "Worker failed"))
    except asyncio.TimeoutError:
        await worker.cancel(request_id)
        return None, "timeout"
    finally:
        worker.finish(request_id)


async def via_worker(worker: Worker, body: dict, key_id: int):
    stream = bool(body.get("stream"))
    try:
        request_id, queue = await worker.start_request("/v1/chat/completions", body)
    except Exception:
        return no_worker()

    try:
        first = await asyncio.wait_for(queue.get(), timeout=WORKER_START_TIMEOUT)
    except asyncio.TimeoutError:
        await worker.cancel(request_id)
        return gateway_timeout()

    if first.get("type") != "response_start":
        worker.finish(request_id)
        return bad_gateway(str(first.get("message", "Worker failed")))

    status = first.get("status")
    if not isinstance(status, int):
        status = 502

    if stream and status == 200:
        return StreamingResponse(
            metered(worker_stream(worker, request_id, queue), key_id),
            media_type="text/event-stream",
        )

    text, error = await collect(worker, request_id, queue)
    if error is not None:
        return gateway_timeout() if error == "timeout" else bad_gateway(error)
    try:
        payload = json.loads(text)
    except ValueError:
        return bad_gateway("Worker returned invalid JSON")
    if status == 200 and isinstance(payload, dict):
        store_usage(key_id, payload.get("usage"))
    return JSONResponse(payload, status_code=status)


async def via_direct(body: dict, key_id: int):
    if not body.get("stream"):
        try:
            upstream = await client.post("/v1/chat/completions", json=body)
        except httpx.HTTPError as exc:
            return worker_failure(exc)
        payload = upstream.json()
        if upstream.status_code == 200 and isinstance(payload, dict):
            store_usage(key_id, payload.get("usage"))
        return JSONResponse(payload, status_code=upstream.status_code)

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

    return StreamingResponse(
        metered(upstream_chunks(upstream), key_id),
        media_type="text/event-stream",
    )


def parse_hello(hello, websocket: WebSocket):
    if not isinstance(hello, dict) or hello.get("type") != "hello":
        return None
    raw_models = hello.get("models")
    models = [m for m in raw_models if isinstance(m, str)] if isinstance(raw_models, list) else []
    concurrency = hello.get("max_concurrency")
    if not isinstance(concurrency, int) or isinstance(concurrency, bool):
        concurrency = 4
    concurrency = max(1, min(64, concurrency))
    name = str(hello.get("worker_name", "worker"))[:64]
    return Worker(name, models, concurrency, websocket)


@app.get("/healthz")
async def healthz():
    if registry.workers:
        return {"status": "ok"}
    if not DIRECT_FALLBACK:
        return JSONResponse({"status": "no_worker"}, status_code=503)
    try:
        response = await client.get("/health")
    except httpx.HTTPError:
        return JSONResponse({"status": "no_worker"}, status_code=503)
    status = "ok" if response.status_code == 200 else "degraded"
    return {"status": status}


@app.websocket("/workers/connect")
async def workers_connect(websocket: WebSocket):
    expected = os.getenv("WORKER_TOKEN")
    token = extract_bearer(websocket.headers.get("authorization"))
    if not expected or token is None or not hmac.compare_digest(token.encode(), expected.encode()):
        await websocket.close(code=1008)
        return
    await websocket.accept()

    try:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, RuntimeError):
        return
    worker = parse_hello(hello, websocket)
    if worker is None:
        await websocket.close(code=1008)
        return

    registry.add(worker)
    logger.info("worker_connected id=%s name=%s models=%s", worker.id, worker.name, worker.models)
    try:
        await worker.send(
            {"type": "welcome", "worker_id": worker.id, "heartbeat_interval": HEARTBEAT_INTERVAL}
        )
        while True:
            message = await asyncio.wait_for(websocket.receive_json(), timeout=HEARTBEAT_TIMEOUT)
            worker.handle(message)
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, RuntimeError):
        pass
    finally:
        registry.remove(worker.id)
        worker.fail_all("Worker disconnected")
        logger.info("worker_disconnected id=%s name=%s", worker.id, worker.name)
        try:
            await websocket.close()
        except Exception:
            pass


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


@app.get("/api/workers", dependencies=[Depends(require_admin)])
async def list_workers():
    return {"workers": registry.snapshot()}


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

    if body.get("stream"):
        stream_options = body.get("stream_options")
        if not isinstance(stream_options, dict):
            stream_options = {}
        stream_options["include_usage"] = True
        body["stream_options"] = stream_options

    worker = registry.pick(body.get("model"))
    if worker is not None:
        return await via_worker(worker, body, api_key["id"])
    if not DIRECT_FALLBACK:
        return no_worker()
    return await via_direct(body, api_key["id"])