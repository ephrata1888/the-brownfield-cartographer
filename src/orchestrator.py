"""
Cartography Orchestrator: wires Surveyor, Hydrologist, Semanticist, Archivist.
Supports full run and incremental update mode using git diff.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import networkx as nx
from networkx.readwrite import json_graph

from src.agents.archivist import Archivist
from src.agents.hydrologist import Hydrologist
from src.agents.semanticist import Semanticist
from src.agents.surveyor import Surveyor
from src.analyzers.tree_sitter_analyzer import LanguageRouter
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.models.module_node import ModuleNode
from src.models.semantic import DayOneReport
from src.utils.trace import TraceLogger


def _cartography_dir(repo_root: Path) -> Path:
    return Path.cwd()/ ".cartography"


class CartographyOrchestrator:
    """
    Wires Surveyor (structural), Hydrologist (lineage), Semanticist (purpose/day-one),
    and Archivist (CODEBASE.md, onboarding brief) into a single pipeline.
    Supports incremental update: only re-analyze files changed since last run.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.trace = TraceLogger(self.repo_root / "cartography_trace.jsonl")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_structural(self, incremental: bool = True) -> KnowledgeGraph:
        """
        Run the Surveyor to produce the structural graph and PageRank.
        If incremental=True and .cartography state exists, only update changed nodes (git diff).
        Serializes to `.cartography/module_graph.json`.
        """
        out_dir = _cartography_dir(self.repo_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        module_graph_path = out_dir / "module_graph.json"

        router = LanguageRouter()
        surveyor = Surveyor(repo_root=self.repo_root, trace=self.trace, router=router)
        all_paths = list(self._iter_repo_files())

        if incremental and module_graph_path.exists():
            try:
                changed = self._get_changed_paths()
                existing_nodes = self._load_module_nodes_from_graph(module_graph_path)
                if existing_nodes is not None:
                    node_list = self._merge_nodes(
                        all_paths=all_paths,
                        changed_rel_paths=changed,
                        existing_nodes=existing_nodes,
                        surveyor=surveyor,
                    )
                    nodes = node_list
                else:
                    nodes = surveyor.analyze_paths(all_paths)
            except Exception as e:
                self.trace.log_error(
                    stage="run_structural_incremental",
                    path=str(module_graph_path),
                    error=e,
                )
                nodes = surveyor.analyze_paths(all_paths)
        else:
            nodes = surveyor.analyze_paths(all_paths)

        nodes = surveyor.apply_velocity_flags(nodes, days=30)
        kg = KnowledgeGraph.build(nodes)

        data = json_graph.node_link_data(kg.graph, edges="links")
        module_graph_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_last_run_commit()
        return kg

    def run_lineage(self) -> LineageGraph:
        """
        Run the Hydrologist to produce the data lineage graph.
        Re-runs full lineage (global metrics). Serializes to `.cartography/lineage_graph.json`.
        """
        hydrologist = Hydrologist(repo_root=self.repo_root, trace=self.trace)
        lg = hydrologist.build_graph()

        out_dir = _cartography_dir(self.repo_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "lineage_graph.json"

        data = json_graph.node_link_data(lg, edges="links")
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return lg

    def run_all(self, incremental: bool = True) -> Tuple[KnowledgeGraph, LineageGraph]:
        """
        Run Surveyor then Hydrologist in sequence.
        """
        kg = self.run_structural(incremental=incremental)
        lg = self.run_lineage()
        return kg, lg

    def run_semantic(self, kg: KnowledgeGraph, lg: LineageGraph) -> DayOneReport:
        """
        Run the Semanticist: purpose statements, domain clustering, day-one answers.
        Serializes to `.cartography/semantic_day_one_answers.json`.
        """
        self.trace.log_agent_action(
            agent="orchestrator",
            action="run_semantic",
            evidence_source="static_analysis",
            confidence_score=1.0,
        )
        semanticist = Semanticist(
            repo_root=self.repo_root,
            trace=self.trace,
            kg=kg,
            lg=lg,
        )
        purposes = semanticist.generate_purpose_statements()
        _clusters = semanticist.cluster_into_domains(purposes)
        report = semanticist.answer_day_one_questions()

        out_dir = _cartography_dir(self.repo_root)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Persist enriched semantic annotations back to the module graph so that
        # subsequent runs (or standalone Archivist invocations) can read
        # purpose statements and domain clusters from disk.
        module_graph_path = out_dir / "module_graph.json"
        data = json_graph.node_link_data(kg.graph, edges="links")
        module_graph_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        out_path = out_dir / "semantic_day_one_answers.json"
        out_path.write_text(report.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    def run_archivist(
        self,
        kg: KnowledgeGraph,
        lg: LineageGraph,
        day_one_report: Optional[DayOneReport] = None,
        update: bool = False,
    ) -> Tuple[str, str]:
        """
        Run the Archivist: generate CODEBASE.md and onboarding_brief.md.
        Cold start: day_one_report can be None. Update: overwrite existing files.
        Returns (codebase_md_content, onboarding_brief_content).
        """
        self.trace.log_agent_action(
            agent="orchestrator",
            action="run_archivist",
            evidence_source="static_analysis",
            confidence_score=1.0,
        )
        out_dir = _cartography_dir(self.repo_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        archivist = Archivist(
            repo_root=self.repo_root,
            trace=self.trace,
            kg=kg,
            lg=lg,
            day_one_report=day_one_report,
        )
        codebase = archivist.generate_CODEBASE_md(output_path=out_dir / "CODEBASE.md", update=update)
        brief = archivist.generate_onboarding_brief_md(output_path=out_dir / "onboarding_brief.md", update=update)
        return codebase, brief

    # ------------------------------------------------------------------ #
    # Incremental update helpers
    # ------------------------------------------------------------------ #

    def _cartography_state_exists(self) -> bool:
        d = _cartography_dir(self.repo_root)
        return (d / "module_graph.json").exists()

    def _get_changed_paths(self) -> Set[str]:
        """
        Return set of repo-relative paths (with forward slashes) that changed since last run.
        Uses git diff --name-only from last stored commit, or HEAD if no stored commit.
        """
        out_dir = _cartography_dir(self.repo_root)
        last_run = out_dir / "last_run_commit.txt"
        ref = "HEAD"
        if last_run.exists():
            ref = last_run.read_text(encoding="utf-8").strip() or "HEAD"
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only", ref, "--"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                return set()
            out = proc.stdout.strip()
            if not out:
                return set()
            return {p.replace("\\", "/") for p in out.splitlines() if p.strip()}
        except Exception:
            return set()

    def _write_last_run_commit(self) -> None:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                out_dir = _cartography_dir(self.repo_root)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "last_run_commit.txt").write_text(proc.stdout.strip(), encoding="utf-8")
        except Exception:
            pass

    def _load_module_nodes_from_graph(self, path: Path) -> Optional[List[ModuleNode]]:
        """
        Load node list from a previously saved module_graph.json (node_link_data format).
        Returns None if the file is invalid or cannot be converted to ModuleNodes.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        nodes_data = data.get("nodes")
        if not nodes_data:
            return None
        result: List[ModuleNode] = []
        for nd in nodes_data:
            nid = nd.get("id")
            if not nid:
                continue
            # Ensure id and path for ModuleNode
            if "path" not in nd:
                nd["path"] = nid
            try:
                result.append(ModuleNode(**nd))
            except Exception:
                continue
        return result if result else None

    def _merge_nodes(
        self,
        all_paths: List[Path],
        changed_rel_paths: Set[str],
        existing_nodes: List[ModuleNode],
        surveyor: Surveyor,
    ) -> List[ModuleNode]:
        """
        Build full node list: use existing node for unchanged files, re-analyze changed files.
        Drop nodes whose path no longer exists in the repo.
        """
        existing_by_id = {n.id: n for n in existing_nodes}
        rel_paths_current = set()
        result: List[ModuleNode] = []

        for p in all_paths:
            try:
                rel = p.resolve().relative_to(self.repo_root.resolve())
            except ValueError:
                rel = Path(p.name)
            rel_str = str(rel).replace("\\", "/")
            rel_paths_current.add(rel_str)

            if rel_str in changed_rel_paths or rel_str not in existing_by_id:
                node = surveyor.analyze_module(p)
                if node is not None:
                    result.append(node)
            else:
                result.append(existing_by_id[rel_str])

        return result

    def _iter_repo_files(self) -> Iterable[Path]:
        skip_dirs = {
            ".git", ".cartography", ".venv", "venv", "node_modules",
            "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        }
        allowed_suffixes = {".py", ".sql", ".yml", ".yaml", ".js", ".ts", ".tsx"}

        for p in self.repo_root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in skip_dirs for part in p.parts):
                continue
            if p.suffix.lower() in allowed_suffixes:
                yield p
