from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PurposeStatement(BaseModel):
    module_id: str
    purpose: str
    has_docstring: bool = False
    documentation_drift: bool = False
    drift_explanation: Optional[str] = None


class DomainCluster(BaseModel):
    name: str
    modules: List[str] = Field(default_factory=list)


class DayOneCitation(BaseModel):
    file: str
    line: int
    context: str | None = None


class DayOneAnswer(BaseModel):
    question: str
    answer: str
    citations: List[DayOneCitation] = Field(default_factory=list)


class DayOneReport(BaseModel):
    ingestion_path: DayOneAnswer
    critical_outputs: DayOneAnswer
    blast_radius_hubs: DayOneAnswer
    logic_concentration: DayOneAnswer
    git_velocity_hotspots: DayOneAnswer

