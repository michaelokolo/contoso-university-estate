"""Contoso Events: a fictional events platform for open days, campus tours and applicant days.

Unlike the other vendors, it uses OAuth 2.0 client credentials: exchange a client ID
and secret for a short-lived access token, then call the API with that token.

    POST /oauth/token                       form: grant_type=client_credentials, client_id, client_secret
    GET  /api/v2/events
    GET  /api/v2/events/{eventId}/registrations?page=&perPage=
    POST /api/v2/events/{eventId}/registrations
    POST /api/v2/events/{eventId}/registrations/{registrationId}/check-in
    POST /admin/simulate                    {"count": 40}   (bookings arrive over time)
    GET  /health

Webhooks: registration.created, registration.cancelled, attendee.checked_in.
Tokens expire after TOKEN_TTL_SECONDS (default 3600). Set the chaos panel's
extra.token_ttl_seconds to something small (e.g. 60) to feel expiring tokens.
"""

from __future__ import annotations

import asyncio
import math
import os
import random
import secrets
import time
import unicodedata
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.chaos import Chaos
from common.webhooks import Webhooks, now_iso

CLIENT_ID = os.environ.get("EVENTS_CLIENT_ID", "contoso-university")
CLIENT_SECRET = os.environ.get("EVENTS_CLIENT_SECRET", "change-me")
TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

FIRST = ["Amelia", "Oliver", "Isla", "Noah", "Ava", "Leo", "Zoë", "Musa", "Priya", "Chloé", "Kwame", "Siobhán",
         "Harry", "Grace", "Yusuf", "Mia", "Arjun", "Freya", "Tomás", "Ngozi"]
LAST = ["Smith", "Jones", "Khan", "Patel", "O'Brien", "Okafor", "Taylor", "Brown", "Nguyen", "Williams", "Singh",
        "Evans", "García", "Wilson", "Adeyemi", "Murphy", "Chen", "Hughes", "Smith-Jones", "Davies"]
INTERESTS = ["Computer Science", "Nursing", "Law", "Psychology", "Games Design", "Business Management",
             "Mechanical Engineering", "Data Science", "Midwifery", "Criminology"]


def chaos_error(status: int, message: str, headers: dict[str, str]) -> JSONResponse:
    return JSONResponse({"errors": [{"status": str(status), "title": message}]}, status_code=status, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_events()
    hooks.bind(asyncio.get_running_loop())
    yield


app = FastAPI(title="Contoso Events (fictional)", lifespan=lifespan)
chaos = Chaos("Contoso Events", chaos_error)
hooks = Webhooks("Events", chaos)
app.include_router(chaos.router())
app.include_router(hooks.router())

events: dict[str, dict] = {}
registrations: dict[str, list[dict]] = {}
tokens: dict[str, float] = {}


def build_events() -> None:
    rng = random.Random(2027)
    start = date(2026, 11, 7)
    kinds = [("Undergraduate Open Day", 600), ("Postgraduate Open Evening", 150), ("Applicant Day", 250),
             ("Campus Tour", 40), ("Virtual Information Session", 300)]
    for i in range(28):
        kind, capacity = kinds[i % len(kinds)]
        day = start + timedelta(days=7 * i + rng.randint(0, 3))
        ev_id = f"ev_{2026 + (day.year - 2026)}{i:03d}"
        events[ev_id] = {"id": ev_id, "name": f"{kind} - {day:%d %B %Y}", "type": kind, "date": day.isoformat(),
                         "location": "Online" if "Virtual" in kind else "Contoso University, Main Campus",
                         "capacity": capacity, "status": "open"}
        registrations[ev_id] = []


def require_token(authorization: str | None) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    expiry = tokens.get(token)
    if not expiry:
        raise HTTPException(401, detail="invalid_token")
    if time.time() > expiry:
        raise HTTPException(401, detail="token_expired")


def register(ev_id: str, attendee: dict) -> dict:
    reg = {"id": f"reg_{uuid.uuid4().hex[:12]}", "eventId": ev_id, "status": "booked", "createdAt": now_iso(),
           "attendee": attendee}
    registrations[ev_id].append(reg)
    hooks.emit("registration.created", {"registrationId": reg["id"], "eventId": ev_id, "attendee": attendee,
                                        "createdAt": reg["createdAt"]})
    return reg


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "system": "events", "events": len(events),
            "registrations": sum(len(v) for v in registrations.values())}


