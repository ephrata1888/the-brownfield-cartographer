from __future__ import annotations

"""
Compatibility wrapper exposing the SQL lineage analyzer at
`src/analyzers/sql_lineage.py` while delegating to the implementation under
`src/analyzers/lineage/sql_analyzer.py`.
"""

from src.analyzers.lineage.sql_analyzer import SqlLineageAnalyzer, SqlLineageResult

__all__ = ["SqlLineageAnalyzer", "SqlLineageResult"]

