import asyncio
import json
import logging
import os
import random
import re

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

GATEWAY_URL = os.getenv("GATEWAY_URL", "ws://localhost:8080/workers/connect")
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000")
WORKER_NAME = os.getenv("WORKER_NAME", "local-gpu")
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "8"))
AGENT_VERSION = "0.1.0"
ALLOWED_PATHS = {"/v1/chat/completions"}
MAX_BACKOFF = 60.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent")
logging.getLogger("httpx").setLevel(logging.WARNING)

METRIC_NAMES = {
    "running": ("vllm:num_requests_running",),
    "waiting": ("vllm:num_requests_waiting",),
    "kv_cache_usage": ("vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"),
}


def parse_metrics(text):
    totals = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[{ ]", line, maxsplit=1)[0]
        try:
            value = float(line.rsplit(" ", 1)[1])
        except (IndexError, ValueError):
            continue
        totals[name] = totals.get(name, 0.0) + value
    return {
        key: next((totals[name] for name in names if name in totals), 0.0)
        for key, names in METRIC_NAMES.items()
    }


async def send(ws, payload):
    await ws.send(json.dumps(payload))


async def discover_models(http):
    response = await http.get("/v1/models")
    response.raise_for_status()
    return [item["id"] for item in response.json().get("data", [])]


async def heartbeat_loop(ws, http, interval):
    while True:
        try:
            response = await http.get("/metrics")
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("vllm_unreachable closing connection")
            await ws.close(code=1011)
            return
        await send(ws, {"type": "heartbeat", **parse_metrics(response.text)})
        await asyncio.sleep(interval)


async def handle_request(ws, http, message):
    request_id = message.get("request_id")
    path = message.get("path")
    body = message.get("body")
    if not isinstance(request_id, str):
        return
    if path not in ALLOWED_PATHS or not isinstance(body, dict):
        await send(
            ws,
            {"type": "response_error", "request_id": request_id, "message": "Rejected request"},
        )
        return
    logger.info("request_start request_id=%s", request_id[:12])
    try:
        async with http.stream("POST", path, json=body) as response:
            await send(
                ws,
                {"type": "response_start", "request_id": request_id, "status": response.status_code},
            )
            if response.status_code == 200 and body.get("stream"):
                async for text in response.aiter_text():
                    await send(ws, {"type": "response_chunk", "request_id": request_id, "data": text})
            else:
                data = (await response.aread()).decode(errors="replace")
                await send(ws, {"type": "response_chunk", "request_id": request_id, "data": data})
        await send(ws, {"type": "response_end", "request_id": request_id})
        logger.info("request_end request_id=%s", request_id[:12])
    except asyncio.CancelledError:
        logger.info("request_cancelled request_id=%s", request_id[:12])
        raise
    except ConnectionClosed:
        return
    except httpx.HTTPError as exc:
        try:
            await send(
                ws,
                {
                    "type": "response_error",
                    "request_id": request_id,
                    "message": f"vLLM request failed: {type(exc).__name__}",
                },
            )
        except ConnectionClosed:
            return


async def session(http, state):
    models = await discover_models(http)
    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}
    async with connect(GATEWAY_URL, additional_headers=headers, max_size=8 * 1024 * 1024) as ws:
        await send(
            ws,
            {
                "type": "hello",
                "worker_name": WORKER_NAME,
                "models": models,
                "max_concurrency": MAX_CONCURRENCY,
                "agent_version": AGENT_VERSION,
            },
        )
        welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if welcome.get("type") != "welcome":
            raise RuntimeError("unexpected handshake reply")
        state["ready"] = True
        interval = float(welcome.get("heartbeat_interval", 5))
        logger.info("connected worker_id=%s models=%s", welcome.get("worker_id"), models)

        tasks = {}
        heartbeat = asyncio.create_task(heartbeat_loop(ws, http, interval))
        try:
            async for raw in ws:
                message = json.loads(raw)
                kind = message.get("type")
                if kind == "request":
                    request_id = message.get("request_id")
                    task = asyncio.create_task(handle_request(ws, http, message))
                    tasks[request_id] = task
                    task.add_done_callback(lambda _task, rid=request_id: tasks.pop(rid, None))
                elif kind == "cancel":
                    task = tasks.get(message.get("request_id"))
                    if task is not None:
                        task.cancel()
        finally:
            heartbeat.cancel()
            for task in list(tasks.values()):
                task.cancel()
            await asyncio.gather(heartbeat, *tasks.values(), return_exceptions=True)


async def run():
    delay = 1.0
    timeout = httpx.Timeout(120.0, connect=5.0)
    async with httpx.AsyncClient(base_url=VLLM_URL, timeout=timeout) as http:
        while True:
            state = {"ready": False}
            try:
                await session(http, state)
                logger.info("disconnected")
            except Exception as exc:
                logger.warning("connection_failed reason=%s", type(exc).__name__)
            delay = 1.0 if state["ready"] else min(delay * 2, MAX_BACKOFF)
            wait = delay * random.uniform(0.5, 1.5)
            logger.info("reconnecting in %.1fs", wait)
            await asyncio.sleep(wait)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("stopped")