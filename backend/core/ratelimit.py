"""Per-user rate limits on the endpoints that cost money or credits.

Nothing stood between one script and unlimited analyses, ADE extractions or chat turns. Each of
those spends real money now (OpenAI per analysis, LandingAI per extraction), so the limit is not
about server load: it is a spending cap that survives a bug in a retry loop as well as abuse.

Deliberately in-process rather than Redis: the API runs as a single instance (the same
assumption the startup recovery rests on), and a dependency-free limiter that works today beats
a distributed one nobody has stood up. With several replicas each would allow the limit, so this
moves to a shared store at the same time as the job queue.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from .auth import get_current_user
from .config import get_settings

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()

# Stops the dict growing without bound if keys are one-shot (an unauthenticated caller behind
# rotating IPs, say). Well above any real user count on one instance.
_MAX_TRACKED_KEYS = 50_000


def _allow(key: str, max_calls: int, per_seconds: int, now: float | None = None) -> bool:
    """Sliding window: true if this call fits inside the last `per_seconds`."""
    now = time.monotonic() if now is None else now
    with _lock:
        if len(_hits) > _MAX_TRACKED_KEYS:
            _hits.clear()
        window = _hits[key]
        cutoff = now - per_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= max_calls:
            return False
        window.append(now)
        return True


def reset() -> None:
    """Forget every window. For tests, and for a process that wants a clean slate."""
    with _lock:
        _hits.clear()


def rate_limit(name: str, max_calls: int, per_seconds: int = 60) -> Callable:
    """A FastAPI dependency that limits `name` to `max_calls` per `per_seconds`, per user.

    Keyed on the authenticated user, falling back to the client address, so one noisy user
    cannot spend another user's allowance.
    """
    def dependency(request: Request, user: dict = Depends(get_current_user)) -> None:
        if not get_settings().rate_limit_enabled:
            return
        client = request.client.host if request.client else "unknown"
        key = f"{name}:{user.get('user_id') or client}"
        if not _allow(key, max_calls, per_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests — {name} is limited to "
                       f"{max_calls} per {per_seconds // 60 or 1} minute(s). Try again shortly.",
            )
    return dependency
