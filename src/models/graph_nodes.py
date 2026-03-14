from __future__ import annotations

"""
Core graph node and edge schemas used by the Brownfield Cartographer.

These Pydantic models provide a stable, serializable representation of:
- ModuleNode (see `module_node.py`)
- DatasetNode: logical datasets / tables in the lineage graph
- FunctionNode: callable entry-points and tasks
- TransformationNode: processing steps that turn inputs into outputs
- GraphEdge: typed edges between the above (IMPORTS, PRODUCES, CONSUMES, CALLS, CONFIGURES)
"""

from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    IMPORTS = "IMPORTS"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    CALLS = "CALLS"
    CONFIGURES = "CONFIGURES"


class DatasetNode(BaseModel):
    id: str
    name: str
    kind: Literal["table", "view", "topic", "file", "model"] = "table"
    schema: str | None = None
    catalog: str | None = None
    description: str | None = None


class FunctionNode(BaseModel):
    id: str
    name: str
    module: str
    qualname: str | None = None
    is_task: bool = False
    description: str | None = None


class TransformationNode(BaseModel):
    id: str
    name: str
    implementation: str | None = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    description: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: EdgeType = EdgeType.IMPORTS

