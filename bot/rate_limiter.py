import time
from collections import defaultdict
from config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW


class RateLimiter:
    def __init__(self):
        self._log: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        window = self._log[user_id]

        # Drop timestamps outside the window
        self._log[user_id] = [t for t in window if now - t < RATE_LIMIT_WINDOW]

        if len(self._log[user_id]) >= RATE_LIMIT_REQUESTS:
            return False

        self._log[user_id].append(now)
        return True

    def reset(self, user_id: int):
        self._log.pop(user_id, None)


# Singleton used across all handlers
limiter = RateLimiter()
