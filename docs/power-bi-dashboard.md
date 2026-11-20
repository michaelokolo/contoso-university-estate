# Admissions dashboard (Power BI)

The Admissions Overview report shows applications, offers and offer rate by faculty and status, built on a semantic model over the CRM (Dataverse).

## Semantic model

| Table       | Role                                   | Source                                                 |
| ----------- | -------------------------------------- | ------------------------------------------------------ |
| Application | Fact: one row per application          | `cu_application`                                       |
| Programme   | Dimension: faculty, level, award, mode | `cu_programme`                                         |
| Contact     | Dimension: the applicant               | Native SQL query selecting five columns from `contact` |

- **Storage mode:** Import, refreshed on a schedule. Daily data is enough for admissions reporting, and import gives fast reports and full DAX.
- **Relationships:** Application → Programme (`cu_programme` → `cu_programmeid`) and Application → Contact (`cu_applicant` → `contactid`), both many-to-one, single direction.
- **ID columns** are hidden from report view; they are used only for relationships.

## Measures

| Measure            | DAX                                                                                                            |
| ------------------ | -------------------------------------------------------------------------------------------------------------- |
| Total applications | `COUNTROWS('Application')`                                                                                     |
| Offers made        | `CALCULATE([Total applications], 'Application'[Status] IN { "Offer - Conditional", "Offer - Unconditional" })` |
| Offer rate %       | `DIVIDE([Offers made], [Total applications])`                                                                  |
| Awaiting decision  | `CALCULATE([Total applications], 'Application'[Status] = "Submitted")`                                         |

Measures were checked against known totals before building visuals: 200 applications, and a status breakdown summing to 200.

## Security

Row-level security uses one role per faculty, filtering `Programme[Faculty]`. The filter flows to Application through the relationship. Tested with "Test as role": Faculty - SCI sees 57 applications.

## Known issues and decisions

- **Contact would not load in full** through the TDS endpoint (error 8657) because the table is very wide. Loaded with a native query selecting only the columns the report needs.
- **Choice labels came through empty** (`...name` columns null) until customisations were published. The TDS endpoint reads labels from published metadata.
- **Firm acceptances and Conversion rate %** need the applicant reply column, which is filled from CU-24 (offer approvals).
