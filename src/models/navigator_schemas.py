"""
Pydantic schemas for Navigator tool outputs.
Every tool output includes source_of_truth and file:line citations.
"""
from __future__ import annotations

from typing import Any, List, Literal, Tuple

from pydantic import BaseModel, Field


class FileLineCitation(BaseModel):
    file: str
    line: int
    context: str | None = None

    def to_string(self) -> str:
        base = f"{self.file}:{self.line}"
        return f"{base} ({self.context})" if self.context else base


class ToolResult(BaseModel):
    """Base for all Navigator tool results."""
    source_of_truth: Literal["static_analysis", "llm_inference"]
    citations: list[FileLineCitation] = Field(default_factory=list)
    confidence_score: float = 1.0


class FindImplementationResult(ToolResult):
    tool: Literal["find_implementation"] = "find_implementation"
    concept: str
    matches: list[dict[str, Any]] = Field(default_factory=list)


class TraceLineageResult(ToolResult):
    tool: Literal["trace_lineage"] = "trace_lineage"
    dataset: str
    direction: Literal["upstream", "downstream"]
    nodes: list[str] = Field(default_factory=list)
    edges: List[Tuple[str, str]] = Field(default_factory=list)


class BlastRadiusResult(ToolResult):
    tool: Literal["blast_radius"] = "blast_radius"
    module_path: str
    downstream_count: int = 0
    affected_nodes: list[str] = Field(default_factory=list)
    structural_blast: list[str] = Field(default_factory=list)
    lineage_blast: list[str] = Field(default_factory=list)


class ExplainModuleResult(ToolResult):
    tool: Literal["explain_module"] = "explain_module"
    path: str
    api_surface: dict[str, Any] = Field(default_factory=dict)
    purpose: str | None = None
    domain_cluster: str | None = None
