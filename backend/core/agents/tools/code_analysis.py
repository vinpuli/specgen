"""
Code Analysis ToolNode for LangGraph agents.

Provides LangChain tools for code analysis using Tree-sitter:
- Language detection
- AST parsing and extraction
- Type-aware analysis for statically typed languages
- Syntax and heuristic analysis for dynamic languages
- Architecture inference for brownfield codebases
- Component inventory generation with classifications
- C4 model generation (Context, Container, Component)
- Mermaid diagram rendering for architecture visualizations
- User-guided architecture annotation interface
- Function/class extraction
- Import analysis
- Code metrics (LOC, complexity)
- Dependency graph construction
- File impact classification (create, modify, delete)
"""

import asyncio
from copy import deepcopy
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type
from uuid import UUID

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.services.tree_sitter_service import (
    TreeSitterService,
    TreeSitterServiceError,
)


class DetectLanguageInput(BaseModel):
    """Input schema for DetectLanguageTool."""

    file_path: str = Field(..., description="Path to file for language detection")


class DetectLanguageTool(BaseTool):
    """Tool for detecting programming language of a file."""

    name: str = "detect_language"
    description: str = """
    Detect the programming language of a file.
    Uses extension, shebang, and lightweight content heuristics.
    Returns the detected language and confidence.
    """
    args_schema: Type[BaseModel] = DetectLanguageInput

    # Language mapping based on extensions
    LANGUAGE_MAP: Dict[str, str] = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".md": "markdown",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
    }
    TARGET_LANGUAGES: Set[str] = {
        "typescript",
        "javascript",
        "python",
        "java",
        "go",
        "csharp",
        "rust",
        "php",
        "ruby",
    }
    _CONTENT_PATTERNS: Dict[str, List[str]] = {
        "typescript": [
            r"\binterface\s+\w+",
            r"\btype\s+\w+\s*=",
            r"\bimport\s+type\b",
            r"\bas\s+const\b",
            r":\s*(string|number|boolean|any|unknown|never|void)\b",
        ],
        "javascript": [
            r"\bmodule\.exports\b",
            r"\brequire\s*\(",
            r"\bexport\s+default\b",
            r"\bconsole\.log\s*\(",
        ],
        "python": [
            r"^\s*def\s+\w+\s*\(",
            r"^\s*class\s+\w+",
            r"^\s*from\s+\w+.*\s+import\s+",
            r"^\s*import\s+\w+",
            r"if\s+__name__\s*==\s*[\"']__main__[\"']",
        ],
        "java": [
            r"\bpackage\s+[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*\s*;",
            r"\bimport\s+java\.",
            r"\bpublic\s+class\s+\w+",
            r"\bSystem\.out\.",
        ],
        "go": [
            r"^\s*package\s+\w+",
            r"^\s*import\s+\(",
            r"^\s*func\s+\w+\s*\(",
            r"\b:=\s*",
        ],
        "csharp": [
            r"\busing\s+System\b",
            r"\bnamespace\s+\w+",
            r"\bpublic\s+class\s+\w+",
            r"\bConsole\.WriteLine\s*\(",
            r"\basync\s+Task\b",
        ],
        "rust": [
            r"\bfn\s+\w+\s*\(",
            r"\blet\s+mut\s+",
            r"\buse\s+std::",
            r"\bpub\s+struct\s+\w+",
            r"\bimpl\s+\w+",
        ],
        "php": [
            r"<\?php",
            r"\$\w+\s*->",
            r"\bnamespace\s+[A-Za-z_\\][A-Za-z0-9_\\]*\s*;",
            r"\bfunction\s+\w+\s*\(",
        ],
        "ruby": [
            r"^\s*def\s+\w+[!?=]?",
            r"^\s*class\s+\w+",
            r"^\s*module\s+\w+",
            r"^\s*require\s+[\"']",
            r"^\s*puts\s+",
        ],
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._tree_sitter = TreeSitterService()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str) -> Dict[str, Any]:
        """Execute language detection."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            ext = Path(resolved_path).suffix.lower()
            language = self.LANGUAGE_MAP.get(ext, "unknown")
            detected_by = "extension"
            confidence = 0.98 if language != "unknown" else 0.0

            sample = self._read_sample(resolved_path)

            if language == "unknown":
                shebang_language = self._detect_from_shebang(sample)
                if shebang_language:
                    language = shebang_language
                    detected_by = "shebang"
                    confidence = 0.9
                else:
                    content_language, content_confidence = self._detect_from_content(sample)
                    language = content_language
                    detected_by = "content" if content_language != "unknown" else "unknown"
                    confidence = content_confidence

            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "extension": ext,
                "detected_by": detected_by,
                "confidence": round(confidence, 2),
                "is_target_language": language in self.TARGET_LANGUAGES,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _read_sample(self, path: str, limit: int = 32768) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(limit)
        except Exception:
            return ""

    def _detect_from_shebang(self, content: str) -> Optional[str]:
        first_line = content.splitlines()[0] if content else ""
        if not first_line.startswith("#!"):
            return None

        shebang = first_line.lower()
        if "python" in shebang:
            return "python"
        if "node" in shebang or "deno" in shebang or "bun" in shebang:
            return "javascript"
        if "php" in shebang:
            return "php"
        if "ruby" in shebang:
            return "ruby"
        return None

    def _detect_from_content(self, content: str) -> tuple[str, float]:
        if not content.strip():
            return "unknown", 0.0

        scores: Dict[str, int] = {}
        for language, patterns in self._CONTENT_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, content, flags=re.MULTILINE):
                    score += 1
            if score > 0:
                scores[language] = score

        if not scores:
            return "unknown", 0.0

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_language, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        if top_score <= 1 or top_score == second_score:
            return "unknown", 0.35

        confidence = min(0.9, 0.45 + (top_score * 0.12))
        return top_language, confidence

    async def _arun(self, file_path: str) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path)


class ParseASTInput(BaseModel):
    """Input schema for ParseASTTool."""

    file_path: str = Field(..., description="Path to file to parse")
    language: Optional[str] = Field(
        default=None, description="Force language (auto-detect if not provided)"
    )


class ParseASTTool(BaseTool):
    """Tool for parsing code into AST (Abstract Syntax Tree)."""

    name: str = "parse_ast"
    description: str = """
    Parse source code into an Abstract Syntax Tree.
    Returns structured representation of code.
    Use language parameter to force specific parser.
    """
    args_schema: Type[BaseModel] = ParseASTInput
    SUPPORTED_LANGUAGES: Set[str] = {
        "typescript",
        "javascript",
        "python",
        "java",
        "go",
        "csharp",
        "rust",
        "php",
        "ruby",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._tree_sitter = TreeSitterService()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Execute AST parsing."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            # Read file content
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Detect language if not provided
            if not language:
                detector = DetectLanguageTool(base_path=self._base_path)
                lang_result = detector._run(file_path)
                if lang_result["status"] == "success":
                    language = lang_result["language"]

            language = (language or "unknown").strip().lower()
            ast_result: Dict[str, Any]
            parser_backend = "simple"
            parse_warning: Optional[str] = None

            # Use Tree-sitter when available; fallback preserves backward compatibility.
            if language in self.SUPPORTED_LANGUAGES and self._tree_sitter.is_available():
                try:
                    ast_result = self._tree_sitter.parse_content(content, language)
                    parser_backend = "tree_sitter"
                except TreeSitterServiceError as parse_error:
                    parse_warning = str(parse_error)
                    ast_result = self._simple_parse(content, language)
            else:
                if language not in self.SUPPORTED_LANGUAGES and language != "unknown":
                    parse_warning = f"Language '{language}' is not in AST supported set"
                elif not self._tree_sitter.is_available() and language in self.SUPPORTED_LANGUAGES:
                    parse_warning = (
                        "Tree-sitter runtime unavailable; used simplified parser fallback"
                    )
                ast_result = self._simple_parse(content, language)

            response = {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "is_supported_language": language in self.SUPPORTED_LANGUAGES,
                "parser_backend": parser_backend,
                "ast": ast_result,
                "node_count": ast_result.get("node_count", 0),
            }
            if parse_warning:
                response["parse_warning"] = parse_warning
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _simple_parse(self, content: str, language: str) -> Dict[str, Any]:
        """Simple AST parsing (placeholder for tree-sitter)."""
        lines = content.split("\n")
        return {
            "root": "module",
            "language": language,
            "node_count": len(lines),
            "line_count": len(lines),
            "content_length": len(content),
            "functions": [],
            "classes": [],
            "imports": [],
        }

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path, language)


class ExtractFunctionsInput(BaseModel):
    """Input schema for ExtractFunctionsTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language"
    )


class ExtractFunctionsTool(BaseTool):
    """Tool for extracting function definitions from source code."""

    name: str = "extract_functions"
    description: str = """
    Extract all function definitions from source code.
    Returns function names, signatures, and line numbers.
    """
    args_schema: Type[BaseModel] = ExtractFunctionsInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Execute function extraction."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Detect language
            if not language:
                detector = DetectLanguageTool(base_path=self._base_path)
                lang_result = detector._run(file_path)
                if lang_result["status"] == "success":
                    language = lang_result["language"]

            # Extract functions (simplified)
            functions = self._extract_functions_by_language(content, language)

            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "functions": functions,
                "count": len(functions),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _extract_functions_by_language(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        """Extract functions based on language patterns."""
        functions = []
        lines = content.split("\n")

        # Common function patterns by language
        patterns = {
            "python": r"^\s*def\s+(\w+)\s*\(([^)]*)\)\s*:",
            "javascript": r"^\s*(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{",
            "typescript": r"^\s*(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*[{:]",
            "java": r"^\s*(?:public|private|protected|static|\s)*\s*(?:void|[\w<>\[\]]+)\s+(\w+)\s*\([^)]*\)",
            "go": r"^\s*func\s+(?:\([^)]+\)\s*)?(\w+)\s*\([^)]*\)",
            "rust": r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(",
        }

        pattern = patterns.get(language, patterns["python"])

        for i, line in enumerate(lines):
            import re
            match = re.match(pattern, line)
            if match:
                functions.append(
                    {
                        "name": match.group(1),
                        "line_number": i + 1,
                        "line_content": line.strip(),
                        "signature": match.group(0) if match.groups() else line.strip(),
                    }
                )

        return functions

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path, language)


class ExtractClassesInput(BaseModel):
    """Input schema for ExtractClassesTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language"
    )


class ExtractClassesTool(BaseTool):
    """Tool for extracting class definitions from source code."""

    name: str = "extract_classes"
    description: str = """
    Extract all class definitions from source code.
    Returns class names, inheritance, and line numbers.
    """
    args_schema: Type[BaseModel] = ExtractClassesInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Execute class extraction."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Detect language
            if not language:
                detector = DetectLanguageTool(base_path=self._base_path)
                lang_result = detector._run(file_path)
                if lang_result["status"] == "success":
                    language = lang_result["language"]

            # Extract classes (simplified)
            classes = self._extract_classes_by_language(content, language)

            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "classes": classes,
                "count": len(classes),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _extract_classes_by_language(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        """Extract classes based on language patterns."""
        classes = []
        lines = content.split("\n")

        # Class patterns by language
        patterns = {
            "python": r"^\s*class\s+(\w+)(?:\s*\(\s*([\w,\s]+)\s*\))?\s*:",
            "javascript": r"^\s*class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{",
            "typescript": r"^\s*class\s+(\w+)(?:\s+extends\s+(\w+))?\s*",
            "java": r"^\s*(?:public|private|protected|abstract|static|\s)*\s*class\s+(\w+)",
            "go": r"^\s*type\s+(\w+)\s+(?:struct|interface)",
            "rust": r"^\s*(?:pub\s+)?struct\s+(\w+)",
            "cpp": r"^\s*(?:class|struct)\s+(\w+)",
        }

        pattern = patterns.get(language, patterns["python"])

        for i, line in enumerate(lines):
            import re
            match = re.match(pattern, line)
            if match:
                class_info = {
                    "name": match.group(1),
                    "line_number": i + 1,
                    "line_content": line.strip(),
                }
                if match.group(2):
                    class_info["extends"] = match.group(2).strip()
                classes.append(class_info)

        return classes

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path, language)


class ExtractImportsInput(BaseModel):
    """Input schema for ExtractImportsTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language"
    )


class ExtractImportsTool(BaseTool):
    """Tool for extracting import/require statements from source code."""

    name: str = "extract_imports"
    description: str = """
    Extract all import statements from source code.
    Returns module names, paths, and types.
    """
    args_schema: Type[BaseModel] = ExtractImportsInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Execute import extraction."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Detect language
            if not language:
                detector = DetectLanguageTool(base_path=self._base_path)
                lang_result = detector._run(file_path)
                if lang_result["status"] == "success":
                    language = lang_result["language"]

            # Extract imports
            imports = self._extract_imports_by_language(content, language)

            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "imports": imports,
                "count": len(imports),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _extract_imports_by_language(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        """Extract imports based on language patterns."""
        imports: List[Dict[str, Any]] = []
        lines = content.split("\n")
        seen: Set[tuple[str, str, int]] = set()

        def add_import(module: str, import_type: str, line_number: int, line_content: str) -> None:
            normalized_module = (module or "").strip()
            if not normalized_module:
                return
            key = (normalized_module, import_type, line_number)
            if key in seen:
                return
            seen.add(key)
            imports.append(
                {
                    "module": normalized_module,
                    "type": import_type,
                    "line_number": int(line_number),
                    "line_content": line_content.strip(),
                }
            )

        if language == "python":
            for i, line in enumerate(lines):
                stripped = line.strip()
                from_match = re.match(r"^from\s+([.\w]+)\s+import\s+(.+)$", stripped)
                if from_match:
                    base_module = from_match.group(1)
                    imported_names = [
                        token.strip().split(" as ")[0].strip()
                        for token in from_match.group(2).split(",")
                    ]
                    add_import(base_module, "from", i + 1, line)
                    for imported_name in imported_names:
                        if imported_name and imported_name not in {"*", ""} and re.match(r"^[A-Za-z_]\w*$", imported_name):
                            add_import(f"{base_module}.{imported_name}", "from-member", i + 1, line)
                    continue
                import_match = re.match(r"^import\s+(.+)$", stripped)
                if import_match:
                    modules = [m.strip() for m in import_match.group(1).split(",")]
                    for module in modules:
                        base_module = module.split(" as ")[0].strip()
                        add_import(base_module, "import", i + 1, line)

        elif language in {"javascript", "typescript"}:
            for i, line in enumerate(lines):
                stripped = line.strip()
                from_match = re.match(
                    r"^import\s+(?:type\s+)?(?:[\w*\s{},$]+)\s+from\s+['\"]([^'\"]+)['\"]",
                    stripped,
                )
                if from_match:
                    add_import(from_match.group(1), "import", i + 1, line)
                side_effect_match = re.match(r"^import\s+['\"]([^'\"]+)['\"]", stripped)
                if side_effect_match:
                    add_import(side_effect_match.group(1), "import", i + 1, line)
                require_match = re.search(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped)
                if require_match:
                    add_import(require_match.group(1), "require", i + 1, line)
                dynamic_import_match = re.search(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped)
                if dynamic_import_match:
                    add_import(dynamic_import_match.group(1), "dynamic-import", i + 1, line)

        elif language == "java":
            for i, line in enumerate(lines):
                stripped = line.strip()
                static_match = re.match(r"^import\s+static\s+([\w.]+);", stripped)
                if static_match:
                    add_import(static_match.group(1), "static-import", i + 1, line)
                    continue
                import_match = re.match(r"^import\s+([\w.]+);", stripped)
                if import_match:
                    add_import(import_match.group(1), "import", i + 1, line)

        elif language == "go":
            for i, line in enumerate(lines):
                single_match = re.match(r'^\s*import\s+"([^"]+)"', line)
                if single_match:
                    add_import(single_match.group(1), "import", i + 1, line)
            for block_match in re.finditer(r"(?ms)^\s*import\s*\((.*?)^\s*\)", content):
                block_start_line = content[: block_match.start()].count("\n") + 1
                block_body = block_match.group(1)
                for offset, block_line in enumerate(block_body.splitlines(), start=1):
                    module_match = re.search(r'"([^"]+)"', block_line)
                    if module_match:
                        add_import(
                            module_match.group(1),
                            "import",
                            block_start_line + offset,
                            block_line,
                        )

        elif language == "csharp":
            for i, line in enumerate(lines):
                using_match = re.match(r"^\s*using\s+([A-Za-z_][\w.]*)\s*;", line)
                if using_match:
                    add_import(using_match.group(1), "using", i + 1, line)

        elif language == "rust":
            for i, line in enumerate(lines):
                use_match = re.match(r"^\s*use\s+([^;]+);", line)
                if use_match:
                    add_import(use_match.group(1), "use", i + 1, line)

        elif language == "php":
            for i, line in enumerate(lines):
                use_match = re.match(r"^\s*use\s+([A-Za-z_\\][A-Za-z0-9_\\]*)\s*;", line)
                if use_match:
                    add_import(use_match.group(1), "use", i + 1, line)
                include_match = re.search(
                    r"\b(include|include_once|require|require_once)\s*\(?\s*['\"]([^'\"]+)['\"]\s*\)?",
                    line,
                )
                if include_match:
                    add_import(include_match.group(2), include_match.group(1), i + 1, line)

        elif language == "ruby":
            for i, line in enumerate(lines):
                require_relative_match = re.match(r"^\s*require_relative\s+['\"]([^'\"]+)['\"]", line)
                if require_relative_match:
                    add_import(require_relative_match.group(1), "require_relative", i + 1, line)
                    continue
                require_match = re.match(r"^\s*require\s+['\"]([^'\"]+)['\"]", line)
                if require_match:
                    add_import(require_match.group(1), "require", i + 1, line)

        return imports

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path, language)


class TypeAwareAnalysisInput(BaseModel):
    """Input schema for TypeAwareAnalysisTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language (auto-detect if omitted)"
    )


class TypeAwareAnalysisTool(BaseTool):
    """Tool for type-aware analysis of statically typed languages."""

    name: str = "type_aware_analysis"
    description: str = """
    Perform type-aware analysis for statically typed languages.
    Extracts type definitions, typed symbols, signatures, generics, and casts.
    """
    args_schema: Type[BaseModel] = TypeAwareAnalysisInput
    STATIC_TYPED_LANGUAGES: Set[str] = {"typescript", "java", "go", "csharp"}

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._detector = DetectLanguageTool(base_path=self._base_path)
        self._parser = ParseASTTool(base_path=self._base_path)

    def _resolve_path(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        try:
            resolved_path = self._resolve_path(file_path)
            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            if not language:
                lang_result = self._detector._run(file_path)
                if lang_result.get("status") == "success":
                    language = lang_result.get("language")

            language = (language or "unknown").strip().lower()
            with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if language not in self.STATIC_TYPED_LANGUAGES:
                return {
                    "status": "success",
                    "file_path": file_path,
                    "language": language,
                    "is_statically_typed_language": False,
                    "type_summary": {
                        "type_definition_count": 0,
                        "typed_symbol_count": 0,
                        "function_signature_count": 0,
                        "generic_usage_count": 0,
                        "cast_count": 0,
                        "inferred_symbol_count": 0,
                        "unique_type_count": 0,
                        "explicit_type_ratio": 0.0,
                    },
                    "warning": f"Language '{language}' is not supported for type-aware analysis",
                }

            parse_result = self._parser._run(file_path=file_path, language=language)
            parser_backend = parse_result.get("parser_backend", "unknown")
            parse_warning = parse_result.get("parse_warning")

            if language == "typescript":
                analysis = self._analyze_typescript(content)
            elif language == "java":
                analysis = self._analyze_java(content)
            elif language == "go":
                analysis = self._analyze_go(content)
            else:
                analysis = self._analyze_csharp(content)

            unique_types = sorted({t for t in analysis["type_references"] if t})
            explicit_count = len(analysis["typed_symbols"])
            inferred_count = len(analysis["inferred_symbols"])
            explicit_ratio = (
                round(explicit_count / (explicit_count + inferred_count), 3)
                if (explicit_count + inferred_count) > 0
                else 1.0
            )

            response = {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "is_statically_typed_language": True,
                "analysis_backend": "heuristic",
                "parser_backend": parser_backend,
                "type_definitions": analysis["type_definitions"],
                "typed_symbols": analysis["typed_symbols"],
                "function_signatures": analysis["function_signatures"],
                "generic_usages": analysis["generic_usages"],
                "casts": analysis["casts"],
                "inferred_symbols": analysis["inferred_symbols"],
                "type_references": unique_types,
                "type_summary": {
                    "type_definition_count": len(analysis["type_definitions"]),
                    "typed_symbol_count": explicit_count,
                    "function_signature_count": len(analysis["function_signatures"]),
                    "generic_usage_count": len(analysis["generic_usages"]),
                    "cast_count": len(analysis["casts"]),
                    "inferred_symbol_count": inferred_count,
                    "unique_type_count": len(unique_types),
                    "explicit_type_ratio": explicit_ratio,
                },
            }
            if parse_warning:
                response["parse_warning"] = parse_warning
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _empty_analysis(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "type_definitions": [],
            "typed_symbols": [],
            "function_signatures": [],
            "generic_usages": [],
            "casts": [],
            "inferred_symbols": [],
            "type_references": [],
        }

    def _add_type_reference(self, analysis: Dict[str, Any], raw_type: Optional[str]) -> None:
        normalized = self._normalize_type(raw_type)
        if normalized:
            analysis["type_references"].append(normalized)

    def _normalize_type(self, raw_type: Optional[str]) -> str:
        if not raw_type:
            return ""
        normalized = raw_type.strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.rstrip("{").rstrip(";").strip()
        return normalized

    def _extract_generics(self, line: str) -> List[str]:
        matches = re.findall(r"\b[A-Za-z_]\w*<[^>\n]+>", line)
        return [m.strip() for m in matches]

    def _extract_params(self, params: str, language: str) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        if not params.strip():
            return results
        parts = [part.strip() for part in params.split(",") if part.strip()]
        for part in parts:
            if language in {"typescript", "csharp"}:
                match = re.match(r"^(\w+)\??\s*:\s*(.+)$", part)
                if match:
                    results.append({"name": match.group(1), "type": match.group(2).strip()})
                    continue
            if language == "java":
                match = re.match(r"^(?:final\s+)?(.+?)\s+(\w+)$", part)
                if match:
                    results.append({"name": match.group(2), "type": match.group(1).strip()})
                    continue
            if language == "go":
                match = re.match(r"^(\w+)\s+(.+)$", part)
                if match:
                    results.append({"name": match.group(1), "type": match.group(2).strip()})
                    continue
            results.append({"name": part, "type": ""})
        return results

    def _analyze_typescript(self, content: str) -> Dict[str, Any]:
        analysis = self._empty_analysis()
        lines = content.split("\n")

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()

            type_def_match = re.match(
                r"^(?:export\s+)?(interface|type|class|enum)\s+(\w+)(?:<([^>]+)>)?",
                stripped,
            )
            if type_def_match:
                generics = type_def_match.group(3).strip() if type_def_match.group(3) else None
                analysis["type_definitions"].append(
                    {
                        "kind": type_def_match.group(1),
                        "name": type_def_match.group(2),
                        "line_number": line_number,
                        "generics": generics,
                    }
                )
                self._add_type_reference(analysis, type_def_match.group(2))

            function_match = re.match(
                r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*([^ {=>]+))?",
                stripped,
            )
            if function_match:
                params = self._extract_params(function_match.group(2), "typescript")
                return_type = (function_match.group(3) or "void").strip()
                analysis["function_signatures"].append(
                    {
                        "name": function_match.group(1),
                        "line_number": line_number,
                        "parameters": params,
                        "return_type": return_type,
                    }
                )
                self._add_type_reference(analysis, return_type)
                for param in params:
                    if param.get("type"):
                        analysis["typed_symbols"].append(
                            {
                                "name": param.get("name"),
                                "type": param.get("type"),
                                "kind": "parameter",
                                "line_number": line_number,
                            }
                        )
                        self._add_type_reference(analysis, param.get("type"))

            variable_match = re.match(
                r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*:\s*([^=;]+)",
                stripped,
            )
            if variable_match:
                var_type = variable_match.group(2).strip()
                analysis["typed_symbols"].append(
                    {
                        "name": variable_match.group(1),
                        "type": var_type,
                        "kind": "variable",
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, var_type)
            else:
                inferred_match = re.match(r"^(?:const|let|var)\s+(\w+)\s*=\s*", stripped)
                if inferred_match:
                    analysis["inferred_symbols"].append(
                        {
                            "name": inferred_match.group(1),
                            "kind": "variable",
                            "line_number": line_number,
                        }
                    )

            for cast_type in re.findall(r"\bas\s+([A-Za-z_][\w<>\[\]\.|,&? ]*)", stripped):
                analysis["casts"].append({"type": cast_type.strip(), "line_number": line_number})
                self._add_type_reference(analysis, cast_type)

            for generic in self._extract_generics(stripped):
                analysis["generic_usages"].append({"type": generic, "line_number": line_number})
                self._add_type_reference(analysis, generic)

        return analysis

    def _analyze_java(self, content: str) -> Dict[str, Any]:
        analysis = self._empty_analysis()
        lines = content.split("\n")

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()

            type_def_match = re.match(
                r"^(?:public|protected|private|abstract|final|static|\s)*(class|interface|enum|record)\s+(\w+)(?:<([^>]+)>)?",
                stripped,
            )
            if type_def_match:
                analysis["type_definitions"].append(
                    {
                        "kind": type_def_match.group(1),
                        "name": type_def_match.group(2),
                        "line_number": line_number,
                        "generics": type_def_match.group(3).strip() if type_def_match.group(3) else None,
                    }
                )
                self._add_type_reference(analysis, type_def_match.group(2))

            method_match = re.match(
                r"^(?:public|protected|private|static|final|synchronized|abstract|native|default|\s)+([\w<>\[\], ?]+)\s+(\w+)\s*\(([^)]*)\)",
                stripped,
            )
            if method_match and method_match.group(2) not in {"if", "for", "while", "switch", "catch"}:
                return_type = method_match.group(1).strip()
                params = self._extract_params(method_match.group(3), "java")
                analysis["function_signatures"].append(
                    {
                        "name": method_match.group(2),
                        "line_number": line_number,
                        "parameters": params,
                        "return_type": return_type,
                    }
                )
                self._add_type_reference(analysis, return_type)
                for param in params:
                    if param.get("type"):
                        analysis["typed_symbols"].append(
                            {
                                "name": param.get("name"),
                                "type": param.get("type"),
                                "kind": "parameter",
                                "line_number": line_number,
                            }
                        )
                        self._add_type_reference(analysis, param.get("type"))

            variable_match = re.match(
                r"^(?:final\s+)?([\w<>\[\], ?]+)\s+(\w+)\s*(?:=|;)",
                stripped,
            )
            if variable_match and variable_match.group(2) not in {"return", "throw", "new"}:
                var_type = variable_match.group(1).strip()
                analysis["typed_symbols"].append(
                    {
                        "name": variable_match.group(2),
                        "type": var_type,
                        "kind": "variable",
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, var_type)

            for cast_type in re.findall(r"\(\s*([A-Za-z_][\w<>\[\].? ,]+)\s*\)\s*[A-Za-z_(]", stripped):
                analysis["casts"].append({"type": cast_type.strip(), "line_number": line_number})
                self._add_type_reference(analysis, cast_type)

            for generic in self._extract_generics(stripped):
                analysis["generic_usages"].append({"type": generic, "line_number": line_number})
                self._add_type_reference(analysis, generic)

        return analysis

    def _analyze_go(self, content: str) -> Dict[str, Any]:
        analysis = self._empty_analysis()
        lines = content.split("\n")
        in_struct = False

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()

            struct_start = re.match(r"^type\s+(\w+)\s+struct\s*\{", stripped)
            if struct_start:
                in_struct = True
                analysis["type_definitions"].append(
                    {
                        "kind": "struct",
                        "name": struct_start.group(1),
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, struct_start.group(1))
                continue

            interface_start = re.match(r"^type\s+(\w+)\s+interface\s*\{", stripped)
            if interface_start:
                analysis["type_definitions"].append(
                    {
                        "kind": "interface",
                        "name": interface_start.group(1),
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, interface_start.group(1))
                continue

            alias_match = re.match(r"^type\s+(\w+)\s*=\s*([^\s{]+)", stripped)
            if alias_match:
                analysis["type_definitions"].append(
                    {
                        "kind": "alias",
                        "name": alias_match.group(1),
                        "line_number": line_number,
                        "aliased_type": alias_match.group(2),
                    }
                )
                self._add_type_reference(analysis, alias_match.group(2))

            if stripped == "}":
                in_struct = False

            if in_struct:
                field_match = re.match(r"^(\w+)\s+([*\w\[\].]+)", stripped)
                if field_match:
                    field_type = field_match.group(2).strip()
                    analysis["typed_symbols"].append(
                        {
                            "name": field_match.group(1),
                            "type": field_type,
                            "kind": "struct-field",
                            "line_number": line_number,
                        }
                    )
                    self._add_type_reference(analysis, field_type)

            function_match = re.match(
                r"^func\s*(?:\([^)]+\)\s*)?(\w+)\s*\(([^)]*)\)\s*([^{]*)",
                stripped,
            )
            if function_match:
                params = self._extract_params(function_match.group(2), "go")
                return_type = function_match.group(3).strip()
                analysis["function_signatures"].append(
                    {
                        "name": function_match.group(1),
                        "line_number": line_number,
                        "parameters": params,
                        "return_type": return_type,
                    }
                )
                self._add_type_reference(analysis, return_type)
                for param in params:
                    if param.get("type"):
                        analysis["typed_symbols"].append(
                            {
                                "name": param.get("name"),
                                "type": param.get("type"),
                                "kind": "parameter",
                                "line_number": line_number,
                            }
                        )
                        self._add_type_reference(analysis, param.get("type"))

            variable_match = re.match(r"^var\s+(\w+)\s+([^\s=;]+)", stripped)
            if variable_match:
                analysis["typed_symbols"].append(
                    {
                        "name": variable_match.group(1),
                        "type": variable_match.group(2),
                        "kind": "variable",
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, variable_match.group(2))

            inferred_match = re.match(r"^(\w+(?:\s*,\s*\w+)*)\s*:=", stripped)
            if inferred_match:
                for symbol in [p.strip() for p in inferred_match.group(1).split(",") if p.strip()]:
                    analysis["inferred_symbols"].append(
                        {
                            "name": symbol,
                            "kind": "variable",
                            "line_number": line_number,
                        }
                    )

        return analysis

    def _analyze_csharp(self, content: str) -> Dict[str, Any]:
        analysis = self._empty_analysis()
        lines = content.split("\n")

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()

            type_def_match = re.match(
                r"^(?:public|private|protected|internal|abstract|sealed|partial|static|\s)*(class|interface|struct|record|enum)\s+(\w+)(?:<([^>]+)>)?",
                stripped,
            )
            if type_def_match:
                analysis["type_definitions"].append(
                    {
                        "kind": type_def_match.group(1),
                        "name": type_def_match.group(2),
                        "line_number": line_number,
                        "generics": type_def_match.group(3).strip() if type_def_match.group(3) else None,
                    }
                )
                self._add_type_reference(analysis, type_def_match.group(2))

            method_match = re.match(
                r"^(?:public|private|protected|internal|static|virtual|override|abstract|async|sealed|partial|extern|new|\s)+([\w<>\[\],?.]+)\s+(\w+)\s*\(([^)]*)\)",
                stripped,
            )
            if method_match and method_match.group(2) not in {"if", "for", "while", "switch", "catch"}:
                return_type = method_match.group(1).strip()
                params = self._extract_params(method_match.group(3), "csharp")
                analysis["function_signatures"].append(
                    {
                        "name": method_match.group(2),
                        "line_number": line_number,
                        "parameters": params,
                        "return_type": return_type,
                    }
                )
                self._add_type_reference(analysis, return_type)

            property_match = re.match(
                r"^(?:public|private|protected|internal|static|virtual|override|abstract|\s)+([\w<>\[\],?.]+)\s+(\w+)\s*\{\s*get;",
                stripped,
            )
            if property_match:
                prop_type = property_match.group(1).strip()
                analysis["typed_symbols"].append(
                    {
                        "name": property_match.group(2),
                        "type": prop_type,
                        "kind": "property",
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, prop_type)

            explicit_var_match = re.match(r"^([\w<>\[\],?.]+)\s+(\w+)\s*(?:=|;)", stripped)
            if explicit_var_match and explicit_var_match.group(1) not in {
                "return",
                "throw",
                "new",
                "if",
                "for",
                "while",
                "switch",
                "catch",
            }:
                var_type = explicit_var_match.group(1).strip()
                analysis["typed_symbols"].append(
                    {
                        "name": explicit_var_match.group(2),
                        "type": var_type,
                        "kind": "variable",
                        "line_number": line_number,
                    }
                )
                self._add_type_reference(analysis, var_type)

            inferred_var_match = re.match(r"^var\s+(\w+)\s*=", stripped)
            if inferred_var_match:
                analysis["inferred_symbols"].append(
                    {
                        "name": inferred_var_match.group(1),
                        "kind": "variable",
                        "line_number": line_number,
                    }
                )

            for cast_type in re.findall(r"\(\s*([A-Za-z_][\w<>\[\],?. ]*)\s*\)\s*[A-Za-z_(]", stripped):
                analysis["casts"].append({"type": cast_type.strip(), "line_number": line_number})
                self._add_type_reference(analysis, cast_type)
            for cast_type in re.findall(r"\bas\s+([A-Za-z_][\w<>\[\],?. ]*)", stripped):
                analysis["casts"].append({"type": cast_type.strip(), "line_number": line_number})
                self._add_type_reference(analysis, cast_type)

            for generic in self._extract_generics(stripped):
                analysis["generic_usages"].append({"type": generic, "line_number": line_number})
                self._add_type_reference(analysis, generic)

        return analysis

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        return self._run(file_path, language)


class DynamicHeuristicAnalysisInput(BaseModel):
    """Input schema for DynamicHeuristicAnalysisTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language (auto-detect if omitted)"
    )


