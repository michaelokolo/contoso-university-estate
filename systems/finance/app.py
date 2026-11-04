"""Contoso Finance System: an ERP-style REST API plus a nightly CSV export.

Behaves like an older finance system (think Unit4 or Agresso):
    - REST/JSON with PascalCase fields, money as strings ("9535.00"), dates as dd/MM/yyyy
    - API key in the X-Api-Key header
    - paged lists: pageSize is silently capped at 100
    - schema v2 renames StudentRef to StudentReference (switch it on in the chaos panel)
    - payments are NOT de-duplicated: send the same payment twice and it is recorded twice
    - a nightly export writes customers_export_YYYYMMDD.csv in Windows-1252 to the drop zone

Endpoints
    GET  /api/v1/customers?page=&pageSize=&studentRef=
    GET  /api/v1/customers/{CustomerNo}
    POST /api/v1/customers
    GET  /api/v1/invoices?customerNo=&status=
    POST /api/v1/invoices
    POST /api/v1/payments
    POST /admin/export/run          run the nightly export now
    GET  /health
"""

from __future__ import annotations

import asyncio
import csv
import math
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.chaos import Chaos
from common.db import connect, wait_for_db

API_KEY = os.environ.get("FINANCE_API_KEY", "change-me")
SEED_DIR = Path(os.environ.get("SEED_DIR", "/seed"))
DROPZONE = Path(os.environ.get("DROPZONE", "/dropzone")) / "finance"
EXPORT_TIME_UTC = os.environ.get("EXPORT_TIME_UTC", "02:00")
MAX_PAGE_SIZE = 100


def chaos_error(status: int, message: str, headers: dict[str, str]) -> JSONResponse:
    return JSONResponse({"ErrorCode": status, "Message": message}, status_code=status, headers=headers)


chaos = Chaos("Finance System", chaos_error)


