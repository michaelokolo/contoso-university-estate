"""Contoso's UCAS-style admissions feed (a fictional "UCAS Link").

The university downloads one XML transaction file per day, like a provider's daily
UCAS download. Files only become visible once their date has arrived on the
"cycle clock", so a new file appears each day without anyone doing anything.

    GET /link/v1/files?from=YYYY-MM-DD&to=YYYY-MM-DD    list available files
    GET /link/v1/files/{name}                           download one file
    PUT /admin/clock   {"today": "2027-08-12"}           jump the cycle clock (e.g. to results day)
    GET /health
Auth: header X-Provider-Key.

Chaos switches (chaos panel "extra"):
    late_file: true        today's file is not published yet (404) until you switch it off
    truncated_file: true   today's file is cut off half way (invalid XML)
"""

from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from common.chaos import Chaos

PROVIDER_KEY = os.environ.get("UCAS_PROVIDER_KEY", "change-me")
FILES_DIR = Path(os.environ.get("UCAS_FILES_DIR", "/app/seed/ucas"))


def chaos_error(status: int, message: str, headers: dict[str, str]) -> JSONResponse:
    return JSONResponse({"errorCode": status, "errorMessage": message}, status_code=status, headers=headers)


app = FastAPI(title="Contoso UCAS Link (fictional)")
chaos = Chaos("UCAS Link", chaos_error)
app.include_router(chaos.router())
clock: dict[str, date | None] = {"today": None}   # None = follow the real date


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


def today() -> date:
    return clock["today"] or datetime.now(timezone.utc).date()


def file_date(path: Path) -> date:
    stamp = path.stem.split("_")[1]            # ucas_20270812
    return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))


def visible() -> list[Path]:
    files = sorted(FILES_DIR.glob("ucas_*.xml"))
    late = chaos.config.extra.get("late_file")
    return [f for f in files if file_date(f) < today() or (file_date(f) == today() and not late)]


def require_key(key: str | None) -> None:
    if not key or not secrets.compare_digest(key, PROVIDER_KEY):
        raise HTTPException(401, detail="Missing or invalid X-Provider-Key")


@app.get("/health")
def health():
    return {"status": "ok", "system": "ucas", "cycleToday": today().isoformat(), "filesVisible": len(visible())}


@app.get("/link/v1/files")
def list_files(request: Request, to: str | None = None, x_provider_key: str | None = Header(default=None)):
    require_key(x_provider_key)
    lo = request.query_params.get("from")   # "from" is a Python keyword, so read it directly
    files = visible()
    if lo:
        files = [f for f in files if file_date(f).isoformat() >= lo]
    if to:
        files = [f for f in files if file_date(f).isoformat() <= to]
    return {"cycleToday": today().isoformat(),
            "files": [{"name": f.name, "date": file_date(f).isoformat(), "sizeBytes": f.stat().st_size} for f in files]}


@app.get("/link/v1/files/{name}")
def get_file(name: str, x_provider_key: str | None = Header(default=None)):
    require_key(x_provider_key)
    match = next((f for f in visible() if f.name == name), None)
    if not match:
        raise HTTPException(404, detail=f"File {name} is not available")
    data = match.read_bytes()
    if chaos.config.extra.get("truncated_file") and file_date(match) == today():
        data = data[: len(data) // 2]
    return Response(data, media_type="application/xml")


@app.put("/admin/clock")
def set_clock(body: dict, x_admin_token: str | None = Header(default=None)):
    if x_admin_token != chaos.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    value = body.get("today")
    clock["today"] = date.fromisoformat(value) if value else None
    return {"cycleToday": today().isoformat(), "following": "real date" if clock["today"] is None else "fixed date"}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"errorCode": exc.status_code, "errorMessage": exc.detail}, status_code=exc.status_code)
