"""
Git Operations ToolNode for LangGraph agents.

Provides LangChain tools for Git operations including:
- Repository cloning and initialization
- Branch management (create, list, delete)
- Commit operations
- Diff and log viewing
- Merge and rebase operations
"""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class CloneRepoInput(BaseModel):
    """Input schema for CloneRepoTool."""

    repo_url: str = Field(..., description="Repository URL to clone")
    target_path: Optional[str] = Field(
        default=None, description="Target directory path"
    )
    branch: Optional[str] = Field(default=None, description="Branch to checkout")
    depth: Optional[int] = Field(default=None, ge=1, description="Shallow clone depth")


class CloneRepoTool(BaseTool):
    """Tool for cloning Git repositories."""

    name: str = "clone_repo"
    description: str = """
    Clone a Git repository to a local directory.
    Use depth for shallow clones of large repositories.
    Returns the path to the cloned repository.
    """
    args_schema: Type[BaseModel] = CloneRepoInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self,
        repo_url: str,
        target_path: str = None,
        branch: str = None,
        depth: int = None,
    ) -> Dict[str, Any]:
        """Execute repository clone."""
        try:
            # Determine target path
            if target_path:
                resolved_target = target_path
                if not os.path.isabs(resolved_target):
                    resolved_target = os.path.join(self._base_path, resolved_target)
            else:
                # Extract repo name from URL
                repo_name = repo_url.rstrip("/").split("/")[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
                resolved_target = os.path.join(self._base_path, repo_name)

            # Build git clone command
            cmd = ["git", "clone"]
            if depth:
                cmd.extend(["--depth", str(depth)])
            if branch:
                cmd.extend(["--branch", branch])
            cmd.extend([repo_url, resolved_target])

            # Execute clone
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "repo_url": repo_url,
                "path": resolved_target,
                "branch": branch or "main",
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Clone operation timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self,
        repo_url: str,
        target_path: str = None,
        branch: str = None,
        depth: int = None,
    ) -> Dict[str, Any]:
        """Async wrapper for clone repo."""
        return self._run(repo_url, target_path, branch, depth)


class InitRepoInput(BaseModel):
    """Input schema for InitRepoTool."""

    path: Optional[str] = Field(default=None, description="Path to initialize repo")
    bare: bool = Field(default=False, description="Create bare repository")


class InitRepoTool(BaseTool):
    """Tool for initializing Git repositories."""

    name: str = "init_repo"
    description: str = """
    Initialize a new Git repository.
    Use bare=True for creating a bare repository (for servers).
    """
    args_schema: Type[BaseModel] = InitRepoInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, path: str = None, bare: bool = False
    ) -> Dict[str, Any]:
        """Execute repository init."""
        try:
            target_path = path or "."
            if not os.path.isabs(target_path):
                target_path = os.path.join(self._base_path, target_path)

            cmd = ["git", "init"]
            if bare:
                cmd.append("--bare")
            cmd.append(target_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "path": target_path,
                "bare": bare,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, path: str = None, bare: bool = False
    ) -> Dict[str, Any]:
        """Async wrapper for init repo."""
        return self._run(path, bare)


class ListBranchesInput(BaseModel):
    """Input schema for ListBranchesTool."""

    repo_path: str = Field(default=".", description="Repository path")
    all: bool = Field(default=False, description="List all branches including remotes")


