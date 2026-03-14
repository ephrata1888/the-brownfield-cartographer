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
from src.agents.hydrologist import Hydrologist
from src.agents.navigator import Navigator
from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.lineage_graph import LineageGraph
from src.utils.trace import TraceLogger


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
    Writes artifacts under the project root `.cartography/` (not inside the analyzed repo).
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
    typer.echo(f"[Analyze] Wrote outputs to {_ROOT / '.cartography'}")


@app.command()
def lineage(repo_path: str) -> None:
    """
    Build a data lineage graph; writes to project root `.cartography/lineage_graph.json`.
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
    Writes project root `.cartography/CODEBASE.md` and `onboarding_brief.md`.
    """
    repo_root = Path(repo_path).resolve()
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    kg = orchestrator.run_structural(incremental=True)
    lg = orchestrator.run_lineage()

    # Optional: load day-one report for richer onboarding brief
    day_one_path = _ROOT / ".cartography" / "semantic_day_one_answers.json"
    day_one_report = None
    if day_one_path.exists():
        try:
            day_one_report = DayOneReport.model_validate_json(day_one_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    codebase, brief = orchestrator.run_archivist(kg=kg, lg=lg, day_one_report=day_one_report, update=True)
    typer.echo(f"[Archivist] Wrote to {_ROOT / '.cartography'}")


@app.command()
def query(
    repo_path: str,
    tool: str = typer.Argument(
        ...,
        help="Navigator tool to run: one of [find_implementation, trace_lineage, blast_radius, explain_module]",
    ),
    param: str = typer.Argument(
        ...,
        help="Primary parameter for the selected tool (concept, dataset, or module path).",
    ),
    direction: str = typer.Option(
        "downstream",
        "--direction",
        "-d",
        help="For trace_lineage: 'upstream' or 'downstream'.",
    ),
) -> None:
    """
    Navigator mode: interactive read-only querying over the structural and
    lineage graphs using the Navigator agent tools.

    Tools:
    - find_implementation <concept>
    - trace_lineage <dataset> --direction [upstream|downstream]
    - blast_radius <module_path>
    - explain_module <module_path>
    """
    repo_root = Path(repo_path).resolve()

    # Reuse existing artifacts when present to keep query mode fast; otherwise
    # build fresh graphs.
    orchestrator = CartographyOrchestrator(repo_root=repo_root)
    cartography_dir = orchestrator.cartography_dir
    module_graph_path = cartography_dir / "module_graph.json"
    lineage_graph_path = cartography_dir / "lineage_graph.json"

    if module_graph_path.exists():
        data = json.loads(module_graph_path.read_text(encoding="utf-8"))
        kg = KnowledgeGraph(graph=json_graph.node_link_graph(data, directed=True, multigraph=False))
    else:
        kg = orchestrator.run_structural(incremental=True)

    if lineage_graph_path.exists():
        data = json.loads(lineage_graph_path.read_text(encoding="utf-8"))
        lg = LineageGraph(json_graph.node_link_graph(data, directed=True, multigraph=False))
    else:
        lg = orchestrator.run_lineage()

    trace = TraceLogger(cartography_dir / "cartography_trace.jsonl")
    hydrologist = Hydrologist(repo_root=repo_root, trace=trace, graph=lg)
    navigator = Navigator(repo_root=repo_root, trace=trace, kg=kg, hydrologist=hydrologist)

    if tool == "find_implementation":
        result = navigator.find_implementation(concept=param)
    elif tool == "trace_lineage":
        dir_lit = "downstream" if direction not in {"upstream", "downstream"} else direction
        result = navigator.trace_lineage(dataset=param, direction=dir_lit)  # type: ignore[arg-type]
    elif tool == "blast_radius":
        result = navigator.blast_radius(module_path=param)
    elif tool == "explain_module":
        result = navigator.explain_module(path=param)
    else:
        raise typer.BadParameter(f"Unknown Navigator tool: {tool}")

    typer.echo(result.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()

