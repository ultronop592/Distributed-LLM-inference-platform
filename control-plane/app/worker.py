import asyncio
import time
import uuid

RESPONSE_TYPES = {"response_start", "response_chunk", "response_end", "response_error"}


def as_number(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


class Worker:
    def __init__(self, name, models, max_concurrency, websocket):
        self.id = uuid.uuid4().hex[:12]
        self.name = name
        self.models = models
        self.max_concurrency = max_concurrency
        self.websocket = websocket
        self.connected_at = time.time()
        self.last_heartbeat = time.monotonic()
        self.running = 0.0
        self.waiting = 0.0
        self.kv_cache_usage = 0.0
        self.inflight = {}
        self.send_lock = asyncio.Lock()

    async def send(self, message):
        async with self.send_lock:
            await self.websocket.send_json(message)

    async def start_request(self, path, body):
        request_id = uuid.uuid4().hex
        queue = asyncio.Queue()
        self.inflight[request_id] = queue
        try:
            await self.send(
                {"type": "request", "request_id": request_id, "path": path, "body": body}
            )
        except Exception:
            self.inflight.pop(request_id, None)
            raise
        return request_id, queue

    def finish(self, request_id):
        self.inflight.pop(request_id, None)

    async def cancel(self, request_id):
        self.finish(request_id)
        try:
            await self.send({"type": "cancel", "request_id": request_id})
        except Exception:
            return

    def handle(self, message):
        if not isinstance(message, dict):
            return
        kind = message.get("type")
        if kind == "heartbeat":
            self.last_heartbeat = time.monotonic()
            self.running = as_number(message.get("running"))
            self.waiting = as_number(message.get("waiting"))
            self.kv_cache_usage = as_number(message.get("kv_cache_usage"))
            return
        request_id = message.get("request_id")
        if not isinstance(request_id, str) or kind not in RESPONSE_TYPES:
            return
        queue = self.inflight.get(request_id)
        if queue is not None:
            queue.put_nowait(message)

    def fail_all(self, reason):
        for queue in self.inflight.values():
            queue.put_nowait({"type": "response_error", "message": reason})

    def snapshot(self):
        return {
            "id": self.id,
            "name": self.name,
            "models": self.models,
            "max_concurrency": self.max_concurrency,
            "inflight": len(self.inflight),
            "running": self.running,
            "waiting": self.waiting,
            "kv_cache_usage": self.kv_cache_usage,
            "connected_at": int(self.connected_at),
        }


class WorkerRegistry:
    def __init__(self):
        self.workers = {}

    def add(self, worker):
        self.workers[worker.id] = worker

    def remove(self, worker_id):
        self.workers.pop(worker_id, None)

    def pick(self, model):
        if not isinstance(model, str):
            return None
        candidates = [
            worker
            for worker in self.workers.values()
            if model in worker.models and len(worker.inflight) < worker.max_concurrency
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda worker: (len(worker.inflight) + worker.waiting, worker.kv_cache_usage),
        )

    def snapshot(self):
        return [worker.snapshot() for worker in self.workers.values()]