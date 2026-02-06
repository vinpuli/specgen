"""
Tool Versioning and Compatibility Checks for LangGraph agents.

Provides comprehensive versioning system:
- Semantic versioning for tools
- Version compatibility checking
- Breaking change detection
- Deprecation management
- Migration path generation
- Changelog generation
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Type
from uuid import UUID


class VersionChangeType(str, Enum):
    """Type of version change."""

    MAJOR = "major"  # Breaking change
    MINOR = "minor"  # New feature (backward compatible)
    PATCH = "patch"  # Bug fix (backward compatible)
    NONE = "none"    # No change


class CompatibilityLevel(str, Enum):
    """Level of compatibility between versions."""

    FULL = "full"           # Fully compatible
    PARTIAL = "partial"     # Some breaking changes
    NONE = "none"           # Incompatible
    DEPRECATED = "deprecated"  # Tool is deprecated


class BreakingChangeType(str, Enum):
    """Types of breaking changes."""

    PARAMETER_REMOVED = "parameter_removed"
    PARAMETER_RENAMED = "parameter_renamed"
    PARAMETER_TYPE_CHANGED = "parameter_type_changed"
    PARAMETER_REQUIRED_ADDED = "parameter_required_added"
    PARAMETER_DEFAULT_CHANGED = "parameter_default_changed"
    RETURN_TYPE_CHANGED = "return_type_changed"
    RETURN_STRUCTURE_CHANGED = "return_structure_changed"
    BEHAVIOR_CHANGED = "behavior_changed"
    ERROR_CODES_CHANGED = "error_codes_changed"
    PERMISSION_REQUIRED = "permission_required"


class DeprecationStatus(str, Enum):
    """Deprecation status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass
class BreakingChange:
    """A breaking change between versions."""

    change_type: BreakingChangeType
    description: str
    severity: str  # "high", "medium", "low"
    migration_guide: Optional[str] = None
    affected_parameters: List[str] = field(default_factory=list)
    affected_returns: bool = False


@dataclass
class VersionInfo:
    """Version information for a tool."""

    version: str
    release_date: str
    changelog: str
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    new_features: List[str] = field(default_factory=list)
    bug_fixes: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
    is_deprecated: bool = False
    deprecation_date: Optional[str] = None
    removal_date: Optional[str] = None
    replacement_tool: Optional[str] = None


@dataclass
class ParameterSpec:
    """Parameter specification for compatibility checking."""

    name: str
    param_type: str
    required: bool
    default: Any = None
    enum_values: Optional[List[str]] = None


@dataclass
class CompatibilityReport:
    """Report of compatibility between two versions."""

    old_version: str
    new_version: str
    compatibility_level: CompatibilityLevel
    change_type: VersionChangeType
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    migration_required: bool = False
    migration_steps: List[str] = field(default_factory=list)
    score: float = 0.0  # 0-100 compatibility score


