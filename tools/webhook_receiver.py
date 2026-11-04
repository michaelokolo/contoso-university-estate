"""A tiny local webhook receiver: prints every webhook and checks its signature.

    pip install fastapi uvicorn
    WEBHOOK_SECRET=your-secret python tools/webhook_receiver.py      # listens on http://localhost:9000/webhooks

Point a vendor at it:  PUT /admin/webhooks  {"url": "http://host.docker.internal:9000/webhooks", "secret": "..."}
"""

import hashlib
import hmac
import os
import time

import uvicorn
from fastapi import FastAPI, Request, Response

SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")
TOLERANCE_SECONDS = 300
app = FastAPI()
seen: set[str] = set()


def verify(header: str, body: bytes) -> str:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts, sig = int(parts["t"]), parts["v1"]
    except Exception:
        return "malformed signature header"
    if abs(time.time() - ts) > TOLERANCE_SECONDS:
        return "timestamp too old (possible replay)"
    expected = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return "ok" if hmac.compare_digest(expected, sig) else "BAD SIGNATURE"


@app.post("/webhooks")
async def receive(request: Request):
    body = await request.body()
    result = verify(request.headers.get("x-contoso-signature", ""), body)
    event_id = request.headers.get("x-contoso-event-id", "?")
    duplicate = event_id in seen
    seen.add(event_id)
    print(f"{time.strftime('%H:%M:%S')}  signature={result:<10} {'DUPLICATE ' if duplicate else ''}{body.decode()[:200]}")
    return Response(status_code=200 if result == "ok" else 401)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9000")), log_level="warning")
