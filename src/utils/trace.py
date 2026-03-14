from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TraceLogger:
    trace_path: Path

    def log_error(
        self,
        *,
        stage: str,
        path: str | Path,
        error: Exception,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": "error",
            "stage": stage,
            "path": str(path),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        if extra:
            payload["extra"] = extra

        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_event(
        self,
        *,
        stage: str,
        path: str | Path,
        message: str,
        extra: dict[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "stage": stage,
            "path": str(path),
            "message": message,
        }
        if extra:
            payload["extra"] = extra

        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_agent_action(
        self,
        *,
        agent: str,
        action: str,
        evidence_source: str,
        confidence_score: float,
        path: str | Path | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """
        Log every agent action across the pipeline.
        Fields: timestamp, agent, action, evidence_source, confidence_score.
        """
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "stage": "agent_action",
            "agent": agent,
            "action": action,
            "evidence_source": evidence_source,
            "confidence_score": confidence_score,
        }
        if path is not None:
            payload["path"] = str(path)
        if extra:
            payload["extra"] = extra
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

