# 🦅 FFIEC Toolkit
### Centralized Financial Institution Data Explorer
*William & Mary — AI Final Project*

---

```
███████╗███████╗██╗███████╗ ██████╗    ████████╗ ██████╗  ██████╗ ██╗     ██╗  ██╗██╗████████╗
██╔════╝██╔════╝██║██╔════╝██╔════╝    ╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██║ ██╔╝██║╚══██╔══╝
█████╗  █████╗  ██║█████╗  ██║            ██║   ██║   ██║██║   ██║██║     █████╔╝ ██║   ██║
██╔══╝  ██╔══╝  ██║██╔══╝  ██║            ██║   ██║   ██║██║   ██║██║     ██╔═██╗ ██║   ██║
██║     ██║     ██║███████╗╚██████╗       ██║   ╚██████╔╝╚██████╔╝███████╗██║  ██╗██║   ██║
╚═╝     ╚═╝     ╚═╝╚══════╝ ╚═════╝       ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝
```

---

## 📋 Table of Contents

- [Why This Matters](#-why-this-matters)
- [Authors](#-authors)
- [Project Scope](#-project-scope)
- [Project Details](#-project-details)
- [Architecture Overview](#-architecture-overview)
- [What's Next](#-whats-next)
- [Responsible AI Considerations](#-responsible-ai-considerations)
- [References](#-references)

---

## 💡 Why This Matters

Financial institutions in the United States are required to file **Call Reports** — standardized quarterly disclosures of their financial condition — with the **Federal Financial Institutions Examination Council (FFIEC)**. These reports contain some of the most comprehensive and granular data on the health of the U.S. banking system, covering everything from loan portfolios to capital adequacy ratios.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     THE DATA ACCESS PROBLEM                                 │
│                                                                             │
│   📄 10,000+ banks        🌐 FFIEC Portal         😤 Analysts Today        │
│   file quarterly   ──►    Raw .zip / XBRL    ──►   Manual downloads         │
│   call reports            XML bundles              Fragmented queries       │
│                                                     Hours of prep work      │
│                                                                             │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│   📄 10,000+ banks        🦅 FFIEC Toolkit        ✅ Analysts Now          │
│   file quarterly   ──►    Auto-ingestion     ──►   One search bar           │
│   call reports            BigQuery backend         Instant results          │
│                           NLP query layer           Historical trends       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**The business case is significant.** Regulatory analysts, compliance officers, risk managers, and researchers regularly need to cross-reference historical call report data across institutions and time periods. Today, that process involves navigating multiple FFIEC portals, manually downloading ZIP archives, parsing obscure XBRL schemas, and stitching together spreadsheets — a workflow that can consume days of work for a single analysis.

The FFIEC Toolkit automates this entire pipeline: from bulk ingestion of XBRL call report bundles, to structured storage in Google BigQuery, to natural-language querying via an integrated LLM interface — making institutional financial data as accessible as a Google search.

---

## 👥 Authors

| Name | Role |
|------|------|
| **Tai Chirasittikorn** | Student |
| **Pranav Prathap** | Student |
| **Daniel Robbins** | Student |
| **Ashley Gasswint** | Student |

*MS in Business Analytics | William & Mary, Class of 2026*

---

## 🎯 Project Scope

This project is **narrowly focused** on the following pipeline:

> **Automated ingestion, parsing, and natural-language querying of FFIEC Call Report data (FFIEC 031, 041, and 051 forms) from 2001 to present, stored in Google BigQuery and surfaced through a Streamlit web application.**

### In Scope

- Bulk downloading of quarterly Call Report ZIP bundles from the FFIEC Central Data Repository (CDR)
- XBRL/XML parsing of call report financial schedules into structured tabular records
- Storage and deduplication of records in Google BigQuery
- A Streamlit UI for manual date-range selection and smart catch-up updates
- A natural language query interface (LLM Assist) for querying the database without SQL knowledge
- Database maintenance tools (deduplication, period reset)

### Out of Scope

- Real-time or intraday financial data feeds
- Non-FFIEC regulatory filings (e.g., FR Y-9C, HMDA)
- Multi-user authentication or enterprise access control
- Mobile application development

---

## 🔧 Project Details

### Tech Stack

```
┌──────────────────────────────────────────────────────┐
│                   USER INTERFACE                     │
│              Streamlit (Python)                      │
│   Home  │  Fetch Tool  │  LLM Assist  │  Maintenance │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│                 APPLICATION LAYER                    │
│                                                      │
│  update_engine.py                                    │
│  ├── run_bulk_download()  ← Playwright/Selenium      │
│  ├── run_bulk_parse()     ← lxml / XBRL parsing      │
│  └── wipe_period()        ← BigQuery DML             │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│                  DATA LAYER                          │
│                                                      │
│         Google BigQuery (ffiec_data dataset)         │
│  ┌─────────────────────┐  ┌───────────────────────┐  │
│  │ call_reports_       │  │   migration_log       │  │
│  │ financials          │  │   (status tracking)   │  │
│  └─────────────────────┘  └───────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Module 1 — API Fetch Tool (`pages/1_Fetch_Tool.py`)

The Fetch Tool provides a query interface into the `call_reports_financials` BigQuery table. Users can filter by institution name, RSSD ID, XBRL tag, and date range to retrieve specific financial data points. Results are displayed as interactive DataFrames exportable to CSV.

### Module 2 — Bulk Update Database Tool (`Home.py`)

This is the core data ingestion module. It operates in two modes:

**Smart Catch-up Mode** scans the FFIEC CDR server for available report dates, compares them against the `migration_log` table in BigQuery, and downloads only the missing periods. This prevents re-processing of already-ingested data.

**Specific Date Range Mode** allows users to select a start and end quarter (Q1–Q4) and year (2001 to present) via dropdown menus. The UI validates that the end date is not before the start date before allowing submission.

Both modes follow a two-phase pipeline:

```
Phase 1: Download (0% → 50% progress)
  └── Browser automation fetches .zip bundles from FFIEC CDR

Phase 2: Parse & Push (50% → 100% progress)
  └── XML/XBRL files extracted and parsed into rows
  └── Rows inserted into BigQuery via streaming inserts
  └── migration_log updated with COMPLETED status
  └── Temp directory cleaned up
```

### Module 3 — LLM Assist (`pages/3_Smart_Search.py`)

The LLM Assist module enables natural-language querying of the call report database. A user can ask questions like *"What were the total assets of community banks in Virginia in Q3 2022?"* and receive a structured data response — without writing SQL. The module translates user prompts into BigQuery-compatible queries using an LLM, executes them, and renders results in the Streamlit UI.

### Module 4 — Database Maintenance

Accessible from the home page under an expandable panel, this module provides two tools:

**Global Deduplication** rewrites the `call_reports_financials` table using `SELECT DISTINCT *`, removing any exact-duplicate rows introduced by re-runs or partial uploads.

**Period Reset** allows a user to select any ingested report date and wipe all associated records from both the financials table and the migration log — enabling clean re-ingestion of corrupted or partial downloads.

---

## 🏗️ Architecture Overview

```
                        ┌─────────────────┐
                        │   FFIEC CDR     │
                        │  (public web)   │
                        └────────┬────────┘
                                 │  .zip bundles (XBRL/XML)
                                 ▼
                    ┌────────────────────────┐
                    │   update_engine.py     │
                    │  ┌──────────────────┐  │
                    │  │ Browser Download │  │
                    │  └────────┬─────────┘  │
                    │  ┌────────▼─────────┐  │
                    │  │  XBRL Parser     │  │
                    │  └────────┬─────────┘  │
                    └───────────┼────────────┘
                                │  Structured rows
                                ▼
                    ┌────────────────────────┐
                    │    Google BigQuery     │
                    │   (ffiec_data dataset) │
                    └───────────┬────────────┘
                                │
               ┌────────────────┴────────────────┐
               │                                 │
     ┌─────────▼──────────┐          ┌───────────▼──────────┐
     │   Fetch Tool       │          │    LLM Assist        │
     │  (SQL queries)     │          │  (NL → SQL via LLM)  │
     └────────────────────┘          └──────────────────────┘
               │                                 │
               └────────────────┬────────────────┘
                                 │
                    ┌────────────▼───────────┐
                    │   Streamlit Frontend   │
                    │     (Home.py)          │
                    └────────────────────────┘
```

### Data Schema

**`call_reports_financials`**

| Column | Type | Description |
|---|---|---|
| `report_date` | DATE | Quarter-end date (e.g., 2023-03-31) |
| `rssd_id` | STRING | Unique institution identifier |
| `institution_name` | STRING | Bank or savings association name |
| `xbrl_tag` | STRING | FFIEC XBRL concept name |
| `value` | FLOAT64 | Reported dollar amount (in thousands) |
| `unit` | STRING | Unit of measure |

**`migration_log`**

| Column | Type | Description |
|---|---|---|
| `report_date` | DATE | Quarter-end date |
| `status` | STRING | `COMPLETED`, `IN_PROGRESS`, or `FAILED` |
| `ingested_at` | TIMESTAMP | Time of ingestion |

---

## 🔭 What's Next

### Near-Term Enhancements

**Automated Scheduling** — Currently, database updates require a human to click "Start Bulk Download & Parse." A cron job or Cloud Scheduler integration could trigger automatic ingestion shortly after each FFIEC quarterly release (typically 30–45 days after quarter-end).

**Expanded XBRL Coverage** — The current parser targets the primary balance sheet and income statement schedules. Future versions should include Schedule RC-R (regulatory capital), Schedule RC-C (loans and leases), and RC-N (past due and nonaccrual assets).

**Institution Comparison Dashboard** — A dedicated Streamlit page allowing side-by-side comparison of financial metrics across multiple institutions, with charting via Plotly or Altair.

### Longer-Term Vision

**Predictive Risk Flagging** — By training a model on historical call report trajectories, the toolkit could surface early indicators of financial stress (e.g., rising nonaccrual loan ratios, declining capital adequacy) before they become public knowledge.

**API Layer** — Exposing a REST API endpoint would allow external tools, dashboards, and research pipelines to query the BigQuery backend programmatically without going through the Streamlit UI.

**Multi-Form Support** — FFIEC 002 (foreign banking organizations) and the FR Y-9C (bank holding companies) follow similar XBRL structures and could be ingested into the same infrastructure with modest additions to the parser.

### Known Concerns

- **FFIEC CDR Structural Changes** — The FFIEC periodically revises XBRL taxonomies. A taxonomy version mismatch could silently break parsing without error. Version tracking and schema validation checks should be added.
- **BigQuery Cost at Scale** — As data grows across two decades and thousands of institutions, query costs on large unpartitioned tables will increase. Partitioning by `report_date` and clustering by `rssd_id` should be implemented.
- **Browser Automation Fragility** — The download module relies on browser automation to navigate the CDR portal. Changes to that portal's frontend could break the downloader without warning.

---

## ⚖️ Responsible AI Considerations

### Transparency in LLM-Generated Queries

The LLM Assist module generates BigQuery SQL from natural-language prompts. Users should be aware that the model may produce syntactically valid but semantically incorrect queries — for example, selecting the wrong XBRL tag for a given financial concept. All LLM-generated queries should be displayed to the user before execution, and raw results should be shown alongside any LLM-generated interpretation.

### Data Provenance and Accuracy

Call report data is self-reported by financial institutions and subject to later amendment. The toolkit ingests data as-of the time of download, which may not reflect subsequent restatements. Users should treat outputs as reference data rather than certified financial statements. Source links back to the FFIEC CDR should be provided alongside query results.

### Access and Equity

This toolkit democratizes access to data that is technically public but practically inaccessible to those without significant technical resources. This is a net positive — but deployment teams should ensure the tool is not used to disadvantage smaller institutions (e.g., by enabling large competitors or hedge funds to systematically exploit regulatory disclosures for trading advantage in ways not intended by the reporting framework).

### Model Bias in NLP Layer

LLMs used for query generation may have been trained predominantly on data from large financial institutions and may underperform on queries about community banks, credit unions, or institutions with non-standard reporting structures. Ongoing evaluation of query accuracy across institution types is recommended.

### Data Security

Call reports contain institution-level financial data that, in aggregate or in combination with other data sources, could be sensitive. The BigQuery dataset should be secured with IAM role-based access control, and service account credentials should never be committed to version control.

---

## 📚 References

### Primary Data Sources

- **FFIEC Central Data Repository (CDR)** — Public bulk data download portal for quarterly call reports.
  https://cdr.ffiec.gov/public/pws/downloadbulkdata.aspx

- **FFIEC 031/041/051 Reporting Forms and Instructions** — Official form specifications and XBRL taxonomies.
  https://www.ffiec.gov/ffiec_report_forms.htm

- **FDIC Call Reports** — Supplemental instructions and historical filing archives.
  https://www.fdic.gov/callreports

### Research Paper

- **Du, K., Zhao, Y., Mao, R., & Xing, F. (2024).** *Natural language processing in finance: A survey.* Information Fusion, Elsevier. https://doi.org/10.1016/j.inffus.2024.102343

  > This peer-reviewed survey from Nanyang Technological University (NTU) and the National University of Singapore (NUS) provides a comprehensive review of NLP applications across ten major financial domains — including regulatory compliance monitoring, financial narrative processing, and question-answering systems. Directly relevant to the LLM Assist module of this project, which applies NLP to structured financial regulatory data.

- **Achitouv, I., et al. (2023).** *Natural Language Processing for Financial Regulation.* arXiv:2311.08533.
  https://arxiv.org/abs/2311.08533

  > This paper explores semantic matching between regulatory rules and policy documents using NLP techniques, with direct applicability to automated compliance monitoring of call report filings.

- **Conference of State Bank Supervisors (CSBS). (2023).** *Community Banking in the 21st Century: 2023 Research Paper.* https://www.csbs.org/sites/default/files/2023-05/WM_CSBS_2023.pdf

  > This comprehensive research paper explores the performance, consolidation trends, and regulatory hurdles of community banks. It provides essential context for the "Why This Matters" section of the FFIEC Toolkit, specifically regarding how granular call report data can be used to monitor the resilience of smaller financial institutions in a shifting economic environment.

### Additional Resources

- **Google BigQuery Documentation** — https://cloud.google.com/bigquery/docs
- **Streamlit Documentation** — https://docs.streamlit.io
- **FFIEC XBRL Taxonomy** — https://www.ffiec.gov/nicpubweb/content/XBRL.aspx
- **FDIC BankFind Suite** — Complementary tool for institution lookups: https://banks.data.fdic.gov/

---

### Link
[Click here to view the app](https://ffiectools-tp2.streamlit.app/)

<div align="center">

**🦅 FFIEC Toolkit** 

</div>
