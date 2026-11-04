# Day 3: the vendor (SaaS) systems

Four external companies Contoso University buys services from. Each has its own API style, its own way of authenticating, and its own quirks, exactly like real vendors.

| System | Plays the part of | Auth | How it talks to the university |
| --- | --- | --- | --- |
| **Application Portal** | An online application form vendor | `Authorization: Bearer <key>` | REST API with cursor paging + **webhooks** (`application.submitted`, `application.updated`) |
| **UCAS Link** (fictional) | UCAS daily data downloads | `X-Provider-Key` header | **Daily XML files** you download; a new one appears each day |
| **Contoso Pay** | A payment provider (Flywire, WPM, Stripe) | `Authorization: Bearer sk_test_...` | Payment requests API + **signed webhooks** (`payment.succeeded`, `payment.failed`) |
| **Contoso Events** | An events platform (Eventbrite, Cvent) | **OAuth 2.0 client credentials** (tokens expire) | REST API with page numbers + webhooks (`registration.created`, `attendee.checked_in`) |

## Step 1: run them locally first (5 minutes, no cost)

Add the new values to your `.env` (copy the "Vendor systems" block from `.env.example` and change each value), then:

```bash
docker compose --profile vendors up -d --build
for p in 8083 8084 8085 8086; do curl -s localhost:$p/health; echo; done
```

Interactive API docs for each: http://localhost:8083/docs, http://localhost:8084/docs, http://localhost:8085/docs, http://localhost:8086/docs

### Watch webhooks arrive

In a second terminal (inside the data-generator venv, which already has the packages):

```bash
pip install fastapi uvicorn
WEBHOOK_SECRET=<your WEBHOOK_SECRET from .env> python tools/webhook_receiver.py
```

Then make the portal simulate 10 applicants:

```bash
curl -s -X POST -H "X-Admin-Token: <ADMIN_TOKEN>" -H "Content-Type: application/json" \
  -d '{"count": 10, "interval_ms": 1000}' http://localhost:8083/admin/simulate
```

The receiver prints each `application.submitted` event with `signature=ok`. That's a real signed webhook, verified exactly as you'll do it in an Azure Function next week.

## Step 2: set a budget alert (5 minutes, before deploying)

Azure portal → **Cost Management** → **Budgets** → **Add**:

1. Scope: your subscription. Name: `contoso-estate`. Reset: Monthly. Amount: **£40**.
2. Alert conditions: **Actual 50%** and **Actual 90%**, plus **Forecasted 100%**.
3. Alert recipients: your personal email. **Create**.

## Step 3: deploy to Azure (about 15 minutes)

```bash
brew install azure-cli      # if you don't have it
az login                    # your PERSONAL Azure account
./deploy/deploy-vendors.sh
```

The script builds the images **inside Azure** (no local Docker needed), creates the four apps with secrets held as Container Apps secrets, and saves every URL and secret to `deploy/.vendors.env` (ignored by Git).

Check them:

```bash
source deploy/.vendors.env
curl -s "$UCAS_URL/health"
curl -s -H "X-Provider-Key: $UCAS_PROVIDER_KEY" "$UCAS_URL/link/v1/files?from=2026-11-01"
```

The first call after a quiet period takes 10–20 seconds while the app **scales up from zero**. That's normal, and it's a real-world behaviour worth knowing ("cold start").

### Webhooks from Azure

The Azure copies have no webhook destination yet. In Week 2 you'll build an Azure Function to receive them and point the vendors at it:

```bash
curl -s -X PUT -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://<your-function>/api/webhooks/payments", "secret": "'"$WEBHOOK_SECRET"'"}' \
  "$PAYMENTS_URL/admin/webhooks"
```

## Try each vendor

```bash
source deploy/.vendors.env     # or use localhost URLs and your .env values

# Portal: list applications, following nextCursor until it is null
curl -s -H "Authorization: Bearer $PORTAL_API_KEY" "$PORTAL_URL/api/v1/applications?limit=5"

# UCAS: jump the cycle clock to results day (Clearing) and download that file
curl -s -X PUT -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"today": "2027-08-12"}' "$UCAS_URL/admin/clock"
curl -s -H "X-Provider-Key: $UCAS_PROVIDER_KEY" "$UCAS_URL/link/v1/files/ucas_20270812.xml" | head -20

# Payments: request a deposit, then play the applicant paying
curl -s -X POST -H "Authorization: Bearer $PAYMENTS_SECRET_KEY" -H "Content-Type: application/json" \
  -d '{"reference": "INV0005817", "amount": "500.00", "currency": "GBP", "payerEmail": "ada@example.com"}' \
  "$PAYMENTS_URL/v1/payment-requests"
curl -s -X POST -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"outcome": "succeeded"}' "$PAYMENTS_URL/admin/simulate/pay/<pr_id from above>"

# Events: get an OAuth token, then call the API with it
TOKEN=$(curl -s -X POST -d "grant_type=client_credentials&client_id=contoso-university&client_secret=$EVENTS_CLIENT_SECRET" \
  "$EVENTS_URL/oauth/token" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" "$EVENTS_URL/api/v2/events" | head -c 400
```

## Behaviour you will meet later (on purpose)

| Vendor | Behaviour | What it teaches |
| --- | --- | --- |
| All with webhooks | Signed with HMAC-SHA256 (`X-Contoso-Signature: t=...,v1=...`) | Verifying signatures, replay protection |
| All with webhooks | Retries with back-off when you don't answer 2xx | Respond fast, process later (queue) |
| All with webhooks | The same event can arrive twice; order isn't guaranteed | Idempotency on the event ID |
| Portal | Cursor paging, `limit` capped at 50 | Following `nextCursor` |
| Portal | Data lives in memory; empties when it scales to zero | Don't treat a vendor as your database |
| UCAS | A new file appears each day; the clock can jump to results day | Scheduled file pickup, the Clearing spike |
| Events | OAuth tokens expire (default 1 hour) | Caching and refreshing tokens |
| Events | Page-number paging (`page`, `perPage`, `totalPages`) | Different vendors page differently |
| Payments | Amounts are decimal strings; currency upper-cased | Money handling |

## Chaos switches for vendors

On top of the standard chaos panel (latency, errors, 429s, maintenance; see Day 2), vendors have these `extra` switches:

| Switch | System | Effect |
| --- | --- | --- |
| `{"extra": {"duplicate_rate": 0.3}}` | Webhook senders | 30% of webhooks are delivered twice |
| `{"extra": {"out_of_order": true}}` | Webhook senders | Random delays, so events arrive out of order |
| `{"extra": {"bad_signature_rate": 0.1}}` | Webhook senders | 10% of webhooks have an invalid signature |
| `{"extra": {"late_file": true}}` | UCAS | Today's file isn't published yet |
| `{"extra": {"truncated_file": true}}` | UCAS | Today's file is cut in half (invalid XML) |
| `{"extra": {"token_ttl_seconds": 60}}` | Events | Tokens expire after 60 seconds |

Admin endpoints for webhooks: `GET /admin/webhooks/deliveries` (what was sent and the response), `POST /admin/webhooks/redeliver/{event_id}`.

## Cost and clean-up

| Resource | Rough cost |
| --- | --- |
| Container Registry (Basic) | About £4 a month |
| Container Apps (scale to zero) | Usually within the free monthly grant at lab volumes |
| Log Analytics (created with the environment) | Pennies at lab volumes |

Delete everything when you no longer need it: `./deploy/teardown-vendors.sh`.
