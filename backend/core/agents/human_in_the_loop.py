"""
Human-in-the-Loop (HITL) interrupt system for LangGraph agents.

This module provides:
1. Interrupt configuration and types
2. interrupt() calls in agents for human approval
3. Response handlers for human inputs
4. Timeout and auto-reject policies
"""

from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from datetime import datetime, timedelta
from uuid import uuid4
from pydantic import BaseModel, Field
from langgraph.types import Interrupt, Command


# ==================== Interrupt Types ====================

class InterruptType(str, Enum):
    """Types of human-in-the-loop interrupts."""
    CONTRADICTION_RESOLUTION = "contradiction_resolution"
    DECISION_LOCKING = "decision_locking"
    ARTIFACT_APPROVAL = "artifact_approval"
    BRANCH_MERGE = "branch_merge"
    QUESTION_DEFERRAL = "question_deferral"
    GENERATION_APPROVAL = "generation_approval"
    CUSTOM = "custom"


class InterruptStatus(str, Enum):
    """Status of an interrupt."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IGNORED = "ignored"
    TIMEOUT = "timeout"
    EXPIRED = "expired"


class InterruptPriority(str, Enum):
    """Priority levels for interrupts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== Interrupt Configuration ====================

class HumanInterruptConfig(BaseModel):
    """Configuration for a human interrupt."""
    interrupt_id: str = Field(default_factory=lambda: str(uuid4()))
    interrupt_type: InterruptType
    priority: InterruptPriority = InterruptPriority.MEDIUM
    title: str
    description: str
    options: List[str] = Field(default_factory=list)
    allow_ignore: bool = True
    allow_response: bool = True
    timeout_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if the interrupt has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_timed_out(self) -> bool:
        """Check if the interrupt has timed out."""
        if self.timeout_seconds is None:
            return False
        return datetime.utcnow() > (self.created_at + timedelta(seconds=self.timeout_seconds))
    
    def can_ignore(self) -> bool:
        """Check if this interrupt can be ignored."""
        return self.allow_ignore
    
    def can_respond(self) -> bool:
        """Check if custom response is allowed for this interrupt."""
        return self.allow_response
    
    def get_available_actions(self) -> List[str]:
        """Get list of available actions based on configuration."""
        actions = []
        if self.options:
            actions.extend(self.options)
        if self.allow_response:
            actions.append("Custom Response")
        if self.allow_ignore:
            actions.append("Ignore")
        return actions


class InterruptResponse(BaseModel):
    """Response from a human to an interrupt."""
    response_id: str = Field(default_factory=lambda: str(uuid4()))
    interrupt_id: str
    user_id: Optional[str] = None
    status: InterruptStatus
    response: Optional[str] = None
    comment: Optional[str] = None
    responded_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CustomInterruptResponse(InterruptResponse):
    """
    Extended response for custom/free-form responses.
    
    Used when allow_response=True and user provides custom input.
    """
    response_type: str = "custom"  # "custom", "selected_option", "ignored"
    selected_option_index: Optional[int] = None
    validation_warnings: List[str] = Field(default_factory=list)


# ==================== Contradiction Interrupt Configuration ====================

class ContradictionResolutionOption(str, Enum):
    """Resolution options for contradictions."""
    KEEP_BOTH_REVISE = "keep_both_revise"
    KEEP_FIRST_ONLY = "keep_first_only"
    KEEP_SECOND_ONLY = "keep_second_only"
    MERGE_DECISIONS = "merge_decisions"
    DEFER_RESOLUTION = "defer_resolution"
    REJECT_ARTIFACT = "reject_artifact"


class ContradictionSeverity(str, Enum):
    """Severity levels for contradictions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContradictionDetails(BaseModel):
    """Details about a detected contradiction."""
    decision_1_id: str
    decision_2_id: str
    decision_1_question: str
    decision_1_answer: str
    decision_2_question: str
    decision_2_answer: str
    similarity_score: float
    severity: ContradictionSeverity
    affected_artifacts: List[str] = Field(default_factory=list)
    affected_decisions: List[str] = Field(default_factory=list)


class ContradictionInterruptConfig(HumanInterruptConfig):
    """
    Configuration specifically for contradiction resolution interrupts.
    
    This class extends HumanInterruptConfig with fields specific to
    contradiction resolution, including the conflicting decisions,
    severity assessment, and impact analysis.
    """
    
    # Contradiction-specific fields
    contradiction_details: ContradictionDetails
    resolution_options: List[ContradictionResolutionOption] = Field(default_factory=list)
    
    # Impact assessment
    impact_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # Suggestion based on analysis
    suggested_resolution: Optional[ContradictionResolutionOption] = None
    suggested_reasoning: Optional[str] = None
    
    # Allow multiple contradictions to be resolved together
    batch_mode: bool = False
    related_interrupt_ids: List[str] = Field(default_factory=list)
    
    @classmethod
    def create(
        cls,
        decision_1_id: str,
        decision_2_id: str,
        decision_1_question: str,
        decision_1_answer: str,
        decision_2_question: str,
        decision_2_answer: str,
        similarity_score: float,
        severity: ContradictionSeverity = ContradictionSeverity.MEDIUM,
        affected_artifacts: Optional[List[str]] = None,
        affected_decisions: Optional[List[str]] = None,
        timeout_seconds: int = 600,
        impact_analysis: Optional[Dict[str, Any]] = None,
        suggested_resolution: Optional[ContradictionResolutionOption] = None,
        suggested_reasoning: Optional[str] = None,
    ) -> "ContradictionInterruptConfig":
        """
        Factory method to create a ContradictionInterruptConfig.
        
        Args:
            decision_1_id: ID of the first conflicting decision
            decision_2_id: ID of the second conflicting decision
            decision_1_question: Question text for decision 1
            decision_1_answer: Answer text for decision 1
            decision_2_question: Question text for decision 2
            decision_2_answer: Answer text for decision 2
            similarity_score: Similarity score between decisions (0-1)
            severity: Severity level of the contradiction
            affected_artifacts: List of artifact IDs affected by this contradiction
            affected_decisions: List of decision IDs affected by this contradiction
            timeout_seconds: Timeout in seconds
            impact_analysis: Dictionary with impact analysis results
            suggested_resolution: AI-suggested resolution option
            suggested_reasoning: Reasoning for the suggested resolution
        
        Returns:
            ContradictionInterruptConfig instance
        """
        # Determine severity based on similarity score
        if similarity_score >= 0.9:
            severity = ContradictionSeverity.CRITICAL
        elif similarity_score >= 0.7:
            severity = ContradictionSeverity.HIGH
        elif similarity_score >= 0.5:
            severity = ContradictionSeverity.MEDIUM
        else:
            severity = ContradictionSeverity.LOW
        
        details = ContradictionDetails(
            decision_1_id=decision_1_id,
            decision_2_id=decision_2_id,
            decision_1_question=decision_1_question,
            decision_1_answer=decision_1_answer,
            decision_2_question=decision_2_question,
            decision_2_answer=decision_2_answer,
            similarity_score=similarity_score,
            severity=severity,
            affected_artifacts=affected_artifacts or [],
            affected_decisions=affected_decisions or [],
        )
        
        # Build description with contradiction details
        severity_emoji = {
            ContradictionSeverity.LOW: "🟢",
            ContradictionSeverity.MEDIUM: "🟡",
            ContradictionSeverity.HIGH: "🟠",
            ContradictionSeverity.CRITICAL: "🔴",
        }
        
        description = f"""# Contradiction Detected {severity_emoji.get(severity, '⚪')}

A potential contradiction has been detected between two decisions in your project.

## Decision 1
**ID:** {decision_1_id}
**Question:** {decision_1_question}
**Answer:** {decision_1_answer}

## Decision 2
**ID:** {decision_2_id}
**Question:** {decision_2_question}
**Answer:** {decision_2_answer}

## Analysis
**Similarity Score:** {similarity_score:.2%}
**Severity:** {severity.value.upper()}
"""
        
        if affected_artifacts:
            description += f"\n**Affected Artifacts:** {', '.join(affected_artifacts)}"
        
        if affected_decisions:
            description += f"\n**Affected Decisions:** {', '.join(affected_decisions)}"
        
        if impact_analysis:
            description += f"\n\n## Impact Analysis\n"
            for key, value in impact_analysis.items():
                description += f"- **{key}:** {value}\n"
        
        description += """\n## Resolution Options

Please select how you would like to resolve this contradiction:

1. **Keep Both (Revise One)** - Keep both decisions but revise one to remove the contradiction
2. **Keep First Only** - Discard Decision 2 and keep Decision 1
3. **Keep Second Only** - Discard Decision 1 and keep Decision 2
4. **Merge Decisions** - Combine the best parts of both decisions
5. **Defer Resolution** - Postpone resolution until more information is available

"""
        
        if suggested_resolution:
            description += f"""## AI Suggestion

**Suggested Resolution:** {suggested_resolution.value.replace('_', ' ').title()}

**Reasoning:** {suggested_reasoning or 'The AI analyzed both decisions and believes this resolution option would be most appropriate.'}

You can accept this suggestion or choose a different resolution.
"""
        
        return cls(
            interrupt_type=InterruptType.CONTRADICTION_RESOLUTION,
            title=f"Contradiction: Decision {decision_1_id[:8]} vs {decision_2_id[:8]}",
            description=description,
            priority=InterruptPriority.HIGH if severity in [ContradictionSeverity.HIGH, ContradictionSeverity.CRITICAL] else InterruptPriority.MEDIUM,
            options=[
                "Keep Both (Revise One)",
                "Keep First Only",
                "Keep Second Only",
                "Merge Decisions",
                "Defer Resolution",
            ],
            timeout_seconds=timeout_seconds,
            contradiction_details=details,
            resolution_options=[
                ContradictionResolutionOption.KEEP_BOTH_REVISE,
                ContradictionResolutionOption.KEEP_FIRST_ONLY,
                ContradictionResolutionOption.KEEP_SECOND_ONLY,
                ContradictionResolutionOption.MERGE_DECISIONS,
                ContradictionResolutionOption.DEFER_RESOLUTION,
            ],
            impact_analysis=impact_analysis or {},
            suggested_resolution=suggested_resolution,
            suggested_reasoning=suggested_reasoning,
        )
    
    def get_affected_decision_ids(self) -> List[str]:
        """Get the IDs of all decisions affected by this contradiction."""
        return [
            self.contradiction_details.decision_1_id,
            self.contradiction_details.decision_2_id,
        ] + self.contradiction_details.affected_decisions
    
    def get_affected_artifact_ids(self) -> List[str]:
        """Get the IDs of all artifacts affected by this contradiction."""
        return self.contradiction_details.affected_artifacts
    
    def to_interrupt_value(self) -> Dict[str, Any]:
        """Convert to a value suitable for LangGraph Interrupt."""
        return {
            "interrupt_id": self.interrupt_id,
            "interrupt_type": self.interrupt_type.value,
            "title": self.title,
            "description": self.description,
            "options": self.options,
            "priority": self.priority.value,
            "severity": self.contradiction_details.severity.value,
            "similarity_score": self.contradiction_details.similarity_score,
            "decision_1": {
                "id": self.contradiction_details.decision_1_id,
                "question": self.contradiction_details.decision_1_question,
                "answer": self.contradiction_details.decision_1_answer,
            },
            "decision_2": {
                "id": self.contradiction_details.decision_2_id,
                "question": self.contradiction_details.decision_2_question,
                "answer": self.contradiction_details.decision_2_answer,
            },
            "affected_artifacts": self.contradiction_details.affected_artifacts,
            "affected_decisions": self.contradiction_details.affected_decisions,
            "impact_analysis": self.impact_analysis,
            "suggested_resolution": self.suggested_resolution.value if self.suggested_resolution else None,
            "suggested_reasoning": self.suggested_reasoning,
        }


class ContradictionResolutionResponse(InterruptResponse):
    """
    Response specifically for contradiction resolution interrupts.
    
    Extends InterruptResponse with fields for tracking the specific
    resolution action taken and any resulting changes.
    """
    
    # Contradiction-specific response fields
    resolution_option: ContradictionResolutionOption
    
    # If revision was chosen
    revised_decision_id: Optional[str] = None
    revised_decision_text: Optional[str] = None
    
    # If merge was chosen
    merged_decision_text: Optional[str] = None
    
    # Track which decision was discarded (if any)
    discarded_decision_id: Optional[str] = None
    
    def get_resolved_decision_ids(self) -> List[str]:
        """Get the IDs of decisions that remain after resolution."""
        if self.resolution_option == ContradictionResolutionOption.KEEP_FIRST_ONLY:
            # Return decision_1_id from the interrupt config
            return []  # Need to get from interrupt config
        elif self.resolution_option == ContradictionResolutionOption.KEEP_SECOND_ONLY:
            return []  # Need to get from interrupt config
        elif self.resolution_option == ContradictionResolutionOption.MERGE_DECISIONS:
            return [self.revised_decision_id or "merged"]
        else:
            return []
    
    def get_discarded_decision_ids(self) -> List[str]:
        """Get the IDs of decisions that were discarded."""
        if self.resolution_option == ContradictionResolutionOption.KEEP_FIRST_ONLY:
            return [self.discarded_decision_id or "decision_2"]
        elif self.resolution_option == ContradictionResolutionOption.KEEP_SECOND_ONLY:
            return [self.discarded_decision_id or "decision_1"]
        return []


# ==================== Decision Lock Interrupt Configuration ====================

class DecisionLockAction(str, Enum):
    """Actions for decision locking."""
    LOCK = "lock"
    UNLOCK = "unlock"
    TEMPORARY_UNLOCK = "temporary_unlock"


class DecisionLockSeverity(str, Enum):
    """Severity levels for decision locking."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionLockDetails(BaseModel):
    """Details about a decision being locked/unlocked."""
    decision_id: str
    decision_question: str
    decision_answer: str
    decision_category: str
    is_locked: bool = False
    affected_artifacts: List[str] = Field(default_factory=list)
    affected_decisions: List[str] = Field(default_factory=list)
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
   