@app.post("/oauth/token")
def token(grant_type: str = Form(...), client_id: str = Form(...), client_secret: str = Form(...)):
    if grant_type != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if client_id != CLIENT_ID or not secrets.compare_digest(client_secret, CLIENT_SECRET):
        return JSONResponse({"error": "invalid_client"}, status_code=401)
    ttl = int(chaos.config.extra.get("token_ttl_seconds", TOKEN_TTL_SECONDS))
    value = secrets.token_urlsafe(32)
    tokens[value] = time.time() + ttl
    return {"access_token": value, "token_type": "Bearer", "expires_in": ttl}


@app.get("/api/v2/events")
def list_events(authorization: str | None = Header(default=None)):
    require_token(authorization)
    return {"data": [{**e, "booked": len(registrations[e["id"]])} for e in events.values()]}


@app.get("/api/v2/events/{ev_id}/registrations")
def list_registrations(ev_id: str, page: int = 1, perPage: int = 20, authorization: str | None = Header(default=None)):
    require_token(authorization)
    if ev_id not in events:
        raise HTTPException(404, detail="event_not_found")
    per = max(1, min(perPage, 100))
    rows = registrations[ev_id]
    pages = max(1, math.ceil(len(rows) / per))
    return {"data": rows[(page - 1) * per: page * per],
            "meta": {"page": page, "perPage": per, "totalPages": pages, "total": len(rows)}}


@app.post("/api/v2/events/{ev_id}/registrations", status_code=201)
def create_registration(ev_id: str, body: dict, authorization: str | None = Header(default=None)):
    require_token(authorization)
    if ev_id not in events:
        raise HTTPException(404, detail="event_not_found")
    for field in ("firstName", "lastName", "email"):
        if not body.get(field):
            raise HTTPException(422, detail=f"{field} is required")
    return register(ev_id, {k: body.get(k) for k in ("firstName", "lastName", "email", "subjectInterest", "postcode")})


@app.post("/api/v2/events/{ev_id}/registrations/{reg_id}/check-in")
def check_in(ev_id: str, reg_id: str, authorization: str | None = Header(default=None)):
    require_token(authorization)
    reg = next((r for r in registrations.get(ev_id, []) if r["id"] == reg_id), None)
    if not reg:
        raise HTTPException(404, detail="registration_not_found")
    reg["status"] = "attended"
    hooks.emit("attendee.checked_in", {"registrationId": reg_id, "eventId": ev_id, "checkedInAt": now_iso()})
    return reg


@app.post("/admin/simulate")
async def simulate(body: dict, x_admin_token: str | None = Header(default=None)):
    if x_admin_token != chaos.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    count = int(body.get("count", 20))

    async def run():
        for _ in range(count):
            ev_id = random.choice(list(events))
            first, last = random.choice(FIRST), random.choice(LAST)
            local = unicodedata.normalize("NFKD", f"{first}.{last}").encode("ascii", "ignore").decode()
            register(ev_id, {"firstName": first, "lastName": last,
                             "email": f"{local}{random.randint(1, 99)}@example.com".lower().replace("'", ""),
                             "subjectInterest": random.choice(INTERESTS), "postcode": None})
            await asyncio.sleep(random.uniform(0.2, 1.5))

    asyncio.get_running_loop().create_task(run())
    return {"simulating": count}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    headers = {"WWW-Authenticate": f'Bearer error="{exc.detail}"'} if exc.status_code == 401 else None
    return JSONResponse({"errors": [{"status": str(exc.status_code), "title": exc.detail}]},
                        status_code=exc.status_code, headers=headers)