class ListBranchesTool(BaseTool):
    """Tool for listing Git branches."""

    name: str = "list_branches"
    description: str = """
    List all branches in a Git repository.
    Use all=True to include remote branches.
    """
    args_schema: Type[BaseModel] = ListBranchesInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", all: bool = False
    ) -> Dict[str, Any]:
        """Execute branch listing."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "branch"]
            if all:
                cmd.append("-a")

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            branches = [
                branch.strip().replace("* ", "")
                for branch in result.stdout.strip().split("\n")
                if branch.strip()
            ]

            current_branch = None
            for branch in branches:
                if branch.startswith("*"):
                    current_branch = branch.replace("* ", "").strip()
                    break

            return {
                "status": "success",
                "repo_path": repo_path,
                "branches": branches,
                "current_branch": current_branch,
                "total_count": len(branches),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", all: bool = False
    ) -> Dict[str, Any]:
        """Async wrapper for list branches."""
        return self._run(repo_path, all)


class CreateBranchInput(BaseModel):
    """Input schema for CreateBranchTool."""

    repo_path: str = Field(default=".", description="Repository path")
    branch_name: str = Field(..., description="Name of new branch")
    from_branch: Optional[str] = Field(
        default=None, description="Source branch (defaults to current)"
    )


class CreateBranchTool(BaseTool):
    """Tool for creating Git branches."""

    name: str = "create_branch"
    description: str = """
    Create a new Git branch.
    Use from_branch to specify source branch.
    """
    args_schema: Type[BaseModel] = CreateBranchInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", branch_name: str = None, from_branch: str = None
    ) -> Dict[str, Any]:
        """Execute branch creation."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            # Create branch
            cmd = ["git", "checkout", "-b"]
            if from_branch:
                cmd.extend([branch_name, from_branch])
            else:
                cmd.append(branch_name)

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "branch_name": branch_name,
                "from_branch": from_branch,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", branch_name: str = None, from_branch: str = None
    ) -> Dict[str, Any]:
        """Async wrapper for create branch."""
        return self._run(repo_path, branch_name, from_branch)


class CheckoutBranchInput(BaseModel):
    """Input schema for CheckoutBranchTool."""

    repo_path: str = Field(default=".", description="Repository path")
    branch_name: str = Field(..., description="Branch to checkout")
    create_new: bool = Field(
        default=False, description="Create branch if it doesn't exist"
    )


class CheckoutBranchTool(BaseTool):
    """Tool for switching Git branches."""

    name: str = "checkout_branch"
    description: str = """
    Switch to a different Git branch.
    Use create_new=True to create the branch if it doesn't exist.
    """
    args_schema: Type[BaseModel] = CheckoutBranchInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", branch_name: str = None, create_new: bool = False
    ) -> Dict[str, Any]:
        """Execute branch checkout."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "checkout"]
            if create_new:
                cmd.append("-b")
            cmd.append(branch_name)

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "branch_name": branch_name,
                "created": create_new,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", branch_name: str = None, create_new: bool = False
    ) -> Dict[str, Any]:
        """Async wrapper for checkout branch."""
        return self._run(repo_path, branch_name, create_new)


class GetCommitLogInput(BaseModel):
    """Input schema for GetCommitLogTool."""

    repo_path: str = Field(default=".", description="Repository path")
    limit: int = Field(default=20, ge=1, le=100, description="Number of commits")
    branch: Optional[str] = Field(default=None, description="Specific branch")
    format: str = Field(
        default="oneline", description="Format (oneline, short, full, raw)"
    )


class GetCommitLogTool(BaseTool):
    """Tool for viewing Git commit log."""

    name: str = "get_commit_log"
    description: str = """
    View commit history in a Git repository.
    Use limit to control number of commits returned.
    Use format to control output format.
    """
    args_schema: Type[BaseModel] = GetCommitLogInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self,
        repo_path: str = ".",
        limit: int = 20,
        branch: str = None,
        format: str = "oneline",
    ) -> Dict[str, Any]:
        """Execute commit log retrieval."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "log", f"-n{limit}", f"--format={format}"]
            if branch:
                cmd.append(branch)

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            commits = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]

            return {
                "status": "success",
                "repo_path": repo_path,
                "commits": commits,
                "count": len(commits),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self,
        repo_path: str = ".",
        limit: int = 20,
        branch: str = None,
        format: str = "oneline",
    ) -> Dict[str, Any]:
        """Async wrapper for get commit log."""
        return self._run(repo_path, limit, branch, format)


