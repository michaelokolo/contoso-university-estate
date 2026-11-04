"""Contoso Application Portal: a modern SaaS application form vendor.

Applicants apply here (direct and postgraduate routes). The portal:
    - exposes a REST API (Bearer token) to read applications, with cursor paging
    - sends a signed webhook "application.submitted" for every new application
    - accepts status updates back from the university ("application.updated" webhook)
    - can replay realistic applications from the seed data (the simulator)

Endpoints
    POST  /api/v1/applications                   submit an application (what the web form calls)
    GET   /api/v1/applications?since=&limit=&cursor=
    GET   /api/v1/applications/{applicationId}
    PATCH /api/v1/applications/{applicationId}   {"status": "Offer - Conditional"}
    POST  /admin/simulate                        {"count": 50, "interval_ms": 500}
    GET   /health
Data is held in memory: when the app scales to zero it starts empty again. Replay with the simulator.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.chaos import Chaos
from common.webhooks import Webhooks, now_iso

API_KEY = os.environ.get("PORTAL_API_KEY", "change-me")
SEED_FILE = Path(os.environ.get("SEED_FILE", "/app/seed/applications.jsonl"))
VALID_STATUSES = {"Submitted", "Under review", "Offer - Conditional", "Offer - Unconditional", "Unsuccessful", "Withdrawn"}


def chaos_error(status: int, message: str, headers: dict[str, str]) -> JSONResponse:
    return JSONResponse({"error": {"code": status, "message": message}}, status_code=status, headers=headers)


store: dict[str, dict] = {}
order: list[str] = []
lock = Lock()
seed: list[dict] = []
next_no = 900000


@asynccontextmanager
async def lifespan(app: FastAPI):
    if SEED_FILE.exists():
        with open(SEED_FILE, encoding="utf-8") as f:
            seed.extend(json.loads(line) for line in f if line.strip())
    print(f"[portal] {len(seed)} seed applications available for the simulator")
    hooks.bind(asyncio.get_running_loop())
    yield


app = FastAPI(title="Contoso Application Portal", lifespan=lifespan)
chaos = Chaos("Application Portal", chaos_error)
hooks = Webhooks("Portal", chaos)
app.include_router(chaos.router())
app.include_router(hooks.router())


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


def require_key(authorization: str | None) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, API_KEY):
        raise HTTPException(401, detail="Missing or invalid bearer token")


def validate(doc: dict) -> list[str]:
    errors = []
    a = doc.get("applicant") or {}
    for field in ("firstName", "lastName", "email", "dateOfBirth"):
        if not a.get(field):
            errors.append(f"applicant.{field} is required")
    if a.get("email") and "@" not in a["email"]:
        errors.append("applicant.email is not a valid email address")
    if not (doc.get("programme") or {}).get("code"):
        errors.append("programme.code is required")
    return errors


def save(doc: dict) -> dict:
    global next_no
    with lock:
        next_no += 1
        doc = {**doc, "applicationId": f"APP-2027-{next_no}", "submittedAt": now_iso(), "updatedAt": now_iso(),
               "status": "Submitted"}
        store[doc["applicationId"]] = doc
        order.append(doc["applicationId"])
    hooks.emit("application.submitted", {"applicationId": doc["applicationId"], "programmeCode": doc["programme"]["code"],
                                         "submittedAt": doc["submittedAt"]})
    return doc


@app.get("/health")
def health():
    return {"status": "ok", "system": "portal", "applications": len(store)}


@app.post("/api/v1/applications", status_code=201)
def submit(doc: dict, authorization: str | None = Header(default=None)):
    require_key(authorization)
    errors = validate(doc)
    if errors:
        return JSONResponse({"error": {"code": 400, "message": "Validation failed", "details": errors}}, status_code=400)
    return save(doc)


@app.get("/api/v1/applications")
def list_applications(since: str | None = None, limit: int = 25, cursor: str | None = None,
                      authorization: str | None = Header(default=None)):
    """Cursor paging: follow 'nextCursor' until it is null. 'limit' is capped at 50."""
    require_key(authorization)
    limit = max(1, min(limit, 50))
    start = int(base64.urlsafe_b64decode(cursor).decode()) if cursor else 0
    ids = order if not since else [i for i in order if store[i]["updatedAt"] > since]
    page = ids[start:start + limit]
    more = start + limit < len(ids)
    return {"items": [store[i] for i in page],
            "nextCursor": base64.urlsafe_b64encode(str(start + limit).encode()).decode() if more else None}


@app.get("/api/v1/applications/{application_id}")
def get_application(application_id: str, authorization: str | None = Header(default=None)):
    require_key(authorization)
    doc = store.get(application_id)
    if not doc:
        raise HTTPException(404, detail=f"Application {application_id} not found")
    return doc


@app.patch("/api/v1/applications/{application_id}")
def update_status(application_id: str, body: dict, authorization: str | None = Header(default=None)):
    require_key(authorization)
    doc = store.get(application_id)
    if not doc:
        raise HTTPException(404, detail=f"Application {application_id} not found")
    status = body.get("status")
    if status not in VALID_STATUSES:
        raise HTTPException(400, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    doc["status"], doc["updatedAt"] = status, now_iso()
    hooks.emit("application.updated", {"applicationId": application_id, "status": status, "updatedAt": doc["updatedAt"]})
    return doc


@app.post("/admin/simulate")
async def simulate(body: dict, x_admin_token: str | None = Header(default=None)):
    """Replay realistic applications from the seed data, as if applicants were submitting now."""
    if x_admin_token != chaos.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    if not seed:
        raise HTTPException(409, detail="No seed data in this image")
    count, interval = int(body.get("count", 10)), int(body.get("interval_ms", 500))

    async def run():
        for _ in range(count):
            original = random.choice(seed)
            save({"applicant": original["applicant"], "programme": original["programme"]})
            await asyncio.sleep(interval / 1000)

    asyncio.get_running_loop().create_task(run())
    return {"simulating": count, "interval_ms": interval}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": {"code": exc.status_code, "message": exc.detail}}, status_code=exc.status_code)
