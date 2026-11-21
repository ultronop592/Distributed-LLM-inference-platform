import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.hits = defaultdict(deque)

    def check(self, key):
        now = time.monotonic()
        queue = self.hits[key]
        while queue and now - queue[0] >= self.window:
            queue.popleft()
        if len(queue) >= self.limit:
            retry_after = max(1, int(self.window - (now - queue[0])) + 1)
            return False, retry_after
        queue.append(now)
        return True, 0