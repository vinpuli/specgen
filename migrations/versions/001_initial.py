"""Initial database migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-04 00:00:00.000000

"""
from typing import Union
import uuid
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables for the specgen database."""
    
    # Create ENUM types
    _create_enum_types()
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('is_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('two_factor_enabled', sa.Boolean, default=False, nullable=False),
        sa.Column('two_factor_secret', sa.String(255), nullable=True),
        sa.Column('oauth_providers', postgresql.ARRAY(sa.String(50)), default=list, nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        schema='public',
    )
    
    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_tier', sa.Enum('free', 'starter', 'professional', 'enterprise', name='plan_tier_enum'), default='free', nullable=False),
        sa.Column('settings', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_workspaces_owner_id', 'owner_id'),
        schema='public',
    )
    
    # Create workspace_members table
    op.create_table(
        'workspace_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('role', sa.Enum('owner', 'admin', 'editor', 'viewer', name='workspace_role_enum'), default='viewer', nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_workspace_members_workspace_id', 'workspace_id'),
        sa.Index('ix_workspace_members_user_id', 'user_id'),
        schema='public',
    )
    
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('project_type', sa.Enum('greenfield', 'brownfield', name='project_type_enum'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'active', 'completed', 'archived', name='project_status_enum'), default='draft', nullable=False),
        sa.Column('repository_url', sa.String(512), nullable=True),
        sa.Column('repository_provider', sa.String(50), nullable=True),
        sa.Column('default_branch', sa.String(100), default='main', nullable=False),
        sa.Column('settings', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_projects_workspace_id', 'workspace_id'),
        sa.Index('ix_projects_status', 'status'),
        sa.Index('ix_projects_created_by', 'created_by'),
        schema='public',
    )
    
    # Create branches table
    op.create_table(
        'branches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('branches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('active', 'merged', 'closed', name='branch_status_enum'), default='active', nullable=False),
        sa.Column('is_protected', sa.Boolean, default=False, nullable=False),
        sa.Column('mergeable', sa.Boolean, default=True, nullable=False),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('merge_conflicts', postgresql.JSONB, default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_branches_project_id', 'project_id'),
        sa.Index('ix_branches_status', 'status'),
        sa.Index('ix_branches_name', 'name'),
        schema='public',
    )
    
    # Create decisions table
    op.create_table(
        'decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('branches.id', ondelete='CASCADE'), nullable=True),
        sa.Column('asked_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('answered_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_text', sa.Text, nullable=False),
        sa.Column('answer_text', sa.Text, nullable=True),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('category', sa.Enum('architecture', 'database', 'api', 'security', 'deployment', 'framework', 'integration', 'ux_ui', 'performance', 'compliance', 'other', name='decision_category_enum'), default='other', nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), default=list, nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'awaiting_answer', 'answered', 'locked', 'deprecated', name='decision_status_enum'), default='pending', nullable=False),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', 'critical', name='decision_priority_enum'), default='medium', nullable=False),
        sa.Column('is_locked', sa.Boolean, default=False, nullable=False),
        sa.Column('locked_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ai_generated', sa.Boolean, default=False, nullable=False),
        sa.Column('confidence_score', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Index('ix_decisions_project_id', 'project_id'),
        sa.Index('ix_decisions_status', 'status'),
        sa.Index('ix_decisions_category', 'category'),
        sa.Index('ix_decisions_branch_id', 'branch_id'),
        schema='public',
    )
    
    # Create decision_dependencies table
    op.create_table(
        'decision_dependencies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('source_decision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('decisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_decision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('decisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dependency_type', sa.String(50), default='requires', nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_decision_dependencies_source', 'source_decision_id'),
        sa.Index('ix_decision_dependencies_target', 'target_decision_id'),
        schema='public',
    )
    
    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('branches.id', ondelete='CASCADE'), nullable=True),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('artifact_type', sa.Enum('prd', 'api_spec', 'database_schema', 'architecture', 'tickets', 'tests', 'deployment', 'openapi', 'graphql', 'grpc', 'markdown', 'json', 'yaml', 'custom', name='artifact_type_enum'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('content', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('format', sa.Enum('markdown', 'json', 'yaml', 'html', 'pdf', 'plaintext', 'openapi_json', 'openapi_yaml', name='artifact_format_enum'), default='markdown', nullable=False),
        sa.Column('status', sa.Enum('pending', 'generating', 'completed', 'failed', 'regenerating', name='artifact_status_enum'), default='pending', nullable=False),
        sa.Column('version', sa.Integer, default=1, nullable=False),
        sa.Column('is_latest', sa.Boolean, default=True, nullable=False),
        sa.Column('file_size', sa.Integer, nullable=True),
        sa.Column('checksum', sa.String(64), nullable=True),
        sa.Column('metadata', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Index('ix_artifacts_project_id', 'project_id'),
        sa.Index('ix_artifacts_type', 'artifact_type'),
        sa.Index('ix_artifacts_status', 'status'),
        sa.Index('ix_artifacts_branch_id', 'branch_id'),
        schema='public',
    )
    
    # Create artifact_versions table
    op.create_table(
        'artifact_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('changelog', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_artifact_versions_artifact_id', 'artifact_id'),
        schema='public',
    )
    
    # Create decision_artifacts association table
    op.create_table(
        'decision_artifacts',
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('decisions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id', ondelete='CASCADE'), primary_key=True),
        schema='public',
    )
    
    # Create comments table
    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('decisions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('parent_comment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('comment_type', sa.Enum('question', 'suggestion', 'issue', 'praise', 'clarification', 'contradiction', 'ai_review', name='comment_type_enum'), default='suggestion', nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('status', sa.Enum('open', 'resolved', 'wontfix', 'archived', name='comment_status_enum'), default='open', nullable=False),
        sa.Column('is_ai_generated', sa.Boolean, default=False, nullable=False),
        sa.Column('resolve_requested', sa.Boolean, default=False, nullable=False),
        sa.Column('re_question_triggered', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Index('ix_comments_project_id', 'project_id'),
        sa.Index('ix_comments_artifact_id', 'artifact_id'),
        sa.Index('ix_comments_decision_id', 'decision_id'),
        sa.Index('ix_comments_parent_id', 'parent_comment_id'),
        sa.Index('ix_comments_author_id', 'author_id'),
        schema='public',
    )
    
    # Create conversation_turns table
    op.create_table(
        'conversation_turns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('decisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('turn_number', sa.Integer, nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_ai_generated', sa.Boolean, default=False, nullable=False),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('confidence_score', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_conversation_turns_decision_id', 'decision_id'),
        schema='public',
    )
    
    # Create codebase_analyses table
    op.create_table(
        'codebase_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'failed', name='analysis_status_enum'), default='pending', nullable=False),
        sa.Column('repository_url', sa.String(512), nullable=True),
        sa.Column('commit_sha', sa.String(40), nullable=True),
        sa.Column('branch_name', sa.String(100), nullable=True),
        sa.Column('languages', postgresql.ARRAY(sa.String(50)), default=list, nullable=False),
        sa.Column('language_stats', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('total_loc', sa.Integer, nullable=True),
        sa.Column('file_count', sa.Integer, nullable=True),
        sa.Column('architecture_summary', sa.Text, nullable=True),
        sa.Column('component_inventory', postgresql.JSONB, default=list, nullable=False),
        sa.Column('dependency_graph', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('detected_patterns', postgresql.JSONB, default=list, nullable=False),
        sa.Column('file_metrics', postgresql.JSONB, default=list, nullable=False),
        sa.Column('findings', postgresql.JSONB, default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Index('ix_codebase_analyses_project_id', 'project_id'),
        sa.Index('ix_codebase_analyses_status', 'status'),
        schema='public',
    )
    
    # Create impact_analyses table
    op.create_table(
        'impact_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('codebase_analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('codebase_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_description', sa.Text, nullable=False),
        sa.Column('affected_files', postgresql.ARRAY(sa.String(512)), default=list, nullable=False),
        sa.Column('affected_components', postgresql.ARRAY(sa.String(255)), default=list, nullable=False),
        sa.Column('risk_level', sa.Enum('low', 'medium', 'high', 'critical', name='risk_level_enum'), default='medium', nullable=False),
        sa.Column('risk_factors', postgresql.JSONB, default=list, nullable=False),
        sa.Column('breaking_changes', postgresql.JSONB, default=list, nullable=False),
        sa.Column('api_changes', postgresql.JSONB, default=list, nullable=False),
        sa.Column('schema_changes', postgresql.JSONB, default=list, nullable=False),
        sa.Column('downstream_dependencies', postgresql.JSONB, default=list, nullable=False),
        sa.Column('upstream_dependencies', postgresql.JSONB, default=list, nullable=False),
        sa.Column('test_impact', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('new_tests_needed', postgresql.JSONB, default=list, nullable=False),
        sa.Column('rollback_procedure', sa.Text, nullable=True),
        sa.Column('rollback_risk', sa.Enum('low', 'medium', 'high', 'critical', name='risk_level_enum'), nullable=True),
        sa.Column('change_plan', postgresql.JSONB, default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_impact_analyses_project_id', 'project_id'),
        sa.Index('ix_impact_analyses_risk_level', 'risk_level'),
        schema='public',
    )
    
    # Create templates table
    op.create_table(
        'templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.Enum('web_application', 'api_service', 'microservice', 'mobile_app', 'cli_tool', 'library', 'full_stack', 'data_pipeline', 'machine_learning', 'custom', name='template_category_enum'), default='custom', nullable=False),
        sa.Column('content', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('default_decisions', postgresql.JSONB, default=list, nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), default=list, nullable=False),
        sa.Column('technologies', postgresql.ARRAY(sa.String(100)), default=list, nullable=False),
        sa.Column('is_public', sa.Boolean, default=False, nullable=False),
        sa.Column('is_featured', sa.Boolean, default=False, nullable=False),
        sa.Column('usage_count', sa.Integer, default=0, nullable=False),
        sa.Column('rating', sa.Integer, nullable=True),
        sa.Column('version', sa.Integer, default=1, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_templates_workspace_id', 'workspace_id'),
        sa.Index('ix_templates_category', 'category'),
        sa.Index('ix_templates_name', 'name'),
        schema='public',
    )
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='SET NULL'), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.Enum('login', 'logout', 'login_failed', 'password_change', 'password_reset', 'mfa_enabled', 'mfa_disabled', 'oauth_connect', 'oauth_disconnect', 'user_create', 'user_update', 'user_delete', 'user_verify', 'workspace_create', 'workspace_update', 'workspace_delete', 'workspace_join', 'workspace_leave', 'workspace_invite', 'workspace_role_change', 'project_create', 'project_update', 'project_delete', 'project_archive', 'decision_create', 'decision_update', 'decision_answer', 'decision_lock', 'decision_unlock', 'decision_dependency_add', 'decision_dependency_remove', 'branch_create', 'branch_merge', 'branch_delete', 'branch_conflict', 'artifact_generate', 'artifact_update', 'artifact_delete', 'artifact_export', 'artifact_version', 'artifact_rollback', 'comment_create', 'comment_update', 'comment_delete', 'comment_resolve', 'codebase_analyze', 'impact_analyze', 'change_plan_generate', 'admin_action', 'data_export', 'data_delete', name='audit_action_enum'), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('success', sa.Boolean, default=True, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('changes', postgresql.JSONB, default=dict, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
        sa.Index('ix_audit_logs_user_id', 'user_id'),
        sa.Index('ix_audit_logs_action', 'action'),
        sa.Index('ix_audit_logs_resource_type', 'resource_type'),
        sa.Index('ix_audit_logs_resource_id', 'resource_id'),
        sa.Index('ix_audit_logs_workspace_id', 'workspace_id'),
        sa.Index('ix_audit_logs_created_at', 'created_at'),
        schema='public',
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('audit_logs', schema='public')
    op.drop_table('templates', schema='public')
    op.drop_table('impact_analyses', schema='public')
    op.drop_table('codebase_analyses', schema='public')
    op.drop_table('conversation_turns', schema='public')
    op.drop_table('comments', schema='public')
    op.drop_table('decision_artifacts', schema='public')
    op.drop_table('artifact_versions', schema='public')
    op.drop_table('artifacts', schema='public')
    op.drop_table('decision_dependencies', schema='public')
    op.drop_table('decisions', schema='public')
    op.drop_table('branches', schema='public')
    op.drop_table('projects', schema='public')
    op.drop_table('workspace_members', schema='public')
    op.drop_table('workspaces', schema='public')
    op.drop_table('users', schema='public')
    
    # Drop enum types
    _drop_enum_types()


def _create_enum_types():
    """Create PostgreSQL enum types."""
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE plan_tier_enum AS ENUM ('free', 'starter', 'professional', 'enterprise');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE workspace_role_enum AS ENUM ('owner', 'admin', 'editor', 'viewer');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE project_type_enum AS ENUM ('greenfield', 'brownfield');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE project_status_enum AS ENUM ('draft', 'active', 'completed', 'archived');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE branch_status_enum AS ENUM ('active', 'merged', 'closed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decision_category_enum AS ENUM ('architecture', 'database', 'api', 'security', 'deployment', 'framework', 'integration', 'ux_ui', 'performance', 'compliance', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decision_status_enum AS ENUM ('pending', 'in_progress', 'awaiting_answer', 'answered', 'locked', 'deprecated');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decision_priority_enum AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE artifact_type_enum AS ENUM ('prd', 'api_spec', 'database_schema', 'architecture', 'tickets', 'tests', 'deployment', 'openapi', 'graphql', 'grpc', 'markdown', 'json', 'yaml', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE artifact_format_enum AS ENUM ('markdown', 'json', 'yaml', 'html', 'pdf', 'plaintext', 'openapi_json', 'openapi_yaml');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE artifact_status_enum AS ENUM ('pending', 'generating', 'completed', 'failed', 'regenerating');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE comment_type_enum AS ENUM ('question', 'suggestion', 'issue', 'praise', 'clarification', 'contradiction', 'ai_review');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE comment_status_enum AS ENUM ('open', 'resolved', 'wontfix', 'archived');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analysis_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE risk_level_enum AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE template_category_enum AS ENUM ('web_application', 'api_service', 'microservice', 'mobile_app', 'cli_tool', 'library', 'full_stack', 'data_pipeline', 'machine_learning', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE audit_action_enum AS ENUM ('login', 'logout', 'login_failed', 'password_change', 'password_reset', 'mfa_enabled', 'mfa_disabled', 'oauth_connect', 'oauth_disconnect', 'user_create', 'user_update', 'user_delete', 'user_verify', 'workspace_create', 'workspace_update', 'workspace_delete', 'workspace_join', 'workspace_leave', 'workspace_invite', 'workspace_role_change', 'project_create', 'project_update', 'project_delete', 'project_archive', 'decision_create', 'decision_update', 'decision_answer', 'decision_lock', 'decision_unlock', 'decision_dependency_add', 'decision_dependency_remove', 'branch_create', 'branch_merge', 'branch_delete', 'branch_conflict', 'artifact_generate', 'artifact_update', 'artifact_delete', 'artifact_export', 'artifact_version', 'artifact_rollback', 'comment_create', 'comment_update', 'comment_delete', 'comment_resolve', 'codebase_analyze', 'impact_analyze', 'change_plan_generate', 'admin_action', 'data_export', 'data_delete');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)


def _drop_enum_types():
    """Drop PostgreSQL enum types."""
    op.execute("DROP TYPE IF EXISTS audit_action_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS template_category_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS risk_level_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS analysis_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS comment_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS comment_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS artifact_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS artifact_format_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS artifact_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS decision_priority_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS decision_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS decision_category_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS branch_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS project_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS project_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS workspace_role_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS plan_tier_enum CASCADE;")
