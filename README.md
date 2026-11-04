# Contoso University Estate

A fictional university's systems, built to practise **real integration work**: realistic data, realistic flaws, and systems that behave like the ones universities actually run.

> Personal learning project. Contoso University is fictional. No real university code, data or architecture is used.

## The estate

Ten systems in three zones, the way a real university is split:

| # | System | Zone | Plays the part of | Status |
| --- | --- | --- | --- | --- |
| 1 | CRM | Microsoft cloud | Dynamics 365 / Dataverse + Education Accelerator | Planned |
| 2 | Virtual learning environment | "On premises" (laptop) | Moodle | Planned |
| 3 | Student record system (SIS) | "On premises" (laptop) | SITS / PeopleSoft, SOAP API | **Running** (Day 2) |
| 4 | Microsoft 365 | Microsoft cloud | Outlook, Teams, SharePoint via Graph | Planned |
| 5 | Admissions feed | Vendor SaaS (Azure) | UCAS daily XML transactions | **Ready** (Day 3) |
| 6 | Application portal | Vendor SaaS (Azure) | Online application form | **Ready** (Day 3) |
| 7 | Finance / ERP | "On premises" (laptop) | Unit4 / Agresso | **Running** (Day 2) |
| 8 | Payment provider | Vendor SaaS (Azure) | Flywire / WPM, signed webhooks | **Ready** (Day 3) |
| 9 | Events platform | Vendor SaaS (Azure) | Open days, signed webhooks | **Ready** (Day 3) |
| 10 | Identity | Microsoft cloud | Entra ID | Planned |

Run the on-premises systems: [docs/day2-on-prem-systems.md](docs/day2-on-prem-systems.md).
Run and deploy the vendor systems: [docs/day3-vendor-systems.md](docs/day3-vendor-systems.md).

See [docs/architecture.md](docs/architecture.md) for who owns which data, how IDs differ between systems, and the known data problems.

## Quick start: generate the data

```bash
cd data-generator
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generate.py                   # full size, about 5 seconds
python generate.py --applications 2000 --students 500   # small test run
```

Output lands in `output/` (ignored by Git; regenerate any time, the seed makes it repeatable):

| Folder | Format | What it is |
| --- | --- | --- |
| `reference/` | CSV | Faculties, programmes, **code map** between systems, academic periods, fees |
| `ucas/` | XML, one file per day | UCAS-style APP (application) and RPL (reply) transactions |
| `portal/` | JSON Lines | Direct and postgraduate applications from the portal |
| `sis/` | Pipe-delimited text | Legacy student extract and route list |
| `finance/` | CSV, **Windows-1252** | Customer and invoice export |
| `_truth/` | JSON Lines | The answer key. **Integrations must never read this.** Use it only to check your work |

## Running it on an 8 GB Mac

Run only what you need. The light "on-premises" services (student records, finance, file drop) run together; Moodle runs on its own, with the others stopped.

## Roadmap

1. **Week 1:** systems and data (this repo)
2. **Week 2 onwards:** integrations between them on Azure (APIM, Functions, Service Bus, Event Grid, Logic Apps, Key Vault, App Insights)
3. **Then:** troubleshooting tickets with planted faults, written up as STAR stories