def v2() -> bool:
    return chaos.config.schema_version == "v2"


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def uk_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def parse_money(value) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise HTTPException(400, detail={"ErrorCode": "INVALID_AMOUNT", "Message": f"'{value}' is not a valid amount"})


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_no   varchar(10) PRIMARY KEY,
    customer_name varchar(200) NOT NULL,      -- "Surname, Forename"
    student_ref   varchar(8),                 -- SIS student code; sometimes missing
    created_at    timestamp NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS invoices (
    invoice_no    varchar(12) PRIMARY KEY,
    customer_no   varchar(10) NOT NULL REFERENCES customers(customer_no),
    fee_code      varchar(12) NOT NULL,
    academic_year varchar(6) NOT NULL,
    invoice_date  date NOT NULL,
    amount        numeric(10,2) NOT NULL,
    status        varchar(10) NOT NULL DEFAULT 'Open'
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id    serial PRIMARY KEY,
    invoice_no    varchar(12) NOT NULL REFERENCES invoices(invoice_no),
    amount        numeric(10,2) NOT NULL,
    reference     varchar(100),               -- NOT unique: duplicates are accepted
    received_at   timestamp NOT NULL DEFAULT now()
);
CREATE SEQUENCE IF NOT EXISTS customer_seq START 200000;
CREATE SEQUENCE IF NOT EXISTS invoice_seq START 1;
"""


def init_db() -> None:
    wait_for_db()
    with connect() as conn:
        conn.execute(SCHEMA)
        if conn.execute("SELECT count(*) AS n FROM customers").fetchone()["n"] == 0:
            seed(conn)
        conn.commit()


def seed(conn) -> None:
    src = SEED_DIR / "finance" / "customers_export.csv"
    if not src.exists():
        print(f"[finance] No seed data at {src}; run the data generator first. Starting empty.")
        return
    customers, invoices, payments = [], [], []
    with open(src, encoding="cp1252", newline="") as f:
        for row in csv.DictReader(f):
            inv_no = f"INV{len(invoices) + 1:07d}"
            customers.append((row["Customer No"], row["Customer Name"], row["Student Ref"] or None))
            d, m, y = row["Invoice Date"].split("/")
            invoices.append((inv_no, row["Customer No"], row["Fee Code"], row["Academic Year"], date(int(y), int(m), int(d)),
                             parse_money(row["Invoice Amount"]), row["Account Status"]))
            paid = parse_money(row["Amount Paid"])
            if paid > 0:
                payments.append((inv_no, paid, f"SEED-{inv_no}"))
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO customers (customer_no, customer_name, student_ref) VALUES (%s,%s,%s)", customers)
        cur.executemany("INSERT INTO invoices VALUES (%s,%s,%s,%s,%s,%s,%s)", invoices)
        cur.executemany("INSERT INTO payments (invoice_no, amount, reference) VALUES (%s,%s,%s)", payments)
        cur.execute("SELECT setval('invoice_seq', %s)", (len(invoices) + 1,))
    print(f"[finance] Seeded {len(customers)} customers, {len(invoices)} invoices, {len(payments)} payments")


# --------------------------------------------------------------------------
# Nightly export
# --------------------------------------------------------------------------
def run_export() -> Path:
    DROPZONE.mkdir(parents=True, exist_ok=True)
    target = DROPZONE / f"customers_export_{datetime.now(timezone.utc):%Y%m%d}.csv"
    tmp = target.with_suffix(".tmp")
    with connect() as conn:
        rows = conn.execute("""
            SELECT c.customer_no, c.customer_name, c.student_ref, i.fee_code, i.academic_year, i.invoice_date,
                   i.amount, COALESCE(SUM(p.amount), 0) AS paid, i.status
            FROM customers c JOIN invoices i ON i.customer_no = c.customer_no
            LEFT JOIN payments p ON p.invoice_no = i.invoice_no
            GROUP BY c.customer_no, c.customer_name, c.student_ref, i.invoice_no
            ORDER BY c.customer_no""").fetchall()
    with open(tmp, "w", encoding="cp1252", errors="replace", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Customer No", "Customer Name", "Student Ref", "Fee Code", "Academic Year", "Invoice Date",
                    "Invoice Amount", "Amount Paid", "Balance", "Account Status"])
        for r in rows:
            w.writerow([r["customer_no"], r["customer_name"], r["student_ref"] or "", r["fee_code"], r["academic_year"],
                        uk_date(r["invoice_date"]), f"{r['amount']:,.2f}", f"{r['paid']:,.2f}",
                        f"{r['amount'] - r['paid']:,.2f}", r["status"]])
    tmp.replace(target)   # write-then-rename, so readers never see half a file
    print(f"[finance] Export written: {target} ({len(rows)} rows)")
    return target


def scheduler() -> None:
    last_run = None
    while True:
        now = datetime.now(timezone.utc)
        if now.strftime("%H:%M") == EXPORT_TIME_UTC and last_run != now.date():
            try:
                run_export()
            except Exception as exc:
                print(f"[finance] Export failed: {exc}")
            last_run = now.date()
        time.sleep(20)


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    threading.Thread(target=scheduler, daemon=True).start()
    yield


app = FastAPI(title="Contoso Finance", lifespan=lifespan)
app.include_router(chaos.router())


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"ErrorCode": exc.status_code, "Message": exc.detail}
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


def require_key(x_api_key: str | None) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(401, detail={"ErrorCode": "UNAUTHORISED", "Message": "Missing or invalid X-Api-Key"})


def customer_json(r: dict) -> dict:
    ref_field = "StudentReference" if v2() else "StudentRef"
    return {"CustomerNo": r["customer_no"], "CustomerName": r["customer_name"], ref_field: r["student_ref"],
            "CreatedDate": uk_date(r["created_at"].date())}


@app.get("/health")
def health():
    return {"status": "ok", "system": "finance", "schemaVersion": chaos.config.schema_version}


@app.get("/api/v1/customers")
def list_customers(page: int = 1, pageSize: int = 50, studentRef: str | None = None,
                   x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    size = max(1, min(pageSize, MAX_PAGE_SIZE))     # silently capped, like many real APIs
    page = max(1, page)
    where, params = ("WHERE student_ref = %s", [studentRef]) if studentRef else ("", [])
    with connect() as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM customers {where}", params).fetchone()["n"]
        rows = conn.execute(f"SELECT * FROM customers {where} ORDER BY customer_no LIMIT %s OFFSET %s",
                            params + [size, (page - 1) * size]).fetchall()
    return {"Page": page, "PageSize": size, "TotalRecords": total, "TotalPages": math.ceil(total / size) if total else 0,
            "Items": [customer_json(r) for r in rows]}


@app.get("/api/v1/customers/{customer_no}")
def get_customer(customer_no: str, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    with connect() as conn:
        row = conn.execute("SELECT * FROM customers WHERE customer_no = %s", (customer_no,)).fetchone()
    if not row:
        raise HTTPException(404, detail={"ErrorCode": "NOT_FOUND", "Message": f"Customer {customer_no} not found"})
    return customer_json(row)


@app.post("/api/v1/customers", status_code=201)
def create_customer(body: dict, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    name = body.get("CustomerName")
    # In v2 the field is StudentReference. A v1 caller still sending StudentRef is silently ignored.
    ref = body.get("StudentReference") if v2() else body.get("StudentRef")
    if not name:
        raise HTTPException(400, detail={"ErrorCode": "MISSING_FIELD", "Message": "CustomerName is required"})
    with connect() as conn:
        no = f"C{conn.execute('SELECT nextval(%s) AS n', ('customer_seq',)).fetchone()['n']}"
        conn.execute("INSERT INTO customers (customer_no, customer_name, student_ref) VALUES (%s,%s,%s)", (no, name, ref))
        conn.commit()
        row = conn.execute("SELECT * FROM customers WHERE customer_no = %s", (no,)).fetchone()
    return customer_json(row)


@app.get("/api/v1/invoices")
def list_invoices(customerNo: str | None = None, status: str | None = None, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    clauses, params = [], []
    if customerNo:
        clauses.append("i.customer_no = %s"); params.append(customerNo)
    if status:
        clauses.append("i.status = %s"); params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(f"""
            SELECT i.*, COALESCE(SUM(p.amount), 0) AS paid FROM invoices i
            LEFT JOIN payments p ON p.invoice_no = i.invoice_no {where}
            GROUP BY i.invoice_no ORDER BY i.invoice_no LIMIT {MAX_PAGE_SIZE}""", params).fetchall()
    return {"Items": [{"InvoiceNo": r["invoice_no"], "CustomerNo": r["customer_no"], "FeeCode": r["fee_code"],
                       "AcademicYear": r["academic_year"], "InvoiceDate": uk_date(r["invoice_date"]),
                       "Amount": money(r["amount"]), "AmountPaid": money(r["paid"]),
                       "Balance": money(r["amount"] - r["paid"]), "Status": r["status"]} for r in rows]}


@app.post("/api/v1/invoices", status_code=201)
def create_invoice(body: dict, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    for field in ("CustomerNo", "FeeCode", "AcademicYear", "Amount"):
        if not body.get(field):
            raise HTTPException(400, detail={"ErrorCode": "MISSING_FIELD", "Message": f"{field} is required"})
    amount = parse_money(body["Amount"])
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM customers WHERE customer_no = %s", (body["CustomerNo"],)).fetchone():
            raise HTTPException(404, detail={"ErrorCode": "NOT_FOUND", "Message": f"Customer {body['CustomerNo']} not found"})
        no = f"INV{conn.execute('SELECT nextval(%s) AS n', ('invoice_seq',)).fetchone()['n']:07d}"
        conn.execute("INSERT INTO invoices VALUES (%s,%s,%s,%s,%s,%s,'Open')",
                     (no, body["CustomerNo"], body["FeeCode"], body["AcademicYear"], date.today(), amount))
        conn.commit()
    return {"InvoiceNo": no, "Amount": money(amount), "Status": "Open"}


@app.post("/api/v1/payments", status_code=201)
def create_payment(body: dict, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    for field in ("InvoiceNo", "Amount"):
        if not body.get(field):
            raise HTTPException(400, detail={"ErrorCode": "MISSING_FIELD", "Message": f"{field} is required"})
    amount = parse_money(body["Amount"])
    with connect() as conn:
        inv = conn.execute("SELECT amount FROM invoices WHERE invoice_no = %s", (body["InvoiceNo"],)).fetchone()
        if not inv:
            raise HTTPException(404, detail={"ErrorCode": "NOT_FOUND", "Message": f"Invoice {body['InvoiceNo']} not found"})
        pid = conn.execute("INSERT INTO payments (invoice_no, amount, reference) VALUES (%s,%s,%s) RETURNING payment_id",
                           (body["InvoiceNo"], amount, body.get("Reference"))).fetchone()["payment_id"]
        paid = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE invoice_no = %s",
                            (body["InvoiceNo"],)).fetchone()["s"]
        status = "Settled" if paid >= inv["amount"] else "Open"
        conn.execute("UPDATE invoices SET status = %s WHERE invoice_no = %s", (status, body["InvoiceNo"]))
        conn.commit()
    return {"PaymentId": pid, "InvoiceNo": body["InvoiceNo"], "Amount": money(amount),
            "InvoiceBalance": money(inv["amount"] - paid), "InvoiceStatus": status}


@app.post("/admin/export/run")
def export_now(x_admin_token: str | None = Header(default=None)):
    if x_admin_token != chaos.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    path = run_export()
    return {"file": path.name}
