from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from tree_sitter import Language as TS_Language
from tree_sitter import Parser as TS_Parser

from src.utils.trace import TraceLogger


Language = Literal["python", "sql", "yaml", "javascript", "typescript", "unknown"]


@dataclass(frozen=True)
class ParsedFile:
    path: Path
    language: Language
    source_text: str
    tree: Any | None = None
    yaml_obj: Any | None = None


class LanguageRouter:
    def __init__(self) -> None:
        self._parsers: dict[Language, Any] = {}

        # Prefer tree-sitter-languages when available.
        try:
            from tree_sitter_languages import get_parser as _get_parser  # type: ignore

            self._parsers.update(
                {
                    "python": _get_parser("python"),
                    "sql": _get_parser("sql"),
                    "javascript": _get_parser("javascript"),
                    "typescript": _get_parser("typescript"),
                }
            )
            return
        except Exception:
            pass

        # Fallback: per-language grammar packages.
        self._parsers.update(self._fallback_parsers())

    def _fallback_parsers(self) -> dict[Language, Any]:
        def _mk_parser(lang: TS_Language) -> TS_Parser:
            p = TS_Parser()
            if hasattr(p, "set_language"):
                p.set_language(lang)  # tree_sitter <= 0.21
                return p
            # tree_sitter newer versions may use constructor language
            return TS_Parser(lang)  # type: ignore[call-arg]

        parsers: dict[Language, Any] = {}
        try:
            import tree_sitter_python as tsp  # type: ignore

            parsers["python"] = _mk_parser(TS_Language(tsp.language()))
        except Exception:
            pass

        try:
            import tree_sitter_sql as tss  # type: ignore

            parsers["sql"] = _mk_parser(TS_Language(tss.language()))
        except Exception:
            pass

        try:
            import tree_sitter_javascript as tsj  # type: ignore

            parsers["javascript"] = _mk_parser(TS_Language(tsj.language()))
        except Exception:
            pass

        try:
            import tree_sitter_typescript as tst  # type: ignore

            # Prefer TypeScript; TSX is routed to "typescript" by file extension.
            lang_fn = getattr(tst, "language_typescript", None) or getattr(tst, "language", None)
            if lang_fn is not None:
                parsers["typescript"] = _mk_parser(TS_Language(lang_fn()))
        except Exception:
            pass

        return parsers

    def route(self, path: str | Path) -> Language:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix == ".sql":
            return "sql"
        if suffix in {".yml", ".yaml"}:
            return "yaml"
        if suffix == ".js":
            return "javascript"
        if suffix in {".ts", ".tsx"}:
            return "typescript"
        return "unknown"

    def parse_file(self, path: str | Path, *, trace: TraceLogger) -> ParsedFile | None:
        p = Path(path)
        language = self.route(p)
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            if language == "yaml":
                # YAML: parser is PyYAML (tree-sitter not required)
                obj = yaml.safe_load(source) if source.strip() else None
                return ParsedFile(path=p, language=language, source_text=source, yaml_obj=obj)

            if language in self._parsers:
                parser = self._parsers[language]
                tree = parser.parse(bytes(source, "utf-8"))
                return ParsedFile(path=p, language=language, source_text=source, tree=tree)

            return ParsedFile(path=p, language="unknown", source_text=source)
        except Exception as e:
            trace.log_error(stage="parse_file", path=p, error=e, extra={"language": language})
            return None

