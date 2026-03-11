from __future__ import annotations

"""
Compatibility wrapper exposing the config/DAG topology analyzer at
`src/analyzers/dag_config_parser.py` while delegating to the implementation
under `src/analyzers/lineage/config_analyzer.py`.
"""

from src.analyzers.lineage.config_analyzer import (
    ConfigLineageAnalyzer,
    ConfigLineageResult,
)

__all__ = ["ConfigLineageAnalyzer", "ConfigLineageResult"]

