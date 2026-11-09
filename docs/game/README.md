# Contoso University: the game (design note)

> Status: **design agreed, not started.** The game begins when the first integration is live (end of Sprint 1, around 22 November 2026). The full welcome pack is written just before the first ticket.

## The idea

Contoso University has hired Michael as its **Integration Developer** (Digital Services). The university runs on its academic calendar, people raise tickets, and things break the way they do in real universities. No answers are given up front: you investigate, fix through the proper process, write it up, and every ticket becomes a STAR story in the story bank.

**Why:** a STAR example written once is not the same as a story you lived. Interview panels ask for specific, hands-on examples (troubleshooting inherited services, diagnosing failures, working with external systems, security). The game produces them.

## The cast (fictional)

| Person | Role | Typical ticket |
| --- | --- | --- |
| Priya | Head of Admissions (business owner) | "Applicants are missing from the CRM and Clearing is in 3 days!" |
| Dan | Service Desk (first line) | "Student says she paid but her account shows unpaid" |
| Grace | Information Security | "A secret has appeared in a public repo. Please respond." |
| Tom | SIS team (student record system owners) | "We're patching the SIS on Saturday, 02:00 to 06:00" |
| Vendor support | Portal, Payments, UCAS, Events | Changes announced late, or not at all |
| Your manager | Head of Integration | Priorities, change approvals, post-incident reviews |

You can ask any character questions. The game master answers as that person, with only what they would really know.

## The academic calendar (compressed into weeks)

1. **Autumn:** open days (event webhook surges), UCAS cycle opens
2. **January:** UCAS deadline (portal volume spikes, rate limits)
3. **Results day and Clearing:** the boss level (huge volume, CRM throttling, slow vendors, admissions under pressure)
4. **Enrolment:** SIS, Finance and Moodle must agree

## Ticket types (based on what really breaks in production)

| Type | Examples |
| --- | --- |
| Incident | Expired OAuth token over a weekend · vendor renames a field without notice (Finance schema v2) · rate limits as volume grows · webhooks return 200 but data is stale · one bad record breaks a batch · half-written overnight file · an older TLS version dropped |
| Silent failure | Sync reports success but some records never arrived (found by reconciliation) |
| Idempotency | A retry after a timeout creates a duplicate payment |
| Data drift | A new status value not handled · retired or renamed programmes · same applicant typed twice |
| Hidden dependency | The "CRM outage" is really the identity provider failing upstream |
| Change request | New field for Admissions · onboard a new vendor · vendor API retiring in 30 days |
| Security | Leaked secret · replayed webhooks · permissions too broad |
| Problem (ITIL) | Find the root cause behind several similar incidents |

Tickets arrive as **GitHub Issues** (incident template), with a priority **P1 to P4** and a response target.

## How a ticket is played

1. **Ticket arrives** with symptoms only, as a real user would describe them.
2. **Game master** (Claude) has quietly caused the fault beforehand: chaos panel, planted data or a configuration change.
3. **Investigate** with real tools: logs, Application Insights, correlation IDs, Postman, the code.
4. **Fix** through the proper process: branch, PR, CI, deployment, and a change approval where needed.
5. **Close properly:** incident note, root cause, what prevents a repeat. Big ones get a short post-incident review.
6. **STAR story** written the same day and added to the story bank under every question it answers.

## Answers and hints

- **Answers are never stored in this repo.** The game master keeps them and reveals them only after the ticket is closed.
- **Hints on request:** stuck for more than an hour? Ask for hint 1, then hint 2, then the answer.

## Levels and badges

Badges match what interviewers look for: *First Responder* (first P1 fixed) · *Root Cause* (a problem record solved) · *No Data Lost* (dead-letter recovery) · *Security Guardian* · *Clearing Survivor*. The story map in the Interview Hub is the progress map.

## When systems join the game

Each integration joins the game as it goes live, the way a real platform grows while you support it:

| Goes live | Joins the game |
| --- | --- |
| Sprint 1: portal → Service Bus → CRM | First tickets: webhooks, duplicates, throttling, expired credentials |
| Payments, Events | Payment reconciliation, idempotency, surges |
| Finance nightly export (CU-16) | Batch failures, encoding, schema v2 |
| SIS via APIM self-hosted gateway (CU-17) | Legacy SOAP faults, maintenance windows |
| Power Platform ALM (CU-20) | Failed solution imports, missing dependencies |
