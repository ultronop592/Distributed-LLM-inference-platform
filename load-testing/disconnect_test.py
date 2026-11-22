import os
import sys
import time

import httpx

GATEWAY = "http://localhost:8080"
VLLM = "http://localhost:8000"
API_KEY = os.environ["API_KEY"]


def running_requests():
    text = httpx.get(f"{VLLM}/metrics").text
    for line in text.splitlines():
        if line.startswith("vllm:num_requests_running"):
            return float(line.split()[-1])
    return None


payload = {
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "messages": [{"role": "user", "content": "Write a very long story about a dragon."}],
    "stream": True,
    "max_tokens": 1500,
}

before = running_requests()
if before is None:
    print("Could not find vllm:num_requests_running in /metrics")
    sys.exit(1)
print("running before:", before)

during = None
with httpx.Client(timeout=60) as client:
    with client.stream(
        "POST",
        f"{GATEWAY}/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {API_KEY}"},
    ) as response:
        print("gateway status:", response.status_code)
        for count, line in enumerate(response.iter_lines()):
            if count == 5:
                during = running_requests()
                print("running during:", during)
                break

time.sleep(3)
after = running_requests()
print("running after disconnect:", after)
print("PASS" if during == 1.0 and after == 0.0 else "FAIL")