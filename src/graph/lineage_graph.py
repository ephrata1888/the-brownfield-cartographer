from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import networkx as nx

from src.analyzers.lineage.config_analyzer import ConfigLineageAnalyzer
from src.analyzers.lineage.python_analyzer import PythonLineageAnalyzer
from src.analyzers.lineage.sql_analyzer import SqlLineageAnalyzer
from src.analyzers.tree_sitter_analyzer import LanguageRouter
from src.utils.trace import TraceLogger


class LineageGraph(nx.DiGraph):
    """
    Data lineage graph: datasets, tasks, and configuration edges.
    """

    @classmethod
    def build(cls, repo_root: Path, trace: TraceLogger) -> "LineageGraph":
        repo_root = repo_root.resolve()
        g = cls()

        router = LanguageRouter()
        py_analyzer = PythonLineageAnalyzer(repo_root=repo_root, router=router, trace=trace)
        sql_analyzer = SqlLineageAnalyzer(repo_root=repo_root, trace=trace)
        cfg_analyzer = ConfigLineageAnalyzer(repo_root=repo_root, trace=trace)

        py_files: List[Path] = []
        sql_files: List[Path] = []
        yaml_files: List[Path] = []

        for p in repo_root.rglob("*"):
            if not p.is_file():
                continue
            suffix = p.suffix.lower()
            if suffix == ".py":
                py_files.append(p)
            elif suffix == ".sql":
                sql_files.append(p)
            elif suffix in {".yml", ".yaml"}:
                yaml_files.append(p)

        # Python lineage
        for res in py_analyzer.analyze_files(py_files):
            g.add_node(res.file_id, type="file")
            for ds in res.datasets_read:
                g.add_node(ds, type="dataset")
                g.add_edge(ds, res.file_id, kind="reads")
            for ds in res.datasets_written:
                g.add_node(ds, type="dataset")
                g.add_edge(res.file_id, ds, kind="writes")

        # SQL lineage
        for res in sql_analyzer.analyze_files(sql_files):
            g.add_node(res.file_id, type="file")
            for tbl in res.tables:
                g.add_node(tbl, type="table")
                g.add_edge(tbl, res.file_id, kind="sql_dep")

        # Config lineage (Airflow + dbt YAML)
        for res in cfg_analyzer.analyze_py_files(py_files):
            for a, b in res.edges:
                g.add_node(a, type="task")
                g.add_node(b, type="task")
                g.add_edge(a, b, kind="airflow")

        for res in cfg_analyzer.analyze_yaml_files(yaml_files):
            for a, b in res.edges:
                g.add_node(a, type="dataset")
                g.add_node(b, type="dataset")
                g.add_edge(a, b, kind="config")

        return g

