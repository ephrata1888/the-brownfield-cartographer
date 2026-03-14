from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from src.analyzers.tree_sitter_analyzer import LanguageRouter
from src.utils.trace import TraceLogger


@dataclass(frozen=True)
class PythonLineageResult:
    file_id: str
    datasets_read: Set[str]
    datasets_written: Set[str]


class PythonLineageAnalyzer:
    """
    Uses tree-sitter to find Python data access patterns:
    - pandas.read_csv / pandas.read_sql
    - sqlalchemy.create_engine and .execute()
    - pyspark.read / .write
    """

    def __init__(self, repo_root: Path, router: LanguageRouter, trace: TraceLogger) -> None:
        self.repo_root = repo_root
        self.router = router
        self.trace = trace

    def analyze_files(self, files: Iterable[Path]) -> List[PythonLineageResult]:
        results: List[PythonLineageResult] = []
        for path in files:
            try:
                res = self.analyze_file(path)
                if res is not None:
                    results.append(res)
            except Exception as e:
                self.trace.log_error(stage="python_lineage_analyze_file", path=path, error=e)
        return results

    def analyze_file(self, path: Path) -> PythonLineageResult | None:
        parsed = self.router.parse_file(path, trace=self.trace)
        if parsed is None or parsed.language != "python" or parsed.tree is None:
            return None

        try:
            rel = path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            rel = Path(path.name)
        file_id = str(rel).replace("\\", "/")

        src_bytes = parsed.source_text.encode("utf-8", errors="replace")
        tree = parsed.tree

        datasets_read: Set[str] = set()
        datasets_written: Set[str] = set()

        # Generic DFS over the tree to find call expressions.
        cursor = tree.walk()
        stack: List[Tuple[object, bool]] = [(cursor.node, False)]  # type: ignore[arg-type]

        while stack:
            node, visited = stack.pop()
            if visited:
                continue

            # node.type strings come from tree-sitter-python grammar.
            ntype = getattr(node, "type", "")
            if ntype == "call":
                try:
                    self._handle_call(node, src_bytes, file_id, datasets_read, datasets_written)
                except Exception as e:
                    self.trace.log_error(
                        stage="python_lineage_call",
                        path=path,
                        error=e,
                    )

            # Push children
            for child in getattr(node, "children", []):
                stack.append((child, False))

        if not datasets_read and not datasets_written:
            return None
        return PythonLineageResult(file_id=file_id, datasets_read=datasets_read, datasets_written=datasets_written)

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #

    def _node_text(self, node, src: bytes) -> str:
        start, end = node.start_byte, node.end_byte
        return src[start:end].decode("utf-8", errors="replace")

    def _function_qualname(self, call_node, src: bytes) -> str:
        fn = None
        for child in getattr(call_node, "children", []):
            if getattr(child, "field_name", None) == "function":
                fn = child
                break
        if fn is None:
            return ""
        text = self._node_text(fn, src).strip()
        return text

    def _string_argument(self, call_node, src: bytes):
        # Grab first argument as text if it's a plain string literal.
        for child in getattr(call_node, "children", []):
            if getattr(child, "field_name", None) == "arguments":
                for arg in getattr(child, "children", []):
                    if getattr(arg, "type", "") in {"string", "string_literal"}:
                        raw = self._node_text(arg, src).strip()
                        if len(raw) >= 2 and raw[0] in {'"', "'"} and raw[-1] == raw[0]:
                            value = raw[1:-1]
                            return value
                        return raw
                    if getattr(arg, "type", "") in {"f_string", "interpolated_string"}:
                        # dynamic reference
                        return None
        return None

    def _record_dynamic(self, file_id: str, call_desc: str) -> None:
        self.trace.log_error(
            stage="python_lineage_dynamic_reference",
            path=file_id,
            error=RuntimeError("dynamic reference, cannot resolve"),
            extra={"call": call_desc},
        )

    def _handle_call(
        self,
        call_node,
        src: bytes,
        file_id: str,
        datasets_read: Set[str],
        datasets_written: Set[str],
    ) -> None:
        qualname = self._function_qualname(call_node, src)
        if not qualname:
            return

        # pandas.read_csv / read_sql
        if qualname.endswith("read_csv") or qualname.endswith("pandas.read_csv"):
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                datasets_read.add(arg)
            return

        if qualname.endswith("read_sql") or qualname.endswith("pandas.read_sql"):
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                datasets_read.add(arg)
            return

        # sqlalchemy engine.execute(...)
        if qualname.endswith("create_engine") or "sqlalchemy.create_engine" in qualname:
            # Connection string may be a static DSN.
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                datasets_read.add(arg)
            return

        if qualname.endswith("execute"):
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                # Treat the SQL text as a logical data source.
                datasets_read.add(arg)
            return

        # pyspark.read / .write
        if ".read" in qualname:
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                datasets_read.add(arg)
            return

        if ".write" in qualname:
            arg = self._string_argument(call_node, src)
            if arg is None:
                self._record_dynamic(file_id, f"{qualname}()")
            else:
                datasets_written.add(arg)

