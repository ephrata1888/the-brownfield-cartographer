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
    Analyze a repository and write `.cartography/module_graph.json`.
    """
    repo_root = Path(repo_path).resolve()
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    kg = orchestrator.run_structural()

    # Console validation summary (unchanged)
    num_nodes = kg.graph.number_of_nodes()
    num_links = kg.graph.number_of_edges()

    # Top 3 hubs by PageRank (already populated in KnowledgeGraph._run_algorithms)
    hubs = sorted(
        kg.graph.nodes(data=True),
        key=lambda t: float(t[1].get("hub_score", 0.0)),
        reverse=True,
    )[:3]
    top_hub_ids = [node_id for node_id, _ in hubs]

    typer.echo(f"Total Nodes: {num_nodes}")
    typer.echo(f"Total Links: {num_links}")
    typer.echo(f"Top 3 Architectural Hubs: {top_hub_ids}")


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

    # Files are already serialized by the orchestrator; CLI only reports stats here.


if __name__ == "__main__":
    app()