@dataclass
class ToolVersion:
    """Versioned tool with metadata."""

    tool_name: str
    version: str
    schema_version: str  # Schema version for this definition
    parameters: List[ParameterSpec] = field(default_factory=list)
    return_type: Optional[str] = None
    return_schema: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class VersionParser:
    """Parse and compare semantic versions."""

    # Regex for semantic versioning (major.minor.patch[-prerelease][+build])
    SEMANTIC_VERSION_PATTERN = re.compile(
        r"^(?P<major>0|[1-9]\d*)\."
        r"(?P<minor>0|[1-9]\d*)\."
        r"(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    @classmethod
    def parse(cls, version: str) -> Tuple[int, int, int, str, str]:
        """
        Parse a semantic version string.

        Returns:
            Tuple of (major, minor, patch, prerelease, build)
        """
        match = cls.SEMANTIC_VERSION_PATTERN.match(version)
        if not match:
            raise ValueError(f"Invalid semantic version: {version}")

        groups = match.groupdict()
        major = int(groups["major"])
        minor = int(groups["minor"])
        patch = int(groups["patch"])
        prerelease = groups["prerelease"] or ""
        build = groups["buildmetadata"] or ""

        return (major, minor, patch, prerelease, build)

    @classmethod
    def compare(cls, v1: str, v2: str) -> int:
        """
        Compare two semantic versions.

        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """
        p1 = cls.parse(v1)
        p2 = cls.parse(v2)

        for i in range(3):  # major, minor, patch
            if p1[i] < p2[i]:
                return -1
            elif p1[i] > p2[i]:
                return 1

        # Compare prerelease
        prerelease1 = p1[3]
        prerelease2 = p2[3]

        if prerelease1 == prerelease2:
            return 0
        elif not prerelease1:
            return 1  # Release > prerelease
        elif not prerelease2:
            return -1  # Prerelease < release
        else:
            # Compare prerelease parts
            parts1 = prerelease1.split(".")
            parts2 = prerelease2.split(".")
            for i in range(min(len(parts1), len(parts2))):
                part1 = parts1[i]
                part2 = parts2[i]
                # Try numeric comparison
                try:
                    n1 = int(part1)
                    n2 = int(part2)
                    if n1 < n2:
                        return -1
                    elif n1 > n2:
                        return 1
                except ValueError:
                    # String comparison
                    if part1 < part2:
                        return -1
                    elif part1 > part2:
                        return 1

            # Shorter prerelease is smaller
            return -1 if len(parts1) < len(parts2) else 1

    @classmethod
    def get_change_type(cls, old_version: str, new_version: str) -> VersionChangeType:
        """
        Determine the type of change between versions.

        Args:
            old_version: Previous version
            new_version: New version

        Returns:
            VersionChangeType indicating the change level
        """
        p_old = cls.parse(old_version)
        p_new = cls.parse(new_version)

        # Major version changed
        if p_old[0] != p_new[0]:
            return VersionChangeType.MAJOR

        # Minor version changed
        if p_old[1] != p_new[1]:
            return VersionChangeType.MINOR

        # Patch version changed
        if p_old[2] != p_new[2]:
            return VersionChangeType.PATCH

        return VersionChangeType.NONE

    @classmethod
    def format_version(
        cls,
        major: int,
        minor: int,
        patch: int,
        prerelease: str = "",
        build: str = "",
    ) -> str:
        """Format a version string."""
        version = f"{major}.{minor}.{patch}"
        if prerelease:
            version += f"-{prerelease}"
        if build:
            version += f"+{build}"
        return version


class CompatibilityChecker:
    """Check compatibility between tool versions."""

    def __init__(self):
        """Initialize the compatibility checker."""
        self._breaking_change_rules: Dict[BreakingChangeType, str] = {}

    def check_parameter_compatibility(
        self,
        old_params: List[ParameterSpec],
        new_params: List[ParameterSpec],
    ) -> List[BreakingChange]:
        """
        Check parameter compatibility between versions.

        Args:
            old_params: Previous version parameters
            new_params: New version parameters

        Returns:
            List of breaking changes
        """
        breaking_changes: List[BreakingChange] = []

        old_param_map = {p.name: p for p in old_params}
        new_param_map = {p.name: p for p in new_params}

        # Check for removed parameters
        for name, param in old_param_map.items():
            if name not in new_param_map:
                breaking_changes.append(
                    BreakingChange(
                        change_type=BreakingChangeType.PARAMETER_REMOVED,
                        description=f"Parameter '{name}' was removed",
                        severity="high",
                        migration_guide=f"Remove '{name}' from your calls to this tool",
                        affected_parameters=[name],
                    )
                )

        # Check for renamed parameters
        # This requires manual mapping - we can only detect potential renames
        # by type and position similarity
        for name, param in new_param_map.items():
            if name not in old_param_map:
                # Check if this might be a rename
                for old_name, old_param in old_param_map.items():
                    if old_name not in new_param_map:
                        # Similar types, different names
                        if param.param_type == old_param.param_type:
                            breaking_changes.append(
                                BreakingChange(
                                    change_type=BreakingChangeType.PARAMETER_RENAMED,
                                    description=f"Parameter may have been renamed from '{old_name}' to '{name}'",
                                    severity="medium",
                                    migration_guide=f"Rename parameter '{old_name}' to '{name}'",
                                    affected_parameters=[name, old_name],
                                )
                            )
                            break

        # Check for type changes
        for name, param in new_param_map.items():
            if name in old_param_map:
                old_param = old_param_map[name]
                if param.param_type != old_param.param_type:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=BreakingChangeType.PARAMETER_TYPE_CHANGED,
                            description=f"Parameter '{name}' type changed from '{old_param.param_type}' to '{param.param_type}'",
                            severity="high",
                            migration_guide=f"Update parameter type to '{param.param_type}'",
                            affected_parameters=[name],
                        )
                    )

        # Check for new required parameters
        for name, param in new_param_map.items():
            if name in old_param_map:
                old_param = old_param_map[name]
                if param.required and not old_param.required:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=BreakingChangeType.PARAMETER_REQUIRED_ADDED,
                            description=f"Parameter '{name}' is now required",
                            severity="high",
                            migration_guide=f"Provide value for required parameter '{name}'",
                            affected_parameters=[name],
                        )
                    )

        return breaking_changes

    def check_return_compatibility(
        self,
        old_return_type: Optional[str],
        new_return_type: Optional[str],
        old_return_schema: Optional[Dict[str, Any]],
        new_return_schema: Optional[Dict[str, Any]],
    ) -> List[BreakingChange]:
        """Check return type compatibility."""
        breaking_changes: List[BreakingChange] = []

        if old_return_type != new_return_type:
            breaking_changes.append(
                BreakingChange(
                    change_type=BreakingChangeType.RETURN_TYPE_CHANGED,
                    description=f"Return type changed from '{old_return_type}' to '{new_return_type}'",
                    severity="high",
                    affected_returns=True,
                )
            )

        return breaking_changes

    def generate_compatibility_report(
        self,
        old_version: str,
        new_version: str,
        old_params: List[ParameterSpec],
        new_params: List[ParameterSpec],
        old_return_type: Optional[str] = None,
        new_return_type: Optional[str] = None,
        old_return_schema: Optional[Dict[str, Any]] = None,
        new_return_schema: Optional[Dict[str, Any]] = None,
    ) -> CompatibilityReport:
        """
        Generate a full compatibility report.

        Args:
            old_version: Previous version string
            new_version: New version string
            old_params: Previous version parameters
            new_params: New version parameters
            old_return_type: Previous return type
            new_return_type: New return type
            old_return_schema: Previous return schema
            new_return_schema: New return schema

        Returns:
            CompatibilityReport with full analysis
        """
        change_type = VersionParser.get_change_type(old_version, new_version)
        breaking_changes: List[BreakingChange] = []
        warnings: List[str] = []
        migration_steps: List[str] = []

        # Check parameter compatibility
        param_changes = self.check_parameter_compatibility(old_params, new_params)
        breaking_changes.extend(param_changes)

        # Check return compatibility
        return_changes = self.check_return_compatibility(
            old_return_type,
            new_return_type,
            old_return_schema,
            new_return_schema,
        )
        breaking_changes.extend(return_changes)

        # Generate migration steps
        for change in breaking_changes:
            if change.migration_guide:
                migration_steps.append(change.migration_guide)

        # Determine compatibility level
        if change_type == VersionChangeType.NONE:
            compatibility = CompatibilityLevel.FULL
            score = 100.0
        elif change_type == VersionChangeType.PATCH:
            compatibility = CompatibilityLevel.FULL
            score = 95.0 - (len(breaking_changes) * 10)
        elif change_type == VersionChangeType.MINOR:
            if breaking_changes:
                compatibility = CompatibilityLevel.PARTIAL
                score = 70.0 - (len(breaking_changes) * 10)
            else:
                compatibility = CompatibilityLevel.FULL
                score = 90.0
        else:  # MAJOR
            if breaking_changes:
                compatibility = CompatibilityLevel.NONE
                score = max(0.0, 50.0 - (len(breaking_changes) * 15))
            else:
                compatibility = CompatibilityLevel.PARTIAL
                score = 60.0

        if breaking_changes:
            migration_required = True
        else:
            migration_required = False

        return CompatibilityReport(
            old_version=old_version,
            new_version=new_version,
            compatibility_level=compatibility,
            change_type=change_type,
            breaking_changes=breaking_changes,
            warnings=warnings,
            migration_required=migration_required,
            migration_steps=migration_steps,
            score=score,
        )


