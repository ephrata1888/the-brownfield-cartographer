from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set

import sqlglot
from sqlglot import expressions as exp

from src.utils.trace import TraceLogger


_REF_RE = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SqlLineageResult:
    file_id: str
    tables: Set[str]
    # Logical dbt parents discovered via ref() calls; used by Hydrologist
    # to stitch together model-to-model lineage.
    dbt_parents: Set[str] = field(default_factory=set)


class SqlLineageAnalyzer:
    """
    Uses sqlglot to parse SQL and extract table dependencies from
    SELECT, FROM, JOIN, and WITH (CTE) blocks across multiple dialects.
    """

    DIALECTS = ["postgres", "bigquery", "snowflake", "duckdb"]

    def __init__(self, repo_root: Path, trace: TraceLogger) -> None:
        self.repo_root = repo_root
        self.trace = trace

    def analyze_files(self, files: Iterable[Path]) -> List[SqlLineageResult]:
        results: List[SqlLineageResult] = []
        for path in files:
            try:
                res = self.analyze_file(path)
                if res is not None:
                    results.append(res)
            except Exception as e:
                self.trace.log_error(stage="sql_lineage_analyze_file", path=path, error=e)
        return results

    def analyze_file(self, path: Path) -> Optional[SqlLineageResult]:
        try:
            sql_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.trace.log_error(stage="sql_lineage_read", path=path, error=e)
            return None

        # Capture dbt parents before we mutate the SQL via preprocessing.
        dbt_parents: Set[str] = set(_REF_RE.findall(sql_text))

        # Preprocess dbt {{ ref('...') }} into plain table names
        def _replace_ref(match: re.Match) -> str:
            model = match.group(1)
            # Use the model name directly as a logical table
            return model

        preprocessed = _REF_RE.sub(_replace_ref, sql_text)

        # Convert dbt source() macros into schema.table-style identifiers so
        # they are visible to sqlglot like regular tables.
        def _replace_source(match: re.Match) -> str:
            src_name, tbl_name = match.group(1), match.group(2)
            return f"{src_name}.{tbl_name}"

        preprocessed = _SOURCE_RE.sub(_replace_source, preprocessed)

        tree = None
        for dialect in self.DIALECTS:
            try:
                tree = sqlglot.parse_one(preprocessed, read=dialect)
                if tree is not None:
                    break
            except sqlglot.errors.ParseError:
                continue

        if tree is None:
            self.trace.log_error(
                stage="sql_lineage_parse",
                path=path,
                error=RuntimeError("Unable to parse SQL in any supported dialect"),
                extra={"dialects_tried": self.DIALECTS},
            )
            return None

        tables: Set[str] = set()
        try:
            # Collect table references and CTEs
            for t in tree.find_all(exp.Table):
                name = t.name
                db = getattr(t, "db", None) or ""
                full = f"{db}.{name}" if db else name
                if full:
                    tables.add(full)

            for cte in tree.find_all(exp.CTE):
                alias = cte.alias_or_name
                if alias:
                    tables.add(alias)
        except Exception as e:
            self.trace.log_error(stage="sql_lineage_walk", path=path, error=e)
            return None

        if not tables and not dbt_parents:
            return None

        try:
            rel = path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            rel = Path(path.name)
        file_id = str(rel).replace("\\", "/")

        return SqlLineageResult(file_id=file_id, tables=tables, dbt_parents=dbt_parents)