class DecisionLockInterruptConfig(HumanInterruptConfig):
    """
    Configuration specifically for decision locking interrupts.
    
    This class extends HumanInterruptConfig with fields specific to
    decision locking, including impact analysis and history.
    """
    
    # Decision lock-specific fields
    decision_details: DecisionLockDetails
    lock_action: DecisionLockAction
    severity: DecisionLockSeverity
    
    # Impact assessment
    impact_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # History tracking
    lock_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Approval requirements
    requires_approval: bool = True
    approval_threshold: str = "any_member"
    
    @classmethod
    def create_lock_request(
        cls,
        decision_id: str,
        decision_question: str,
        decision_answer: str,
        decision_category: str,
        affected_artifacts: Optional[List[str]] = None,
        affected_decisions: Optional[List[str]] = None,
        timeout_seconds: int = 300,
        impact_analysis: Optional[Dict[str, Any]] = None,
    ) -> "DecisionLockInterruptConfig":
        """
        Factory method to create a decision lock interrupt.
        
        Args:
            decision_id: ID of the decision to lock
            decision_question: Question text for the decision
            decision_answer: Answer text for the decision
            decision_category: Category of the decision
            affected_artifacts: List of artifact IDs affected by this lock
            affected_decisions: List of decision IDs affected by this lock
            timeout_seconds: Timeout in seconds
            impact_analysis: Dictionary with impact analysis results
        
        Returns:
            DecisionLockInterruptConfig instance
        """
        # Analyze impact to determine severity
        impact_score = 0
        if affected_artifacts:
            impact_score += len(affected_artifacts) * 2
        if affected_decisions:
            impact_score += len(affected_decisions) * 3
        
        if impact_score >= 10:
            severity = DecisionLockSeverity.CRITICAL
        elif impact_score >= 7:
            severity = DecisionLockSeverity.HIGH
        elif impact_score >= 4:
            severity = DecisionLockSeverity.MEDIUM
        elif impact_score >= 2:
            severity = DecisionLockSeverity.LOW
        else:
            severity = DecisionLockSeverity.INFO
        
        details = DecisionLockDetails(
            decision_id=decision_id,
            decision_question=decision_question,
            decision_answer=decision_answer,
            decision_category=decision_category,
            is_locked=False,
            affected_artifacts=affected_artifacts or [],
            affected_decisions=affected_decisions or [],
        )
        
        # Build description
        severity_emoji = {
            DecisionLockSeverity.INFO: "ℹ️",
            DecisionLockSeverity.LOW: "🟢",
            DecisionLockSeverity.MEDIUM: "🟡",
            DecisionLockSeverity.HIGH: "🟠",
            DecisionLockSeverity.CRITICAL: "🔴",
        }
        
        impact_summary = impact_analysis.get("summary", "No significant impact") if impact_analysis else "No significant impact"
        downstream_impact = impact_analysis.get("downstream_impact", "Minimal") if impact_analysis else "Minimal"
        
        description = f"""# Decision Lock Request {severity_emoji.get(severity, '⚪')}

A request has been made to lock this decision for permanent implementation.

## Decision Details
**ID:** {decision_id}
**Category:** {decision_category}
**Question:** {decision_question}
**Answer:** {decision_answer}

## Impact Assessment
**Severity:** {severity.value.upper()}
**Impact Summary:** {impact_summary}
**Downstream Impact:** {downstream_impact}
"""
        
        if affected_artifacts:
            description += f"\n**Affected Artifacts:** {', '.join(affected_artifacts)}"
        
        if affected_decisions:
            description += f"\n**Affected Decisions:** {', '.join(affected_decisions)}"
        
        description += """

## What Locking Means

When a decision is **locked**:
- The decision cannot be modified without explicit approval
- All dependent artifacts will be marked as based on this locked decision
- The decision becomes part of the project's permanent specification
- Changes require going through the unlock request process

## Options

1. **Lock Decision** - Approve and permanently lock this decision
2. **Request Changes** - Request modifications before locking
3. **Defer** - Put this lock request on hold

"""
        
        return cls(
            interrupt_type=InterruptType.DECISION_LOCKING,
            title=f"Lock Request: {decision_question[:50]}...",
            description=description,
            priority=InterruptPriority.HIGH if severity in [DecisionLockSeverity.HIGH, DecisionLockSeverity.CRITICAL] else InterruptPriority.MEDIUM,
            options=[
                "Lock Decision",
                "Request Changes",
                "Defer",
            ],
            timeout_seconds=timeout_seconds,
            decision_details=details,
            lock_action=DecisionLockAction.LOCK,
            severity=severity,
            impact_analysis=impact_analysis or {},
            lock_history=[],
            requires_approval=True,
        )
    
    @classmethod
    def create_unlock_request(
        cls,
        decision_id: str,
        decision_question: str,
        decision_answer: str,
        decision_category: str,
        locked_by: str,
        locked_at: datetime,
        reason: str,
        affected_artifacts: Optional[List[str]] = None,
        affected_decisions: Optional[List[str]] = None,
        timeout_seconds: int = 600,
        impact_analysis: Optional[Dict[str, Any]] = None,
    ) -> "DecisionLockInterruptConfig":
        """
        Factory method to create an unlock request interrupt.
        
        Args:
            decision_id: ID of the decision to unlock
            decision_question: Question text for the decision
            decision_answer: Answer text for the decision
            decision_category: Category of the decision
            locked_by: User who locked the decision
            locked_at: When the decision was locked
            reason: Reason for unlocking
            affected_artifacts: List of artifact IDs affected by this unlock
            affected_decisions: List of decision IDs affected by this unlock
            timeout_seconds: Timeout in seconds
            impact_analysis: Dictionary with impact analysis results
        
        Returns:
            DecisionLockInterruptConfig instance
        """
        details = DecisionLockDetails(
            decision_id=decision_id,
            decision_question=decision_question,
            decision_answer=decision_answer,
            decision_category=decision_category,
            is_locked=True,
            affected_artifacts=affected_artifacts or [],
            affected_decisions=affected_decisions or [],
            locked_by=locked_by,
            locked_at=locked_at,
        )
        
        # Analyze impact - unlocking is typically higher impact
        impact_score = 5  # Base score for unlocking
        if affected_artifacts:
            impact_score += len(affected_artifacts) * 2
        if affected_decisions:
            impact_score += len(affected_decisions) * 3
        
        if impact_score >= 15:
            severity = DecisionLockSeverity.CRITICAL
        elif impact_score >= 10:
            severity = DecisionLockSeverity.HIGH
        elif impact_score >= 6:
            severity = DecisionLockSeverity.MEDIUM
        else:
            severity = DecisionLockSeverity.LOW
        
        description = f"""# Decision Unlock Request 🔓

A request has been made to unlock this previously locked decision.

## Decision Details
**ID:** {decision_id}
**Category:** {decision_category}
**Question:** {decision_question}
**Answer:** {decision_answer}

## Current Lock Status
**Locked By:** {locked_by}
**Locked At:** {locked_at.strftime('%Y-%m-%d %H:%M UTC')}

## Unlock Reason
{reason}

## Impact Assessment
**Severity:** {severity.value.upper()}
"""
        
        if affected_artifacts:
            description += f"\n**Affected Artifacts:** {', '.join(affected_artifacts)}"
        
        if affected_decisions:
            description += f"\n**Affected Decisions:** {', '.join(affected_decisions)}"
        
        description += """

## What Unlocking Means

When a decision is **unlocked**:
- The decision becomes editable again
- All dependent artifacts may need re-validation
- The change will be recorded in the audit log
- Downstream decisions may be affected

## Options

1. **Approve Unlock** - Allow modifications to this decision
2. **Deny Unlock** - Keep the decision locked
3. **Temporary Unlock** - Allow edits for a limited time

"""
        
        return cls(
            interrupt_type=InterruptType.DECISION_LOCKING,
            title=f"Unlock Request: {decision_question[:50]}...",
            description=description,
            priority=InterruptPriority.HIGH,
            options=[
                "Approve Unlock",
                "Deny Unlock",
                "Temporary Unlock",
            ],
            timeout_seconds=timeout_seconds,
            decision_details=details,
            lock_action=DecisionLockAction.UNLOCK,
            severity=severity,
            impact_analysis=impact_analysis or {},
            lock_history=[],
            requires_approval=True,
        )
    
    def get_decision_id(self) -> str:
        """Get the ID of the decision being locked/unlocked."""
        return self.decision_details.decision_id
    
    def get_affected_artifact_ids(self) -> List[str]:
        """Get the IDs of all artifacts affected by this lock/unlock."""
        return self.decision_details.affected_artifacts
    
    def get_affected_decision_ids(self) -> List[str]:
        """Get the IDs of all decisions affected by this lock/unlock."""
        return self.decision_details.affected_decisions
    
    def to_interrupt_value(self) -> Dict[str, Any]:
        """Convert to a value suitable for LangGraph Interrupt."""
        return {
            "interrupt_id": self.interrupt_id,
            "interrupt_type": self.interrupt_type.value,
            "title": self.title,
            "description": self.description,
            "options": self.options,
            "priority": self.priority.value,
            "lock_action": self.lock_action.value,
            "severity": self.severity.value,
            "decision": {
                "id": self.decision_details.decision_id,
                "question": self.decision_details.decision_question,
                "answer": self.decision_details.decision_answer,
                "category": self.decision_details.decision_category,
                "is_locked": self.decision_details.is_locked,
            },
            "affected_artifacts": self.decision_details.affected_artifacts,
            "affected_decisions": self.decision_details.affected_decisions,
            "impact_analysis": self.impact_analysis,
            "requires_approval": self.requires_approval,
        }


class DecisionLockResponse(InterruptResponse):
    """
    Response specifically for decision lock interrupts.
    
    Extends InterruptResponse with fields for tracking the lock action
    and any conditions or time limits applied.
    """
    
    # Decision lock-specific response fields
    lock_action: DecisionLockAction
    
    # If temporary unlock was chosen
    temporary_duration_minutes: Optional[int] = None
    
    # If changes were requested
    requested_changes: Optional[str] = None
    
    # Approval tracking
    approved_by: Optional[str] = None
    approval_comment: Optional[str] = None
    
    def get_effective_action(self) -> str:
        """Get the effective action string for logging/display."""
        if self.lock_action == DecisionLockAction.LOCK:
            return "LOCK"
        elif self.lock_action == DecisionLockAction.UNLOCK:
            return "UNLOCK"
        elif self.lock_action == DecisionLockAction.TEMPORARY_UNLOCK:
            return f"TEMPORARY_UNLOCK ({self.temporary_duration_minutes}min)"
        return "UNKNOWN"


# ==================== Artifact Approval Interrupt Configuration ====================

class ArtifactApprovalAction(str, Enum):
    """Actions for artifact approval."""
    APPROVE = "approve"
    REQUEST_REVISIONS = "request_revisions"
    REGENERATE = "regenerate"
    REJECT = "reject"
    DEFER = "defer"


class ArtifactApprovalSeverity(str, Enum):
    """Severity levels for artifact approval."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ArtifactApprovalDetails(BaseModel):
    """Details about an artifact awaiting approval."""
    artifact_id: str
    artifact_type: str
    artifact_title: str
    artifact_version: int = 1
    project_id: str
    generation_method: str
    format_type: Optional[str] = None
    preview_content: str
    content_length: int
    affected_decisions: List[str] = Field(default_factory=list)
    related_artifacts: List[str] = Field(default_factory=list)
    generated_by: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    dependencies: List[str] = Field(default_factory=list)


class ArtifactApprovalInterruptConfig(HumanInterruptConfig):
    """
    Configuration specifically for artifact approval interrupts.
    
    This class extends HumanInterruptConfig with fields specific to
    artifact approval, including preview content and revision tracking.
    """
    
    # Artifact approval-specific fields
    artifact_details: ArtifactApprovalDetails
    approval_action: ArtifactApprovalAction
    severity: ArtifactApprovalSeverity
    
    # Quality assessment
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Revision history
    revision_count: int = 0
    previous_versions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Approval requirements
    requires_signature: bool = False
    signature_requirement: Optional[str] = None
    
    @classmethod
    def create_approval_request(
        cls,
        artifact_id: str,
        artifact_type: str,
        artifact_title: str,
        project_id: str,
        generation_method: str,
        preview_content: str,
        content_length: int,
        affected_decisions: Optional[List[str]] = None,
        related_artifacts: Optional[List[str]] = None,
        generated_by: Optional[str] = None,
        format_type: Optional[str] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        validation_results: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 900,
    ) -> "ArtifactApprovalInterruptConfig":
        """
        Factory method to create an artifact approval interrupt.
        
        Args:
            artifact_id: ID of the artifact to approve
            artifact_type: Type of artifact (specification, design document, etc.)
            artifact_title: Title of the artifact
            project_id: ID of the project
            generation_method: Method used to generate the artifact
            preview_content: Preview content for the artifact
            content_length: Length of the artifact content
            affected_decisions: List of decision IDs this artifact depends on
            related_artifacts: List of related artifact IDs
            generated_by: Agent or user who generated the artifact
            format_type: Output format type (markdown, json, etc.)
            quality_metrics: Quality assessment metrics
            validation_results: Validation check results
            timeout_seconds: Timeout in seconds
        
        Returns:
            ArtifactApprovalInterruptConfig instance
        """
        # Analyze quality to determine severity
        quality_score = 0
        if quality_metrics:
            completeness = quality_metrics.get("completeness", 0.5)
            consistency = quality_metrics.get("consistency", 0.5)
            clarity = quality_metrics.get("clarity", 0.5)
            quality_score = (completeness + consistency + clarity) / 3
        
        # Determine severity based on quality and validation
        has_validation_errors = validation_results and validation_results.get("errors")
        if has_validation_errors:
            severity = ArtifactApprovalSeverity.CRITICAL
        elif quality_score >= 0.9:
            severity = ArtifactApprovalSeverity.INFO
        elif quality_score >= 0.7:
            severity = ArtifactApprovalSeverity.LOW
        elif quality_score >= 0.5:
            severity = ArtifactApprovalSeverity.MEDIUM
        else:
            severity = ArtifactApprovalSeverity.HIGH
        
        details = ArtifactApprovalDetails(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            artifact_title=artifact_title,
            project_id=project_id,
            generation_method=generation_method,
            format_type=format_type,
            preview_content=preview_content[:2000] if len(preview_content) > 2000 else preview_content,
            content_length=content_length,
            affected_decisions=affected_decisions or [],
            related_artifacts=related_artifacts or [],
            generated_by=generated_by,
            dependencies=[],
        )
        
        # Build description
        severity_emoji = {
            ArtifactApprovalSeverity.INFO: "ℹ️",
            ArtifactApprovalSeverity.LOW: "🟢",
            ArtifactApprovalSeverity.MEDIUM: "🟡",
            ArtifactApprovalSeverity.HIGH: "🟠",
            ArtifactApprovalSeverity.CRITICAL: "🔴",
        }
        
        validation_status = "✅ Passed" if validation_results and not validation_results.get("errors") else "❌ Failed" if validation_results and validation_results.get("errors") else "⚪ Not validated"
        
        description = f"""# Artifact Ready for Approval {severity_emoji.get(severity, '⚪')}

