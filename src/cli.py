from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

import typer
from networkx.readwrite import json_graph

# Allow `python src/cli.py ...` (script execution) while keeping `from src...` imports.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.models.semantic import DayOneReport
from src.orchestrator import CartographyOrchestrator


app = typer.Typer(add_completion=False)


@app.callback()
def _main() -> None:
    """
    Brownfield Cartographer CLI.
    """
    return


def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    skip_dirs = {
        ".git",
        ".cartography",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
    allowed_suffixes = {".py", ".sql", ".yml", ".yaml", ".js", ".ts", ".tsx"}

    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.suffix.lower() in allowed_suffixes:
            yield p


@app.command()
def analyze(repo_path: str) -> None:
    """
    Full pipeline: structural + lineage + semantic + archivist.
    Writes `.cartography/module_graph.json`, `.cartography/lineage_graph.json`,
    `.cartography/CODEBASE.md`, and `.cartography/onboarding_brief.md`.
    """
    repo_root = Path(repo_path).resolve()
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    kg = orchestrator.run_structural()
    lg = orchestrator.run_lineage()
    day_one_report = orchestrator.run_semantic(kg=kg, lg=lg)
    codebase, brief = orchestrator.run_archivist(kg=kg, lg=lg, day_one_report=day_one_report, update=True)

    # Console validation summary for quick sanity check.
    num_nodes = kg.graph.number_of_nodes()
    num_links = kg.graph.number_of_edges()
    hubs = sorted(
        kg.graph.nodes(data=True),
        key=lambda t: float(t[1].get("hub_score", 0.0)),
        reverse=True,
    )[:3]
    top_hub_ids = [node_id for node_id, _ in hubs]

    typer.echo(f"[Analyze] Total Nodes: {num_nodes}")
    typer.echo(f"[Analyze] Total Links: {num_links}")
    typer.echo(f"[Analyze] Top 3 Architectural Hubs: {top_hub_ids}")
    typer.echo("[Analyze] Wrote .cartography/module_graph.json, lineage_graph.json, CODEBASE.md, onboarding_brief.md")


@app.command()
def lineage(repo_path: str) -> None:
    """
    Build a data lineage graph and write `.cartography/lineage_graph.json`.
    """
    repo_root = Path(repo_path).resolve()
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    lg = orchestrator.run_lineage()

    num_nodes = lg.number_of_nodes()
    num_links = lg.number_of_edges()

    typer.echo(f"[Lineage] Total Nodes: {num_nodes}")
    typer.echo(f"[Lineage] Total Links: {num_links}")


@app.command()
def archive(repo_path: str) -> None:
    """
    Run structural + lineage (if needed), then Archivist.
    Writes `.cartography/CODEBASE.md` and `.cartography/onboarding_brief.md`.
    """
    repo_root = Path(repo_path).resolve()
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    kg = orchestrator.run_structural(incremental=True)
    lg = orchestrator.run_lineage()

    # Optional: load day-one report for richer onboarding brief
    day_one_path = repo_root / ".cartography" / "semantic_day_one_answers.json"
    day_one_report = None
    if day_one_path.exists():
        try:
            day_one_report = DayOneReport.model_validate_json(day_one_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    codebase, brief = orchestrator.run_archivist(kg=kg, lg=lg, day_one_report=day_one_report, update=True)
    typer.echo("[Archivist] CODEBASE.md and onboarding_brief.md written to .cartography/")


if __name__ == "__main__":
    app()

