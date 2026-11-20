# Retrospectives

One entry per sprint: what went well, what didn't, one improvement.

## Sprint 0

- Went well: The estate is running and seeded end to end: on-premises systems locally, vendor systems in Azure, the CRM loaded and reconciled, and a secured Power BI report. CI blocks failing changes, and GitHub signs in to Azure with OIDC and no stored secrets.
- Didn't go well: I moved very fast through a lot of new technology, and it was easy to finish a setup step without fully understanding what it created, so I later had to rediscover how parts of the estate fit together. The sprint also overran: it was due on 15 November, finished on 20 November, and CU-6 and CU-7 were not started, partly because new Power Platform stories were added mid-sprint.
- One improvement: For every setup step in Sprint 1, write down in docs/architecture.md what it created, where it lives and why, before moving on.
