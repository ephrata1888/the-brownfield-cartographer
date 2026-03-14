from __future__ import annotations

import ast
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.analyzers.tree_sitter_analyzer import LanguageRouter
from src.models.module_node import ClassInfo, ModuleNode
from src.utils.trace import TraceLogger


_REF_RE = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Surveyor:
    repo_root: Path
    trace: TraceLogger
    router: LanguageRouter

    def analyze_module(self, path: str | Path) -> ModuleNode | None:
        p = Path(path)
        parsed = self.router.parse_file(p, trace=self.trace)
        if parsed is None:
            return None

        try:
            rel = p.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            # Fallback: best-effort relative form
            rel = Path(p.name)
        rel_str = str(rel).replace("\\", "/")

        node = ModuleNode(id=rel_str, path=rel_str, language=parsed.language)
        try:
            if parsed.language == "python":
                self._analyze_python(parsed.source_text, node)
            elif parsed.language == "sql":
                self._analyze_sql(parsed.source_text, node)
            else:
                # yaml/js/ts/unknown: still a node, but no extra extraction required in Phase 1
                pass
            return node
        except Exception as e:
            self.trace.log_error(stage="analyze_module", path=p, error=e, extra={"language": parsed.language})
            return None

    def _analyze_python(self, source: str, node: ModuleNode) -> None:
        tree = ast.parse(source)

        imports: list[str] = []
        public_functions: list[str] = []
        public_classes: list[ClassInfo] = []

        for n in tree.body:
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imports.append(alias.name)
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                if n.level and mod:
                    mod = "." * n.level + mod
                elif n.level and not mod:
                    mod = "." * n.level
                imports.append(mod)
            elif isinstance(n, ast.FunctionDef):
                if not n.name.startswith("_"):
                    public_functions.append(n.name)
            elif isinstance(n, ast.AsyncFunctionDef):
                if not n.name.startswith("_"):
                    public_functions.append(n.name)
            elif isinstance(n, ast.ClassDef):
                if not n.name.startswith("_"):
                    bases: list[str] = []
                    for b in n.bases:
                        if isinstance(b, ast.Name):
                            bases.append(b.id)
                        elif isinstance(b, ast.Attribute):
                            bases.append(self._flatten_attr(b))
                        else:
                            bases.append(ast.unparse(b) if hasattr(ast, "unparse") else "unknown")
                    public_classes.append(ClassInfo(name=n.name, bases=bases))

        node.imports = sorted(set(i for i in imports if i))
        node.public_functions = sorted(set(public_functions))
        node.public_classes = public_classes

    def _flatten_attr(self, a: ast.Attribute) -> str:
        parts: list[str] = []
        cur: ast.AST = a
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))

    def _analyze_sql(self, source: str, node: ModuleNode) -> None:
        node.sql_refs = sorted(set(_REF_RE.findall(source)))
        node.sql_sources = sorted({f"{a}.{b}" for (a, b) in _SOURCE_RE.findall(source)})

    def extract_git_velocity(self, path: str | Path, *, days: int = 90) -> int:
        """
        Returns the number of commits touching <path> within the last <days>.
        """
        p = Path(path)
        try:
            cmd = [
                "git",
                "log",
                "--oneline",
                f"--since={days} days ago",
                "--",
                str(p),
            ]
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                # No git history / not a repo / file not tracked → treat as zero velocity
                return 0
            out = proc.stdout.strip()
            if not out:
                return 0
            return len([ln for ln in out.splitlines() if ln.strip()])
        except Exception as e:
            self.trace.log_error(stage="extract_git_velocity", path=p, error=e, extra={"days": days})
            return 0

    def apply_velocity_flags(self, nodes: list[ModuleNode], *, days: int = 90) -> list[ModuleNode]:
        counts: list[tuple[int, ModuleNode]] = []
        for n in nodes:
            cc = self.extract_git_velocity(n.path, days=days)
            n.change_count_30d = cc
            counts.append((cc, n))

        n_files = len(nodes)
        if n_files == 0:
            return nodes

        top_k = max(1, int(math.ceil(0.2 * n_files)))
        ranked = sorted(counts, key=lambda t: t[0], reverse=True)
        top = {id(node) for _, node in ranked[:top_k]}

        for _, node in ranked:
            node.is_high_velocity = id(node) in top and node.change_count_30d > 0
        return nodes

    def analyze_paths(self, paths: Iterable[Path]) -> list[ModuleNode]:
        nodes: list[ModuleNode] = []
        for p in paths:
            n = self.analyze_module(p)
            if n is not None:
                nodes.append(n)
        return nodes

