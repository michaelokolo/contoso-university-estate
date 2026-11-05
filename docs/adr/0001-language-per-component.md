# ADR 0001: Choose the language per component (Python and C#)

**Status:** Accepted · **Date:** 2026-11-05

## Context
Integration roles we target ask for different languages: some Python, some C# (.NET). Azure Functions supports both equally. Some Microsoft SDKs are stronger in .NET (Dataverse, plug-ins); Python is lighter for small event handlers and is needed for AI-200.

## Decision
Choose the language for each component by what it needs:
- **Python:** lightweight event handlers and API calls (portal, payments and events webhooks, UCAS XML processing, Microsoft Graph notifications, Moodle enrolment).
- **C#:** components where .NET tooling is stronger (CRM upsert worker with the Dataverse SDK, SIS SOAP adapter, finance file to Azure SQL with stored procedures, Dataverse plug-ins).

## Consequences
- Two toolchains in CI (Python and .NET), both deployed by the same pipeline.
- Engineers need both skills; each component's README states its language and how to run it.
