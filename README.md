## the-brownfield-cartographer

Static structural and data lineage cartography for brownfield repositories.

## Setup

This project uses **uv** for dependency management. To set up the environment:

## Usage

The tool uses a central **Orchestrator** to run the Surveyor (Structural) and Hydrologist (Lineage) agents.

#### 1. Structural Analysis

Maps the module import graph, calculates PageRank (centrality), and identifies git velocity/churn.

#### 2. Data Lineage Analysis

Extracts SQL dependencies, CTEs, and dbt/YAML configurations to map the data flow.

## Outputs

All artifacts are serialized to the `.cartography/` directory in the project root:

- `.cartography/module_graph.json`: Structural node-link JSON showing file dependencies and architectural hubs.
- `.cartography/lineage_graph.json`: Data flow JSON mapping sources, staging models, and final sinks.
- `cartography_trace.jsonl`: Detailed audit trail of the analysis process and any file-level exceptions.

## Architecture

- **Surveyor Agent**: Responsible for AST-based structural mapping.
- **Hydrologist Agent**: Responsible for SQL-glot based lineage extraction and blast radius calculation.
- **Orchestrator**: Manages the execution sequence and shared state between agents.

