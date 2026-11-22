import os
import time

from locust import HttpUser, between, events, task

API_KEY = os.environ["API_KEY"]
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


class ChatUser(HttpUser):
    wait_time = between(float(os.getenv("THINK_MIN", "0.5")), float(os.getenv("THINK_MAX", "1.5")))

    @task
    def stream_chat(self):
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Explain gravity in three sentences."}],
            "stream": True,
            "max_tokens": 64,
        }
        started = time.perf_counter()
        first_chunk = None
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=HEADERS,
            stream=True,
            catch_response=True,
            name="chat_stream",
        ) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
                return
            for line in response.iter_lines():
                if line.startswith(b"data:") and first_chunk is None:
                    first_chunk = (time.perf_counter() - started) * 1000
            response.success()
        total = (time.perf_counter() - started) * 1000
        if first_chunk is not None:
            events.request.fire(
                request_type="STREAM",
                name="time_to_first_chunk",
                response_time=first_chunk,
                response_length=0,
                exception=None,
                context={},
            )
        events.request.fire(
            request_type="STREAM",
            name="total_stream_time",
            response_time=total,
            response_length=0,
            exception=None,
            context={},
        )