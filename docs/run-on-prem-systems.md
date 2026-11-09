# Running the on-premises systems

Two systems that behave like the old, in-house systems a university runs in its own data centre.

| System | URL on your Mac | Style | Auth |
| --- | --- | --- | --- |
| Student Record System (SIS) | http://localhost:8081 | SOAP 1.1 + WSDL | HTTP Basic (`SIS_USER` / `SIS_PASSWORD`) |
| Finance (ERP) | http://localhost:8082 | REST/JSON + nightly CSV export | `X-Api-Key` header |
| PostgreSQL (both databases) | localhost:**5433** | SQL | `postgres` / `DB_PASSWORD` |

## Start it (about 10 minutes the first time)

```bash
cd contoso-university-estate
cp .env.example .env          # then edit .env and change every value
python3 data-generator/generate.py   # if you haven't generated data yet (inside the venv)
docker compose up -d --build
docker compose logs sis finance      # expect "Seeded 126 routes and 6000 students" and "Seeded ... customers"
```

Check both are alive:

```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
```

The services seed themselves from `output/` the first time. To start again from fresh data: `docker compose down -v`, regenerate, then `docker compose up -d`.

Memory: about 600 MB in total. Stop it when you're not using it: `docker compose stop`.

## Try the SIS (SOAP)

Open the WSDL in a browser: http://localhost:8081/sis/StudentService?wsdl

Call it from the terminal (replace the password with yours from `.env`):

```bash
curl -s -u integration:YOUR_SIS_PASSWORD \
  -H "Content-Type: text/xml; charset=utf-8" \
  --data @samples/sis/GetStudent.xml \
  http://localhost:8081/sis/StudentService
```

Then try `samples/sis/CreateStudent.xml`. Run it twice: the second time you get a `DUPLICATE_STUDENT` fault. Change the date to `2008-12-10` and you get `INVALID_DATE`.

**Tip:** import the WSDL into Postman (*Import → paste the WSDL URL*) to get every operation ready to call.

## Try Finance (REST)

```bash
K="X-Api-Key: YOUR_FINANCE_API_KEY"
curl -s -H "$K" "http://localhost:8082/api/v1/customers?pageSize=5"
curl -s -H "$K" "http://localhost:8082/api/v1/invoices?customerNo=C100001"
```

Interactive docs (try every endpoint in the browser): http://localhost:8082/docs

Run the nightly export now instead of waiting for 02:00 UTC:

```bash
curl -s -X POST -H "X-Admin-Token: YOUR_ADMIN_TOKEN" http://localhost:8082/admin/export/run
ls dropzone/finance
```

## Behaviour you will meet later (on purpose)

| System | Behaviour | Why it's there |
| --- | --- | --- |
| SIS | Rejects ISO dates; wants `DD-MON-YYYY` | Data transformation |
| SIS | Surnames stored in UPPER CASE | Matching and display |
| SIS | `ROUTE_RETIRED` fault for three routes still open in the CRM | Reference data drift |
| SIS | `DUPLICATE_STUDENT` fault on same email + date of birth | Idempotency |
| SIS | No index on surname or email | Performance diagnosis |
| SIS | Errors come back as HTTP 500 with a SOAP Fault, even for bad input | Reading legacy errors |
| Finance | `pageSize` silently capped at 100 | "Only the first 100 records sync" |
| Finance | Same payment sent twice is recorded twice | Idempotency |
| Finance | Schema v2 renames `StudentRef` to `StudentReference`; v1 callers silently lose the field | Upstream schema change |
| Finance | Export is Windows-1252, money as `"9,535.00"`, dates `dd/mm/yyyy` | File parsing |
| Both | One database connection per request | Connection overhead under load |

## The chaos panel

Both systems can be made to misbehave without touching their code. These are the switches your troubleshooting tickets will flip.

```bash
A="X-Admin-Token: YOUR_ADMIN_TOKEN"
curl -s -H "$A" http://localhost:8081/admin/chaos                         # see settings
curl -s -X PUT -H "$A" -H "Content-Type: application/json" \
  -d '{"latency_ms": 3000}' http://localhost:8081/admin/chaos             # every call takes 3s
curl -s -X PUT -H "$A" -H "Content-Type: application/json" \
  -d '{"rate_limit_per_minute": 30, "retry_after_seconds": 20}' http://localhost:8081/admin/chaos
curl -s -X POST -H "$A" http://localhost:8081/admin/chaos/reset          # back to normal
```

| Setting | Effect |
| --- | --- |
| `latency_ms`, `jitter_ms` | Slow responses |
| `error_rate` (0–1), `error_status` | A share of calls fail |
| `rate_limit_per_minute`, `retry_after_seconds` | 429 with `Retry-After` |
| `maintenance` | Everything returns 503 |
| `maintenance_window_utc` | 503 every day in that window, e.g. `"02:00-02:30"` |
| `schema_version` | `"v2"` changes field names (Finance) |
| `extra.slow_search_ms` | Slows `FindStudents` only (SIS) |

Health checks and admin calls are never affected, which is realistic: a system can report "healthy" while failing real requests.
