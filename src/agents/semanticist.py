from __future__ import annotations

import math
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import networkx as nx
from google import genai

from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.models.module_node import ModuleNode
from src.models.semantic import (
    DayOneAnswer,
    DayOneCitation,
    DayOneReport,
    DomainCluster,
    PurposeStatement,
)
from src.utils.trace import TraceLogger


class ContextWindowBudget:
    """
    Simple token budget manager using a 4-char-per-token heuristic.
    """

    def __init__(
        self,
        max_tokens_flash: int = 1_000_000,
        max_tokens_pro: int = 200_000,
    ) -> None:
        self.max_tokens_flash = max_tokens_flash
        self.max_tokens_pro = max_tokens_pro
        self.used_flash = 0
        self.used_pro = 0

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    def record(self, model: str, tokens: int) -> None:
        if "pro" in model:
            self.used_pro += tokens
        else:
            self.used_flash += tokens

    def remaining(self, model: str) -> int:
        if "pro" in model:
            return max(0, self.max_tokens_pro - self.used_pro)
        return max(0, self.max_tokens_flash - self.used_flash)


# Preferred Gemini model candidates for the Gemini v1 API, ordered by preference.
MODELS: List[str] = [
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
]


class LLMClient:
    """
    Thin abstraction over the underlying LLM provider.

    NOTE: This is intentionally left as a stub; integrate your actual client
    (e.g., Gemini SDK) here.
    """

    def __init__(self, trace: TraceLogger, budget: ContextWindowBudget) -> None:
        self.trace = trace
        self.budget = budget

        # Detect Gemini API key presence (without hard dependency on the SDK).
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            # Inform the trace that we are running in stub mode so callers
            # understand why semantic fields may look generic.
            self.trace.log_event(
                stage="semanticist.llm_client",
                path="",
                message="No GEMINI_API_KEY/GOOGLE_API_KEY set; using stub LLM responses.",
                extra={},
            )

    def generate(self, *, model: str, stage: str, path: str, system_prompt: str, user_prompt: str) -> str:
        text = system_prompt + "\n\n" + user_prompt
        tokens = self.budget.estimate_tokens(text)
        self.budget.record(model, tokens)

        # Log all calls and reasoning
        self.trace.log_event(
            stage=f"semanticist.{stage}",
            path=path,
            message="LLM call",
            extra={
                "model": model,
                "estimated_tokens": tokens,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "has_gemini_api_key": bool(self.api_key),
            },
        )

        if not self.api_key:
            return "Semantic summary unavailable: no Gemini API key configured."

        # Try a sequence of known-good Gemini v1 model IDs. We intentionally
        # ignore the caller's `model` hint here to avoid coupling to any
        # deprecated IDs; instead we iterate over `MODELS` in order.
        models_to_try: List[str] = MODELS.copy()

        client = genai.Client(
            api_key=self.api_key,
            http_options={"api_version": "v1"},
        )

        def _call(model_name: str) -> str:
            # Embed the system instructions into the prompt body so the API
            # only receives a single `contents` string, which is compatible
            # across SDK versions.
            combined_prompt = f"INSTRUCTIONS: {system_prompt}\n\nTASK: {user_prompt}"
            response = client.models.generate_content(
                model=model_name,
                contents=combined_prompt,
            )
            text_out = getattr(response, "text", None)
            if not text_out:
                text_out = str(response)
            return text_out

        last_error: Exception | None = None
        for model_name in models_to_try:
            try:
                return _call(model_name)
            except Exception as e:
                last_error = e
                continue

        # If we reach here, all model attempts failed.
        self.trace.log_error(
            stage=f"semanticist.{stage}",
            path=path,
            error=last_error or Exception("Unknown LLM error"),
        )
        attempted = ", ".join(models_to_try)
        return (
            f"LLM generation failed for stage '{stage}' on {path} "
            f"(models_tried=[{attempted}]): {last_error}"
        )


