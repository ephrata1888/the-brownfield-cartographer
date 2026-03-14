from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import yaml

from src.utils.trace import TraceLogger


@dataclass(frozen=True)
class ConfigLineageResult:
    file_id: str
    edges: Set[Tuple[str, str]]


class ConfigLineageAnalyzer:
    """
    Extracts topology from configuration:
    - Airflow DAG .py files: bitwise operators (>>, <<) and .set_upstream()
    - dbt schema.yml / sources.yml: relationships defined in YAML
    """

    def __init__(self, repo_root: Path, trace: TraceLogger) -> None:
        self.repo_root = repo_root
        self.trace = trace

    def analyze_py_files(self, files: Iterable[Path]) -> List[ConfigLineageResult]:
        results: List[ConfigLineageResult] = []
        for path in files:
            try:
                res = self._analyze_airflow_py(path)
                if res is not None:
                    results.append(res)
            except Exception as e:
                self.trace.log_error(stage="config_lineage_airflow_py", path=path, error=e)
        return results

    def analyze_yaml_files(self, files: Iterable[Path]) -> List[ConfigLineageResult]:
        results: List[ConfigLineageResult] = []
        for path in files:
            try:
                res = self._analyze_dbt_yaml(path)
                if res is not None:
                    results.append(res)
            except Exception as e:
                self.trace.log_error(stage="config_lineage_dbt_yaml", path=path, error=e)
        return results

    # ------------------------------------------------------------------ #
    # Airflow DAGs (.py)
    # ------------------------------------------------------------------ #

    def _analyze_airflow_py(self, path: Path) -> Optional[ConfigLineageResult]:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.trace.log_error(stage="config_lineage_airflow_read", path=path, error=e)
            return None

        try:
            tree = ast.parse(source)
        except Exception as e:
            self.trace.log_error(stage="config_lineage_airflow_parse", path=path, error=e)
            return None

        edges: Set[Tuple[str, str]] = set()

        class Visitor(ast.NodeVisitor):
            def visit_BinOp(self, node: ast.BinOp) -> None:  # type: ignore[override]
                if isinstance(node.op, ast.RShift):
                    left = self._task_name(node.left)
                    right = self._task_name(node.right)
                    if left and right:
                        edges.add((left, right))
                elif isinstance(node.op, ast.LShift):
                    left = self._task_name(node.left)
                    right = self._task_name(node.right)
                    if left and right:
                        edges.add((right, left))
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:  # type: ignore[override]
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "set_upstream":
                    this = self._task_name(func.value)
                    if node.args:
                        other = self._task_name(node.args[0])
                    else:
                        other = None
                    if this and other:
                        # other -> this
                        edges.add((other, this))
                self.generic_visit(node)

            def _task_name(self, n: ast.AST) -> Optional[str]:
                if isinstance(n, ast.Name):
                    return n.id
                if isinstance(n, ast.Attribute):
                    return n.attr
                return None

        Visitor().visit(tree)

        if not edges:
            return None

        try:
            rel = path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            rel = Path(path.name)
        file_id = str(rel).replace("\\", "/")

        # Prefix task IDs with the file for uniqueness
        scoped_edges = {(f"{file_id}::{a}", f"{file_id}::{b}") for (a, b) in edges}
        return ConfigLineageResult(file_id=file_id, edges=scoped_edges)

    # ------------------------------------------------------------------ #
    # dbt YAML (schema.yml / sources.yml)
    # ------------------------------------------------------------------ #

    def _analyze_dbt_yaml(self, path: Path) -> Optional[ConfigLineageResult]:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            data = yaml.safe_load(raw) or {}
        except Exception as e:
            self.trace.log_error(stage="config_lineage_dbt_yaml_read", path=path, error=e)
            return None

        edges: Set[Tuple[str, str]] = set()

        sources = data.get("sources") or []
        for src in sources:
            src_name = src.get("name")
            if not src_name:
                continue
            tables = src.get("tables") or []
            for tbl in tables:
                tbl_name = tbl.get("name")
                if not tbl_name:
                    continue
                src_id = f"source:{src_name}"
                tbl_id = f"source:{src_name}.{tbl_name}"
                edges.add((src_id, tbl_id))

        models = data.get("models") or []
        for mdl in models:
            mdl_name = mdl.get("name")
            if not mdl_name:
                continue
            # Link all declared sources in this file to the model
            for src in sources:
                src_name = src.get("name")
                if not src_name:
                    continue
                src_id = f"source:{src_name}"
                mdl_id = f"model:{mdl_name}"
                edges.add((src_id, mdl_id))

        if not edges:
            return None

        try:
            rel = path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            rel = Path(path.name)
        file_id = str(rel).replace("\\", "/")

        return ConfigLineageResult(file_id=file_id, edges=edges)

