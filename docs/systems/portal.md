# Application Portal (vendor SaaS)

What the portal exposes, how it authenticates and how it behaves. Read this before building anything that talks to it.

## Interfaces

| Interface                                        | Auth            | Use                                                          |
| ------------------------------------------------ | --------------- | ------------------------------------------------------------ |
| `POST /api/v1/applications`                      | Bearer token    | Submit an application (the web form)                         |
| `GET /api/v1/applications?since=&limit=&cursor=` | Bearer token    | List applications; cursor paging, `limit` capped at 50       |
| `GET /api/v1/applications/{applicationId}`       | Bearer token    | One full application                                         |
| `PATCH /api/v1/applications/{applicationId}`     | Bearer token    | Send a status back, e.g. `{"status": "Offer - Conditional"}` |
| Webhooks (outbound)                              | HMAC signature  | The portal calls us when something happens                   |
| `/admin/webhooks`                                | `X-Admin-Token` | Set the webhook destination and secret                       |

## Payloads

Webhooks are **thin events**: they carry IDs, not the application. Fetch the full record with `GET /api/v1/applications/{applicationId}`.

```json
{
  "id": "evt_3f9a1c...",
  "type": "application.submitted",
  "created": "2026-11-23T08:30:00Z",
  "data": { "applicationId": "APP-2027-900001", "programmeCode": "...", "submittedAt": "..." }
}
```

| Event                   | When            | `data`                                          |
| ----------------------- | --------------- | ----------------------------------------------- |
| `application.submitted` | New application | `applicationId`, `programmeCode`, `submittedAt` |
| `application.updated`   | Status changed  | `applicationId`, `status`, `updatedAt`          |

## Security

Each webhook carries:

```
X-Contoso-Signature: t=<unix timestamp>,v1=<hex HMAC-SHA256 of "t.body" using the shared secret>
X-Contoso-Event-Id: evt_...
```

To verify:

1. Use the **raw request body** exactly as received; re-serialising the JSON breaks the signature.
2. Compute HMAC-SHA256 of `"<t>." + body` with the shared secret.
3. Compare with `v1` in constant time (`hmac.compare_digest`).
4. Reject timestamps older than 5 minutes (replay protection).

## Failure behaviour

- Any 2xx = delivered. Anything else, or no response within 10 seconds, is retried after 2s, 10s, 30s, 60s and 120s, then dropped.
- Receivers must respond quickly and be **idempotent**: the same event can arrive more than once.
- Chaos switches (`extra`): `duplicate_rate` (deliver twice), `out_of_order` (random delay), `bad_signature_rate` (wrong secret).

## Quirks

- Data is held **in memory**: after scaling to zero the portal starts empty, so a fetch for an older application returns 404.
- Events can arrive **out of order**: an `updated` may arrive before its `submitted`. Fetching the current record avoids acting on stale data.
