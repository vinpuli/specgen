"""
File Operations ToolNode for LangGraph agents.

Provides LangChain tools for file operations including:
- Reading and writing files
- Listing directories
- File search and glob patterns
- File metadata and information
- File compression and extraction
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class ReadFileInput(BaseModel):
    """Input schema for ReadFileTool."""

    file_path: str = Field(..., description="Path to the file to read")
    encoding: str = Field(default="utf-8", description="File encoding")


class ReadFileTool(BaseTool):
    """Tool for reading file contents."""

    name: str = "read_file"
    description: str = """
    Read the contents of a file.
    Returns the file content as a string.
    Use this to read source code, documentation, or configuration files.
    """
    args_schema: Type[BaseModel] = ReadFileInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self, file_path: str, encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Execute file read."""
        try:
            resolved_path = self._resolve_path(file_path)
            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"File not found: {file_path}"}

            with open(resolved_path, "r", encoding=encoding) as f:
                content = f.read()

            return {
                "status": "success",
                "file_path": file_path,
                "content": content,
                "size": len(content),
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, file_path: str, encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Async wrapper for file read."""
        return self._run(file_path, encoding)


class WriteFileInput(BaseModel):
    """Input schema for WriteFileTool."""

    file_path: str = Field(..., description="Path to write the file")
    content: str = Field(..., description="Content to write")
    encoding: str = Field(default="utf-8", description="File encoding")
    mode: str = Field(default="w", description="Write mode ('w' for write, 'a' for append)")


class WriteFileTool(BaseTool):
    """Tool for writing file contents."""

    name: str = "write_file"
    description: str = """
    Write content to a file.
    Creates the file if it doesn't exist.
    Use mode='a' to append to existing files.
    """
    args_schema: Type[BaseModel] = WriteFileInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        mode: str = "w",
    ) -> Dict[str, Any]:
        """Execute file write."""
        try:
            resolved_path = self._resolve_path(file_path)

            # Create parent directories if needed
            parent = Path(resolved_path).parent
            parent.mkdir(parents=True, exist_ok=True)

            with open(resolved_path, mode, encoding=encoding) as f:
                f.write(content)

            return {
                "status": "success",
                "file_path": file_path,
                "bytes_written": len(content.encode(encoding)),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        mode: str = "w",
    ) -> Dict[str, Any]:
        """Async wrapper for file write."""
        return self._run(file_path, content, encoding, mode)


class ListDirectoryInput(BaseModel):
    """Input schema for ListDirectoryTool."""

    directory_path: str = Field(default=".", description="Path to list")
    include_hidden: bool = Field(default=False, description="Include hidden files")
    recursive: bool = Field(default=False, description="List recursively")


class ListDirectoryTool(BaseTool):
    """Tool for listing directory contents."""

    name: str = "list_directory"
    description: str = """
    List files and directories in a path.
    Returns a list of entries with type information.
    Use recursive=True for deep listing.
    """
    args_schema: Type[BaseModel] = ListDirectoryInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, directory_path: str) -> str:
        """Resolve directory path relative to base path."""
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self,
        directory_path: str = ".",
        include_hidden: bool = False,
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """Execute directory listing."""
        try:
            resolved_path = self._resolve_path(directory_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"Directory not found: {directory_path}"}

            if not os.path.isdir(resolved_path):
                return {"status": "error", "error": f"Not a directory: {directory_path}"}

            entries = []

            if recursive:
                for root, dirs, files in os.walk(resolved_path):
                    for name in dirs:
                        if include_hidden or not name.startswith("."):
                            full_path = os.path.join(root, name)
                            entries.append(
                                {
                                    "name": name,
                                    "path": os.path.relpath(full_path, resolved_path),
                                    "type": "directory",
                                    "size": self._get_size(full_path),
                                }
                            )
                    for name in files:
                        if include_hidden or not name.startswith("."):
                            full_path = os.path.join(root, name)
                            entries.append(
                                {
                                    "name": name,
                                    "path": os.path.relpath(full_path, resolved_path),
                                    "type": "file",
                                    "size": os.path.getsize(full_path),
                                }
                            )
            else:
                for name in os.listdir(resolved_path):
                    if include_hidden or not name.startswith("."):
                        full_path = os.path.join(resolved_path, name)
                        entries.append(
                            {
                                "name": name,
                                "path": name,
                                "type": "directory" if os.path.isdir(full_path) else "file",
                                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else 0,
                            }
                        )

            return {
                "status": "success",
                "directory_path": directory_path,
                "entries": entries,
                "total_count": len(entries),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_size(self, path: str) -> int:
        """Get size of a path."""
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
        return total

    async def _arun(
        self,
        directory_path: str = ".",
        include_hidden: bool = False,
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """Async wrapper for directory listing."""
        return self._run(directory_path, include_hidden, recursive)


class GlobSearchInput(BaseModel):
    """Input schema for GlobSearchTool."""

    pattern: str = Field(..., description="Glob pattern (e.g., '**/*.py')")
    base_path: Optional[str] = Field(
        default=None, description="Base path for search"
    )
    max_results: int = Field(default=100, ge=1, le=1000, description="Max results")


class GlobSearchTool(BaseTool):
    """Tool for searching files using glob patterns."""

    name: str = "glob_search"
    description: str = """
    Search for files matching a glob pattern.
    Use patterns like '*.py', '**/*.py', 'src/**/*.ts'.
    Useful for finding source files, configs, etc.
    """
    args_schema: Type[BaseModel] = GlobSearchInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, base_path: str) -> str:
        """Resolve base path."""
        path = Path(base_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(
        self, pattern: str, base_path: str = None, max_results: int = 100
    ) -> Dict[str, Any]:
        """Execute glob search."""
        try:
            search_base = self._resolve_path(base_path or self._base_path)
            base_path_obj = Path(search_base)

            # Handle patterns
            full_pattern = str(base_path_obj / pattern)

            # Use glob
            results = list(Path(search_base).glob(pattern))[:max_results]

            files = []
            for path in results:
                files.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "relative_path": str(path.relative_to(base_path_obj)),
                        "is_file": path.is_file(),
                        "size": path.stat().st_size if path.is_file() else 0,
                    }
                )

            return {
                "status": "success",
                "pattern": pattern,
                "base_path": search_base,
                "files": files,
                "total_found": len(files),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, pattern: str, base_path: str = None, max_results: int = 100
    ) -> Dict[str, Any]:
        """Async wrapper for glob search."""
        return self._run(pattern, base_path, max_results)


class GetFileInfoInput(BaseModel):
    """Input schema for GetFileInfoTool."""

    file_path: str = Field(..., description="Path to get information about")


class GetFileInfoTool(BaseTool):
    """Tool for getting file metadata and information."""

    name: str = "get_file_info"
    description: str = """
    Get metadata and information about a file or directory.
    Returns size, creation time, modification time, permissions, etc.
    """
    args_schema: Type[BaseModel] = GetFileInfoInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str) -> Dict[str, Any]:
        """Execute file info."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"Path not found: {file_path}"}

            stat = os.stat(resolved_path)
            is_dir = os.path.isdir(resolved_path)

            info = {
                "status": "success",
                "file_path": file_path,
                "name": os.path.basename(resolved_path),
                "is_directory": is_dir,
                "is_file": not is_dir,
                "size": stat.st_size if not is_dir else self._get_dir_size(resolved_path),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "readable": os.access(resolved_path, os.R_OK),
                "writable": os.access(resolved_path, os.W_OK),
                "executable": os.access(resolved_path, os.X_OK),
            }

            return info
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_dir_size(self, path: str) -> int:
        """Get total size of a directory."""
        total = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
        return total

    async def _arun(self, file_path: str) -> Dict[str, Any]:
        """Async wrapper for file info."""
        return self._run(file_path)


class DeleteFileInput(BaseModel):
    """Input schema for DeleteFileTool."""

    file_path: str = Field(..., description="Path to delete")
    recursive: bool = Field(default=False, description="Delete recursively for directories")


class DeleteFileTool(BaseTool):
    """Tool for deleting files and directories."""

    name: str = "delete_file"
    description: str = """
    Delete a file or directory.
    Use recursive=True for directories to delete contents.
    This action is irreversible!
    """
    args_schema: Type[BaseModel] = DeleteFileInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, file_path: str, recursive: bool = False) -> Dict[str, Any]:
        """Execute file deletion."""
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return {"status": "error", "error": f"Path not found: {file_path}"}

            if os.path.isdir(resolved_path):
                if recursive:
                    import shutil
                    shutil.rmtree(resolved_path)
                else:
                    return {
                        "status": "error",
                        "error": f"Directory not empty, use recursive=True: {file_path}",
                    }
            else:
                os.remove(resolved_path)

            return {"status": "success", "file_path": file_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(self, file_path: str, recursive: bool = False) -> Dict[str, Any]:
        """Async wrapper for file deletion."""
        return self._run(file_path, recursive)


class CopyFileInput(BaseModel):
    """Input schema for CopyFileTool."""

    source_path: str = Field(..., description="Source file path")
    destination_path: str = Field(..., description="Destination file path")


class CopyFileTool(BaseTool):
    """Tool for copying files and directories."""

    name: str = "copy_file"
    description: str = """
    Copy a file or directory to a new location.
    Creates parent directories as needed.
    """
    args_schema: Type[BaseModel] = CopyFileInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Execute file copy."""
        try:
            resolved_source = self._resolve_path(source_path)
            resolved_dest = self._resolve_path(destination_path)

            if not os.path.exists(resolved_source):
                return {"status": "error", "error": f"Source not found: {source_path}"}

            # Create parent directories
            dest_parent = Path(resolved_dest).parent
            dest_parent.mkdir(parents=True, exist_ok=True)

            import shutil

            if os.path.isdir(resolved_source):
                shutil.copytree(resolved_source, resolved_dest)
            else:
                shutil.copy2(resolved_source, resolved_dest)

            return {
                "status": "success",
                "source_path": source_path,
                "destination_path": destination_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Async wrapper for file copy."""
        return self._run(source_path, destination_path)


class MoveFileInput(BaseModel):
    """Input schema for MoveFileTool."""

    source_path: str = Field(..., description="Source file path")
    destination_path: str = Field(..., description="Destination file path")


class MoveFileTool(BaseTool):
    """Tool for moving/renaming files and directories."""

    name: str = "move_file"
    description: str = """
    Move or rename a file or directory.
    Can be used for renaming files or moving to different directories.
    """
    args_schema: Type[BaseModel] = MoveFileInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to base path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Execute file move."""
        try:
            resolved_source = self._resolve_path(source_path)
            resolved_dest = self._resolve_path(destination_path)

            if not os.path.exists(resolved_source):
                return {"status": "error", "error": f"Source not found: {source_path}"}

            # Create parent directories
            dest_parent = Path(resolved_dest).parent
            dest_parent.mkdir(parents=True, exist_ok=True)

            import shutil

            shutil.move(resolved_source, resolved_dest)

            return {
                "status": "success",
                "source_path": source_path,
                "destination_path": destination_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Async wrapper for file move."""
        return self._run(source_path, destination_path)


class CreateDirectoryInput(BaseModel):
    """Input schema for CreateDirectoryTool."""

    directory_path: str = Field(..., description="Path to create")
    parents: bool = Field(default=True, description="Create parent directories")


class CreateDirectoryTool(BaseTool):
    """Tool for creating directories."""

    name: str = "create_directory"
    description: str = """
    Create a directory.
    Use parents=True to create nested directories.
    """
    args_schema: Type[BaseModel] = CreateDirectoryInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _resolve_path(self, directory_path: str) -> str:
        """Resolve directory path relative to base path."""
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(self._base_path) / path
        return str(path)

    def _run(self, directory_path: str, parents: bool = True) -> Dict[str, Any]:
        """Execute directory creation."""
        try:
            resolved_path = self._resolve_path(directory_path)

            if os.path.exists(resolved_path):
                return {
                    "status": "error",
                    "error": f"Already exists: {directory_path}",
                }

            Path(resolved_path).mkdir(parents=parents, exist_ok=True)

            return {"status": "success", "directory_path": directory_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(self, directory_path: str, parents: bool = True) -> Dict[str, Any]:
        """Async wrapper for directory creation."""
        return self._run(directory_path, parents)


class FileOperationToolNode:
    """
    Factory for creating file operation tool nodes for LangGraph agents.

    Provides easy access to all file operation tools.
    """

    def __init__(self, base_path: str = None):
        """
        Initialize the tool node factory.

        Args:
            base_path: Base path for relative file operations
        """
        self._base_path = base_path or os.getcwd()
        self._tools: List[BaseTool] = []

    def get_all_tools(self) -> List[BaseTool]:
        """Get all file operation tools."""
        if not self._tools:
            self._tools = [
                ReadFileTool(base_path=self._base_path),
                WriteFileTool(base_path=self._base_path),
                ListDirectoryTool(base_path=self._base_path),
                GlobSearchTool(base_path=self._base_path),
                GetFileInfoTool(base_path=self._base_path),
                DeleteFileTool(base_path=self._base_path),
                CopyFileTool(base_path=self._base_path),
                MoveFileTool(base_path=self._base_path),
                CreateDirectoryTool(base_path=self._base_path),
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
def create_file_tools(base_path: str = None) -> List[BaseTool]:
    """Create all file operation tools."""
    node = FileOperationToolNode(base_path=base_path)
    return node.get_all_tools()


def get_read_file_tool(base_path: str = None) -> ReadFileTool:
    """Get the read file tool."""
    return ReadFileTool(base_path=base_path)


def get_write_file_tool(base_path: str = None) -> WriteFileTool:
    """Get the write file tool."""
    return WriteFileTool(base_path=base_path)


def get_list_directory_tool(base_path: str = None) -> ListDirectoryTool:
    """Get the list directory tool."""
    return ListDirectoryTool(base_path=base_path)


def get_glob_search_tool(base_path: str = None) -> GlobSearchTool:
    """Get the glob search tool."""
    return GlobSearchTool(base_path=base_path)


def get_file_info_tool(base_path: str = None) -> GetFileInfoTool:
    """Get the file info tool."""
    return GetFileInfoTool(base_path=base_path)


def get_delete_file_tool(base_path: str = None) -> DeleteFileTool:
    """Get the delete file tool."""
    return DeleteFileTool(base_path=base_path)
