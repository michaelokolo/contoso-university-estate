"""Signed webhooks, sent the way real SaaS vendors send them.

Every event is JSON:
    {"id": "evt_...", "type": "payment.succeeded", "created": "2026-11-04T19:30:00Z", "data": {...}}

and carries a signature header, Stripe-style:
    X-Contoso-Signature: t=1730748600,v1=<hex HMAC-SHA256 of "t.body" with the shared secret>

To verify: rebuild "t.body" from the raw request body, HMAC it with the secret, compare
(constant-time), and reject old timestamps (replay protection).

Delivery: any 2xx response = delivered. Anything else, or a timeout, is retried with
back-off (2s, 10s, 30s, 60s, 120s). Like real vendors, the same event can arrive more
than once and events can arrive out of order, so receivers must be idempotent.

Admin API (header X-Admin-Token):
    GET  /admin/webhooks                    destination settings
    PUT  /admin/webhooks                    {"url": "...", "secret": "..."}
    GET  /admin/webhooks/deliveries         recent delivery attempts
    POST /admin/webhooks/redeliver/{id}     send an event again
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import random
import time
import uuid
from collections import deque
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException

from .chaos import Chaos

BACKOFF_SECONDS = [2, 10, 30, 60, 120]


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Webhooks:
    def __init__(self, system: str, chaos: Chaos):
        self.system = system
        self.chaos = chaos
        self.url = os.environ.get("WEBHOOK_URL", "")
        self.secret = os.environ.get("WEBHOOK_SECRET", "change-me")
        self.events: dict[str, dict] = {}
        self.deliveries: deque[dict] = deque(maxlen=500)
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Call once at startup so events emitted from worker threads still get delivered."""
        self.loop = loop

    def _schedule(self, coro) -> None:
        try:
            asyncio.get_running_loop().create_task(coro)
        except RuntimeError:  # called from a sync endpoint's worker thread
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def emit(self, event_type: str, data: dict) -> dict:
        event = {"id": f"evt_{uuid.uuid4().hex[:20]}", "type": event_type, "created": now_iso(), "data": data}
        self.events[event["id"]] = event
        if self.url:
            self._schedule(self._deliver(event))
            extra = self.chaos.config.extra
            if random.random() < float(extra.get("duplicate_rate", 0)):
                self._schedule(self._deliver(event, delay=random.uniform(1, 5)))
        return event

    async def _deliver(self, event: dict, delay: float = 0.0) -> None:
        extra = self.chaos.config.extra
        if extra.get("out_of_order"):
            delay += random.uniform(0, 8)
        if delay:
            await asyncio.sleep(delay)
        body = json.dumps(event, separators=(",", ":")).encode()
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            ts = int(time.time())
            signature = sign(self.secret, ts, body)
            if random.random() < float(extra.get("bad_signature_rate", 0)):
                signature = sign("wrong-secret", ts, body)
            record = {"event_id": event["id"], "type": event["type"], "attempt": attempt + 1, "at": now_iso(),
                      "url": self.url}
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(self.url, content=body, headers={
                        "Content-Type": "application/json",
                        "X-Contoso-Signature": signature,
                        "X-Contoso-Event-Id": event["id"],
                        "User-Agent": f"Contoso-{self.system}-Webhooks/1.0",
                    })
                record["status"] = r.status_code
                self.deliveries.appendleft(record)
                if 200 <= r.status_code < 300:
                    return
            except httpx.HTTPError as exc:
                record["status"] = f"error: {type(exc).__name__}"
                self.deliveries.appendleft(record)
            if attempt < len(BACKOFF_SECONDS):
                await asyncio.sleep(BACKOFF_SECONDS[attempt])

    def router(self) -> APIRouter:
        r = APIRouter(prefix="/admin/webhooks", tags=["admin"])

        def check(token: str | None) -> None:
            if token != self.chaos.admin_token:
                raise HTTPException(status_code=401, detail="Invalid admin token")

        @r.get("")
        def get_settings(x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            return {"url": self.url, "secret_set": bool(self.secret)}

        @r.put("")
        def put_settings(body: dict, x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            self.url = body.get("url", self.url)
            self.secret = body.get("secret", self.secret)
            return {"url": self.url, "secret_set": bool(self.secret)}

        @r.get("/deliveries")
        def deliveries(x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            return list(self.deliveries)

        @r.post("/redeliver/{event_id}")
        async def redeliver(event_id: str, x_admin_token: str | None = Header(default=None)):
            check(x_admin_token)
            event = self.events.get(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Unknown event")
            asyncio.get_running_loop().create_task(self._deliver(event))
            return {"redelivering": event_id}

        return r
