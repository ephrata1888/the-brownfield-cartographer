from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

from src.graph.lineage_graph import LineageGraph
from src.utils.trace import TraceLogger


@dataclass
class Hydrologist:
    """
    High-level interface over the data lineage graph.
    """

    repo_root: Path
    trace: TraceLogger
    graph: LineageGraph | None = None

    def build_graph(self) -> LineageGraph:
        """
        Build (or rebuild) the lineage graph for the repository.
        """
        self.graph = LineageGraph.build(repo_root=self.repo_root, trace=self.trace)
        return self.graph

    # ------------------------------------------------------------------ #
    # Query API (moved from LineageGraph)
    # ------------------------------------------------------------------ #

    def blast_radius(self, node_id: str) -> List[str]:
        """
        Returns all downstream nodes reachable from node_id via BFS.
        """
        g = self._ensure_graph()
        if node_id not in g:
            return []

        visited: Set[str] = set()
        queue: deque[str] = deque()
        queue.append(node_id)
        visited.add(node_id)

        result: List[str] = []
        while queue:
            cur = queue.popleft()
            for _, nbr in g.out_edges(cur):
                if nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
                    result.append(nbr)
        return result

    def find_sources(self) -> List[str]:
        """
        Nodes where data enters the system (in_degree == 0).
        """
        g = self._ensure_graph()
        return [n for n in g.nodes() if g.in_degree(n) == 0]

    def find_sinks(self) -> List[str]:
        """
        Nodes where data exits the system (out_degree == 0).
        """
        g = self._ensure_graph()
        return [n for n in g.nodes() if g.out_degree(n) == 0]

    # ------------------------------------------------------------------ #

    def _ensure_graph(self) -> LineageGraph:
        if self.graph is None:
            self.build_graph()
        assert self.graph is not None
        return self.graph

