"""Contoso Student Record System (SIS): a legacy SOAP service.

Behaves like an older student record system (think SITS or PeopleSoft):
    - SOAP 1.1, document/literal, described by a WSDL
    - HTTP Basic authentication
    - dates must be DD-MON-YYYY; ISO dates are rejected
    - surnames stored in upper case
    - no index on surname or email (searches get slow as data grows)

Endpoints
    POST /sis/StudentService          SOAP operations
    GET  /sis/StudentService?wsdl     the WSDL
    GET  /health                      health check
    /admin/chaos                      chaos panel (see common/chaos.py)
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from lxml import etree

from common.chaos import Chaos
from common.db import connect, wait_for_db

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS = "urn:contoso:sis:v1"
NSMAP = {"soap": SOAP_NS, "tns": TNS}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
SIS_DATE = re.compile(r"^(\d{2})-([A-Z]{3})-(\d{4})$")
WSDL_PATH = Path(__file__).parent / "wsdl" / "StudentService.wsdl"

SIS_USER = os.environ.get("SIS_USER", "integration")
SIS_PASSWORD = os.environ.get("SIS_PASSWORD", "change-me")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8081")
SEED_DIR = Path(os.environ.get("SEED_DIR", "/seed"))


# --------------------------------------------------------------------------
# SOAP helpers
# --------------------------------------------------------------------------
class SisFault(Exception):
    def __init__(self, code: str, message: str, client_error: bool = True):
        self.code, self.message, self.client_error = code, message, client_error


def envelope(body_child: etree._Element) -> bytes:
    env = etree.Element(f"{{{SOAP_NS}}}Envelope", nsmap=NSMAP)
    body = etree.SubElement(env, f"{{{SOAP_NS}}}Body")
    body.append(body_child)
    return etree.tostring(env, xml_declaration=True, encoding="utf-8")


def fault_response(status: int, code: str, message: str, client_error: bool = True,
                   headers: dict[str, str] | None = None) -> Response:
    fault = etree.Element(f"{{{SOAP_NS}}}Fault")
    etree.SubElement(fault, "faultcode").text = "soap:Client" if client_error else "soap:Server"
    etree.SubElement(fault, "faultstring").text = message
    detail = etree.SubElement(fault, "detail")
    err = etree.SubElement(detail, f"{{{TNS}}}SisError")
    etree.SubElement(err, f"{{{TNS}}}Code").text = code
    etree.SubElement(err, f"{{{TNS}}}Message").text = message
    return Response(envelope(fault), status_code=status, media_type="text/xml; charset=utf-8", headers=headers or {})


def chaos_error(status: int, message: str, headers: dict[str, str]) -> Response:
    code = {429: "RATE_LIMITED", 503: "UNAVAILABLE"}.get(status, "SERVER_ERROR")
    return fault_response(status, code, message, client_error=False, headers=headers)


def el(parent: etree._Element, name: str, value) -> None:
    etree.SubElement(parent, f"{{{TNS}}}{name}").text = "" if value is None else str(value)


def text(req: etree._Element, name: str, required: bool = True) -> str | None:
    node = req.find(f"tns:{name}", NSMAP)
    value = node.text.strip() if node is not None and node.text else None
    if required and not value:
        raise SisFault("MISSING_FIELD", f"{name} is required")
    return value


def parse_sis_date(value: str) -> date:
    m = SIS_DATE.match(value or "")
    if not m or m.group(2) not in MONTHS:
        raise SisFault("INVALID_DATE", f"Date '{value}' must be in DD-MON-YYYY format, e.g. 04-NOV-2026")
    return date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1)))


def format_sis_date(d: date | None) -> str:
    return "" if d is None else f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def student_xml(parent: etree._Element, row: dict) -> None:
    s = etree.SubElement(parent, f"{{{TNS}}}Student")
    el(s, "StudentCode", row["stu_code"])
    el(s, "Surname", row["surname"])
    el(s, "Forename", row["forename"])
    el(s, "DateOfBirth", format_sis_date(row["dob"]))
    el(s, "Email", row["email"])
    el(s, "Postcode", row["postcode"])
    el(s, "FeeStatus", row["fee_status"])
    el(s, "RouteCode", row["route_code"])
    el(s, "EntryYear", row["entry_year"])
    el(s, "YearOfStudy", row["year_of_study"])
    el(s, "Status", row["status"])


# --------------------------------------------------------------------------
# Database: schema and seed data
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    route_code   varchar(6) PRIMARY KEY,
    route_name   varchar(200) NOT NULL,
    level        varchar(2) NOT NULL,
    status       char(1) NOT NULL            -- A = active, R = retired
);
CREATE TABLE IF NOT EXISTS students (
    stu_code      varchar(8) PRIMARY KEY,
    surname       varchar(100) NOT NULL,     -- stored in UPPER CASE
    forename      varchar(100) NOT NULL,
    dob           date NOT NULL,
    email         varchar(200) NOT NULL,     -- no index: searches scan the table
    postcode      varchar(10),
    fee_status    char(1) NOT NULL,          -- H = home, O = overseas
    route_code    varchar(6) NOT NULL REFERENCES routes(route_code),
    entry_year    int NOT NULL,
    year_of_study int NOT NULL,
    status        char(2) NOT NULL,          -- EN, IN, WD
    created_at    timestamp NOT NULL DEFAULT now(),
    updated_at    timestamp NOT NULL DEFAULT now()
);
CREATE SEQUENCE IF NOT EXISTS stu_code_seq START 10100000;
"""