class ToolVersionManager:
    """
    Manage tool versions and compatibility.

    Features:
    - Track tool versions
    - Check compatibility between versions
    - Generate migration guides
    - Manage deprecations
    - Generate changelogs
    """

    def __init__(self):
        """Initialize the version manager."""
        self._versions: Dict[str, List[VersionInfo]] = {}  # tool_name -> versions
        self._latest_versions: Dict[str, str] = {}  # tool_name -> latest version
        self._compatibility_checker = CompatibilityChecker()

    def register_version(self, tool_name: str, version_info: VersionInfo) -> None:
        """
        Register a new version for a tool.

        Args:
            tool_name: Name of the tool
            version_info: Version information
        """
        if tool_name not in self._versions:
            self._versions[tool_name] = []

        self._versions[tool_name].append(version_info)

        # Update latest version
        latest = self._latest_versions.get(tool_name)
        if latest is None or VersionParser.compare(latest, version_info.version) < 0:
            self._latest_versions[tool_name] = version_info.version

    def get_version_history(self, tool_name: str) -> List[VersionInfo]:
        """Get all versions for a tool, sorted by release date."""
        if tool_name not in self._versions:
            return []

        def version_key(v: VersionInfo) -> Tuple[int, int, int, str, str]:
            """Sort key that includes prerelease for proper semver ordering."""
            return VersionParser.parse(v.version)

        versions = sorted(
            self._versions[tool_name],
            key=version_key,
            reverse=True,
        )
        return versions

    def get_latest_version(self, tool_name: str) -> Optional[VersionInfo]:
        """Get the latest version of a tool."""
        if tool_name not in self._versions:
            return None

        latest = self._latest_versions.get(tool_name)
        if latest is None:
            return None

        for version in self._versions[tool_name]:
            if version.version == latest:
                return version
        return None

    def get_version(self, tool_name: str, version: str) -> Optional[VersionInfo]:
        """Get a specific version of a tool."""
        if tool_name not in self._versions:
            return None

        for v in self._versions[tool_name]:
            if v.version == version:
                return v
        return None

    def check_compatibility(
        self,
        tool_name: str,
        old_version: str,
        new_version: Optional[str] = None,
    ) -> CompatibilityReport:
        """
        Check compatibility between tool versions.

        Args:
            tool_name: Name of the tool
            old_version: Version to check from
            new_version: Version to check against (defaults to latest)

        Returns:
            CompatibilityReport
        """
        if new_version is None:
            latest = self.get_latest_version(tool_name)
            if latest is None:
                raise ValueError(f"No versions registered for tool: {tool_name}")
            new_version = latest.version

        old_v = self.get_version(tool_name, old_version)
        new_v = self.get_version(tool_name, new_version)

        if old_v is None:
            raise ValueError(f"Version {old_version} not found for tool: {tool_name}")
        if new_v is None:
            raise ValueError(f"Version {new_version} not found for tool: {tool_name}")

        return self._compatibility_checker.generate_compatibility_report(
            old_version=old_version,
            new_version=new_version,
            old_params=[],
            new_params=[],
        )

    def is_version_deprecated(self, tool_name: str, version: str) -> bool:
        """Check if a specific version is deprecated."""
        version_info = self.get_version(tool_name, version)
        if version_info is None:
            return False
        return version_info.is_deprecated

    def get_deprecation_info(
        self, tool_name: str, version: str
    ) -> Optional[Dict[str, Any]]:
        """Get deprecation information for a version."""
        version_info = self.get_version(tool_name, version)
        if version_info is None:
            return None

        return {
            "is_deprecated": version_info.is_deprecated,
            "deprecation_date": version_info.deprecation_date,
            "removal_date": version_info.removal_date,
            "replacement_tool": version_info.replacement_tool,
        }

    def generate_changelog(
        self, tool_name: str, from_version: Optional[str] = None, to_version: Optional[str] = None
    ) -> str:
        """
        Generate a changelog for a tool.

        Args:
            tool_name: Name of the tool
            from_version: Start version (defaults to first version)
            to_version: End version (defaults to latest)

        Returns:
            Changelog in Markdown format
        """
        versions = self.get_version_history(tool_name)

        if not versions:
            return f"# Changelog for {tool_name}\n\nNo versions recorded."

        # Determine range
        if to_version is None:
            to_version = versions[0].version if versions else None
        if from_version is None:
            from_version = versions[-1].version if versions else None

        # Find indices
        from_idx = None
        to_idx = None
        for i, v in enumerate(versions):
            if v.version == to_version:
                to_idx = i
            if v.version == from_version:
                from_idx = i

        if from_idx is None:
            from_idx = len(versions) - 1
        if to_idx is None:
            to_idx = 0

        # Generate changelog
        lines = [f"# Changelog: {tool_name}\n"]
        lines.append(f"_Generated: {datetime.utcnow().isoformat()}_\n")

        for i in range(to_idx, from_idx + 1):
            v = versions[i]
            lines.append(f"## {v.version}")
            lines.append(f"_Release Date: {v.release_date}_\n")

            if v.is_deprecated:
                lines.append(f"⚠️ **DEPRECATED**\n")

            if v.new_features:
                lines.append("### New Features")
                for feature in v.new_features:
                    lines.append(f"- {feature}")
                lines.append("")

            if v.bug_fixes:
                lines.append("### Bug Fixes")
                for fix in v.bug_fixes:
                    lines.append(f"- {fix}")
                lines.append("")

            if v.breaking_changes:
                lines.append("### Breaking Changes")
                for change in v.breaking_changes:
                    lines.append(f"- **{change.change_type}**: {change.description}")
                    if change.migration_guide:
                        lines.append(f"  - Migration: {change.migration_guide}")
                lines.append("")

            if v.known_issues:
                lines.append("### Known Issues")
                for issue in v.known_issues:
                    lines.append(f"- {issue}")
                lines.append("")

            lines.append("---\n")

        return "\n".join(lines)