The following {artifact_type} artifact is ready for your review and approval.

## Artifact Details
**ID:** {artifact_id}
**Title:** {artifact_title}
**Type:** {artifact_type}
**Format:** {format_type or 'N/A'}
**Version:** {details.artifact_version}
**Generated By:** {generated_by or 'System'}
**Generation Method:** {generation_method}

## Quality Assessment
**Quality Score:** {quality_score:.1%}"""
        
        if quality_metrics:
            description += f"""
- **Completeness:** {quality_metrics.get('completeness', 0):.1%}
- **Consistency:** {quality_metrics.get('consistency', 0):.1%}
- **Clarity:** {quality_metrics.get('clarity', 0):.1%}"""
        
        description += f"""

## Validation Status
**Status:** {validation_status}
"""
        
        if validation_results and validation_results.get("warnings"):
            description += f"**Warnings:** {', '.join(validation_results['warnings'])}\n"
        
        if affected_decisions:
            description += f"\n**Affected Decisions:** {', '.join(affected_decisions)}"
        
        if related_artifacts:
            description += f"\n**Related Artifacts:** {', '.join(related_artifacts)}"
        
        description += f"""

## Preview
```
{preview_content[:1000]}{'...' if len(preview_content) > 1000 else ''}
```

## Actions

Please select how you would like to proceed:

1. **Approve** - Accept this artifact as final
2. **Request Revisions** - Specify changes needed before approval
3. **Regenerate** - Generate a new version with AI assistance
4. **Reject** - Reject this artifact (with reason)
5. **Defer** - Put approval on hold

