"""
Phase 4: Agent 5 (The Navigator).
Tool-based query interface over the Knowledge Graph and Lineage Graph.
Every tool outputs Source of Truth (Static Analysis vs. LLM Inference) and file:line citations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Literal, Optional

import networkx as nx

from src.agents.hydrologist import Hydrologist
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.models.navigator_schemas import (
    BlastRadiusResult,
    ExplainModuleResult,
    FileLineCitation,
    FindImplementationResult,
    TraceLineageResult,
)
from src.utils.trace import TraceLogger


class Navigator:
    """
    Query agent: find_implementation, trace_lineage, blast_radius, explain_module.
    Uses Surveyor (structural) + Semanticist (purpose) data from the Knowledge Graph,
    and Hydrologist for lineage/blast radius.
    """

    def __init__(
        self,
        repo_root: Path,
        trace: TraceLogger,
        kg: KnowledgeGraph,
        hydrologist: Hydrologist,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.trace = trace
        self.kg = kg
        self.hydrologist = hydrologist
        self._lg: Optional[LineageGraph] = None

    def _lineage_graph(self) -> LineageGraph:
        if self._lg is None:
            self._lg = self.hydrologist._ensure_graph()
        return self._lg

    def _cite(self, file_path: str, line: int = 1, context: Optional[str] = None) -> FileLineCitation:
        return FileLineCitation(file=file_path, line=line, context=context)

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def find_implementation(self, concept: str) -> FindImplementationResult:
        """
        Semantic search over purpose statements in the Knowledge Graph.
        Source of truth: static_analysis (we search stored purpose text).
        """
        self.trace.log_agent_action(
            agent="navigator",
            action="find_implementation",
            evidence_source="static_analysis",
            confidence_score=0.85,
            extra={"concept": concept},
        )
        concept_lower = concept.lower()
        matches: List[dict[str, Any]] = []
        citations: List[FileLineCitation] = []
        g = self.kg.graph
        for nid, data in g.nodes(data=True):
            purpose = data.get("purpose") or ""
            if concept_lower in purpose.lower() or concept_lower in nid.lower():
                path = data.get("path", nid)
                matches.append({
                    "module_id": nid,
                    "path": path,
                    "purpose": purpose,
                    "domain_cluster": data.get("domain_cluster"),
                })
                citations.append(self._cite(path, 1, purpose[:80]))
        return FindImplementationResult(
            source_of_truth="static_analysis",
            citations=citations[:10],
            confidence_score=0.85,
            concept=concept,
            matches=matches,
        )

    def trace_lineage(
        self,
        dataset: str,
        direction: Literal["upstream", "downstream"],
    ) -> TraceLineageResult:
        """
        Upstream or downstream graph traversal on the Lineage Graph.
        Source of truth: static_analysis.
        """
        self.trace.log_agent_action(
            agent="navigator",
            action="trace_lineage",
            evidence_source="static_analysis",
            confidence_score=1.0,
            extra={"dataset": dataset, "direction": direction},
        )
        lg = self._lineage_graph()
        if dataset not in lg:
            return TraceLineageResult(
                source_of_truth="static_analysis",
                citations=[],
                confidence_score=1.0,
                dataset=dataset,
                direction=direction,
                nodes=[],
                edges=[],
            )
        if direction == "downstream":
            edges = list(lg.out_edges(dataset))
            nodes = [dataset] + [v for _, v in edges]
        else:
            edges = list(lg.in_edges(dataset))
            nodes = [dataset] + [u for u, _ in edges]
        citations = [self._cite(dataset, 1, f"lineage_{direction}")]
        return TraceLineageResult(
            source_of_truth="static_analysis",
            citations=citations,
            confidence_score=1.0,
            dataset=dataset,
            direction=direction,
            nodes=nodes,
            edges=[(u, v) for u, v in edges],
        )

    def blast_radius(self, module_path: str) -> BlastRadiusResult:
        """
        BFS/DFS to find all downstream dependents.
        Uses structural graph (Knowledge Graph) and lineage graph (Hydrologist).
        Source of truth: static_analysis.
        """
        self.trace.log_agent_action(
            agent="navigator",
            action="blast_radius",
            evidence_source="static_analysis",
            confidence_score=1.0,
            path=module_path,
        )
        # Normalize to repo-relative id if needed
        node_id = module_path.replace("\\", "/")
        g = self.kg.graph
        lg = self._lineage_graph()

        structural_downstream: List[str] = []
        if node_id in g:
            visited = set()
            stack = [node_id]
            while stack:
                cur = stack.pop()
                for _, succ in g.out_edges(cur):
                    if succ not in visited:
                        visited.add(succ)
                        structural_downstream.append(succ)
                        stack.append(succ)

        lineage_downstream: List[str] = self.hydrologist.blast_radius(node_id) if node_id in lg else []

        citations = [self._cite(module_path, 1, "blast_radius")]
        return BlastRadiusResult(
            source_of_truth="static_analysis",
            citations=citations,
            confidence_score=1.0,
            module_path=module_path,
            downstream_count=len(structural_downstream) + len(lineage_downstream),
            affected_nodes=list(dict.fromkeys(structural_downstream + lineage_downstream)),
            structural_blast=structural_downstream,
            lineage_blast=lineage_downstream,
        )

    def explain_module(self, path: str) -> ExplainModuleResult:
        """
        Combines API surface (Surveyor) and Purpose (Semanticist) for a module.
        Source of truth: static_analysis for API; purpose may be from LLM (semanticist).
        """
        self.trace.log_agent_action(
            agent="navigator",
            action="explain_module",
            evidence_source="static_analysis",
            confidence_score=0.9,
            path=path,
        )
        node_id = path.replace("\\", "/")
        g = self.kg.graph
        if node_id not in g:
            return ExplainModuleResult(
                source_of_truth="static_analysis",
                citations=[],
                confidence_score=0.0,
                path=path,
                api_surface={},
                purpose=None,
                domain_cluster=None,
            )
        data = dict(g.nodes[node_id])
        api_surface = {
            "public_functions": data.get("public_functions", []),
            "public_classes": [
                {"name": c.get("name"), "bases": c.get("bases", [])}
                for c in data.get("public_classes", [])
            ],
            "imports": data.get("imports", []),
            "sql_refs": data.get("sql_refs", []),
        }
        purpose = data.get("purpose")
        domain_cluster = data.get("domain_cluster")
        source = "llm_inference" if purpose else "static_analysis"
        citations = [self._cite(data.get("path", path), 1, "module definition")]
        if purpose:
            citations.append(self._cite(data.get("path", path), 0, "purpose (Semanticist)"))
        return ExplainModuleResult(
            source_of_truth=source,
            citations=citations,
            confidence_score=0.9,
            path=path,
            api_surface=api_surface,
            purpose=purpose,
            domain_cluster=domain_cluster,
        )

    # ------------------------------------------------------------------ #
    # Dispatcher (tool-based)
    # ------------------------------------------------------------------ #

    def dispatch(
        self,
        tool: Literal["find_implementation", "trace_lineage", "blast_radius", "explain_module"],
        **kwargs: Any,
    ) -> Any:
        """
        Single entry point for all Navigator tools.
        """
        if tool == "find_implementation":
            return self.find_implementation(kwargs["concept"])
        if tool == "trace_lineage":
            return self.trace_lineage(kwargs["dataset"], kwargs["direction"])
        if tool == "blast_radius":
            return self.blast_radius(kwargs["module_path"])
        if tool == "explain_module":
            return self.explain_module(kwargs["path"])
        raise ValueError(f"Unknown tool: {tool}")
