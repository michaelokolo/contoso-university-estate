"""Chaos panel: makes a system misbehave on demand, like real systems do.

Every Contoso system mounts this. Faults are switched on through an admin API,
so an integration can be broken without changing its code:

    GET  /admin/chaos          current settings
    PUT  /admin/chaos          change settings (JSON body, any subset of fields)
    POST /admin/chaos/reset    back to normal

All admin calls need the header  X-Admin-Token: <ADMIN_TOKEN>.
Paths starting /admin and /health are never affected by chaos.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from collections import deque
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response


@dataclass
class ChaosConfig:
    latency_ms: int = 0              # added to every response
    jitter_ms: int = 0               # plus a random 0..jitter_ms
    error_rate: float = 0.0          # 0.0 - 1.0 share of requests that fail
    error_status: int = 500          # status code used for those failures
    rate_limit_per_minute: int = 0   # 0 = no limit; above it -> 429 + Retry-After
    retry_after_seconds: int = 30
    maintenance: bool = False        # True = everything returns 503
    maintenance_window_utc: str = "" # e.g. "02:00-02:30": 503 during that time every day
    schema_version: str = "v1"       # systems may change field names in v2
    extra: dict = field(default_factory=dict)  # system-specific switches


ErrorRenderer = Callable[[int, str, dict[str, str]], Response]


class Chaos:
    def __init__(self, system: str, render_error: ErrorRenderer):
        self.system = system
        self.config = ChaosConfig()
        self.render_error = render_error
        self._hits: deque[float] = deque()
        self.admin_token = os.environ.get("ADMIN_TOKEN", "change-me")

    # -- runtime ------------------------------------------------------------
    def _in_window(self) -> bool:
        window = self.config.maintenance_window_utc
        if not window:
            return False
        start, end = window.split("-")
        now = datetime.now(timezone.utc).strftime("%H:%M")
        return start <= now < end if start <= end else (now >= start or now < end)

    async def apply(self, request: Request) -> Response | None:
        path = request.url.path
        if path.startswith("/admin") or path.startswith("/health"):
            return None
        c = self.config
        if c.maintenance or self._in_window():
            return self.render_error(503, f"{self.system} is unavailable for scheduled maintenance",
                                     {"Retry-After": str(c.retry_after_seconds)})
        if c.rate_limit_per_minute:
            now = time.monotonic()
            while self._hits and now - self._hits[0] > 60:
                self._hits.popleft()
            if len(self._hits) >= c.rate_limit_per_minute:
                return self.render_error(429, "Too many requests",
                                         {"Retry-After": str(c.retry_after_seconds)})
            self._hits.append(now)
        delay = c.latency_ms + (random.randint(0, c.jitter_ms) if c.jitter_ms else 0)
        if delay:
            await asyncio.sleep(delay / 1000)
        if c.error_rate and random.random() < c.error_rate:
            return self.render_error(c.error_status, f"{self.system} internal error", {})
        return None

    # -- admin API ----------------------------------------------------------
    def router(self) -> APIRouter:
        r = APIRouter(prefix="/admin", tags=["admin"])

        def check(token: str | None) -> None:
            if token != self.admin_token:
                raise HTTPException(status_code=401, detail="Invalid admin token")

        @r.get("/chaos")
        def get_chaos(x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            return asdict(self.config)

        @r.put("/chaos")
        def put_chaos(body: dict, x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            allowed = {f.name for f in fields(ChaosConfig)}
            unknown = set(body) - allowed
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown settings: {sorted(unknown)}")
            for key, value in body.items():
                setattr(self.config, key, value)
            return asdict(self.config)

        @r.post("/chaos/reset")
        def reset(x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            self.config = ChaosConfig()
            return asdict(self.config)

        return r