class GetDiffInput(BaseModel):
    """Input schema for GetDiffTool."""

    repo_path: str = Field(default=".", description="Repository path")
    compare: str = Field(
        default="HEAD", description="Compare ref (commit, branch, or range)"
    )
    file_path: Optional[str] = Field(default=None, description="Specific file")
    staged: bool = Field(default=False, description="Show staged changes")


class GetDiffTool(BaseTool):
    """Tool for viewing Git diffs."""

    name: str = "get_diff"
    description: str = """
    View changes in a Git repository.
    Use compare to specify what to compare against.
    Use file_path to diff a specific file.
    Use staged=True to show staged changes.
    """
    args_schema: Type[BaseModel] = GetDiffInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self,
        repo_path: str = ".",
        compare: str = "HEAD",
        file_path: str = None,
        staged: bool = False,
    ) -> Dict[str, Any]:
        """Execute diff retrieval."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            else:
                cmd.append(compare)

            if file_path:
                cmd.append(file_path)

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "repo_path": repo_path,
                "diff": result.stdout,
                "changes": result.stdout.count("\n@@") if result.stdout else 0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self,
        repo_path: str = ".",
        compare: str = "HEAD",
        file_path: str = None,
        staged: bool = False,
    ) -> Dict[str, Any]:
        """Async wrapper for get diff."""
        return self._run(repo_path, compare, file_path, staged)


class CommitChangesInput(BaseModel):
    """Input schema for CommitChangesTool."""

    repo_path: str = Field(default=".", description="Repository path")
    message: str = Field(..., description="Commit message")
    all: bool = Field(default=True, description="Stage all changes")
    amend: bool = Field(default=False, description="Amend previous commit")


class CommitChangesTool(BaseTool):
    """Tool for creating Git commits."""

    name: str = "commit_changes"
    description: str = """
    Create a Git commit.
    Use all=True to automatically stage all changes.
    Use amend=True to modify the previous commit.
    """
    args_schema: Type[BaseModel] = CommitChangesInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", message: str = None, all: bool = True, amend: bool = False
    ) -> Dict[str, Any]:
        """Execute commit creation."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            # Stage changes if all=True
            if all:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=resolved_path,
                    capture_output=True,
                    timeout=60,
                )

            # Create commit
            cmd = ["git", "commit"]
            if amend:
                cmd.append("--amend")
            cmd.extend(["-m", message])

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "status": "success",
                "commit_hash": hash_result.stdout.strip(),
                "message": message,
                "amended": amend,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", message: str = None, all: bool = True, amend: bool = False
    ) -> Dict[str, Any]:
        """Async wrapper for commit changes."""
        return self._run(repo_path, message, all, amend)


class PushChangesInput(BaseModel):
    """Input schema for PushChangesTool."""

    repo_path: str = Field(default=".", description="Repository path")
    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Branch to push")
    tags: bool = Field(default=False, description="Push tags")


class PushChangesTool(BaseTool):
    """Tool for pushing Git changes."""

    name: str = "push_changes"
    description: str = """
    Push changes to a remote repository.
    Use tags=True to push tags as well.
    """
    args_schema: Type[BaseModel] = PushChangesInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", remote: str = "origin", branch: str = None, tags: bool = False
    ) -> Dict[str, Any]:
        """Execute push operation."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)
            if tags:
                cmd.append("--tags")

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "remote": remote,
                "branch": branch,
                "tags_pushed": tags,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", remote: str = "origin", branch: str = None, tags: bool = False
    ) -> Dict[str, Any]:
        """Async wrapper for push changes."""
        return self._run(repo_path, remote, branch, tags)


class PullChangesInput(BaseModel):
    """Input schema for PullChangesTool."""

    repo_path: str = Field(default=".", description="Repository path")
    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Branch to pull")


class PullChangesTool(BaseTool):
    """Tool for pulling Git changes."""

    name: str = "pull_changes"
    description: str = """
    Pull changes from a remote repository.
    """
    args_schema: Type[BaseModel] = PullChangesInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", remote: str = "origin", branch: str = None
    ) -> Dict[str, Any]:
        """Execute pull operation."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "pull", remote]
            if branch:
                cmd.append(branch)

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            return {
                "status": "success",
                "remote": remote,
                "branch": branch,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", remote: str = "origin", branch: str = None
    ) -> Dict[str, Any]:
        """Async wrapper for pull changes."""
        return self._run(repo_path, remote, branch)


