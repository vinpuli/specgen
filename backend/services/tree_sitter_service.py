"""
Tree-sitter service for multi-language source parsing.

This service provides:
- Optional Tree-sitter runtime integration
- Multi-language parser resolution
- Parse metadata extraction for downstream analysis
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class TreeSitterServiceError(Exception):
    """Base exception for tree-sitter integration errors."""


class TreeSitterUnavailableError(TreeSitterServiceError):
    """Raised when tree-sitter runtime is unavailable."""


class TreeSitterUnsupportedLanguageError(TreeSitterServiceError):
    """Raised when the requested language is not supported."""


class TreeSitterService:
    """
    Wrapper for Tree-sitter parser loading and parsing.

    Supports multiple language loader backends and fails safely when
    tree-sitter dependencies are not installed.
    """

    _LANGUAGE_ALIASES: Dict[str, str] = {
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "tsx": "tsx",
        "jsx": "jsx",
        "java": "java",
        "go": "go",
        "csharp": "csharp",
        "c#": "csharp",
        "c_sharp": "csharp",
        "rust": "rust",
        "php": "php",
        "ruby": "ruby",
        "c": "c",
        "cpp": "cpp",
        "c++": "cpp",
    }
    _LOADER_LANGUAGE_CANDIDATES: Dict[str, List[str]] = {
        "csharp": ["csharp", "c_sharp"],
    }

    def __init__(self):
        self._parser_cls = self._load_parser_class()
        self._language_loader = self._load_language_loader()
        self._parser_cache: Dict[str, Any] = {}

    def is_available(self) -> bool:
        """Return True when both parser runtime and language loader are available."""
        return self._parser_cls is not None and self._language_loader is not None

    def parse_file(self, file_path: str, language: str) -> Dict[str, Any]:
        """Parse file content with Tree-sitter."""
        path = Path(file_path)
        if not path.exists():
            raise TreeSitterServiceError(f"File not found: {file_path}")
        content = path.read_text(encoding="utf-8", errors="ignore")
        return self.parse_content(content, language)

    def parse_content(
        self,
        content: str,
        language: str,
        max_serialized_nodes: int = 500,
        max_serialized_depth: int = 6,
    ) -> Dict[str, Any]:
        """Parse source content and return structural metadata."""
        if not self.is_available():
            raise TreeSitterUnavailableError(
                "Tree-sitter runtime is unavailable. Install 'tree-sitter' plus a language loader "
                "('tree-sitter-languages' or 'tree-sitter-language-pack')."
            )

        canonical_language = self._normalize_language(language)
        parser = self._get_parser(canonical_language)
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node
        node_count, max_depth = self._count_nodes_and_depth(root)
        serialized_limit = max(1, int(max_serialized_nodes))
        serialized_depth_limit = max(1, int(max_serialized_depth))
        serialized_budget = {"remaining": serialized_limit}
        ast_tree = self._serialize_node(
            root,
            depth=1,
            max_depth=serialized_depth_limit,
            budget=serialized_budget,
        )
        serialized_node_count = serialized_limit - serialized_budget["remaining"]

        return {
            "backend": "tree_sitter",
            "language": canonical_language,
            "root": root.type,
            "node_count": node_count,
            "depth": max_depth,
            "has_error": bool(getattr(root, "has_error", False)),
            "byte_range": [int(root.start_byte), int(root.end_byte)],
            "line_range": {
                "start": int(root.start_point[0]) + 1,
                "end": int(root.end_point[0]) + 1,
            },
            "ast": ast_tree,
            "serialized_node_count": serialized_node_count,
            "serialized_limit": serialized_limit,
            "serialized_depth_limit": serialized_depth_limit,
        }

    def _get_parser(self, language: str) -> Any:
        if language in self._parser_cache:
            return self._parser_cache[language]

        if self._parser_cls is None or self._language_loader is None:
            raise TreeSitterUnavailableError("Tree-sitter runtime not initialized")

        ts_language = self._load_ts_language(language)
        parser = self._create_parser(ts_language)
        self._parser_cache[language] = parser
        return parser

    def _create_parser(self, ts_language: Any) -> Any:
        parser_cls = self._parser_cls
        if parser_cls is None:
            raise TreeSitterUnavailableError("Tree-sitter parser class unavailable")

        # Compatibility with multiple py-tree-sitter APIs.
        try:
            parser = parser_cls()
            if hasattr(parser, "set_language"):
                parser.set_language(ts_language)
            else:
                setattr(parser, "language", ts_language)
            return parser
        except TypeError:
            return parser_cls(ts_language)
        except Exception as exc:
            raise TreeSitterServiceError(f"Failed to initialize parser: {exc}") from exc

    def _normalize_language(self, language: str) -> str:
        normalized = (language or "").strip().lower()
        if normalized not in self._LANGUAGE_ALIASES:
            raise TreeSitterUnsupportedLanguageError(f"Unsupported Tree-sitter language: {language}")
        return self._LANGUAGE_ALIASES[normalized]

    def _load_ts_language(self, language: str) -> Any:
        if self._language_loader is None:
            raise TreeSitterUnavailableError("Tree-sitter language loader unavailable")

        candidates = self._LOADER_LANGUAGE_CANDIDATES.get(language, [language])
        errors: List[str] = []
        for candidate in candidates:
            try:
                return self._language_loader(candidate)
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")

        raise TreeSitterUnsupportedLanguageError(
            "Failed to load Tree-sitter language "
            f"'{language}'. Tried: {', '.join(candidates)}. Errors: {' | '.join(errors)}"
        )

    def _load_parser_class(self) -> Optional[type]:
        try:
            from tree_sitter import Parser

            return Parser
        except Exception:
            logger.info("tree_sitter.Parser not available")
            return None

    def _load_language_loader(self) -> Optional[Callable[[str], Any]]:
        try:
            from tree_sitter_languages import get_language

            return get_language
        except Exception:
            pass

        try:
            from tree_sitter_language_pack import get_language

            return get_language
        except Exception:
            logger.info("No Tree-sitter language loader available")
            return None

    def _count_nodes_and_depth(self, root_node: Any) -> tuple[int, int]:
        stack = [(root_node, 1)]
        count = 0
        max_depth = 0

        while stack:
            node, depth = stack.pop()
            count += 1
            if depth > max_depth:
                max_depth = depth
            for child in getattr(node, "children", []):
                stack.append((child, depth + 1))

        return count, max_depth

    def _serialize_node(
        self,
        node: Any,
        depth: int,
        max_depth: int,
        budget: Dict[str, int],
    ) -> Dict[str, Any]:
        if budget["remaining"] <= 0:
            return {"type": getattr(node, "type", "unknown"), "truncated": True}

        budget["remaining"] -= 1
        start_point = getattr(node, "start_point", (0, 0))
        end_point = getattr(node, "end_point", (0, 0))

        payload: Dict[str, Any] = {
            "type": getattr(node, "type", "unknown"),
            "named": bool(getattr(node, "is_named", True)),
            "byte_range": [int(getattr(node, "start_byte", 0)), int(getattr(node, "end_byte", 0))],
            "line_range": {
                "start": int(start_point[0]) + 1,
                "end": int(end_point[0]) + 1,
            },
            "column_range": {
                "start": int(start_point[1]) + 1,
                "end": int(end_point[1]) + 1,
            },
        }

        children = list(getattr(node, "named_children", []) or getattr(node, "children", []))
        payload["child_count"] = len(children)
        if not children:
            return payload

        if depth >= max_depth:
            payload["children_truncated"] = True
            return payload

        serialized_children = []
        for child in children:
            if budget["remaining"] <= 0:
                break
            serialized_children.append(
                self._serialize_node(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                    budget=budget,
                )
            )

        if serialized_children:
            payload["children"] = serialized_children
        payload["children_truncated"] = len(serialized_children) < len(children)
        return payload
