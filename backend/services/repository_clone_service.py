"""
Repository cloning service with authentication and local caching.

This service provides:
- Authenticated clone URL construction for GitHub/GitLab
- Local repository cache reuse across analyses
- Shallow clone optimization for large repositories
- Branch checkout and commit SHA resolution
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse, quote


logger = logging.getLogger(__name__)


class RepositoryCloneError(Exception):
    """Raised when repository clone/update fails."""


@dataclass
class RepositoryCloneResult:
    """Result of a clone-or-cache operation."""

    local_path: str
    cache_hit: bool
    shallow_clone: bool
    clone_depth: Optional[int]
    directory_scope: Optional[list[str]]
    branch_name: Optional[str]
    commit_sha: Optional[str]


class RepositoryCloneService:
    """
    Clone repositories with token-based auth and local caching.
    """

    _locks: Dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        timeout_seconds: int = 180,
        shallow_clone: Optional[bool] = None,
        clone_depth: Optional[int] = None,
    ):
        self.cache_dir = Path(cache_dir or os.getenv("REPO_CACHE_DIR", "tmp/repo_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.shallow_clone = (
            shallow_clone
            if shallow_clone is not None
            else self._parse_bool_env(os.getenv("REPO_SHALLOW_CLONE", "true"))
        )
        raw_depth = (
            clone_depth
            if clone_depth is not None
            else self._parse_int_env(os.getenv("REPO_CLONE_DEPTH"), default=1)
        )
        self.clone_depth = max(1, raw_depth)

    async def clone_or_get_cached(
        self,
        repository_url: str,
        branch_name: Optional[str] = None,
        directory_scope: Optional[list[str]] = None,
        github_access_token: Optional[str] = None,
        gitlab_access_token: Optional[str] = None,
        gitlab_base_url: Optional[str] = None,
    ) -> RepositoryCloneResult:
        """
        Clone repository or reuse cached copy.

        Returns repository local path, whether cache was reused, effective branch, and commit SHA.
        """
        normalized_scope = self._normalize_directory_scope(directory_scope)
        cache_key = self._build_cache_key(repository_url, branch_name, normalized_scope)
        if cache_key not in self._locks:
            self._locks[cache_key] = asyncio.Lock()

        async with self._locks[cache_key]:
            return await asyncio.to_thread(
                self._clone_or_get_cached_sync,
                repository_url,
                branch_name,
                normalized_scope,
                github_access_token,
                gitlab_access_token,
                gitlab_base_url,
            )

    def _clone_or_get_cached_sync(
        self,
        repository_url: str,
        branch_name: Optional[str],
        directory_scope: Optional[list[str]],
        github_access_token: Optional[str],
        gitlab_access_token: Optional[str],
        gitlab_base_url: Optional[str],
    ) -> RepositoryCloneResult:
        cache_key = self._build_cache_key(repository_url, branch_name, directory_scope)
        repo_path = self.cache_dir / cache_key
        authenticated_url = self._build_authenticated_url(
            repository_url=repository_url,
            github_access_token=github_access_token,
            gitlab_access_token=gitlab_access_token,
            gitlab_base_url=gitlab_base_url,
        )

        cache_hit = repo_path.exists() and (repo_path / ".git").exists()
        if cache_hit:
            fetch_cmd = ["fetch", "--all", "--prune"]
            if self.shallow_clone and self._is_shallow_repo(repo_path):
                fetch_cmd.append(f"--depth={self.clone_depth}")
            self._run_git(fetch_cmd, cwd=repo_path)
        else:
            clone_cmd = ["clone"]
            if self.shallow_clone:
                clone_cmd.extend(["--depth", str(self.clone_depth), "--single-branch"])
            if branch_name:
                clone_cmd.extend(["--branch", branch_name])
            clone_cmd.extend([authenticated_url, str(repo_path)])
            self._run_git(clone_cmd, cwd=None)

        effective_branch = branch_name or self._resolve_default_branch(repo_path)
        if effective_branch:
            self._run_git(["checkout", effective_branch], cwd=repo_path)
            # Ensure cached repository is updated to remote branch tip.
            if self.shallow_clone and self._is_shallow_repo(repo_path):
                self._run_git(
                    ["fetch", "origin", effective_branch, f"--depth={self.clone_depth}"],
                    cwd=repo_path,
                )
            self._run_git(["pull", "--ff-only", "origin", effective_branch], cwd=repo_path)

        if directory_scope:
            self._apply_directory_scope(repo_path, directory_scope)

        commit_sha = self._run_git(["rev-parse", "HEAD"], cwd=repo_path).strip()

        logger.info(
            "Repository prepared for analysis: url=%s branch=%s commit=%s cache_hit=%s shallow=%s depth=%s",
            self._sanitize_url(repository_url),
            effective_branch,
            commit_sha,
            cache_hit,
            self.shallow_clone,
            self.clone_depth if self.shallow_clone else None,
        )

        return RepositoryCloneResult(
            local_path=str(repo_path),
            cache_hit=cache_hit,
            shallow_clone=self.shallow_clone,
            clone_depth=self.clone_depth if self.shallow_clone else None,
            directory_scope=directory_scope,
            branch_name=effective_branch,
            commit_sha=commit_sha,
        )

    def _run_git(self, args: list[str], cwd: Optional[Path]) -> str:
        cmd = ["git", *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            message = stderr or stdout or str(e)
            raise RepositoryCloneError(f"Git command failed ({' '.join(cmd)}): {message}")
        except subprocess.TimeoutExpired:
            raise RepositoryCloneError(f"Git command timed out ({' '.join(cmd)})")
        except FileNotFoundError:
            raise RepositoryCloneError("Git executable not found on server")

    def _resolve_default_branch(self, repo_path: Path) -> Optional[str]:
        try:
            symbolic_ref = self._run_git(
                ["symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=repo_path,
            ).strip()
            if symbolic_ref.startswith("refs/remotes/origin/"):
                return symbolic_ref.split("refs/remotes/origin/")[-1]
        except RepositoryCloneError:
            pass
        return None

    def _is_shallow_repo(self, repo_path: Path) -> bool:
        try:
            value = self._run_git(["rev-parse", "--is-shallow-repository"], cwd=repo_path).strip().lower()
            return value == "true"
        except RepositoryCloneError:
            return False

    def _build_cache_key(
        self,
        repository_url: str,
        branch_name: Optional[str],
        directory_scope: Optional[list[str]],
    ) -> str:
        normalized = self._sanitize_url(repository_url).lower().strip()
        scope_part = ",".join(directory_scope) if directory_scope else ""
        key_src = f"{normalized}|{branch_name or ''}|{scope_part}"
        return hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:24]

    def _apply_directory_scope(self, repo_path: Path, directory_scope: list[str]) -> None:
        self._run_git(["sparse-checkout", "init", "--cone"], cwd=repo_path)
        self._run_git(["sparse-checkout", "set", *directory_scope], cwd=repo_path)

    def _build_authenticated_url(
        self,
        repository_url: str,
        github_access_token: Optional[str],
        gitlab_access_token: Optional[str],
        gitlab_base_url: Optional[str],
    ) -> str:
        parsed = urlparse(repository_url)
        if not parsed.scheme:
            parsed = urlparse(f"https://{repository_url}")

        hostname = parsed.hostname or ""
        if not hostname:
            return repository_url

        username: Optional[str] = None
        password: Optional[str] = None
        is_github = "github.com" in hostname.lower()
        is_gitlab = "gitlab" in hostname.lower()

        if not is_gitlab and gitlab_base_url:
            gitlab_host = urlparse(
                gitlab_base_url if gitlab_base_url.startswith("http") else f"https://{gitlab_base_url}"
            ).hostname
            if gitlab_host and hostname.lower() == gitlab_host.lower():
                is_gitlab = True

        if is_github and github_access_token:
            username = "x-access-token"
            password = github_access_token
        elif is_gitlab and gitlab_access_token:
            username = "oauth2"
            password = gitlab_access_token

        if not username or not password:
            return repository_url

        host = hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        netloc = f"{username}:{quote(password, safe='')}@{host}"
        rebuilt = parsed._replace(netloc=netloc)
        return urlunparse(rebuilt)

    @staticmethod
    def _sanitize_url(repository_url: str) -> str:
        parsed = urlparse(repository_url)
        if not parsed.netloc:
            return repository_url
        host = parsed.hostname or parsed.netloc
        if parsed.port:
            host = f"{host}:{parsed.port}"
        cleaned = parsed._replace(netloc=host)
        return urlunparse(cleaned)

    @staticmethod
    def _parse_bool_env(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_int_env(value: Optional[str], default: int) -> int:
        if value is None:
            return default
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_directory_scope(directory_scope: Optional[list[str]]) -> Optional[list[str]]:
        if not directory_scope:
            return None

        normalized: list[str] = []
        for raw_path in directory_scope:
            if raw_path is None:
                continue
            path = raw_path.strip().replace("\\", "/")
            while path.startswith("./"):
                path = path[2:]
            path = path.strip("/")

            if not path:
                continue
            if path.startswith("..") or "/.." in path or "../" in path:
                raise RepositoryCloneError(f"Invalid directory scope path: {raw_path}")
            if ":" in path:
                raise RepositoryCloneError(f"Invalid directory scope path: {raw_path}")

            normalized.append(path)

        if not normalized:
            return None

        # Deduplicate while preserving deterministic ordering.
        return sorted(set(normalized))
