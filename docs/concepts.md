# How real university systems work, and how the estate copies them

Short explanations of the real systems our fictional ones stand in for, and the real behaviour the estate copies, so every pattern here applies to a real estate.

## Student record systems (SITS, PeopleSoft, Banner)

**What they are.** Large off-the-shelf systems that hold students, programmes, enrolments and results. **Tribal SITS** is common in UK universities; **PeopleSoft Campus Solutions** is Oracle's; **Ellucian Banner** is common in the US.

**How PeopleSoft works.** Web pages for staff and students, an application server running the business rules, and a database (usually **Oracle Database**). Oracle's toolkit, **PeopleTools**, is used to change it, in its own language, **PeopleCode**. Oracle owns and maintains it; the university configures and customises it.

**Who builds their APIs.** The vendor ships some web services. The university's own system team (or a partner) builds custom ones, in PeopleSoft's case with the **Integration Broker**. Integration engineers mostly **consume** these services and agree interfaces with the system team.

**How they're integrated in practice: a mix, depending on version and licensing.**

| Method | Typical use |
| --- | --- |
| SOAP web services | Older but common: look up or create records one at a time |
| REST APIs | Newer versions (PeopleSoft REST services, SITS's newer APIs, Banner Ethos) |
| Database views (read-only) | Reporting and bulk reads, granted by the system team |
| Scheduled file extracts and imports | Bulk nightly data in both directions |

**How people learn them.** Mostly on the job, on the employer's licensed test copies. Oracle's full demo environments are only for licensed customers and partners. Documentation (e.g. PeopleBooks) is public.

**What an integration engineer needs to know:** how the system exposes data, its key IDs and data, which data it owns, its limits and maintenance windows, basic SQL, and how its team handles changes. You don't need to write PeopleCode or administer the database.

**In the estate:** our SIS offers **SOAP** (with a WSDL), **pipe-delimited extract files**, and (story CU-18) **read-only reporting views**. It enforces legacy rules: DD-MON-YYYY dates, UPPER-CASE surnames, retired routes, duplicate checks.

## Oracle Database

**What it is.** Oracle's relational database: software that can run **on premises** (very common for student record systems), in **Oracle Cloud**, in **Azure** (Oracle Database@Azure or virtual machines), on AWS, or hosted by the vendor. Always find out where it actually lives: that decides how you connect.

**Free edition.** *Oracle AI Database 26ai Free*: the full database with limits of 2 CPUs, 2 GB of RAM and 12 GB of data, no support or patches; available as a Docker image.

**In the estate:** the SIS uses **PostgreSQL** (lighter to run locally; very similar SQL). Story CU-19 can swap it to Oracle Free later to support Oracle-specific integration work.

## Reaching "on-premises" systems from the cloud

Systems in a university's data centre aren't on the public internet. Azure services reach them through a component installed **inside** the network that connects **outwards** to Azure:

| Tool | Used by | Runs on |
| --- | --- | --- |
| **Self-hosted integration runtime** | Azure Data Factory | Windows machine inside the network |
| **On-premises data gateway** | Logic Apps, Power Platform, Power BI | Windows machine inside the network |
| **APIM self-hosted gateway** | API Management | A container (Docker / Kubernetes) inside the network |
| **Hybrid Connection Manager** | App Service, Functions (Hybrid Connections) | Windows machine inside the network |
| VPN / ExpressRoute | Anything, network-level | Network infrastructure |

**In the estate:** the laptop is the "data centre". Story CU-17 makes the SIS **reachable from Azure only through the APIM self-hosted gateway** running in Docker on the laptop, exactly as a university would expose SOAP services without opening its firewall. The Windows-only tools can't run on the Mac, so where a story would normally use them (Data Factory, CU-16) it uses an equally real alternative: **upload the file to Blob storage, then process it in the cloud**.

## Azure Data Factory

**What it is.** Azure's service for moving and transforming **bulk data** on a schedule, between 90+ sources. It works with **cloud and on-premises** data.

**Integration runtimes (the engine that does the work):**
- **Azure IR:** cloud sources and destinations; nothing to install.
- **Self-hosted IR:** on-premises and private networks; installed on Windows inside the network.
- **Azure-SSIS IR:** runs existing SSIS packages in Azure.

**Logic Apps vs Data Factory:** Logic Apps for business processes and individual messages or events; Data Factory for bulk, scheduled data movement (e.g. loading a warehouse or Fabric for reporting).

**In the estate:** story CU-16 loads the finance nightly export into Azure SQL with Data Factory (Azure IR), with a stored-procedure upsert and a failure alert.
