# ADR 0003: Three environments with an ephemeral test environment

**Status:** Accepted · **Date:** 2026-11-05

## Context
We need to show changes working before production, but a permanent test environment would roughly double running costs for a small team.

## Decision
- **dev:** permanent, deployed on every merge to `main`.
- **test:** **created by the release pipeline for each release**, used for integration tests, then **destroyed**.
- **prod:** permanent, deployed only after the release passes in test **and** a required reviewer approves.

## Consequences
- Test environments are always clean and match the Terraform code exactly (no drift).
- Releases take longer (an environment is created each time), which is acceptable at our release frequency.
- The Terraform code must work from empty, which also proves disaster recovery.