# Convenience functions
def create_version_manager() -> ToolVersionManager:
    """Create a new version manager."""
    return ToolVersionManager()


def create_compatibility_checker() -> CompatibilityChecker:
    """Create a new compatibility checker."""
    return CompatibilityChecker()


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse a semantic version string."""
    return VersionParser.parse(version)[:3]


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic versions."""
    return VersionParser.compare(v1, v2)


# Example usage
def demonstrate_versioning():
    """Demonstrate the versioning system."""
    manager = ToolVersionManager()

    # Register versions
    v1 = VersionInfo(
        version="1.0.0",
        release_date="2024-01-01",
        changelog="Initial release",
        new_features=["Initial feature set"],
    )
    manager.register_version("my_tool", v1)

    v2 = VersionInfo(
        version="1.1.0",
        release_date="2024-02-01",
        changelog="Minor update",
        new_features=["Added new parameter 'filter'"],
    )
    manager.register_version("my_tool", v2)

    v3 = VersionInfo(
        version="2.0.0",
        release_date="2024-03-01",
        changelog="Major update with breaking changes",
        breaking_changes=[
            BreakingChange(
                change_type=BreakingChangeType.PARAMETER_REMOVED,
                description="Removed 'old_param' parameter",
                severity="high",
                migration_guide="Remove 'old_param' from your calls",
                affected_parameters=["old_param"],
            )
        ],
        new_features=["Completely new API"],
    )
    manager.register_version("my_tool", v3)

    # Check compatibility
    report = manager.check_compatibility("my_tool", "1.0.0", "2.0.0")
    print(f"Compatibility: {report.compatibility_level}")
    print(f"Change Type: {report.change_type}")
    print(f"Breaking Changes: {len(report.breaking_changes)}")

    # Generate changelog
    changelog = manager.generate_changelog("my_tool", "1.0.0", "2.0.0")
    print(changelog)