def init_db() -> None:
    wait_for_db()
    with connect() as conn:
        conn.execute(SCHEMA)
        if conn.execute("SELECT count(*) AS n FROM routes").fetchone()["n"] == 0:
            seed(conn)
        conn.commit()


def seed(conn) -> None:
    routes_file, students_file = SEED_DIR / "sis" / "ROUTES.txt", SEED_DIR / "sis" / "STU_EXTRACT.txt"
    if not routes_file.exists():
        print(f"[sis] No seed data at {routes_file}; run the data generator first. Starting empty.")
        return
    with open(routes_file, encoding="utf-8") as f:
        next(f)
        rows = [line.rstrip("\n").split("|") for line in f if line.strip()]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO routes VALUES (%s, %s, %s, %s)", rows)
    with open(students_file, encoding="utf-8") as f:
        next(f)
        students = []
        for line in f:
            c = line.rstrip("\n").split("|")
            if len(c) < 11:
                continue
            students.append((c[0], c[1], c[2], parse_sis_date(c[3]), c[4], c[5] or None, c[6], c[7],
                             int(c[8]), int(c[9]), c[10]))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO students (stu_code, surname, forename, dob, email, postcode, fee_status, route_code,"
            " entry_year, year_of_study, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", students)
    print(f"[sis] Seeded {len(rows)} routes and {len(students)} students")


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------
def op_get_student(req: etree._Element) -> etree._Element:
    code = text(req, "StudentCode")
    with connect() as conn:
        row = conn.execute("SELECT * FROM students WHERE stu_code = %s", (code,)).fetchone()
    if not row:
        raise SisFault("NOT_FOUND", f"Student {code} not found")
    resp = etree.Element(f"{{{TNS}}}GetStudentResponse")
    student_xml(resp, row)
    return resp


def op_find_students(req: etree._Element) -> etree._Element:
    surname = text(req, "Surname").upper()
    dob = text(req, "DateOfBirth", required=False)
    sql = "SELECT * FROM students WHERE upper(trim(surname)) LIKE %s"
    params: list = [surname + "%"]
    if dob:
        sql += " AND dob = %s"
        params.append(parse_sis_date(dob))
    with connect() as conn:
        rows = conn.execute(sql + " ORDER BY stu_code LIMIT 50", params).fetchall()
    resp = etree.Element(f"{{{TNS}}}FindStudentsResponse")
    for row in rows:
        student_xml(resp, row)
    return resp


def op_list_routes(req: etree._Element) -> etree._Element:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM routes ORDER BY route_code").fetchall()
    resp = etree.Element(f"{{{TNS}}}ListRoutesResponse")
    for r in rows:
        route = etree.SubElement(resp, f"{{{TNS}}}Route")
        el(route, "RouteCode", r["route_code"])
        el(route, "RouteName", r["route_name"])
        el(route, "Level", r["level"])
        el(route, "Status", r["status"])
    return resp


