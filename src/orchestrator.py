from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Tuple

from networkx.readwrite import json_graph

from src.agents.hydrologist import Hydrologist
from src.agents.surveyor import Surveyor
from src.analyzers.tree_sitter_analyzer import LanguageRouter
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.utils.trace import TraceLogger


class CartographyOrchestrator:
    """
    Wires the Surveyor (structural graph) and Hydrologist (data lineage graph)
    into a single execution pipeline.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.trace = TraceLogger(self.repo_root / "cartography_trace.jsonl")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_structural(self) -> KnowledgeGraph:
        """
        Run the Surveyor to produce the structural graph and PageRank,
        and serialize it to `.cartography/module_graph.json`.
        """
        router = LanguageRouter()
        surveyor = Surveyor(repo_root=self.repo_root, trace=self.trace, router=router)

        paths = list(self._iter_repo_files())
        nodes = surveyor.analyze_paths(paths)
        nodes = surveyor.apply_velocity_flags(nodes, days=30)

        kg = KnowledgeGraph.build(nodes)

        out_dir = Path.cwd() / ".cartography"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "module_graph.json"

        data = json_graph.node_link_data(kg.graph, edges="links")
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return kg

    def run_lineage(self) -> LineageGraph:
        """
        Run the Hydrologist to produce the data lineage graph,
        and serialize it to `.cartography/lineage_graph.json`.
        """
        hydrologist = Hydrologist(repo_root=self.repo_root, trace=self.trace)
        lg = hydrologist.build_graph()

        out_dir = Path.cwd() / ".cartography"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "lineage_graph.json"

        data = json_graph.node_link_data(lg, edges="links")
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return lg

    def run_all(self) -> Tuple[KnowledgeGraph, LineageGraph]:
        """
        Run Surveyor then Hydrologist in sequence.
        """
        kg = self.run_structural()
        lg = self.run_lineage()
        return kg, lg

    # ------------------------------------------------------------------ #

    def _iter_repo_files(self) -> Iterable[Path]:
        """
        File iterator used by the Surveyor structural pass.
        """
        skip_dirs = {
            ".git",
            ".cartography",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
        }
        allowed_suffixes = {".py", ".sql", ".yml", ".yaml", ".js", ".ts", ".tsx"}

        for p in self.repo_root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in skip_dirs for part in p.parts):
                continue
            if p.suffix.lower() in allowed_suffixes:
                yield p

