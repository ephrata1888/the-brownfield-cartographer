from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClassInfo(BaseModel):
    name: str
    bases: list[str] = Field(default_factory=list)


class ModuleNode(BaseModel):
    id: str
    path: str
    language: Literal["python", "sql", "yaml", "javascript", "typescript", "unknown"] = "unknown"

    imports: list[str] = Field(default_factory=list)
    sql_refs: list[str] = Field(default_factory=list)
    sql_sources: list[str] = Field(default_factory=list)

    public_functions: list[str] = Field(default_factory=list)
    public_classes: list[ClassInfo] = Field(default_factory=list)

    change_count_30d: int = 0
    is_high_velocity: bool = False

    hub_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Semanticist-enriched fields
    purpose: str | None = None
    documentation_drift: bool = False
    drift_explanation: str | None = None
    domain_cluster: str | None = None

    def stem(self) -> str:
        return Path(self.path).stem

