from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import networkx as nx

from src.models.module_node import ModuleNode


@dataclass
class KnowledgeGraph:
    graph: nx.DiGraph

    @classmethod
    def build(cls, nodes: Iterable[ModuleNode]) -> "KnowledgeGraph":
        g = nx.DiGraph()
        node_list = list(nodes)

        by_id: dict[str, ModuleNode] = {n.id: n for n in node_list}
        by_stem: dict[str, str] = {Path(n.path).stem: n.id for n in node_list}

        for n in node_list:
            g.add_node(n.id, **n.model_dump())

        def add_edge(src_id: str, dst_id: str, *, edge_type: str = "IMPORTS") -> None:
            if src_id == dst_id:
                return
            if src_id not in by_id or dst_id not in by_id:
                return
            g.add_edge(src_id, dst_id, type=edge_type)

        # SQL edges via ref('model')
        for n in node_list:
            if n.language != "sql":
                continue
            for ref in n.sql_refs:
                ref_id = by_stem.get(ref)
                if ref_id:
                    # stg_orders -> fct_orders
                    add_edge(ref_id, n.id)

        # Python edges via imports (best-effort, repo-local only)
        for n in node_list:
            if n.language != "python":
                continue
            for imp in n.imports:
                # Normalize relative imports (".foo") are ignored for now (no package root resolution in Phase 1)
                if not imp or imp.startswith("."):
                    continue
                target_id = cls.resolve_import_to_id(imp, current_file_id=n.id, known_ids=set(by_id.keys()))
                if target_id is not None:
                    add_edge(target_id, n.id)

        kg = cls(graph=g)
        kg._run_algorithms()
        return kg

    @staticmethod
    def resolve_import_to_id(import_stmt: str, current_file_id: str, known_ids: set[str]) -> Optional[str]:
        """
        Best-effort mapping from an import statement to a ModuleNode.id (relative path).

        Python example: "src.agents.surveyor" -> "src/agents/surveyor.py"
        """
        # Phase 1: we intentionally ignore package context and only handle absolute-style imports.
        if import_stmt.startswith("."):
            return None

        # Direct "src.agents.surveyor" → "src/agents/surveyor.py"
        candidate = import_stmt.replace(".", "/") + ".py"
        if candidate in known_ids:
            return candidate

        # Common pattern: project sources live under "src/", but imports omit the prefix:
        # "agents.surveyor" → "src/agents/surveyor.py"
        candidate_with_src = f"src/{candidate}"
        if candidate_with_src in known_ids:
            return candidate_with_src

        # As a last resort, try matching on stem within the same directory tree as current_file_id.
        cur_dir = str(Path(current_file_id).parent)
        for k in known_ids:
            if not k.endswith(".py"):
                continue
            if Path(k).stem == import_stmt.split(".")[-1] and k.startswith(cur_dir):
                return k

        return None

    def _run_algorithms(self) -> None:
        # PageRank hub score (architectural hubs)
        if self.graph.number_of_nodes() > 0 and self.graph.number_of_edges() > 0:
            pr = nx.pagerank(self.graph)
        else:
            pr = {n: 0.0 for n in self.graph.nodes()}

        for node_id, score in pr.items():
            self.graph.nodes[node_id]["hub_score"] = float(score)

        # Circular dependencies (SCCs > 1)
        circular_components: list[list[str]] = []
        for comp in nx.strongly_connected_components(self.graph):
            comp_list = list(comp)
            if len(comp_list) > 1:
                circular_components.append(sorted(comp_list))
                for node_id in comp_list:
                    md = self.graph.nodes[node_id].setdefault("metadata", {})
                    md["circular_dependency"] = True

        self.graph.graph["circular_dependencies"] = circular_components

        # Dead code heuristic: modules with no incoming or outgoing edges and
        # no recent git activity (change_count_30d==0) are flagged as dead.
        for node_id, data in self.graph.nodes(data=True):
            deg_in = self.graph.in_degree(node_id)
            deg_out = self.graph.out_degree(node_id)
            is_isolated = deg_in == 0 and deg_out == 0
            change_count = int(data.get("change_count_30d", 0))
            data["is_dead_code"] = bool(is_isolated and change_count == 0)

