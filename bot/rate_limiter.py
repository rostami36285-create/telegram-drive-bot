import time
from config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

_CLEANUP_INTERVAL = 300  # prune idle entries every 5 minutes


class RateLimiter:
    def __init__(self):
        self._log: dict[int, list[float]] = {}
        self._last_cleanup = time.monotonic()

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()

        # Periodic cleanup to prevent unbounded memory growth
        if now - self._last_cleanup > _CLEANUP_INTERVAL:
            self._cleanup(now)

        window = self._log.get(user_id, [])
        self._log[user_id] = [t for t in window if now - t < RATE_LIMIT_WINDOW]

        if len(self._log[user_id]) >= RATE_LIMIT_REQUESTS:
            return False

        self._log[user_id].append(now)
        return True

    def reset(self, user_id: int):
        self._log.pop(user_id, None)

    def _cleanup(self, now: float):
        self._last_cleanup = now
        cutoff = now - RATE_LIMIT_WINDOW
        dead = [uid for uid, ts in self._log.items() if not ts or ts[-1] < cutoff]
        for uid in dead:
            del self._log[uid]


# Singleton used across all handlers
limiter = RateLimiter()