@dataclass
class Semanticist:
    repo_root: Path
    trace: TraceLogger
    kg: KnowledgeGraph
    lg: LineageGraph
    budget: ContextWindowBudget | None = None

    def __post_init__(self) -> None:
        if self.budget is None:
            self.budget = ContextWindowBudget()
        self.llm = LLMClient(self.trace, self.budget)

    # ------------------------------------------------------------------ #
    # Purpose statements & documentation drift
    # ------------------------------------------------------------------ #

    def generate_purpose_statement_for_node(self, module_id: str) -> PurposeStatement | None:
        node_data = self.kg.graph.nodes.get(module_id)
        if not node_data:
            return None

        path = self.repo_root / node_data.get("path", module_id)
        try:
            raw_code = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.trace.log_error(stage="semanticist.read_code", path=path, error=e)
            return None

        docstring = self._extract_docstring(raw_code) if node_data.get("language") == "python" else None

        system_prompt = (
            "You are an expert software architect. "
            "Given the raw source code of a module, explain the BUSINESS PURPOSE "
            "(what it does and why it exists) in 2-4 sentences. "
            "IGNORE any existing docstrings or comments; infer from the logic."
        )
        user_prompt = f"Module path: {node_data.get('path')}\n\n```python\n{raw_code}\n```"

        # Bulk module analysis → flash-tier model (hint; LLMClient maintains its own fallback list)
        model_name = MODELS[0]
        purpose = self.llm.generate(
            model=model_name,
            stage="purpose_statement",
            path=str(path),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        has_doc = bool(docstring)
        documentation_drift = False
        drift_explanation: str | None = None

        if has_doc:
            if not self._semantically_similar(purpose, docstring):
                documentation_drift = True
                drift_explanation = "LLM-inferred purpose appears to diverge from existing docstring."

        # Update node payload in the graph
        # Store under both `purpose` (legacy) and `purpose_statement` (for Archivist).
        node_data["purpose"] = purpose
        node_data["purpose_statement"] = purpose
        node_data["documentation_drift"] = documentation_drift
        node_data["drift_explanation"] = drift_explanation

        return PurposeStatement(
            module_id=module_id,
            purpose=purpose,
            has_docstring=has_doc,
            documentation_drift=documentation_drift,
            drift_explanation=drift_explanation,
        )

    def generate_purpose_statements(self) -> List[PurposeStatement]:
        results: List[PurposeStatement] = []
        for module_id, data in self.kg.graph.nodes(data=True):
            # Limit to code-bearing modules (python/sql/js/ts)
            if data.get("language") in {"python", "sql", "javascript", "typescript"}:
                ps = self.generate_purpose_statement_for_node(module_id)
                if ps is not None:
                    results.append(ps)
        return results

    # ------------------------------------------------------------------ #
    # Domain clustering
    # ------------------------------------------------------------------ #

    def cluster_into_domains(self, purposes: Iterable[PurposeStatement]) -> List[DomainCluster]:
        """
        Group modules into 5-8 logical domains using the LLM. This method
        prepares a prompt and expects a structured (e.g. JSON) response,
        but for now it returns a single default cluster as a stub.
        """
        items = [{"module_id": p.module_id, "purpose": p.purpose} for p in purposes]
        system_prompt = (
            "You are organizing a large analytics codebase into domains. "
            "Given a list of modules and their business purpose summaries, "
            "group them into 5-8 logical domains (e.g., Ingestion, Transformation, Marts, Monitoring). "
            "Return a JSON array of objects with fields: name, modules[]."
        )
        user_prompt = f"Modules and purposes:\n{items}"

        model_name = MODELS[0]
        _raw = self.llm.generate(
            model=model_name,
            stage="cluster_into_domains",
            path=str(self.repo_root),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Stub: assign everything to a single domain until real parsing is wired in.
        all_ids = [p.module_id for p in purposes]
        clusters = [DomainCluster(name="default_domain", modules=all_ids)]

        # Update graph nodes
        for cluster in clusters:
            for module_id in cluster.modules:
                if module_id in self.kg.graph.nodes:
                    self.kg.graph.nodes[module_id]["domain_cluster"] = cluster.name

        return clusters

    # ------------------------------------------------------------------ #
    # Day-one questions
    # ------------------------------------------------------------------ #

    def answer_day_one_questions(self) -> DayOneReport:
        """
        Synthesis pass that feeds structural (PageRank, velocity) and lineage
        information into the LLM to answer the Five FDE Day-One questions.
        """
        structural_view = self._summarize_structural()
        lineage_view = self._summarize_lineage()

        system_prompt = (
            "You are a senior data engineer performing a brownfield assessment.\n"
            "You will receive:\n"
            "- A structural summary (PageRank hub scores, git velocity, file info).\n"
            "- A lineage summary (datasets, tasks, sources, sinks, blast radius hints).\n\n"
            "You must answer the following five questions:\n"
            "1) Primary Ingestion Path\n"
            "2) 3-5 Critical Output Datasets\n"
            "3) Blast Radius of architectural hubs\n"
            "4) Where Business Logic is concentrated\n"
            "5) Git Velocity hotspots\n\n"
            "IMPORTANT: For every factual statement, include explicit citations in the form "
            "`<file_path>:<line_number>` referencing evidence from the input summaries."
        )

        user_prompt = f"STRUCTURAL:\n{structural_view}\n\nLINEAGE:\n{lineage_view}"

        # Final synthesis → pro-tier model (hint; LLMClient maintains its own fallback list)
        model_name = MODELS[-1]
        _raw = self.llm.generate(
            model=model_name,
            stage="day_one_questions",
            path=str(self.repo_root),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # We do not attempt to parse the pro model's free-form answer here;
        # instead, we return placeholder answers that remind the caller that
        # real LLM integration is needed for semantic synthesis.
        placeholder = "See LLM-generated assessment (integration required)."
        empty_citations: List[DayOneCitation] = []

        return DayOneReport(
            ingestion_path=DayOneAnswer(
                question="Primary Data Ingestion Path",
                answer=placeholder,
                citations=empty_citations,
            ),
            critical_outputs=DayOneAnswer(
                question="3-5 Critical Output Datasets",
                answer=placeholder,
                citations=empty_citations,
            ),
            blast_radius_hubs=DayOneAnswer(
                question="Blast Radius of Architectural Hubs",
                answer=placeholder,
                citations=empty_citations,
            ),
            logic_concentration=DayOneAnswer(
                question="Where Business Logic is Concentrated",
                answer=placeholder,
                citations=empty_citations,
            ),
            git_velocity_hotspots=DayOneAnswer(
                question="Git Velocity Hotspots",
                answer=placeholder,
                citations=empty_citations,
            ),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _extract_docstring(self, raw_code: str) -> str | None:
        """
        Best-effort extraction of the top-level Python module docstring
        without importing or executing the code.
        """
        import ast

        try:
            tree = ast.parse(raw_code)
            return ast.get_docstring(tree)
        except Exception:
            return None

    def _semantically_similar(self, a: str, b: str, threshold: float = 0.3) -> bool:
        """
        Extremely cheap bag-of-words similarity heuristic to approximate
        whether two texts broadly agree. This is only a stopgap until an
        embedding-based strategy is wired in.
        """
        if not a or not b:
            return False
        ta = {t.lower() for t in a.split() if len(t) > 3}
        tb = {t.lower() for t in b.split() if len(t) > 3}
        if not ta or not tb:
            return False
        overlap = len(ta & tb) / float(len(ta | tb))
        return overlap >= threshold

    def _summarize_structural(self) -> Dict[str, Dict[str, float | int | str]]:
        """
        Build a compact, model-friendly view of the structural graph.
        """
        summary: Dict[str, Dict[str, float | int | str]] = {}
        for node_id, data in self.kg.graph.nodes(data=True):
            summary[node_id] = {
                "path": data.get("path", node_id),
                "hub_score": float(data.get("hub_score", 0.0)),
                "change_count_30d": int(data.get("change_count_30d", 0)),
                "is_high_velocity": bool(data.get("is_high_velocity", False)),
                "language": data.get("language", "unknown"),
            }
        return summary

    def _summarize_lineage(self) -> Dict[str, Dict[str, str | List[str]]]:
        """
        Build a compact view of the lineage graph: neighbors, types, etc.
        """
        g: nx.DiGraph = self.lg
        out: Dict[str, Dict[str, str | List[str]]] = {}
        for node in g.nodes:
            node_type = g.nodes[node].get("type", "unknown")
            downstream = [b for _, b in g.out_edges(node)]
            upstream = [a for a, _ in g.in_edges(node)]
            out[node] = {
                "type": node_type,
                "downstream": downstream,
                "upstream": upstream,
            }
        return out