class GitStatusInput(BaseModel):
    """Input schema for GitStatusTool."""

    repo_path: str = Field(default=".", description="Repository path")
    short: bool = Field(default=True, description="Use short format")


class GitStatusTool(BaseTool):
    """Tool for checking Git repository status."""

    name: str = "git_status"
    description: str = """
    Check the status of a Git repository.
    Returns information about staged, unstaged, and untracked files.
    """
    args_schema: Type[BaseModel] = GitStatusInput

    def __init__(self, base_path: str = None):
        super().__init__()
        self._base_path = base_path or os.getcwd()

    def _run(
        self, repo_path: str = ".", short: bool = True
    ) -> Dict[str, Any]:
        """Execute status check."""
        try:
            resolved_path = repo_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(self._base_path, resolved_path)

            if not os.path.exists(os.path.join(resolved_path, ".git")):
                return {"status": "error", "error": "Not a git repository"}

            cmd = ["git", "status"]
            if short:
                cmd.append("-s")

            result = subprocess.run(
                cmd,
                cwd=resolved_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"status": "error", "error": result.stderr}

            lines = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]

            return {
                "status": "success",
                "repo_path": repo_path,
                "output": result.stdout,
                "changes": len(lines),
                "lines": lines,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _arun(
        self, repo_path: str = ".", short: bool = True
    ) -> Dict[str, Any]:
        """Async wrapper for git status."""
        return self._run(repo_path, short)


class GitToolNode:
    """
    Factory for creating Git operation tool nodes for LangGraph agents.

    Provides easy access to all Git operation tools.
    """

    def __init__(self, base_path: str = None):
        """
        Initialize the tool node factory.

        Args:
            base_path: Base path for repository operations
        """
        self._base_path = base_path or os.getcwd()
        self._tools: List[BaseTool] = []

    def get_all_tools(self) -> List[BaseTool]:
        """Get all Git operation tools."""
        if not self._tools:
            self._tools = [
                CloneRepoTool(base_path=self._base_path),
                InitRepoTool(base_path=self._base_path),
                ListBranchesTool(base_path=self._base_path),
                CreateBranchTool(base_path=self._base_path),
                CheckoutBranchTool(base_path=self._base_path),
                GetCommitLogTool(base_path=self._base_path),
                GetDiffTool(base_path=self._base_path),
                CommitChangesTool(base_path=self._base_path),
                PushChangesTool(base_path=self._base_path),
                PullChangesTool(base_path=self._base_path),
                GitStatusTool(base_path=self._base_path),
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
def create_git_tools(base_path: str = None) -> List[BaseTool]:
    """Create all Git operation tools."""
    node = GitToolNode(base_path=base_path)
    return node.get_all_tools()


def get_clone_repo_tool(base_path: str = None) -> CloneRepoTool:
    """Get the clone repo tool."""
    return CloneRepoTool(base_path=base_path)


def get_list_branches_tool(base_path: str = None) -> ListBranchesTool:
    """Get the list branches tool."""
    return ListBranchesTool(base_path=base_path)


def get_create_branch_tool(base_path: str = None) -> CreateBranchTool:
    """Get the create branch tool."""
    return CreateBranchTool(base_path=base_path)


def get_commit_changes_tool(base_path: str = None) -> CommitChangesTool:
    """Get the commit changes tool."""
    return CommitChangesTool(base_path=base_path)


def get_push_changes_tool(base_path: str = None) -> PushChangesTool:
    """Get the push changes tool."""
    return PushChangesTool(base_path=base_path)