def op_create_student(req: etree._Element) -> etree._Element:
    forename, surname = text(req, "Forename"), text(req, "Surname").upper()
    dob = parse_sis_date(text(req, "DateOfBirth"))
    email, postcode = text(req, "Email"), text(req, "Postcode", required=False)
    fee_status, route_code = text(req, "FeeStatus"), text(req, "RouteCode")
    entry_year = int(text(req, "EntryYear"))
    if fee_status not in ("H", "O"):
        raise SisFault("INVALID_FEE_STATUS", "FeeStatus must be H (home) or O (overseas)")
    with connect() as conn:
        route = conn.execute("SELECT status FROM routes WHERE route_code = %s", (route_code,)).fetchone()
        if not route:
            raise SisFault("ROUTE_NOT_FOUND", f"Route {route_code} does not exist")
        if route["status"] != "A":
            raise SisFault("ROUTE_RETIRED", f"Route {route_code} is retired and cannot accept new students")
        existing = conn.execute("SELECT stu_code FROM students WHERE lower(email) = lower(%s) AND dob = %s",
                                (email, dob)).fetchone()
        if existing:
            raise SisFault("DUPLICATE_STUDENT", f"A student with this email and date of birth already exists: "
                                                f"{existing['stu_code']}")
        code = str(conn.execute("SELECT nextval('stu_code_seq') AS n").fetchone()["n"])
        conn.execute(
            "INSERT INTO students (stu_code, surname, forename, dob, email, postcode, fee_status, route_code,"
            " entry_year, year_of_study, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,'EN')",
            (code, surname, forename, dob, email, postcode, fee_status, route_code, entry_year))
        conn.commit()
    resp = etree.Element(f"{{{TNS}}}CreateStudentResponse")
    el(resp, "StudentCode", code)
    return resp


def op_update_status(req: etree._Element) -> etree._Element:
    code, status = text(req, "StudentCode"), text(req, "Status")
    if status not in ("EN", "IN", "WD"):
        raise SisFault("INVALID_STATUS", "Status must be EN, IN or WD")
    with connect() as conn:
        n = conn.execute("UPDATE students SET status = %s, updated_at = now() WHERE stu_code = %s",
                         (status, code)).rowcount
        conn.commit()
    if not n:
        raise SisFault("NOT_FOUND", f"Student {code} not found")
    resp = etree.Element(f"{{{TNS}}}UpdateStudentStatusResponse")
    el(resp, "Result", "OK")
    return resp


OPERATIONS = {
    "GetStudentRequest": op_get_student,
    "FindStudentsRequest": op_find_students,
    "ListRoutesRequest": op_list_routes,
    "CreateStudentRequest": op_create_student,
    "UpdateStudentStatusRequest": op_update_status,
}


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    yield


app = FastAPI(title="Contoso SIS", lifespan=lifespan)
chaos = Chaos("Student Record System", chaos_error)
app.include_router(chaos.router())


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    failure = await chaos.apply(request)
    return failure if failure is not None else await call_next(request)


def authorised(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return secrets.compare_digest(user, SIS_USER) and secrets.compare_digest(password, SIS_PASSWORD)


@app.get("/health")
def health():
    return {"status": "ok", "system": "sis", "time": datetime.utcnow().isoformat() + "Z"}


@app.get("/sis/StudentService")
def wsdl(request: Request):
    if "wsdl" not in request.query_params:
        return Response("Add ?wsdl to get the service description", media_type="text/plain")
    return Response(WSDL_PATH.read_text().replace("__PUBLIC_URL__", PUBLIC_URL), media_type="text/xml")


@app.post("/sis/StudentService")
async def soap(request: Request):
    if not authorised(request):
        return Response("Unauthorized", status_code=401, headers={"WWW-Authenticate": 'Basic realm="SIS"'})
    raw = await request.body()
    try:
        doc = etree.fromstring(raw)
        body = doc.find("soap:Body", NSMAP)
        req = body[0]
    except Exception:
        return fault_response(500, "MALFORMED_REQUEST", "Request is not a valid SOAP 1.1 envelope")
    name = etree.QName(req).localname
    handler = OPERATIONS.get(name)
    if handler is None or etree.QName(req).namespace != TNS:
        return fault_response(500, "UNKNOWN_OPERATION", f"Unknown operation {name}")
    slow = chaos.config.extra.get("slow_search_ms") if name == "FindStudentsRequest" else None
    if slow:
        await asyncio.sleep(int(slow) / 1000)
    try:
        result = await asyncio.to_thread(handler, req)
    except SisFault as f:
        return fault_response(500, f.code, f.message, f.client_error)
    except Exception as exc:  # a real legacy system leaks errors like this
        return fault_response(500, "SERVER_ERROR", f"Unexpected error: {type(exc).__name__}", client_error=False)
    return Response(envelope(result), media_type="text/xml; charset=utf-8")
