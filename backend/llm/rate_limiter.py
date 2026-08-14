import time
from typing import Optional
from collections import deque


class RateLimiter:
    def __init__(self, requests_per_minute: int = 50):
        self.rate = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.timestamps: deque = deque()

    async def acquire(self):
        now = time.monotonic()
        while self.timestamps and self.timestamps[0] < now - 60:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.rate:
            sleep_time = self.timestamps[0] + 60 - now
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.timestamps.append(time.monotonic())

    def remaining(self) -> int:
        now = time.monotonic()
        while self.timestamps and self.timestamps[0] < now - 60:
            self.timestamps.popleft()
        return max(0, self.rate - len(self.timestamps))