class DynamicHeuristicAnalysisTool(BaseTool):
    """Tool for syntax and heuristic analysis of dynamic languages."""

    name: str = "dynamic_heuristic_analysis"
    description: str = """
    Perform syntax and heuristic analysis for dynamic languages.
    Detects runtime/metaprogramming patterns and dynamic behavior risks.
    """
    args_schema: Type[BaseModel] = DynamicHeuristicAnalysisInput
    DYNAMIC_LANGUAGES: Set[str] = {"python", "javascript", "php", "ruby"}

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._detector = DetectLanguageTool(base_path=self._base_path)
        self._parser = ParseASTTool(base_path=self._base_path)
        self._imports = ExtractImportsTool(base_path=self._base_path)

    def _resolve_path(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        try:
            resolved_path = self._resolve_path(file_path)
            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            if not language:
                lang_result = self._detector._run(file_path)
                if lang_result.get("status") == "success":
                    language = lang_result.get("language")
            language = (language or "unknown").strip().lower()

            with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if language not in self.DYNAMIC_LANGUAGES:
                return {
                    "status": "success",
                    "file_path": file_path,
                    "language": language,
                    "is_dynamic_language": False,
                    "heuristic_summary": {
                        "dynamic_construct_count": 0,
                        "runtime_hook_count": 0,
                        "reflection_count": 0,
                        "dynamic_import_count": 0,
                        "serialization_risk_count": 0,
                        "metaprogramming_count": 0,
                        "risk_score": 0,
                    },
                    "warning": f"Language '{language}' is not supported for dynamic analysis",
                }

            parse_result = self._parser._run(file_path=file_path, language=language)
            parser_backend = parse_result.get("parser_backend", "unknown")
            parse_warning = parse_result.get("parse_warning")
            imports = self._imports._extract_imports_by_language(content, language)

            if language == "python":
                analysis = self._analyze_python(content)
            elif language == "javascript":
                analysis = self._analyze_javascript(content)
            elif language == "php":
                analysis = self._analyze_php(content)
            else:
                analysis = self._analyze_ruby(content)

            risk_score = self._calculate_risk_score(analysis)
            response = {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "is_dynamic_language": True,
                "analysis_backend": "heuristic",
                "parser_backend": parser_backend,
                "imports": imports,
                "syntax_summary": analysis["syntax_summary"],
                "dynamic_constructs": analysis["dynamic_constructs"],
                "runtime_hooks": analysis["runtime_hooks"],
                "reflection_usages": analysis["reflection_usages"],
                "dynamic_imports": analysis["dynamic_imports"],
                "serialization_risks": analysis["serialization_risks"],
                "metaprogramming_usages": analysis["metaprogramming_usages"],
                "dangerous_calls": analysis["dangerous_calls"],
                "heuristic_summary": {
                    "dynamic_construct_count": len(analysis["dynamic_constructs"]),
                    "runtime_hook_count": len(analysis["runtime_hooks"]),
                    "reflection_count": len(analysis["reflection_usages"]),
                    "dynamic_import_count": len(analysis["dynamic_imports"]),
                    "serialization_risk_count": len(analysis["serialization_risks"]),
                    "metaprogramming_count": len(analysis["metaprogramming_usages"]),
                    "risk_score": risk_score,
                },
            }
            if parse_warning:
                response["parse_warning"] = parse_warning
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _init_dynamic_result(self) -> Dict[str, Any]:
        return {
            "syntax_summary": {
                "function_count": 0,
                "class_count": 0,
                "conditional_count": 0,
                "loop_count": 0,
                "exception_handling_count": 0,
            },
            "dynamic_constructs": [],
            "runtime_hooks": [],
            "reflection_usages": [],
            "dynamic_imports": [],
            "serialization_risks": [],
            "metaprogramming_usages": [],
            "dangerous_calls": [],
        }

    def _record_event(
        self,
        bucket: List[Dict[str, Any]],
        line_number: int,
        pattern: str,
        line: str,
    ) -> None:
        bucket.append(
            {
                "line_number": line_number,
                "pattern": pattern,
                "line_content": line.strip(),
            }
        )

    def _analyze_python(self, content: str) -> Dict[str, Any]:
        result = self._init_dynamic_result()
        lines = content.split("\n")
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r"^\s*def\s+\w+\s*\(", stripped):
                result["syntax_summary"]["function_count"] += 1
            if re.match(r"^\s*class\s+\w+", stripped):
                result["syntax_summary"]["class_count"] += 1
            if re.match(r"^\s*(if|elif)\b", stripped):
                result["syntax_summary"]["conditional_count"] += 1
            if re.match(r"^\s*(for|while)\b", stripped):
                result["syntax_summary"]["loop_count"] += 1
            if re.match(r"^\s*except\b", stripped):
                result["syntax_summary"]["exception_handling_count"] += 1

            if re.search(r"\b(eval|exec|compile)\s*\(", stripped):
                self._record_event(result["dynamic_constructs"], idx, "eval/exec/compile", line)
                self._record_event(result["dangerous_calls"], idx, "eval/exec/compile", line)
            if re.search(r"\bgetattr\s*\(|\bsetattr\s*\(|\bhasattr\s*\(", stripped):
                self._record_event(result["reflection_usages"], idx, "getattr/setattr/hasattr", line)
            if re.search(r"\bimportlib\.", stripped):
                self._record_event(result["dynamic_imports"], idx, "importlib", line)
            if re.search(r"\b__import__\s*\(", stripped):
                self._record_event(result["dynamic_imports"], idx, "__import__", line)
            if re.search(r"\bpickle\.(load|loads)\s*\(", stripped):
                self._record_event(result["serialization_risks"], idx, "pickle load", line)
            if re.search(r"\b(yaml\.load)\s*\(", stripped):
                self._record_event(result["serialization_risks"], idx, "yaml.load", line)
            if re.search(r"\bsetattr\s*\(|\b__dict__\b|\bglobals\s*\(|\blocals\s*\(", stripped):
                self._record_event(result["metaprogramming_usages"], idx, "runtime object mutation", line)
            if re.search(r"\b__getattr__\b|\b__getattribute__\b|\b__setattr__\b", stripped):
                self._record_event(result["runtime_hooks"], idx, "dunder attribute hook", line)
        return result

    def _analyze_javascript(self, content: str) -> Dict[str, Any]:
        result = self._init_dynamic_result()
        lines = content.split("\n")
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.search(r"\bfunction\b|\=\>\s*\{?", stripped):
                result["syntax_summary"]["function_count"] += 1
            if re.search(r"\bclass\s+\w+", stripped):
                result["syntax_summary"]["class_count"] += 1
            if re.search(r"\bif\s*\(", stripped):
                result["syntax_summary"]["conditional_count"] += 1
            if re.search(r"\bfor\s*\(|\bwhile\s*\(", stripped):
                result["syntax_summary"]["loop_count"] += 1
            if re.search(r"\bcatch\s*\(", stripped):
                result["syntax_summary"]["exception_handling_count"] += 1

            if re.search(r"\beval\s*\(|\bFunction\s*\(", stripped):
                self._record_event(result["dynamic_constructs"], idx, "eval/Function", line)
                self._record_event(result["dangerous_calls"], idx, "eval/Function", line)
            if re.search(r"\brequire\s*\(\s*[a-zA-Z_$]", stripped):
                self._record_event(result["dynamic_imports"], idx, "dynamic require", line)
            if re.search(r"\bimport\s*\(", stripped):
                self._record_event(result["dynamic_imports"], idx, "dynamic import()", line)
            if re.search(r"\bReflect\.", stripped):
                self._record_event(result["reflection_usages"], idx, "Reflect API", line)
            if re.search(r"\bProxy\s*\(", stripped):
                self._record_event(result["runtime_hooks"], idx, "Proxy", line)
            if re.search(r"\bJSON\.parse\s*\(", stripped):
                self._record_event(result["serialization_risks"], idx, "JSON.parse", line)
            if re.search(r"\bObject\.defineProperty\b|\bObject\.setPrototypeOf\b", stripped):
                self._record_event(result["metaprogramming_usages"], idx, "prototype mutation", line)
        return result

    def _analyze_php(self, content: str) -> Dict[str, Any]:
        result = self._init_dynamic_result()
        lines = content.split("\n")
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.search(r"\bfunction\s+\w+\s*\(", stripped):
                result["syntax_summary"]["function_count"] += 1
            if re.search(r"\bclass\s+\w+", stripped):
                result["syntax_summary"]["class_count"] += 1
            if re.search(r"\bif\s*\(", stripped):
                result["syntax_summary"]["conditional_count"] += 1
            if re.search(r"\bfor(each)?\s*\(|\bwhile\s*\(", stripped):
                result["syntax_summary"]["loop_count"] += 1
            if re.search(r"\bcatch\s*\(", stripped):
                result["syntax_summary"]["exception_handling_count"] += 1

            if re.search(r"\beval\s*\(", stripped):
                self._record_event(result["dynamic_constructs"], idx, "eval", line)
                self._record_event(result["dangerous_calls"], idx, "eval", line)
            if re.search(r"\b(include|include_once|require|require_once)\s*\(?\s*\$", stripped):
                self._record_event(result["dynamic_imports"], idx, "dynamic include/require", line)
            if re.search(r"\b(unserialize)\s*\(", stripped):
                self._record_event(result["serialization_risks"], idx, "unserialize", line)
            if re.search(r"\bReflection[A-Za-z_]+\b", stripped):
                self._record_event(result["reflection_usages"], idx, "Reflection API", line)
            if re.search(r"\b__call\b|\b__callStatic\b|\b__get\b|\b__set\b", stripped):
                self._record_event(result["runtime_hooks"], idx, "magic method hook", line)
            if re.search(r"\$[A-Za-z_]\w*\s*->\s*\$[A-Za-z_]\w*", stripped):
                self._record_event(result["metaprogramming_usages"], idx, "dynamic property access", line)
        return result

    def _analyze_ruby(self, content: str) -> Dict[str, Any]:
        result = self._init_dynamic_result()
        lines = content.split("\n")
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r"^\s*def\s+\w+[!?=]?", stripped):
                result["syntax_summary"]["function_count"] += 1
            if re.match(r"^\s*class\s+\w+|^\s*module\s+\w+", stripped):
                result["syntax_summary"]["class_count"] += 1
            if re.search(r"\bif\b|\bunless\b", stripped):
                result["syntax_summary"]["conditional_count"] += 1
            if re.search(r"\bwhile\b|\buntil\b|\beach\s+do\b", stripped):
                result["syntax_summary"]["loop_count"] += 1
            if re.search(r"\brescue\b", stripped):
                result["syntax_summary"]["exception_handling_count"] += 1

            if re.search(r"\beval\s*\(", stripped):
                self._record_event(result["dynamic_constructs"], idx, "eval", line)
                self._record_event(result["dangerous_calls"], idx, "eval", line)
            if re.search(r"\brequire\s+\w+|\brequire_relative\s+\w+", stripped):
                if not re.search(r"['\"]", stripped):
                    self._record_event(result["dynamic_imports"], idx, "dynamic require", line)
            if re.search(r"\bconst_get\b|\bconst_set\b|\bsend\s*\(|\bpublic_send\s*\(", stripped):
                self._record_event(result["reflection_usages"], idx, "const_get/send", line)
            if re.search(r"\bMarshal\.load\b|\bYAML\.load\b", stripped):
                self._record_event(result["serialization_risks"], idx, "unsafe deserialize", line)
            if re.search(r"\bmethod_missing\b|\bdefine_method\b|\bclass_eval\b|\bmodule_eval\b", stripped):
                self._record_event(result["runtime_hooks"], idx, "runtime method hook", line)
                self._record_event(result["metaprogramming_usages"], idx, "meta programming", line)
        return result

    def _calculate_risk_score(self, analysis: Dict[str, Any]) -> int:
        weighted = (
            len(analysis["dangerous_calls"]) * 4
            + len(analysis["serialization_risks"]) * 3
            + len(analysis["dynamic_imports"]) * 2
            + len(analysis["runtime_hooks"]) * 2
            + len(analysis["reflection_usages"]) * 1
            + len(analysis["metaprogramming_usages"]) * 2
        )
        return min(100, weighted)

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        return self._run(file_path, language)


class GetCodeMetricsInput(BaseModel):
    """Input schema for GetCodeMetricsTool."""

    file_path: str = Field(..., description="Path to source file")
    language: Optional[str] = Field(
        default=None, description="Programming language"
    )


class GetCodeMetricsTool(BaseTool):
    """Tool for calculating code metrics (LOC, complexity, etc.)."""

    name: str = "get_code_metrics"
    description: str = """
    Calculate code metrics for a source file.
    Returns lines of code, comment lines, complexity estimates, etc.
    """
    args_schema: Type[BaseModel] = GetCodeMetricsInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._detector = DetectLanguageTool(base_path=self._base_path)
        self._extract_functions = ExtractFunctionsTool(base_path=self._base_path)
        self._extract_classes = ExtractClassesTool(base_path=self._base_path)
        self._extract_imports = ExtractImportsTool(base_path=self._base_path)

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Execute metrics calculation."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Detect language
            if not language:
                lang_result = self._detector._run(file_path)
                if lang_result["status"] == "success":
                    language = lang_result["language"]
            language = (language or "unknown").strip().lower()

            lines = content.split("\n")
            total_lines = len(lines)
            code_lines = 0
            comment_only_lines = 0
            inline_comment_lines = 0
            blank_lines = 0

            single_prefixes = self._single_line_comment_prefixes(language)
            multi_markers = self._multiline_comment_markers(language)
            in_multiline_comment: Optional[str] = None

            for line in lines:
                stripped = line.strip()

                if not stripped:
                    blank_lines += 1
                    continue

                if in_multiline_comment:
                    comment_only_lines += 1
                    if in_multiline_comment in stripped:
                        in_multiline_comment = None
                    continue

                if self._is_full_line_comment(stripped, single_prefixes):
                    comment_only_lines += 1
                    continue

                started_block, ended_same_line, comment_only = self._starts_multiline_comment(
                    stripped, multi_markers
                )
                if started_block:
                    if comment_only:
                        comment_only_lines += 1
                    else:
                        inline_comment_lines += 1
                        code_lines += 1
                    if not ended_same_line:
                        in_multiline_comment = started_block
                    continue

                if self._has_inline_comment(stripped, single_prefixes):
                    inline_comment_lines += 1
                code_lines += 1

            function_count = len(self._extract_functions._extract_functions_by_language(content, language))
            class_count = len(self._extract_classes._extract_classes_by_language(content, language))
            import_count = len(self._extract_imports._extract_imports_by_language(content, language))
            decision_points = self._estimate_decision_points(content, language)
            cyclomatic_complexity = max(1, decision_points + 1)
            complexity_per_loc = round(cyclomatic_complexity / code_lines, 4) if code_lines > 0 else 0.0
            complexity_level = self._complexity_level(cyclomatic_complexity)

            max_line_length = max((len(line) for line in lines), default=0)
            avg_line_length = round(sum(len(line) for line in lines) / total_lines, 2) if total_lines > 0 else 0.0
            comment_lines = comment_only_lines + inline_comment_lines
            comment_ratio = round(comment_lines / total_lines * 100, 2) if total_lines > 0 else 0
            code_ratio = round(code_lines / total_lines * 100, 2) if total_lines > 0 else 0
            blank_ratio = round(blank_lines / total_lines * 100, 2) if total_lines > 0 else 0

            maintainability_index = max(
                0.0,
                min(
                    100.0,
                    round(
                        100.0
                        - (cyclomatic_complexity * 1.5)
                        - (avg_line_length * 0.08)
                        - (max(0, code_lines - comment_lines) * 0.01),
                        2,
                    ),
                ),
            )

            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "total_lines": total_lines,
                "loc": code_lines,
                "code_lines": code_lines,
                "comment_lines": comment_lines,
                "comment_only_lines": comment_only_lines,
                "inline_comment_lines": inline_comment_lines,
                "blank_lines": blank_lines,
                "comment_ratio": comment_ratio,
                "code_ratio": code_ratio,
                "blank_ratio": blank_ratio,
                "function_count": function_count,
                "class_count": class_count,
                "import_count": import_count,
                "decision_points": decision_points,
                "cyclomatic_complexity": cyclomatic_complexity,
                "complexity_per_loc": complexity_per_loc,
                "complexity_level": complexity_level,
                "max_line_length": max_line_length,
                "avg_line_length": avg_line_length,
                "maintainability_index": maintainability_index,
                "metrics_version": 2,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _single_line_comment_prefixes(self, language: str) -> List[str]:
        mapping = {
            "python": ["#"],
            "ruby": ["#"],
            "javascript": ["//"],
            "typescript": ["//"],
            "java": ["//"],
            "go": ["//"],
            "csharp": ["//"],
            "rust": ["//"],
            "php": ["//", "#"],
            "sql": ["--"],
            "yaml": ["#"],
        }
        return mapping.get(language, ["//", "#", "--"])

    def _multiline_comment_markers(self, language: str) -> List[tuple[str, str]]:
        markers = {
            "python": [('"""', '"""'), ("'''", "'''")],
            "javascript": [("/*", "*/")],
            "typescript": [("/*", "*/")],
            "java": [("/*", "*/")],
            "go": [("/*", "*/")],
            "csharp": [("/*", "*/")],
            "rust": [("/*", "*/")],
            "php": [("/*", "*/")],
            "ruby": [("=begin", "=end")],
        }
        return markers.get(language, [("/*", "*/")])

    def _is_full_line_comment(self, stripped: str, prefixes: List[str]) -> bool:
        return any(stripped.startswith(prefix) for prefix in prefixes)

    def _starts_multiline_comment(
        self,
        stripped: str,
        markers: List[tuple[str, str]],
    ) -> tuple[Optional[str], bool, bool]:
        for start, end in markers:
            start_idx = stripped.find(start)
            if start_idx == -1:
                continue
            end_idx = stripped.find(end, start_idx + len(start))
            ended_same_line = end_idx != -1 and end_idx > start_idx
            comment_only = start_idx == 0
            if ended_same_line and comment_only:
                trailing = stripped[end_idx + len(end):].strip()
                comment_only = trailing == ""
            return end, ended_same_line, comment_only
        return None, False, False

    def _has_inline_comment(self, stripped: str, prefixes: List[str]) -> bool:
        for prefix in prefixes:
            idx = stripped.find(prefix)
            if idx > 0:
                return True
        for start, _ in [("/*", "*/"), ('"""', '"""'), ("'''", "'''")]:
            idx = stripped.find(start)
            if idx > 0:
                return True
        return False

    def _estimate_decision_points(self, content: str, language: str) -> int:
        patterns = {
            "python": [r"\bif\b", r"\belif\b", r"\bfor\b", r"\bwhile\b", r"\bexcept\b", r"\band\b", r"\bor\b"],
            "javascript": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"&&", r"\|\|", r"\?"],
            "typescript": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"&&", r"\|\|", r"\?"],
            "java": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"&&", r"\|\|", r"\?"],
            "go": [r"\bif\b", r"\bfor\b", r"\bcase\b", r"\bselect\b", r"&&", r"\|\|"],
            "csharp": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"&&", r"\|\|", r"\?"],
            "rust": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bmatch\b", r"&&", r"\|\|"],
            "php": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"&&", r"\|\|", r"\?"],
            "ruby": [r"\bif\b", r"\belsif\b", r"\bfor\b", r"\bwhile\b", r"\brescue\b", r"\band\b", r"\bor\b"],
        }
        selected = patterns.get(language, patterns["javascript"])
        return sum(len(re.findall(pattern, content)) for pattern in selected)

    def _complexity_level(self, cyclomatic_complexity: int) -> str:
        if cyclomatic_complexity <= 10:
            return "low"
        if cyclomatic_complexity <= 20:
            return "medium"
        if cyclomatic_complexity <= 40:
            return "high"
        return "very_high"

    async def _arun(self, file_path: str, language: str = None) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(file_path, language)


class GenerateCodebaseMetricsInput(BaseModel):
    """Input schema for GenerateCodebaseMetricsTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    extensions: Optional[List[str]] = Field(
        default=None, description="Optional extension filter"
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    include_unknown: bool = Field(
        default=False,
        description="Include files with unknown language in totals",
    )


class GenerateCodebaseMetricsTool(BaseTool):
    """Generate aggregate LOC and code metrics for a directory."""

    name: str = "generate_codebase_metrics"
    description: str = """
    Generate aggregate LOC and code quality metrics for a codebase directory.
    Returns per-file metrics and per-language summaries.
    """
    args_schema: Type[BaseModel] = GenerateCodebaseMetricsInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._detector = DetectLanguageTool(base_path=self._base_path)
        self._metrics = GetCodeMetricsTool(base_path=self._base_path)
        language_map = type(self._detector).__dict__.get("LANGUAGE_MAP", {})
        fallback_extensions = {
            ".py",
            ".js",
            ".mjs",
            ".cjs",
            ".ts",
            ".mts",
            ".cts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".cs",
            ".rs",
            ".php",
            ".rb",
        }
        if isinstance(language_map, dict) and language_map:
            self._known_extensions = set(language_map.keys())
        else:
            self._known_extensions = fallback_extensions

    def _resolve_path(self, directory_path: str) -> str:
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self,
        directory_path: str = ".",
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        include_unknown: bool = False,
    ) -> Dict[str, Any]:
        try:
            resolved_root = self._resolve_path(directory_path)
            root = Path(resolved_root)
            if not root.exists():
                return {"status": "error", "error": f"Directory not found: {directory_path}"}
            if not root.is_dir():
                return {"status": "error", "error": f"Not a directory: {directory_path}"}

            per_file: List[Dict[str, Any]] = []
            language_stats: Dict[str, Dict[str, Any]] = {}

            total_files = 0
            analyzed_files = 0
            total_lines = 0
            total_loc = 0
            total_comment_lines = 0
            total_blank_lines = 0
            total_decision_points = 0
            total_complexity = 0
            complexity_distribution = {"low": 0, "medium": 0, "high": 0, "very_high": 0}

            for current_root, dirs, filenames in os.walk(root):
                if not recursive:
                    dirs.clear()

                for filename in filenames:
                    total_files += 1
                    abs_path = Path(current_root) / filename
                    ext = abs_path.suffix.lower()

                    if extensions and ext not in extensions:
                        continue
                    if not extensions and ext not in self._known_extensions:
                        continue

                    rel_path = abs_path.resolve().relative_to(root.resolve()).as_posix()
                    lang_result = self._detector._run(str(abs_path))
                    language = lang_result.get("language", "unknown")
                    if language == "unknown" and not include_unknown:
                        continue

                    file_metrics = self._metrics._run(str(abs_path), language=language)
                    if file_metrics.get("status") != "success":
                        continue

                    analyzed_files += 1
                    total_lines += int(file_metrics.get("total_lines", 0))
                    total_loc += int(file_metrics.get("loc", file_metrics.get("code_lines", 0)))
                    total_comment_lines += int(file_metrics.get("comment_lines", 0))
                    total_blank_lines += int(file_metrics.get("blank_lines", 0))
                    total_decision_points += int(file_metrics.get("decision_points", 0))
                    total_complexity += int(file_metrics.get("cyclomatic_complexity", 0))

                    complexity_level = file_metrics.get("complexity_level", "low")
                    if complexity_level in complexity_distribution:
                        complexity_distribution[complexity_level] += 1

                    language_bucket = language_stats.setdefault(
                        language,
                        {
                            "files": 0,
                            "loc": 0,
                            "total_lines": 0,
                            "comment_lines": 0,
                            "blank_lines": 0,
                            "cyclomatic_complexity": 0,
                            "decision_points": 0,
                        },
                    )
                    language_bucket["files"] += 1
                    language_bucket["loc"] += int(file_metrics.get("loc", 0))
                    language_bucket["total_lines"] += int(file_metrics.get("total_lines", 0))
                    language_bucket["comment_lines"] += int(file_metrics.get("comment_lines", 0))
                    language_bucket["blank_lines"] += int(file_metrics.get("blank_lines", 0))
                    language_bucket["cyclomatic_complexity"] += int(file_metrics.get("cyclomatic_complexity", 0))
                    language_bucket["decision_points"] += int(file_metrics.get("decision_points", 0))

                    per_file.append(
                        {
                            "path": rel_path,
                            "language": language,
                            "extension": ext,
                            "loc": int(file_metrics.get("loc", 0)),
                            "total_lines": int(file_metrics.get("total_lines", 0)),
                            "comment_lines": int(file_metrics.get("comment_lines", 0)),
                            "blank_lines": int(file_metrics.get("blank_lines", 0)),
                            "cyclomatic_complexity": int(file_metrics.get("cyclomatic_complexity", 0)),
                            "complexity_level": complexity_level,
                            "maintainability_index": file_metrics.get("maintainability_index", 0.0),
                        }
                    )

            language_percentages = {
                language: round((stats["loc"] / total_loc) * 100, 2) if total_loc > 0 else 0.0
                for language, stats in language_stats.items()
            }

            average_loc_per_file = round(total_loc / analyzed_files, 2) if analyzed_files > 0 else 0.0
            average_complexity = round(total_complexity / analyzed_files, 2) if analyzed_files > 0 else 0.0
            comment_density = round((total_comment_lines / total_lines) * 100, 2) if total_lines > 0 else 0.0

            largest_files = sorted(per_file, key=lambda item: item["loc"], reverse=True)[:10]
            most_complex_files = sorted(
                per_file,
                key=lambda item: item["cyclomatic_complexity"],
                reverse=True,
            )[:10]

            for stats in language_stats.values():
                files = stats["files"] or 1
                stats["avg_loc_per_file"] = round(stats["loc"] / files, 2)
                stats["avg_cyclomatic_complexity"] = round(stats["cyclomatic_complexity"] / files, 2)
                stats["comment_density"] = round(
                    (stats["comment_lines"] / stats["total_lines"]) * 100,
                    2,
                ) if stats["total_lines"] > 0 else 0.0

            return {
                "status": "success",
                "directory_path": directory_path,
                "total_files": total_files,
                "analyzed_files": analyzed_files,
                "total_lines": total_lines,
                "total_loc": total_loc,
                "total_comment_lines": total_comment_lines,
                "total_blank_lines": total_blank_lines,
                "total_decision_points": total_decision_points,
                "average_loc_per_file": average_loc_per_file,
                "average_cyclomatic_complexity": average_complexity,
                "comment_density": comment_density,
                "complexity_distribution": complexity_distribution,
                "language_stats": language_stats,
                "language_percentages": language_percentages,
                "largest_files": largest_files,
                "most_complex_files": most_complex_files,
                "file_metrics": per_file,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self,
        directory_path: str = ".",
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        include_unknown: bool = False,
    ) -> Dict[str, Any]:
        return self._run(directory_path, extensions, recursive, include_unknown)


class ScanDirectoryInput(BaseModel):
    """Input schema for ScanDirectoryTool."""

    directory_path: str = Field(..., description="Directory to scan")
    extensions: Optional[List[str]] = Field(
        default=None, description="File extensions to include"
    )
    recursive: bool = Field(default=True, description="Scan recursively")


class ScanDirectoryTool(BaseTool):
    """Tool for scanning directories and collecting source files."""

    name: str = "scan_directory"
    description: str = """
    Scan a directory for source code files.
    Returns list of files with language detection.
    """
    args_schema: Type[BaseModel] = ScanDirectoryInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, directory_path: str) -> str:
        """Resolve directory path."""
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self, directory_path: str = None, extensions: List[str] = None, recursive: bool = True
    ) -> Dict[str, Any]:
        """Execute directory scan."""
        try:
            resolved_path = self._resolve_path(directory_path or ".")

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"Directory not found: {directory_path}"}

            if not os.path.isdir(resolved_path):
                return {"status": "error", "error": f"Not a directory: {directory_path}"}

            detector = DetectLanguageTool(base_path=self._base_path)
            files = []

            for root, dirs, filenames in os.walk(resolved_path):
                if not recursive:
                    dirs.clear()

                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    ext = Path(filename).suffix.lower()

                    # Filter by extensions if provided
                    if extensions and ext not in extensions:
                        continue

                    # Detect language
                    lang_result = detector._run(file_path)
                    language = lang_result.get("language", "unknown") if lang_result["status"] == "success" else "unknown"

                    # Get file size
                    size = os.path.getsize(file_path)

                    files.append(
                        {
                            "path": file_path,
                            "name": filename,
                            "extension": ext,
                            "language": language,
                            "size": size,
                        }
                    )

            return {
                "status": "success",
                "directory_path": directory_path,
                "files": files,
                "total_count": len(files),
                "languages": self._count_languages(files),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _count_languages(self, files: List[Dict]) -> Dict[str, int]:
        """Count files by language."""
        counts = {}
        for f in files:
            lang = f.get("language", "unknown")
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    async def _arun(
        self, directory_path: str = None, extensions: List[str] = None, recursive: bool = True
    ) -> Dict[str, Any]:
        """Async wrapper."""
        return self._run(directory_path, extensions, recursive)


class BuildDependencyGraphInput(BaseModel):
    """Input schema for BuildDependencyGraphTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    recursive: bool = Field(default=True, description="Scan directories recursively")
    include_external: bool = Field(
        default=False,
        description="Include unresolved/external imports as graph edges",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter (e.g. ['.py', '.ts'])",
    )


