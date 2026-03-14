# [RECONNAISSANCE.md](http://RECONNAISSANCE.md): Phase 0 – Manual Reconnaissance

## The Five FDE Day-One Answers

## 1. Primary Data Ingestion Path

- **Location:** `seeds/` directory.
- **Details:** The system ingests raw data via static CSV files: `raw_customers.csv`, `raw_orders.csv`, and `raw_payments.csv`.
- **Observation:** This indicates the project starts with a **"Seed-First"** approach, where raw data is treated as local reference tables before being processed by the staging models.

## 2. 3-5 Critical Output Datasets

Based on the file naming conventions and directory depth, the primary sinks for the business logic are:

- `dim_customers.sql`: The primary dimension for customer-centric analytics.
- `fct_orders.sql`: The core transactional fact table.
- `orders.sql`: A top-level aggregated mart used for reporting.

## 3. Blast Radius

- **Critical Node:** `models/staging/stg_orders.sql`.
- **Reasoning:** This model acts as the **"bottleneck"** of the DAG. Because it normalizes the raw order data used by almost every downstream mart, a single error or schema change in this file will propagate and break the entire Marts layer.

## 4. Business Logic Concentration

- **Staging (**`models/staging/`**):** Dedicated to "low-level" logic such as column renaming, data type casting, and basic cleanup.
- **Marts (**`models/marts/`**):** Dedicated to "high-level" business logic. This is where complex metrics—such as **Lifetime Value (LTV)** and **order counts**—are calculated.

## 5. Git Velocity

- **Predicted Churn:** High commit frequency is expected in `dbt_project.yml` and the **Staging models**.
- **Reasoning:** As raw data sources evolve, the staging layer requires constant adjustment to maintain the schema contract for the rest of the pipeline.

---

## Difficulty Analysis

## The "Jump" Problem

- **Observation:** Tracing a single data element requires significant context switching.
- **Details:** To verify a single column's logic, a developer must manually navigate at least **four distinct directory layers** (Seeds -> Staging -> Marts -> Final Output). This creates a high "cognitive load" and increases the chance of manual error during refactoring.

## Stale Documentation & The "Hidden DAG"

- **Observation:** Manual understanding is inherently slow due to the nature of dbt.
- **Details:** Because the project relies on `{{ ref() }}` tags to link files, the actual pipeline structure is a **"Hidden DAG"**. This structure is not visible in a standard file explorer, meaning a developer cannot see the impact of a change just by looking at the folder tree. This creates a high risk of documentation drift where the READMEs eventually stop matching the actual code flow.

