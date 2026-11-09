# Contoso University Estate

[![CI](https://github.com/michaelokolo/contoso-university-estate/actions/workflows/ci.yml/badge.svg)](https://github.com/michaelokolo/contoso-university-estate/actions/workflows/ci.yml)

Reference integration platform for **Contoso University**, a fictional UK university. It models a realistic higher education systems estate (student records, finance, admissions, payments, events, CRM and Microsoft 365) and the Azure integrations that connect them, delivered with infrastructure as code, CI/CD and multiple environments.

The estate deliberately behaves like the real thing: legacy SOAP services, nightly file exports, signed webhooks, rate limits, maintenance windows and imperfect data, so the integration patterns shown here hold up against real-world conditions.

> Contoso University is a fictional organisation. All data in this repository is generated.

## Architecture

Ten systems across three zones:

| Zone | System | Interface |
| --- | --- | --- |
| **On premises** | Student record system (SIS) | SOAP 1.1 (WSDL), pipe-delimited extracts |
| | Finance / ERP | REST (OpenAPI), nightly CSV export |
| | Virtual learning environment | Moodle web services |
| **Vendor SaaS** (Azure Container Apps) | Application portal | REST, cursor paging, signed webhooks |
| | Admissions feed | Daily XML transactions |
| | Payment provider | REST, signed webhooks |
| | Events platform | OAuth 2.0 client credentials, signed webhooks |
| **Microsoft cloud** | CRM | Dataverse |
| | Microsoft 365 | Microsoft Graph |
| | Identity | Microsoft Entra ID |

Integrations run on Azure: API Management, Functions, Service Bus, Logic Apps, Data Factory, Key Vault and Application Insights. See [docs/architecture.md](docs/architecture.md) for data ownership, identifiers across systems and known data-quality issues.

## Repository structure

| Path | Contents |
| --- | --- |
| `data-generator/` | Generates the estate's seed data (reproducible with a fixed seed) |
| `systems/` | The simulated systems and shared components (fault injection, webhooks) |
| `deploy/` | Bootstrap and deployment scripts |
| `infra/` | Terraform configuration and remote state settings |
| `docs/` | Architecture, runbooks, concepts and architecture decision records |
| `tests/` | Unit tests |

## Getting started

### Prerequisites

- Python 3.12+
- Docker Desktop
- Azure CLI and an Azure subscription (for the vendor systems)
- GitHub CLI

### 1. Generate the data

```bash
cd data-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python generate.py
```

### 2. Run the on-premises systems

```bash
cp .env.example .env
docker compose up -d --build
```

Student record system on `http://localhost:8081`, Finance on `http://localhost:8082`. See [docs/run-on-prem-systems.md](docs/run-on-prem-systems.md).

### 3. Run or deploy the vendor systems

Locally: `docker compose --profile vendors up -d --build`. To Azure: `./deploy/deploy-vendors.sh`. See [docs/deploy-vendor-systems.md](docs/deploy-vendor-systems.md).

## Delivery

- **Branching:** GitHub Flow. `main` is protected; every change goes through a pull request with passing checks.
- **CI:** lint and unit tests on every pull request.
- **CD:** build once, deploy the same artefact to dev, a short-lived test environment, then production after approval.
- **Azure access:** OIDC workload identity federation. No stored credentials.
- **Infrastructure:** Terraform with remote state in Azure Storage.

See [docs/ways-of-working.md](docs/ways-of-working.md) and the [architecture decision records](docs/adr/).

## Documentation

- [Architecture](docs/architecture.md)
- [Concepts: the real systems the estate models](docs/concepts.md)
- [Running the on-premises systems](docs/run-on-prem-systems.md)
- [Deploying the vendor systems](docs/deploy-vendor-systems.md)
- [Ways of working](docs/ways-of-working.md)