class BuildDependencyGraphTool(BaseTool):
    """Tool for constructing dependency graph from imports and references."""

    name: str = "build_dependency_graph"
    description: str = """
    Build a file-level dependency graph from imports/references.
    Detects internal/external edges, reverse references, and cycles.
    """
    args_schema: Type[BaseModel] = BuildDependencyGraphInput
    SUPPORTED_LANGUAGES: Set[str] = {
        "typescript",
        "javascript",
        "python",
        "java",
        "go",
        "csharp",
        "rust",
        "php",
        "ruby",
    }
    _RELATIVE_IMPORT_LANGUAGES: Set[str] = {"typescript", "javascript", "php", "ruby"}

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._detector = DetectLanguageTool(base_path=self._base_path)
        self._import_extractor = ExtractImportsTool(base_path=self._base_path)

    def _resolve_path(self, directory_path: str) -> str:
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external: bool = False,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            resolved_root = self._resolve_path(directory_path)
            root_path = Path(resolved_root).resolve()

            if not root_path.exists():
                return {"status": "error", "error": f"Directory not found: {directory_path}"}
            if not root_path.is_dir():
                return {"status": "error", "error": f"Not a directory: {directory_path}"}

            files: List[Dict[str, Any]] = []
            file_nodes: Set[str] = set()
            aliases_to_file: Dict[str, Set[str]] = {}

            for current_root, dirs, filenames in os.walk(root_path):
                if not recursive:
                    dirs.clear()
                for filename in filenames:
                    abs_path = Path(current_root) / filename
                    ext = abs_path.suffix.lower()
                    if extensions and ext not in extensions:
                        continue
                    lang_result = self._detector._run(str(abs_path))
                    if lang_result.get("status") != "success":
                        continue
                    language = lang_result.get("language", "unknown")
                    if language not in self.SUPPORTED_LANGUAGES:
                        continue

                    rel_path = abs_path.resolve().relative_to(root_path).as_posix()
                    files.append(
                        {
                            "abs_path": str(abs_path.resolve()),
                            "rel_path": rel_path,
                            "language": language,
                            "extension": ext,
                        }
                    )
                    file_nodes.add(rel_path)
                    for alias in self._build_aliases(rel_path, language):
                        aliases_to_file.setdefault(alias, set()).add(rel_path)

            imports_by_file: Dict[str, List[Dict[str, Any]]] = {}
            for entry in files:
                with open(entry["abs_path"], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                imports_by_file[entry["rel_path"]] = self._import_extractor._extract_imports_by_language(
                    content, entry["language"]
                )

            edges: List[Dict[str, Any]] = []
            adjacency: Dict[str, Set[str]] = {}
            reverse_edges: Dict[str, Set[str]] = {}
            unresolved_import_count = 0
            external_edge_count = 0

            files_by_rel = {f["rel_path"]: f for f in files}
            for source_rel, import_items in imports_by_file.items():
                source_entry = files_by_rel[source_rel]
                source_abs = source_entry["abs_path"]
                source_lang = source_entry["language"]

                for item in import_items:
                    module = item.get("module", "")
                    target_rel = self._resolve_import_to_file(
                        module=module,
                        source_rel=source_rel,
                        source_abs=source_abs,
                        source_language=source_lang,
                        root_path=root_path,
                        files_by_rel=files_by_rel,
                        aliases_to_file=aliases_to_file,
                    )

                    if target_rel:
                        adjacency.setdefault(source_rel, set()).add(target_rel)
                        reverse_edges.setdefault(target_rel, set()).add(source_rel)
                        edges.append(
                            {
                                "source": source_rel,
                                "target": target_rel,
                                "module": module,
                                "line_number": item.get("line_number"),
                                "import_type": item.get("type"),
                                "is_external": False,
                                "is_resolved": True,
                            }
                        )
                    else:
                        unresolved_import_count += 1
                        if include_external:
                            external_edge_count += 1
                            edges.append(
                                {
                                    "source": source_rel,
                                    "target": module,
                                    "module": module,
                                    "line_number": item.get("line_number"),
                                    "import_type": item.get("type"),
                                    "is_external": True,
                                    "is_resolved": False,
                                }
                            )

            cycles = self._find_cycles(adjacency)
            downstream_dependencies = {
                node: sorted(list(reverse_edges.get(node, set())))
                for node in sorted(file_nodes)
                if reverse_edges.get(node)
            }

            return {
                "status": "success",
                "directory_path": directory_path,
                "root_path": str(root_path),
                "node_count": len(file_nodes),
                "edge_count": len(edges),
                "nodes": [
                    {
                        "id": f["rel_path"],
                        "path": f["rel_path"],
                        "language": f["language"],
                        "extension": f["extension"],
                    }
                    for f in sorted(files, key=lambda item: item["rel_path"])
                ],
                "edges": edges,
                "downstream_dependencies": downstream_dependencies,
                "cycles": cycles,
                "summary": {
                    "internal_edge_count": sum(1 for edge in edges if not edge["is_external"]),
                    "external_edge_count": external_edge_count,
                    "unresolved_import_count": unresolved_import_count,
                    "cycle_count": len(cycles),
                },
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _build_aliases(self, rel_path: str, language: str) -> Set[str]:
        aliases: Set[str] = set()
        rel = Path(rel_path)
        stem_path = rel.with_suffix("").as_posix()
        aliases.add(stem_path)
        aliases.add(stem_path.replace("/", "."))

        if rel.stem == "index":
            parent = rel.parent.as_posix()
            if parent != ".":
                aliases.add(parent)
                aliases.add(parent.replace("/", "."))

        if language == "python":
            if rel.name == "__init__.py":
                package = rel.parent.as_posix()
                if package and package != ".":
                    aliases.add(package.replace("/", "."))
                    aliases.add(package)
            aliases.add(stem_path.replace("/", "."))

        if language in {"java", "csharp"}:
            parts = [part for part in stem_path.split("/") if part]
            for index in range(1, len(parts)):
                aliases.add(".".join(parts[index:]))

        if language == "rust" and rel.name == "mod.rs":
            module_root = rel.parent.as_posix()
            if module_root != ".":
                aliases.add(module_root)
                aliases.add(module_root.replace("/", "::"))

        return {a for a in aliases if a}

    def _resolve_import_to_file(
        self,
        module: str,
        source_rel: str,
        source_abs: str,
        source_language: str,
        root_path: Path,
        files_by_rel: Dict[str, Dict[str, Any]],
        aliases_to_file: Dict[str, Set[str]],
    ) -> Optional[str]:
        normalized = (module or "").strip()
        if not normalized:
            return None

        candidate_paths: List[str] = []
        source_parent_rel = Path(source_rel).parent

        if source_language in self._RELATIVE_IMPORT_LANGUAGES and normalized.startswith("."):
            rel_candidate = os.path.normpath((source_parent_rel / normalized).as_posix())
            rel_candidate = rel_candidate.replace("\\", "/").lstrip("./")
            candidate_paths.extend(self._expand_relative_candidates(rel_candidate))

        if source_language == "python":
            candidate_paths.extend(
                self._resolve_python_candidates(normalized, source_parent_rel.as_posix())
            )
        elif source_language in {"java", "csharp"}:
            candidate_paths.extend(self._expand_relative_candidates(normalized.replace(".", "/")))
        elif source_language == "rust":
            rust_path = normalized.replace("crate::", "").replace("super::", "")
            rust_path = rust_path.replace("::", "/")
            candidate_paths.extend(
                self._expand_relative_candidates(rust_path, prefer_exts=[".rs"])
            )

        for candidate in candidate_paths:
            if candidate in files_by_rel:
                return candidate

        alias_candidates = [
            normalized,
            normalized.replace("\\", "/"),
            normalized.replace("/", "."),
            normalized.replace(".", "/"),
            normalized.replace("::", "/"),
            normalized.replace("::", "."),
        ]
        for alias in alias_candidates:
            matches = aliases_to_file.get(alias, set())
            if len(matches) == 1:
                return next(iter(matches))

        if source_language == "go" and "/" in normalized:
            suffix = normalized.strip("/")
            suffix_matches = [
                rel for rel in files_by_rel if rel.endswith(f"{suffix}.go") or rel.endswith(f"{suffix}/mod.rs")
            ]
            if len(suffix_matches) == 1:
                return suffix_matches[0]

        return None

    def _expand_relative_candidates(
        self,
        module_path: str,
        prefer_exts: Optional[List[str]] = None,
    ) -> List[str]:
        normalized = module_path.replace("\\", "/").strip()
        if normalized.startswith("/"):
            normalized = normalized[1:]
        base = Path(normalized)
        exts = prefer_exts or [
            ".py",
            ".ts",
            ".tsx",
            ".mts",
            ".cts",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            ".java",
            ".go",
            ".cs",
            ".rs",
            ".php",
            ".rb",
        ]
        candidates = [base.with_suffix(ext).as_posix() for ext in exts if ext]
        candidates.extend(
            [
                (base / "__init__.py").as_posix(),
                (base / "index.ts").as_posix(),
                (base / "index.tsx").as_posix(),
                (base / "index.js").as_posix(),
                (base / "index.jsx").as_posix(),
                (base / "mod.rs").as_posix(),
            ]
        )
        deduped: List[str] = []
        seen: Set[str] = set()
        for candidate in candidates:
            cleaned = candidate.replace("//", "/")
            if cleaned not in seen:
                seen.add(cleaned)
                deduped.append(cleaned)
        return deduped

    def _resolve_python_candidates(self, module: str, source_parent: str) -> List[str]:
        normalized = module.strip()
        if not normalized:
            return []
        if normalized.startswith("."):
            level = len(normalized) - len(normalized.lstrip("."))
            tail = normalized[level:]
            parent_parts = [] if source_parent in {"", "."} else source_parent.split("/")
            if level > 0:
                trim = max(0, level - 1)
                parent_parts = parent_parts[: max(0, len(parent_parts) - trim)]
            module_parts = [p for p in tail.split(".") if p]
            target_path = "/".join(parent_parts + module_parts)
        else:
            target_path = normalized.replace(".", "/")
        return self._expand_relative_candidates(target_path, prefer_exts=[".py"])

    def _find_cycles(self, adjacency: Dict[str, Set[str]]) -> List[List[str]]:
        visited: Dict[str, int] = {}
        stack: List[str] = []
        in_stack: Set[str] = set()
        cycles: Set[tuple[str, ...]] = set()

        def canonicalize_cycle(path_cycle: List[str]) -> tuple[str, ...]:
            if not path_cycle:
                return tuple()
            min_index = min(range(len(path_cycle)), key=lambda idx: path_cycle[idx])
            rotated = path_cycle[min_index:] + path_cycle[:min_index]
            return tuple(rotated)

        def dfs(node: str) -> None:
            visited[node] = 1
            stack.append(node)
            in_stack.add(node)

            for neighbor in adjacency.get(node, set()):
                if visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
                elif neighbor in in_stack:
                    idx = stack.index(neighbor)
                    cycle_nodes = stack[idx:].copy()
                    canonical = canonicalize_cycle(cycle_nodes)
                    if canonical:
                        cycles.add(canonical)

            stack.pop()
            in_stack.remove(node)
            visited[node] = 2

        for node in adjacency:
            if visited.get(node, 0) == 0:
                dfs(node)

        return [list(cycle) for cycle in sorted(cycles)]

    async def _arun(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external: bool = False,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._run(directory_path, recursive, include_external, extensions)


class ClassifyFileImpactInput(BaseModel):
    """Input schema for ClassifyFileImpactTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for diff mode (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for diff mode; when omitted uses working tree mode",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files as create impacts (working tree mode)",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter (e.g. ['.py', '.ts'])",
    )


class ClassifyFileImpactTool(BaseTool):
    """Classify file impacts as create, modify, or delete from git changes."""

    name: str = "classify_file_impact"
    description: str = """
    Classify changed files into create/modify/delete.
    Supports working-tree changes and explicit ref-to-ref diffs.
    """
    args_schema: Type[BaseModel] = ClassifyFileImpactInput

    _STATUS_TO_IMPACT: Dict[str, str] = {
        "A": "create",
        "D": "delete",
        "M": "modify",
        "R": "modify",
        "C": "modify",
        "T": "modify",
        "U": "modify",
        "X": "modify",
        "B": "modify",
    }
    _IMPACT_PRIORITY: Dict[str, int] = {"modify": 1, "create": 2, "delete": 3}

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, directory_path: str) -> Path:
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return path.resolve()

    def _run_git(self, repo_root: Path, args: List[str]) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return completed.stdout

    def _get_repo_root(self, start_path: Path) -> Path:
        completed = subprocess.run(
            ["git", "-C", str(start_path), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return Path(completed.stdout.strip()).resolve()

    def _scope_pathspec(self, repo_root: Path, requested_path: Path) -> Optional[str]:
        try:
            rel = requested_path.relative_to(repo_root).as_posix()
        except ValueError:
            return None
        if rel in {"", "."}:
            return None
        return rel

    def _normalize_path(self, path: str) -> str:
        return str(path).replace("\\", "/").lstrip("./")

    def _parse_name_status(self, output: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status_token = parts[0].strip()
            status_code = status_token[0] if status_token else ""
            if status_code in {"R", "C"} and len(parts) >= 3:
                old_path = self._normalize_path(parts[1])
                new_path = self._normalize_path(parts[2])
                entries.append(
                    {
                        "status_code": status_code,
                        "raw_status": status_token,
                        "path": new_path,
                        "old_path": old_path,
                    }
                )
                continue
            path = self._normalize_path(parts[1])
            entries.append(
                {
                    "status_code": status_code,
                    "raw_status": status_token,
                    "path": path,
                }
            )
        return entries

    def _collect_working_tree_changes(
        self,
        repo_root: Path,
        include_untracked: bool,
        scope_pathspec: Optional[str],
    ) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []

        staged_args = ["diff", "--cached", "--name-status", "-M"]
        unstaged_args = ["diff", "--name-status", "-M"]
        if scope_pathspec:
            staged_args.extend(["--", scope_pathspec])
            unstaged_args.extend(["--", scope_pathspec])

        entries.extend(self._parse_name_status(self._run_git(repo_root, staged_args)))
        entries.extend(self._parse_name_status(self._run_git(repo_root, unstaged_args)))

        if include_untracked:
            untracked_args = ["ls-files", "--others", "--exclude-standard"]
            if scope_pathspec:
                untracked_args.extend(["--", scope_pathspec])
            untracked_output = self._run_git(repo_root, untracked_args)
            for line in untracked_output.splitlines():
                path = self._normalize_path(line.strip())
                if path:
                    entries.append(
                        {
                            "status_code": "A",
                            "raw_status": "UNTRACKED",
                            "path": path,
                        }
                    )
        return entries

    def _collect_ref_diff_changes(
        self,
        repo_root: Path,
        base_ref: str,
        target_ref: Optional[str],
        scope_pathspec: Optional[str],
    ) -> List[Dict[str, Any]]:
        args = ["diff", "--name-status", "-M", base_ref]
        if target_ref:
            args.append(target_ref)
        if scope_pathspec:
            args.extend(["--", scope_pathspec])
        return self._parse_name_status(self._run_git(repo_root, args))

    def _is_in_scope(self, path: str, scope_pathspec: Optional[str]) -> bool:
        if not scope_pathspec:
            return True
        normalized_scope = self._normalize_path(scope_pathspec).rstrip("/")
        normalized_path = self._normalize_path(path)
        return normalized_path == normalized_scope or normalized_path.startswith(f"{normalized_scope}/")

    def _extension_allowed(self, path: str, extensions: Optional[List[str]]) -> bool:
        if not extensions:
            return True
        allowed = {ext.lower() for ext in extensions}
        return Path(path).suffix.lower() in allowed

    def _merge_impact(
        self,
        merged: Dict[str, Dict[str, Any]],
        entry: Dict[str, Any],
    ) -> None:
        path = str(entry.get("path", "")).strip()
        if not path:
            return

        status_code = str(entry.get("status_code", "")).strip()[:1]
        impact = self._STATUS_TO_IMPACT.get(status_code, "modify")
        raw_status = str(entry.get("raw_status", "")).strip()
        old_path = entry.get("old_path")

        current = merged.get(path)
        if current is None:
            merged[path] = {
                "path": path,
                "impact": impact,
                "raw_statuses": [raw_status] if raw_status else [],
                "old_path": old_path,
            }
            return

        existing_impact = str(current.get("impact", "modify"))
        if self._IMPACT_PRIORITY.get(impact, 0) > self._IMPACT_PRIORITY.get(existing_impact, 0):
            current["impact"] = impact
        if raw_status and raw_status not in current["raw_statuses"]:
            current["raw_statuses"].append(raw_status)
        if old_path and not current.get("old_path"):
            current["old_path"] = old_path

    def _run(
        self,
        directory_path: str = ".",
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            requested_path = self._resolve_path(directory_path)
            if not requested_path.exists():
                return {"status": "error", "error": f"Directory not found: {directory_path}"}
            if requested_path.is_file():
                requested_path = requested_path.parent

            repo_root = self._get_repo_root(requested_path)
            scope_pathspec = self._scope_pathspec(repo_root, requested_path)

            if base_ref:
                raw_entries = self._collect_ref_diff_changes(
                    repo_root=repo_root,
                    base_ref=base_ref,
                    target_ref=target_ref,
                    scope_pathspec=scope_pathspec,
                )
                mode = "ref_diff"
            else:
                raw_entries = self._collect_working_tree_changes(
                    repo_root=repo_root,
                    include_untracked=include_untracked,
                    scope_pathspec=scope_pathspec,
                )
                mode = "working_tree"

            merged: Dict[str, Dict[str, Any]] = {}
            for entry in raw_entries:
                path = str(entry.get("path", "")).strip()
                if not path:
                    continue
                if not self._is_in_scope(path, scope_pathspec):
                    continue
                if not self._extension_allowed(path, extensions):
                    continue
                self._merge_impact(merged, entry)

            file_impacts = sorted(merged.values(), key=lambda item: item["path"])
            impact_groups = {"create": [], "modify": [], "delete": []}
            for impact in file_impacts:
                impact_type = str(impact.get("impact", "modify"))
                impact_groups.setdefault(impact_type, []).append(impact["path"])

            for impact_type in impact_groups:
                impact_groups[impact_type] = sorted(set(impact_groups[impact_type]))

            return {
                "status": "success",
                "directory_path": directory_path,
                "repo_root": str(repo_root),
                "mode": mode,
                "scope_pathspec": scope_pathspec or ".",
                "base_ref": base_ref,
                "target_ref": target_ref,
                "file_impacts": file_impacts,
                "classifications": impact_groups,
                "summary": {
                    "total_impacted_files": len(file_impacts),
                    "create_count": len(impact_groups.get("create", [])),
                    "modify_count": len(impact_groups.get("modify", [])),
                    "delete_count": len(impact_groups.get("delete", [])),
                },
            }
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            message = stderr or str(exc)
            return {"status": "error", "error": message}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _analyze_file_impact(
        self,
        repo_root: Path,
        entry: Dict[str, Any],
        mode: str,
        old_ref: str,
        target_ref: Optional[str],
    ) -> List[Dict[str, Any]]:
        path = str(entry.get("path", "")).replace("\\", "/").strip()
        if not path:
            return []

        impact = str(entry.get("impact", "modify")).strip().lower()
        old_path = entry.get("old_path")
        if isinstance(old_path, str):
            old_path = old_path.replace("\\", "/").strip()
        else:
            old_path = None

        language = self._infer_language(path)
        old_content = self._load_old_content(repo_root, old_ref, old_path or path)
        new_content = self._load_new_content(repo_root, path, mode, target_ref)
        old_contract = self._extract_contract_surface(old_content, language, old_path or path)
        new_contract = self._extract_contract_surface(new_content, language, path)

        path_hint = self._is_api_contract_path(path) or (old_path and self._is_api_contract_path(old_path))
        if impact == "delete":
            return self._deleted_file_findings(path=path, contract=old_contract, path_hint=bool(path_hint))
        if impact == "create":
            return []

        findings: List[Dict[str, Any]] = []
        if old_path and old_path != path and path_hint:
            findings.append(
                {
                    "category": "api_contract_path_change",
                    "severity": "medium",
                    "file_path": path,
                    "old_path": old_path,
                    "change_type": "path_rename",
                    "description": f"Public/API contract file moved from '{old_path}' to '{path}'",
                }
            )
        findings.extend(
            self._compare_contracts(
                path=path,
                old_contract=old_contract,
                new_contract=new_contract,
                path_hint=bool(path_hint),
            )
        )
        return findings

    def _infer_language(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        fallback_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".java": "java",
            ".go": "go",
            ".cs": "csharp",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".graphql": "graphql",
            ".gql": "graphql",
            ".proto": "proto",
        }
        if ext in fallback_map:
            return fallback_map[ext]
        return "unknown"

    def _load_old_content(self, repo_root: Path, old_ref: str, path: str) -> Optional[str]:
        if not path:
            return None
        return self._git_show(repo_root, old_ref, path)

    def _load_new_content(
        self,
        repo_root: Path,
        path: str,
        mode: str,
        target_ref: Optional[str],
    ) -> Optional[str]:
        if target_ref:
            return self._git_show(repo_root, target_ref, path)
        abs_path = (repo_root / path).resolve()
        if abs_path.exists() and abs_path.is_file():
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                return file_obj.read()
        if mode == "ref_diff":
            return None
        return None

    def _git_show(self, repo_root: Path, ref: str, path: str) -> Optional[str]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{ref}:{path}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return completed.stdout
        except subprocess.CalledProcessError:
            return None

    def _is_api_contract_path(self, path: str) -> bool:
        lower = path.replace("\\", "/").lower()
        ext = Path(lower).suffix.lower()
        if ext in self._CONTRACT_EXTENSIONS:
            return True
        parts = [part for part in lower.split("/") if part]
        return any(part in self._API_PATH_HINTS for part in parts)

    def _extract_contract_surface(
        self,
        content: Optional[str],
        language: str,
        path: str,
    ) -> Dict[str, Dict[str, Any]]:
        if not content:
            return {}

        ext = Path(path).suffix.lower()
        if ext == ".json":
            return self._extract_json_contracts(content)
        if ext in {".yaml", ".yml"}:
            return self._extract_yaml_contracts(content)

        if language == "python":
            return self._extract_python_contracts(content)
        if language in {"javascript", "typescript"}:
            return self._extract_js_ts_contracts(content, language)
        if language == "java":
            return self._extract_java_contracts(content)
        if language == "go":
            return self._extract_go_contracts(content)
        if language == "csharp":
            return self._extract_csharp_contracts(content)
        if language == "rust":
            return self._extract_rust_contracts(content)
        if language == "php":
            return self._extract_php_contracts(content)
        if language == "ruby":
            return self._extract_ruby_contracts(content)
        return {}

    def _extract_python_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:",
            content,
        ):
            name = match.group(1)
            if name.startswith("_"):
                continue
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            returns = (match.group(3) or "Any").strip()
            key = f"function:{name}"
            contracts[key] = {
                "kind": "function",
                "name": name,
                "signature": f"({params}) -> {returns}",
            }

        for match in re.finditer(r"(?m)^\s*class\s+([A-Za-z_]\w*)(?:\(([^)]*)\))?\s*:", content):
            name = match.group(1)
            if name.startswith("_"):
                continue
            base = (match.group(2) or "").strip()
            key = f"class:{name}"
            contracts[key] = {
                "kind": "class",
                "name": name,
                "signature": f"class {name}({base})" if base else f"class {name}",
            }

        for match in re.finditer(r"(?m)^\s*@\s*[A-Za-z_][\w.]*\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]", content):
            method = match.group(1).upper()
            route = match.group(2)
            key = f"endpoint:{method}:{route}"
            contracts[key] = {
                "kind": "endpoint",
                "name": f"{method} {route}",
                "signature": f"{method} {route}",
            }
        return contracts

    def _extract_js_ts_contracts(self, content: str, language: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*export\s+(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}

        for match in re.finditer(
            r"(?m)^\s*export\s+(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}

        for match in re.finditer(r"(?m)^\s*export\s+class\s+([A-Za-z_]\w*)(?:\s+extends\s+([A-Za-z_]\w*))?", content):
            name = match.group(1)
            base = (match.group(2) or "").strip()
            key = f"class:{name}"
            contracts[key] = {
                "kind": "class",
                "name": name,
                "signature": f"class {name} extends {base}" if base else f"class {name}",
            }

        if language == "typescript":
            for match in re.finditer(r"(?m)^\s*export\s+interface\s+([A-Za-z_]\w*)", content):
                name = match.group(1)
                key = f"interface:{name}"
                contracts[key] = {"kind": "interface", "name": name, "signature": f"interface {name}"}

        for match in re.finditer(
            r"(?m)\b(?:app|router)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
            content,
        ):
            method = match.group(1).upper()
            route = match.group(2)
            key = f"endpoint:{method}:{route}"
            contracts[key] = {
                "kind": "endpoint",
                "name": f"{method} {route}",
                "signature": f"{method} {route}",
            }
        return contracts

    def _extract_java_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "method", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_go_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*func\s+(?:\([^)]+\)\s*)?([A-Z][A-Za-z0-9_]*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_csharp_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+(?:static\s+|virtual\s+|override\s+|async\s+)*[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"method:{name}"
            contracts[key] = {"kind": "method", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_rust_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*pub\s+(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_php_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_ruby_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*def\s+([A-Za-z_]\w*[!?=]?)\s*(?:\(([^)]*)\))?", content):
            name = match.group(1)
            if name.startswith("_"):
                continue
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        return contracts

    def _extract_json_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        try:
            payload = json.loads(content)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        contracts: Dict[str, Dict[str, Any]] = {}
        for key, value in payload.items():
            key_name = str(key)
            contracts[f"schema:{key_name}"] = {
                "kind": "schema_key",
                "name": key_name,
                "signature": type(value).__name__,
            }
        return contracts

    def _extract_yaml_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for line in content.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith(" ") or line.startswith("\t"):
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
            if not match:
                continue
            key_name = match.group(1).strip()
            raw_val = match.group(2).strip()
            value_type = "scalar" if raw_val else "object"
            contracts[f"schema:{key_name}"] = {
                "kind": "schema_key",
                "name": key_name,
                "signature": value_type,
            }
        return contracts

    def _deleted_file_findings(
        self,
        path: str,
        contract: Dict[str, Dict[str, Any]],
        path_hint: bool,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        if contract:
            for old_entry in contract.values():
                kind = str(old_entry.get("kind", "contract"))
                severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
                findings.append(
                    {
                        "category": "api_contract_removal",
                        "severity": severity,
                        "file_path": path,
                        "change_type": "removed_symbol",
                        "symbol": old_entry.get("name"),
                        "symbol_kind": kind,
                        "description": f"Removed {kind} '{old_entry.get('name')}' due to file deletion",
                        "old_signature": old_entry.get("signature"),
                        "new_signature": None,
                    }
                )
        elif path_hint:
            findings.append(
                {
                    "category": "api_contract_removal",
                    "severity": "high",
                    "file_path": path,
                    "change_type": "deleted_api_contract_file",
                    "description": f"Deleted API/contract-oriented file '{path}'",
                    "old_signature": None,
                    "new_signature": None,
                }
            )
        return findings

    def _compare_contracts(
        self,
        path: str,
        old_contract: Dict[str, Dict[str, Any]],
        new_contract: Dict[str, Dict[str, Any]],
        path_hint: bool,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        old_keys = set(old_contract.keys())
        new_keys = set(new_contract.keys())

        for key in sorted(old_keys - new_keys):
            old_entry = old_contract[key]
            kind = str(old_entry.get("kind", "contract"))
            severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
            findings.append(
                {
                    "category": "api_contract_removal",
                    "severity": severity,
                    "file_path": path,
                    "change_type": "removed_symbol",
                    "symbol": old_entry.get("name"),
                    "symbol_kind": kind,
                    "description": f"Removed {kind} '{old_entry.get('name')}' from public surface",
                    "old_signature": old_entry.get("signature"),
                    "new_signature": None,
                }
            )

        for key in sorted(old_keys & new_keys):
            old_entry = old_contract[key]
            new_entry = new_contract[key]
            old_sig = str(old_entry.get("signature", "")).strip()
            new_sig = str(new_entry.get("signature", "")).strip()
            if old_sig == new_sig:
                continue
            kind = str(old_entry.get("kind", "contract"))
            severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
            findings.append(
                {
                    "category": "api_contract_signature_change",
                    "severity": severity,
                    "file_path": path,
                    "change_type": "signature_change",
                    "symbol": old_entry.get("name"),
                    "symbol_kind": kind,
                    "description": f"Changed signature for {kind} '{old_entry.get('name')}'",
                    "old_signature": old_sig,
                    "new_signature": new_sig,
                }
            )

        if not findings and path_hint and old_contract and not new_contract:
            findings.append(
                {
                    "category": "api_contract_surface_loss",
                    "severity": "high",
                    "file_path": path,
                    "change_type": "surface_loss",
                    "description": "Public/API contract surface was removed from this file",
                    "old_signature": None,
                    "new_signature": None,
                }
            )
        return findings

    async def _arun(
        self,
        directory_path: str = ".",
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            extensions=extensions,
        )


class TraceDownstreamDependenciesInput(BaseModel):
    """Input schema for TraceDownstreamDependenciesTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Changed file paths relative to directory_path; auto-detected when omitted",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_depth: int = Field(
        default=5,
        ge=1,
        le=12,
        description="Max traversal depth through reverse call graph",
    )
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved/external edges when building dependency graph",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter for analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Optional base git ref for auto-detecting changed files",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Optional target git ref for auto-detecting changed files",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when auto-detecting changes",
    )


class TraceDownstreamDependenciesTool(BaseTool):
    """Trace downstream dependents through a reverse call graph."""

    name: str = "trace_downstream_dependencies"
    description: str = """
    Trace downstream dependencies from changed files through a reverse call graph.
    Uses import dependency graph + function call inference to identify transitive impact.
    """
    args_schema: Type[BaseModel] = TraceDownstreamDependenciesInput

    _FUNCTION_KEYWORDS: Set[str] = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "new",
        "await",
        "sizeof",
        "typeof",
        "instanceof",
        "print",
        "println",
    }
    _SUPPORTED_FUNCTION_LANGUAGES: Set[str] = {
        "python",
        "javascript",
        "typescript",
        "java",
        "go",
        "rust",
        "csharp",
        "php",
        "ruby",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._graph = BuildDependencyGraphTool(base_path=self._base_path)
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        recursive: bool = True,
        max_depth: int = 5,
        include_external_dependencies: bool = False,
        extensions: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
    ) -> Dict[str, Any]:
        try:
            graph_result = self._graph._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external=include_external_dependencies,
                extensions=extensions,
            )
            if graph_result.get("status") != "success":
                return graph_result

            root_path = Path(str(graph_result.get("root_path", ""))).resolve()
            nodes = graph_result.get("nodes", [])
            known_nodes = {str(node.get("path", "")).replace("\\", "/") for node in nodes}

            auto_change_result: Optional[Dict[str, Any]] = None
            if changed_files is None:
                auto_change_result = self._impact._run(
                    directory_path=directory_path,
                    base_ref=base_ref,
                    target_ref=target_ref,
                    include_untracked=include_untracked,
                    extensions=extensions,
                )
                if auto_change_result.get("status") != "success":
                    return {
                        "status": "error",
                        "error": "Unable to auto-detect changed files",
                        "details": auto_change_result.get("error", "unknown error"),
                    }
                classes = auto_change_result.get("classifications", {})
                changed_files = sorted(
                    {
                        str(path)
                        for key in ("create", "modify", "delete")
                        for path in classes.get(key, [])
                    }
                )

            changed_files = changed_files or []
            normalized_changes, unresolved_changes = self._normalize_changed_files(
                changed_files=changed_files,
                root_path=root_path,
                known_nodes=known_nodes,
                scope_pathspec=(
                    str(auto_change_result.get("scope_pathspec"))
                    if auto_change_result and auto_change_result.get("scope_pathspec")
                    else None
                ),
            )

            if not normalized_changes:
                return {
                    "status": "success",
                    "directory_path": directory_path,
                    "changed_files": [],
                    "unresolved_changed_files": unresolved_changes,
                    "downstream_traces": [],
                    "aggregate_impacted_files": [],
                    "summary": {
                        "seed_file_count": 0,
                        "resolved_seed_file_count": 0,
                        "unresolved_seed_file_count": len(unresolved_changes),
                        "impacted_file_count": 0,
                        "max_depth": max_depth,
                    },
                }

            call_graph = self._build_call_graph(
                root_path=root_path,
                nodes=nodes,
                edges=graph_result.get("edges", []),
            )
            reverse_adjacency = self._build_reverse_adjacency(call_graph.get("edges", []))

            downstream_traces: List[Dict[str, Any]] = []
            aggregate_impacted: Set[str] = set()
            for seed in normalized_changes:
                trace = self._trace_from_seed(
                    seed=seed,
                    reverse_adjacency=reverse_adjacency,
                    max_depth=max_depth,
                )
                impacted_files = [item["path"] for item in trace]
                aggregate_impacted.update(impacted_files)
                downstream_traces.append(
                    {
                        "source_file": seed,
                        "impacted_files": trace,
                        "impacted_count": len(impacted_files),
                    }
                )

            direct_downstream = {
                target: sorted({edge["source"] for edge in reverse_adjacency.get(target, [])})
                for target in sorted(reverse_adjacency.keys())
            }

            return {
                "status": "success",
                "directory_path": directory_path,
                "changed_files": normalized_changes,
                "unresolved_changed_files": unresolved_changes,
                "downstream_traces": downstream_traces,
                "aggregate_impacted_files": sorted(aggregate_impacted),
                "direct_downstream_dependencies": direct_downstream,
                "call_graph": call_graph,
                "summary": {
                    "seed_file_count": len(changed_files),
                    "resolved_seed_file_count": len(normalized_changes),
                    "unresolved_seed_file_count": len(unresolved_changes),
                    "impacted_file_count": len(aggregate_impacted),
                    "max_depth": max_depth,
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _analyze_file_impact(
        self,
        repo_root: Path,
        entry: Dict[str, Any],
        mode: str,
        old_ref: str,
        target_ref: Optional[str],
    ) -> List[Dict[str, Any]]:
        path = str(entry.get("path", "")).replace("\\", "/").strip()
        if not path:
            return []

        impact = str(entry.get("impact", "modify")).strip().lower()
        old_path = entry.get("old_path")
        if isinstance(old_path, str):
            old_path = old_path.replace("\\", "/").strip()
        else:
            old_path = None

        language = self._infer_language(path)
        old_content = self._load_old_content(repo_root, old_ref, old_path or path)
        new_content = self._load_new_content(repo_root, path, mode, target_ref)
        old_contract = self._extract_contract_surface(old_content, language, old_path or path)
        new_contract = self._extract_contract_surface(new_content, language, path)

        path_hint = self._is_api_contract_path(path) or (old_path and self._is_api_contract_path(old_path))
        if impact == "delete":
            return self._deleted_file_findings(path=path, contract=old_contract, path_hint=bool(path_hint))
        if impact == "create":
            return []

        findings: List[Dict[str, Any]] = []
        if old_path and old_path != path and path_hint:
            findings.append(
                {
                    "category": "api_contract_path_change",
                    "severity": "medium",
                    "file_path": path,
                    "old_path": old_path,
                    "change_type": "path_rename",
                    "description": f"Public/API contract file moved from '{old_path}' to '{path}'",
                }
            )
        findings.extend(
            self._compare_contracts(
                path=path,
                old_contract=old_contract,
                new_contract=new_contract,
                path_hint=bool(path_hint),
            )
        )
        return findings

    def _infer_language(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        fallback_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".java": "java",
            ".go": "go",
            ".cs": "csharp",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".graphql": "graphql",
            ".gql": "graphql",
            ".proto": "proto",
        }
        if ext in fallback_map:
            return fallback_map[ext]
        return "unknown"

    def _load_old_content(self, repo_root: Path, old_ref: str, path: str) -> Optional[str]:
        if not path:
            return None
        return self._git_show(repo_root, old_ref, path)

    def _load_new_content(
        self,
        repo_root: Path,
        path: str,
        mode: str,
        target_ref: Optional[str],
    ) -> Optional[str]:
        if target_ref:
            return self._git_show(repo_root, target_ref, path)
        abs_path = (repo_root / path).resolve()
        if abs_path.exists() and abs_path.is_file():
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                return file_obj.read()
        if mode == "ref_diff":
            return None
        return None

    def _git_show(self, repo_root: Path, ref: str, path: str) -> Optional[str]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{ref}:{path}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return completed.stdout
        except subprocess.CalledProcessError:
            return None

    def _is_api_contract_path(self, path: str) -> bool:
        lower = path.replace("\\", "/").lower()
        ext = Path(lower).suffix.lower()
        if ext in self._CONTRACT_EXTENSIONS:
            return True
        parts = [part for part in lower.split("/") if part]
        return any(part in self._API_PATH_HINTS for part in parts)

    def _extract_contract_surface(
        self,
        content: Optional[str],
        language: str,
        path: str,
    ) -> Dict[str, Dict[str, Any]]:
        if not content:
            return {}

        ext = Path(path).suffix.lower()
        if ext == ".json":
            return self._extract_json_contracts(content)
        if ext in {".yaml", ".yml"}:
            return self._extract_yaml_contracts(content)

        if language == "python":
            return self._extract_python_contracts(content)
        if language in {"javascript", "typescript"}:
            return self._extract_js_ts_contracts(content, language)
        if language == "java":
            return self._extract_java_contracts(content)
        if language == "go":
            return self._extract_go_contracts(content)
        if language == "csharp":
            return self._extract_csharp_contracts(content)
        if language == "rust":
            return self._extract_rust_contracts(content)
        if language == "php":
            return self._extract_php_contracts(content)
        if language == "ruby":
            return self._extract_ruby_contracts(content)
        return {}

    def _extract_python_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:",
            content,
        ):
            name = match.group(1)
            if name.startswith("_"):
                continue
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            returns = (match.group(3) or "Any").strip()
            key = f"function:{name}"
            contracts[key] = {
                "kind": "function",
                "name": name,
                "signature": f"({params}) -> {returns}",
            }

        for match in re.finditer(r"(?m)^\s*class\s+([A-Za-z_]\w*)(?:\(([^)]*)\))?\s*:", content):
            name = match.group(1)
            if name.startswith("_"):
                continue
            base = (match.group(2) or "").strip()
            key = f"class:{name}"
            contracts[key] = {
                "kind": "class",
                "name": name,
                "signature": f"class {name}({base})" if base else f"class {name}",
            }

        for match in re.finditer(r"(?m)^\s*@\s*[A-Za-z_][\w.]*\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]", content):
            method = match.group(1).upper()
            route = match.group(2)
            key = f"endpoint:{method}:{route}"
            contracts[key] = {
                "kind": "endpoint",
                "name": f"{method} {route}",
                "signature": f"{method} {route}",
            }

        for match in re.finditer(
            r"(?m)^\s*@\s*[A-Za-z_][\w.]*\s*\.route\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?",
            content,
        ):
            route = match.group(1)
            methods_raw = (match.group(2) or "'GET'")
            method_tokens = re.findall(r"['\"]([A-Za-z]+)['\"]", methods_raw)
            methods = [m.upper() for m in method_tokens] or ["GET"]
            for method in methods:
                key = f"endpoint:{method}:{route}"
                contracts[key] = {
                    "kind": "endpoint",
                    "name": f"{method} {route}",
                    "signature": f"{method} {route}",
                }
        return contracts

    def _extract_js_ts_contracts(self, content: str, language: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*export\s+(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {
                "kind": "function",
                "name": name,
                "signature": f"({params})",
            }

        for match in re.finditer(
            r"(?m)^\s*export\s+(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {
                "kind": "function",
                "name": name,
                "signature": f"({params})",
            }

        for match in re.finditer(r"(?m)^\s*export\s+class\s+([A-Za-z_]\w*)(?:\s+extends\s+([A-Za-z_]\w*))?", content):
            name = match.group(1)
            base = (match.group(2) or "").strip()
            key = f"class:{name}"
            contracts[key] = {
                "kind": "class",
                "name": name,
                "signature": f"class {name} extends {base}" if base else f"class {name}",
            }

        if language == "typescript":
            for match in re.finditer(r"(?m)^\s*export\s+interface\s+([A-Za-z_]\w*)", content):
                name = match.group(1)
                key = f"interface:{name}"
                contracts[key] = {"kind": "interface", "name": name, "signature": f"interface {name}"}
            for match in re.finditer(r"(?m)^\s*export\s+type\s+([A-Za-z_]\w*)\s*=\s*([^;]+);?", content):
                name = match.group(1)
                rhs = re.sub(r"\s+", " ", (match.group(2) or "").strip())
                key = f"type:{name}"
                contracts[key] = {"kind": "type", "name": name, "signature": rhs}

        for match in re.finditer(
            r"(?m)\b(?:app|router)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
            content,
        ):
            method = match.group(1).upper()
            route = match.group(2)
            key = f"endpoint:{method}:{route}"
            contracts[key] = {
                "kind": "endpoint",
                "name": f"{method} {route}",
                "signature": f"{method} {route}",
            }
        return contracts

    def _extract_java_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "method", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*public\s+(?:abstract\s+)?(?:class|interface)\s+([A-Za-z_]\w*)", content):
            name = match.group(1)
            kind = "interface" if "interface" in match.group(0) else "class"
            key = f"{kind}:{name}"
            contracts[key] = {"kind": kind, "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_go_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*func\s+(?:\([^)]+\)\s*)?([A-Z][A-Za-z0-9_]*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*type\s+([A-Z][A-Za-z0-9_]*)\s+(?:struct|interface)", content):
            name = match.group(1)
            key = f"type:{name}"
            contracts[key] = {"kind": "type", "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_csharp_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+(?:static\s+|virtual\s+|override\s+|async\s+)*[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"method:{name}"
            contracts[key] = {"kind": "method", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*public\s+(?:class|interface)\s+([A-Za-z_]\w*)", content):
            name = match.group(1)
            kind = "interface" if "interface" in match.group(0) else "class"
            key = f"{kind}:{name}"
            contracts[key] = {"kind": kind, "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_rust_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*pub\s+(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", content):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*pub\s+(?:struct|enum|trait)\s+([A-Za-z_]\w*)", content):
            name = match.group(1)
            key = f"type:{name}"
            contracts[key] = {"kind": "type", "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_php_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(
            r"(?m)^\s*public\s+function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)",
            content,
        ):
            name = match.group(1)
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*(?:final\s+|abstract\s+)?class\s+([A-Za-z_]\w*)", content):
            name = match.group(1)
            key = f"class:{name}"
            contracts[key] = {"kind": "class", "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_ruby_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for match in re.finditer(r"(?m)^\s*def\s+([A-Za-z_]\w*[!?=]?)\s*(?:\(([^)]*)\))?", content):
            name = match.group(1)
            if name.startswith("_"):
                continue
            params = re.sub(r"\s+", " ", (match.group(2) or "").strip())
            key = f"function:{name}"
            contracts[key] = {"kind": "function", "name": name, "signature": f"({params})"}
        for match in re.finditer(r"(?m)^\s*(?:class|module)\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", content):
            name = match.group(1)
            key = f"type:{name}"
            contracts[key] = {"kind": "type", "name": name, "signature": match.group(0).strip()}
        return contracts

    def _extract_json_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        try:
            payload = json.loads(content)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        contracts: Dict[str, Dict[str, Any]] = {}
        for key, value in payload.items():
            key_name = str(key)
            contracts[f"schema:{key_name}"] = {
                "kind": "schema_key",
                "name": key_name,
                "signature": type(value).__name__,
            }
        return contracts

    def _extract_yaml_contracts(self, content: str) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for line in content.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith(" ") or line.startswith("\t"):
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
            if not match:
                continue
            key_name = match.group(1).strip()
            raw_val = match.group(2).strip()
            value_type = "scalar" if raw_val else "object"
            contracts[f"schema:{key_name}"] = {
                "kind": "schema_key",
                "name": key_name,
                "signature": value_type,
            }
        return contracts

    def _deleted_file_findings(
        self,
        path: str,
        contract: Dict[str, Dict[str, Any]],
        path_hint: bool,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        if contract:
            for old_entry in contract.values():
                kind = str(old_entry.get("kind", "contract"))
                severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
                findings.append(
                    {
                        "category": "api_contract_removal",
                        "severity": severity,
                        "file_path": path,
                        "change_type": "removed_symbol",
                        "symbol": old_entry.get("name"),
                        "symbol_kind": kind,
                        "description": f"Removed {kind} '{old_entry.get('name')}' due to file deletion",
                        "old_signature": old_entry.get("signature"),
                        "new_signature": None,
                    }
                )
        elif path_hint:
            findings.append(
                {
                    "category": "api_contract_removal",
                    "severity": "high",
                    "file_path": path,
                    "change_type": "deleted_api_contract_file",
                    "description": f"Deleted API/contract-oriented file '{path}'",
                    "old_signature": None,
                    "new_signature": None,
                }
            )
        return findings

    def _compare_contracts(
        self,
        path: str,
        old_contract: Dict[str, Dict[str, Any]],
        new_contract: Dict[str, Dict[str, Any]],
        path_hint: bool,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        old_keys = set(old_contract.keys())
        new_keys = set(new_contract.keys())

        for key in sorted(old_keys - new_keys):
            old_entry = old_contract[key]
            kind = str(old_entry.get("kind", "contract"))
            severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
            findings.append(
                {
                    "category": "api_contract_removal",
                    "severity": severity,
                    "file_path": path,
                    "change_type": "removed_symbol",
                    "symbol": old_entry.get("name"),
                    "symbol_kind": kind,
                    "description": f"Removed {kind} '{old_entry.get('name')}' from public surface",
                    "old_signature": old_entry.get("signature"),
                    "new_signature": None,
                }
            )

        for key in sorted(old_keys & new_keys):
            old_entry = old_contract[key]
            new_entry = new_contract[key]
            old_sig = str(old_entry.get("signature", "")).strip()
            new_sig = str(new_entry.get("signature", "")).strip()
            if old_sig == new_sig:
                continue
            kind = str(old_entry.get("kind", "contract"))
            severity = "high" if kind in {"endpoint", "interface", "schema_key"} else "medium"
            findings.append(
                {
                    "category": "api_contract_signature_change",
                    "severity": severity,
                    "file_path": path,
                    "change_type": "signature_change",
                    "symbol": old_entry.get("name"),
                    "symbol_kind": kind,
                    "description": f"Changed signature for {kind} '{old_entry.get('name')}'",
                    "old_signature": old_sig,
                    "new_signature": new_sig,
                }
            )

        if not findings and path_hint and old_contract and not new_contract:
            findings.append(
                {
                    "category": "api_contract_surface_loss",
                    "severity": "high",
                    "file_path": path,
                    "change_type": "surface_loss",
                    "description": "Public/API contract surface was removed from this file",
                    "old_signature": None,
                    "new_signature": None,
                }
            )
        return findings

    def _dedupe_findings(self, findings: List[Dict[str, Any]], max_findings: int) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: Set[tuple[str, str, str, str]] = set()
        for item in findings:
            key = (
                str(item.get("file_path", "")),
                str(item.get("category", "")),
                str(item.get("change_type", "")),
                str(item.get("symbol", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= max_findings:
                break

        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        deduped.sort(
            key=lambda entry: (
                severity_rank.get(str(entry.get("severity", "low")), 9),
                str(entry.get("file_path", "")),
                str(entry.get("symbol", "")),
            )
        )
        return deduped

    def _severity_counts(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in findings:
            severity = str(finding.get("severity", "low"))
            if severity in counts:
                counts[severity] += 1
        return counts

    def _risk_level(self, counts: Dict[str, int]) -> str:
        critical = int(counts.get("critical", 0))
        high = int(counts.get("high", 0))
        medium = int(counts.get("medium", 0))
        if critical > 0 or high >= 6:
            return "critical"
        if high > 0 or medium >= 6:
            return "high"
        if medium > 0:
            return "medium"
        return "low"

    def _risk_factors(
        self,
        findings: List[Dict[str, Any]],
        counts: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        factors: List[Dict[str, Any]] = []
        if counts.get("critical", 0):
            factors.append(
                {
                    "factor": "critical_breaking_changes",
                    "severity": "critical",
                    "evidence": f"{counts['critical']} critical breaking-change finding(s)",
                }
            )
        if counts.get("high", 0):
            factors.append(
                {
                    "factor": "high_breaking_changes",
                    "severity": "high",
                    "evidence": f"{counts['high']} high-severity API/contract finding(s)",
                }
            )
        endpoint_changes = [f for f in findings if str(f.get("symbol_kind", "")) == "endpoint"]
        if endpoint_changes:
            factors.append(
                {
                    "factor": "endpoint_contract_changes",
                    "severity": "high",
                    "evidence": f"{len(endpoint_changes)} endpoint contract change(s)",
                }
            )
        schema_changes = [f for f in findings if str(f.get("symbol_kind", "")) == "schema_key"]
        if schema_changes:
            factors.append(
                {
                    "factor": "schema_contract_changes",
                    "severity": "high",
                    "evidence": f"{len(schema_changes)} schema contract key change(s)",
                }
            )
        if not factors:
            factors.append(
                {
                    "factor": "no_breaking_changes_detected",
                    "severity": "low",
                    "evidence": "No API or contract-breaking changes detected",
                }
            )
        return factors

    def _normalize_changed_files(
        self,
        changed_files: List[str],
        root_path: Path,
        known_nodes: Set[str],
        scope_pathspec: Optional[str],
    ) -> tuple[List[str], List[str]]:
        normalized: List[str] = []
        unresolved: List[str] = []
        seen: Set[str] = set()
        normalized_scope = ""
        if scope_pathspec and scope_pathspec not in {"", "."}:
            normalized_scope = scope_pathspec.replace("\\", "/").strip("/")

        for raw in changed_files:
            candidate = str(raw or "").strip().replace("\\", "/")
            if not candidate:
                continue

            resolved = self._resolve_changed_file(
                candidate=candidate,
                root_path=root_path,
                known_nodes=known_nodes,
                normalized_scope=normalized_scope,
            )
            if resolved:
                if resolved not in seen:
                    seen.add(resolved)
                    normalized.append(resolved)
            else:
                unresolved.append(candidate)

        return sorted(normalized), sorted(set(unresolved))

    def _resolve_changed_file(
        self,
        candidate: str,
        root_path: Path,
        known_nodes: Set[str],
        normalized_scope: str,
    ) -> Optional[str]:
        raw_candidate = candidate.lstrip("./")
        candidates = [raw_candidate]
        if normalized_scope and raw_candidate.startswith(f"{normalized_scope}/"):
            candidates.append(raw_candidate[len(normalized_scope) + 1 :])
        if normalized_scope and not raw_candidate.startswith(f"{normalized_scope}/"):
            candidates.append(f"{normalized_scope}/{raw_candidate}")

        for item in candidates:
            normalized = item.replace("\\", "/").strip("/")
            if normalized in known_nodes:
                return normalized

        path = Path(candidate)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(root_path).as_posix()
            except Exception:
                rel = None
            if rel and rel in known_nodes:
                return rel
        else:
            abs_candidate = (root_path / raw_candidate).resolve()
            try:
                rel = abs_candidate.relative_to(root_path).as_posix()
            except Exception:
                rel = None
            if rel and rel in known_nodes:
                return rel

        suffix = raw_candidate.strip("/")
        matches = [
            node
            for node in known_nodes
            if node == suffix or node.endswith(f"/{suffix}")
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _build_call_graph(
        self,
        root_path: Path,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        function_names_by_file: Dict[str, Set[str]] = {}
        call_tokens_by_file: Dict[str, Set[str]] = {}

        for node in nodes:
            rel_path = str(node.get("path", "")).replace("\\", "/")
            language = str(node.get("language", "unknown")).strip().lower()
            if not rel_path:
                continue

            abs_path = (root_path / rel_path).resolve()
            if not abs_path.exists() or not abs_path.is_file():
                continue
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()

            if language in self._SUPPORTED_FUNCTION_LANGUAGES:
                function_names_by_file[rel_path] = self._extract_function_names(content, language)
            else:
                function_names_by_file[rel_path] = set()
            call_tokens_by_file[rel_path] = self._extract_call_tokens(content)

        edge_map: Dict[tuple[str, str], Dict[str, Any]] = {}
        for edge in edges:
            if edge.get("is_external"):
                continue
            source = str(edge.get("source", "")).replace("\\", "/")
            target = str(edge.get("target", "")).replace("\\", "/")
            if not source or not target:
                continue

            key = (source, target)
            bucket = edge_map.setdefault(
                key,
                {
                    "source": source,
                    "target": target,
                    "edge_kind": "import_reference",
                    "import_types": set(),
                    "line_numbers": set(),
                    "called_symbols": set(),
                    "call_signal_count": 0,
                },
            )

            import_type = edge.get("import_type")
            if import_type:
                bucket["import_types"].add(str(import_type))
            line_number = edge.get("line_number")
            if isinstance(line_number, int):
                bucket["line_numbers"].add(line_number)

        for bucket in edge_map.values():
            source = bucket["source"]
            target = bucket["target"]
            target_functions = function_names_by_file.get(target, set())
            source_calls = call_tokens_by_file.get(source, set())
            called_symbols = source_calls & target_functions
            if called_symbols:
                bucket["edge_kind"] = "call"
                bucket["called_symbols"] = set(sorted(called_symbols))
                bucket["call_signal_count"] = len(called_symbols)

        compact_edges = []
        call_edge_count = 0
        for bucket in edge_map.values():
            if bucket["edge_kind"] == "call":
                call_edge_count += 1
            compact_edges.append(
                {
                    "source": bucket["source"],
                    "target": bucket["target"],
                    "edge_kind": bucket["edge_kind"],
                    "call_signal_count": bucket["call_signal_count"],
                    "called_symbols": sorted(bucket["called_symbols"])[:20],
                    "import_types": sorted(bucket["import_types"]),
                    "line_numbers": sorted(bucket["line_numbers"])[:25],
                }
            )

        compact_edges.sort(key=lambda item: (item["source"], item["target"]))
        return {
            "node_count": len(nodes),
            "edge_count": len(compact_edges),
            "call_edge_count": call_edge_count,
            "import_only_edge_count": len(compact_edges) - call_edge_count,
            "edges": compact_edges,
        }

    def _extract_function_names(self, content: str, language: str) -> Set[str]:
        patterns = {
            "python": r"^\s*def\s+([A-Za-z_]\w*)\s*\(",
            "javascript": r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(",
            "typescript": r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(",
            "java": r"^\s*(?:public|private|protected|static|\s)+[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(",
            "go": r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_]\w*)\s*\(",
            "rust": r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(",
            "csharp": r"^\s*(?:public|private|protected|internal|static|virtual|override|async|\s)+[\w<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\(",
            "php": r"^\s*(?:public|private|protected|static|\s)*function\s+([A-Za-z_]\w*)\s*\(",
            "ruby": r"^\s*def\s+([A-Za-z_]\w*[!?=]?)",
        }
        pattern = patterns.get(language)
        if not pattern:
            return set()

        result: Set[str] = set()
        for line in content.splitlines():
            match = re.match(pattern, line)
            if match:
                result.add(match.group(1))
        return result

    def _extract_call_tokens(self, content: str) -> Set[str]:
        tokens: Set[str] = set()
        for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", content):
            token = match.group(1)
            if token not in self._FUNCTION_KEYWORDS:
                tokens.add(token)
        for match in re.finditer(r"\.\s*([A-Za-z_]\w*)\s*\(", content):
            token = match.group(1)
            if token not in self._FUNCTION_KEYWORDS:
                tokens.add(token)
        return tokens

    def _build_reverse_adjacency(
        self,
        edges: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        reverse: Dict[str, List[Dict[str, Any]]] = {}
        for edge in edges:
            target = str(edge.get("target", "")).replace("\\", "/")
            source = str(edge.get("source", "")).replace("\\", "/")
            if not source or not target:
                continue
            reverse.setdefault(target, []).append(edge)
        for target in reverse:
            reverse[target] = sorted(reverse[target], key=lambda item: item.get("source", ""))
        return reverse

    def _trace_from_seed(
        self,
        seed: str,
        reverse_adjacency: Dict[str, List[Dict[str, Any]]],
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        frontier: List[str] = [seed]
        best_depth: Dict[str, int] = {seed: 0}
        traces: Dict[str, Dict[str, Any]] = {}

        for depth in range(1, max_depth + 1):
            if not frontier:
                break
            next_frontier: List[str] = []
            for current in frontier:
                for edge in reverse_adjacency.get(current, []):
                    dependent = str(edge.get("source", "")).replace("\\", "/")
                    if not dependent or dependent == seed:
                        continue

                    prev_depth = best_depth.get(dependent)
                    if prev_depth is not None and prev_depth < depth:
                        continue
                    best_depth[dependent] = depth

                    trace_entry = {
                        "path": dependent,
                        "depth": depth,
                        "via_path": current,
                        "edge_kind": edge.get("edge_kind", "import_reference"),
                        "called_symbols": edge.get("called_symbols", []),
                    }
                    existing = traces.get(dependent)
                    if existing is None:
                        traces[dependent] = trace_entry
                    else:
                        if depth < int(existing.get("depth", depth + 1)):
                            traces[dependent] = trace_entry
                        elif depth == int(existing.get("depth", depth)) and trace_entry["edge_kind"] == "call":
                            traces[dependent] = trace_entry

                    if prev_depth is None or depth < prev_depth:
                        next_frontier.append(dependent)

            frontier = sorted(set(next_frontier))

        return sorted(
            traces.values(),
            key=lambda item: (int(item.get("depth", 0)), str(item.get("path", ""))),
        )

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        recursive: bool = True,
        max_depth: int = 5,
        include_external_dependencies: bool = False,
        extensions: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            recursive=recursive,
            max_depth=max_depth,
            include_external_dependencies=include_external_dependencies,
            extensions=extensions,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
        )

class DetectBreakingChangesInput(BaseModel):
    """Input schema for DetectBreakingChangesTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    max_findings: int = Field(
        default=200,
        ge=10,
        le=1000,
        description="Maximum number of breaking-change findings to return",
    )


class DetectBreakingChangesTool(TraceDownstreamDependenciesTool):
    """Detect potential breaking changes for APIs and contracts."""

    name: str = "detect_breaking_changes"
    description: str = """
    Detect potential breaking changes for APIs/contracts by diffing public surface.
    Reports removals, signature changes, endpoint removals, and schema key removals.
    """
    args_schema: Type[BaseModel] = DetectBreakingChangesInput

    _API_PATH_HINTS: Set[str] = {
        "api",
        "apis",
        "route",
        "routes",
        "controller",
        "controllers",
        "endpoint",
        "endpoints",
        "contract",
        "contracts",
        "schema",
        "schemas",
        "openapi",
        "swagger",
        "graphql",
        "proto",
        "public",
        "interface",
        "interfaces",
        "dto",
    }
    _CONTRACT_EXTENSIONS: Set[str] = {
        ".proto",
        ".graphql",
        ".gql",
        ".json",
        ".yaml",
        ".yml",
        ".avsc",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
        max_findings: int = 200,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            repo_root = Path(str(impact_result.get("repo_root", ""))).resolve()
            if not repo_root.exists():
                return {"status": "error", "error": "Unable to resolve repository root"}

            selected_paths = {str(path).replace("\\", "/").strip() for path in (changed_files or []) if str(path).strip()}
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [item for item in file_impacts if str(item.get("path", "")).replace("\\", "/") in selected_paths]

            findings: List[Dict[str, Any]] = []
            mode = str(impact_result.get("mode", "working_tree"))
            old_ref = base_ref or "HEAD"

            for entry in file_impacts:
                if len(findings) >= max_findings:
                    break
                findings.extend(
                    self._analyze_file_impact(
                        repo_root=repo_root,
                        entry=entry,
                        mode=mode,
                        old_ref=old_ref,
                        target_ref=target_ref,
                    )
                )

            deduped = self._dedupe_findings(findings, max_findings=max_findings)
            severity_counts = self._severity_counts(deduped)
            risk_factors = self._risk_factors(deduped, severity_counts)
            if deduped and all(str(item.get("factor")) == "no_breaking_changes_detected" for item in risk_factors):
                risk_factors = [
                    {
                        "factor": "breaking_changes_detected",
                        "severity": self._risk_level(severity_counts),
                        "evidence": f"{len(deduped)} breaking-change finding(s) detected",
                    }
                ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
                "mode": mode,
                "analyzed_files": [str(item.get("path", "")) for item in file_impacts],
                "breaking_changes": deduped,
                "risk_level": self._risk_level(severity_counts),
                "risk_factors": risk_factors,
                "summary": {
                    "analyzed_files": len(file_impacts),
                    "breaking_change_count": len(deduped),
                    "critical_count": severity_counts.get("critical", 0),
                    "high_count": severity_counts.get("high", 0),
                    "medium_count": severity_counts.get("medium", 0),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
        max_findings: int = 200,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            extensions=extensions,
            max_findings=max_findings,
        )


class AnalyzeTypeSystemChangesInput(BaseModel):
    """Input schema for AnalyzeTypeSystemChangesTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    max_findings: int = Field(
        default=250,
        ge=10,
        le=2000,
        description="Maximum number of type-safety findings to return",
    )


class AnalyzeTypeSystemChangesTool(BaseTool):
    """Analyze type system changes and assess type-safety impact."""

    name: str = "analyze_type_system_changes"
    description: str = """
    Analyze type-system changes between revisions for type safety.
    Detects removed/changed type definitions, function signatures, typed symbols, and unsafe typing drift.
    """
    args_schema: Type[BaseModel] = AnalyzeTypeSystemChangesInput

    _LANGUAGE_BY_EXTENSION: Dict[str, str] = {
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".java": "java",
        ".go": "go",
        ".cs": "csharp",
    }
    _UNSAFE_TYPE_MARKERS: Set[str] = {"any", "unknown", "dynamic", "object"}

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._type = TypeAwareAnalysisTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
        max_findings: int = 250,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            repo_root = Path(str(impact_result.get("repo_root", ""))).resolve()
            if not repo_root.exists():
                return {"status": "error", "error": "Unable to resolve repository root"}

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            findings: List[Dict[str, Any]] = []
            per_file_reports: List[Dict[str, Any]] = []
            skipped_files: List[Dict[str, Any]] = []
            old_ref = base_ref or "HEAD"

            for entry in file_impacts:
                path = str(entry.get("path", "")).replace("\\", "/").strip()
                if not path:
                    continue
                language = self._infer_language(path)
                if language not in self._type.STATIC_TYPED_LANGUAGES:
                    skipped_files.append(
                        {
                            "path": path,
                            "reason": f"unsupported_language:{language}",
                        }
                    )
                    continue

                impact = str(entry.get("impact", "modify")).strip().lower()
                old_path = entry.get("old_path")
                if isinstance(old_path, str):
                    old_path = old_path.replace("\\", "/").strip()
                else:
                    old_path = None

                old_content = self._load_content(repo_root, old_ref, old_path or path)
                new_content = self._load_content(repo_root, target_ref, path)

                before = self._analyze_content(language, old_content)
                after = self._analyze_content(language, new_content)
                file_findings = self._diff_type_system(
                    path=path,
                    impact=impact,
                    before=before,
                    after=after,
                )
                if file_findings:
                    findings.extend(file_findings)

                per_file_reports.append(
                    {
                        "path": path,
                        "impact": impact,
                        "language": language,
                        "before_summary": before.get("summary", {}),
                        "after_summary": after.get("summary", {}),
                        "finding_count": len(file_findings),
                    }
                )

                if len(findings) >= max_findings:
                    break

            trimmed_findings = self._sort_and_trim_findings(findings, max_findings=max_findings)
            severity_counts = self._severity_counts(trimmed_findings)
            risk_level = self._risk_level(severity_counts)

            return {
                "status": "success",
                "directory_path": directory_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
                "mode": impact_result.get("mode"),
                "type_safety_findings": trimmed_findings,
                "risk_level": risk_level,
                "risk_factors": self._risk_factors(trimmed_findings, severity_counts, skipped_files),
                "analyzed_files": per_file_reports,
                "skipped_files": skipped_files,
                "summary": {
                    "candidate_changed_files": len(file_impacts),
                    "analyzed_file_count": len(per_file_reports),
                    "skipped_file_count": len(skipped_files),
                    "finding_count": len(trimmed_findings),
                    "critical_count": severity_counts.get("critical", 0),
                    "high_count": severity_counts.get("high", 0),
                    "medium_count": severity_counts.get("medium", 0),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _infer_language(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        return self._LANGUAGE_BY_EXTENSION.get(ext, "unknown")

    def _load_content(
        self,
        repo_root: Path,
        ref: Optional[str],
        path: str,
    ) -> Optional[str]:
        if ref:
            try:
                completed = subprocess.run(
                    ["git", "-C", str(repo_root), "show", f"{ref}:{path}"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return completed.stdout
            except subprocess.CalledProcessError:
                return None
        abs_path = (repo_root / path).resolve()
        if abs_path.exists() and abs_path.is_file():
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                return file_obj.read()
        return None

    def _analyze_content(self, language: str, content: Optional[str]) -> Dict[str, Any]:
        if not content:
            return {
                "type_definitions": [],
                "typed_symbols": [],
                "function_signatures": [],
                "generic_usages": [],
                "casts": [],
                "inferred_symbols": [],
                "type_references": [],
                "summary": {
                    "type_definition_count": 0,
                    "typed_symbol_count": 0,
                    "function_signature_count": 0,
                    "generic_usage_count": 0,
                    "cast_count": 0,
                    "inferred_symbol_count": 0,
                    "explicit_type_ratio": 0.0,
                    "unsafe_type_usage_count": 0,
                },
            }

        if language == "typescript":
            analysis = self._type._analyze_typescript(content)
        elif language == "java":
            analysis = self._type._analyze_java(content)
        elif language == "go":
            analysis = self._type._analyze_go(content)
        elif language == "csharp":
            analysis = self._type._analyze_csharp(content)
        else:
            analysis = self._type._empty_analysis()

        explicit_count = len(analysis.get("typed_symbols", []))
        inferred_count = len(analysis.get("inferred_symbols", []))
        explicit_ratio = (
            round(explicit_count / (explicit_count + inferred_count), 3)
            if (explicit_count + inferred_count) > 0
            else 1.0
        )
        unsafe_type_usage = self._count_unsafe_type_usage(analysis)

        return {
            **analysis,
            "summary": {
                "type_definition_count": len(analysis.get("type_definitions", [])),
                "typed_symbol_count": explicit_count,
                "function_signature_count": len(analysis.get("function_signatures", [])),
                "generic_usage_count": len(analysis.get("generic_usages", [])),
                "cast_count": len(analysis.get("casts", [])),
                "inferred_symbol_count": inferred_count,
                "explicit_type_ratio": explicit_ratio,
                "unsafe_type_usage_count": unsafe_type_usage,
            },
        }

    def _count_unsafe_type_usage(self, analysis: Dict[str, Any]) -> int:
        count = 0
        for symbol in analysis.get("typed_symbols", []):
            marker = str(symbol.get("type", "")).lower()
            if any(keyword in marker for keyword in self._UNSAFE_TYPE_MARKERS):
                count += 1
        for fn in analysis.get("function_signatures", []):
            marker = str(fn.get("return_type", "")).lower()
            if any(keyword in marker for keyword in self._UNSAFE_TYPE_MARKERS):
                count += 1
        for ref in analysis.get("type_references", []):
            marker = str(ref).lower()
            if any(keyword in marker for keyword in self._UNSAFE_TYPE_MARKERS):
                count += 1
        return count

    def _diff_type_system(
        self,
        path: str,
        impact: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        before_summary = before.get("summary", {})
        after_summary = after.get("summary", {})

        before_defs = {f"{item.get('kind')}:{item.get('name')}" for item in before.get("type_definitions", [])}
        after_defs = {f"{item.get('kind')}:{item.get('name')}" for item in after.get("type_definitions", [])}
        removed_defs = sorted(before_defs - after_defs)

        before_signatures = self._signature_map(before.get("function_signatures", []))
        after_signatures = self._signature_map(after.get("function_signatures", []))

        if impact == "delete":
            if before_summary.get("type_definition_count", 0) or before_summary.get("function_signature_count", 0):
                findings.append(
                    {
                        "category": "type_surface_removed",
                        "severity": "high",
                        "file_path": path,
                        "description": "Deleted file removed typed API/type surface",
                        "before_summary": before_summary,
                        "after_summary": after_summary,
                    }
                )
            return findings

        for removed in removed_defs:
            findings.append(
                {
                    "category": "type_definition_removed",
                    "severity": "high",
                    "file_path": path,
                    "symbol": removed,
                    "description": f"Removed type definition '{removed}'",
                }
            )

        for fn_name, old_signatures in before_signatures.items():
            new_signatures = after_signatures.get(fn_name, set())
            if not new_signatures:
                findings.append(
                    {
                        "category": "typed_function_removed",
                        "severity": "high",
                        "file_path": path,
                        "symbol": fn_name,
                        "description": f"Removed typed function signature for '{fn_name}'",
                    }
                )
                continue
            if old_signatures != new_signatures and (old_signatures - new_signatures):
                findings.append(
                    {
                        "category": "typed_function_signature_changed",
                        "severity": "high",
                        "file_path": path,
                        "symbol": fn_name,
                        "old_signature": sorted(old_signatures),
                        "new_signature": sorted(new_signatures),
                        "description": f"Changed type signature for function '{fn_name}'",
                    }
                )

        before_symbol_map = self._typed_symbol_map(before.get("typed_symbols", []))
        after_symbol_map = self._typed_symbol_map(after.get("typed_symbols", []))
        for symbol_key, old_types in before_symbol_map.items():
            new_types = after_symbol_map.get(symbol_key)
            if new_types is None:
                findings.append(
                    {
                        "category": "typed_symbol_removed",
                        "severity": "medium",
                        "file_path": path,
                        "symbol": symbol_key,
                        "description": f"Removed typed symbol '{symbol_key}'",
                    }
                )
                continue
            if old_types != new_types and (old_types - new_types):
                findings.append(
                    {
                        "category": "typed_symbol_type_changed",
                        "severity": "medium",
                        "file_path": path,
                        "symbol": symbol_key,
                        "old_type": sorted(old_types),
                        "new_type": sorted(new_types),
                        "description": f"Changed declared type for symbol '{symbol_key}'",
                    }
                )

        explicit_ratio_before = float(before_summary.get("explicit_type_ratio", 0.0))
        explicit_ratio_after = float(after_summary.get("explicit_type_ratio", 0.0))
        if explicit_ratio_after + 0.15 < explicit_ratio_before:
            findings.append(
                {
                    "category": "explicit_typing_regression",
                    "severity": "medium",
                    "file_path": path,
                    "description": (
                        "Explicit typing ratio decreased from "
                        f"{explicit_ratio_before:.3f} to {explicit_ratio_after:.3f}"
                    ),
                }
            )

        casts_before = int(before_summary.get("cast_count", 0))
        casts_after = int(after_summary.get("cast_count", 0))
        if casts_after > casts_before + 2:
            findings.append(
                {
                    "category": "cast_usage_increase",
                    "severity": "medium",
                    "file_path": path,
                    "description": f"Type cast usage increased from {casts_before} to {casts_after}",
                }
            )

        unsafe_before = int(before_summary.get("unsafe_type_usage_count", 0))
        unsafe_after = int(after_summary.get("unsafe_type_usage_count", 0))
        if unsafe_after > unsafe_before:
            severity = "high" if unsafe_after - unsafe_before >= 2 else "medium"
            findings.append(
                {
                    "category": "unsafe_type_usage_increase",
                    "severity": severity,
                    "file_path": path,
                    "description": (
                        "Unsafe type marker usage increased from "
                        f"{unsafe_before} to {unsafe_after}"
                    ),
                }
            )

        return findings

    def _signature_map(self, signatures: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        mapping: Dict[str, Set[str]] = {}
        for signature in signatures:
            name = str(signature.get("name", "")).strip()
            if not name:
                continue
            params = signature.get("parameters", [])
            param_types: List[str] = []
            if isinstance(params, list):
                for param in params:
                    if isinstance(param, dict):
                        p_name = str(param.get("name", "")).strip()
                        p_type = str(param.get("type", "")).strip()
                        param_types.append(f"{p_name}:{p_type}")
                    else:
                        param_types.append(str(param))
            return_type = str(signature.get("return_type", "")).strip()
            normalized = f"({','.join(param_types)})->{return_type}"
            mapping.setdefault(name, set()).add(normalized)
        return mapping

    def _typed_symbol_map(self, symbols: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        mapping: Dict[str, Set[str]] = {}
        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            kind = str(symbol.get("kind", "symbol")).strip()
            name = str(symbol.get("name", "")).strip()
            if not name:
                continue
            symbol_type = str(symbol.get("type", "")).strip()
            key = f"{kind}:{name}"
            mapping.setdefault(key, set()).add(symbol_type)
        return mapping

    def _severity_counts(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in findings:
            severity = str(finding.get("severity", "low")).lower()
            if severity in counts:
                counts[severity] += 1
        return counts

    def _risk_level(self, counts: Dict[str, int]) -> str:
        critical = int(counts.get("critical", 0))
        high = int(counts.get("high", 0))
        medium = int(counts.get("medium", 0))
        if critical > 0 or high >= 8:
            return "critical"
        if high > 0 or medium >= 8:
            return "high"
        if medium > 0:
            return "medium"
        return "low"

    def _risk_factors(
        self,
        findings: List[Dict[str, Any]],
        counts: Dict[str, int],
        skipped_files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        factors: List[Dict[str, Any]] = []
        if counts.get("high", 0):
            factors.append(
                {
                    "factor": "high_severity_type_safety_findings",
                    "severity": "high",
                    "evidence": f"{counts['high']} high-severity type-safety finding(s)",
                }
            )
        if counts.get("medium", 0):
            factors.append(
                {
                    "factor": "medium_severity_type_safety_findings",
                    "severity": "medium",
                    "evidence": f"{counts['medium']} medium-severity type-safety finding(s)",
                }
            )
        unsafe_findings = [
            f for f in findings if str(f.get("category")) == "unsafe_type_usage_increase"
        ]
        if unsafe_findings:
            factors.append(
                {
                    "factor": "unsafe_type_usage_growth",
                    "severity": "high",
                    "evidence": f"{len(unsafe_findings)} file(s) increased unsafe type markers",
                }
            )
        if skipped_files:
            factors.append(
                {
                    "factor": "partial_language_coverage",
                    "severity": "low",
                    "evidence": f"Skipped {len(skipped_files)} file(s) with unsupported language",
                }
            )
        if not factors:
            factors.append(
                {
                    "factor": "no_type_safety_risks_detected",
                    "severity": "low",
                    "evidence": "No type-system risks detected in analyzed files",
                }
            )
        return factors

    def _sort_and_trim_findings(
        self,
        findings: List[Dict[str, Any]],
        max_findings: int,
    ) -> List[Dict[str, Any]]:
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        deduped: List[Dict[str, Any]] = []
        seen: Set[tuple[str, str, str]] = set()
        for finding in findings:
            key = (
                str(finding.get("file_path", "")),
                str(finding.get("category", "")),
                str(finding.get("symbol", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)

        deduped.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity", "low")).lower(), 9),
                str(item.get("file_path", "")),
                str(item.get("category", "")),
            )
        )
        return deduped[: max(1, max_findings)]

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        extensions: Optional[List[str]] = None,
        max_findings: int = 250,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            extensions=extensions,
            max_findings=max_findings,
        )


class AssessTestImpactInput(BaseModel):
    """Input schema for AssessTestImpactTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )


class AssessTestImpactTool(BaseTool):
    """Assess test impact scope for regression testing."""

    name: str = "assess_test_impact"
    description: str = """
    Assess test impact for regression testing from changed files.
    Identifies directly changed tests, downstream-impacted tests, and likely missing coverage.
    """
    args_schema: Type[BaseModel] = AssessTestImpactInput

    _TEST_DIR_HINTS: Set[str] = {"test", "tests", "__tests__", "spec", "specs", "e2e", "integration"}
    _TEST_SUFFIXES: tuple[str, ...] = (
        "_test.py",
        "_spec.py",
        ".test.ts",
        ".test.tsx",
        ".spec.ts",
        ".spec.tsx",
        ".test.js",
        ".spec.js",
        ".feature",
    )

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._trace = TraceDownstreamDependenciesTool(base_path=self._base_path)
        self._scan = ScanDirectoryTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            repo_root = Path(str(impact_result.get("repo_root", ""))).resolve()
            if not repo_root.exists():
                return {"status": "error", "error": "Unable to resolve repository root"}

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_path_list = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            directly_changed_tests = sorted(path for path in changed_path_list if self._is_test_file(path))
            changed_source_files = sorted(path for path in changed_path_list if not self._is_test_file(path))

            trace_result: Optional[Dict[str, Any]] = None
            downstream_impacted_files: Set[str] = set()
            downstream_impacted_tests: Set[str] = set()
            source_to_downstream_tests: Dict[str, Set[str]] = {}
            if changed_source_files:
                trace_result = self._trace._run(
                    directory_path=directory_path,
                    changed_files=changed_source_files,
                    recursive=recursive,
                    max_depth=max_downstream_depth,
                    include_external_dependencies=False,
                    extensions=extensions,
                    base_ref=base_ref,
                    target_ref=target_ref,
                    include_untracked=include_untracked,
                )
                if trace_result.get("status") == "success":
                    downstream_impacted_files = {
                        str(path).replace("\\", "/").strip()
                        for path in trace_result.get("aggregate_impacted_files", [])
                        if str(path).strip()
                    }
                    downstream_impacted_tests = {
                        path for path in downstream_impacted_files if self._is_test_file(path)
                    }
                    for trace_item in trace_result.get("downstream_traces", []):
                        source_file = str(trace_item.get("source_file", "")).replace("\\", "/").strip()
                        if not source_file:
                            continue
                        impacted = {
                            str(item.get("path", "")).replace("\\", "/").strip()
                            for item in trace_item.get("impacted_files", [])
                            if isinstance(item, dict) and str(item.get("path", "")).strip()
                        }
                        source_to_downstream_tests[source_file] = {
                            path for path in impacted if self._is_test_file(path)
                        }

            all_test_files = self._collect_all_test_files(
                directory_path=directory_path,
                repo_root=repo_root,
                recursive=recursive,
                extensions=extensions,
            )
            related_tests = self._map_related_tests(
                changed_source_files=changed_source_files,
                all_test_files=all_test_files,
            )

            impacted_tests = set(directly_changed_tests) | downstream_impacted_tests | related_tests
            coverage_gaps = self._coverage_gaps(
                changed_source_files=changed_source_files,
                all_test_files=all_test_files,
                source_to_downstream_tests=source_to_downstream_tests,
            )
            regression_scope = self._regression_scope(impacted_tests, changed_source_files, coverage_gaps)

            summary = {
                "candidate_changed_files": len(changed_path_list),
                "changed_source_file_count": len(changed_source_files),
                "directly_changed_test_count": len(directly_changed_tests),
                "downstream_impacted_test_count": len(downstream_impacted_tests),
                "related_test_count": len(related_tests),
                "total_impacted_test_count": len(impacted_tests),
                "coverage_gap_count": len(coverage_gaps),
                "regression_scope": regression_scope,
            }

            return {
                "status": "success",
                "directory_path": directory_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
                "mode": impact_result.get("mode"),
                "changed_files": changed_path_list,
                "changed_source_files": changed_source_files,
                "directly_changed_tests": directly_changed_tests,
                "downstream_impacted_tests": sorted(downstream_impacted_tests),
                "related_tests": sorted(related_tests),
                "impacted_tests": sorted(impacted_tests),
                "coverage_gaps": coverage_gaps,
                "recommended_test_plan": self._recommended_plan(
                    impacted_tests=impacted_tests,
                    directly_changed_tests=directly_changed_tests,
                    regression_scope=regression_scope,
                ),
                "summary": summary,
                "dependency_trace_summary": (
                    trace_result.get("summary", {}) if trace_result and trace_result.get("status") == "success" else {}
                ),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _is_test_file(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").strip().lower()
        if not normalized:
            return False
        parts = [part for part in normalized.split("/") if part]
        if any(part in self._TEST_DIR_HINTS for part in parts):
            return True
        if any(normalized.endswith(suffix) for suffix in self._TEST_SUFFIXES):
            return True
        stem = Path(normalized).stem
        return stem.startswith("test_") or stem.endswith("_test") or stem.endswith("_spec")

    def _collect_all_test_files(
        self,
        directory_path: str,
        repo_root: Path,
        recursive: bool,
        extensions: Optional[List[str]],
    ) -> Set[str]:
        scan_result = self._scan._run(
            directory_path=directory_path,
            extensions=extensions,
            recursive=recursive,
        )
        if scan_result.get("status") != "success":
            return set()

        tests: Set[str] = set()
        for file_entry in scan_result.get("files", []):
            raw = str(file_entry.get("path", "")).strip()
            if not raw:
                continue
            rel = self._to_relative(raw, repo_root)
            if self._is_test_file(rel):
                tests.add(rel)
        return tests

    def _to_relative(self, path: str, repo_root: Path) -> str:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (repo_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        try:
            return candidate.relative_to(repo_root).as_posix()
        except Exception:
            return candidate.as_posix()

    def _map_related_tests(
        self,
        changed_source_files: List[str],
        all_test_files: Set[str],
    ) -> Set[str]:
        related: Set[str] = set()
        source_keys = {source: self._path_keys(source) for source in changed_source_files}
        for test_file in all_test_files:
            test_keys = self._path_keys(test_file, is_test=True)
            if not test_keys:
                continue
            for source, keys in source_keys.items():
                if not keys:
                    continue
                if keys & test_keys:
                    related.add(test_file)
                    break
                source_stem = Path(source).stem.lower()
                test_stem = Path(test_file).stem.lower()
                if source_stem and source_stem in test_stem:
                    related.add(test_file)
                    break
        return related

    def _path_keys(self, path: str, is_test: bool = False) -> Set[str]:
        normalized = str(path).replace("\\", "/").lower()
        parts = [part for part in normalized.split("/") if part]
        keys: Set[str] = set()
        for part in parts:
            stem = Path(part).stem
            if not stem:
                continue
            stem = stem.replace("-", "_")
            if is_test:
                for token in ["test_", "_test", "_spec", ".test", ".spec"]:
                    stem = stem.replace(token, "")
            for token in re.split(r"[_\W]+", stem):
                cleaned = token.strip()
                if len(cleaned) >= 3 and cleaned not in self._TEST_DIR_HINTS:
                    keys.add(cleaned)
        return keys

    def _coverage_gaps(
        self,
        changed_source_files: List[str],
        all_test_files: Set[str],
        source_to_downstream_tests: Optional[Dict[str, Set[str]]] = None,
    ) -> List[Dict[str, Any]]:
        if not changed_source_files:
            return []
        test_keys_index = {test_file: self._path_keys(test_file, is_test=True) for test_file in all_test_files}
        downstream_map = source_to_downstream_tests or {}
        gaps: List[Dict[str, Any]] = []
        for source in changed_source_files:
            if downstream_map.get(source):
                continue
            source_keys = self._path_keys(source)
            has_related = False
            for test_file, test_keys in test_keys_index.items():
                if source_keys and source_keys & test_keys:
                    has_related = True
                    break
                source_stem = Path(source).stem.lower()
                test_stem = Path(test_file).stem.lower()
                if source_stem and source_stem in test_stem:
                    has_related = True
                    break
            if not has_related:
                gaps.append(
                    {
                        "source_file": source,
                        "reason": "no_related_tests_detected",
                        "recommendation": "Add or update tests covering this changed source file.",
                    }
                )
        return gaps

    def _regression_scope(
        self,
        impacted_tests: Set[str],
        changed_source_files: List[str],
        coverage_gaps: List[Dict[str, Any]],
    ) -> str:
        impacted_count = len(impacted_tests)
        changed_count = len(changed_source_files)
        gap_count = len(coverage_gaps)
        if impacted_count >= 40 or changed_count >= 25:
            return "full_suite"
        if impacted_count >= 10 or changed_count >= 8 or gap_count >= 5:
            return "broad_regression"
        if impacted_count > 0 or changed_count > 0:
            return "targeted_regression"
        return "smoke"

    def _recommended_plan(
        self,
        impacted_tests: Set[str],
        directly_changed_tests: List[str],
        regression_scope: str,
    ) -> Dict[str, Any]:
        plan = {
            "scope": regression_scope,
            "steps": [],
            "recommended_commands": [],
        }
        if directly_changed_tests:
            plan["steps"].append("Run directly changed tests first as a fast safety check.")
        if impacted_tests:
            plan["steps"].append("Run all impacted tests next to validate regression boundaries.")
        if regression_scope in {"broad_regression", "full_suite"}:
            plan["steps"].append("Run broader regression suite before merge.")
        if regression_scope == "full_suite":
            plan["steps"].append("Run full test suite due wide impact.")

        plan["recommended_commands"] = self._suggest_commands(impacted_tests, regression_scope)
        return plan

    def _suggest_commands(self, impacted_tests: Set[str], regression_scope: str) -> List[str]:
        commands: List[str] = []
        impacted = sorted(impacted_tests)
        py_tests = [p for p in impacted if p.endswith(".py")]
        js_tests = [p for p in impacted if p.endswith((".ts", ".tsx", ".js", ".jsx"))]
        go_tests = [p for p in impacted if p.endswith(".go")]
        cs_tests = [p for p in impacted if p.endswith(".cs")]

        if py_tests:
            subset = " ".join(py_tests[:12])
            commands.append(f"pytest {subset}".strip())
        if js_tests:
            subset = " ".join(js_tests[:12])
            commands.append(f"npm test -- {subset}".strip())
        if go_tests:
            commands.append("go test ./...")
        if cs_tests:
            commands.append("dotnet test")

        if regression_scope in {"broad_regression", "full_suite"}:
            commands.append("Run project regression suite")
        if regression_scope == "full_suite":
            commands.append("Run full CI test workflow")

        if not commands:
            commands.append("Run smoke tests")
        return commands

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
        )


class AssessRiskLevelInput(BaseModel):
    """Input schema for AssessRiskLevelTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )


class AssessRiskLevelTool(BaseTool):
    """Assess aggregate change risk level (low/medium/high/critical)."""

    name: str = "assess_risk_level"
    description: str = """
    Assess overall change risk level (low, medium, high, critical).
    Aggregates impact, dependency, breaking-change, type-safety, and test-impact signals.
    """
    args_schema: Type[BaseModel] = AssessRiskLevelInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._trace = TraceDownstreamDependenciesTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._type = AnalyzeTypeSystemChangesTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )

            trace_result = self._trace._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                recursive=recursive,
                max_depth=max_downstream_depth,
                include_external_dependencies=False,
                extensions=extensions,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            type_result = self._type._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )

            risk_factors: List[Dict[str, Any]] = []
            warnings: List[str] = []
            score = 0

            score += self._score_file_impacts(file_impacts, risk_factors)

            if trace_result.get("status") == "success":
                score += self._score_downstream(trace_result, risk_factors)
            else:
                warnings.append(f"downstream_analysis_failed: {trace_result.get('error', 'unknown')}")
                score += 2

            if breaking_result.get("status") == "success":
                score += self._score_breaking_changes(breaking_result, risk_factors)
            else:
                warnings.append(f"breaking_change_analysis_failed: {breaking_result.get('error', 'unknown')}")
                score += 2

            if type_result.get("status") == "success":
                score += self._score_type_changes(type_result, risk_factors)
            else:
                warnings.append(f"type_change_analysis_failed: {type_result.get('error', 'unknown')}")
                score += 2

            if test_result.get("status") == "success":
                score += self._score_test_impact(test_result, risk_factors)
            else:
                warnings.append(f"test_impact_analysis_failed: {test_result.get('error', 'unknown')}")
                score += 2

            risk_level = self._level_from_score(score)
            confidence = self._confidence(trace_result, breaking_result, type_result, test_result)

            response = {
                "status": "success",
                "directory_path": directory_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
                "risk_level": risk_level,
                "risk_score": score,
                "confidence": confidence,
                "risk_factors": sorted(
                    risk_factors,
                    key=lambda item: (-int(item.get("points", 0)), str(item.get("factor", ""))),
                ),
                "summary": {
                    "changed_file_count": len(changed_paths),
                    "create_count": len(impact_result.get("classifications", {}).get("create", [])),
                    "modify_count": len(impact_result.get("classifications", {}).get("modify", [])),
                    "delete_count": len(impact_result.get("classifications", {}).get("delete", [])),
                    "risk_factor_count": len(risk_factors),
                },
                "signals": {
                    "file_impact": {
                        "status": impact_result.get("status"),
                        "summary": impact_result.get("summary", {}),
                    },
                    "downstream": {
                        "status": trace_result.get("status"),
                        "summary": trace_result.get("summary", {}),
                    },
                    "breaking_changes": {
                        "status": breaking_result.get("status"),
                        "risk_level": breaking_result.get("risk_level"),
                        "summary": breaking_result.get("summary", {}),
                    },
                    "type_system": {
                        "status": type_result.get("status"),
                        "risk_level": type_result.get("risk_level"),
                        "summary": type_result.get("summary", {}),
                    },
                    "test_impact": {
                        "status": test_result.get("status"),
                        "summary": test_result.get("summary", {}),
                    },
                },
            }
            if warnings:
                response["warnings"] = warnings
            return response
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _score_file_impacts(
        self,
        file_impacts: List[Dict[str, Any]],
        risk_factors: List[Dict[str, Any]],
    ) -> int:
        score = 0
        total = len(file_impacts)
        deletes = sum(1 for item in file_impacts if str(item.get("impact", "")) == "delete")
        modifies = sum(1 for item in file_impacts if str(item.get("impact", "")) == "modify")
        creates = sum(1 for item in file_impacts if str(item.get("impact", "")) == "create")

        if total >= 25:
            points = 8
            score += points
            risk_factors.append(
                {
                    "factor": "large_change_set",
                    "severity": "high",
                    "points": points,
                    "evidence": f"{total} changed files",
                    "source_tool": "classify_file_impact",
                }
            )
        elif total >= 10:
            points = 4
            score += points
            risk_factors.append(
                {
                    "factor": "moderate_change_set",
                    "severity": "medium",
                    "points": points,
                    "evidence": f"{total} changed files",
                    "source_tool": "classify_file_impact",
                }
            )

        if deletes > 0:
            points = min(10, deletes * 2)
            score += points
            risk_factors.append(
                {
                    "factor": "file_deletions_present",
                    "severity": "high" if deletes >= 2 else "medium",
                    "points": points,
                    "evidence": f"{deletes} deleted file(s)",
                    "source_tool": "classify_file_impact",
                }
            )

        if modifies > 0 and modifies >= 8:
            points = min(6, modifies // 2)
            score += points
            risk_factors.append(
                {
                    "factor": "many_modifications",
                    "severity": "medium",
                    "points": points,
                    "evidence": f"{modifies} modified file(s)",
                    "source_tool": "classify_file_impact",
                }
            )

        if creates > 0 and creates >= 6:
            points = min(4, creates // 3)
            score += points
            risk_factors.append(
                {
                    "factor": "many_new_files",
                    "severity": "low",
                    "points": points,
                    "evidence": f"{creates} created file(s)",
                    "source_tool": "classify_file_impact",
                }
            )
        return score

    def _score_downstream(
        self,
        trace_result: Dict[str, Any],
        risk_factors: List[Dict[str, Any]],
    ) -> int:
        summary = trace_result.get("summary", {})
        impacted = int(summary.get("impacted_file_count", 0))
        unresolved = int(summary.get("unresolved_seed_file_count", 0))
        score = 0

        if impacted >= 20:
            points = 10
            severity = "high"
        elif impacted >= 8:
            points = 6
            severity = "medium"
        elif impacted >= 1:
            points = 2
            severity = "low"
        else:
            points = 0
            severity = "low"

        if points > 0:
            score += points
            risk_factors.append(
                {
                    "factor": "downstream_dependency_impact",
                    "severity": severity,
                    "points": points,
                    "evidence": f"{impacted} downstream impacted file(s)",
                    "source_tool": "trace_downstream_dependencies",
                }
            )

        if unresolved > 0:
            points = min(4, unresolved)
            score += points
            risk_factors.append(
                {
                    "factor": "unresolved_seed_files",
                    "severity": "medium",
                    "points": points,
                    "evidence": f"{unresolved} changed file(s) could not be resolved for tracing",
                    "source_tool": "trace_downstream_dependencies",
                }
            )
        return score

    def _score_breaking_changes(
        self,
        breaking_result: Dict[str, Any],
        risk_factors: List[Dict[str, Any]],
    ) -> int:
        risk = str(breaking_result.get("risk_level", "low")).lower()
        summary = breaking_result.get("summary", {})
        count = int(summary.get("breaking_change_count", 0))
        mapping = {"critical": 14, "high": 10, "medium": 6, "low": 0}
        points = mapping.get(risk, 0)
        if points > 0:
            risk_factors.append(
                {
                    "factor": "breaking_change_risk",
                    "severity": risk,
                    "points": points,
                    "evidence": f"{count} breaking-change finding(s), tool risk={risk}",
                    "source_tool": "detect_breaking_changes",
                }
            )
        return points

    def _score_type_changes(
        self,
        type_result: Dict[str, Any],
        risk_factors: List[Dict[str, Any]],
    ) -> int:
        risk = str(type_result.get("risk_level", "low")).lower()
        summary = type_result.get("summary", {})
        count = int(summary.get("finding_count", 0))
        mapping = {"critical": 12, "high": 8, "medium": 4, "low": 0}
        points = mapping.get(risk, 0)
        if points > 0:
            risk_factors.append(
                {
                    "factor": "type_safety_risk",
                    "severity": risk,
                    "points": points,
                    "evidence": f"{count} type-safety finding(s), tool risk={risk}",
                    "source_tool": "analyze_type_system_changes",
                }
            )
        return points

    def _score_test_impact(
        self,
        test_result: Dict[str, Any],
        risk_factors: List[Dict[str, Any]],
    ) -> int:
        summary = test_result.get("summary", {})
        scope = str(summary.get("regression_scope", "smoke")).lower()
        gap_count = int(summary.get("coverage_gap_count", 0))
        impacted_tests = int(summary.get("total_impacted_test_count", 0))
        changed_source = int(summary.get("changed_source_file_count", 0))

        scope_points = {
            "smoke": 0,
            "targeted_regression": 3,
            "broad_regression": 7,
            "full_suite": 12,
        }
        points = scope_points.get(scope, 0)
        if points > 0:
            risk_factors.append(
                {
                    "factor": "regression_scope_size",
                    "severity": "high" if scope in {"broad_regression", "full_suite"} else "medium",
                    "points": points,
                    "evidence": f"regression scope={scope}",
                    "source_tool": "assess_test_impact",
                }
            )

        if gap_count > 0:
            gap_points = min(10, gap_count * 2)
            points += gap_points
            risk_factors.append(
                {
                    "factor": "test_coverage_gaps",
                    "severity": "high" if gap_count >= 3 else "medium",
                    "points": gap_points,
                    "evidence": f"{gap_count} coverage gap(s) detected",
                    "source_tool": "assess_test_impact",
                }
            )

        if changed_source > 0 and impacted_tests == 0:
            orphan_points = 8
            points += orphan_points
            risk_factors.append(
                {
                    "factor": "no_impacted_tests_detected",
                    "severity": "high",
                    "points": orphan_points,
                    "evidence": (
                        f"{changed_source} changed source file(s) with 0 impacted tests"
                    ),
                    "source_tool": "assess_test_impact",
                }
            )
        return points

    def _level_from_score(self, score: int) -> str:
        if score >= 24:
            return "critical"
        if score >= 15:
            return "high"
        if score >= 8:
            return "medium"
        return "low"

    def _confidence(
        self,
        trace_result: Dict[str, Any],
        breaking_result: Dict[str, Any],
        type_result: Dict[str, Any],
        test_result: Dict[str, Any],
    ) -> str:
        statuses = [
            str(trace_result.get("status", "error")),
            str(breaking_result.get("status", "error")),
            str(type_result.get("status", "error")),
            str(test_result.get("status", "error")),
        ]
        success_count = sum(1 for status in statuses if status == "success")
        if success_count == 4:
            return "high"
        if success_count >= 2:
            return "medium"
        return "low"

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
        )


class IdentifyAffectedFeaturesInput(BaseModel):
    """Input schema for IdentifyAffectedFeaturesTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    max_features: int = Field(
        default=12,
        ge=1,
        le=100,
        description="Maximum number of affected feature groups to return",
    )


class IdentifyAffectedFeaturesTool(BaseTool):
    """Identify affected product features for user-facing communication."""

    name: str = "identify_affected_features"
    description: str = """
    Identify affected product features from changed and downstream-impacted files.
    Produces user-communication-oriented feature summaries and priorities.
    """
    args_schema: Type[BaseModel] = IdentifyAffectedFeaturesInput

    _NOISE_PARTS: Set[str] = {
        "src",
        "app",
        "lib",
        "backend",
        "frontend",
        "core",
        "common",
        "shared",
        "services",
        "service",
        "api",
        "internal",
        "pkg",
        "module",
        "modules",
        "components",
        "utils",
        "helpers",
        "tests",
        "test",
        "spec",
        "specs",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._trace = TraceDownstreamDependenciesTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_features: int = 12,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths:
                return {
                    "status": "success",
                    "directory_path": directory_path,
                    "affected_features": [],
                    "summary": {
                        "feature_count": 0,
                        "total_changed_files": 0,
                        "total_impacted_files": 0,
                        "total_impacted_tests": 0,
                        "high_priority_count": 0,
                    },
                    "user_communication": {
                        "headline": "No affected features detected",
                        "key_messages": [],
                        "audience_hint": "No user-facing changes identified from current diff.",
                    },
                }

            trace_result = self._trace._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                recursive=recursive,
                max_depth=max_downstream_depth,
                include_external_dependencies=False,
                extensions=extensions,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )

            downstream_files = set(changed_paths)
            if trace_result.get("status") == "success":
                downstream_files.update(
                    str(path).replace("\\", "/").strip()
                    for path in trace_result.get("aggregate_impacted_files", [])
                    if str(path).strip()
                )

            impacted_tests = set()
            coverage_gaps = []
            if test_result.get("status") == "success":
                impacted_tests = {
                    str(path).replace("\\", "/").strip()
                    for path in test_result.get("impacted_tests", [])
                    if str(path).strip()
                }
                coverage_gaps = test_result.get("coverage_gaps", []) if isinstance(test_result.get("coverage_gaps"), list) else []

            groups = self._group_features(
                changed_paths=changed_paths,
                downstream_files=downstream_files,
                file_impacts=file_impacts,
                impacted_tests=impacted_tests,
                coverage_gaps=coverage_gaps,
            )

            global_risk = str(risk_result.get("risk_level", "low")) if risk_result.get("status") == "success" else "unknown"
            affected_features = self._rank_and_format_features(
                groups=groups,
                global_risk=global_risk,
                max_features=max_features,
            )

            high_priority_count = sum(
                1
                for feature in affected_features
                if str(feature.get("communication_priority", "low")) in {"high", "critical"}
            )
            key_messages = [
                str(feature.get("recommended_message", "")).strip()
                for feature in affected_features[:6]
                if str(feature.get("recommended_message", "")).strip()
            ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "base_ref": base_ref,
                "target_ref": target_ref,
                "affected_features": affected_features,
                "summary": {
                    "feature_count": len(affected_features),
                    "total_changed_files": len(changed_paths),
                    "total_impacted_files": len(downstream_files),
                    "total_impacted_tests": len(impacted_tests),
                    "high_priority_count": high_priority_count,
                    "global_risk_level": global_risk,
                },
                "user_communication": {
                    "headline": self._headline(affected_features, global_risk),
                    "key_messages": key_messages,
                    "audience_hint": self._audience_hint(global_risk, high_priority_count),
                },
                "signals": {
                    "risk": {
                        "status": risk_result.get("status"),
                        "risk_level": risk_result.get("risk_level"),
                        "risk_score": risk_result.get("risk_score"),
                    },
                    "test_impact": {
                        "status": test_result.get("status"),
                        "summary": test_result.get("summary", {}),
                    },
                    "downstream": {
                        "status": trace_result.get("status"),
                        "summary": trace_result.get("summary", {}),
                    },
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _group_features(
        self,
        changed_paths: List[str],
        downstream_files: Set[str],
        file_impacts: List[Dict[str, Any]],
        impacted_tests: Set[str],
        coverage_gaps: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        impact_by_path = {
            str(item.get("path", "")).replace("\\", "/").strip(): str(item.get("impact", "modify"))
            for item in file_impacts
            if str(item.get("path", "")).strip()
        }
        groups: Dict[str, Dict[str, Any]] = {}

        for path in sorted(downstream_files):
            feature_key = self._feature_key(path)
            group = groups.setdefault(
                feature_key,
                {
                    "key": feature_key,
                    "changed_files": set(),
                    "impacted_files": set(),
                    "impacted_tests": set(),
                    "change_breakdown": {"create": 0, "modify": 0, "delete": 0},
                    "coverage_gaps": 0,
                    "components": set(),
                },
            )
            group["impacted_files"].add(path)
            group["components"].add(self._component_from_path(path))
            if path in changed_paths:
                group["changed_files"].add(path)
                impact = impact_by_path.get(path, "modify")
                if impact not in group["change_breakdown"]:
                    group["change_breakdown"][impact] = 0
                group["change_breakdown"][impact] += 1

        for test_file in impacted_tests:
            feature_key = self._feature_key(test_file)
            group = groups.setdefault(
                feature_key,
                {
                    "key": feature_key,
                    "changed_files": set(),
                    "impacted_files": set(),
                    "impacted_tests": set(),
                    "change_breakdown": {"create": 0, "modify": 0, "delete": 0},
                    "coverage_gaps": 0,
                    "components": set(),
                },
            )
            group["impacted_tests"].add(test_file)
            group["components"].add(self._component_from_path(test_file))

        for gap in coverage_gaps:
            source = str(gap.get("source_file", "")).replace("\\", "/").strip()
            if not source:
                continue
            feature_key = self._feature_key(source)
            group = groups.setdefault(
                feature_key,
                {
                    "key": feature_key,
                    "changed_files": set(),
                    "impacted_files": set(),
                    "impacted_tests": set(),
                    "change_breakdown": {"create": 0, "modify": 0, "delete": 0},
                    "coverage_gaps": 0,
                    "components": set(),
                },
            )
            group["coverage_gaps"] += 1

        return groups

    def _feature_key(self, path: str) -> str:
        normalized = str(path).replace("\\", "/").strip().lower()
        parts = [part for part in normalized.split("/") if part]
        if not parts:
            return "core"

        for part in parts[:-1]:
            cleaned = re.sub(r"[^a-z0-9_\\-]", "", part).strip("_-")
            if cleaned and cleaned not in self._NOISE_PARTS:
                return cleaned

        stem = Path(parts[-1]).stem.lower()
        stem = re.sub(r"(?:^test_|_test$|_spec$|\\.test$|\\.spec$)", "", stem)
        tokens = [token for token in re.split(r"[_\\-]+", stem) if token and token not in self._NOISE_PARTS]
        if tokens:
            return tokens[0]

        first = re.sub(r"[^a-z0-9_\\-]", "", parts[0]).strip("_-")
        return first or "core"

    def _component_from_path(self, path: str) -> str:
        parts = [part for part in str(path).replace("\\", "/").split("/") if part]
        return parts[0] if parts else "root"

    def _rank_and_format_features(
        self,
        groups: Dict[str, Dict[str, Any]],
        global_risk: str,
        max_features: int,
    ) -> List[Dict[str, Any]]:
        global_boost = 2 if global_risk in {"high", "critical"} else 0
        features: List[Dict[str, Any]] = []

        for key, group in groups.items():
            changed_count = len(group["changed_files"])
            impacted_count = len(group["impacted_files"])
            test_count = len(group["impacted_tests"])
            deletes = int(group["change_breakdown"].get("delete", 0))
            gaps = int(group.get("coverage_gaps", 0))

            score = global_boost
            score += min(8, changed_count * 2)
            score += min(6, impacted_count // 2)
            score += min(4, test_count // 2)
            score += deletes * 3
            score += gaps * 3

            if score >= 14:
                priority = "critical"
            elif score >= 9:
                priority = "high"
            elif score >= 4:
                priority = "medium"
            else:
                priority = "low"

            feature_name = key.replace("_", " ").replace("-", " ").title()
            summary = (
                f"{feature_name} impacted by {changed_count} changed file(s) and "
                f"{max(0, impacted_count - changed_count)} downstream file(s)."
            )
            message = self._message_for_feature(
                feature_name=feature_name,
                priority=priority,
                changed_count=changed_count,
                impacted_count=impacted_count,
                test_count=test_count,
                deletes=deletes,
                gaps=gaps,
            )

            features.append(
                {
                    "feature_id": f"feature_{key}",
                    "feature_name": feature_name,
                    "feature_key": key,
                    "summary": summary,
                    "communication_priority": priority,
                    "score": score,
                    "changed_files": sorted(group["changed_files"]),
                    "impacted_file_count": impacted_count,
                    "impacted_test_count": test_count,
                    "coverage_gap_count": gaps,
                    "change_breakdown": group["change_breakdown"],
                    "affected_components": sorted(group["components"]),
                    "recommended_message": message,
                }
            )

        features.sort(
            key=lambda item: (
                -int(item.get("score", 0)),
                str(item.get("feature_name", "")),
            )
        )
        return features[: max(1, max_features)]

    def _message_for_feature(
        self,
        feature_name: str,
        priority: str,
        changed_count: int,
        impacted_count: int,
        test_count: int,
        deletes: int,
        gaps: int,
    ) -> str:
        base = (
            f"{feature_name}: {changed_count} changed file(s), "
            f"{impacted_count} total impacted file(s), {test_count} impacted test(s)."
        )
        if deletes > 0:
            base += f" Includes {deletes} deleted file(s)."
        if gaps > 0:
            base += f" {gaps} coverage gap(s) detected; add regression tests."
        if priority in {"high", "critical"}:
            base += " Communicate as high-impact update to stakeholders."
        return base

    def _headline(self, affected_features: List[Dict[str, Any]], global_risk: str) -> str:
        count = len(affected_features)
        if count == 0:
            return "No affected features identified"
        high_count = sum(
            1
            for feature in affected_features
            if str(feature.get("communication_priority", "")) in {"high", "critical"}
        )
        return (
            f"{count} affected feature(s) identified"
            f" ({high_count} high-priority, overall risk: {global_risk})."
        )

    def _audience_hint(self, global_risk: str, high_priority_count: int) -> str:
        if global_risk in {"critical", "high"} or high_priority_count > 0:
            return "Prioritize PM, QA, and support communication before release."
        if global_risk == "medium":
            return "Share with QA and release manager for targeted validation."
        return "Standard release-note communication is sufficient."

    async def _arun(
        self,
        directory_path: str = ".",
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_features: int = 12,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            max_features=max_features,
        )


class GenerateChangeProcedureInput(BaseModel):
    """Input schema for GenerateChangeProcedureTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional change objective to frame the generated procedure",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    max_steps: int = Field(
        default=16,
        ge=6,
        le=50,
        description="Maximum number of generated procedure steps",
    )


class GenerateChangeProcedureTool(BaseTool):
    """Generate a detailed step-by-step change procedure."""

    name: str = "generate_change_procedure"
    description: str = """
    Generate a detailed step-by-step procedure for implementing the planned change.
    Uses impact, risk, feature, breaking-change, type, and test signals to produce execution steps.
    """
    args_schema: Type[BaseModel] = GenerateChangeProcedureInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._type = AnalyzeTypeSystemChangesTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_steps: int = 16,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]
            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            type_result = self._type._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            type_finding_count = int(type_result.get("summary", {}).get("finding_count", 0)) if type_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            ordered_files = self._ordered_files(file_impacts)
            steps = self._build_steps(
                objective=objective,
                directory_path=directory_path,
                changed_paths=changed_paths,
                ordered_files=ordered_files,
                risk_level=risk_level,
                regression_scope=regression_scope,
                breaking_count=breaking_count,
                type_finding_count=type_finding_count,
                affected_features=affected_features,
                impacted_tests=(
                    test_result.get("impacted_tests", [])
                    if test_result.get("status") == "success"
                    else []
                ),
                max_steps=max_steps,
            )

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Implement planned code changes safely",
                "procedure_steps": steps,
                "summary": {
                    "step_count": len(steps),
                    "changed_file_count": len(changed_paths),
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "breaking_change_count": breaking_count,
                    "type_finding_count": type_finding_count,
                    "affected_feature_count": len(affected_features),
                },
                "execution_notes": {
                    "ordered_files": ordered_files,
                    "top_affected_features": [
                        {
                            "feature_name": item.get("feature_name"),
                            "priority": item.get("communication_priority"),
                        }
                        for item in affected_features[:5]
                    ],
                },
                "signal_status": {
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "type_changes": type_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _ordered_files(self, file_impacts: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        grouped = {"delete": [], "modify": [], "create": []}
        for item in file_impacts:
            path = str(item.get("path", "")).replace("\\", "/").strip()
            if not path:
                continue
            impact = str(item.get("impact", "modify")).lower()
            if impact not in grouped:
                impact = "modify"
            grouped[impact].append(path)
        for key in grouped:
            grouped[key] = sorted(set(grouped[key]))
        return grouped

    def _build_steps(
        self,
        objective: Optional[str],
        directory_path: str,
        changed_paths: List[str],
        ordered_files: Dict[str, List[str]],
        risk_level: str,
        regression_scope: str,
        breaking_count: int,
        type_finding_count: int,
        affected_features: List[Dict[str, Any]],
        impacted_tests: List[str],
        max_steps: int,
    ) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        step_no = 1

        def add_step(
            title: str,
            actions: List[str],
            validation: str,
            outputs: List[str],
            when: str = "always",
        ) -> None:
            nonlocal step_no
            if len(steps) >= max_steps:
                return
            steps.append(
                {
                    "step_number": step_no,
                    "title": title,
                    "when": when,
                    "actions": actions,
                    "validation": validation,
                    "expected_outputs": outputs,
                }
            )
            step_no += 1

        add_step(
            title="Confirm Change Objective And Scope",
            actions=[
                f"Review objective: {objective or 'Implement planned code changes safely'}",
                f"Confirm working directory scope: {directory_path}",
                f"Review changed files ({len(changed_paths)}): {', '.join(changed_paths[:12]) or 'none'}",
            ],
            validation="Team confirms scope and objective before editing.",
            outputs=["Validated scope statement", "Reviewed file list"],
        )

        add_step(
            title="Establish Risk Guardrails",
            actions=[
                f"Review aggregate risk level: {risk_level}",
                f"Review regression scope target: {regression_scope}",
                f"Capture high-risk factors and owners before implementation.",
            ],
            validation="Risk owner assigned and risk controls acknowledged.",
            outputs=["Risk checklist", "Owner assignments"],
        )

        if ordered_files.get("delete"):
            add_step(
                title="Execute Deletions With Safety Checks",
                when="if deleted files exist",
                actions=[
                    f"Process deleted files first ({len(ordered_files['delete'])}): {', '.join(ordered_files['delete'][:10])}",
                    "Verify no retained references remain for each deletion.",
                    "Update imports/contracts to avoid orphan references.",
                ],
                validation="No unresolved references remain after deletions.",
                outputs=["Deletion diff reviewed", "Reference cleanup complete"],
            )

        if ordered_files.get("modify"):
            add_step(
                title="Implement Modifications In Dependency Order",
                when="if modified files exist",
                actions=[
                    f"Apply modifications ({len(ordered_files['modify'])}): {', '.join(ordered_files['modify'][:12])}",
                    "Prioritize shared/core files before leaf files.",
                    "Keep changes atomic per file or concern.",
                ],
                validation="All modified files compile/lint locally without new warnings.",
                outputs=["Modification commits or staged changes"],
            )

        if ordered_files.get("create"):
            add_step(
                title="Add New Files And Integrate",
                when="if created files exist",
                actions=[
                    f"Add created files ({len(ordered_files['create'])}): {', '.join(ordered_files['create'][:10])}",
                    "Wire new files into existing modules/routes/services.",
                    "Document interfaces and usage points for new files.",
                ],
                validation="New files are referenced correctly and reachable where expected.",
                outputs=["Integrated new files", "Updated interface references"],
            )

        if breaking_count > 0:
            add_step(
                title="Resolve Breaking Changes",
                when="if breaking changes detected",
                actions=[
                    f"Address {breaking_count} breaking-change finding(s).",
                    "Update public interfaces/contracts or provide compatibility layers.",
                    "Document migration notes for affected consumers.",
                ],
                validation="Breaking-change findings are mitigated or intentionally accepted with notes.",
                outputs=["Contract updates", "Consumer migration notes"],
            )

        if type_finding_count > 0:
            add_step(
                title="Resolve Type-Safety Regressions",
                when="if type findings detected",
                actions=[
                    f"Address {type_finding_count} type-system finding(s).",
                    "Replace unsafe typing (`any`/dynamic) with explicit types where possible.",
                    "Update function signatures and typed symbols consistently.",
                ],
                validation="Type checks pass and type-risk findings are reduced.",
                outputs=["Updated type definitions/signatures"],
            )

        add_step(
            title="Execute Regression Test Plan",
            actions=[
                f"Run regression scope: {regression_scope}",
                f"Prioritize impacted tests ({len(impacted_tests)}): {', '.join(sorted(set(impacted_tests))[:12]) or 'none'}",
                "Capture failures and iterate fixes before final verification.",
            ],
            validation="All required tests pass for declared regression scope.",
            outputs=["Test results", "Failure remediation notes"],
        )

        top_features = [
            f"{item.get('feature_name')} ({item.get('communication_priority')})"
            for item in affected_features[:5]
            if item.get("feature_name")
        ]
        add_step(
            title="Validate User-Facing Feature Impact",
            actions=[
                f"Review affected features: {', '.join(top_features) or 'none'}",
                "Validate user-visible flows for top-priority affected features.",
                "Prepare support/release notes for impacted behavior.",
            ],
            validation="Feature owners confirm behavior and communication notes.",
            outputs=["Feature validation notes", "User communication draft"],
        )

        add_step(
            title="Finalize Procedure Exit Criteria",
            actions=[
                "Ensure code changes, tests, and risk mitigations are complete.",
                "Summarize what changed, why, and residual risk.",
                "Mark procedure complete and ready for downstream workflow tickets.",
            ],
            validation="All acceptance checks completed and documented.",
            outputs=["Completion checklist", "Final implementation summary"],
        )

        return steps[:max_steps]

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_steps: int = 16,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            max_steps=max_steps,
        )


class GenerateGitWorkflowInput(BaseModel):
    """Input schema for GenerateGitWorkflowTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional change objective used for branch naming and PR template",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 279, TICKET-279, PROJ-123)",
    )
    change_type: Optional[str] = Field(
        default=None,
        description=(
            "Optional change type override. Supported: feature, bugfix, hotfix, "
            "refactor, chore, breaking-change, experimental"
        ),
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    base_branch: str = Field(
        default="main",
        description="Primary integration branch name",
    )
    include_command_examples: bool = Field(
        default=True,
        description="Include concrete git command examples in workflow steps",
    )


class GenerateGitWorkflowTool(BaseTool):
    """Generate a Git workflow format with branch naming conventions."""

    name: str = "generate_git_workflow"
    description: str = """
    Generate a Git workflow format with branch naming conventions for the planned change.
    Produces branch name templates, generated branch recommendation, PR/merge strategy, and workflow steps.
    """
    args_schema: Type[BaseModel] = GenerateGitWorkflowInput

    _CHANGE_TYPES: Set[str] = {
        "feature",
        "bugfix",
        "hotfix",
        "refactor",
        "chore",
        "breaking-change",
        "experimental",
    }

    _PREFIX_CATALOG: Dict[str, str] = {
        "feature": "feature",
        "bugfix": "fix",
        "hotfix": "hotfix",
        "refactor": "refactor",
        "chore": "chore",
        "breaking-change": "breaking",
        "experimental": "exp",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        change_type: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        base_branch: str = "main",
        include_command_examples: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=8,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            coverage_gap_count = (
                int(test_result.get("summary", {}).get("coverage_gap_count", 0))
                if test_result.get("status") == "success"
                else 0
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            resolved_change_type = self._resolve_change_type(
                requested_change_type=change_type,
                file_impacts=file_impacts,
                risk_level=risk_level,
                breaking_count=breaking_count,
            )
            workflow_model = self._select_workflow_model(
                change_type=resolved_change_type,
                risk_level=risk_level,
                breaking_count=breaking_count,
            )
            branch_name = self._generate_branch_name(
                change_type=resolved_change_type,
                ticket_id=ticket_id,
                objective=objective,
                affected_features=affected_features,
                changed_paths=changed_paths,
            )
            required_checks = self._required_checks(
                risk_level=risk_level,
                regression_scope=regression_scope,
                breaking_count=breaking_count,
                coverage_gap_count=coverage_gap_count,
            )
            merge_strategy = self._select_merge_strategy(
                change_type=resolved_change_type,
                risk_level=risk_level,
                breaking_count=breaking_count,
            )
            workflow_steps = self._build_workflow_steps(
                base_branch=base_branch,
                branch_name=branch_name,
                resolved_change_type=resolved_change_type,
                required_checks=required_checks,
                regression_scope=regression_scope,
                include_command_examples=include_command_examples,
                risk_level=risk_level,
                breaking_count=breaking_count,
            )

            prefix_examples = [
                f"{prefix}/TICKET-123-short-description"
                for prefix in ["feature", "fix", "hotfix", "refactor", "chore"]
            ]
            top_features = [
                str(item.get("feature_name", "")).strip()
                for item in affected_features[:3]
                if str(item.get("feature_name", "")).strip()
            ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Implement planned code changes with controlled Git workflow",
                "git_workflow_format": {
                    "workflow_model": workflow_model,
                    "base_branch": base_branch,
                    "change_type": resolved_change_type,
                    "branch_naming": {
                        "pattern": "<prefix>/<ticket-or-scope>-<short-description>",
                        "prefix_catalog": self._PREFIX_CATALOG,
                        "generated_branch": branch_name,
                        "examples": prefix_examples,
                        "rules": [
                            "Use lowercase kebab-case branch descriptions",
                            "Start branch with approved prefix",
                            "Include ticket/work item when available",
                            "Keep branch names under ~80 characters",
                        ],
                    },
                    "pull_request": {
                        "title_template": f"[{resolved_change_type}] {ticket_id or 'TICKET-XXX'}: <summary>",
                        "required_sections": [
                            "Scope",
                            "Risk assessment",
                            "Test evidence",
                            "Rollback notes",
                        ],
                        "target_branch": base_branch,
                    },
                    "merge_policy": {
                        "strategy": merge_strategy,
                        "delete_branch_after_merge": True,
                        "require_up_to_date_with_base": True,
                    },
                    "required_checks": required_checks,
                },
                "workflow_steps": workflow_steps,
                "summary": {
                    "changed_file_count": len(changed_paths),
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "breaking_change_count": breaking_count,
                    "coverage_gap_count": coverage_gap_count,
                    "affected_feature_count": len(affected_features),
                    "top_affected_features": top_features,
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _resolve_change_type(
        self,
        requested_change_type: Optional[str],
        file_impacts: List[Dict[str, Any]],
        risk_level: str,
        breaking_count: int,
    ) -> str:
        normalized = str(requested_change_type or "").strip().lower()
        if normalized in {"bug", "bugfix", "fix"}:
            return "bugfix"
        if normalized in self._CHANGE_TYPES:
            return normalized

        if breaking_count > 0:
            return "breaking-change"
        if risk_level == "critical":
            return "hotfix"

        impact_set = {str(item.get("impact", "")).lower() for item in file_impacts}
        if "delete" in impact_set:
            return "refactor"
        if "create" in impact_set:
            return "feature"
        if risk_level == "high":
            return "bugfix"
        return "chore"

    def _select_workflow_model(
        self,
        change_type: str,
        risk_level: str,
        breaking_count: int,
    ) -> str:
        if change_type == "hotfix":
            return "hotfix-flow"
        if breaking_count > 0 or risk_level in {"critical", "high"}:
            return "trunk-based-with-release-gates"
        return "trunk-based-short-lived-branches"

    def _generate_branch_name(
        self,
        change_type: str,
        ticket_id: Optional[str],
        objective: Optional[str],
        affected_features: List[Dict[str, Any]],
        changed_paths: List[str],
    ) -> str:
        prefix = self._PREFIX_CATALOG.get(change_type, "chore")
        token = self._ticket_token(ticket_id)
        scope = self._scope_slug(objective, affected_features, changed_paths)
        branch = f"{prefix}/{token}-{scope}" if token else f"{prefix}/{scope}"
        return branch[:80].rstrip("-")

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""

        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else "TICKET"

        return self._slugify(raw).upper()

    def _scope_slug(
        self,
        objective: Optional[str],
        affected_features: List[Dict[str, Any]],
        changed_paths: List[str],
    ) -> str:
        objective_slug = self._slugify(objective or "")
        if objective_slug:
            return objective_slug

        if affected_features:
            top_feature = str(affected_features[0].get("feature_name", ""))
            feature_slug = self._slugify(top_feature)
            if feature_slug:
                return feature_slug

        if changed_paths:
            name = Path(changed_paths[0]).stem
            path_slug = self._slugify(name)
            if path_slug:
                return path_slug
        return "update"

    def _slugify(self, text: str, max_tokens: int = 6) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip().lower()).strip("-")
        if not cleaned:
            return ""
        tokens = [token for token in cleaned.split("-") if token]
        return "-".join(tokens[:max_tokens]) if tokens else ""

    def _required_checks(
        self,
        risk_level: str,
        regression_scope: str,
        breaking_count: int,
        coverage_gap_count: int,
    ) -> List[str]:
        checks = ["Lint", "Unit tests"]
        scope = regression_scope.lower()
        if scope in {"targeted_regression", "broad_regression", "full_suite"}:
            checks.append("Regression tests")
        if scope in {"broad_regression", "full_suite"} or risk_level in {"high", "critical"}:
            checks.append("Integration tests")
        if risk_level == "critical":
            checks.append("Manual QA sign-off")
        if breaking_count > 0:
            checks.append("API/contract compatibility review")
        if coverage_gap_count > 0:
            checks.append("Test coverage gap remediation")
        return checks

    def _select_merge_strategy(
        self,
        change_type: str,
        risk_level: str,
        breaking_count: int,
    ) -> str:
        if change_type == "hotfix":
            return "rebase-and-merge"
        if breaking_count > 0 or risk_level in {"high", "critical"}:
            return "merge-commit"
        return "squash-merge"

    def _build_workflow_steps(
        self,
        base_branch: str,
        branch_name: str,
        resolved_change_type: str,
        required_checks: List[str],
        regression_scope: str,
        include_command_examples: bool,
        risk_level: str,
        breaking_count: int,
    ) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        step_no = 1

        def add_step(
            title: str,
            actions: List[str],
            exit_criteria: str,
            commands: Optional[List[str]] = None,
            when: str = "always",
        ) -> None:
            nonlocal step_no
            step = {
                "step_number": step_no,
                "title": title,
                "when": when,
                "actions": actions,
                "exit_criteria": exit_criteria,
            }
            if include_command_examples:
                step["commands"] = commands or []
            steps.append(step)
            step_no += 1

        add_step(
            title="Sync Base Branch And Create Working Branch",
            actions=[
                f"Update local `{base_branch}` with remote before branching.",
                f"Create branch using naming convention: {branch_name}",
                "Push branch and set upstream.",
            ],
            exit_criteria="Branch exists on remote and tracks origin.",
            commands=[
                "git fetch --all --prune",
                f"git checkout {base_branch}",
                f"git pull --rebase origin {base_branch}",
                f"git checkout -b {branch_name}",
                f"git push -u origin {branch_name}",
            ],
        )

        add_step(
            title="Implement Changes In Atomic Commits",
            actions=[
                f"Apply code changes for `{resolved_change_type}` in small, reviewable chunks.",
                "Keep each commit focused on one concern.",
                "Use consistent commit messages with issue context.",
            ],
            exit_criteria="Local branch contains a clean sequence of atomic commits.",
            commands=[
                "git add -p",
                "git commit -m \"<type>: <short summary>\"",
            ],
        )

        add_step(
            title="Run Required Validation Gates",
            actions=[
                f"Execute required checks: {', '.join(required_checks)}.",
                f"Ensure regression scope `{regression_scope}` is satisfied.",
                "Fix failures before opening PR.",
            ],
            exit_criteria="All required checks pass on local and CI pipelines.",
            commands=[
                "# Run project lint/tests using repo commands",
                "git status",
            ],
        )

        add_step(
            title="Open Pull Request Using Standard Format",
            actions=[
                f"Open PR from `{branch_name}` into `{base_branch}`.",
                "Use PR template sections: Scope, Risk assessment, Test evidence, Rollback notes.",
                "Link ticket/work item and request required reviewers.",
            ],
            exit_criteria="PR is open with complete context and required reviewers assigned.",
            commands=[],
        )

        if risk_level in {"high", "critical"} or breaking_count > 0:
            add_step(
                title="Apply Elevated Release Controls",
                when="if risk is high/critical or breaking changes exist",
                actions=[
                    "Require explicit approval from tech lead and QA owner.",
                    "Confirm deployment safeguards and rollback readiness before merge.",
                    "Record compatibility or migration notes for downstream consumers.",
                ],
                exit_criteria="Elevated controls are acknowledged and documented in PR.",
                commands=[],
            )

        add_step(
            title="Merge And Clean Up Branch",
            actions=[
                "Merge using repository merge policy.",
                "Delete remote/local branch after successful merge.",
                "Verify base branch includes latest merged commit.",
            ],
            exit_criteria="Change is merged to base branch and feature branch is removed.",
            commands=[
                f"git checkout {base_branch}",
                f"git pull origin {base_branch}",
                f"git branch -d {branch_name}",
                f"git push origin --delete {branch_name}",
            ],
        )

        add_step(
            title="Post-Merge Verification",
            actions=[
                "Monitor CI/deployment status after merge.",
                "Validate critical user-facing flows impacted by this change.",
                "Publish release notes/update stakeholders as needed.",
            ],
            exit_criteria="Post-merge validation complete and stakeholders informed.",
            commands=[],
        )

        return steps

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        change_type: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        base_branch: str = "main",
        include_command_examples: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            change_type=change_type,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            base_branch=base_branch,
            include_command_examples=include_command_examples,
        )


class GenerateCommitSequenceInput(BaseModel):
    """Input schema for GenerateCommitSequenceTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional change objective used to frame commit intent",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 280, TICKET-280, PROJ-123)",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    max_commits: int = Field(
        default=8,
        ge=1,
        le=30,
        description="Maximum number of generated commits in the sequence",
    )
    include_command_examples: bool = Field(
        default=True,
        description="Include concrete git command examples per commit",
    )
    include_validation_commit: bool = Field(
        default=True,
        description="Include a dedicated validation/test evidence commit recommendation",
    )


class GenerateCommitSequenceTool(BaseTool):
    """Generate an atomic commit sequence for planned changes."""

    name: str = "generate_commit_sequence"
    description: str = """
    Generate an ordered commit sequence for atomic changes.
    Uses impact/risk/test/breaking/type signals to group files into focused commits with messages.
    """
    args_schema: Type[BaseModel] = GenerateCommitSequenceInput

    _NOISE_PARTS: Set[str] = {
        "src",
        "app",
        "backend",
        "frontend",
        "core",
        "lib",
        "pkg",
        "module",
        "modules",
        "internal",
        "services",
        "service",
        "shared",
        "common",
    }
    _CONTRACT_HINTS: Set[str] = {
        "type",
        "types",
        "interface",
        "interfaces",
        "schema",
        "schemas",
        "contract",
        "contracts",
        "dto",
        "model",
        "models",
        "api",
        "migration",
        "migrations",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._type = AnalyzeTypeSystemChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_commits: int = 8,
        include_command_examples: bool = True,
        include_validation_commit: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            if not changed_paths:
                return {
                    "status": "success",
                    "directory_path": directory_path,
                    "objective": objective or "Implement planned changes in atomic commits",
                    "commit_sequence": [],
                    "summary": {
                        "commit_count": 0,
                        "changed_file_count": 0,
                        "risk_level": "unknown",
                        "breaking_change_count": 0,
                        "type_finding_count": 0,
                    },
                }

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            type_result = self._type._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=6,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            impacted_tests = (
                sorted(set(test_result.get("impacted_tests", [])))
                if test_result.get("status") == "success"
                else []
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            type_finding_count = int(type_result.get("summary", {}).get("finding_count", 0)) if type_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            commit_sequence = self._build_sequence(
                file_impacts=file_impacts,
                objective=objective,
                ticket_id=ticket_id,
                risk_level=risk_level,
                regression_scope=regression_scope,
                impacted_tests=impacted_tests,
                breaking_count=breaking_count,
                type_finding_count=type_finding_count,
                include_validation_commit=include_validation_commit,
                include_command_examples=include_command_examples,
                max_commits=max_commits,
            )

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Implement planned changes in atomic commits",
                "commit_sequence": commit_sequence,
                "summary": {
                    "commit_count": len(commit_sequence),
                    "changed_file_count": len(changed_paths),
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "breaking_change_count": breaking_count,
                    "type_finding_count": type_finding_count,
                    "affected_feature_count": len(affected_features),
                },
                "conventions": {
                    "message_style": "conventional_commits",
                    "ordering_strategy": [
                        "deletions_first",
                        "contracts_and_types_before_implementation",
                        "implementation_by_component",
                        "tests_and_validation_last",
                    ],
                    "atomicity_rules": [
                        "One concern per commit",
                        "Prefer <= 12 files per commit when practical",
                        "Keep commit message scope specific and actionable",
                    ],
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "type_changes": type_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _build_sequence(
        self,
        file_impacts: List[Dict[str, Any]],
        objective: Optional[str],
        ticket_id: Optional[str],
        risk_level: str,
        regression_scope: str,
        impacted_tests: List[str],
        breaking_count: int,
        type_finding_count: int,
        include_validation_commit: bool,
        include_command_examples: bool,
        max_commits: int,
    ) -> List[Dict[str, Any]]:
        impact_by_path: Dict[str, str] = {}
        for item in file_impacts:
            path = str(item.get("path", "")).replace("\\", "/").strip()
            if path:
                impact_by_path[path] = str(item.get("impact", "modify")).lower()

        delete_files = sorted([path for path, impact in impact_by_path.items() if impact == "delete"])
        create_files = {path for path, impact in impact_by_path.items() if impact == "create"}
        changed_paths = sorted(impact_by_path.keys())

        ticket_token = self._ticket_token(ticket_id)
        commits: List[Dict[str, Any]] = []

        def add_commit(
            commit_type: str,
            scope: str,
            summary: str,
            intent: str,
            files: List[str],
            validation: str,
            when: str = "always",
        ) -> None:
            if len(commits) >= max_commits:
                return
            number = len(commits) + 1
            message = self._commit_message(commit_type, scope, summary, ticket_token)
            commit = {
                "commit_number": number,
                "when": when,
                "intent": intent,
                "commit_message": message,
                "file_scope": files[:24],
                "depends_on": [number - 1] if number > 1 else [],
                "validation": validation,
            }
            if include_command_examples:
                add_target = " ".join(files[:10]) if files else "-A"
                safe_message = message.replace('"', '\\"')
                commit["commands"] = [
                    f"git add {add_target}",
                    f'git commit -m "{safe_message}"',
                ]
            commits.append(commit)

        if delete_files:
            add_commit(
                commit_type="refactor",
                scope="cleanup",
                summary="remove deprecated or replaced files",
                intent="Isolate removals to reduce diff noise in follow-up commits",
                files=delete_files,
                validation="No unresolved imports/references remain after deletion commit.",
            )

        remaining_files = [path for path in changed_paths if path not in set(delete_files)]
        contract_files = sorted([path for path in remaining_files if self._is_contract_file(path)])
        implementation_files = [path for path in remaining_files if path not in set(contract_files)]

        if contract_files:
            commit_type = "feat" if any(path in create_files for path in contract_files) else "refactor"
            add_commit(
                commit_type=commit_type,
                scope="contracts",
                summary="update shared interfaces, schemas, and type contracts",
                intent="Land cross-cutting contracts before component-level implementation.",
                files=contract_files,
                validation="Type checks and contract references stay consistent.",
            )

        area_groups = self._group_by_area(implementation_files)
        for area, area_files in area_groups:
            has_create = any(path in create_files for path in area_files)
            commit_type = "feat" if has_create else ("fix" if risk_level in {"high", "critical"} else "refactor")
            area_summary = "implement component updates"
            if has_create:
                area_summary = "introduce new component logic"
            add_commit(
                commit_type=commit_type,
                scope=area,
                summary=area_summary,
                intent=f"Keep `{area}` changes together as one atomic review unit.",
                files=area_files,
                validation="Build/lint passes for this component scope.",
            )

        if type_finding_count > 0:
            typed_scope = [path for path in changed_paths if self._looks_like_typed_file(path)]
            add_commit(
                commit_type="fix",
                scope="types",
                summary="resolve type-safety regressions",
                intent="Apply explicit type fixes after implementation commits.",
                files=(typed_scope or changed_paths)[:24],
                validation="Type checker passes without new errors.",
                when="if type findings exist",
            )

        needs_validation_commit = (
            include_validation_commit
            or bool(impacted_tests)
            or regression_scope.lower() in {"targeted_regression", "broad_regression", "full_suite"}
        )
        if needs_validation_commit:
            changed_test_files = [path for path in changed_paths if self._is_test_file(path)]
            test_scope = sorted(set(changed_test_files + impacted_tests))
            add_commit(
                commit_type="test",
                scope="regression",
                summary=f"add or update validation for {regression_scope} scope",
                intent="Keep test evidence separate from production code changes.",
                files=test_scope[:24],
                validation="Required regression tests pass in CI.",
            )

        if breaking_count > 0:
            add_commit(
                commit_type="docs",
                scope="migration",
                summary="document breaking change rollout and migration notes",
                intent="Capture consumer-facing compatibility guidance separately.",
                files=["docs/migration.md", "docs/release-notes.md"],
                validation="Migration instructions reviewed by maintainers.",
                when="if breaking changes exist",
            )

        if not commits:
            add_commit(
                commit_type="chore",
                scope="changes",
                summary=self._slug_to_summary(objective) or "apply planned updates",
                intent="Single atomic commit for limited scope change.",
                files=changed_paths[:24],
                validation="Local checks pass for impacted files.",
            )

        return commits[:max_commits]

    def _group_by_area(self, paths: List[str]) -> List[tuple[str, List[str]]]:
        groups: Dict[str, List[str]] = {}
        for path in paths:
            area = self._area_from_path(path)
            groups.setdefault(area, []).append(path)
        ordered = sorted(
            ((area, sorted(set(files))) for area, files in groups.items()),
            key=lambda item: (-len(item[1]), item[0]),
        )
        return ordered

    def _area_from_path(self, path: str) -> str:
        parts = [part for part in str(path).replace("\\", "/").split("/") if part]
        if not parts:
            return "root"
        for part in parts[:-1]:
            token = part.lower()
            if token not in self._NOISE_PARTS:
                return self._slugify(token) or "module"
        if len(parts) > 1:
            return self._slugify(parts[-2]) or "module"
        return "root"

    def _is_contract_file(self, path: str) -> bool:
        lowered = str(path).lower()
        parts = [part for part in re.split(r"[\\/._-]+", lowered) if part]
        return any(token in self._CONTRACT_HINTS for token in parts)

    def _is_test_file(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        if re.search(r"(^|/)(test|tests|spec|specs|__tests__)(/|$)", normalized):
            return True
        return bool(re.search(r"(_test\.[a-z0-9]+|\.test\.[a-z0-9]+|\.spec\.[a-z0-9]+)$", normalized))

    def _looks_like_typed_file(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in {".ts", ".tsx", ".java", ".go", ".cs", ".rs"}

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else ""
        return self._slugify(raw, max_tokens=3).upper()

    def _commit_message(
        self,
        commit_type: str,
        scope: str,
        summary: str,
        ticket_token: str,
    ) -> str:
        normalized_scope = self._slugify(scope, max_tokens=2) or "core"
        normalized_summary = self._slug_to_summary(summary) or "apply updates"
        base = f"{commit_type}({normalized_scope}): {normalized_summary}"
        return f"{base} [{ticket_token}]" if ticket_token else base

    def _slug_to_summary(self, text: Optional[str]) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        cleaned = cleaned.strip(":;- ")
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        return lowered[:72].strip()

    def _slugify(self, text: str, max_tokens: int = 5) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip().lower()).strip("-")
        if not cleaned:
            return ""
        tokens = [token for token in cleaned.split("-") if token]
        return "-".join(tokens[:max_tokens]) if tokens else ""

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        max_commits: int = 8,
        include_command_examples: bool = True,
        include_validation_commit: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            max_commits=max_commits,
            include_command_examples=include_command_examples,
            include_validation_commit=include_validation_commit,
        )


class GenerateRollbackProcedureInput(BaseModel):
    """Input schema for GenerateRollbackProcedureTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional change objective used to contextualize rollback guidance",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 281, TICKET-281, PROJ-123)",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    base_branch: str = Field(
        default="main",
        description="Primary integration branch name used for rollback commands",
    )
    deployment_environment: str = Field(
        default="production",
        description="Environment the rollback procedure is targeting",
    )
    include_command_examples: bool = Field(
        default=True,
        description="Include concrete command examples in generated steps",
    )
    include_data_safety_checks: bool = Field(
        default=True,
        description="Include explicit data backup/snapshot checks",
    )


class GenerateRollbackProcedureTool(BaseTool):
    """Generate a rollback procedure for safe recovery."""

    name: str = "generate_rollback_procedure"
    description: str = """
    Generate a rollback procedure for safe recovery.
    Uses impact, risk, breaking, and test signals to define rollback triggers, steps, and validation criteria.
    """
    args_schema: Type[BaseModel] = GenerateRollbackProcedureInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        base_branch: str = "main",
        deployment_environment: str = "production",
        include_command_examples: bool = True,
        include_data_safety_checks: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=8,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            coverage_gap_count = (
                int(test_result.get("summary", {}).get("coverage_gap_count", 0))
                if test_result.get("status") == "success"
                else 0
            )
            impacted_tests = (
                sorted(set(test_result.get("impacted_tests", [])))
                if test_result.get("status") == "success"
                else []
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            rollback_strategy = self._rollback_strategy(
                risk_level=risk_level,
                breaking_count=breaking_count,
                changed_file_count=len(changed_paths),
            )
            rollback_triggers = self._rollback_triggers(
                risk_level=risk_level,
                regression_scope=regression_scope,
                breaking_count=breaking_count,
                coverage_gap_count=coverage_gap_count,
            )
            rollback_steps = self._build_rollback_steps(
                ticket_id=ticket_id,
                base_branch=base_branch,
                deployment_environment=deployment_environment,
                rollback_strategy=rollback_strategy,
                risk_level=risk_level,
                regression_scope=regression_scope,
                breaking_count=breaking_count,
                impacted_tests=impacted_tests,
                include_data_safety_checks=include_data_safety_checks,
                include_command_examples=include_command_examples,
            )
            top_features = [
                str(item.get("feature_name", "")).strip()
                for item in affected_features[:4]
                if str(item.get("feature_name", "")).strip()
            ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Provide safe rollback execution guidance",
                "rollback_plan": {
                    "strategy": rollback_strategy,
                    "environment": deployment_environment,
                    "base_branch": base_branch,
                    "triggers": rollback_triggers,
                    "steps": rollback_steps,
                    "success_criteria": [
                        "Service health returns to baseline",
                        "Critical user flows recover",
                        "Error-rate/latency alerts return below threshold",
                    ],
                },
                "summary": {
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "changed_file_count": len(changed_paths),
                    "breaking_change_count": breaking_count,
                    "coverage_gap_count": coverage_gap_count,
                    "impacted_test_count": len(impacted_tests),
                    "affected_feature_count": len(affected_features),
                    "top_affected_features": top_features,
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _rollback_strategy(
        self,
        risk_level: str,
        breaking_count: int,
        changed_file_count: int,
    ) -> str:
        if breaking_count > 0:
            return "controlled_revert_with_compatibility_guardrails"
        if risk_level in {"critical", "high"} or changed_file_count >= 20:
            return "immediate_revert_and_stabilize"
        return "standard_revert"

    def _rollback_triggers(
        self,
        risk_level: str,
        regression_scope: str,
        breaking_count: int,
        coverage_gap_count: int,
    ) -> List[Dict[str, Any]]:
        triggers: List[Dict[str, Any]] = [
            {
                "trigger": "Sev1/Sev2 customer-facing incident after release",
                "severity": "critical",
                "action": "Start rollback immediately",
            },
            {
                "trigger": "Health checks or SLO alerts remain breached for > 15 minutes",
                "severity": "high",
                "action": "Initiate rollback window",
            },
        ]
        if regression_scope.lower() in {"broad_regression", "full_suite"}:
            triggers.append(
                {
                    "trigger": "Multiple regression failures in post-deploy validation",
                    "severity": "high",
                    "action": "Rollback and quarantine change set",
                }
            )
        if breaking_count > 0:
            triggers.append(
                {
                    "trigger": "Consumer contract incompatibility detected",
                    "severity": "critical",
                    "action": "Rollback plus compatibility communication",
                }
            )
        if coverage_gap_count > 0:
            triggers.append(
                {
                    "trigger": "Uncovered path failure in production",
                    "severity": "medium",
                    "action": "Rollback if impact exceeds agreed threshold",
                }
            )
        if risk_level in {"critical", "high"}:
            triggers.append(
                {
                    "trigger": "On-call cannot restore stability through mitigation within SLA",
                    "severity": "high",
                    "action": "Escalate and execute rollback",
                }
            )
        return triggers

    def _build_rollback_steps(
        self,
        ticket_id: Optional[str],
        base_branch: str,
        deployment_environment: str,
        rollback_strategy: str,
        risk_level: str,
        regression_scope: str,
        breaking_count: int,
        impacted_tests: List[str],
        include_data_safety_checks: bool,
        include_command_examples: bool,
    ) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        step_no = 1
        ticket_token = self._ticket_token(ticket_id)

        def add_step(
            title: str,
            actions: List[str],
            exit_criteria: str,
            commands: Optional[List[str]] = None,
            when: str = "always",
        ) -> None:
            nonlocal step_no
            step = {
                "step_number": step_no,
                "title": title,
                "when": when,
                "actions": actions,
                "exit_criteria": exit_criteria,
            }
            if include_command_examples:
                step["commands"] = commands or []
            steps.append(step)
            step_no += 1

        add_step(
            title="Declare Rollback Event And Freeze Deployments",
            actions=[
                f"Declare rollback for `{deployment_environment}` and communicate incident bridge.",
                "Pause new deployments/merges until service is stable.",
                f"Record work item reference: {ticket_token or 'N/A'}.",
            ],
            exit_criteria="Incident owner assigned and deployment freeze active.",
            commands=[],
        )

        add_step(
            title="Capture Rollback Point And Evidence",
            actions=[
                "Identify last known good release/commit SHA.",
                "Capture current failing release identifier and telemetry snapshot.",
                f"Confirm rollback strategy: {rollback_strategy}.",
            ],
            exit_criteria="Rollback target and current bad version are explicitly documented.",
            commands=[
                "git fetch --all --prune",
                f"git checkout {base_branch}",
                f"git pull origin {base_branch}",
                "git log --oneline -n 20",
            ],
        )

        if include_data_safety_checks:
            add_step(
                title="Protect Data State Before Revert",
                actions=[
                    "Take database snapshot/backup before applying rollback.",
                    "Export critical queue/state checkpoints if applicable.",
                    "Confirm recovery owner for data rollback path.",
                ],
                exit_criteria="Data safety checkpoint completed and recoverable.",
                commands=[],
                when="if release includes data/state changes",
            )

        add_step(
            title="Execute Code Rollback",
            actions=[
                "Revert offending commit range or redeploy last known good artifact.",
                "Apply rollback through the standard deployment pipeline.",
                "Track rollout progress and halt if additional errors appear.",
            ],
            exit_criteria="Rollback artifact deployed successfully to target environment.",
            commands=[
                "git revert <bad-commit-sha> --no-edit",
                "git push origin HEAD",
            ],
        )

        if breaking_count > 0:
            add_step(
                title="Apply Compatibility Safeguards",
                when="if breaking changes were part of the release",
                actions=[
                    "Re-enable compatibility fallbacks or previous API contract versions.",
                    "Coordinate with dependent consumers to prevent repeated failures.",
                    "Confirm contract version alignment after rollback.",
                ],
                exit_criteria="Downstream consumers are stable on compatible contracts.",
                commands=[],
            )

        add_step(
            title="Run Post-Rollback Validation",
            actions=[
                f"Run smoke + `{regression_scope}` validation checks.",
                f"Prioritize impacted tests: {', '.join(impacted_tests[:8]) or 'none'}.",
                "Verify SLOs, logs, and error rates have returned to baseline.",
            ],
            exit_criteria="Validation checks pass and operational metrics are stable.",
            commands=[],
        )

        if risk_level in {"critical", "high"}:
            add_step(
                title="Complete Incident Communication And Follow-Up",
                when="if risk level is high or critical",
                actions=[
                    "Publish incident update with rollback status and user impact.",
                    "Create follow-up actions to prevent recurrence.",
                    "Schedule postmortem with engineering and product stakeholders.",
                ],
                exit_criteria="Stakeholders informed and follow-up items tracked.",
                commands=[],
            )

        return steps

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else ""
        normalized = re.sub(r"[^A-Z0-9]+", "-", compact).strip("-")
        return normalized[:32]

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        base_branch: str = "main",
        deployment_environment: str = "production",
        include_command_examples: bool = True,
        include_data_safety_checks: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            base_branch=base_branch,
            deployment_environment=deployment_environment,
            include_command_examples=include_command_examples,
            include_data_safety_checks=include_data_safety_checks,
        )


class GenerateFeatureFlagStrategyInput(BaseModel):
    """Input schema for GenerateFeatureFlagStrategyTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional change objective used to frame flag strategy",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 282, TICKET-282, PROJ-123)",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    flag_key_prefix: str = Field(
        default="ff",
        description="Prefix for generated feature flag keys",
    )
    environments: List[str] = Field(
        default_factory=lambda: ["dev", "staging", "production"],
        description="Ordered environments for rollout progression",
    )
    include_kill_switch: bool = Field(
        default=True,
        description="Include kill-switch strategy in generated output",
    )
    include_experiment_support: bool = Field(
        default=True,
        description="Include optional A/B experiment support recommendations",
    )


class GenerateFeatureFlagStrategyTool(BaseTool):
    """Generate a feature-flag strategy for gradual rollout."""

    name: str = "generate_feature_flag_strategy"
    description: str = """
    Generate a feature-flag strategy for gradual rollout.
    Uses impact, risk, regression, and breaking-change signals to propose flag design and rollout phases.
    """
    args_schema: Type[BaseModel] = GenerateFeatureFlagStrategyInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        flag_key_prefix: str = "ff",
        environments: Optional[List[str]] = None,
        include_kill_switch: bool = True,
        include_experiment_support: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=8,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            coverage_gap_count = (
                int(test_result.get("summary", {}).get("coverage_gap_count", 0))
                if test_result.get("status") == "success"
                else 0
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            envs = self._normalize_environments(environments)
            strategy_mode = self._strategy_mode(
                risk_level=risk_level,
                breaking_count=breaking_count,
                coverage_gap_count=coverage_gap_count,
            )
            rollout_percentages = self._rollout_percentages(
                risk_level=risk_level,
                breaking_count=breaking_count,
            )
            flag_key = self._flag_key(
                prefix=flag_key_prefix,
                objective=objective,
                affected_features=affected_features,
                ticket_id=ticket_id,
            )
            rollout_phases = self._rollout_phases(
                percentages=rollout_percentages,
                risk_level=risk_level,
                regression_scope=regression_scope,
            )
            monitoring = self._monitoring_plan(
                risk_level=risk_level,
                regression_scope=regression_scope,
                coverage_gap_count=coverage_gap_count,
            )

            top_features = [
                str(item.get("feature_name", "")).strip()
                for item in affected_features[:4]
                if str(item.get("feature_name", "")).strip()
            ]

            strategy: Dict[str, Any] = {
                "flag_key": flag_key,
                "mode": strategy_mode,
                "environments": envs,
                "default_state": {
                    "dev": "enabled_for_testing",
                    "staging": "disabled_by_default",
                    "production": "disabled_by_default",
                },
                "targeting_rules": [
                    "Allow internal staff cohort first",
                    "Promote to low-risk tenant/account cohort next",
                    "Expand to general population by rollout phase percentages",
                ],
                "rollout_phases": rollout_phases,
                "monitoring": monitoring,
                "operational_policies": [
                    "Require on-call owner during each production phase transition",
                    "Hold promotion when alert thresholds are exceeded",
                    "Document final flag cleanup date once rollout reaches 100%",
                ],
            }

            if include_kill_switch:
                strategy["kill_switch"] = {
                    "enabled": True,
                    "expectation": "Global flag disable path must complete within 5 minutes",
                    "trigger_conditions": [
                        "Error rate increase above agreed threshold",
                        "SLO breach sustained > 10 minutes",
                        "Critical customer-impacting incident",
                    ],
                    "actions": [
                        f"Set `{flag_key}` to disabled globally",
                        "Pause rollout progression",
                        "Execute rollback procedure if stability does not recover",
                    ],
                }

            if include_experiment_support:
                strategy["experiment_support"] = {
                    "enabled": True,
                    "variant_model": "control vs treatment",
                    "allocation_guidance": "Start with 90/10 split and rebalance as confidence improves",
                    "success_metrics": [
                        "Primary business KPI",
                        "Error rate and latency guardrails",
                        "User support ticket trend",
                    ],
                }

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Roll out changes safely with feature flags",
                "feature_flag_strategy": strategy,
                "summary": {
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "breaking_change_count": breaking_count,
                    "coverage_gap_count": coverage_gap_count,
                    "changed_file_count": len(changed_paths),
                    "affected_feature_count": len(affected_features),
                    "top_affected_features": top_features,
                    "phase_count": len(rollout_phases),
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _normalize_environments(self, environments: Optional[List[str]]) -> List[str]:
        raw = environments or ["dev", "staging", "production"]
        ordered: List[str] = []
        seen: Set[str] = set()
        for env in raw:
            token = re.sub(r"[^a-z0-9_-]+", "", str(env).strip().lower())
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        if "production" not in seen:
            ordered.append("production")
        return ordered

    def _strategy_mode(
        self,
        risk_level: str,
        breaking_count: int,
        coverage_gap_count: int,
    ) -> str:
        if breaking_count > 0:
            return "compatibility_first_progressive_rollout"
        if risk_level in {"critical", "high"}:
            return "conservative_canary_rollout"
        if coverage_gap_count > 0:
            return "guardrailed_staged_rollout"
        return "standard_gradual_rollout"

    def _rollout_percentages(self, risk_level: str, breaking_count: int) -> List[int]:
        if breaking_count > 0 or risk_level == "critical":
            return [1, 5, 10, 25, 50, 100]
        if risk_level == "high":
            return [5, 10, 25, 50, 100]
        if risk_level == "medium":
            return [10, 25, 50, 100]
        return [25, 50, 100]

    def _flag_key(
        self,
        prefix: str,
        objective: Optional[str],
        affected_features: List[Dict[str, Any]],
        ticket_id: Optional[str],
    ) -> str:
        safe_prefix = re.sub(r"[^a-z0-9_]+", "_", str(prefix or "ff").strip().lower()).strip("_")
        if not safe_prefix:
            safe_prefix = "ff"

        source = objective or ""
        if not source and affected_features:
            source = str(affected_features[0].get("feature_name", ""))
        slug = self._slugify(source, max_tokens=5) or "change"

        ticket_token = self._ticket_token(ticket_id)
        if ticket_token:
            return f"{safe_prefix}_{ticket_token.lower()}_{slug}"
        return f"{safe_prefix}_{slug}"

    def _rollout_phases(
        self,
        percentages: List[int],
        risk_level: str,
        regression_scope: str,
    ) -> List[Dict[str, Any]]:
        phases: List[Dict[str, Any]] = []
        for idx, pct in enumerate(percentages, start=1):
            phases.append(
                {
                    "phase_number": idx,
                    "exposure_percentage": pct,
                    "audience": self._phase_audience(idx, pct),
                    "promotion_criteria": [
                        "No Sev1/Sev2 incidents in phase window",
                        "Error/latency metrics remain within guardrails",
                        f"Regression checks ({regression_scope}) remain healthy",
                    ],
                    "hold_conditions": [
                        "Material KPI degradation",
                        "Alert threshold breach",
                        "Unexpected support escalation",
                    ],
                    "minimum_observation_window": self._observation_window(
                        risk_level=risk_level,
                        percentage=pct,
                    ),
                }
            )
        return phases

    def _phase_audience(self, phase_number: int, percentage: int) -> str:
        if phase_number == 1:
            return "internal users / staff accounts"
        if percentage <= 10:
            return "early-adopter low-risk cohort"
        if percentage <= 50:
            return "broader low/medium-risk cohort"
        if percentage < 100:
            return "general user population"
        return "all users"

    def _observation_window(self, risk_level: str, percentage: int) -> str:
        if risk_level in {"critical", "high"}:
            return "4-24 hours depending on traffic volume"
        if percentage < 50:
            return "2-8 hours"
        return "1-4 hours"

    def _monitoring_plan(
        self,
        risk_level: str,
        regression_scope: str,
        coverage_gap_count: int,
    ) -> Dict[str, Any]:
        thresholds = {
            "error_rate": "no more than +0.5% absolute increase",
            "latency_p95": "no more than +10% increase",
            "availability": "must remain within service SLO target",
        }
        if risk_level in {"critical", "high"}:
            thresholds["error_rate"] = "no more than +0.2% absolute increase"
            thresholds["latency_p95"] = "no more than +5% increase"

        checks = [
            "Service health dashboards",
            "Error logs with flag-enabled dimension",
            f"Automated {regression_scope} verification",
        ]
        if coverage_gap_count > 0:
            checks.append("Manual exploratory check for known coverage gaps")

        return {
            "thresholds": thresholds,
            "checks": checks,
            "owner_roles": ["on-call engineer", "QA owner", "release manager"],
        }

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else ""
        normalized = re.sub(r"[^A-Z0-9]+", "-", compact).strip("-")
        return normalized[:32]

    def _slugify(self, text: str, max_tokens: int = 5) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip().lower()).strip("-")
        if not cleaned:
            return ""
        tokens = [token for token in cleaned.split("-") if token]
        return "-".join(tokens[:max_tokens]) if tokens else ""

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        flag_key_prefix: str = "ff",
        environments: Optional[List[str]] = None,
        include_kill_switch: bool = True,
        include_experiment_support: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            flag_key_prefix=flag_key_prefix,
            environments=environments,
            include_kill_switch=include_kill_switch,
            include_experiment_support=include_experiment_support,
        )


class GenerateMultiPhaseRolloutPlanInput(BaseModel):
    """Input schema for GenerateMultiPhaseRolloutPlanTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional objective used to frame rollout plan phases",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 283, TICKET-283, PROJ-123)",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    environments: List[str] = Field(
        default_factory=lambda: ["dev", "staging", "production"],
        description="Ordered environments for rollout progression",
    )
    max_phases: int = Field(
        default=7,
        ge=3,
        le=12,
        description="Maximum number of rollout phases to generate",
    )
    include_command_examples: bool = Field(
        default=True,
        description="Include command/action examples for phase transitions",
    )
    include_rollback_handoffs: bool = Field(
        default=True,
        description="Include explicit rollback handoff points between phases",
    )


class GenerateMultiPhaseRolloutPlanTool(BaseTool):
    """Generate multi-phase rollout plans for complex changes."""

    name: str = "generate_multi_phase_rollout_plan"
    description: str = """
    Generate a multi-phase rollout plan for complex changes.
    Combines risk, testing, breaking-change, feature-impact, flag, and rollback signals into staged deployment phases.
    """
    args_schema: Type[BaseModel] = GenerateMultiPhaseRolloutPlanInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)
        self._flags = GenerateFeatureFlagStrategyTool(base_path=self._base_path)
        self._rollback = GenerateRollbackProcedureTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        environments: Optional[List[str]] = None,
        max_phases: int = 7,
        include_command_examples: bool = True,
        include_rollback_handoffs: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=10,
            )
            flag_result = self._flags._run(
                directory_path=directory_path,
                objective=objective,
                ticket_id=ticket_id,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                environments=environments,
                include_kill_switch=True,
                include_experiment_support=True,
            )
            rollback_result = self._rollback._run(
                directory_path=directory_path,
                objective=objective,
                ticket_id=ticket_id,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                include_command_examples=include_command_examples,
                include_data_safety_checks=True,
            )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            coverage_gap_count = (
                int(test_result.get("summary", {}).get("coverage_gap_count", 0))
                if test_result.get("status") == "success"
                else 0
            )
            impacted_tests = (
                sorted(set(test_result.get("impacted_tests", [])))
                if test_result.get("status") == "success"
                else []
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            complexity = self._complexity_profile(
                changed_file_count=len(changed_paths),
                risk_level=risk_level,
                breaking_count=breaking_count,
                affected_feature_count=len(affected_features),
                regression_scope=regression_scope,
                coverage_gap_count=coverage_gap_count,
            )

            envs = self._normalize_environments(environments)
            flag_strategy = (
                flag_result.get("feature_flag_strategy", {})
                if flag_result.get("status") == "success"
                else {}
            )
            flag_key = str(flag_strategy.get("flag_key", "")).strip() or self._default_flag_key(
                objective=objective,
                ticket_id=ticket_id,
            )
            suggested_exposures = self._exposure_schedule(
                complexity_level=complexity["level"],
                risk_level=risk_level,
                flag_strategy=flag_strategy,
            )

            rollout_phases = self._build_rollout_phases(
                complexity_level=complexity["level"],
                objective=objective,
                environments=envs,
                exposures=suggested_exposures,
                risk_level=risk_level,
                regression_scope=regression_scope,
                impacted_tests=impacted_tests,
                affected_features=affected_features,
                flag_key=flag_key,
                max_phases=max_phases,
                include_command_examples=include_command_examples,
                include_rollback_handoffs=include_rollback_handoffs,
            )

            rollback_triggers = (
                rollback_result.get("rollback_plan", {}).get("triggers", [])
                if rollback_result.get("status") == "success"
                else []
            )

            release_readiness = self._release_readiness_checks(
                risk_level=risk_level,
                regression_scope=regression_scope,
                breaking_count=breaking_count,
                coverage_gap_count=coverage_gap_count,
            )

            top_features = [
                str(item.get("feature_name", "")).strip()
                for item in affected_features[:5]
                if str(item.get("feature_name", "")).strip()
            ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Roll out complex change safely in phases",
                "multi_phase_rollout_plan": {
                    "complexity_profile": complexity,
                    "flag_key": flag_key,
                    "environments": envs,
                    "phase_count": len(rollout_phases),
                    "phases": rollout_phases,
                    "rollback_handoffs": rollback_triggers[:5],
                    "release_readiness_checks": release_readiness,
                },
                "summary": {
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "changed_file_count": len(changed_paths),
                    "breaking_change_count": breaking_count,
                    "coverage_gap_count": coverage_gap_count,
                    "affected_feature_count": len(affected_features),
                    "top_affected_features": top_features,
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                    "feature_flags": flag_result.get("status"),
                    "rollback_plan": rollback_result.get("status"),
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _complexity_profile(
        self,
        changed_file_count: int,
        risk_level: str,
        breaking_count: int,
        affected_feature_count: int,
        regression_scope: str,
        coverage_gap_count: int,
    ) -> Dict[str, Any]:
        score = 0
        score += min(10, changed_file_count // 3)
        score += min(8, affected_feature_count * 2)
        score += min(10, breaking_count * 4)
        score += min(6, coverage_gap_count * 2)

        risk_points = {"low": 0, "medium": 3, "high": 6, "critical": 9}
        score += risk_points.get(risk_level, 2)

        regression_points = {
            "smoke": 0,
            "targeted_regression": 2,
            "broad_regression": 4,
            "full_suite": 6,
        }
        score += regression_points.get(regression_scope.lower(), 1)

        if score >= 26:
            level = "highly_complex"
        elif score >= 16:
            level = "complex"
        elif score >= 9:
            level = "moderate"
        else:
            level = "standard"

        return {
            "level": level,
            "score": score,
            "signals": {
                "changed_file_count": changed_file_count,
                "affected_feature_count": affected_feature_count,
                "breaking_change_count": breaking_count,
                "coverage_gap_count": coverage_gap_count,
            },
        }

    def _normalize_environments(self, environments: Optional[List[str]]) -> List[str]:
        raw = environments or ["dev", "staging", "production"]
        cleaned: List[str] = []
        seen: Set[str] = set()
        for env in raw:
            token = re.sub(r"[^a-z0-9_-]+", "", str(env).strip().lower())
            if not token or token in seen:
                continue
            seen.add(token)
            cleaned.append(token)
        if "production" not in seen:
            cleaned.append("production")
        return cleaned

    def _default_flag_key(self, objective: Optional[str], ticket_id: Optional[str]) -> str:
        slug = self._slugify(objective or "", max_tokens=4) or "change"
        ticket = self._ticket_token(ticket_id)
        if ticket:
            return f"ff_{ticket.lower()}_{slug}"
        return f"ff_{slug}"

    def _exposure_schedule(
        self,
        complexity_level: str,
        risk_level: str,
        flag_strategy: Dict[str, Any],
    ) -> List[int]:
        candidate = []
        for phase in flag_strategy.get("rollout_phases", []):
            try:
                candidate.append(int(phase.get("exposure_percentage", 0)))
            except Exception:
                continue
        candidate = sorted({v for v in candidate if v > 0})
        if candidate:
            return candidate

        if complexity_level == "highly_complex" or risk_level == "critical":
            return [1, 5, 10, 20, 40, 70, 100]
        if complexity_level == "complex" or risk_level == "high":
            return [5, 10, 25, 50, 75, 100]
        if complexity_level == "moderate":
            return [10, 25, 50, 100]
        return [25, 50, 100]

    def _build_rollout_phases(
        self,
        complexity_level: str,
        objective: Optional[str],
        environments: List[str],
        exposures: List[int],
        risk_level: str,
        regression_scope: str,
        impacted_tests: List[str],
        affected_features: List[Dict[str, Any]],
        flag_key: str,
        max_phases: int,
        include_command_examples: bool,
        include_rollback_handoffs: bool,
    ) -> List[Dict[str, Any]]:
        phase_names = [
            "Preparation",
            "Internal Validation",
            "Canary Rollout",
            "Limited Cohort Expansion",
            "Broad Rollout",
            "General Availability",
            "Post-Launch Stabilization",
        ]
        top_features = [
            str(item.get("feature_name", "")).strip()
            for item in affected_features[:3]
            if str(item.get("feature_name", "")).strip()
        ]
        phase_count = min(max_phases, max(3, len(exposures) + 1))
        phases: List[Dict[str, Any]] = []

        for idx in range(phase_count):
            phase_number = idx + 1
            name = phase_names[idx] if idx < len(phase_names) else f"Phase {phase_number}"
            exposure = 0 if idx == 0 else exposures[min(idx - 1, len(exposures) - 1)]
            environment = environments[min(idx, len(environments) - 1)]
            checks = [
                "No Sev1/Sev2 incidents during observation window",
                "Error rate and latency within thresholds",
                f"Regression scope `{regression_scope}` remains healthy",
            ]
            if impacted_tests:
                checks.append(f"Targeted checks include: {', '.join(impacted_tests[:6])}")

            phase = {
                "phase_number": phase_number,
                "name": name,
                "environment": environment,
                "target_exposure_percentage": exposure,
                "objective": objective or "Deliver change safely with progressive exposure",
                "focus_features": top_features,
                "entry_criteria": self._entry_criteria(phase_number, complexity_level, risk_level),
                "rollout_actions": [
                    f"Adjust flag `{flag_key}` to {exposure}%" if exposure > 0 else "Keep feature flag disabled in preparation phase",
                    "Monitor service and business metrics during observation window",
                    "Record decision to advance, hold, or rollback",
                ],
                "validation_gates": checks,
                "exit_criteria": self._exit_criteria(phase_number, phase_count),
                "minimum_observation_window": self._phase_window(
                    complexity_level=complexity_level,
                    risk_level=risk_level,
                    phase_number=phase_number,
                ),
            }
            if include_command_examples:
                phase["command_examples"] = [
                    "# Update feature flag using your flag provider CLI/API",
                    f"# Set {flag_key} exposure to {exposure}%",
                ]
            if include_rollback_handoffs:
                phase["rollback_handoff"] = {
                    "ready": True,
                    "trigger": "Any critical incident or sustained KPI regression",
                    "action": "Pause progression and execute rollback plan",
                }
            phases.append(phase)

        return phases

    def _entry_criteria(self, phase_number: int, complexity_level: str, risk_level: str) -> List[str]:
        criteria = ["Previous phase exit criteria completed"]
        if phase_number == 1:
            criteria = [
                "Feature flag integrated and disabled by default",
                "Baseline metrics and alerts configured",
                "Rollback plan reviewed by on-call owner",
            ]
        if complexity_level in {"complex", "highly_complex"} or risk_level in {"high", "critical"}:
            criteria.append("QA and release manager approval recorded")
        return criteria

    def _exit_criteria(self, phase_number: int, phase_count: int) -> List[str]:
        if phase_number < phase_count:
            return [
                "Metrics stable through observation window",
                "No unresolved high-severity issues",
                "Approval granted for next phase promotion",
            ]
        return [
            "100% exposure stable for observation window",
            "Incident rate at or below baseline",
            "Flag cleanup/deprecation work item created",
        ]

    def _phase_window(self, complexity_level: str, risk_level: str, phase_number: int) -> str:
        if complexity_level == "highly_complex" or risk_level == "critical":
            return "8-24 hours"
        if complexity_level == "complex" or risk_level == "high":
            return "4-12 hours"
        if phase_number <= 2:
            return "2-6 hours"
        return "1-4 hours"

    def _release_readiness_checks(
        self,
        risk_level: str,
        regression_scope: str,
        breaking_count: int,
        coverage_gap_count: int,
    ) -> List[str]:
        checks = [
            "Observability dashboards and alerts validated",
            f"Regression plan ready for `{regression_scope}` scope",
            "On-call ownership confirmed for rollout window",
        ]
        if breaking_count > 0:
            checks.append("Compatibility communication plan sent to dependent teams")
        if coverage_gap_count > 0:
            checks.append("Known coverage gaps documented with manual validation checklist")
        if risk_level in {"high", "critical"}:
            checks.append("Go/no-go checkpoint scheduled before each production phase")
        return checks

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else ""
        normalized = re.sub(r"[^A-Z0-9]+", "-", compact).strip("-")
        return normalized[:32]

    def _slugify(self, text: str, max_tokens: int = 5) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip().lower()).strip("-")
        if not cleaned:
            return ""
        tokens = [token for token in cleaned.split("-") if token]
        return "-".join(tokens[:max_tokens]) if tokens else ""

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        environments: Optional[List[str]] = None,
        max_phases: int = 7,
        include_command_examples: bool = True,
        include_rollback_handoffs: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            environments=environments,
            max_phases=max_phases,
            include_command_examples=include_command_examples,
            include_rollback_handoffs=include_rollback_handoffs,
        )


class GenerateDatabaseMigrationStrategyInput(BaseModel):
    """Input schema for GenerateDatabaseMigrationStrategyTool."""

    directory_path: str = Field(default=".", description="Directory within a git repository")
    objective: Optional[str] = Field(
        default=None,
        description="Optional objective used to frame migration strategy",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Optional ticket/work-item id (e.g. 284, TICKET-284, PROJ-123)",
    )
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="Optional changed file list to scope analysis",
    )
    base_ref: Optional[str] = Field(
        default=None,
        description="Base git ref for comparison (e.g. main, HEAD~1)",
    )
    target_ref: Optional[str] = Field(
        default=None,
        description="Target git ref for comparison; omitted means working tree",
    )
    include_untracked: bool = Field(
        default=True,
        description="Include untracked files when using working tree mode",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    max_downstream_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max depth for downstream dependency tracing",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Optional extension filter",
    )
    database_engine: str = Field(
        default="unknown",
        description="Database engine hint (postgres, mysql, sqlite, mssql, etc.)",
    )
    migration_tool: Optional[str] = Field(
        default=None,
        description="Migration tool hint (alembic, flyway, liquibase, django, prisma, etc.)",
    )
    deployment_environment: str = Field(
        default="production",
        description="Environment target for migration strategy",
    )
    include_online_migration_controls: bool = Field(
        default=True,
        description="Include online migration controls (batched backfills, concurrent index guidance)",
    )
    include_rollback_plan: bool = Field(
        default=True,
        description="Include explicit rollback strategy and triggers",
    )
    include_command_examples: bool = Field(
        default=True,
        description="Include migration command examples",
    )


class GenerateDatabaseMigrationStrategyTool(BaseTool):
    """Generate database migration strategy for safe schema/data evolution."""

    name: str = "generate_database_migration_strategy"
    description: str = """
    Generate a database migration strategy with phased execution and safety controls.
    Uses impact/risk/test/breaking/type signals to recommend migration pattern and rollback plan.
    """
    args_schema: Type[BaseModel] = GenerateDatabaseMigrationStrategyInput

    _MIGRATION_HINTS: Set[str] = {
        "migration",
        "migrations",
        "schema",
        "ddl",
        "dml",
        "model",
        "models",
        "entity",
        "entities",
        "sql",
        "database",
        "db",
        "prisma",
        "alembic",
        "flyway",
        "liquibase",
    }

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._impact = ClassifyFileImpactTool(base_path=self._base_path)
        self._risk = AssessRiskLevelTool(base_path=self._base_path)
        self._test = AssessTestImpactTool(base_path=self._base_path)
        self._breaking = DetectBreakingChangesTool(base_path=self._base_path)
        self._type = AnalyzeTypeSystemChangesTool(base_path=self._base_path)
        self._features = IdentifyAffectedFeaturesTool(base_path=self._base_path)
        self._rollback = GenerateRollbackProcedureTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        database_engine: str = "unknown",
        migration_tool: Optional[str] = None,
        deployment_environment: str = "production",
        include_online_migration_controls: bool = True,
        include_rollback_plan: bool = True,
        include_command_examples: bool = True,
    ) -> Dict[str, Any]:
        try:
            impact_result = self._impact._run(
                directory_path=directory_path,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            if impact_result.get("status") != "success":
                return impact_result

            selected_paths = {
                str(path).replace("\\", "/").strip()
                for path in (changed_files or [])
                if str(path).strip()
            }
            file_impacts = impact_result.get("file_impacts", [])
            if selected_paths:
                file_impacts = [
                    item
                    for item in file_impacts
                    if str(item.get("path", "")).replace("\\", "/") in selected_paths
                ]

            changed_paths = sorted(
                {str(item.get("path", "")).replace("\\", "/").strip() for item in file_impacts if item.get("path")}
            )
            if not changed_paths and selected_paths:
                changed_paths = sorted(selected_paths)

            risk_result = self._risk._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            test_result = self._test._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
            )
            breaking_result = self._breaking._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            type_result = self._type._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                extensions=extensions,
            )
            feature_result = self._features._run(
                directory_path=directory_path,
                changed_files=changed_paths or None,
                base_ref=base_ref,
                target_ref=target_ref,
                include_untracked=include_untracked,
                recursive=recursive,
                max_downstream_depth=max_downstream_depth,
                extensions=extensions,
                max_features=8,
            )

            rollback_result: Dict[str, Any] = {}
            if include_rollback_plan:
                rollback_result = self._rollback._run(
                    directory_path=directory_path,
                    objective=objective,
                    ticket_id=ticket_id,
                    changed_files=changed_paths or None,
                    base_ref=base_ref,
                    target_ref=target_ref,
                    include_untracked=include_untracked,
                    recursive=recursive,
                    max_downstream_depth=max_downstream_depth,
                    extensions=extensions,
                    deployment_environment=deployment_environment,
                    include_command_examples=include_command_examples,
                    include_data_safety_checks=True,
                )

            risk_level = str(risk_result.get("risk_level", "unknown")) if risk_result.get("status") == "success" else "unknown"
            regression_scope = (
                str(test_result.get("summary", {}).get("regression_scope", "unknown"))
                if test_result.get("status") == "success"
                else "unknown"
            )
            coverage_gap_count = (
                int(test_result.get("summary", {}).get("coverage_gap_count", 0))
                if test_result.get("status") == "success"
                else 0
            )
            breaking_count = int(breaking_result.get("summary", {}).get("breaking_change_count", 0)) if breaking_result.get("status") == "success" else 0
            type_finding_count = int(type_result.get("summary", {}).get("finding_count", 0)) if type_result.get("status") == "success" else 0
            affected_features = feature_result.get("affected_features", []) if feature_result.get("status") == "success" else []

            migration_candidates = [path for path in changed_paths if self._is_migration_related(path)]
            schema_candidates = [path for path in migration_candidates if self._is_schema_change(path)]
            data_candidates = [path for path in migration_candidates if self._is_data_change(path)]
            model_candidates = [path for path in changed_paths if self._is_model_file(path)]

            strategy_mode = self._strategy_mode(
                risk_level=risk_level,
                breaking_count=breaking_count,
                schema_change_count=len(schema_candidates),
                data_change_count=len(data_candidates),
                deployment_environment=deployment_environment,
            )
            lock_risk = self._lock_risk(
                strategy_mode=strategy_mode,
                risk_level=risk_level,
                schema_change_count=len(schema_candidates),
                engine=database_engine,
            )
            resolved_tool = self._resolve_migration_tool(
                migration_tool=migration_tool,
                changed_paths=changed_paths,
            )

            phases = self._build_migration_phases(
                strategy_mode=strategy_mode,
                database_engine=database_engine,
                migration_tool=resolved_tool,
                migration_candidates=migration_candidates,
                schema_candidates=schema_candidates,
                data_candidates=data_candidates,
                model_candidates=model_candidates,
                regression_scope=regression_scope,
                include_online_migration_controls=include_online_migration_controls,
                include_command_examples=include_command_examples,
            )

            top_features = [
                str(item.get("feature_name", "")).strip()
                for item in affected_features[:4]
                if str(item.get("feature_name", "")).strip()
            ]
            rollback_hints = []
            if rollback_result.get("status") == "success":
                rollback_hints = rollback_result.get("rollback_plan", {}).get("triggers", [])[:4]

            ticket_token = self._ticket_token(ticket_id)
            return {
                "status": "success",
                "directory_path": directory_path,
                "objective": objective or "Evolve database schema/data safely with controlled migration",
                "database_migration_strategy": {
                    "ticket": ticket_token or None,
                    "strategy_mode": strategy_mode,
                    "database_engine": database_engine,
                    "migration_tool": resolved_tool,
                    "deployment_environment": deployment_environment,
                    "lock_risk": lock_risk,
                    "migration_artifacts": {
                        "migration_files": migration_candidates[:20],
                        "schema_files": schema_candidates[:20],
                        "data_files": data_candidates[:20],
                        "model_files": model_candidates[:20],
                    },
                    "phases": phases,
                    "safety_controls": [
                        "Backup/snapshot before migration execution",
                        "Track migration duration and row-lock indicators",
                        "Gate promotion on service + data integrity checks",
                    ],
                    "verification_checks": [
                        "Schema diff matches expected target state",
                        "Data consistency checks pass (counts/checksums/invariants)",
                        f"Regression validation complete ({regression_scope})",
                    ],
                    "rollback_hints": rollback_hints,
                },
                "summary": {
                    "risk_level": risk_level,
                    "regression_scope": regression_scope,
                    "breaking_change_count": breaking_count,
                    "type_finding_count": type_finding_count,
                    "coverage_gap_count": coverage_gap_count,
                    "changed_file_count": len(changed_paths),
                    "migration_file_count": len(migration_candidates),
                    "schema_change_count": len(schema_candidates),
                    "data_change_count": len(data_candidates),
                    "affected_feature_count": len(affected_features),
                    "top_affected_features": top_features,
                    "phase_count": len(phases),
                },
                "signal_status": {
                    "impact": impact_result.get("status"),
                    "risk": risk_result.get("status"),
                    "test_impact": test_result.get("status"),
                    "breaking_changes": breaking_result.get("status"),
                    "type_changes": type_result.get("status"),
                    "feature_impact": feature_result.get("status"),
                    "rollback_plan": rollback_result.get("status") if rollback_result else "skipped",
                },
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _is_migration_related(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        ext = Path(normalized).suffix.lower()
        if ext in {".sql"}:
            return True
        tokens = [token for token in re.split(r"[\\/._-]+", normalized) if token]
        return any(token in self._MIGRATION_HINTS for token in tokens)

    def _is_schema_change(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        ext = Path(normalized).suffix.lower()
        if ext in {".sql"} and any(k in normalized for k in ["schema", "ddl", "alter", "create", "drop"]):
            return True
        return any(k in normalized for k in ["schema", "model", "entity", "table", "column", "migration"])

    def _is_data_change(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        return any(k in normalized for k in ["seed", "backfill", "data", "dml", "populate"])

    def _is_model_file(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        ext = Path(normalized).suffix.lower()
        if ext not in {".py", ".ts", ".tsx", ".js", ".java", ".go", ".cs", ".rb", ".php"}:
            return False
        return any(k in normalized for k in ["model", "entity", "schema", "orm", "prisma"])

    def _strategy_mode(
        self,
        risk_level: str,
        breaking_count: int,
        schema_change_count: int,
        data_change_count: int,
        deployment_environment: str,
    ) -> str:
        env = str(deployment_environment).strip().lower()
        if breaking_count > 0 or schema_change_count >= 3 or env == "production":
            return "expand_contract"
        if risk_level in {"high", "critical"} or data_change_count > 0:
            return "staged_migration"
        return "direct_migration"

    def _lock_risk(
        self,
        strategy_mode: str,
        risk_level: str,
        schema_change_count: int,
        engine: str,
    ) -> str:
        engine_token = str(engine or "").strip().lower()
        if strategy_mode == "expand_contract":
            return "medium"
        if risk_level in {"high", "critical"} or schema_change_count >= 2:
            return "medium"
        if engine_token in {"sqlite"}:
            return "medium"
        return "low"

    def _resolve_migration_tool(
        self,
        migration_tool: Optional[str],
        changed_paths: List[str],
    ) -> str:
        if migration_tool:
            return str(migration_tool).strip().lower()
        joined = " ".join(path.lower() for path in changed_paths)
        if "alembic" in joined:
            return "alembic"
        if "prisma" in joined:
            return "prisma"
        if "flyway" in joined:
            return "flyway"
        if "liquibase" in joined:
            return "liquibase"
        if "manage.py" in joined or "django" in joined:
            return "django"
        return "custom_sql"

    def _build_migration_phases(
        self,
        strategy_mode: str,
        database_engine: str,
        migration_tool: str,
        migration_candidates: List[str],
        schema_candidates: List[str],
        data_candidates: List[str],
        model_candidates: List[str],
        regression_scope: str,
        include_online_migration_controls: bool,
        include_command_examples: bool,
    ) -> List[Dict[str, Any]]:
        phases: List[Dict[str, Any]] = []

        phase_defs = [
            (
                "Pre-Migration Readiness",
                [
                    "Confirm migration ordering and idempotency",
                    "Validate backups/snapshots and recovery access",
                    f"Review target engine specifics: {database_engine}",
                ],
            ),
            (
                "Expand Schema Safely",
                [
                    "Apply additive schema changes first (new nullable columns/tables/indexes)",
                    "Avoid destructive operations in this phase",
                    f"Apply migration artifacts: {', '.join(schema_candidates[:8]) or 'none'}",
                ],
            ),
            (
                "Backfill And Dual-Write",
                [
                    "Backfill new schema in batches with progress checkpoints",
                    "Enable dual-write/read compatibility path in application",
                    f"Data scripts: {', '.join(data_candidates[:8]) or 'none'}",
                ],
            ),
            (
                "Cutover And Contract",
                [
                    "Switch application reads/writes to new schema paths",
                    "Run integrity checks and target regression suite",
                    "Remove deprecated schema only after stability window passes",
                ],
            ),
            (
                "Post-Migration Verification",
                [
                    "Compare key counts/checksums between old and new paths",
                    f"Run {regression_scope} validation and monitor production metrics",
                    f"Review model/schema alignment: {', '.join(model_candidates[:8]) or 'none'}",
                ],
            ),
        ]

        if strategy_mode == "direct_migration":
            phase_defs = [
                phase_defs[0],
                (
                    "Apply Migration",
                    [
                        f"Execute migration files: {', '.join(migration_candidates[:10]) or 'none'}",
                        "Run post-migration smoke checks immediately",
                        "Prepare fast rollback window if metrics degrade",
                    ],
                ),
                phase_defs[-1],
            ]
        elif strategy_mode == "staged_migration":
            phase_defs = [phase_defs[0], phase_defs[1], phase_defs[2], phase_defs[-1]]

        for idx, (name, actions) in enumerate(phase_defs, start=1):
            phase: Dict[str, Any] = {
                "phase_number": idx,
                "name": name,
                "actions": actions,
                "entry_criteria": [
                    "Previous phase marked complete",
                    "No unresolved critical alerts",
                ] if idx > 1 else [
                    "Migration plan approved by backend + DBA owners",
                    "Backup and rollback checkpoints confirmed",
                ],
                "exit_criteria": [
                    "Phase actions completed",
                    "Verification checks pass for this phase",
                ],
            }
            if include_online_migration_controls and name in {"Expand Schema Safely", "Backfill And Dual-Write"}:
                phase["online_controls"] = [
                    "Use small migration batches to limit lock duration",
                    "Prefer concurrent/online index creation when supported",
                    "Throttle backfill load based on DB health metrics",
                ]
            if include_command_examples:
                phase["command_examples"] = self._migration_commands(migration_tool=migration_tool)
            phases.append(phase)

        return phases

    def _migration_commands(self, migration_tool: str) -> List[str]:
        tool = str(migration_tool or "").strip().lower()
        if tool == "alembic":
            return [
                "alembic current",
                "alembic upgrade head",
                "alembic downgrade -1",
            ]
        if tool == "django":
            return [
                "python manage.py showmigrations",
                "python manage.py migrate",
                "python manage.py migrate <app_name> <previous_migration>",
            ]
        if tool == "prisma":
            return [
                "npx prisma migrate status",
                "npx prisma migrate deploy",
                "npx prisma migrate resolve --rolled-back <migration_name>",
            ]
        if tool == "flyway":
            return [
                "flyway info",
                "flyway migrate",
                "flyway undo",
            ]
        if tool == "liquibase":
            return [
                "liquibase status",
                "liquibase update",
                "liquibase rollbackCount 1",
            ]
        return [
            "# Execute SQL migration scripts using your database deployment pipeline",
            "# Validate applied schema version after execution",
            "# Revert using pre-defined rollback SQL or versioned migration tool",
        ]

    def _ticket_token(self, ticket_id: Optional[str]) -> str:
        raw = str(ticket_id or "").strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw).upper()
        if compact.isdigit():
            return f"TICKET-{compact}"
        if re.fullmatch(r"[A-Z]+-\d+", compact):
            return compact
        if re.fullmatch(r"TICKET-?\d+", compact):
            digits = re.sub(r"\D", "", compact)
            return f"TICKET-{digits}" if digits else ""
        normalized = re.sub(r"[^A-Z0-9]+", "-", compact).strip("-")
        return normalized[:32]

    async def _arun(
        self,
        directory_path: str = ".",
        objective: Optional[str] = None,
        ticket_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        include_untracked: bool = True,
        recursive: bool = True,
        max_downstream_depth: int = 6,
        extensions: Optional[List[str]] = None,
        database_engine: str = "unknown",
        migration_tool: Optional[str] = None,
        deployment_environment: str = "production",
        include_online_migration_controls: bool = True,
        include_rollback_plan: bool = True,
        include_command_examples: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            objective=objective,
            ticket_id=ticket_id,
            changed_files=changed_files,
            base_ref=base_ref,
            target_ref=target_ref,
            include_untracked=include_untracked,
            recursive=recursive,
            max_downstream_depth=max_downstream_depth,
            extensions=extensions,
            database_engine=database_engine,
            migration_tool=migration_tool,
            deployment_environment=deployment_environment,
            include_online_migration_controls=include_online_migration_controls,
            include_rollback_plan=include_rollback_plan,
            include_command_examples=include_command_examples,
        )


class InferArchitectureInput(BaseModel):
    """Input schema for InferArchitectureTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    recursive: bool = Field(default=True, description="Scan recursively")
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved imports in dependency analysis",
    )
    use_llm: bool = Field(
        default=True,
        description="Attempt LLM-assisted architecture inference",
    )


class InferArchitectureTool(BaseTool):
    """Infer architecture from codebase structure, dependencies, and metrics."""

    name: str = "infer_architecture"
    description: str = """
    Infer architecture patterns/components from a codebase.
    Uses static heuristics and optional LLM synthesis.
    """
    args_schema: Type[BaseModel] = InferArchitectureInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._scan = ScanDirectoryTool(base_path=self._base_path)
        self._graph = BuildDependencyGraphTool(base_path=self._base_path)
        self._metrics = GenerateCodebaseMetricsTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        try:
            root_path = Path(directory_path)
            if not root_path.is_absolute():
                root_path = Path(self._base_path) / root_path
            root_path = root_path.resolve()

            scan_result = self._scan._run(directory_path=directory_path, recursive=recursive)
            if scan_result.get("status") != "success":
                return scan_result

            graph_result = self._graph._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external=include_external_dependencies,
            )
            if graph_result.get("status") != "success":
                return graph_result

            metrics_result = self._metrics._run(
                directory_path=directory_path,
                recursive=recursive,
                include_unknown=False,
            )
            if metrics_result.get("status") != "success":
                return metrics_result

            files = scan_result.get("files", [])
            component_inventory = self._build_component_inventory(files, root_path)
            inferred_patterns = self._infer_patterns(
                component_inventory=component_inventory,
                graph_summary=graph_result.get("summary", {}),
                language_stats=metrics_result.get("language_stats", {}),
            )
            heuristics_summary = self._compose_heuristic_summary(
                component_inventory=component_inventory,
                inferred_patterns=inferred_patterns,
                metrics_result=metrics_result,
                graph_result=graph_result,
            )

            llm_result = None
            architecture_summary = heuristics_summary
            analysis_backend = "heuristic"

            if use_llm:
                llm_result = self._infer_with_llm(
                    directory_path=directory_path,
                    component_inventory=component_inventory,
                    inferred_patterns=inferred_patterns,
                    metrics_result=metrics_result,
                    graph_result=graph_result,
                    heuristics_summary=heuristics_summary,
                )
                if llm_result.get("status") == "success":
                    architecture_summary = llm_result.get("summary", heuristics_summary)
                    analysis_backend = "heuristic+llm"

            context, containers = self._build_c4_candidates(
                component_inventory=component_inventory,
                inferred_patterns=inferred_patterns,
                language_stats=metrics_result.get("language_stats", {}),
            )

            response = {
                "status": "success",
                "directory_path": directory_path,
                "analysis_backend": analysis_backend,
                "architecture_summary": architecture_summary,
                "heuristic_summary": heuristics_summary,
                "inferred_patterns": inferred_patterns,
                "component_inventory": component_inventory,
                "dependency_signals": {
                    "node_count": graph_result.get("node_count", 0),
                    "edge_count": graph_result.get("edge_count", 0),
                    "cycle_count": len(graph_result.get("cycles", [])),
                    "unresolved_import_count": graph_result.get("summary", {}).get(
                        "unresolved_import_count",
                        0,
                    ),
                    "external_edge_count": graph_result.get("summary", {}).get(
                        "external_edge_count",
                        0,
                    ),
                },
                "metrics_summary": {
                    "analyzed_files": metrics_result.get("analyzed_files", 0),
                    "total_loc": metrics_result.get("total_loc", 0),
                    "language_percentages": metrics_result.get("language_percentages", {}),
                    "average_cyclomatic_complexity": metrics_result.get(
                        "average_cyclomatic_complexity",
                        0.0,
                    ),
                },
                "c4_candidates": {
                    "context": context,
                    "containers": containers,
                },
            }
            if llm_result is not None:
                response["llm_analysis"] = llm_result
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _build_component_inventory(
        self,
        files: List[Dict[str, Any]],
        root_path: Path,
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for f in files:
            raw_path = Path(str(f.get("path", ""))).resolve()
            try:
                rel_path = raw_path.relative_to(root_path).as_posix()
            except Exception:
                rel_path = raw_path.as_posix()
            parts = [p for p in rel_path.split("/") if p]
            component_name = parts[0] if parts else "root"
            bucket = grouped.setdefault(
                component_name,
                {
                    "name": component_name,
                    "classification": self._classify_component(component_name),
                    "file_count": 0,
                    "languages": {},
                    "sample_paths": [],
                },
            )
            bucket["file_count"] += 1
            language = f.get("language", "unknown")
            bucket["languages"][language] = bucket["languages"].get(language, 0) + 1
            if len(bucket["sample_paths"]) < 5:
                bucket["sample_paths"].append(rel_path)

        components = sorted(grouped.values(), key=lambda item: item["file_count"], reverse=True)
        return components

    def _classify_component(self, name: str) -> str:
        token = name.lower()
        if any(k in token for k in ["api", "route", "controller", "handler"]):
            return "api"
        if any(k in token for k in ["service", "domain", "core"]):
            return "service"
        if any(k in token for k in ["repo", "repository", "dao"]):
            return "repository"
        if any(k in token for k in ["model", "schema", "entity", "migration", "db", "database"]):
            return "data"
        if any(k in token for k in ["web", "ui", "frontend", "client", "components", "pages"]):
            return "frontend"
        if any(k in token for k in ["worker", "jobs", "queue", "consumer", "producer"]):
            return "worker"
        if any(k in token for k in ["test", "tests", "spec"]):
            return "test"
        if any(k in token for k in ["infra", "deploy", "k8s", "terraform", "helm"]):
            return "infrastructure"
        return "module"

    def _infer_patterns(
        self,
        component_inventory: List[Dict[str, Any]],
        graph_summary: Dict[str, Any],
        language_stats: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        component_types = {c.get("classification", "module") for c in component_inventory}
        cycle_count = int(graph_summary.get("cycle_count", 0))
        unresolved = int(graph_summary.get("unresolved_import_count", 0))
        languages = set(language_stats.keys())
        patterns: List[Dict[str, Any]] = []

        if {"api", "service", "repository", "data"}.issubset(component_types):
            patterns.append(
                {
                    "pattern": "layered_architecture",
                    "confidence": 0.86,
                    "evidence": "Detected api/service/repository/data component layers",
                }
            )
        if "frontend" in component_types and "api" in component_types:
            patterns.append(
                {
                    "pattern": "client_server",
                    "confidence": 0.78,
                    "evidence": "Separate frontend and API-oriented backend components",
                }
            )
        service_like = [
            c for c in component_inventory if c.get("classification") in {"service", "worker"}
        ]
        if len(service_like) >= 3:
            patterns.append(
                {
                    "pattern": "service_oriented",
                    "confidence": 0.72,
                    "evidence": f"Multiple service/worker components detected ({len(service_like)})",
                }
            )
        if any(c.get("classification") == "infrastructure" for c in component_inventory):
            patterns.append(
                {
                    "pattern": "infrastructure_as_code",
                    "confidence": 0.64,
                    "evidence": "Infrastructure/deployment modules present",
                }
            )
        if {"typescript", "javascript", "python", "java", "go", "csharp"} & languages and len(languages) >= 2:
            patterns.append(
                {
                    "pattern": "polyglot_codebase",
                    "confidence": 0.68,
                    "evidence": f"Multiple implementation languages detected ({', '.join(sorted(languages))})",
                }
            )
        if cycle_count > 0:
            patterns.append(
                {
                    "pattern": "cyclic_dependency_hotspot",
                    "confidence": 0.74,
                    "evidence": f"Detected {cycle_count} dependency cycle(s)",
                }
            )
        if unresolved > 0:
            patterns.append(
                {
                    "pattern": "external_dependency_boundary",
                    "confidence": 0.61,
                    "evidence": f"{unresolved} unresolved imports indicate external integrations",
                }
            )
        if not patterns:
            patterns.append(
                {
                    "pattern": "modular_monolith",
                    "confidence": 0.66,
                    "evidence": "Single repo with internal modules and no strong distributed signals",
                }
            )
        return patterns

    def _compose_heuristic_summary(
        self,
        component_inventory: List[Dict[str, Any]],
        inferred_patterns: List[Dict[str, Any]],
        metrics_result: Dict[str, Any],
        graph_result: Dict[str, Any],
    ) -> str:
        top_components = ", ".join(
            f"{c['name']} ({c['classification']}, {c['file_count']} files)"
            for c in component_inventory[:5]
        ) or "no major components detected"
        patterns = ", ".join(p["pattern"] for p in inferred_patterns[:4])
        loc = metrics_result.get("total_loc", 0)
        languages = ", ".join(sorted(metrics_result.get("language_stats", {}).keys()))
        cycles = len(graph_result.get("cycles", []))
        unresolved = graph_result.get("summary", {}).get("unresolved_import_count", 0)
        return (
            f"Heuristic architecture inference indicates: {patterns}. "
            f"Primary components: {top_components}. "
            f"Codebase size is ~{loc} LOC across languages: {languages or 'unknown'}. "
            f"Dependency graph shows {cycles} cycle(s) and {unresolved} unresolved import edges."
        )

    def _build_c4_candidates(
        self,
        component_inventory: List[Dict[str, Any]],
        inferred_patterns: List[Dict[str, Any]],
        language_stats: Dict[str, Dict[str, Any]],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        dominant_languages = sorted(
            language_stats.items(),
            key=lambda item: item[1].get("loc", 0),
            reverse=True,
        )
        primary_language = dominant_languages[0][0] if dominant_languages else "unknown"
        context = {
            "system": "Inferred Brownfield System",
            "primary_language": primary_language,
            "architecture_patterns": [p["pattern"] for p in inferred_patterns[:5]],
        }
        containers = []
        for component in component_inventory[:12]:
            containers.append(
                {
                    "name": component["name"],
                    "type": component["classification"],
                    "file_count": component["file_count"],
                    "languages": component["languages"],
                }
            )
        return context, containers

    def _infer_with_llm(
        self,
        directory_path: str,
        component_inventory: List[Dict[str, Any]],
        inferred_patterns: List[Dict[str, Any]],
        metrics_result: Dict[str, Any],
        graph_result: Dict[str, Any],
        heuristics_summary: str,
    ) -> Dict[str, Any]:
        prompt_payload = {
            "directory_path": directory_path,
            "heuristic_summary": heuristics_summary,
            "patterns": inferred_patterns[:8],
            "component_inventory": component_inventory[:15],
            "metrics_summary": {
                "total_loc": metrics_result.get("total_loc", 0),
                "analyzed_files": metrics_result.get("analyzed_files", 0),
                "language_stats": metrics_result.get("language_stats", {}),
                "average_cyclomatic_complexity": metrics_result.get(
                    "average_cyclomatic_complexity",
                    0.0,
                ),
            },
            "dependency_summary": graph_result.get("summary", {}),
        }
        prompt = (
            "Infer the current software architecture from the analysis JSON. "
            "Return concise plain text with: "
            "1) architecture style, "
            "2) major components and responsibilities, "
            "3) boundaries/integrations, "
            "4) top architectural risks.\n\n"
            f"{json.dumps(prompt_payload, indent=2)}"
        )

        try:
            from backend.core.llm import TaskComplexity, get_llm_client, select_model

            async def _call_llm() -> str:
                llm = get_llm_client()
                selection = select_model(TaskComplexity.COMPLEX)
                generation = await llm.agenerate(
                    prompt=prompt,
                    system_message=(
                        "You are a principal software architect analyzing an existing codebase. "
                        "Stay factual and avoid speculation."
                    ),
                    model=selection.model_name if hasattr(selection, "model_name") else None,
                )
                return getattr(generation, "text", None) or str(generation)

            llm_summary = self._run_async_sync(_call_llm())
            return {"status": "success", "summary": llm_summary}
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def _run_async_sync(self, coro: Any) -> Any:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop.is_running():
            result_holder: Dict[str, Any] = {}
            error_holder: Dict[str, Exception] = {}

            def _runner() -> None:
                try:
                    result_holder["result"] = asyncio.run(coro)
                except Exception as thread_exc:
                    error_holder["error"] = thread_exc

            import threading

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            thread.join()
            if "error" in error_holder:
                raise error_holder["error"]
            return result_holder.get("result")

        return asyncio.run(coro)

    async def _arun(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            recursive=recursive,
            include_external_dependencies=include_external_dependencies,
            use_llm=use_llm,
        )


class GenerateComponentInventoryInput(BaseModel):
    """Input schema for GenerateComponentInventoryTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    recursive: bool = Field(default=True, description="Scan recursively")
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved/external dependencies in summary counts",
    )
    include_unknown_languages: bool = Field(
        default=False,
        description="Include unknown language files in code metrics calculations",
    )


class GenerateComponentInventoryTool(BaseTool):
    """Generate classified component inventory enriched with dependency and LOC metrics."""

    name: str = "generate_component_inventory"
    description: str = """
    Generate a component inventory with inferred classifications.
    Enriches each component with file, language, dependency, cycle, and LOC signals.
    """
    args_schema: Type[BaseModel] = GenerateComponentInventoryInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._scan = ScanDirectoryTool(base_path=self._base_path)
        self._graph = BuildDependencyGraphTool(base_path=self._base_path)
        self._metrics = GenerateCodebaseMetricsTool(base_path=self._base_path)
        self._infer = InferArchitectureTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        include_unknown_languages: bool = False,
    ) -> Dict[str, Any]:
        try:
            root_path = Path(directory_path)
            if not root_path.is_absolute():
                root_path = Path(self._base_path) / root_path
            root_path = root_path.resolve()

            scan_result = self._scan._run(directory_path=directory_path, recursive=recursive)
            if scan_result.get("status") != "success":
                return scan_result

            graph_result = self._graph._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external=include_external_dependencies,
            )
            if graph_result.get("status") != "success":
                return graph_result

            metrics_result = self._metrics._run(
                directory_path=directory_path,
                recursive=recursive,
                include_unknown=include_unknown_languages,
            )
            if metrics_result.get("status") != "success":
                return metrics_result

            files = scan_result.get("files", [])
            base_inventory = self._infer._build_component_inventory(files, root_path)
            components = self._enrich_components(
                root_path=root_path,
                files=files,
                base_inventory=base_inventory,
                graph_result=graph_result,
                metrics_result=metrics_result,
            )

            classification_summary = self._build_classification_summary(components)
            total_components = len(components)
            total_files = sum(int(component.get("file_count", 0)) for component in components)
            total_loc = sum(int(component.get("loc", 0)) for component in components)
            high_risk_components = [
                component["name"] for component in components if component.get("risk_level") in {"high", "critical"}
            ]

            return {
                "status": "success",
                "directory_path": directory_path,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "component_inventory": components,
                "classification_summary": classification_summary,
                "summary": {
                    "component_count": total_components,
                    "file_count": total_files,
                    "total_loc": total_loc,
                    "classification_count": len(classification_summary),
                    "high_risk_component_count": len(high_risk_components),
                    "high_risk_components": high_risk_components[:10],
                },
                "dependency_summary": graph_result.get("summary", {}),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _enrich_components(
        self,
        root_path: Path,
        files: List[Dict[str, Any]],
        base_inventory: List[Dict[str, Any]],
        graph_result: Dict[str, Any],
        metrics_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        enriched: Dict[str, Dict[str, Any]] = {
            str(component.get("name", "")): {
                "name": str(component.get("name", "")),
                "classification": str(component.get("classification", "module")),
                "file_count": int(component.get("file_count", 0)),
                "languages": dict(component.get("languages", {})),
                "sample_paths": list(component.get("sample_paths", [])),
                "loc": 0,
                "average_file_loc": 0.0,
                "average_cyclomatic_complexity": 0.0,
                "max_cyclomatic_complexity": 0,
                "dependency_counts": {
                    "inbound": 0,
                    "outbound": 0,
                    "internal": 0,
                    "external_outbound": 0,
                },
                "cycle_participation_count": 0,
                "risk_level": "low",
            }
            for component in base_inventory
            if component.get("name")
        }

        file_to_component: Dict[str, str] = {}
        for file_entry in files:
            rel_path = self._relative_to_root(file_entry.get("path", ""), root_path)
            component_name = self._component_from_rel_path(rel_path)
            file_to_component[rel_path] = component_name
            if component_name not in enriched:
                enriched[component_name] = self._new_component(component_name)

        metrics_by_path: Dict[str, Dict[str, Any]] = {
            str(item.get("path", "")): item for item in metrics_result.get("file_metrics", [])
        }
        for rel_path, metric in metrics_by_path.items():
            component_name = file_to_component.get(rel_path, self._component_from_rel_path(rel_path))
            component = enriched.setdefault(component_name, self._new_component(component_name))
            component["loc"] += int(metric.get("loc", 0))
            complexity = int(metric.get("cyclomatic_complexity", 0))
            component["max_cyclomatic_complexity"] = max(component["max_cyclomatic_complexity"], complexity)
            component.setdefault("_complexity_total", 0)
            component.setdefault("_complexity_count", 0)
            component["_complexity_total"] += complexity
            component["_complexity_count"] += 1

        for edge in graph_result.get("edges", []):
            source = str(edge.get("source", "")).strip()
            source_component = file_to_component.get(source, self._component_from_rel_path(source))
            source_bucket = enriched.setdefault(source_component, self._new_component(source_component))

            if edge.get("is_external"):
                source_bucket["dependency_counts"]["external_outbound"] += 1
                continue

            target = str(edge.get("target", "")).strip()
            target_component = file_to_component.get(target, self._component_from_rel_path(target))
            target_bucket = enriched.setdefault(target_component, self._new_component(target_component))

            if source_component == target_component:
                source_bucket["dependency_counts"]["internal"] += 1
            else:
                source_bucket["dependency_counts"]["outbound"] += 1
                target_bucket["dependency_counts"]["inbound"] += 1

        for cycle in graph_result.get("cycles", []):
            if not isinstance(cycle, list):
                continue
            cycle_components = {
                file_to_component.get(str(path), self._component_from_rel_path(str(path))) for path in cycle
            }
            for component_name in cycle_components:
                if component_name not in enriched:
                    enriched[component_name] = self._new_component(component_name)
                enriched[component_name]["cycle_participation_count"] += 1

        ranked_components: List[Dict[str, Any]] = []
        for component in enriched.values():
            files_in_component = int(component.get("file_count", 0))
            if files_in_component > 0:
                component["average_file_loc"] = round(component.get("loc", 0) / files_in_component, 2)
            complexity_count = int(component.pop("_complexity_count", 0))
            complexity_total = int(component.pop("_complexity_total", 0))
            component["average_cyclomatic_complexity"] = (
                round(complexity_total / complexity_count, 2) if complexity_count > 0 else 0.0
            )
            component["risk_level"] = self._risk_level(component)
            ranked_components.append(component)

        ranked_components.sort(
            key=lambda item: (
                int(item.get("file_count", 0)),
                int(item.get("loc", 0)),
                int(item.get("dependency_counts", {}).get("inbound", 0)),
            ),
            reverse=True,
        )
        return ranked_components

    def _relative_to_root(self, raw_path: str, root_path: Path) -> str:
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = (root_path / path).resolve()
        else:
            path = path.resolve()
        try:
            return path.relative_to(root_path).as_posix()
        except Exception:
            return path.as_posix()

    def _component_from_rel_path(self, rel_path: str) -> str:
        normalized = str(rel_path).replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part]
        return parts[0] if parts else "root"

    def _new_component(self, component_name: str) -> Dict[str, Any]:
        return {
            "name": component_name,
            "classification": self._infer._classify_component(component_name),
            "file_count": 0,
            "languages": {},
            "sample_paths": [],
            "loc": 0,
            "average_file_loc": 0.0,
            "average_cyclomatic_complexity": 0.0,
            "max_cyclomatic_complexity": 0,
            "dependency_counts": {
                "inbound": 0,
                "outbound": 0,
                "internal": 0,
                "external_outbound": 0,
            },
            "cycle_participation_count": 0,
            "risk_level": "low",
        }

    def _risk_level(self, component: Dict[str, Any]) -> str:
        deps = component.get("dependency_counts", {})
        inbound = int(deps.get("inbound", 0))
        outbound = int(deps.get("outbound", 0))
        cycles = int(component.get("cycle_participation_count", 0))
        max_complexity = int(component.get("max_cyclomatic_complexity", 0))
        score = (cycles * 3) + (1 if inbound >= 10 else 0) + (1 if outbound >= 10 else 0)
        score += 1 if max_complexity >= 25 else 0
        if cycles >= 2 and max_complexity >= 35:
            return "critical"
        if score >= 5:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _build_classification_summary(self, components: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        summary: Dict[str, Dict[str, Any]] = {}
        for component in components:
            classification = str(component.get("classification", "module"))
            bucket = summary.setdefault(
                classification,
                {
                    "component_count": 0,
                    "file_count": 0,
                    "loc": 0,
                    "risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                },
            )
            bucket["component_count"] += 1
            bucket["file_count"] += int(component.get("file_count", 0))
            bucket["loc"] += int(component.get("loc", 0))
            risk = str(component.get("risk_level", "low"))
            if risk in bucket["risk_distribution"]:
                bucket["risk_distribution"][risk] += 1
        return dict(sorted(summary.items(), key=lambda item: item[0]))

    async def _arun(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        include_unknown_languages: bool = False,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            recursive=recursive,
            include_external_dependencies=include_external_dependencies,
            include_unknown_languages=include_unknown_languages,
        )


class GenerateC4ModelInput(BaseModel):
    """Input schema for GenerateC4ModelTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    recursive: bool = Field(default=True, description="Scan recursively")
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved imports in dependency model",
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM to enrich C4 descriptions when available",
    )
    system_name: Optional[str] = Field(
        default=None,
        description="Optional explicit system name",
    )
    max_components_per_container: int = Field(
        default=12,
        description="Limit component nodes per container for readability",
    )


class GenerateC4ModelTool(BaseTool):
    """Generate C4 model data for Context, Container, and Component views."""

    name: str = "generate_c4_model"
    description: str = """
    Generate C4 model structures (Context, Container, Component)
    from architecture inference and dependency analysis.
    """
    args_schema: Type[BaseModel] = GenerateC4ModelInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._infer_architecture = InferArchitectureTool(base_path=self._base_path)
        self._scan = ScanDirectoryTool(base_path=self._base_path)
        self._graph = BuildDependencyGraphTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
    ) -> Dict[str, Any]:
        try:
            root_path = Path(directory_path)
            if not root_path.is_absolute():
                root_path = Path(self._base_path) / root_path
            root_path = root_path.resolve()

            architecture = self._infer_architecture._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external_dependencies=include_external_dependencies,
                use_llm=use_llm,
            )
            if architecture.get("status") != "success":
                return architecture

            scan_result = self._scan._run(
                directory_path=directory_path,
                recursive=recursive,
            )
            if scan_result.get("status") != "success":
                return scan_result

            graph_result = self._graph._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external=include_external_dependencies,
            )
            if graph_result.get("status") != "success":
                return graph_result

            component_inventory = architecture.get("component_inventory", [])
            inferred_patterns = architecture.get("inferred_patterns", [])
            metrics_summary = architecture.get("metrics_summary", {})
            system_name = (system_name or self._derive_system_name(directory_path)).strip()

            context_view = self._build_context_view(
                system_name=system_name,
                component_inventory=component_inventory,
                inferred_patterns=inferred_patterns,
                dependency_summary=graph_result.get("summary", {}),
                metrics_summary=metrics_summary,
            )

            containers = self._build_containers(
                component_inventory=component_inventory,
                max_count=20,
            )
            container_relationships = self._build_container_relationships(
                edges=graph_result.get("edges", []),
                containers=containers,
            )

            components_by_container = self._build_components_by_container(
                files=scan_result.get("files", []),
                containers=containers,
                root_path=root_path,
                max_components=max_components_per_container,
            )
            component_relationships = self._build_component_relationships(
                edges=graph_result.get("edges", []),
                components_by_container=components_by_container,
            )

            llm_enrichment = None
            if use_llm:
                llm_enrichment = self._enrich_c4_with_llm(
                    system_name=system_name,
                    context_view=context_view,
                    containers=containers,
                    container_relationships=container_relationships,
                    components_by_container=components_by_container,
                    component_relationships=component_relationships,
                    architecture_summary=architecture.get("architecture_summary", ""),
                )
                if llm_enrichment.get("status") == "success":
                    self._apply_llm_enrichment(
                        context_view=context_view,
                        containers=containers,
                        components_by_container=components_by_container,
                        enrichment=llm_enrichment.get("enrichment", {}),
                    )

            response = {
                "status": "success",
                "directory_path": directory_path,
                "system_name": system_name,
                "analysis_backend": (
                    "heuristic+llm"
                    if llm_enrichment and llm_enrichment.get("status") == "success"
                    else "heuristic"
                ),
                "architecture_summary": architecture.get("architecture_summary"),
                "c4_model": {
                    "context": context_view,
                    "container": {
                        "system": system_name,
                        "containers": containers,
                        "relationships": container_relationships,
                    },
                    "component": {
                        "containers": components_by_container,
                        "relationships": component_relationships,
                    },
                },
                "diagram_specs": {
                    "context_description": self._context_description(context_view),
                    "container_description": self._container_description(
                        system_name, containers, container_relationships
                    ),
                    "component_description": self._component_description(
                        components_by_container, component_relationships
                    ),
                },
            }
            if llm_enrichment is not None:
                response["llm_enrichment"] = llm_enrichment
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _derive_system_name(self, directory_path: str) -> str:
        name = Path(directory_path).name.strip()
        if not name or name == ".":
            name = Path(self._base_path).name.strip() or "Inferred System"
        clean = re.sub(r"[_\-]+", " ", name).strip()
        return clean.title() if clean else "Inferred System"

    def _build_context_view(
        self,
        system_name: str,
        component_inventory: List[Dict[str, Any]],
        inferred_patterns: List[Dict[str, Any]],
        dependency_summary: Dict[str, Any],
        metrics_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        actors = [
            {
                "name": "End User",
                "type": "person",
                "description": "Primary user interacting with the system",
            }
        ]
        has_frontend = any(c.get("classification") == "frontend" for c in component_inventory)
        if has_frontend:
            actors.append(
                {
                    "name": "Operator",
                    "type": "person",
                    "description": "Operational user managing system behavior",
                }
            )

        external_systems: List[Dict[str, Any]] = []
        unresolved = int(dependency_summary.get("unresolved_import_count", 0))
        if unresolved > 0:
            external_systems.append(
                {
                    "name": "External Services",
                    "type": "software_system",
                    "description": f"Unresolved dependencies ({unresolved}) suggest external integrations",
                }
            )

        patterns = [p.get("pattern") for p in inferred_patterns[:6]]
        return {
            "system": {
                "name": system_name,
                "description": (
                    f"Inferred system handling approximately {metrics_summary.get('total_loc', 0)} LOC "
                    f"with architecture patterns: {', '.join(patterns) if patterns else 'unknown'}."
                ),
            },
            "actors": actors,
            "external_systems": external_systems,
            "relationships": self._build_context_relationships(
                system_name=system_name,
                has_frontend=has_frontend,
                has_external=bool(external_systems),
            ),
        }

    def _build_context_relationships(
        self,
        system_name: str,
        has_frontend: bool,
        has_external: bool,
    ) -> List[Dict[str, str]]:
        relationships = []
        entry_point = "Frontend" if has_frontend else system_name
        relationships.append(
            {
                "source": "End User",
                "target": entry_point,
                "description": "Uses system capabilities",
            }
        )
        if has_frontend:
            relationships.append(
                {
                    "source": "Frontend",
                    "target": system_name,
                    "description": "Calls backend APIs",
                }
            )
        if has_external:
            relationships.append(
                {
                    "source": system_name,
                    "target": "External Services",
                    "description": "Integrates with external dependencies",
                }
            )
        return relationships

    def _build_containers(
        self,
        component_inventory: List[Dict[str, Any]],
        max_count: int = 20,
    ) -> List[Dict[str, Any]]:
        containers: List[Dict[str, Any]] = []
        for component in component_inventory[:max_count]:
            languages = component.get("languages", {})
            primary_language = "unknown"
            if languages:
                primary_language = max(languages.items(), key=lambda item: item[1])[0]
            containers.append(
                {
                    "id": component.get("name"),
                    "name": component.get("name"),
                    "type": component.get("classification", "module"),
                    "technology": self._technology_label(primary_language),
                    "description": self._container_description_from_type(
                        component.get("classification", "module")
                    ),
                    "file_count": component.get("file_count", 0),
                    "languages": languages,
                }
            )
        return containers

    def _technology_label(self, language: str) -> str:
        mapping = {
            "python": "Python",
            "javascript": "JavaScript/Node.js",
            "typescript": "TypeScript/Node.js",
            "java": "Java",
            "go": "Go",
            "csharp": "C#/.NET",
            "php": "PHP",
            "ruby": "Ruby",
            "rust": "Rust",
        }
        return mapping.get(language, language or "Unknown")

    def _container_description_from_type(self, classification: str) -> str:
        mapping = {
            "api": "Handles API endpoints and request routing",
            "service": "Implements business workflows and domain logic",
            "repository": "Provides persistence access patterns",
            "data": "Defines data models and schema concerns",
            "frontend": "Presents UI and client-side interactions",
            "worker": "Executes asynchronous/background processing",
            "infrastructure": "Contains deployment/runtime infrastructure",
            "test": "Contains test specifications and test utilities",
            "module": "General-purpose module",
        }
        return mapping.get(classification, "General-purpose module")

    def _build_container_relationships(
        self,
        edges: List[Dict[str, Any]],
        containers: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        container_ids = {c.get("id") for c in containers}
        counts: Dict[tuple[str, str], int] = {}

        for edge in edges:
            if edge.get("is_external"):
                continue
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            src_container = self._top_component(source)
            tgt_container = self._top_component(target)
            if src_container == tgt_container:
                continue
            if src_container not in container_ids or tgt_container not in container_ids:
                continue
            key = (src_container, tgt_container)
            counts[key] = counts.get(key, 0) + 1

        relationships = []
        for (source, target), weight in sorted(counts.items(), key=lambda item: item[1], reverse=True):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "description": f"Depends on {target}",
                    "weight": weight,
                }
            )
        return relationships

    def _build_components_by_container(
        self,
        files: List[Dict[str, Any]],
        containers: List[Dict[str, Any]],
        root_path: Path,
        max_components: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        container_ids = {c.get("id") for c in containers}
        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {cid: {} for cid in container_ids if cid}

        for f in files:
            raw_path = Path(str(f.get("path", ""))).resolve()
            try:
                path = raw_path.relative_to(root_path).as_posix()
            except Exception:
                path = raw_path.as_posix()
            parts = [p for p in path.split("/") if p]
            if not parts:
                continue
            container = parts[0]
            if container not in grouped:
                continue
            component_key = parts[1] if len(parts) > 2 else Path(parts[-1]).stem
            bucket = grouped[container].setdefault(
                component_key,
                {
                    "id": f"{container}.{component_key}",
                    "name": component_key,
                    "description": "Inferred component from file structure",
                    "file_count": 0,
                    "language": f.get("language", "unknown"),
                },
            )
            bucket["file_count"] += 1

        result: Dict[str, List[Dict[str, Any]]] = {}
        for container, comp_map in grouped.items():
            ranked = sorted(comp_map.values(), key=lambda item: item["file_count"], reverse=True)
            result[container] = ranked[: max(1, max_components)]
        return result

    def _build_component_relationships(
        self,
        edges: List[Dict[str, Any]],
        components_by_container: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        component_lookup: Dict[tuple[str, str], str] = {}
        for container, components in components_by_container.items():
            for component in components:
                component_lookup[(container, component["name"])] = component["id"]

        relationships: Dict[str, List[Dict[str, Any]]] = {
            container: [] for container in components_by_container
        }
        seen: Set[tuple[str, str, str]] = set()

        for edge in edges:
            if edge.get("is_external"):
                continue
            source_path = str(edge.get("source", ""))
            target_path = str(edge.get("target", ""))
            source_parts = [p for p in Path(source_path).as_posix().split("/") if p]
            target_parts = [p for p in Path(target_path).as_posix().split("/") if p]
            if len(source_parts) < 2 or len(target_parts) < 2:
                continue

            src_container = source_parts[0]
            tgt_container = target_parts[0]
            if src_container != tgt_container:
                continue
            if src_container not in components_by_container:
                continue

            src_component_name = source_parts[1] if len(source_parts) > 2 else Path(source_parts[-1]).stem
            tgt_component_name = target_parts[1] if len(target_parts) > 2 else Path(target_parts[-1]).stem
            src_id = component_lookup.get((src_container, src_component_name))
            tgt_id = component_lookup.get((tgt_container, tgt_component_name))
            if not src_id or not tgt_id or src_id == tgt_id:
                continue
            key = (src_container, src_id, tgt_id)
            if key in seen:
                continue
            seen.add(key)
            relationships[src_container].append(
                {
                    "source": src_id,
                    "target": tgt_id,
                    "description": "Internal dependency",
                }
            )

        return relationships

    def _top_component(self, path: str) -> str:
        parts = [p for p in Path(path).as_posix().split("/") if p]
        return parts[0] if parts else "root"

    def _enrich_c4_with_llm(
        self,
        system_name: str,
        context_view: Dict[str, Any],
        containers: List[Dict[str, Any]],
        container_relationships: List[Dict[str, Any]],
        components_by_container: Dict[str, List[Dict[str, Any]]],
        component_relationships: Dict[str, List[Dict[str, Any]]],
        architecture_summary: str,
    ) -> Dict[str, Any]:
        payload = {
            "system_name": system_name,
            "context": context_view,
            "containers": containers,
            "container_relationships": container_relationships,
            "components_by_container": components_by_container,
            "component_relationships": component_relationships,
            "architecture_summary": architecture_summary,
        }
        prompt = (
            "You are refining a C4 model draft. Return JSON only with keys: "
            "`system_description` (string), "
            "`container_descriptions` (object keyed by container id), "
            "`component_descriptions` (object keyed by component id). "
            "Keep descriptions concise and factual.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )

        try:
            from backend.core.llm import TaskComplexity, get_llm_client, select_model

            async def _call_llm() -> str:
                llm = get_llm_client()
                selection = select_model(TaskComplexity.MODERATE)
                generation = await llm.agenerate(
                    prompt=prompt,
                    system_message=(
                        "You are a software architect producing strict JSON output."
                    ),
                    model=selection.model_name if hasattr(selection, "model_name") else None,
                )
                return getattr(generation, "text", None) or str(generation)

            raw = self._run_async_sync(_call_llm())
            parsed = self._parse_json_object(raw)
            if not isinstance(parsed, dict):
                return {"status": "unavailable", "error": "LLM response was not valid JSON object"}
            return {"status": "success", "enrichment": parsed}
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def _parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None

    def _apply_llm_enrichment(
        self,
        context_view: Dict[str, Any],
        containers: List[Dict[str, Any]],
        components_by_container: Dict[str, List[Dict[str, Any]]],
        enrichment: Dict[str, Any],
    ) -> None:
        system_desc = enrichment.get("system_description")
        if isinstance(system_desc, str) and system_desc.strip():
            context_view["system"]["description"] = system_desc.strip()

        container_desc = enrichment.get("container_descriptions", {})
        if isinstance(container_desc, dict):
            for container in containers:
                cid = container.get("id")
                desc = container_desc.get(cid)
                if isinstance(desc, str) and desc.strip():
                    container["description"] = desc.strip()

        component_desc = enrichment.get("component_descriptions", {})
        if isinstance(component_desc, dict):
            for container_components in components_by_container.values():
                for component in container_components:
                    cid = component.get("id")
                    desc = component_desc.get(cid)
                    if isinstance(desc, str) and desc.strip():
                        component["description"] = desc.strip()

    def _run_async_sync(self, coro: Any) -> Any:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop.is_running():
            result_holder: Dict[str, Any] = {}
            error_holder: Dict[str, Exception] = {}

            def _runner() -> None:
                try:
                    result_holder["result"] = asyncio.run(coro)
                except Exception as thread_exc:
                    error_holder["error"] = thread_exc

            import threading

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            thread.join()
            if "error" in error_holder:
                raise error_holder["error"]
            return result_holder.get("result")

        return asyncio.run(coro)

    def _context_description(self, context_view: Dict[str, Any]) -> str:
        system = context_view.get("system", {})
        actors = context_view.get("actors", [])
        externals = context_view.get("external_systems", [])
        return (
            f"System: {system.get('name', 'Unknown')} | "
            f"Actors: {', '.join(a.get('name', '?') for a in actors)} | "
            f"External systems: {', '.join(e.get('name', '?') for e in externals) or 'None'}"
        )

    def _container_description(
        self,
        system_name: str,
        containers: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        container_names = ", ".join(c.get("name", "?") for c in containers[:10]) or "None"
        return (
            f"{system_name} containers: {container_names}. "
            f"Inter-container relationships: {len(relationships)}."
        )

    def _component_description(
        self,
        components_by_container: Dict[str, List[Dict[str, Any]]],
        component_relationships: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        container_count = len(components_by_container)
        component_count = sum(len(v) for v in components_by_container.values())
        relationship_count = sum(len(v) for v in component_relationships.values())
        return (
            f"Component diagrams prepared for {container_count} container(s), "
            f"{component_count} component node(s), {relationship_count} relationship(s)."
        )

    async def _arun(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            recursive=recursive,
            include_external_dependencies=include_external_dependencies,
            use_llm=use_llm,
            system_name=system_name,
            max_components_per_container=max_components_per_container,
        )


class RenderC4MermaidInput(BaseModel):
    """Input schema for RenderC4MermaidTool."""

    directory_path: str = Field(default=".", description="Directory to analyze")
    recursive: bool = Field(default=True, description="Scan recursively")
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved imports in dependency model",
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM to enrich C4 descriptions when available",
    )
    system_name: Optional[str] = Field(default=None, description="Optional explicit system name")
    max_components_per_container: int = Field(
        default=12,
        description="Limit component nodes per container",
    )
    include_component_diagrams: bool = Field(
        default=True,
        description="Render component-level Mermaid diagrams per container",
    )


class RenderC4MermaidTool(BaseTool):
    """Render Mermaid diagrams from generated C4 model structures."""

    name: str = "render_c4_mermaid"
    description: str = """
    Render Mermaid diagrams for C4 context/container/component views.
    """
    args_schema: Type[BaseModel] = RenderC4MermaidInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._c4 = GenerateC4ModelTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
        include_component_diagrams: bool = True,
    ) -> Dict[str, Any]:
        try:
            c4_result = self._c4._run(
                directory_path=directory_path,
                recursive=recursive,
                include_external_dependencies=include_external_dependencies,
                use_llm=use_llm,
                system_name=system_name,
                max_components_per_container=max_components_per_container,
            )
            if c4_result.get("status") != "success":
                return c4_result

            c4_model = c4_result.get("c4_model", {})
            context_model = c4_model.get("context", {})
            container_model = c4_model.get("container", {})
            component_model = c4_model.get("component", {})

            context_mermaid = self._render_context_mermaid(context_model)
            container_mermaid = self._render_container_mermaid(container_model)
            component_mermaid: Dict[str, str] = {}

            if include_component_diagrams:
                for container_id, components in component_model.get("containers", {}).items():
                    component_mermaid[container_id] = self._render_component_mermaid(
                        container_id=container_id,
                        components=components,
                        relationships=component_model.get("relationships", {}).get(container_id, []),
                    )

            combined_markdown = self._render_combined_markdown(
                context_mermaid=context_mermaid,
                container_mermaid=container_mermaid,
                component_mermaid=component_mermaid,
            )

            return {
                "status": "success",
                "directory_path": directory_path,
                "system_name": c4_result.get("system_name"),
                "analysis_backend": c4_result.get("analysis_backend"),
                "c4_model": c4_model,
                "mermaid": {
                    "context": context_mermaid,
                    "container": container_mermaid,
                    "component": component_mermaid,
                    "combined_markdown": combined_markdown,
                },
                "diagram_count": 2 + len(component_mermaid),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _render_context_mermaid(self, context: Dict[str, Any]) -> str:
        lines: List[str] = ["flowchart LR"]
        system = context.get("system", {})
        actors = context.get("actors", [])
        externals = context.get("external_systems", [])
        relationships = context.get("relationships", [])

        node_ids: Dict[str, str] = {}

        def add_node(name: str, kind: str, desc: str = "") -> str:
            if name in node_ids:
                return node_ids[name]
            node_id = self._node_id(name, prefix=kind[:1].upper())
            label = self._label(f"{name}\\n{desc}" if desc else name)
            if kind == "person":
                lines.append(f'    {node_id}(["{label}"])')
            elif kind == "external":
                lines.append(f'    {node_id}[("{label}")]')
            else:
                lines.append(f'    {node_id}["{label}"]')
            node_ids[name] = node_id
            return node_id

        system_name = system.get("name", "System")
        add_node(system_name, "system", system.get("description", ""))
        for actor in actors:
            add_node(actor.get("name", "Actor"), "person", actor.get("description", ""))
        for external in externals:
            add_node(external.get("name", "External"), "external", external.get("description", ""))

        emitted_edges: Set[tuple[str, str, str]] = set()
        for rel in relationships:
            source = rel.get("source", "")
            target = rel.get("target", "")
            description = rel.get("description", "uses")
            if not source or not target:
                continue
            src_id = add_node(source, "person")
            tgt_id = add_node(target, "system")
            edge_key = (src_id, tgt_id, description)
            if edge_key in emitted_edges:
                continue
            emitted_edges.add(edge_key)
            lines.append(f'    {src_id} -->|"{self._label(description)}"| {tgt_id}')

        return "\n".join(lines)

    def _render_container_mermaid(self, container_model: Dict[str, Any]) -> str:
        lines: List[str] = ["flowchart LR"]
        system_name = container_model.get("system", "System")
        containers = container_model.get("containers", [])
        relationships = container_model.get("relationships", [])

        system_id = self._node_id(system_name, "SYS")
        lines.append(f'    {system_id}["{self._label(system_name)}"]')

        node_ids: Dict[str, str] = {}
        for container in containers:
            cid = str(container.get("id", container.get("name", "container")))
            name = str(container.get("name", cid))
            tech = str(container.get("technology", ""))
            label = f"{name}\\n[{tech}]" if tech else name
            node_id = self._node_id(cid, "CTR")
            node_ids[cid] = node_id
            lines.append(f'    {node_id}["{self._label(label)}"]')
            lines.append(f"    {system_id} --- {node_id}")

        emitted_edges: Set[tuple[str, str, str]] = set()
        for rel in relationships:
            source = str(rel.get("source", ""))
            target = str(rel.get("target", ""))
            desc = str(rel.get("description", "depends on"))
            if source not in node_ids or target not in node_ids:
                continue
            edge_key = (source, target, desc)
            if edge_key in emitted_edges:
                continue
            emitted_edges.add(edge_key)
            lines.append(
                f'    {node_ids[source]} -->|"{self._label(desc)}"| {node_ids[target]}'
            )

        return "\n".join(lines)

    def _render_component_mermaid(
        self,
        container_id: str,
        components: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        lines: List[str] = ["flowchart TB"]
        container_node = self._node_id(container_id, "CON")
        lines.append(f'    {container_node}["{self._label(container_id)}"]')

        node_ids: Dict[str, str] = {}
        for component in components:
            cid = str(component.get("id", component.get("name", "component")))
            name = str(component.get("name", cid))
            language = str(component.get("language", ""))
            label = f"{name}\\n({language})" if language and language != "unknown" else name
            node_id = self._node_id(cid, "CMP")
            node_ids[cid] = node_id
            lines.append(f'    {node_id}["{self._label(label)}"]')
            lines.append(f"    {container_node} --- {node_id}")

        emitted_edges: Set[tuple[str, str, str]] = set()
        for rel in relationships:
            source = str(rel.get("source", ""))
            target = str(rel.get("target", ""))
            desc = str(rel.get("description", "depends on"))
            if source not in node_ids or target not in node_ids:
                continue
            edge_key = (source, target, desc)
            if edge_key in emitted_edges:
                continue
            emitted_edges.add(edge_key)
            lines.append(
                f'    {node_ids[source]} -->|"{self._label(desc)}"| {node_ids[target]}'
            )

        return "\n".join(lines)

    def _render_combined_markdown(
        self,
        context_mermaid: str,
        container_mermaid: str,
        component_mermaid: Dict[str, str],
    ) -> str:
        chunks = [
            "## C4 Context Diagram",
            "```mermaid",
            context_mermaid,
            "```",
            "",
            "## C4 Container Diagram",
            "```mermaid",
            container_mermaid,
            "```",
        ]
        for container_id, diagram in component_mermaid.items():
            chunks.extend(
                [
                    "",
                    f"## C4 Component Diagram - {container_id}",
                    "```mermaid",
                    diagram,
                    "```",
                ]
            )
        return "\n".join(chunks).strip()

    def _node_id(self, name: str, prefix: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_]", "_", (name or "node").strip())
        base = re.sub(r"_+", "_", base).strip("_")
        if not base:
            base = "node"
        return f"{prefix}_{base}"

    def _label(self, text: str) -> str:
        clean = (text or "").replace('"', "'")
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def _arun(
        self,
        directory_path: str = ".",
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
        include_component_diagrams: bool = True,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            recursive=recursive,
            include_external_dependencies=include_external_dependencies,
            use_llm=use_llm,
            system_name=system_name,
            max_components_per_container=max_components_per_container,
            include_component_diagrams=include_component_diagrams,
        )


class ArchitectureAnnotationInterfaceInput(BaseModel):
    """Input schema for ArchitectureAnnotationInterfaceTool."""

    directory_path: str = Field(default=".", description="Directory to analyze if C4 model is not provided")
    c4_model: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional existing C4 model to annotate",
    )
    recursive: bool = Field(default=True, description="Scan recursively")
    include_external_dependencies: bool = Field(
        default=False,
        description="Include unresolved imports in dependency model",
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM when generating base C4 model",
    )
    system_name: Optional[str] = Field(default=None, description="Optional explicit system name")
    max_components_per_container: int = Field(
        default=12,
        description="Limit component nodes per container",
    )
    generate_questions: bool = Field(
        default=True,
        description="Generate user confirmation questions from inferred model",
    )
    max_questions: int = Field(default=20, description="Max annotation questions")
    annotations: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="User-provided annotation operations to apply",
    )


class ArchitectureAnnotationInterfaceTool(BaseTool):
    """User-guided interface for confirming and correcting inferred architecture."""

    name: str = "architecture_annotation_interface"
    description: str = """
    Present architecture confirmation questions and apply user annotations
    to C4 model structures (context/container/component).
    """
    args_schema: Type[BaseModel] = ArchitectureAnnotationInterfaceInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()
        self._c4 = GenerateC4ModelTool(base_path=self._base_path)

    def _run(
        self,
        directory_path: str = ".",
        c4_model: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
        generate_questions: bool = True,
        max_questions: int = 20,
        annotations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        try:
            source_result: Dict[str, Any] = {}
            base_c4_model: Dict[str, Any]
            resolved_system_name: str

            if c4_model is None:
                source_result = self._c4._run(
                    directory_path=directory_path,
                    recursive=recursive,
                    include_external_dependencies=include_external_dependencies,
                    use_llm=use_llm,
                    system_name=system_name,
                    max_components_per_container=max_components_per_container,
                )
                if source_result.get("status") != "success":
                    return source_result
                base_c4_model = deepcopy(source_result.get("c4_model", {}))
                resolved_system_name = str(
                    source_result.get("system_name")
                    or system_name
                    or Path(directory_path).name
                    or "Inferred System"
                )
            else:
                base_c4_model = deepcopy(c4_model)
                resolved_system_name = str(
                    system_name
                    or base_c4_model.get("context", {}).get("system", {}).get("name")
                    or Path(directory_path).name
                    or "Inferred System"
                )

            working_c4_model = deepcopy(base_c4_model)
            annotation_questions: List[Dict[str, Any]] = []
            if generate_questions:
                annotation_questions = self._generate_annotation_questions(
                    c4_model=working_c4_model,
                    max_questions=max_questions,
                )

            applied_annotations: List[Dict[str, Any]] = []
            rejected_annotations: List[Dict[str, Any]] = []
            if annotations:
                applied_annotations, rejected_annotations = self._apply_annotations(
                    c4_model=working_c4_model,
                    annotations=annotations,
                )

            response = {
                "status": "success",
                "directory_path": directory_path,
                "system_name": resolved_system_name,
                "annotation_schema": self._annotation_schema(),
                "annotation_questions": annotation_questions,
                "question_count": len(annotation_questions),
                "applied_annotations": applied_annotations,
                "rejected_annotations": rejected_annotations,
                "base_c4_model": base_c4_model,
                "annotated_c4_model": working_c4_model,
                "summary": {
                    "applied_count": len(applied_annotations),
                    "rejected_count": len(rejected_annotations),
                    "requires_user_review": len(annotation_questions) > 0,
                },
            }
            if source_result:
                response["source_analysis_backend"] = source_result.get("analysis_backend")
                if source_result.get("architecture_summary"):
                    response["architecture_summary"] = source_result.get("architecture_summary")
            return response
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_annotation_questions(
        self,
        c4_model: Dict[str, Any],
        max_questions: int,
    ) -> List[Dict[str, Any]]:
        questions: List[Dict[str, Any]] = []

        context = c4_model.get("context", {})
        system = context.get("system", {})
        system_name = str(system.get("name", "System"))
        questions.append(
            {
                "id": "context.system_name.confirm",
                "category": "context",
                "question": f"Is '{system_name}' the correct system boundary name?",
                "target": {"level": "context", "id": system_name},
                "options": ["yes", "no", "unsure"],
                "recommended": "yes",
            }
        )

        external_systems = context.get("external_systems", [])
        if external_systems:
            questions.append(
                {
                    "id": "context.external.confirm",
                    "category": "integration",
                    "question": "Should inferred external integrations remain as external systems?",
                    "target": {"level": "context", "id": "external_systems"},
                    "options": ["yes", "no", "unsure"],
                    "recommended": "yes",
                }
            )

        container_section = c4_model.get("container", {})
        containers = container_section.get("containers", [])
        for container in containers[: max(0, max_questions - len(questions))]:
            cid = str(container.get("id", "container"))
            ctype = str(container.get("type", "module"))
            questions.append(
                {
                    "id": f"container.type.{cid}",
                    "category": "container",
                    "question": f"Is '{cid}' correctly classified as '{ctype}'?",
                    "target": {"level": "container", "id": cid},
                    "options": ["yes", "no", "unsure"],
                    "recommended": "yes",
                }
            )
            if len(questions) >= max_questions:
                return questions

        relationships = container_section.get("relationships", [])
        for rel in relationships[: max(0, max_questions - len(questions))]:
            source = rel.get("source")
            target = rel.get("target")
            questions.append(
                {
                    "id": f"container.relationship.{source}.{target}",
                    "category": "relationship",
                    "question": f"Should dependency '{source} -> {target}' be kept?",
                    "target": {
                        "level": "container_relationship",
                        "source": source,
                        "target": target,
                    },
                    "options": ["yes", "no", "unsure"],
                    "recommended": "yes",
                }
            )
            if len(questions) >= max_questions:
                break

        return questions[:max_questions]

    def _apply_annotations(
        self,
        c4_model: Dict[str, Any],
        annotations: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        applied: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for raw in annotations:
            annotation = dict(raw)
            action = str(annotation.get("action", "")).strip()
            if not action:
                rejected.append({**annotation, "error": "Missing action"})
                continue

            try:
                if action in {"confirm_question", "reject_question"}:
                    applied.append(annotation)
                    continue

                if action == "set_system_name":
                    new_name = str(annotation.get("value", "")).strip()
                    if not new_name:
                        raise ValueError("value is required")
                    c4_model.setdefault("context", {}).setdefault("system", {})["name"] = new_name
                    c4_model.setdefault("container", {})["system"] = new_name
                    applied.append(annotation)
                    continue

                if action == "set_system_description":
                    desc = str(annotation.get("value", "")).strip()
                    if not desc:
                        raise ValueError("value is required")
                    c4_model.setdefault("context", {}).setdefault("system", {})["description"] = desc
                    applied.append(annotation)
                    continue

                if action == "rename_container":
                    container = self._find_container(c4_model, str(annotation.get("target_id", "")))
                    if container is None:
                        raise ValueError("target container not found")
                    new_name = str(annotation.get("value", "")).strip()
                    if not new_name:
                        raise ValueError("value is required")
                    container["name"] = new_name
                    applied.append(annotation)
                    continue

                if action == "set_container_type":
                    container = self._find_container(c4_model, str(annotation.get("target_id", "")))
                    if container is None:
                        raise ValueError("target container not found")
                    container_type = str(annotation.get("value", "")).strip()
                    if not container_type:
                        raise ValueError("value is required")
                    container["type"] = container_type
                    applied.append(annotation)
                    continue

                if action == "set_container_description":
                    container = self._find_container(c4_model, str(annotation.get("target_id", "")))
                    if container is None:
                        raise ValueError("target container not found")
                    desc = str(annotation.get("value", "")).strip()
                    if not desc:
                        raise ValueError("value is required")
                    container["description"] = desc
                    applied.append(annotation)
                    continue

                if action == "add_container_relationship":
                    source = str(annotation.get("source", "")).strip()
                    target = str(annotation.get("target", "")).strip()
                    description = str(annotation.get("description", "depends on")).strip() or "depends on"
                    if not source or not target:
                        raise ValueError("source and target are required")
                    rels = c4_model.setdefault("container", {}).setdefault("relationships", [])
                    if not any(r.get("source") == source and r.get("target") == target for r in rels):
                        rels.append({"source": source, "target": target, "description": description})
                    applied.append(annotation)
                    continue

                if action == "remove_container_relationship":
                    source = str(annotation.get("source", "")).strip()
                    target = str(annotation.get("target", "")).strip()
                    rels = c4_model.setdefault("container", {}).setdefault("relationships", [])
                    before = len(rels)
                    rels[:] = [
                        r for r in rels if not (str(r.get("source")) == source and str(r.get("target")) == target)
                    ]
                    if len(rels) == before:
                        raise ValueError("relationship not found")
                    applied.append(annotation)
                    continue

                if action == "rename_component":
                    container_id = str(annotation.get("container_id", "")).strip()
                    component_id = str(annotation.get("target_id", "")).strip()
                    new_name = str(annotation.get("value", "")).strip()
                    if not container_id or not component_id or not new_name:
                        raise ValueError("container_id, target_id and value are required")
                    component = self._find_component(c4_model, container_id, component_id)
                    if component is None:
                        raise ValueError("target component not found")
                    component["name"] = new_name
                    applied.append(annotation)
                    continue

                if action == "set_component_description":
                    container_id = str(annotation.get("container_id", "")).strip()
                    component_id = str(annotation.get("target_id", "")).strip()
                    desc = str(annotation.get("value", "")).strip()
                    if not container_id or not component_id or not desc:
                        raise ValueError("container_id, target_id and value are required")
                    component = self._find_component(c4_model, container_id, component_id)
                    if component is None:
                        raise ValueError("target component not found")
                    component["description"] = desc
                    applied.append(annotation)
                    continue

                if action == "add_component_relationship":
                    container_id = str(annotation.get("container_id", "")).strip()
                    source = str(annotation.get("source", "")).strip()
                    target = str(annotation.get("target", "")).strip()
                    desc = str(annotation.get("description", "depends on")).strip() or "depends on"
                    if not container_id or not source or not target:
                        raise ValueError("container_id, source and target are required")
                    rel_map = c4_model.setdefault("component", {}).setdefault("relationships", {})
                    rels = rel_map.setdefault(container_id, [])
                    if not any(r.get("source") == source and r.get("target") == target for r in rels):
                        rels.append({"source": source, "target": target, "description": desc})
                    applied.append(annotation)
                    continue

                if action == "remove_component_relationship":
                    container_id = str(annotation.get("container_id", "")).strip()
                    source = str(annotation.get("source", "")).strip()
                    target = str(annotation.get("target", "")).strip()
                    rel_map = c4_model.setdefault("component", {}).setdefault("relationships", {})
                    rels = rel_map.setdefault(container_id, [])
                    before = len(rels)
                    rels[:] = [
                        r for r in rels if not (str(r.get("source")) == source and str(r.get("target")) == target)
                    ]
                    if len(rels) == before:
                        raise ValueError("relationship not found")
                    applied.append(annotation)
                    continue

                rejected.append({**annotation, "error": f"Unsupported action '{action}'"})
            except Exception as exc:
                rejected.append({**annotation, "error": str(exc)})

        return applied, rejected

    def _find_container(self, c4_model: Dict[str, Any], container_id: str) -> Optional[Dict[str, Any]]:
        containers = c4_model.get("container", {}).get("containers", [])
        for container in containers:
            if str(container.get("id")) == container_id:
                return container
        return None

    def _find_component(
        self,
        c4_model: Dict[str, Any],
        container_id: str,
        component_id: str,
    ) -> Optional[Dict[str, Any]]:
        containers = c4_model.get("component", {}).get("containers", {})
        components = containers.get(container_id, [])
        for component in components:
            if str(component.get("id")) == component_id:
                return component
        return None

    def _annotation_schema(self) -> Dict[str, Any]:
        return {
            "actions": [
                {
                    "name": "confirm_question",
                    "required_fields": ["question_id", "decision"],
                },
                {
                    "name": "reject_question",
                    "required_fields": ["question_id", "decision"],
                },
                {
                    "name": "set_system_name",
                    "required_fields": ["value"],
                },
                {
                    "name": "set_system_description",
                    "required_fields": ["value"],
                },
                {
                    "name": "rename_container",
                    "required_fields": ["target_id", "value"],
                },
                {
                    "name": "set_container_type",
                    "required_fields": ["target_id", "value"],
                },
                {
                    "name": "set_container_description",
                    "required_fields": ["target_id", "value"],
                },
                {
                    "name": "add_container_relationship",
                    "required_fields": ["source", "target"],
                    "optional_fields": ["description"],
                },
                {
                    "name": "remove_container_relationship",
                    "required_fields": ["source", "target"],
                },
                {
                    "name": "rename_component",
                    "required_fields": ["container_id", "target_id", "value"],
                },
                {
                    "name": "set_component_description",
                    "required_fields": ["container_id", "target_id", "value"],
                },
                {
                    "name": "add_component_relationship",
                    "required_fields": ["container_id", "source", "target"],
                    "optional_fields": ["description"],
                },
                {
                    "name": "remove_component_relationship",
                    "required_fields": ["container_id", "source", "target"],
                },
            ]
        }

    async def _arun(
        self,
        directory_path: str = ".",
        c4_model: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        include_external_dependencies: bool = False,
        use_llm: bool = True,
        system_name: Optional[str] = None,
        max_components_per_container: int = 12,
        generate_questions: bool = True,
        max_questions: int = 20,
        annotations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return self._run(
            directory_path=directory_path,
            c4_model=c4_model,
            recursive=recursive,
            include_external_dependencies=include_external_dependencies,
            use_llm=use_llm,
            system_name=system_name,
            max_components_per_container=max_components_per_container,
            generate_questions=generate_questions,
            max_questions=max_questions,
            annotations=annotations,
        )


class CodeAnalysisToolNode:
    """
    Factory for creating code analysis tool nodes for LangGraph agents.

    Provides easy access to all code analysis tools.
    """

    def __init__(self, base_path: str = None):
        """
        Initialize the tool node factory.

        Args:
            base_path: Base path for file operations
        """
        self._base_path = base_path or os.getcwd()
        self._tools: List[BaseTool] = []

    def get_all_tools(self) -> List[BaseTool]:
        """Get all code analysis tools."""
        if not self._tools:
            self._tools = [
                DetectLanguageTool(base_path=self._base_path),
                ParseASTTool(base_path=self._base_path),
                TypeAwareAnalysisTool(base_path=self._base_path),
                DynamicHeuristicAnalysisTool(base_path=self._base_path),
                InferArchitectureTool(base_path=self._base_path),
                GenerateComponentInventoryTool(base_path=self._base_path),
                GenerateC4ModelTool(base_path=self._base_path),
                RenderC4MermaidTool(base_path=self._base_path),
                ArchitectureAnnotationInterfaceTool(base_path=self._base_path),
                ExtractFunctionsTool(base_path=self._base_path),
                ExtractClassesTool(base_path=self._base_path),
                ExtractImportsTool(base_path=self._base_path),
                BuildDependencyGraphTool(base_path=self._base_path),
                ClassifyFileImpactTool(base_path=self._base_path),
                TraceDownstreamDependenciesTool(base_path=self._base_path),
                DetectBreakingChangesTool(base_path=self._base_path),
                AnalyzeTypeSystemChangesTool(base_path=self._base_path),
                AssessTestImpactTool(base_path=self._base_path),
                AssessRiskLevelTool(base_path=self._base_path),
                IdentifyAffectedFeaturesTool(base_path=self._base_path),
                GenerateChangeProcedureTool(base_path=self._base_path),
                GenerateGitWorkflowTool(base_path=self._base_path),
                GenerateCommitSequenceTool(base_path=self._base_path),
                GenerateRollbackProcedureTool(base_path=self._base_path),
                GenerateFeatureFlagStrategyTool(base_path=self._base_path),
                GenerateMultiPhaseRolloutPlanTool(base_path=self._base_path),
                GenerateDatabaseMigrationStrategyTool(base_path=self._base_path),
                GetCodeMetricsTool(base_path=self._base_path),
                GenerateCodebaseMetricsTool(base_path=self._base_path),
                ScanDirectoryTool(base_path=self._base_path),
            ]
        return self._tools

    def get_tool(self, name: str) -> BaseTool:
        """
        Get a specific tool by name.

        Args:
            name: Tool name

        Returns:
            BaseTool instance
        """
        tools = {tool.name: tool for tool in self.get_all_tools()}
        if name not in tools:
            raise ValueError(f"Unknown tool: {name}")
        return tools[name]


# Convenience functions
def create_code_analysis_tools(base_path: str = None) -> List[BaseTool]:
    """Create all code analysis tools."""
    node = CodeAnalysisToolNode(base_path=base_path)
    return node.get_all_tools()


def get_detect_language_tool(base_path: str = None) -> DetectLanguageTool:
    """Get the detect language tool."""
    return DetectLanguageTool(base_path=base_path)


def get_extract_functions_tool(base_path: str = None) -> ExtractFunctionsTool:
    """Get the extract functions tool."""
    return ExtractFunctionsTool(base_path=base_path)


def get_extract_classes_tool(base_path: str = None) -> ExtractClassesTool:
    """Get the extract classes tool."""
    return ExtractClassesTool(base_path=base_path)


def get_get_code_metrics_tool(base_path: str = None) -> GetCodeMetricsTool:
    """Get the code metrics tool."""
    return GetCodeMetricsTool(base_path=base_path)


def get_generate_codebase_metrics_tool(base_path: str = None) -> GenerateCodebaseMetricsTool:
    """Get the aggregate codebase metrics tool."""
    return GenerateCodebaseMetricsTool(base_path=base_path)


def get_type_aware_analysis_tool(base_path: str = None) -> TypeAwareAnalysisTool:
    """Get the type-aware analysis tool."""
    return TypeAwareAnalysisTool(base_path=base_path)


def get_dynamic_heuristic_analysis_tool(base_path: str = None) -> DynamicHeuristicAnalysisTool:
    """Get the dynamic heuristic analysis tool."""
    return DynamicHeuristicAnalysisTool(base_path=base_path)


def get_infer_architecture_tool(base_path: str = None) -> InferArchitectureTool:
    """Get the architecture inference tool."""
    return InferArchitectureTool(base_path=base_path)


def get_generate_component_inventory_tool(
    base_path: str = None,
) -> GenerateComponentInventoryTool:
    """Get the component inventory generation tool."""
    return GenerateComponentInventoryTool(base_path=base_path)


def get_generate_c4_model_tool(base_path: str = None) -> GenerateC4ModelTool:
    """Get the C4 model generation tool."""
    return GenerateC4ModelTool(base_path=base_path)


def get_render_c4_mermaid_tool(base_path: str = None) -> RenderC4MermaidTool:
    """Get the C4 Mermaid rendering tool."""
    return RenderC4MermaidTool(base_path=base_path)


def get_architecture_annotation_interface_tool(
    base_path: str = None,
) -> ArchitectureAnnotationInterfaceTool:
    """Get the user-guided architecture annotation interface tool."""
    return ArchitectureAnnotationInterfaceTool(base_path=base_path)


def get_build_dependency_graph_tool(base_path: str = None) -> BuildDependencyGraphTool:
    """Get the dependency graph builder tool."""
    return BuildDependencyGraphTool(base_path=base_path)


def get_classify_file_impact_tool(base_path: str = None) -> ClassifyFileImpactTool:
    """Get the file impact classification tool."""
    return ClassifyFileImpactTool(base_path=base_path)


def get_trace_downstream_dependencies_tool(
    base_path: str = None,
) -> TraceDownstreamDependenciesTool:
    """Get the downstream dependency tracing tool."""
    return TraceDownstreamDependenciesTool(base_path=base_path)


def get_detect_breaking_changes_tool(base_path: str = None) -> DetectBreakingChangesTool:
    """Get the breaking change detection tool."""
    return DetectBreakingChangesTool(base_path=base_path)


def get_analyze_type_system_changes_tool(
    base_path: str = None,
) -> AnalyzeTypeSystemChangesTool:
    """Get the type-system change analysis tool."""
    return AnalyzeTypeSystemChangesTool(base_path=base_path)


def get_assess_test_impact_tool(base_path: str = None) -> AssessTestImpactTool:
    """Get the test impact assessment tool."""
    return AssessTestImpactTool(base_path=base_path)


def get_assess_risk_level_tool(base_path: str = None) -> AssessRiskLevelTool:
    """Get the risk level assessment tool."""
    return AssessRiskLevelTool(base_path=base_path)


def get_identify_affected_features_tool(
    base_path: str = None,
) -> IdentifyAffectedFeaturesTool:
    """Get the affected feature identification tool."""
    return IdentifyAffectedFeaturesTool(base_path=base_path)


def get_generate_change_procedure_tool(
    base_path: str = None,
) -> GenerateChangeProcedureTool:
    """Get the detailed step-by-step change procedure generation tool."""
    return GenerateChangeProcedureTool(base_path=base_path)


def get_generate_git_workflow_tool(
    base_path: str = None,
) -> GenerateGitWorkflowTool:
    """Get the Git workflow format generation tool with branch naming conventions."""
    return GenerateGitWorkflowTool(base_path=base_path)


def get_generate_commit_sequence_tool(
    base_path: str = None,
) -> GenerateCommitSequenceTool:
    """Get the atomic commit sequence generation tool."""
    return GenerateCommitSequenceTool(base_path=base_path)


def get_generate_rollback_procedure_tool(
    base_path: str = None,
) -> GenerateRollbackProcedureTool:
    """Get the rollback procedure generation tool for safe recovery."""
    return GenerateRollbackProcedureTool(base_path=base_path)


def get_generate_feature_flag_strategy_tool(
    base_path: str = None,
) -> GenerateFeatureFlagStrategyTool:
    """Get the feature flag strategy generation tool for gradual rollout."""
    return GenerateFeatureFlagStrategyTool(base_path=base_path)


def get_generate_multi_phase_rollout_plan_tool(
    base_path: str = None,
) -> GenerateMultiPhaseRolloutPlanTool:
    """Get the multi-phase rollout planning tool for complex changes."""
    return GenerateMultiPhaseRolloutPlanTool(base_path=base_path)


def get_generate_database_migration_strategy_tool(
    base_path: str = None,
) -> GenerateDatabaseMigrationStrategyTool:
    """Get the database migration strategy generation tool."""
    return GenerateDatabaseMigrationStrategyTool(base_path=base_path)
