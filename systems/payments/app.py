"""Contoso Pay: a fictional payment provider for tuition fee deposits and payments.

The university creates a payment request; the applicant pays on the provider's page;
the provider tells the university what happened with a signed webhook.

    POST /v1/payment-requests        {"reference": "INV0005817", "amount": "500.00", "currency": "GBP",
                                      "payerEmail": "ada@example.com", "description": "Tuition deposit"}
    GET  /v1/payment-requests/{id}
    POST /admin/simulate/pay/{id}    {"outcome": "succeeded" | "failed"}   (play the applicant paying)
    GET  /health
Auth: Authorization: Bearer <secret key>

Webhooks: payment.succeeded, payment.failed (see common/webhooks.py for signatures and retries).
If AUTO_PAY_SECONDS is set, every request is paid (or fails, 8%) automatically after that delay.
"""

from __future__ import annotations

import asyncio
import os
import random
import secrets
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.chaos import Chaos
from common.webhooks import Webhooks, now_iso

SECRET_KEY = os.environ.get("PAYMENTS_SECRET_KEY", "change-me")
AUTO_PAY_SECONDS = int(os.environ.get("AUTO_PAY_SECONDS", "0"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8085")


def chaos_error(status: int, message: str, headers: dict[str, str]) -> JSONResponse:
    return JSONResponse({"error": {"type": "api_error", "status": status, "message": message}},
                        status_code=status, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    hooks.bind(asyncio.get_running_loop())
    yield


app = FastAPI(title="Contoso Pay (fictional)", lifespan=lifespan)
chaos = Chaos("Contoso Pay", chaos_error)
hooks = Webhooks("Pay", chaos)
app.include_router(chaos.router())
app.include_router(hooks.router())
requests_store: dict[str, dict] = {}


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


def require_key(authorization: str | None) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, SECRET_KEY):
        raise HTTPException(401, detail="Invalid API key")


def settle(pr_id: str, outcome: str) -> dict:
    pr = requests_store[pr_id]
    if pr["status"] != "pending":
        return pr
    pr["status"] = outcome
    pr["completedAt"] = now_iso()
    data = {"paymentRequestId": pr_id, "reference": pr["reference"], "amount": pr["amount"],
            "currency": pr["currency"], "status": outcome, "completedAt": pr["completedAt"]}
    if outcome == "succeeded":
        data["paymentMethod"] = random.choice(["card", "card", "bank_transfer", "apple_pay"])
    else:
        data["failureReason"] = random.choice(["card_declined", "insufficient_funds", "expired_card"])
    hooks.emit(f"payment.{outcome}", data)
    return pr


@app.get("/health")
def health():
    return {"status": "ok", "system": "payments", "paymentRequests": len(requests_store)}


@app.post("/v1/payment-requests", status_code=201)
async def create(body: dict, authorization: str | None = Header(default=None)):
    require_key(authorization)
    for field in ("reference", "amount", "currency", "payerEmail"):
        if not body.get(field):
            raise HTTPException(400, detail=f"{field} is required")
    try:
        amount = Decimal(str(body["amount"])).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise HTTPException(400, detail="amount must be a decimal string, e.g. \"500.00\"")
    if amount <= 0:
        raise HTTPException(400, detail="amount must be greater than zero")
    pr_id = f"pr_{uuid.uuid4().hex[:16]}"
    pr = {"id": pr_id, "reference": body["reference"], "amount": f"{amount:.2f}", "currency": body["currency"].upper(),
          "payerEmail": body["payerEmail"], "description": body.get("description"), "status": "pending",
          "createdAt": now_iso(), "payUrl": f"{PUBLIC_URL}/pay/{pr_id}"}
    requests_store[pr_id] = pr
    if AUTO_PAY_SECONDS:
        async def auto():
            await asyncio.sleep(AUTO_PAY_SECONDS)
            settle(pr_id, "failed" if random.random() < 0.08 else "succeeded")
        asyncio.get_running_loop().create_task(auto())
    return pr


@app.get("/v1/payment-requests/{pr_id}")
def get_request(pr_id: str, authorization: str | None = Header(default=None)):
    require_key(authorization)
    pr = requests_store.get(pr_id)
    if not pr:
        raise HTTPException(404, detail=f"No payment request {pr_id}")
    return pr


@app.post("/admin/simulate/pay/{pr_id}")
async def simulate_pay(pr_id: str, body: dict, x_admin_token: str | None = Header(default=None)):
    if x_admin_token != chaos.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    if pr_id not in requests_store:
        raise HTTPException(404, detail=f"No payment request {pr_id}")
    outcome = body.get("outcome", "succeeded")
    if outcome not in ("succeeded", "failed"):
        raise HTTPException(400, detail="outcome must be succeeded or failed")
    return settle(pr_id, outcome)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": {"type": "invalid_request_error", "status": exc.status_code, "message": exc.detail}},
                        status_code=exc.status_code)
