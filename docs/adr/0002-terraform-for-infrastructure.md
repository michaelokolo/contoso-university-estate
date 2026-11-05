# ADR 0002: Terraform for infrastructure as code

**Status:** Accepted · **Date:** 2026-11-05

## Context
Every Azure resource must be repeatable across environments and reviewed like code. Options: Bicep (Azure-only, no state file) or Terraform (multi-cloud, state file). Target employers list Terraform.

## Decision
Use **Terraform**, with remote state in an Azure Storage account (one state file per environment), reusable modules, and a `.tfvars` file per environment. The Day 3 CLI deployment script is replaced by Terraform in Sprint 1.

## Consequences
- State must be protected: stored in Azure Storage with locking, never committed.
- Every infrastructure change appears as a `terraform plan` on the pull request before it's applied.
- Nothing is created by hand in the portal; manual changes are drift and will be overwritten.
