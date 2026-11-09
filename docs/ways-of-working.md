# Ways of working: the Contoso Integration product team

The Contoso Integration team is a product-led team: it owns the integration platform for as long as it exists, ships small changes often, and supports what it runs. This page describes how the team works.

## The team

| Role | Responsibilities |
| --- | --- |
| Integration engineer | Picks up stories, builds, tests, opens pull requests, deploys, supports what's live |
| Product manager | Owns the backlog and priorities, writes stories with acceptance criteria, accepts work at the demo |
| Delivery manager | Runs the sprint rhythm, tracks blockers and risks |
| Reviewer | Reviews pull requests against the Definition of Done |
| The business | Admissions, Finance and Student Records raise requests and incidents |

## The product

**Contoso Integration Platform**: the integrations that connect the university's ten systems (see [architecture.md](architecture.md)). Outcomes we care about: no lost applications, data that matches across systems, failures found before users notice.

## Sprint rhythm (one-week sprints)

| When | Ceremony | What happens | Output |
| --- | --- | --- | --- |
| Monday | **Sprint planning** | Pick stories from the top of the backlog that fit the week | Stories moved to *Sprint backlog* |
| Each work session | **Stand-up note** | Three lines in the sprint issue: done, next, blocked | A comment on the sprint issue |
| Weekend | **Sprint review (demo)** | Show the working integration; the product manager accepts or rejects each story | Stories moved to *Done* |
| Weekend | **Retrospective** | What went well, what didn't, one improvement for next sprint | A short entry in `backlog/retros.md` |

Capacity is agreed at sprint planning. Story points: 1, 2, 3, 5, 8. Anything bigger than 8 gets split.

## The board (GitHub Projects)

Columns: **Backlog → Ready → In progress → In review → Done**. Work-in-progress limit: **2** in *In progress*.

**Definition of Ready** (before a story enters a sprint):
- Written as *As a… I want… so that…*
- Has acceptance criteria someone could test
- Dependencies known; estimated

**Definition of Done** (before a story is accepted):
- [ ] Code merged to `main` through a reviewed pull request
- [ ] Automated tests added and passing in CI
- [ ] Infrastructure changes in Terraform (nothing clicked by hand in the portal)
- [ ] Deployed to **dev** and **test** by the pipeline
- [ ] Monitoring in place: logs, a correlation ID, and an alert for the failure path
- [ ] Docs updated (README or runbook)
- [ ] Demoed and accepted

## Branching: GitHub Flow

- `main` is always deployable and **protected**: no direct pushes, pull request + passing checks required.
- One short-lived branch per story, named after the issue:
  `feature/CU-12-portal-webhook`, `fix/CU-27-duplicate-contacts`, `chore/CU-3-terraform-state`
- Merge within a day or two; rebase on `main` if it drifts.
- **Squash merge**, so each story is one clean commit on `main`.

**Commit messages:** [Conventional Commits](https://www.conventionalcommits.org/), e.g. `feat(portal): receive application webhooks`, `fix(crm): upsert by alternate key`, `chore(ci): cache pip`.

## Pull requests

Every PR uses the template in `.github/pull_request_template.md`: what changed and why, how it was tested, risks and rollback, and the linked issue (`Closes #12`).

Required to merge: **CI green** + **review approved**.

## CI/CD (GitHub Actions)

| Trigger | Pipeline | Does |
| --- | --- | --- |
| Pull request | **CI** | Lint, unit tests, `terraform fmt` and `validate`, `terraform plan` (from Sprint 1) |
| Merge to `main` | **CD** | Build once, deploy to **dev** automatically |
| Release tag `v*` | **Release** | Create an **ephemeral test** environment, run integration tests, destroy it, then deploy to **prod** after approval |

Azure sign-in uses **OIDC (federated credentials)**: GitHub gets a short-lived token per run. No Azure passwords or secrets are stored in GitHub.

## Environments

| Environment | Lifetime | Deployed by | Approval |
| --- | --- | --- | --- |
| `dev` | Always on (scales to zero) | Every merge to `main` | None |
| `test` | **Created per release, destroyed after tests** | Release pipeline | None |
| `prod` | Always on, smallest sizes | Release pipeline | **Required reviewer** |

Configuration differs per environment through Terraform variable files (`dev.tfvars`, `test.tfvars`, `prod.tfvars`) and Key Vault, never through code changes.

## Incidents and problems (ITIL-style)

- An **incident** is something broken now ("applications aren't reaching the CRM"). Raise it with the *Incident* issue template, label `incident`, severity S1–S4.
- Restore service first, then find the cause.
- If the cause needs lasting work, open a **problem** linked to the incident.
- Close every incident with a short **post-incident review**: timeline, impact, root cause, fix, prevention.

## Architecture decisions

Significant decisions are recorded as short **ADRs** in `docs/adr/`: the context, the decision, and the consequences.