"""
        
        return cls(
            interrupt_type=InterruptType.ARTIFACT_APPROVAL,
            title=f"Artifact Ready: {artifact_title}",
            description=description,
            priority=InterruptPriority.HIGH if severity in [ArtifactApprovalSeverity.HIGH, ArtifactApprovalSeverity.CRITICAL] else InterruptPriority.MEDIUM,
            options=[
                "Approve as is",
                "Request Revisions",
                "Regenerate",
                "Reject",
                "Defer",
            ],
            timeout_seconds=timeout_seconds,
            artifact_details=details,
            approval_action=ArtifactApprovalAction.APPROVE,
            severity=severity,
            quality_metrics=quality_metrics or {},
            validation_results=validation_results or {},
            requires_signature=False,
        )
    
    def get_artifact_id(self) -> str:
        """Get the ID of the artifact."""
        return self.artifact_details.artifact_id
    
    def get_artifact_type(self) -> str:
        """Get the type of the artifact."""
        return self.artifact_details.artifact_type
    
    def get_project_id(self) -> str:
        """Get the project ID."""
        return self.artifact_details.project_id
    
    def get_affected_decision_ids(self) -> List[str]:
        """Get the IDs of decisions affected by this artifact."""
        return self.artifact_details.affected_decisions
    
    def get_related_artifact_ids(self) -> List[str]:
        """Get the IDs of related artifacts."""
        return self.artifact_details.related_artifacts
    
    def has_validation_errors(self) -> bool:
        """Check if the artifact has validation errors."""
        return bool(self.validation_results and self.validation_results.get("errors"))
    
    def to_interrupt_value(self) -> Dict[str, Any]:
        """Convert to a value suitable for LangGraph Interrupt."""
        return {
            "interrupt_id": self.interrupt_id,
            "interrupt_type": self.interrupt_type.value,
            "title": self.title,
            "description": self.description,
            "options": self.options,
            "priority": self.priority.value,
            "severity": self.severity.value,
            "artifact": {
                "id": self.artifact_details.artifact_id,
                "type": self.artifact_details.artifact_type,
                "title": self.artifact_details.artifact_title,
                "version": self.artifact_details.artifact_version,
                "project_id": self.artifact_details.project_id,
                "format": self.artifact_details.format_type,
                "content_length": self.artifact_details.content_length,
            },
            "quality_metrics": self.quality_metrics,
            "validation_results": self.validation_results,
            "affected_decisions": self.artifact_details.affected_decisions,
            "related_artifacts": self.artifact_details.related_artifacts,
            "requires_signature": self.requires_signature,
        }


class ArtifactApprovalResponse(InterruptResponse):
    """
    Response specifically for artifact approval interrupts.
    
    Extends InterruptResponse with fields for tracking the approval action
    and any revisions or feedback provided.
    """
    
    # Artifact approval-specific response fields
    approval_action: ArtifactApprovalAction
    
    # If revisions were requested
    revision_feedback: Optional[str] = None
    revision_sections: List[str] = Field(default_factory=list)
    
    # If regeneration was requested
    regeneration_prompt: Optional[str] = None
    
    # If rejection was chosen
    rejection_reason: Optional[str] = None
    
    # Approval tracking
    approved_by: Optional[str] = None
    approval_comment: Optional[str] = None
    signature: Optional[str] = None
    
    # New version tracking
    new_artifact_version: Optional[int] = None
    
    def get_action_summary(self) -> str:
        """Get a summary of the approval action taken."""
        if self.approval_action == ArtifactApprovalAction.APPROVE:
            return f"APPROVED by {self.approved_by or 'Unknown'}"
        elif self.approval_action == ArtifactApprovalAction.REQUEST_REVISIONS:
            return f"REVISIONS REQUESTED: {self.revision_feedback[:100] if self.revision_feedback else 'No feedback provided'}..."
        elif self.approval_action == ArtifactApprovalAction.REGENERATE:
            return f"REGENERATION REQUESTED"
        elif self.approval_action == ArtifactApprovalAction.REJECT:
            return f"REJECTED: {self.rejection_reason or 'No reason provided'}"
        elif self.approval_action == ArtifactApprovalAction.DEFER:
            return "DEFERRED"
        return "UNKNOWN ACTION"
    
    def requires_follow_up(self) -> bool:
        """Check if this response requires follow-up action."""
        return self.approval_action in [
            ArtifactApprovalAction.REQUEST_REVISIONS,
            ArtifactApprovalAction.REGENERATE,
            ArtifactApprovalAction.DEFER,
        ]


# ==================== Interrupt Response Handler ====================

class InterruptResponseHandler:
    """
    Handles response callbacks for human-in-the-loop interrupts.
    
    Provides:
    1. Typed callback registration by interrupt type
    2. Async and sync callback support
    3. Response validation and transformation
    4. Error handling and fallback mechanisms
    """
    
    # Callback type aliases
    CallbackType = Union[
        Callable[[InterruptResponse], None],
        Callable[[InterruptResponse], Awaitable[None]],
    ]
    
    def __init__(self):
        """Initialize the response handler."""
        self._callbacks: Dict[str, List[self.CallbackType]] = {}
        self._type_callbacks: Dict[InterruptType, List[self.CallbackType]] = {}
        self._fallbacks: Dict[str, self.CallbackType] = {}
        self._error_handlers: List[Callable[[Exception, str], None]] = []
    
    def register_callback(
        self,
        interrupt_id: str,
        callback: CallbackType,
    ) -> None:
        """Register a callback for a specific interrupt."""
        if interrupt_id not in self._callbacks:
            self._callbacks[interrupt_id] = []
        self._callbacks[interrupt_id].append(callback)
    
    def register_type_callback(
        self,
        interrupt_type: InterruptType,
        callback: CallbackType,
    ) -> None:
        """Register a callback for all interrupts of a specific type."""
        if interrupt_type not in self._type_callbacks:
            self._type_callbacks[interrupt_type] = []
        self._type_callbacks[interrupt_type].append(callback)
    
    def register_fallback(
        self,
        interrupt_id: str,
        fallback: CallbackType,
    ) -> None:
        """Register a fallback callback for when the primary callback fails."""
        self._fallbacks[interrupt_id] = fallback
    
    def register_error_handler(
        self,
        handler: Callable[[Exception, str], None],
    ) -> None:
        """Register an error handler for callback exceptions."""
        self._error_handlers.append(handler)
    
    def unregister_callback(
        self,
        interrupt_id: str,
        callback: CallbackType,
    ) -> None:
        """Unregister a specific callback."""
        if interrupt_id in self._callbacks:
            self._callbacks[interrupt_id] = [
                cb for cb in self._callbacks[interrupt_id]
                if cb != callback
            ]
    
    def unregister_type_callback(
        self,
        interrupt_type: InterruptType,
        callback: CallbackType,
    ) -> None:
        """Unregister a specific type callback."""
        if interrupt_type in self._type_callbacks:
            self._type_callbacks[interrupt_type] = [
                cb for cb in self._type_callbacks[interrupt_type]
                if cb != callback
            ]
    
    async def handle_response_async(
        self,
        response: InterruptResponse,
        interrupt_config: HumanInterruptConfig,
    ) -> None:
        """
        Handle an interrupt response asynchronously.
        
        Args:
            response: The interrupt response
            interrupt_config: The interrupt configuration
        """
        callbacks = self._callbacks.get(response.interrupt_id, []).copy()
        
        # Also get type-level callbacks
        type_callbacks = self._type_callbacks.get(
            interrupt_config.interrupt_type, []
        ).copy()
        
        all_callbacks = callbacks + type_callbacks
        
        for callback in all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(response)
                else:
                    callback(response)
            except Exception as e:
                await self._handle_callback_error(e, response.interrupt_id)
                # Try fallback if available
                fallback = self._fallbacks.get(response.interrupt_id)
                if fallback:
                    try:
                        if asyncio.iscoroutinefunction(fallback):
                            await fallback(response)
                        else:
                            fallback(response)
                    except Exception as fallback_error:
                        await self._handle_callback_error(
                            fallback_error,
                            response.interrupt_id,
                        )
    
    def handle_response_sync(
        self,
        response: InterruptResponse,
        interrupt_config: HumanInterruptConfig,
    ) -> None:
        """
        Handle an interrupt response synchronously.
        
        Args:
            response: The interrupt response
            interrupt_config: The interrupt configuration
        """
        callbacks = self._callbacks.get(response.interrupt_id, []).copy()
        
        # Also get type-level callbacks
        type_callbacks = self._type_callbacks.get(
            interrupt_config.interrupt_type, []
        ).copy()
        
        all_callbacks = callbacks + type_callbacks
        
        for callback in all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Run async callback in sync context
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create task if loop is already running
                        loop.create_task(callback(response))
                    else:
                        loop.run_until_complete(callback(response))
                else:
                    callback(response)
            except Exception as e:
                self._handle_callback_error_sync(e, response.interrupt_id)
                # Try fallback if available
                fallback = self._fallbacks.get(response.interrupt_id)
                if fallback:
                    try:
                        fallback(response)
                    except Exception as fallback_error:
                        self._handle_callback_error_sync(
                            fallback_error,
                            response.interrupt_id,
                        )
    
    async def _handle_callback_error(
        self,
        error: Exception,
        interrupt_id: str,
    ) -> None:
        """Handle a callback error asynchronously."""
        for handler in self._error_handlers:
            handler(error, interrupt_id)
    
    def _handle_callback_error_sync(
        self,
        error: Exception,
        interrupt_id: str,
    ) -> None:
        """Handle a callback error synchronously."""
        for handler in self._error_handlers:
            handler(error, interrupt_id)
    
    def get_callbacks(self, interrupt_id: str) -> List[CallbackType]:
        """Get all callbacks registered for an interrupt."""
        return self._callbacks.get(interrupt_id, []).copy()
    
    def get_type_callbacks(self, interrupt_type: InterruptType) -> List[CallbackType]:
        """Get all callbacks registered for an interrupt type."""
        return self._type_callbacks.get(interrupt_type, []).copy()
    
    def clear_callbacks(self, interrupt_id: str) -> None:
        """Clear all callbacks for an interrupt."""
        self._callbacks.pop(interrupt_id, None)
        self._fallbacks.pop(interrupt_id, None)
    
    def clear_type_callbacks(self, interrupt_type: InterruptType) -> None:
        """Clear all callbacks for an interrupt type."""
        self._type_callbacks.pop(interrupt_type, None)


# Import asyncio for async support
import asyncio
from typing import Awaitable


# ==================== Interrupt Persistence ====================

class InterruptPersistence:
    """
    Handles persistence and resumption of interrupts for distributed systems.
    
    Provides:
    1. Save/load interrupts to Redis
    2. Session management for interrupt resumption
    3. State snapshot and restore
    4. Distributed lock for concurrent access
    """
    
    def __init__(self, redis_url: str):
        """
        Initialize the persistence layer.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._redis_client = None
    
    async def _get_redis_client(self):
        """Get or create Redis client."""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "redis package required for interrupt persistence. "
                    "Install with: pip install redis"
                )
        return self._redis_client
    
    async def save_interrupt(
        self,
        interrupt_id: str,
        config: HumanInterruptConfig,
        thread_id: str,
    ) -> bool:
        """
        Save an interrupt configuration to persistence.
        
        Args:
            interrupt_id: Unique interrupt identifier
            config: Interrupt configuration to save
            thread_id: LangGraph thread ID
        
        Returns:
            True if saved successfully
        """
        try:
            client = await self._get_redis_client()
            key = f"interrupt:{thread_id}:{interrupt_id}"
            data = config.model_dump_json()
            await client.set(key, data, ex=86400)  # 24 hour expiry
            
            # Also add to thread's interrupt list
            thread_key = f"thread:{thread_id}:interrupts"
            await client.sadd(thread_key, interrupt_id)
            await client.expire(thread_key, 86400)
            
            return True
        except Exception:
            return False
    
    async def load_interrupt(
        self,
        interrupt_id: str,
        thread_id: str,
    ) -> Optional[HumanInterruptConfig]:
        """
        Load an interrupt configuration from persistence.
        
        Args:
            interrupt_id: Unique interrupt identifier
            thread_id: LangGraph thread ID
        
        Returns:
            Interrupt configuration or None if not found
        """
        try:
            client = await self._get_redis_client()
            key = f"interrupt:{thread_id}:{interrupt_id}"
            data = await client.get(key)
            
            if data:
                return HumanInterruptConfig.model_validate_json(data)
            return None
        except Exception:
            return None
    
    async def save_response(
        self,
        response_id: str,
        response: InterruptResponse,
        thread_id: str,
    ) -> bool:
        """
        Save a response to persistence.
        
        Args:
            response_id: Unique response identifier
            response: Response to save
            thread_id: LangGraph thread ID
        
        Returns:
            True if saved successfully
        """
        try:
            client = await self._get_redis_client()
            key = f"response:{thread_id}:{response_id}"
            data = response.model_dump_json()
            await client.set(key, data, ex=86400)
            return True
        except Exception:
            return False
    
    async def load_response(
        self,
        response_id: str,
        thread_id: str,
    ) -> Optional[InterruptResponse]:
        """
        Load a response from persistence.
        
        Args:
            response_id: Unique response identifier
            thread_id: LangGraph thread ID
        
        Returns:
            Response or None if not found
        """
        try:
            client = await self._get_redis_client()
            key = f"response:{thread_id}:{response_id}"
            data = await client.get(key)
            
            if data:
                return InterruptResponse.model_validate_json(data)
            return None
        except Exception:
            return None
    
    async def get_thread_interrupts(
        self,
        thread_id: str,
    ) -> List[str]:
        """
        Get all interrupt IDs for a thread.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            List of interrupt IDs
        """
        try:
            client = await self._get_redis_client()
            thread_key = f"thread:{thread_id}:interrupts"
            interrupt_ids = await client.smembers(thread_key)
            return [i.decode() if isinstance(i, bytes) else i for i in interrupt_ids]
        except Exception:
            return []
    
    async def delete_interrupt(
        self,
        interrupt_id: str,
        thread_id: str,
    ) -> bool:
        """
        Delete an interrupt from persistence.
        
        Args:
            interrupt_id: Unique interrupt identifier
            thread_id: LangGraph thread ID
        
        Returns:
            True if deleted successfully
        """
        try:
            client = await self._get_redis_client()
            interrupt_key = f"interrupt:{thread_id}:{interrupt_id}"
            thread_key = f"thread:{thread_id}:interrupts"
            
            await client.delete(interrupt_key)
            await client.srem(thread_key, interrupt_id)
            return True
        except Exception:
            return False
    
    async def save_session_state(
        self,
        thread_id: str,
        state: Dict[str, Any],
    ) -> bool:
        """
        Save session state for interrupt resumption.
        
        Args:
            thread_id: LangGraph thread ID
            state: State dictionary to save
        
        Returns:
            True if saved successfully
        """
        try:
            client = await self._get_redis_client()
            key = f"session:{thread_id}:state"
            import json
            data = json.dumps(state)
            await client.set(key, data, ex=86400)
            return True
        except Exception:
            return False
    
    async def load_session_state(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load session state for interrupt resumption.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            State dictionary or None if not found
        """
        try:
            client = await self._get_redis_client()
            key = f"session:{thread_id}:state"
            data = await client.get(key)
            
            if data:
                import json
                return json.loads(data)
            return None
        except Exception:
            return None
    
    async def acquire_lock(
        self,
        lock_name: str,
        owner_id: str,
        ttl_seconds: int = 300,
    ) -> bool:
        """
        Acquire a distributed lock.
        
        Args:
            lock_name: Name of the lock
            owner_id: Owner identifier
            ttl_seconds: Lock TTL in seconds
        
        Returns:
            True if lock acquired
        """
        try:
            client = await self._get_redis_client()
            key = f"lock:{lock_name}"
            result = await client.set(key, owner_id, nx=True, ex=ttl_seconds)
            return result is True
        except Exception:
            return False
    
    async def release_lock(
        self,
        lock_name: str,
        owner_id: str,
    ) -> bool:
        """
        Release a distributed lock.
        
        Args:
            lock_name: Name of the lock
            owner_id: Owner identifier (must match to release)
        
        Returns:
            True if lock released
        """
        try:
            client = await self._get_redis_client()
            key = f"lock:{lock_name}"
            # Use Lua script for atomic check-and-delete
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await client.eval(script, 1, key, owner_id)
            return result == 1
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None


class PersistentInterruptManager(InterruptManager):
    """
    Extended InterruptManager with persistence support.
    
    Provides all InterruptManager functionality plus:
    1. Automatic persistence of interrupts
    2. Session state management
    3. Distributed locking
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the persistent interrupt manager.
        
        Args:
            redis_url: Optional Redis URL for persistence
        """
        super().__init__(redis_url=redis_url)
        self.redis_url = redis_url
        self._persistence: Optional[InterruptPersistence] = None
    
    @property
    def persistence(self) -> Optional[InterruptPersistence]:
        """Get the persistence layer."""
        return self._persistence
    
    async def _ensure_persistence(self) -> Optional[InterruptPersistence]:
        """Ensure persistence layer is initialized."""
        if self._persistence is None and self.redis_url:
            self._persistence = InterruptPersistence(self.redis_url)
        return self._persistence
    
    async def create_interrupt(
        self,
        interrupt_type: InterruptType,
        title: str,
        description: str,
        options: Optional[List[str]] = None,
        priority: InterruptPriority = InterruptPriority.MEDIUM,
        allow_ignore: bool = True,
        allow_response: bool = True,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
    ) -> HumanInterruptConfig:
        """
        Create a new human interrupt configuration with persistence.
        
        Args:
            interrupt_type: Type of interrupt
            title: Title of the interrupt
            description: Detailed description
            options: Optional list of response options
            priority: Interrupt priority level
            allow_ignore: Whether ignore is allowed
            allow_response: Whether custom response is allowed
            timeout_seconds: Optional timeout in seconds
            metadata: Additional metadata
            thread_id: LangGraph thread ID for persistence
        
        Returns:
            HumanInterruptConfig instance
        """
        config = super().create_interrupt(
            interrupt_type=interrupt_type,
            title=title,
            description=description,
            options=options,
            priority=priority,
            allow_ignore=allow_ignore,
            allow_response=allow_response,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )
        
        # Persist the interrupt
        persistence = await self._ensure_persistence()
        if persistence and thread_id:
            await persistence.save_interrupt(
                config.interrupt_id,
                config,
                thread_id,
            )
        
        return config
    
    async def record_response(
        self,
        response: InterruptResponse,
        thread_id: Optional[str] = None,
    ) -> None:
        """
        Record a human response to an interrupt with persistence.
        
        Args:
            response: Response to record
            thread_id: LangGraph thread ID for persistence
        """
        super().record_response(response)
        
        # Persist the response
        persistence = await self._ensure_persistence()
        if persistence and thread_id:
            await persistence.save_response(
                response.response_id,
                response,
                thread_id,
            )
    
    async def resume_interrupts(
        self,
        thread_id: str,
    ) -> List[HumanInterruptConfig]:
        """
        Resume all pending interrupts for a thread.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            List of resumed interrupt configurations
        """
        persistence = await self._ensure_persistence()
        if not persistence:
            return []
        
        interrupt_ids = await persistence.get_thread_interrupts(thread_id)
        resumed = []
        
        for interrupt_id in interrupt_ids:
            config = await persistence.load_interrupt(interrupt_id, thread_id)
            if config:
                # Check if not already responded to
                if interrupt_id not in self.responses:
                    self.interrupts[interrupt_id] = config
                    resumed.append(config)
        
        return resumed
    
    async def save_session_state(
        self,
        thread_id: str,
        state: Dict[str, Any],
    ) -> bool:
        """
        Save session state for interrupt resumption.
        
        Args:
            thread_id: LangGraph thread ID
            state: State dictionary to save
        
        Returns:
            True if saved successfully
        """
        persistence = await self._ensure_persistence()
        if persistence:
            return await persistence.save_session_state(thread_id, state)
        return False
    
    async def load_session_state(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load session state for interrupt resumption.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            State dictionary or None if not found
        """
        persistence = await self._ensure_persistence()
        if persistence:
            return await persistence.load_session_state(thread_id)
        return None
    
    async def cleanup_thread(
        self,
        thread_id: str,
    ) -> int:
        """
        Clean up all data for a thread.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            Number of items deleted
        """
        persistence = await self._ensure_persistence()
        if not persistence:
            return 0
        
        interrupt_ids = await persistence.get_thread_interrupts(thread_id)
        count = 0
        
        for interrupt_id in interrupt_ids:
            if await persistence.delete_interrupt(interrupt_id, thread_id):
                count += 1
        
        return count
    
    async def close(self) -> None:
        """Close the persistence connection."""
        if self._persistence:
            await self._persistence.close()
            self._persistence = None


# ==================== Interrupt Manager ====================

class InterruptManager:
    """
    Manages human-in-the-loop interrupts for LangGraph agents.
    
    This class provides:
    1. Interrupt creation and configuration
    2. Interrupt state management
    3. Response handling
    4. Timeout and expiration handling
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the Interrupt Manager.
        
        Args:
            redis_url: Optional Redis URL for distributed interrupt storage
        """
        self.interrupts: Dict[str, HumanInterruptConfig] = {}
        self.responses: Dict[str, InterruptResponse] = {}
        self.redis_url = redis_url
        self._callbacks: Dict[str, Callable] = {}
    
    def create_interrupt(
        self,
        interrupt_type: InterruptType,
        title: str,
        description: str,
        options: Optional[List[str]] = None,
        priority: InterruptPriority = InterruptPriority.MEDIUM,
        allow_ignore: bool = True,
        allow_response: bool = True,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HumanInterruptConfig:
        """
        Create a new human interrupt configuration.
        
        Args:
            interrupt_type: Type of interrupt
            title: Title of the interrupt
            description: Detailed description
            options: Optional list of response options
            priority: Interrupt priority level
            allow_ignore: Whether ignore is allowed
            allow_response: Whether custom response is allowed
            timeout_seconds: Optional timeout in seconds
            metadata: Additional metadata
        
        Returns:
            HumanInterruptConfig instance
        """
        config = HumanInterruptConfig(
            interrupt_type=interrupt_type,
            title=title,
            description=description,
            options=options or [],
            priority=priority,
            allow_ignore=allow_ignore,
            allow_response=allow_response,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )
        
        self.interrupts[config.interrupt_id] = config
        
        # Set expiration if timeout is specified
        if timeout_seconds:
            config.expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        return config
    
    def get_interrupt(self, interrupt_id: str) -> Optional[HumanInterruptConfig]:
        """Get an interrupt configuration by ID."""
        return self.interrupts.get(interrupt_id)
    
    def record_response(self, response: InterruptResponse) -> None:
        """Record a human response to an interrupt."""
        self.responses[response.response_id] = response
        self.interrupts[response.interrupt_id].metadata["last_response"] = response.response_id
    
    def validate_response(
        self,
        interrupt_id: str,
        response_type: str,
    ) -> tuple[bool, str]:
        """
        Validate a response against the interrupt configuration.
        
        Args:
            interrupt_id: ID of the interrupt
            response_type: Type of response being attempted
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        config = self.get_interrupt(interrupt_id)
        if config is None:
            return False, f"Interrupt {interrupt_id} not found"
        
        if response_type == "ignore" and not config.allow_ignore:
            return False, "This interrupt cannot be ignored"
        
        if response_type == "custom" and not config.allow_response:
            return False, "Custom responses are not allowed for this interrupt"
        
        return True, ""
    
    def handle_response(
        self,
        interrupt_id: str,
        status: InterruptStatus,
        response: Optional[str] = None,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
        response_type: str = "selected_option",
    ) -> InterruptResponse:
        """
        Handle a human response to an interrupt.
        
        Args:
            interrupt_id: ID of the interrupt being responded to
            status: Response status (approved, rejected, ignored)
            response: Selected option or custom response
            comment: Optional comment from the human
            user_id: ID of the responding user
            response_type: Type of response ("selected_option", "custom", "ignore")
        
        Returns:
            InterruptResponse instance
        
        Raises:
            ValueError: If the response type is not allowed
        """
        # Validate response type against configuration
        is_valid, error_message = self.validate_response(interrupt_id, response_type)
        if not is_valid:
            raise ValueError(error_message)
        
        resp = CustomInterruptResponse(
            interrupt_id=interrupt_id,
            user_id=user_id,
            status=status,
            response=response,
            comment=comment,
            response_type=response_type,
        )
        
        self.record_response(resp)
        
        # Trigger callback if registered
        callback = self._callbacks.get(interrupt_id)
        if callback:
            callback(resp)
        
        return resp
    
    def approve(
        self,
        interrupt_id: str,
        response: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InterruptResponse:
        """Approve an interrupt."""
        return self.handle_response(
            interrupt_id,
            InterruptStatus.APPROVED,
            response=response,
            user_id=user_id,
            response_type="selected_option",
        )
    
    def reject(
        self,
        interrupt_id: str,
        response: Optional[str] = None,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InterruptResponse:
        """Reject an interrupt."""
        return self.handle_response(
            interrupt_id,
            InterruptStatus.REJECTED,
            response=response,
            comment=comment,
            user_id=user_id,
            response_type="selected_option",
        )
    
    def ignore(
        self,
        interrupt_id: str,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InterruptResponse:
        """Ignore an interrupt (continue without changes)."""
        return self.handle_response(
            interrupt_id,
            InterruptStatus.IGNORED,
            comment=comment,
            user_id=user_id,
            response_type="ignore",
        )
    
    def custom_response(
        self,
        interrupt_id: str,
        response: str,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InterruptResponse:
        """Submit a custom/free-form response to an interrupt."""
        return self.handle_response(
            interrupt_id,
            InterruptStatus.APPROVED,
            response=response,
            comment=comment,
            user_id=user_id,
            response_type="custom",
        )
    
    def register_callback(self, interrupt_id: str, callback: Callable[[InterruptResponse], None]) -> None:
        """Register a callback to be triggered when an interrupt is responded to."""
        self._callbacks[interrupt_id] = callback
    
    def check_timeouts(self) -> List[InterruptResponse]:
        """Check for timed out interrupts and mark them accordingly."""
        timed_out = []
        
        for interrupt_id, config in self.interrupts.items():
            if config.is_timed_out() and interrupt_id not in self.responses:
                resp = self.handle_response(
                    interrupt_id,
                    InterruptStatus.TIMEOUT,
                    comment=f"Interrupt timed out after {config.timeout_seconds} seconds",
                )
                timed_out.append(resp)
        
        return timed_out
    
    def get_pending_interrupts(self) -> List[HumanInterruptConfig]:
        """Get all pending (not responded to) interrupts."""
        return [
            config for config in self.interrupts.values()
            if config.interrupt_id not in self.responses
            and not config.is_expired()
        ]


# ==================== LangGraph Interrupt Helpers ====================

def create_interrupt(
    interrupt_type: InterruptType,
    value: Any,
    resume: Optional[str] = None,
) -> Interrupt:
    """
    Create a LangGraph Interrupt for human approval.
    
    Args:
        interrupt_type: Type of interrupt
        value: Value to present to the human
        resume: Optional resume instruction
    
    Returns:
        Interrupt instance
    """
    return Interrupt(
        value={
            "type": interrupt_type.value,
            "value": value,
            "resume": resume,
        }
    )


def create_command(
    command_type: str,
    arg: Any,
) -> Command:
    """
    Create a LangGraph Command for resuming after interrupt.
    
    Args:
        command_type: Type of command (resume, etc.)
        arg: Command argument
    
    Returns:
        Command instance
    """
    return Command(resume={command_type: arg})


def resume_with_value(value: Any) -> Command:
    """Create a resume command with a value."""
    return Command(resume={"value": value})


def resume_with_approval(value: Any) -> Command:
    """Create a resume command indicating approval."""
    return Command(resume={"approved": value})


def resume_with_rejection(reason: str) -> Command:
    """Create a resume command indicating rejection."""
    return Command(resume={"rejected": True, "reason": reason})


# ==================== Agent Integration Mixins ====================

class HumanInTheLoopMixin:
    """
    Mixin class to add human-in-the-loop capabilities to agents.
    
    Provides:
    1. Interrupt creation helper methods
    2. Response handling methods
    3. Timeout checking
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with interrupt manager."""
        self.interrupt_manager = InterruptManager()
        super().__init__(*args, **kwargs)
    
    def _create_interrupt(
        self,
        interrupt_type: InterruptType,
        title: str,
        description: str,
        options: Optional[List[str]] = None,
        priority: InterruptPriority = InterruptPriority.MEDIUM,
        allow_ignore: bool = True,
        allow_response: bool = True,
        timeout_seconds: Optional[int] = None,
    ) -> HumanInterruptConfig:
        """Create an interrupt for human approval."""
        return self.interrupt_manager.create_interrupt(
            interrupt_type=interrupt_type,
            title=title,
            description=description,
            options=options,
            priority=priority,
            allow_ignore=allow_ignore,
            allow_response=allow_response,
            timeout_seconds=timeout_seconds,
        )
    
    def _interrupt_for_approval(
        self,
        title: str,
        description: str,
        interrupt_type: InterruptType = InterruptType.CUSTOM,
        options: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = 300,
    ) -> Interrupt:
        """
        Create an interrupt for human approval and return the LangGraph Interrupt.
        
        Args:
            title: Interrupt title
            description: Detailed description
            interrupt_type: Type of interrupt
            options: Response options
            timeout_seconds: Timeout in seconds
        
        Returns:
            LangGraph Interrupt instance
        """
        config = self._create_interrupt(
            interrupt_type=interrupt_type,
            title=title,
            description=description,
            options=options,
            timeout_seconds=timeout_seconds,
        )
        
        return create_interrupt(
            interrupt_type=config.interrupt_type,
            value={
                "interrupt_id": config.interrupt_id,
                "title": config.title,
                "description": config.description,
                "options": config.options,
                "priority": config.priority.value,
            },
            resume="human_response",
        )
    
    def _interrupt_for_contradiction(
        self,
        decision_1: Dict[str, Any],
        decision_2: Dict[str, Any],
        similarity_score: float,
    ) -> Interrupt:
        """
        Create an interrupt for contradiction resolution.
        
        Args:
            decision_1: First conflicting decision
            decision_2: Second conflicting decision
            similarity_score: Similarity score between decisions
        
        Returns:
            LangGraph Interrupt instance
        """
        options = [
            "Keep both decisions (revise one)",
            "Keep first decision only",
            "Keep second decision only",
            "Merge decisions",
            "Defer for later",
        ]
        
        return self._interrupt_for_approval(
            title="Contradiction Detected",
            description=(
                f"Two decisions appear to contradict each other:\n\n"
                f"**Decision 1:** {decision_1.get('question_text', 'N/A')}\n"
                f"**Answer:** {decision_1.get('answer_text', 'N/A')}\n\n"
                f"**Decision 2:** {decision_2.get('question_text', 'N/A')}\n"
                f"**Answer:** {decision_2.get('answer_text', 'N/A')}\n\n"
                f"**Similarity Score:** {similarity_score:.2f}\n\n"
                f"Please select how to resolve this contradiction:"
            ),
            interrupt_type=InterruptType.CONTRADICTION_RESOLUTION,
            options=options,
            timeout_seconds=600,
        )
    
    def _interrupt_for_artifact_approval(
        self,
        artifact_type: str,
        artifact_title: str,
        preview: str,
    ) -> Interrupt:
        """
        Create an interrupt for artifact approval.
        
        Args:
            artifact_type: Type of artifact
            artifact_title: Title of the artifact
            preview: Preview of the artifact content
        
        Returns:
            LangGraph Interrupt instance
        """
        options = [
            "Approve as is",
            "Request revisions",
            "Regenerate",
            "Cancel",
        ]
        
        return self._interrupt_for_approval(
            title=f"Artifact Ready: {artifact_title}",
            description=(
                f"The following {artifact_type} artifact is ready for review:\n\n"
                f"---\n{preview[:1000]}...\n---\n\n"
                f"Please select an action:"
            ),
            interrupt_type=InterruptType.ARTIFACT_APPROVAL,
            options=options,
            timeout_seconds=900,
        )
    
    def _interrupt_for_decision_lock(
        self,
        decision: Dict[str, Any],
        impact: str,
    ) -> Interrupt:
        """
        Create an interrupt for decision locking confirmation.
        
        Args:
            decision: Decision to lock
            impact: Impact of locking this decision
        
        Returns:
            LangGraph Interrupt instance
        """
        options = [
            "Lock decision",
            "Unlock (make editable)",
            "Cancel",
        ]
        
        return self._interrupt_for_approval(
            title="Decision Lock Request",
            description=(
                f"**Decision:** {decision.get('question_text', 'N/A')}\n"
                f"**Answer:** {decision.get('answer_text', 'N/A')}\n\n"
                f"**Impact:** {impact}\n\n"
                f"Locking a decision means it cannot be modified without explicit approval. "
                f"Proceed with locking?"
            ),
            interrupt_type=InterruptType.DECISION_LOCKING,
            options=options,
            timeout_seconds=300,
        )
    
    def _interrupt_for_branch_merge(
        self,
        branch_name: str,
        changes_summary: str,
        conflict_count: int,
    ) -> Interrupt:
        """
        Create an interrupt for branch merge confirmation.
        
        Args:
            branch_name: Name of the branch to merge
            changes_summary: Summary of changes
            conflict_count: Number of conflicts
        
        Returns:
            LangGraph Interrupt instance
        """
        options = [
            "Merge branch",
            "Merge with conflicts",
            "Cancel",
        ]
        
        description = (
            f"**Branch:** {branch_name}\n"
            f"**Conflicts:** {conflict_count} conflict(s)\n\n"
            f"**Changes:**\n{changes_summary[:500]}\n\n"
        )
        
        if conflict_count > 0:
            description += "⚠️ This merge has conflicts that need resolution.\n\n"
        
        description += "Select an action:"
        
        return self._interrupt_for_approval(
            title="Branch Merge Request",
            description=description,
            interrupt_type=InterruptType.BRANCH_MERGE,
            options=options,
            timeout_seconds=600,
        )
    
    def _handle_interrupt_response(
        self,
        interrupt_id: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle a human response to an interrupt.
        
        Args:
            interrupt_id: ID of the interrupt
            state: Current agent state
        
        Returns:
            Updated state with interrupt response
        """
        response = self.interrupt_manager.get_interrupt(interrupt_id)
        
        if response is None:
            return state
        
        state["last_interrupt"] = {
            "interrupt_id": interrupt_id,
            "type": response.interrupt_type.value,
            "title": response.title,
            "responded": True,
        }
        
        return state


# ==================== Enhanced Timeout Handler for Human Responses ====================

class TimeoutPolicy(str, Enum):
    """
    Timeout policies for human interrupts.
    
    Policies determine what action to take when a human fails to respond
    within the specified timeout period.
    """
    AUTO_REJECT = "auto_reject"  # Automatically reject the pending action
    AUTO_APPROVE = "auto_approve"  # Automatically approve the pending action
    AUTO_IGNORE = "auto_ignore"  # Automatically ignore and continue execution
    ESCALATE = "escalate"  # Escalate to configured notification targets
    NOTIFY_ONLY = "notify_only"  # Send notification but keep interrupt pending
    AUTO_SUBMIT_DEFAULT = "auto_submit_default"  # Submit with default response


class TimeoutSeverity(str, Enum):
    """Severity levels for timeout handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeoutConfig(BaseModel):
    """Configuration for timeout handling."""
    timeout_seconds: int
    policy: TimeoutPolicy = TimeoutPolicy.AUTO_IGNORE
    severity: TimeoutSeverity = TimeoutSeverity.MEDIUM
    escalation_targets: List[str] = Field(default_factory=list)
    notification_channels: List[str] = Field(default_factory=list)
    max_escalations: int = 3
    default_response: Optional[str] = None
    allow_extension: bool = True
    extension_duration_seconds: Optional[int] = None
    max_extensions: int = 2


class TimeoutEvent(BaseModel):
    """Event record for a timeout occurrence."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    interrupt_id: str
    interrupt_type: InterruptType
    original_timeout: int
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    policy_applied: TimeoutPolicy
    response_generated: Optional[str] = None
    escalation_count: int = 0
    was_extended: bool = False
    extension_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HumanResponseTimeoutHandler:
    """
    Comprehensive timeout handler for human-in-the-loop interrupts.
    
    Provides:
    1. Configurable timeout policies per interrupt type
    2. Scheduled timeout checking
    3. Escalation procedures
    4. Extension handling
    5. Timeout event logging
    6. Integration with notification systems
    """
    
    def __init__(
        self,
        default_policy: TimeoutPolicy = TimeoutPolicy.AUTO_IGNORE,
        check_interval_seconds: int = 30,
        notification_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the timeout handler.
        
        Args:
            default_policy: Default policy when type-specific policy not set
            check_interval_seconds: Interval for checking timed-out interrupts
            notification_callback: Optional callback for timeout notifications
        """
        self.default_policy = default_policy
        self.check_interval_seconds = check_interval_seconds
        self.notification_callback = notification_callback
        
        # Timeout configurations per interrupt type
        self._timeout_configs: Dict[str, TimeoutConfig] = {}
        
        # Active timeouts being monitored
        self._active_timeouts: Dict[str, datetime] = {}
        
        # Escalation counts per interrupt
        self._escalation_counts: Dict[str, int] = {}
        
        # Extension counts per interrupt
        self._extension_counts: Dict[str, int] = {}
        
        # Timeout events history
        self._timeout_events: List[TimeoutEvent] = []
        
        # Escalation targets per interrupt type
        self._escalation_targets: Dict[str, List[str]] = {}
        
        # Notification channels per interrupt type
        self._notification_channels: Dict[str, List[str]] = {}
        
        # Running state
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
    
    def configure_timeout(
        self,
        interrupt_type: str,
        timeout_seconds: int,
        policy: TimeoutPolicy = None,
        severity: TimeoutSeverity = None,
        escalation_targets: List[str] = None,
        notification_channels: List[str] = None,
        max_escalations: int = 3,
        default_response: str = None,
        allow_extension: bool = True,
        extension_duration_seconds: int = None,
        max_extensions: int = 2,
    ) -> None:
        """
        Configure timeout for a specific interrupt type.
        
        Args:
            interrupt_type: Type of interrupt to configure
            timeout_seconds: Timeout in seconds
            policy: Timeout policy (uses default if not specified)
            severity: Severity level
            escalation_targets: List of escalation targets
            notification_channels: Notification channels to use
            max_escalations: Maximum escalation attempts
            default_response: Default response to submit
            allow_extension: Whether to allow timeout extension
            extension_duration_seconds: Extension duration in seconds
            max_extensions: Maximum number of extensions
        """
        self._timeout_configs[interrupt_type] = TimeoutConfig(
            timeout_seconds=timeout_seconds,
            policy=policy or self.default_policy,
            severity=severity or TimeoutSeverity.MEDIUM,
            escalation_targets=escalation_targets or [],
            notification_channels=notification_channels or [],
            max_escalations=max_escalations,
            default_response=default_response,
            allow_extension=allow_extension,
            extension_duration_seconds=extension_duration_seconds,
            max_extensions=max_extensions,
        )
    
    def set_escalation_targets(
        self,
        interrupt_type: str,
        targets: List[str],
    ) -> None:
        """Set escalation targets for an interrupt type."""
        self._escalation_targets[interrupt_type] = targets
        
        # Update config if exists
        if interrupt_type in self._timeout_configs:
            self._timeout_configs[interrupt_type].escalation_targets = targets
    
    def set_notification_channels(
        self,
        interrupt_type: str,
        channels: List[str],
    ) -> None:
        """Set notification channels for an interrupt type."""
        self._notification_channels[interrupt_type] = channels
        
        # Update config if exists
        if interrupt_type in self._timeout_configs:
            self._timeout_configs[interrupt_type].notification_channels = channels
    
    def start_monitoring(
        self,
        interrupt_id: str,
        interrupt_type: str,
        created_at: datetime = None,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Start monitoring an interrupt for timeout.
        
        Args:
            interrupt_id: ID of the interrupt to monitor
            interrupt_type: Type of interrupt
            created_at: When the interrupt was created (defaults to now)
            metadata: Optional metadata for the timeout event
        """
        config = self._timeout_configs.get(interrupt_type)
        if not config:
            return  # No timeout configured for this type
        
        start_time = created_at or datetime.utcnow()
        expiry_time = start_time + timedelta(seconds=config.timeout_seconds)
        
        self._active_timeouts[interrupt_id] = expiry_time
        
        if metadata:
            # Store metadata for later use
            self._timeout_events.append(TimeoutEvent(
                interrupt_id=interrupt_id,
                interrupt_type=InterruptType(interrupt_type),
                original_timeout=config.timeout_seconds,
                occurred_at=start_time,
                policy_applied=config.policy,
                metadata=metadata,
            ))
    
    def stop_monitoring(self, interrupt_id: str) -> bool:
        """
        Stop monitoring an interrupt for timeout.
        
        Args:
            interrupt_id: ID of the interrupt to stop monitoring
        
        Returns:
            True if monitoring was stopped, False if not found
        """
        if interrupt_id in self._active_timeouts:
            del self._active_timeouts[interrupt_id]
            return True
        return False
    
    def extend_timeout(
        self,
        interrupt_id: str,
        additional_seconds: int = None,
    ) -> bool:
        """
        Extend the timeout for an interrupt.
        
        Args:
            interrupt_id: ID of the interrupt
            additional_seconds: Additional time in seconds (uses config if not specified)
        
        Returns:
            True if timeout was extended, False if not allowed or not found
        """
        if interrupt_id not in self._active_timeouts:
            return False
        
        # Find the interrupt type from events
        interrupt_type = None
        for event in self._timeout_events:
            if event.interrupt_id == interrupt_id:
                interrupt_type = event.interrupt_type.value
                break
        
        if not interrupt_type:
            return False
        
        config = self._timeout_configs.get(interrupt_type)
        if not config or not config.allow_extension:
            return False
        
        # Check extension limit
        current_extensions = self._extension_counts.get(interrupt_id, 0)
        if current_extensions >= config.max_extensions:
            return False
        
        # Calculate extension duration
        extension_seconds = (
            additional_seconds or
            config.extension_duration_seconds or
            config.timeout_seconds
        )
        
        # Extend the timeout
        self._active_timeouts[interrupt_id] = (
            datetime.utcnow() + timedelta(seconds=extension_seconds)
        )
        self._extension_counts[interrupt_id] = current_extensions + 1
        
        # Update event
        for event in self._timeout_events:
            if event.interrupt_id == interrupt_id:
                event.was_extended = True
                event.extension_count = self._extension_counts[interrupt_id]
                break
        
        return True
    
    def get_timeout_config(self, interrupt_type: str) -> Optional[TimeoutConfig]:
        """Get timeout configuration for an interrupt type."""
        return self._timeout_configs.get(interrupt_type)
    
    def get_time_remaining(self, interrupt_id: str) -> Optional[int]:
        """
        Get remaining time in seconds before timeout.
        
        Args:
            interrupt_id: ID of the interrupt
        
        Returns:
            Seconds remaining, or None if not found or already timed out
        """
        if interrupt_id not in self._active_timeouts:
            return None
        
        expiry = self._active_timeouts[interrupt_id]
        remaining = (expiry - datetime.utcnow()).total_seconds()
        
        if remaining <= 0:
            return 0
        
        return int(remaining)
    
    def is_timed_out(self, interrupt_id: str) -> bool:
        """Check if an interrupt has timed out."""
        return self.get_time_remaining(interrupt_id) == 0
    
    def get_pending_timeouts(self) -> List[Dict[str, Any]]:
        """
        Get all interrupts that are pending timeout.
        
        Returns:
            List of interrupt info with time remaining
        """
        pending = []
        now = datetime.utcnow()
        
        for interrupt_id, expiry in self._active_timeouts.items():
            remaining = (expiry - now).total_seconds()
            
            # Find interrupt type
            interrupt_type = None
            for event in self._timeout_events:
                if event.interrupt_id == interrupt_id:
                    interrupt_type = event.interrupt_type.value
                    break
            
            pending.append({
                "interrupt_id": interrupt_id,
                "interrupt_type": interrupt_type,
                "expires_at": expiry.isoformat(),
                "time_remaining_seconds": max(0, int(remaining)),
            })
        
        return pending
    
    async def check_timeouts(
        self,
        interrupt_manager: InterruptManager = None,
    ) -> List[TimeoutEvent]:
        """
        Check for timed-out interrupts and handle them.
        
        Args:
            interrupt_manager: Optional interrupt manager to record responses
        
        Returns:
            List of timeout events that were processed
        """
        timed_out_ids = []
        events = []
        now = datetime.utcnow()
        
        for interrupt_id, expiry in self._active_timeouts.items():
            if now >= expiry:
                timed_out_ids.append(interrupt_id)
        
        for interrupt_id in timed_out_ids:
            # Find the interrupt type
            interrupt_type = None
            for event in self._timeout_events:
                if event.interrupt_id == interrupt_id:
                    interrupt_type = event.interrupt_type.value
                    break
            
            if not interrupt_type:
                continue
            
            config = self._timeout_configs.get(interrupt_type)
            if not config:
                continue
            
            # Handle the timeout
            event = await self._handle_timeout(
                interrupt_id=interrupt_id,
                interrupt_type=interrupt_type,
                config=config,
                interrupt_manager=interrupt_manager,
            )
            
            if event:
                events.append(event)
                
                # Remove from active timeouts
                del self._active_timeouts[interrupt_id]
        
        return events
    
    async def _handle_timeout(
        self,
        interrupt_id: str,
        interrupt_type: str,
        config: TimeoutConfig,
        interrupt_manager: InterruptManager = None,
    ) -> Optional[TimeoutEvent]:
        """
        Handle a single timeout event.
        
        Args:
            interrupt_id: ID of the timed-out interrupt
            interrupt_type: Type of interrupt
            config: Timeout configuration
            interrupt_manager: Interrupt manager to record responses
        
        Returns:
            TimeoutEvent if handled, None if skipped
        """
        # Check escalation count
        escalation_count = self._escalation_counts.get(interrupt_id, 0)
        
        if escalation_count < config.max_escalations:
            # Escalate instead of applying policy
            self._escalation_counts[interrupt_id] = escalation_count + 1
            
            await self._send_escalation_notification(
                interrupt_id=interrupt_id,
                interrupt_type=interrupt_type,
                escalation_count=escalation_count + 1,
                targets=config.escalation_targets or self._escalation_targets.get(interrupt_type, []),
                channels=config.notification_channels or self._notification_channels.get(interrupt_type, []),
            )
            
            # Update event
            for event in self._timeout_events:
                if event.interrupt_id == interrupt_id:
                    event.escalation_count = escalation_count + 1
                    break
            
            return None  # Don't apply policy yet, waiting for escalation
        
        # Apply timeout policy
        response = None
        if interrupt_manager:
            response = await self._apply_timeout_policy(
                interrupt_id=interrupt_id,
                config=config,
                interrupt_manager=interrupt_manager,
            )
        
        # Create timeout event
        event = None
        for existing_event in self._timeout_events:
            if existing_event.interrupt_id == interrupt_id:
                event = existing_event
                event.response_generated = response.response if response else None
                break
        
        # Send final notification
        await self._send_timeout_notification(
            interrupt_id=interrupt_id,
            interrupt_type=interrupt_type,
            policy=config.policy,
            response=response,
            targets=config.escalation_targets or self._escalation_targets.get(interrupt_type, []),
            channels=config.notification_channels or self._notification_channels.get(interrupt_type, []),
        )
        
        return event
    
    async def _apply_timeout_policy(
        self,
        interrupt_id: str,
        config: TimeoutConfig,
        interrupt_manager: InterruptManager,
    ) -> InterruptResponse:
        """
        Apply the configured timeout policy.
        
        Args:
            interrupt_id: ID of the interrupt
            config: Timeout configuration
            interrupt_manager: Interrupt manager to record response
        
        Returns:
            The generated response
        """
        if config.policy == TimeoutPolicy.AUTO_REJECT:
            return interrupt_manager.reject(
                interrupt_id=interrupt_id,
                comment=f"Automatic rejection due to timeout after {config.timeout_seconds}s",
            )
        
        elif config.policy == TimeoutPolicy.AUTO_APPROVE:
            return interrupt_manager.approve(
                interrupt_id=interrupt_id,
                response=config.default_response or "Automatically approved due to timeout",
            )
        
        elif config.policy == TimeoutPolicy.AUTO_IGNORE:
            return interrupt_manager.ignore(
                interrupt_id=interrupt_id,
                comment=f"Automatic ignore due to timeout after {config.timeout_seconds}s",
            )
        
        elif config.policy == TimeoutPolicy.ESCALATE:
            return interrupt_manager.handle_response(
                interrupt_id=interrupt_id,
                status=InterruptStatus.TIMEOUT,
                comment=f"Timeout - escalated {self._escalation_counts.get(interrupt_id, 0)} times",
            )
        
        elif config.policy == TimeoutPolicy.NOTIFY_ONLY:
            # Don't modify interrupt state, just notify
            return InterruptResponse(
                interrupt_id=interrupt_id,
                status=InterruptStatus.TIMEOUT,
                comment="Timeout notification sent - interrupt still pending",
            )
        
        elif config.policy == TimeoutPolicy.AUTO_SUBMIT_DEFAULT:
            return interrupt_manager.custom_response(
                interrupt_id=interrupt_id,
                response=config.default_response or "Default response",
                comment=f"Automatic default response due to timeout after {config.timeout_seconds}s",
            )
        
        # Default to ignore
        return interrupt_manager.ignore(
            interrupt_id=interrupt_id,
            comment=f"Automatic ignore due to timeout after {config.timeout_seconds}s",
        )
    
    async def _send_escalation_notification(
        self,
        interrupt_id: str,
        interrupt_type: str,
        escalation_count: int,
        targets: List[str],
        channels: List[str],
    ) -> None:
        """Send escalation notification."""
        notification = {
            "type": "timeout_escalation",
            "interrupt_id": interrupt_id,
            "interrupt_type": interrupt_type,
            "escalation_level": escalation_count,
            "message": f"Human interrupt {interrupt_id} of type {interrupt_type} has timed out. Escalation level: {escalation_count}",
            "targets": targets,
            "channels": channels,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if self.notification_callback:
            self.notification_callback(notification)
        
        # TODO: Integrate with notification system (email, Slack, etc.)
    
    async def _send_timeout_notification(
        self,
        interrupt_id: str,
        interrupt_type: str,
        policy: TimeoutPolicy,
        response: InterruptResponse,
        targets: List[str],
        channels: List[str],
    ) -> None:
        """Send timeout notification."""
        notification = {
            "type": "timeout_handled",
            "interrupt_id": interrupt_id,
            "interrupt_type": interrupt_type,
            "policy_applied": policy.value,
            "response_generated": response.response if response else None,
            "message": f"Timeout for interrupt {interrupt_id} handled with policy: {policy.value}",
            "targets": targets,
            "channels": channels,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if self.notification_callback:
            self.notification_callback(notification)
        
        # TODO: Integrate with notification system
    
    async def start_background_checker(self) -> None:
        """Start the background timeout checker task."""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._background_check_loop())
    
    async def stop_background_checker(self) -> None:
        """Stop the background timeout checker task."""
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
    
    async def _background_check_loop(self) -> None:
        """Background loop for checking timeouts."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval_seconds)
                
                if not self._running:
                    break
                
                await self.check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error and continue
                pass
    
    def get_timeout_events(
        self,
        interrupt_id: str = None,
        interrupt_type: str = None,
        limit: int = 100,
    ) -> List[TimeoutEvent]:
        """
        Get timeout events, optionally filtered.
        
        Args:
            interrupt_id: Filter by interrupt ID
            interrupt_type: Filter by interrupt type
            limit: Maximum number of events to return
        
        Returns:
            List of timeout events
        """
        events = self._timeout_events
        
        if interrupt_id:
            events = [e for e in events if e.interrupt_id == interrupt_id]
        
        if interrupt_type:
            events = [e for e in events if e.interrupt_type.value == interrupt_type]
        
        return events[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get timeout handler statistics.
        
        Returns:
            Dictionary with statistics
        """
        # Count by policy
        policy_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        
        for event in self._timeout_events:
            policy_key = event.policy_applied.value
            policy_counts[policy_key] = policy_counts.get(policy_key, 0) + 1
            
            type_key = event.interrupt_type.value
            type_counts[type_key] = type_counts.get(type_key, 0) + 1
        
        return {
            "active_timeouts": len(self._active_timeouts),
            "total_timeouts_handled": len(self._timeout_events),
            "by_policy": policy_counts,
            "by_interrupt_type": type_counts,
            "is_running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "configured_interrupt_types": list(self._timeout_configs.keys()),
        }
    
    def reset(self) -> None:
        """Reset the timeout handler state."""
        self._active_timeouts.clear()
        self._escalation_counts.clear()
        self._extension_counts.clear()
        # Keep timeout_events for history, but could clear if needed


# ==================== Backward Compatibility Alias ====================

class TimeoutHandler(HumanResponseTimeoutHandler):
    """
    Backward-compatible timeout handler for human interrupts.
    
    This is an alias for HumanResponseTimeoutHandler for backwards compatibility.
    Supports configurable policies:
    - AUTO_REJECT: Automatically reject the action
    - AUTO_APPROVE: Automatically approve the action
    - AUTO_IGNORE: Automatically ignore and continue
    - ESCALATE: Escalate to admin/owner
    """
    
    class TimeoutPolicy(str, Enum):
        """Legacy timeout policy enum for backward compatibility."""
        AUTO_REJECT = "auto_reject"
        AUTO_APPROVE = "auto_approve"
        AUTO_IGNORE = "auto_ignore"
        ESCALATE = "escalate"
    
    def __init__(
        self,
        default_policy: Optional["TimeoutHandler.TimeoutPolicy"] = None,
        check_interval_seconds: int = 30,
        notification_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the timeout handler.
        
        Args:
            default_policy: Default timeout policy
            check_interval_seconds: Interval for checking timed-out interrupts
            notification_callback: Optional callback for timeout notifications
        """
        # Convert legacy policy to new policy
        if default_policy is None:
            policy = TimeoutPolicy.AUTO_IGNORE
        elif isinstance(default_policy, str):
            policy = TimeoutPolicy(default_policy)
        else:
            policy = default_policy
        
        super().__init__(
            default_policy=policy,
            check_interval_seconds=check_interval_seconds,
            notification_callback=notification_callback,
        )
    
    def set_policy(
        self,
        interrupt_type: str,
        policy: "TimeoutHandler.TimeoutPolicy",
    ) -> None:
        """Set timeout policy for a specific interrupt type."""
        self.configure_timeout(
            interrupt_type=interrupt_type,
            timeout_seconds=3600,  # Default timeout
            policy=policy,
        )
    
    def get_policy(self, interrupt_type: str) -> "TimeoutHandler.TimeoutPolicy":
        """Get timeout policy for an interrupt type."""
        config = self.get_timeout_config(interrupt_type)
        if config:
            return self.TimeoutPolicy(config.policy.value)
        return self.TimeoutPolicy(self.default_policy.value)
    
    def set_escalation_target(self, interrupt_type: str, targets: List[str]) -> None:
        """Set escalation targets for an interrupt type."""
        self.set_escalation_targets(interrupt_type, targets)
    
    def get_escalation_targets(self, interrupt_type: str) -> List[str]:
        """Get escalation targets for an interrupt type."""
        config = self.get_timeout_config(interrupt_type)
        if config:
            return config.escalation_targets
        return []
    
    def handle_timeout(
        self,
        interrupt_type: str,
        interrupt_id: str,
        interrupt_manager: InterruptManager,
    ) -> InterruptResponse:
        """
        Handle a timeout for an interrupt (sync version for backward compatibility).
        
        Args:
            interrupt_type: Type of interrupt
            interrupt_id: ID of the interrupt
            interrupt_manager: Interrupt manager to record response
        
        Returns:
            InterruptResponse for the timeout
        """
        # For backward compatibility, apply the policy immediately
        config = self.get_timeout_config(interrupt_type)
        if config:
            policy = config.policy
        else:
            policy = self.default_policy
        
        if policy == TimeoutPolicy.AUTO_REJECT:
            return interrupt_manager.reject(
                interrupt_id,
                comment="Automatic rejection due to timeout",
            )
        elif policy == TimeoutPolicy.AUTO_IGNORE:
            return interrupt_manager.ignore(
                interrupt_id,
                comment="Automatic ignore due to timeout",
            )
        elif policy == TimeoutPolicy.ESCALATE:
            targets = self.get_escalation_targets(interrupt_type)
            return interrupt_manager.handle_response(
                interrupt_id,
                InterruptStatus.TIMEOUT,
                comment=f"Timeout - escalated to {targets}",
            )
        else:  # AUTO_APPROVE
            return interrupt_manager.approve(
                interrupt_id,
                comment="Automatic approval due to timeout",
            )


# ==================== Human-in-the-Loop Decorator ====================

def with_human_in_the_loop(
    interrupt_type: Optional[InterruptType] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    options: Optional[List[str]] = None,
    priority: InterruptPriority = InterruptPriority.MEDIUM,
    allow_ignore: bool = True,
    allow_response: bool = True,
    timeout_seconds: Optional[int] = None,
    condition_key: Optional[str] = None,
    condition_value: Any = True,
    on_interrupt: Optional[Callable] = None,
    manager_attr: str = "interrupt_manager",
) -> Callable:
    """
    Decorator to add human-in-the-loop interrupt capability to a node function.
    
    This decorator wraps a LangGraph node function to:
    1. Check if an interrupt condition is met
    2. Create an interrupt configuration
    3. Return a LangGraph Interrupt if condition is met
    4. Handle the response when execution resumes
    
    Args:
        interrupt_type: Type of interrupt to create
        title: Interrupt title (auto-generated if not provided)
        description: Interrupt description (auto-generated if not provided)
        options: Response options
        priority: Interrupt priority
        allow_ignore: Whether ignore is allowed
        allow_response: Whether custom response is allowed
        timeout_seconds: Timeout in seconds
        condition_key: State key to check for interrupt condition
        condition_value: Value that triggers the interrupt
        on_interrupt: Optional callback when interrupt is created
        manager_attr: Attribute name of interrupt manager on the agent
    
    Returns:
        Decorated function that returns state or Interrupt
    
    Example:
        @with_human_in_the_loop(
            interrupt_type=InterruptType.ARTIFACT_APPROVAL,
            title="Artifact Approval Required",
            condition_key="needs_approval",
            condition_value=True,
        )
        def review_artifact(state):
            # Your node logic here
            return {"artifact": state["generated_artifact"]}
    """
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            # Get the interrupt manager from the agent/state
            manager = kwargs.get(manager_attr)
            if manager is None and "agent" in state:
                manager = state["agent"].get(manager_attr)
            
            # Check condition if specified
            if condition_key is not None:
                current_value = state.get(condition_key)
                if current_value != condition_value:
                    # Condition not met, execute normally
                    return await func(state, *args, **kwargs)
            
            # Create interrupt
            interrupt_title = title or f"{interrupt_type.value.replace('_', ' ').title()} Required"
            interrupt_desc = description or "An interrupt requires your attention."
            
            config = HumanInterruptConfig(
                interrupt_type=interrupt_type or InterruptType.CUSTOM,
                title=interrupt_title,
                description=interrupt_desc,
                options=options or [],
                priority=priority,
                allow_ignore=allow_ignore,
                allow_response=allow_response,
                timeout_seconds=timeout_seconds,
            )
            
            # Store config in state for later reference
            state["pending_interrupt"] = config.model_dump()
            
            # Call on_interrupt callback if provided
            if on_interrupt:
                on_interrupt(config)
            
            # Return interrupt to pause execution
            return create_interrupt(
                interrupt_type=config.interrupt_type,
                value=config.to_interrupt_value() if hasattr(config, "to_interrupt_value") else {
                    "interrupt_id": config.interrupt_id,
                    "title": config.title,
                    "description": config.description,
                    "options": config.options,
                    "priority": config.priority.value,
                },
                resume="human_response",
            )
        
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            # Get the interrupt manager from the agent/state
            manager = kwargs.get(manager_attr)
            if manager is None and "agent" in state:
                manager = state["agent"].get(manager_attr)
            
            # Check condition if specified
            if condition_key is not None:
                current_value = state.get(condition_key)
                if current_value != condition_value:
                    # Condition not met, execute normally
                    return func(state, *args, **kwargs)
            
            # Create interrupt
            interrupt_title = title or f"{interrupt_type.value.replace('_', ' ').title()} Required"
            interrupt_desc = description or "An interrupt requires your attention."
            
            config = HumanInterruptConfig(
                interrupt_type=interrupt_type or InterruptType.CUSTOM,
                title=interrupt_title,
                description=interrupt_desc,
                options=options or [],
                priority=priority,
                allow_ignore=allow_ignore,
                allow_response=allow_response,
                timeout_seconds=timeout_seconds,
            )
            
            # Store config in state for later reference
            state["pending_interrupt"] = config.model_dump()
            
            # Call on_interrupt callback if provided
            if on_interrupt:
                on_interrupt(config)
            
            # Return interrupt to pause execution
            return create_interrupt(
                interrupt_type=config.interrupt_type,
                value={
                    "interrupt_id": config.interrupt_id,
                    "title": config.title,
                    "description": config.description,
                    "options": config.options,
                    "priority": config.priority.value,
                },
                resume="human_response",
            )
        
        # Check if the function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def interrupt_handler(
    state_key: str = "human_response",
    manager_attr: str = "interrupt_manager",
) -> Callable:
    """
    Decorator to handle interrupt responses after resumption.
    
    This decorator wraps a node function that handles the response
    from a human interrupt. It extracts the response from state and
    processes it through the interrupt manager.
    
    Args:
        state_key: State key containing the response value
        manager_attr: Attribute name of interrupt manager on the agent
    
    Returns:
        Decorated function that processes interrupt responses
    
    Example:
        @interrupt_handler(state_key="human_response")
        def handle_approval_response(state):
            response = state[state_key]
            # Process the response
            return {"decision": response}
    """
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            response_value = state.get(state_key)
            
            if response_value is None:
                # No response yet, execute normally
                return await func(state, *args, **kwargs)
            
            # Get the interrupt manager
            manager = kwargs.get(manager_attr)
            if manager is None and "agent" in state:
                manager = state["agent"].get(manager_attr)
            
            # Get the pending interrupt config
            pending_interrupt = state.get("pending_interrupt")
            
            if pending_interrupt and manager:
                interrupt_id = pending_interrupt.get("interrupt_id")
                
                # Handle the response
                if isinstance(response_value, dict):
                    # Response is a dict with details
                    status = InterruptStatus(response_value.get("status", "approved"))
                    response_text = response_value.get("response")
                else:
                    status = InterruptStatus.APPROVED
                    response_text = str(response_value)
                
                manager.record_response(
                    InterruptResponse(
                        interrupt_id=interrupt_id,
                        status=status,
                        response=response_text,
                    )
                )
            
            # Clear the pending interrupt
            state["pending_interrupt"] = None
            
            # Execute the handler
            return await func(state, *args, **kwargs)
        
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            response_value = state.get(state_key)
            
            if response_value is None:
                # No response yet, execute normally
                return func(state, *args, **kwargs)
            
            # Get the interrupt manager
            manager = kwargs.get(manager_attr)
            if manager is None and "agent" in state:
                manager = state["agent"].get(manager_attr)
            
            # Get the pending interrupt config
            pending_interrupt = state.get("pending_interrupt")
            
            if pending_interrupt and manager:
                interrupt_id = pending_interrupt.get("interrupt_id")
                
                # Handle the response
                if isinstance(response_value, dict):
                    status = InterruptStatus(response_value.get("status", "approved"))
                    response_text = response_value.get("response")
                else:
                    status = InterruptStatus.APPROVED
                    response_text = str(response_value)
                
                manager.record_response(
                    InterruptResponse(
                        interrupt_id=interrupt_id,
                        status=status,
                        response=response_text,
                    )
                )
            
            # Clear the pending interrupt
            state["pending_interrupt"] = None
            
            # Execute the handler
            return func(state, *args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def conditional_interrupt(
    condition: Callable[[Dict[str, Any]], bool],
    interrupt_config: HumanInterruptConfig,
    manager_attr: str = "interrupt_manager",
) -> Callable:
    """
    Decorator factory for conditional interrupts based on state.
    
    This decorator checks a condition function and creates an interrupt
    if the condition returns True.
    
    Args:
        condition: Function that takes state and returns bool
        interrupt_config: Interrupt configuration to use
        manager_attr: Attribute name of interrupt manager on the agent
    
    Returns:
        Decorated function that conditionally interrupts
    
    Example:
        def needs_approval(state):
            return state.get("quality_score", 0) < 0.8
        
        @conditional_interrupt(
            condition=needs_approval,
            interrupt_config=HumanInterruptConfig(
                interrupt_type=InterruptType.ARTIFACT_APPROVAL,
                title="Low Quality Artifact",
                description="This artifact scored below quality threshold.",
                options=["Approve anyway", "Regenerate"],
            ),
        )
        def generate_artifact(state):
            return {"artifact": create_artifact(state)}
    """
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            if not condition(state):
                return await func(state, *args, **kwargs)
            
            # Return interrupt
            return create_interrupt(
                interrupt_type=interrupt_config.interrupt_type,
                value=interrupt_config.to_interrupt_value() if hasattr(interrupt_config, "to_interrupt_value") else {
                    "interrupt_id": interrupt_config.interrupt_id,
                    "title": interrupt_config.title,
                    "description": interrupt_config.description,
                    "options": interrupt_config.options,
                    "priority": interrupt_config.priority.value,
                },
                resume="human_response",
            )
        
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            if not condition(state):
                return func(state, *args, **kwargs)
            
            # Return interrupt
            return create_interrupt(
                interrupt_type=interrupt_config.interrupt_type,
                value={
                    "interrupt_id": interrupt_config.interrupt_id,
                    "title": interrupt_config.title,
                    "description": interrupt_config.description,
                    "options": interrupt_config.options,
                    "priority": interrupt_config.priority.value,
                },
                resume="human_response",
            )
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ==================== Checkpoint Before Interrupt ====================

class InterruptCheckpointManager:
    """
    Manages checkpoints before interrupt points for resumption.
    
    Provides:
    1. State snapshot before interrupts
    2. Checkpoint retrieval for resumption
    3. Checkpoint cleanup and management
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the checkpoint manager.
        
        Args:
            redis_url: Optional Redis URL for distributed checkpoint storage
        """
        self.redis_url = redis_url
        self._redis_client = None
        self._local_checkpoints: Dict[str, Dict[str, Any]] = {}
    
    async def _get_redis_client(self):
        """Get or create Redis client."""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "redis package required for checkpoint persistence. "
                    "Install with: pip install redis"
                )
        return self._redis_client
    
    async def save_checkpoint(
        self,
        thread_id: str,
        interrupt_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save a checkpoint before an interrupt.
        
        Args:
            thread_id: LangGraph thread ID
            interrupt_id: ID of the interrupt this checkpoint is for
            state: State dictionary to checkpoint
            metadata: Optional metadata about the checkpoint
        
        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid4())
        
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "thread_id": thread_id,
            "interrupt_id": interrupt_id,
            "state": state,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }
        
        if self.redis_url:
            try:
                client = await self._get_redis_client()
                key = f"checkpoint:{thread_id}:{interrupt_id}"
                import json
                await client.set(key, json.dumps(checkpoint_data), ex=86400)
            except Exception:
                # Fallback to local storage
                self._local_checkpoints[f"{thread_id}:{interrupt_id}"] = checkpoint_data
        else:
            self._local_checkpoints[f"{thread_id}:{interrupt_id}"] = checkpoint_data
        
        return checkpoint_id
    
    async def load_checkpoint(
        self,
        thread_id: str,
        interrupt_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint for an interrupt.
        
        Args:
            thread_id: LangGraph thread ID
            interrupt_id: ID of the interrupt
        
        Returns:
            Checkpoint data or None if not found
        """
        key = f"checkpoint:{thread_id}:{interrupt_id}"
        
        if self.redis_url:
            try:
                client = await self._get_redis_client()
                data = await client.get(key)
                if data:
                    import json
                    return json.loads(data)
                return None
            except Exception:
                pass
        
        # Try local storage
        checkpoint_data = self._local_checkpoints.get(f"{thread_id}:{interrupt_id}")
        return checkpoint_data
    
    async def get_checkpoint_state(
        self,
        thread_id: str,
        interrupt_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the state from a checkpoint.
        
        Args:
            thread_id: LangGraph thread ID
            interrupt_id: ID of the interrupt
        
        Returns:
            State dictionary or None if not found
        """
        checkpoint = await self.load_checkpoint(thread_id, interrupt_id)
        if checkpoint:
            return checkpoint.get("state")
        return None
    
    async def delete_checkpoint(
        self,
        thread_id: str,
        interrupt_id: str,
    ) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            thread_id: LangGraph thread ID
            interrupt_id: ID of the interrupt
        
        Returns:
            True if deleted successfully
        """
        key = f"checkpoint:{thread_id}:{interrupt_id}"
        
        if self.redis_url:
            try:
                client = await self._get_redis_client()
                await client.delete(key)
                self._local_checkpoints.pop(f"{thread_id}:{interrupt_id}", None)
                return True
            except Exception:
                pass
        
        self._local_checkpoints.pop(f"{thread_id}:{interrupt_id}", None)
        return True
    
    async def list_thread_checkpoints(
        self,
        thread_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List all checkpoints for a thread.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            List of checkpoint metadata
        """
        checkpoints = []
        
        if self.redis_url:
            try:
                client = await self._get_redis_client()
                pattern = f"checkpoint:{thread_id}:*"
                keys = await client.keys(pattern)
                
                for key in keys:
                    data = await client.get(key)
                    if data:
                        import json
                        checkpoint = json.loads(data)
                        checkpoints.append({
                            "interrupt_id": checkpoint.get("interrupt_id"),
                            "checkpoint_id": checkpoint.get("checkpoint_id"),
                            "created_at": checkpoint.get("created_at"),
                            "metadata": checkpoint.get("metadata"),
                        })
            except Exception:
                pass
        
        # Include local checkpoints
        for key, value in self._local_checkpoints.items():
            if key.startswith(f"{thread_id}:"):
                checkpoints.append({
                    "interrupt_id": value.get("interrupt_id"),
                    "checkpoint_id": value.get("checkpoint_id"),
                    "created_at": value.get("created_at"),
                    "metadata": value.get("metadata"),
                })
        
        return checkpoints
    
    async def cleanup_thread_checkpoints(self, thread_id: str) -> int:
        """
        Clean up all checkpoints for a thread.
        
        Args:
            thread_id: LangGraph thread ID
        
        Returns:
            Number of checkpoints deleted
        """
        count = 0
        
        if self.redis_url:
            try:
                client = await self._get_redis_client()
                pattern = f"checkpoint:{thread_id}:*"
                keys = await client.keys(pattern)
                
                if keys:
                    count = await client.delete(*keys)
            except Exception:
                pass
        
        # Clean local storage
        keys_to_delete = [
            k for k in self._local_checkpoints.keys()
            if k.startswith(f"{thread_id}:")
        ]
        for key in keys_to_delete:
            del self._local_checkpoints[key]
            count += 1
        
        return count
    
    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None


def checkpoint_before_interrupt(
    checkpoint_manager_attr: str = "checkpoint_manager",
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Decorator to save a checkpoint before an interrupt.
    
    This decorator wraps a node function that may trigger an interrupt.
    It saves a checkpoint of the state before the potential interrupt,
    allowing the agent to resume from this point if needed.
    
    Args:
        checkpoint_manager_attr: Attribute name of checkpoint manager on the agent
        metadata: Optional metadata to include in the checkpoint
    
    Returns:
        Decorated function that saves checkpoint before interrupt
    
    Example:
        @checkpoint_before_interrupt(metadata={"node": "validate_artifact"})
        def validate_artifact(state):
            # Validation logic that may trigger interrupt
            if state.get("needs_approval"):
                return create_interrupt(...)
            return {"validated": True}
    """
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            # Get the checkpoint manager
            checkpoint_manager = kwargs.get(checkpoint_manager_attr)
            if checkpoint_manager is None and "agent" in state:
                checkpoint_manager = state["agent"].get(checkpoint_manager_attr)
            
            # Save checkpoint before executing
            thread_id = state.get("thread_id", "default")
            interrupt_id = state.get("pending_interrupt", {}).get("interrupt_id", str(uuid4()))
            
            checkpoint_id = None
            if checkpoint_manager:
                checkpoint_id = await checkpoint_manager.save_checkpoint(
                    thread_id=thread_id,
                    interrupt_id=interrupt_id,
                    state=state,
                    metadata={"node": func.__name__, **(metadata or {})},
                )
                state["_checkpoint_id"] = checkpoint_id
            
            # Execute the function
            result = await func(state, *args, **kwargs)
            
            # If result is an interrupt, update checkpoint with interrupt_id
            if isinstance(result, Interrupt) and checkpoint_manager:
                interrupt_value = result.value if hasattr(result, "value") else result
                if isinstance(interrupt_value, dict):
                    actual_interrupt_id = interrupt_value.get("interrupt_id", interrupt_id)
                    await checkpoint_manager.save_checkpoint(
                        thread_id=thread_id,
                        interrupt_id=actual_interrupt_id,
                        state=state,
                        metadata={"node": func.__name__, "checkpoint_id": checkpoint_id, **(metadata or {})},
                    )
            
            return result
        
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Union[Dict[str, Any], Interrupt]:
            # Get the checkpoint manager
            checkpoint_manager = kwargs.get(checkpoint_manager_attr)
            if checkpoint_manager is None and "agent" in state:
                checkpoint_manager = state["agent"].get(checkpoint_manager_attr)
            
            # Save checkpoint before executing
            thread_id = state.get("thread_id", "default")
            interrupt_id = state.get("pending_interrupt", {}).get("interrupt_id", str(uuid4()))
            
            checkpoint_id = None
            if checkpoint_manager:
                checkpoint_id = checkpoint_manager.save_checkpoint(
                    thread_id=thread_id,
                    interrupt_id=interrupt_id,
                    state=state,
                    metadata={"node": func.__name__, **(metadata or {})},
                )
                state["_checkpoint_id"] = checkpoint_id
            
            # Execute the function
            result = func(state, *args, **kwargs)
            
            return result
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def resume_from_checkpoint(
    checkpoint_manager_attr: str = "checkpoint_manager",
    state_key: str = "human_response",
) -> Callable:
    """
    Decorator to resume from a checkpoint after an interrupt response.
    
    This decorator wraps a node function that handles the response
    from an interrupt. It retrieves the checkpoint state and uses it
    as the base state for resuming execution.
    
    Args:
        checkpoint_manager_attr: Attribute name of checkpoint manager on the agent
        state_key: State key containing the response value
    
    Returns:
        Decorated function that resumes from checkpoint
    
    Example:
        @resume_from_checkpoint()
        def handle_approval_response(state):
            # State is restored from checkpoint before this runs
            response = state[state_key]
            return process_response(state, response)
    """
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            # Check if we have a response to resume from
            response_value = state.get(state_key)
            
            if response_value is None:
                # No response, execute normally
                return await func(state, *args, **kwargs)
            
            # Get the checkpoint manager
            checkpoint_manager = kwargs.get(checkpoint_manager_attr)
            if checkpoint_manager is None and "agent" in state:
                checkpoint_manager = state["agent"].get(checkpoint_manager_attr)
            
            # Get checkpoint ID from state
            checkpoint_id = state.get("_checkpoint_id")
            
            if checkpoint_manager and checkpoint_id:
                # Try to load from pending interrupt or checkpoint
                interrupt_id = state.get("pending_interrupt", {}).get("interrupt_id")
                
                if interrupt_id:
                    checkpoint_state = await checkpoint_manager.get_checkpoint_state(
                        state.get("thread_id", "default"),
                        interrupt_id,
                    )
                    
                    if checkpoint_state:
                        # Merge checkpoint state with current state
                        # Priority to current state for response values
                        checkpoint_state.update(state)
                        state = checkpoint_state
            
            # Execute the handler with restored state
            return await func(state, *args, **kwargs)
        
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            response_value = state.get(state_key)
            
            if response_value is None:
                return func(state, *args, **kwargs)
            
            checkpoint_manager = kwargs.get(checkpoint_manager_attr)
            if checkpoint_manager is None and "agent" in state:
                checkpoint_manager = state["agent"].get(checkpoint_manager_attr)
            
            checkpoint_id = state.get("_checkpoint_id")
            
            if checkpoint_manager and checkpoint_id:
                interrupt_id = state.get("pending_interrupt", {}).get("interrupt_id")
                
                if interrupt_id:
                    checkpoint_state = checkpoint_manager.get_checkpoint_state(
                        state.get("thread_id", "default"),
                        interrupt_id,
                    )
                    
                    if checkpoint_state:
                        checkpoint_state.update(state)
                        state = checkpoint_state
            
            return func(state, *args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


