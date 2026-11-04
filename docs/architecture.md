# Architecture and data rules

## Zones

| Zone | Hosted on | Why |
| --- | --- | --- |
| "On premises" | Docker on the laptop | Behaves like a university data centre. Azure reaches it through the on-premises data gateway or the APIM self-hosted gateway |
| Vendor SaaS | Azure Container Apps (scale to zero) | Public HTTPS endpoints that call back with webhooks, like real vendors |
| Microsoft cloud | Test Microsoft tenant | The real products: Dataverse, Entra ID, Microsoft 365 |
| Integration layer | Azure | APIM, Functions, Service Bus, Event Grid, Logic Apps, Key Vault, App Insights |

## Who owns which data (source of truth)

Write this down before integrating. Without it, one system silently overwrites another.

| Data | Owner | Others may |
| --- | --- | --- |
| Prospects, applicants, interactions, communications | **CRM** | Read |
| Application decisions and offers | **CRM** | Read |
| UCAS applicant details and replies | **UCAS feed** (into CRM) | Read |
| Students after enrolment, programme, year of study, status | **SIS** | Read |
| Consent and marketing preferences | **CRM** | SIS receives changes |
| Fees, invoices, payments | **Finance** | Read balance only |
| Course enrolments in the VLE | **SIS** (pushed to Moodle) | Moodle never writes back |
| Accounts and sign-in | **Entra ID** | Others store the ID only |

## IDs: every system has its own

| Thing | CRM | SIS | UCAS | Finance | Portal |
| --- | --- | --- | --- | --- | --- |
| Person / applicant | GUID (Dataverse) + alternate key `APP-2027-000123` | `STU_CODE` 8 digits, e.g. `10020005` (students only) | Personal ID `123-456-7890` | Customer `C100001` | `applicationId` |
| Programme | `CS-BSC-2027` | Route `UG0401` | Course `G400` | Fee code `F-SCI-0401` | `CS-BSC-2027` |
| Academic year | `2027/28` | `2027/2028` | `EntryYear` 2027 | `AY2728` | `entryYear` |

`reference/code_map.csv` and `reference/academic_periods.csv` hold the mappings. **Integrations must translate through them.**

## Known data problems (deliberate, like production)

| Problem | Where | Rate | What it will break |
| --- | --- | --- | --- |
| Same person applies twice with details typed differently (case, spaces, accents, hyphens, email typo) | UCAS + portal | ~2% | Duplicate contacts in the CRM unless you match carefully |
| Three programmes **retired in the SIS** but still open in the CRM | Code map | 3 programmes | Creating students on a route that no longer exists |
| Two programmes **renamed in the CRM**, old title in the SIS | Code map | 2 subjects | Matching programmes by title |
| Surnames in UPPER CASE, trailing spaces | SIS extract | ~2% spaces | String comparisons, display |
| Dates as `04-NOV-2026` | SIS | All | Date parsing |
| Dates as `04/11/2026` | Finance | All | Month/day mix-ups |
| Money as `"9,535.00"` strings | Finance | All | Numeric parsing |
| File encoded as **Windows-1252**, not UTF-8 | Finance | All | Accented names turn into garbage if read as UTF-8 |
| Finance customers with no student reference | Finance | ~1% | Linking payments to students |
| Missing phone or postcode | Portal | 2–3% | Required-field validation |
| Invalid email addresses | Portal | ~0.5% | CRM validation, email sending |
| International applicants have no postcode | All | All international | Over-strict validation |
| Clearing spike: about 2,000 transactions on results day | UCAS | 12 Aug 2027 | Throttling, batch windows, queue depth |
| Accented and complex names (Siobhán, Ó Súilleabháin, O'Brien, Smith-Jones) | All | ~18% | Encoding, matching, SQL quoting |
