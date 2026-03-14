"""
Phase 4: Agent 4 (The Archivist).
Produces final deliverables: CODEBASE.md (AI-injectable) and onboarding brief (human-readable).
Handles Cold Start (no existing data) and Update (refreshing existing MD files).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.models.semantic import DayOneReport
from src.utils.trace import TraceLogger

# Same project root as orchestrator: artifacts live under `<repo>/.cartography/`.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Archivist:
    """
    Produces structured markdown artifacts for AI context injection and human onboarding.
    """

    def __init__(
        self,
        repo_root: Path,
        trace: TraceLogger,
        kg: KnowledgeGraph,
        lg: LineageGraph,
        day_one_report: DayOneReport | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.trace = trace
        self.kg = kg
        self.lg = lg
        self.day_one_report = day_one_report

    def generate_CODEBASE_md(self, output_path: Path | None = None, *, update: bool = False) -> str:
        """
        Generate CODEBASE.md structured for AI context injection.
        Use clear headers and XML-style tags for downstream LLM parsing.
        Cold Start: write from current kg/lg. Update: overwrite existing file.
        """
        self.trace.log_agent_action(
            agent="archivist",
            action="generate_CODEBASE_md",
            evidence_source="static_analysis",
            confidence_score=1.0,
            path=output_path or _PROJECT_ROOT / ".cartography" / "CODEBASE.md",
        )

        out_dir = _PROJECT_ROOT / ".cartography"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = output_path or out_dir / "CODEBASE.md"

        # Data from graphs
        g = self.kg.graph
        n_nodes = g.number_of_nodes()
        n_edges = g.number_of_edges()

        # 1. Architecture Overview
        overview = (
            f"This codebase has {n_nodes} modules and {n_edges} dependency links. "
            "Structural analysis (PageRank) and data lineage (sources/sinks) are available below. "
            "Module purposes and domain clusters are indexed for semantic search."
        )

        # 2. Critical Path (Top 5 by PageRank)
        nodes_with_score = [
            (nid, g.nodes[nid].get("hub_score", 0.0))
            for nid in g.nodes()
        ]
        top5 = sorted(nodes_with_score, key=lambda x: float(x[1]), reverse=True)[:5]
        critical_path = [nid for nid, _ in top5]

        # 3. Data Sources & Sinks (Hydrologist semantics: in_degree=0, out_degree=0)
        sources = [n for n in self.lg.nodes() if self.lg.in_degree(n) == 0]
        sinks = [n for n in self.lg.nodes() if self.lg.out_degree(n) == 0]

        # 4. Known Debt
        circular = g.graph.get("circular_dependencies") or []
        drift_modules = [
            nid for nid, data in g.nodes(data=True)
            if data.get("documentation_drift") is True
        ]

        # 5. High-Velocity Files (top 20% by change count; from Surveyor)
        high_velocity = [
            nid for nid, data in g.nodes(data=True)
            if data.get("is_high_velocity") is True
        ]

        # 6. Module Purpose Index (by domain_cluster)
        by_domain: Dict[str, List[str]] = {}
        for nid, data in g.nodes(data=True):
            # Prefer the Semanticist's explicit purpose_statement, but fall
            # back to any legacy `purpose` field if present.
            purpose = data.get("purpose_statement") or data.get("purpose")
            domain = data.get("domain_cluster") or "uncategorized"
            if purpose or domain != "uncategorized":
                by_domain.setdefault(domain, []).append(
                    f"- {nid}: {purpose or '(no purpose)'}"
                )
        for d in by_domain:
            by_domain[d].sort()

        lines: List[str] = [
            "# CODEBASE",
            "",
            "<codebase_summary>",
            "## Architecture Overview",
            "",
            overview,
            "",
            "</codebase_summary>",
            "",
            "<critical_path>",
            "## Critical Path",
            "",
            "Top 5 modules by PageRank (architectural hubs):",
            "",
        ]
        for i, nid in enumerate(critical_path, 1):
            score = g.nodes[nid].get("hub_score", 0)
            lines.append(f"{i}. `{nid}` (hub_score={score:.6f})")
        lines.extend(["", "</critical_path>", ""])

        lines.extend([
            "<data_flow>",
            "## Data Sources & Sinks",
            "",
            "### Sources (in_degree=0)",
            "",
        ])
        for s in sorted(sources):
            lines.append(f"- {s}")
        lines.extend(["", "### Sinks (out_degree=0)", ""])
        for s in sorted(sinks):
            lines.append(f"- {s}")
        lines.extend(["", "</data_flow>", ""])

        lines.extend([
            "<known_debt>",
            "## Known Debt",
            "",
            "### Circular Dependencies",
            "",
        ])
        if circular:
            for comp in circular:
                lines.append(f"- Cycle: {comp}")
        else:
            lines.append("- None detected.")
        lines.extend(["", "### Documentation Drift (docstring vs. inferred purpose)", ""])
        for nid in sorted(drift_modules):
            expl = g.nodes[nid].get("drift_explanation") or "N/A"
            lines.append(f"- `{nid}`: {expl}")
        if not drift_modules:
            lines.append("- None flagged.")
        lines.extend(["", "</known_debt>", ""])

        lines.extend([
            "<high_velocity>",
            "## High-Velocity Files",
            "",
            "Top 20% of files by change count (Surveyor).",
            "",
        ])
        for nid in sorted(high_velocity):
            cc = g.nodes[nid].get("change_count_30d", 0)
            lines.append(f"- `{nid}` (changes={cc})")
        if not high_velocity:
            lines.append("- None in this run.")
        lines.extend(["", "</high_velocity>", ""])

        lines.extend([
            "<module_purpose_index>",
            "## Module Purpose Index",
            "",
            "Grouped by domain_cluster (Semanticist).",
            "",
        ])
        for domain in sorted(by_domain.keys()):
            lines.append(f"### {domain}")
            lines.append("")
            lines.extend(by_domain[domain])
            lines.append("")
        lines.extend(["</module_purpose_index>", ""])

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        return content

    def generate_onboarding_brief_md(self, output_path: Path | None = None, *, update: bool = False) -> str:
        """
        Human-readable report answering the Five FDE Questions with evidence citations (file:line).
        Cold Start: if day_one_report is None, write a placeholder. Update: overwrite existing.
        """
        self.trace.log_agent_action(
            agent="archivist",
            action="generate_onboarding_brief_md",
            evidence_source="static_analysis" if not self.day_one_report else "llm_inference",
            confidence_score=0.9 if self.day_one_report else 0.5,
            path=output_path,
        )

        out_dir = _PROJECT_ROOT / ".cartography"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = output_path or out_dir / "onboarding_brief.md"

        lines: List[str] = [
            "# Onboarding Brief: Five FDE Day-One Questions",
            "",
            "This report answers the five critical questions for a First Day in Engineering (FDE) assessment.",
            "",
        ]

        if self.day_one_report:
            r = self.day_one_report
            for name, answer in [
                ("Primary Data Ingestion Path", r.ingestion_path),
                ("3–5 Critical Output Datasets", r.critical_outputs),
                ("Blast Radius of Architectural Hubs", r.blast_radius_hubs),
                ("Where Business Logic is Concentrated", r.logic_concentration),
                ("Git Velocity Hotspots", r.git_velocity_hotspots),
            ]:
                lines.extend([f"## {name}", ""])
                lines.append(answer.answer)
                lines.append("")
                if answer.citations:
                    lines.append("**Evidence (file:line):**")
                    for c in answer.citations:
                        lines.append(f"- `{c.file}:{c.line}`" + (f" — {c.context}" if c.context else ""))
                    lines.append("")
        else:
            lines.append("*No Day-One report available (cold start). Run the Semanticist and re-run the Archivist to populate this section.*")
            lines.append("")

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        return content
