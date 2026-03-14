# CODEBASE

<codebase_summary>
## Architecture Overview

This codebase has 37 modules and 11 dependency links. Structural analysis (PageRank) and data lineage (sources/sinks) are available below. Module purposes and domain clusters are indexed for semantic search.

</codebase_summary>

<critical_path>
## Critical Path

Top 5 modules by PageRank (architectural hubs):

1. `models/marts/order_items.sql` (hub_score=0.071347)
2. `models/marts/customers.sql` (hub_score=0.061644)
3. `models/marts/orders.sql` (hub_score=0.051941)
4. `models/marts/locations.sql` (hub_score=0.042238)
5. `models/marts/products.sql` (hub_score=0.032534)

</critical_path>

<data_flow>
## Data Sources & Sinks

### Sources (in_degree=0)

- cast_to_date
- compute_booleans
- customer_order_count
- customer_orders_summary
- days
- ecom.raw_customers
- ecom.raw_items
- ecom.raw_orders
- ecom.raw_products
- ecom.raw_stores
- ecom.raw_supplies
- joined
- order_items_summary
- order_supplies_summary
- renamed
- source
- source:ecom
- stg_customers
- stg_locations
- stg_order_items
- stg_orders
- stg_products
- stg_supplies

### Sinks (out_degree=0)

- models/marts/customers.sql
- models/marts/locations.sql
- models/marts/metricflow_time_spine.sql
- models/marts/order_items.sql
- models/marts/orders.sql
- models/marts/products.sql
- models/marts/supplies.sql
- models/staging/stg_customers.sql
- models/staging/stg_locations.sql
- models/staging/stg_order_items.sql
- models/staging/stg_orders.sql
- models/staging/stg_products.sql
- models/staging/stg_supplies.sql
- source:ecom.raw_customers
- source:ecom.raw_items
- source:ecom.raw_orders
- source:ecom.raw_products
- source:ecom.raw_stores
- source:ecom.raw_supplies

</data_flow>

<known_debt>
## Known Debt

### Circular Dependencies

- None detected.

### Documentation Drift (docstring vs. inferred purpose)

- None flagged.

</known_debt>

<high_velocity>
## High-Velocity Files

Top 20% of files by change count (Surveyor).

- None in this run.

</high_velocity>

<module_purpose_index>
## Module Purpose Index

Grouped by domain_cluster (Semanticist).

### default_domain

- .github/workflows/scripts/dbt_cloud_run_job.py: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\.github\workflows\scripts\dbt_cloud_run_job.py (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- macros/cents_to_dollars.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\macros\cents_to_dollars.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- macros/generate_schema_name.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\macros\generate_schema_name.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/customers.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\customers.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/locations.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\locations.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/metricflow_time_spine.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\metricflow_time_spine.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/order_items.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\order_items.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/orders.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\orders.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/products.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\products.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/marts/supplies.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\marts\supplies.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_customers.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_customers.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_locations.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_locations.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_order_items.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_order_items.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_orders.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_orders.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_products.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_products.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}
- models/staging/stg_supplies.sql: LLM generation failed for stage 'purpose_statement' on C:\Users\Ephi\the-brownfield-cartographer\jaffle-shop\models\staging\stg_supplies.sql (models_tried=[gemini-2.0-flash, gemini-1.5-flash]): 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1, or is not supported for generateContent. Call ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}}

</module_purpose_index>
