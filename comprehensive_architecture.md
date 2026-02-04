# Agentic Spec Builder - Comprehensive Architecture Document

**Document Version:** 1.0  
**Last Updated:** 2026-02-04  
**Status:** Complete Architecture Specification  
**Document Owner:** Engineering Leadership  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture Overview](#3-architecture-overview)
4. [Component Architecture](#4-component-architecture)
5. [User Journeys](#5-user-journeys)
6. [Data Architecture](#6-data-architecture)
7. [API Architecture](#7-api-architecture)
8. [Security Architecture](#8-security-architecture)
9. [Scalability and Performance](#9-scalability-and-performance)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Integration Patterns](#11-integration-patterns)
12. [Error Handling and Resilience](#12-error-handling-and-resilience)
13. [Monitoring and Observability](#13-monitoring-and-observability)
14. [Development and CI/CD Pipeline](#14-development-and-cicd-pipeline)
15. [Risk Assessment and Mitigations](#15-risk-assessment-and-mitigations)
16. [Future Roadmap](#16-future-roadmap)
17. [Appendices](#17-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides a comprehensive architectural blueprint for the Agentic Spec Builder platform—a system designed to eliminate ambiguity in software specifications through AI-driven interrogation, context management, and automated artifact generation.

### 1.2 Problem Statement

Software projects fail due to ambiguous requirements, undocumented assumptions, and misalignment between intent and implementation. Traditional PRD tools allow prose with hidden ambiguity, AI code generators hallucinate when specs are vague, and documentation tools lack enforcement of completeness. The Agentic Spec Builder addresses these challenges by:

- Capturing decisions through goal-oriented questioning
- Validating answers in real-time for contradictions
- Maintaining a structured decision graph with full provenance
- Generating formal artifacts (PRDs, schemas, tickets, tests) from decisions
- Supporting both greenfield (new projects) and brownfield (existing codebases) modes

### 1.3 Solution Overview

The platform consists of five AI agents working in concert:

- **Interrogation Agent**: Asks context-aware questions to resolve ambiguity
- **Context Memory Agent**: Maintains long-lived project state via vector embeddings
- **Specification Agent**: Generates formal artifacts from decisions
- **Validation Agent**: Checks consistency and detects contradictions
- **Delivery Agent**: Formats outputs for consumption by humans and AI agents

### 1.4 Key Architecture Principles

1. **Ambiguity Elimination**: Every decision is captured, validated, and traced
2. **Agent Coordination**: Specialized agents collaborate through a central orchestration layer
3. **Context Preservation**: Long-lived project state survives across sessions
4. **Tenant Isolation**: Multi-tenant architecture with workspace-level security
5. **Graceful Degradation**: System continues functioning during partial failures

### 1.5 Target Users

| Persona | Primary Need | Success Metric |
|---------|--------------|----------------|
| Founder/Product Owner | Fast translation of vision to actionable specs | Can hand specs to developers/AI agents with confidence |
| Engineering Lead/Architect | Precision, traceability, no surprises | Specs contain zero assumptions, all edge cases covered |
| AI Coding Agent Operator | Atomic, unambiguous instructions | Agent completes task on first try without clarification |
| Legacy System Maintainer | plans with rollback | Safe, scoped change Changes deployed without incidents |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Web Client Layer                                   │
│     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐      │
│     │ React SPA       │  │ Mobile Web      │  │ API Console         │      │
│     │ (Conversation)  │  │ (Responsive)     │  │ (Developer Tools)   │      │
│     └─────────────────┘  └─────────────────┘  └─────────────────────┘      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ HTTPS / WebSocket
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                      API Gateway / Load Balancer                             │
│         ┌─────────────────────────────────────────────────────────┐         │
│         │  • Rate Limiting  • Authentication  • Routing        │         │
│         │  • Request Validation  • Response Caching            │         │
│         └─────────────────────────────────────────────────────────┘         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                          Orchestration Layer                                 │
│         ┌─────────────────────────────────────────────────────────┐         │
│         │  • Agent Dispatch  • Workflow State Machine           │         │
│         │  • Rate Limiting  • Queue Management                  │         │
│         └─────────────────────────────────────────────────────────┘         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
┌─────────────▼────────────┐ ┌────▼─────────┐ ┌─────▼──────────────┐
│      Agent Layer          │ │  Auth Svc    │ │   File Storage     │
│  ┌───────────────────────┐ │ │              │ │   (S3/GCS/Blob)    │
│  │ Interrogation Agent   │ │ │  • JWT/Sess  │ │                     │
│  │ (Claude/GPT-4)        │ │ │  • OAuth    │ │  • User Uploads    │
│  └───────────────────────┘ │ │  • 2FA/SSO   │ │  • Generated       │
│  ┌───────────────────────┐ │ └─────────────┘ │  • Versioned        │
│  │ Specification Agent   │ │                 │ └─────────────────────┘
│  │ (Claude + OSS)        │ │                 │
│  └───────────────────────┘ │                 │
│  ┌───────────────────────┐ │                 │
│  │ Validation Agent     │ │                 │
│  │ (Claude)              │ │                 │
│  └───────────────────────┘ │                 │
│  ┌───────────────────────┐ │                 │
│  │ Delivery Agent        │ │                 │
│  │ (GPT-4 + OSS)         │ │                 │
│  └───────────────────────┘ │                 │
│  ┌───────────────────────┐ │                 │
│  │ Context Memory Agent  │ │                 │
│  │ (Vector DB + PG)      │ │                 │
│  └───────────────────────┘ │                 │
└────────────────────────────┼───────────────────────────────────────────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
┌─────────────▼───────┐ ┌────▼─────────┐ ┌───▼────────────────┐
│     Data Layer       │ │  Cache Layer │ │  Code Analysis     │
│  ┌─────────────────┐ │ │              │ │  (Brownfield)      │
│  │ PostgreSQL      │ │ │  • Redis     │ │  • Git Ingestion   │
│  │  • Decisions    │ │ │  • Sessions  │ │  • Multi-lang     │
│  │  • Projects     │ │ │  • Rate Lim  │ │  • Dependency      │
│  │  • Artifacts    │ │ │  • Jobs      │ │  • Static Analysis │
│  │  • Users/Worksp │ │ └─────────────┘ │                     │
│  └─────────────────┘ │                 │                     │
│  ┌─────────────────┐ │                 │                     │
│  │ Vector DB       │ │                 │                     │
│  │ (Embeddings)    │ │                 │                     │
│  └─────────────────┘ │                 │                     │
│  ┌─────────────────┐ │                 │                     │
│  │ Blob Storage    │ │                 │                     │
│  │ (Artifacts)     │ │                 │                     │
│  └─────────────────┘ │                 │                     │
└──────────────────────┼─────────────────┴─────────────────────┘
                       │
                       ▼
            ┌──────────────────────────┐
            │  External LLM Providers  │
            │  • Anthropic (Claude)   │
            │  • OpenAI (GPT-4)       │
            │  • Open-Source (Replicate│
            │    /Together)            │
            └──────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18 SPA, TypeScript, D3.js | Conversation interface, decision graph visualization |
| **API Gateway** | Kong/AWS ALB | Rate limiting, auth, routing |
| **Orchestration** | Python/FastAPI | Agent dispatch, workflow management |
| **Agents** | Python, LangChain | Interrogation, specification, validation, delivery |
| **Primary Database** | PostgreSQL 15+ | Structured data (decisions, projects, users) |
| **Vector Database** | Pinecone/Weaviate/PGVector | Semantic search embeddings |
| **Cache** | Redis 7+ | Sessions, rate limiting, job queues |
| **File Storage** | S3/GCS/Blob Storage | User uploads, generated artifacts |
| **Code Analysis** | Tree-sitter, Language Servers | Multi-language parsing |
| **LLM Providers** | Anthropic, OpenAI, Replicate | Text generation, embeddings |
| **Infrastructure** | Kubernetes, Terraform | Container orchestration, IaC |
| **Monitoring** | Prometheus, Grafana, ELK | Metrics, logging, tracing |

### 2.3 Deployment Model

The system follows a multi-environment deployment strategy:

| Environment | Purpose | Configuration |
|-------------|---------|---------------|
| **Development** | Local development | Docker Compose, mock LLM providers |
| **Staging** | Pre-production testing | Single-region cloud, test data |
| **Production** | Live service | Multi-AZ, high availability |

---

## 3. Architecture Overview

### 3.1 Architectural Patterns

#### 3.1.1 Microservices with Agent Specialization

The system employs a microservices architecture where each AI agent operates as an independent service with well-defined interfaces. This pattern provides:

- **Independent Scaling**: Agent services scale based on queue depth
- **Fault Isolation**: Agent failures don't cascade
- **Technology Flexibility**: Each agent can use optimal tooling
- **Team Autonomy**: Separate teams own different agents

#### 3.1.2 Event-Driven Architecture

Communication between components uses an event-driven model:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Event Bus (Redis Pub/Sub)                    │
├─────────────────────────────────────────────────────────────────┤
│  Events:                                                         │
│  • question_generated    • decision_captured                     │
│  • artifact_requested    • artifact_generated                   │
│  • validation_required   • validation_complete                   │
│  • conflict_detected     • branch_created                        │
│  • merge_requested       • merge_complete                        │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.1.3 CQRS (Command Query Responsibility Segregation)

The architecture separates read and write operations:

- **Commands** (writes): Answer questions, create projects, generate artifacts
- **Queries** (reads): List projects, get decisions, view artifacts

This separation enables optimized query paths and scalable read replicas.

### 3.2 Design Decisions Summary

| Category | Decision | Rationale |
|----------|----------|-----------|
| **Database** | PostgreSQL + Vector DB | Structured decisions need relational; context retrieval needs vector search |
| **Caching** | Redis | Sub-millisecond latency for sessions, rate limits, job queues |
| **LLM Abstraction** | Provider-agnostic interface | Multi-provider enables failover and cost optimization |
| **API Style** | REST + WebSocket | REST for CRUD, WebSocket for real-time updates |
| **Authentication** | JWT + OAuth 2.0 | Industry standard, supports SSO integration |
| **Deployment** | Kubernetes | Container orchestration, auto-scaling, self-healing |
| **Multi-tenancy** | Workspace-based isolation | Clean separation between organizations/teams |

---

## 4. Component Architecture

### 4.1 API Gateway

**Purpose**: Single entry point for all client requests

**Responsibilities**:
- Request routing to backend services
- Authentication and authorization enforcement
- Rate limiting per user/workspace
- Request validation and response transformation
- SSL/TLS termination
- Load balancing across service replicas

**Key Features**:
- Kong or AWS Application Load Balancer
- Custom auth middleware
- Redis-backed rate limiting
- Request/response logging

### 4.2 Orchestration Service

**Purpose**: Coordinate agent workflows and manage system state

**Responsibilities**:
- Agent dispatch based on request type
- Workflow state machine management
- Job queue management for async operations
- Rate limit enforcement
- Cross-agent communication

**State Machine**:
```
Project States:  active → paused → archived → completed
Artifact States: pending → generating → complete → stale → failed
Branch States:   active → merging → merged → conflict
```

### 4.3 Agent Layer

#### 4.3.1 Interrogation Agent

**Purpose**: Generate context-aware questions to resolve ambiguity

**Inputs**:
- Decision graph from Context Memory
- Project type (greenfield/brownfield)
- Target artifacts
- User's time investment setting

**Process**:
1. Load decision graph
2. Identify gaps via dependency analysis
3. Load question templates for project type
4. Generate next question with 3-4 concrete options
5. Adapt format (radio, checkboxes, form, free text)

**Outputs**:
- Atomic question with options
- Context/rationale
- Option to defer or use agent default

**LLM Configuration**:
- Primary: Claude Sonnet 4
- Fallback: GPT-4
- Temperature: 0.3 (controlled, precise outputs)

#### 4.3.2 Context Memory Agent

**Purpose**: Maintain long-lived project state across sessions

**Inputs**:
- Conversation turns
- Decisions (structured)
- Generated artifacts

**Process**:
1. Store structured decision graph
2. Embed all decisions in vector DB
3. When context window approached:
   - Retrieve relevant context via RAG
   - Reconstruct structured summary
4. Track dependencies between decisions

**Outputs**:
- Queryable decision graph
- Semantic search over decisions
- Context available to all agents

**Storage**:
- PostgreSQL: Structured decisions
- Vector DB: Decision embeddings (1536 dimensions)

#### 4.3.3 Specification Agent

**Purpose**: Convert decisions into formal artifacts

**Inputs**:
- Decision graph
- Artifact type (PRD, schema, API contract, tickets, architecture, tests, deployment_plan)
- Tech stack

**Process**:
1. Check dependencies: "Can we generate this artifact?"
2. If missing dependencies → list blockers
3. Generate using Claude (primary) + open-source (cost optimization)
4. Validate output against decision graph
5. Generate checkpoint every logical section
6. Return partial artifact on failure

**Outputs**:
- Generated artifact in requested format
- Metadata: generated_at, based_on_decisions[], tech_stack

**LLM Configuration**:
- Primary: Claude Opus 4 (high-complexity artifacts)
- Fallback: Claude Sonnet 4 + open-source (simple artifacts)

#### 4.3.4 Validation Agent

**Purpose**: Real-time validation and contradiction detection

**Inputs**:
- User answer
- Current decision graph

**Process**:
1. Parse answer
2. Check against existing decisions for contradictions
3. If conflict detected:
   - Flag immediately
   - Show conflicting decisions side-by-side
   - Ask user to resolve
4. If no conflict, store decision

**Outputs**:
- Decision confirmation
- Conflict resolution prompt

**Validation Rules**:
- Contradiction detection (LLM-based semantic analysis)
- Constraint validation (type, format, range)
- Dependency satisfaction (required decisions present)

#### 4.3.5 Delivery Agent

**Purpose**: Format artifacts for consumption

**Inputs**:
- Artifact
- Export format
- Target system

**Process**:
1. Detect artifact type
2. Generate requested formats
3. Validate output format validity

**Export Formats Supported**:

| Format | Type | Output |
|--------|------|--------|
| **PRD** | Markdown, HTML, PDF, JSON | Human-readable spec |
| **Database Schema** | SQL DDL, Mermaid ERD | Technical specification |
| **API Contracts** | OpenAPI 3.0, GraphQL SDL, gRPC Protobuf | Developer specification |
| **Tickets** | GitHub Issues, Linear, Markdown | Task management |
| **Architecture** | Mermaid C4 | Visual documentation |
| **Tests** | Gherkin, JUnit, pytest | Test specifications |
| **AI Agent Tasks** | Cursor, Claude Code, Devin, Copilot, Aider | Agent-compatible format |

### 4.4 Code Analysis Service (Brownfield)

**Purpose**: Analyze existing codebases for brownfield projects

**Responsibilities**:
- GitHub/GitLab OAuth integration
- Repository cloning (handle large repos)
- Multi-language parsing via Tree-sitter
- Dependency graph construction
- Architecture inference (C4 model)
- Breaking change detection

**Supported Languages**:
| Tier | Languages |
|------|-----------|
| **Primary** | TypeScript, JavaScript, Python, Java, Go |
| **Secondary** | C#, Rust, Ruby, PHP |
| **Community** | Kotlin, Swift, Scala (via plugins) |

**Analysis Outputs**:
- Language inventory with LOC counts
- Component inventory
- Dependency graph (Mermaid format)
- Architecture diagram (C4 model)
- Breaking change assessment

### 4.5 Auth Service

**Purpose**: User identity and access management

**Authentication Methods**:
| Method | Description | Use Case |
|--------|-------------|----------|
| **Email/Password** | bcrypt hashing, JWT sessions | Primary auth |
| **Magic Links** | One-time email links | Passwordless access |
| **OAuth 2.0** | Google, GitHub, Microsoft | Social/Enterprise login |
| **2FA (TOTP)** | Time-based one-time passwords | Enhanced security |
| **SSO** | SAML/OIDC (Okta, Azure AD, Google) | Enterprise |

**Role-Based Access Control**:
| Role | Permissions |
|------|-------------|
| **Owner** | All + delete workspace + billing |
| **Admin** | Manage members + all project actions |
| **Editor** | Create/edit projects + answer questions + generate artifacts |
| **Viewer** | Read-only access to projects + artifacts |

### 4.6 File Storage Service

**Purpose**: Handle user uploads and generated artifacts

**Storage Organization**:
```
/uploads/{workspace_id}/{project_id}/{timestamp}/{filename}
/artifacts/{workspace_id}/{project_id}/{artifact_id}/{version}/{format}.{extension}
```

**Access Control**:
- Presigned URLs with cryptographic signatures
- Configurable expiration (default: 1 hour download, 15 min upload)
- Public access disabled (always authenticated)

**Lifecycle**:
- Tiered storage (hot → cold → archive)
- Version retention (default: 10 versions)
- Deletion per workspace retention policy

---

## 5. User Journeys

### 5.1 Greenfield Project Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    JOURNEY: Founder → AI Agent Handoff                       │
└─────────────────────────────────────────────────────────────────────────────┘

1. WORKSPACE CREATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: "Create Workspace 'My Startup'"                                 │
   │  System: Workspace created, user assigned Owner role                     │
   │  → Time: < 2s                                                           │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
2. PROJECT INITIALIZATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: "New Project → Greenfield → 'Customer Portal'"                   │
   │  User: Selects template: "SaaS web application"                          │
   │  User: Time investment: "Standard (2 hours)"                             │
   │  User: Uploads: whiteboard sketch (PNG)                                   │
   │  System: Creates project, main branch, loads template questions          │
   │  → Time: < 2s for creation, first question in < 5s                     │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
3. QUESTIONING PHASE
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Interrogation Agent asks ~30-50 questions over 90-120 minutes:           │
   │                                                                         │
   │  Q1: "Who can create an account?"                                        │
   │      Options: [Anyone with email, Invite-only, Domain-restricted]       │
   │      User: "Anyone with email"                                          │
   │                                                                         │
   │  Q2: "Authentication method?"                                           │
   │      Options: [OAuth2, JWT, Magic links, SSO]                            │
   │      User: "Magic links"                                                │
   │                                                                         │
   │  ... (30+ questions covering: users, auth, data, APIs, UI, deployment)   │
   │                                                                         │
   │  Validation Agent validates each answer against previous decisions       │
   │  → Contradictions flagged immediately                                   │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
4. ARTIFACT GENERATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: "Generate PRD"                                                   │
   │  User: "Generate API Contract"                                          │
   │  User: "Generate Engineering Tickets"                                    │
   │                                                                         │
   │  Specification Agent:                                                  │
   │  - Checks dependencies (all decisions present?)                         │
   │  - Generates artifacts with checkpoints                                 │
   │  - Validates against decision graph                                     │
   │  → PRD: ~30s, API Contract: ~60s, Tickets: ~45s                        │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
5. EXPORT FOR AI AGENT
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: "Export → Claude Code format"                                     │
   │                                                                         │
   │  Delivery Agent generates:                                              │
   │  {                                                                      │
   │    "tasks": [                                                            │
   │      {"id": "TASK-001", "title": "Create User model", ...},            │
   │      {"id": "TASK-002", "title": "Implement magic links", ...}          │
   │    ]                                                                    │
   │  }                                                                      │
   │                                                                         │
   │  User: Downloads customer-portal-tickets.json                            │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
6. AGENT HANDOVER
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: `claude-code import customer-portal-tickets.json`                │
   │  AI Agent: Executes tasks with unambiguous specifications               │
   │  → Success metric: Agent completes on first try                         │
   └─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Brownfield Project Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              JOURNEY: Architect → Safe Change Plan                         │
└─────────────────────────────────────────────────────────────────────────────┘

1. PROJECT INITIALIZATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: "New Project → Brownfield → 'Add OAuth2'"                        │
   │  User: Codebase source: GitHub OAuth → selects repo                     │
   │  User: Change intent: "Add a feature"                                   │
   │  System: Clones repo, initiates static analysis                         │
   │  → Analysis: ~5 min for 200K LOC repo                                  │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
2. ARCHITECTURE DERIVATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Code Analysis Service:                                                 │
   │  - Parses code (AST-based, multi-language)                             │
   │  - Builds dependency graph                                             │
   │  - Infers architecture patterns                                        │
   │                                                                         │
   │  Output: Current-state architecture (C4 model)                         │
   │                                                                         │
   │  User: Agent asks confirmation questions:                               │
   │  "Is `/api` a separate service?" → User confirms                       │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
3. SCOPE QUESTIONS
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Interrogation Agent asks ~15-20 questions:                              │
   │                                                                         │
   │  Q1: "Which OAuth2 providers?"                                           │
   │      Options: [Google, GitHub, Microsoft, All]                          │
   │      User: "Google and GitHub"                                          │
   │                                                                         │
   │  Q2: "Token storage?"                                                   │
   │      Options: [Database, Redis, JWT (stateless)]                        │
   │      User: "PostgreSQL (existing DB)"                                   │
   │                                                                         │
   │  ... (additional questions about flows, scopes, error handling)          │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
4. IMPACT ANALYSIS
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Specification Agent + Code Analysis:                                    │
   │                                                                         │
   │  Files affected: 12 (3 create, 8 modify, 1 delete)                      │
   │  Risk level: High (auth logic change)                                   │
   │  Breaking changes: None (additive feature)                              │
   │  Tests affected: 23 (5 new, 18 modify)                                 │
   │                                                                         │
   │  Output: Impact Report with:                                            │
   │  - Files (create/modify/delete)                                         │
   │  - Dependency ripple (downstream components)                            │
   │  - Risk assessment per change                                          │
   │  - Breaking changes flagged                                            │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
5. CHANGE PLAN GENERATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Specification Agent generates:                                          │
   │                                                                         │
   │  1. Detailed Procedure Document (15 steps with code snippets)          │
   │  2. Git Workflow:                                                       │
   │     - Branch: feature/oauth2                                            │
   │     - Commits: 8                                                        │
   │     - PR: 1                                                             │
   │  3. Rollback Procedures (high-risk → included)                          │
   │  4. Feature Flag Strategy (gradual rollout)                            │
   │  5. Regression Test Requirements (Gherkin + manual QA)                    │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
6. TEAM COLLABORATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User: Exports zip with all artifacts                                   │
   │  User: Shares in Slack                                                   │
   │                                                                         │
   │  Teammate: "Comment: Missing CSRF protection"                          │
   │  Validation Agent: Re-opens relevant question                           │
   │  Product Owner: Answers (adds CSRF requirement)                         │
   │  Plan auto-updated with CSRF handling                                   │
   └─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Collaborative Refinement Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              JOURNEY: Product Owner + Engineering Lead                      │
└─────────────────────────────────────────────────────────────────────────────┘

1. INITIAL SPECIFICATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Product Owner creates greenfield project "Payment API"                 │
   │  PO answers 20 questions about business logic                          │
   │  PO generates PRD, shares with Eng Lead (invites to workspace)          │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
2. REVIEW AND COMMENT
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Eng Lead reviews PRD                                                   │
   │  Eng Lead: "Comment on 'Authentication' section"                      │
   │  Type: Issue                                                           │
   │  Text: "We need API key rotation, not just static keys"               │
   │                                                                         │
   │  Validation Agent detects:                                              │
   │  - Current spec says "static API keys"                                │
   │  - Issue requests "key rotation"                                       │
   │  → Triggers re-questioning                                            │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
3. RESOLUTION VIA BRANCHING
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Eng Lead: "Create branch: feature/improve-auth"                       │
   │  Eng Lead in branch:                                                    │
   │    - Changes decision: "Static API keys" → "Rotating API keys"         │
   │    - Regenerates API contract in branch                                 │
   │                                                                         │
   │  Eng Lead: "Request merge to main"                                     │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
4. MERGE AND VALIDATION
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  System: Compares branches, detects conflicts                          │
   │  Product Owner: Reviews diff (side-by-side)                            │
   │  Product Owner: "Approve merge"                                         │
   │                                                                         │
   │  Validation Agent:                                                      │
   │  - Re-validates consistency                                            │
   │  - Confirms no new contradictions                                      │
   │  → Merge complete                                                      │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
5. FINAL EXPORT
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Product Owner: "Export to GitHub Issues"                              │
   │  Development begins with validated, conflict-free specifications        │
   └─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Architecture

### 6.1 Data Model Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE ENTITIES                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ User                                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ user_id: UUID (PK)                                                     │
│ email: string (unique, indexed)                                        │
│ password_hash: string (nullable if OAuth-only)                        │
│ name: string                                                          │
│ totp_secret: string (encrypted, nullable)                             │
│ totp_enabled: boolean                                                  │
│ oauth_providers: jsonb [{provider, external_id}]                      │
│ created_at: timestamp                                                 │
│ last_login_at: timestamp                                              │
│ deleted_at: timestamp (nullable, soft-delete)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Workspace                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ workspace_id: UUID (PK)                                               │
│ name: string                                                          │
│ owner_user_id: UUID (FK → users.user_id)                               │
│ created_at: timestamp                                                 │
│ settings: jsonb {                                                     │
│   branch_protection: boolean,                                         │
│   validation_strictness: enum(minimal/standard/strict),              │
│   retention_policy: enum(free_90d/paid_indefinite/enterprise_custom) │
│ }                                                                     │
│ plan_tier: enum(free/pro/enterprise)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Project                                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ project_id: UUID (PK)                                                 │
│ workspace_id: UUID (FK → workspaces.workspace_id)                       │
│ name: string                                                          │
│ type: enum(greenfield/brownfield)                                     │
│ status: enum(active/paused/archived/completed)                        │
│ time_investment: enum(quick/standard/comprehensive)                   │
│ template_id: UUID (FK → templates.template_id, nullable)              │
│ created_by: UUID (FK → users.user_id)                                │
│ created_at: timestamp                                                 │
│ last_activity_at: timestamp                                           │
│ settings: jsonb {                                                      │
│   tech_stack: {backend_lang, frontend_lang, database, ...},           │
│   codebase_url: string (nullable, for brownfield),                  │
│   codebase_size_loc: int (nullable)                                  │
│ }                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ Branch              │ │ Decision            │ │ Artifact            │
├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
│ branch_id: UUID     │ │ decision_id: UUID   │ │ artifact_id: UUID   │
│ project_id: UUID    │ │ project_id: UUID    │ │ project_id: UUID    │
│ name: string        │ │ branch_id: UUID     │ │ branch_id: UUID    │
│ parent_branch_id    │ │ question_text: text │ │ type: enum(prd/     │
│ created_by: UUID    │ │ answer_text: text   │ │   schema/api_       │
│ created_at: ts      │ │ options: jsonb       │ │   contract/...)     │
│ merged_at: ts       │ │ category: enum      │ │ content: text/ref   │
│ is_protected: bool  │ │ is_assumption: bool │ │ format: enum        │
└─────────────────────┘ │ assumption_reason    │ │ version: int        │
                        │ dependencies: jsonb  │ │ based_on: jsonb     │
                        │ answered_by: UUID    │ │ generated_by: enum  │
                        │ answered_at: ts     │ │ generated_at: ts    │
                        │ version: int        │ │ is_stale: bool      │
                        │ is_locked: bool     │ │ tech_stack: jsonb   │
                        └─────────────────────┘ └─────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Artifact Version                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ version_id: UUID (PK)                                                 │
│ artifact_id: UUID (FK → artifacts.artifact_id)                         │
│ version_number: int                                                   │
│ content: text                                                          │
│ based_on_decisions: jsonb                                             │
│ created_at: timestamp                                                 │
│ created_by: UUID (FK → users.user_id, nullable)                        │
│ content_hash: SHA-256                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Database Schema Details

#### 6.2.1 Users Table

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    totp_secret TEXT,
    totp_enabled BOOLEAN DEFAULT FALSE,
    oauth_providers JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NULL;
```

**Constraints**:
- Email format validation via CHECK constraint
- Password hash uses bcrypt ($2b$12$...)
- OAuth providers stored as JSONB array

#### 6.2.2 Workspaces Table

```sql
CREATE TABLE workspaces (
    workspace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb,
    plan_tier TEXT DEFAULT 'free' CHECK (plan_tier IN ('free', 'pro', 'enterprise'))
);

CREATE INDEX idx_workspaces_owner ON workspaces(owner_user_id);
```

#### 6.2.3 Workspace Members Table

```sql
CREATE TABLE workspace_members (
    member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    invited_by UUID REFERENCES users(user_id),
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    joined_at TIMESTAMPTZ,
    
    UNIQUE (workspace_id, user_id)
);

CREATE INDEX idx_workspace_members_workspace ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_user ON workspace_members(user_id);
```

#### 6.2.4 Projects Table

```sql
CREATE TABLE projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('greenfield', 'brownfield')),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived', 'completed')),
    time_investment TEXT CHECK (time_investment IN ('quick', 'standard', 'comprehensive')),
    template_id UUID REFERENCES templates(template_id),
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_projects_workspace ON projects(workspace_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created_by ON projects(created_by);
```

#### 6.2.5 Branches Table

```sql
CREATE TABLE branches (
    branch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    parent_branch_id UUID REFERENCES branches(branch_id),
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    merged_at TIMESTAMPTZ,
    merged_by UUID REFERENCES users(user_id),
    is_protected BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_branches_project ON branches(project_id);
CREATE UNIQUE INDEX idx_branches_project_name ON branches(project_id, name);
```

#### 6.2.6 Decisions Table

```sql
CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES branches(branch_id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    options_presented JSONB DEFAULT '[]'::jsonb,
    category TEXT CHECK (category IN ('auth', 'database', 'api', 'ui', 'deployment', 'integration', 'security', 'performance', 'other')),
    is_assumption BOOLEAN DEFAULT FALSE,
    assumption_reasoning TEXT,
    dependencies JSONB DEFAULT '[]'::jsonb,
    answered_by UUID REFERENCES users(user_id),
    answered_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    is_locked BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_decisions_project ON decisions(project_id);
CREATE INDEX idx_decisions_branch ON decisions(branch_id);
CREATE INDEX idx_decisions_category ON decisions(category);
CREATE INDEX idx_decisions_answered_at ON decisions(answered_at);
```

#### 6.2.7 Artifacts Table

```sql
CREATE TABLE artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES branches(branch_id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('prd', 'schema', 'api_contract', 'tickets', 'architecture', 'tests', 'deployment_plan')),
    content TEXT,
    blob_storage_key TEXT,
    format TEXT NOT NULL CHECK (format IN ('markdown', 'json', 'yaml', 'sql', 'gherkin', 'mermaid', 'html', 'pdf')),
    version INTEGER DEFAULT 1,
    based_on_decisions JSONB DEFAULT '[]'::jsonb,
    generated_by_agent TEXT CHECK (generated_by_agent IN ('specification', 'delivery')),
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT FALSE,
    tech_stack JSONB
);

CREATE INDEX idx_artifacts_project ON artifacts(project_id);
CREATE INDEX idx_artifacts_branch ON artifacts(branch_id);
CREATE INDEX idx_artifacts_type ON artifacts(type);
CREATE INDEX idx_artifacts_is_stale ON artifacts(is_stale);
```

#### 6.2.8 Artifact Versions Table

```sql
CREATE TABLE artifact_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    based_on_decisions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(user_id),
    content_hash TEXT NOT NULL
);

CREATE INDEX idx_artifact_versions_artifact ON artifact_versions(artifact_id);
```

#### 6.2.9 Comments Table

```sql
CREATE TABLE comments (
    comment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    section VARCHAR(255),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    comment_type TEXT NOT NULL CHECK (comment_type IN ('question', 'issue', 'suggestion', 'approval')),
    text TEXT NOT NULL,
    parent_comment_id UUID REFERENCES comments(comment_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(user_id)
);

CREATE INDEX idx_comments_artifact ON comments(artifact_id);
CREATE INDEX idx_comments_parent ON comments(parent_comment_id);
```

#### 6.2.10 Conversation Turns Table

```sql
CREATE TABLE conversation_turns (
    turn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES branches(branch_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    agent TEXT NOT NULL CHECK (agent IN ('interrogation', 'specification', 'validation', 'delivery')),
    message TEXT NOT NULL,
    user_response TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversation_turns_project ON conversation_turns(project_id, branch_id, turn_number);
```

#### 6.2.11 Codebase Analyses Table

```sql
CREATE TABLE codebase_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    codebase_url TEXT NOT NULL,
    codebase_size_loc INTEGER,
    languages_detected JSONB DEFAULT '[]'::jsonb,
    architecture_derived TEXT,
    architecture_diagram TEXT,
    dependency_graph JSONB,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    analysis_duration_seconds INTEGER
);

CREATE INDEX idx_codebase_analyses_project ON codebase_analyses(project_id);
```

#### 6.2.12 Templates Table

```sql
CREATE TABLE templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('system', 'workspace', 'community')),
    workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE SET NULL,
    description TEXT,
    question_flow JSONB,
    default_tech_stack JSONB,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_templates_type ON templates(type);
```

#### 6.2.13 Audit Logs Table

```sql
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('login', 'create_project', 'answer_question', 'generate_artifact', 'export', 'create_branch', 'merge_branch', 'add_comment', 'modify_settings')),
    resource_type TEXT CHECK (resource_type IN ('project', 'artifact', 'decision', 'branch', 'comment', 'workspace')),
    resource_id UUID,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    details JSONB
);

CREATE INDEX idx_audit_logs_workspace ON audit_logs(workspace_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
```

### 6.3 Vector Database Schema

**Purpose**: Semantic search over decisions for context retrieval

**Collection/Index Structure**:

```
Collection: decisions_{workspace_id}

Document Structure:
{
    "decision_id": "uuid",
    "project_id": "uuid",
    "branch_id": "uuid",
    "decision_text": "Full question + answer text",
    "category": "auth|database|api|...",
    "keywords": ["keyword1", "keyword2", ...],
    "embedding": [1536-dimensional vector],
    "created_at": "timestamp"
}
```

**Index Configuration**:
- Metric: Cosine similarity
- Partitions: Per workspace_id for tenant isolation
- Reindexing: On decision creation and updates
- Monitoring: Query latency, index size

### 6.4 Redis Cache Strategy

**Session Storage**:
```
Key: sess:{session_id}
TTL: 7 days
Value: {
    "user_id": "uuid",
    "workspace_id": "uuid",
    "permissions": ["read", "write", ...],
    "last_activity": timestamp
}
```

**Rate Limiting**:
```
Key: ratelimit:{user_id}:{action_type}
TTL: 24 hours (daily reset) or action completion
Value: {
    "count": integer,
    "limit": integer
}
```

**Job Queues**:
```
Key: queue:{queue_name}
Type: Redis List
Values: {job_id, job_type, payload, created_at}
```

### 6.5 Blob Storage Organization

**User Uploads**:
```
s3://{bucket}/uploads/{workspace_id}/{project_id}/{timestamp}/{filename}
Metadata: {
    "mime_type": "...",
    "size_bytes": integer,
    "uploaded_by": "uuid",
    "uploaded_at": timestamp
}
```

**Generated Artifacts**:
```
s3://{bucket}/artifacts/{workspace_id}/{project_id}/{artifact_id}/{version}/{format}.{extension}
```

---

## 7. API Architecture

### 7.1 REST API Specification

**Base URL**: `https://api.agenticspecbuilder.com/v1`

**Authentication**: Bearer token (JWT in `Authorization` header)

#### 7.1.1 Authentication Endpoints

##### POST /auth/signup

**Purpose**: Create new user account

**Request**:
```json
{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "name": "Alice Smith"
}
```

**Response (201)**:
```json
{
    "user_id": "uuid",
    "email": "user@example.com",
    "token": "jwt_token",
    "workspaces": []
}
```

**Error Codes**:
- 400: Invalid email format or weak password
- 409: Email already exists
- 429: Rate limit exceeded

---

##### POST /auth/login

**Purpose**: Authenticate user

**Request**:
```json
{
    "email": "user@example.com",
    "password": "SecurePass123!"
}
```

**Response (200)**:
```json
{
    "token": "jwt_token",
    "user_id": "uuid",
    "workspaces": [
        {"workspace_id": "uuid", "name": "My Startup", "role": "owner"}
    ]
}
```

**Error Codes**:
- 401: Invalid credentials
- 429: Rate limit exceeded

---

##### POST /auth/logout

**Purpose**: Invalidate session

**Request**: (empty)

**Response (200)**:
```json
{"status": "logged_out"}
```

---

##### POST /auth/magic-link

**Purpose**: Request passwordless login

**Request**:
```json
{"email": "user@example.com"}
```

**Response (200)**:
```json
{"status": "magic_link_sent", "expires_in_minutes": 15}
```

---

##### POST /auth/verify-magic-link

**Purpose**: Complete magic link login

**Request**:
```json
{
    "token": "one_time_token",
    "expires_at": "2026-02-04T10:15:00Z"
}
```

**Response (200)**:
```json
{"token": "jwt_token", "user_id": "uuid"}
```

---

##### POST /auth/2fa/enable

**Purpose**: Enable two-factor authentication

**Response (200)**:
```json
{
    "secret": "JBSWY3DPEHPK3PXP",
    "qr_code": "data:image/png;base64,...",
    "backup_codes": ["code1", "code2", ...]
}
```

---

##### POST /auth/2fa/verify

**Purpose**: Verify 2FA code during login

**Request**:
```json
{"code": "123456"}
```

**Response (200)**:
```json
{"status": "verified", "token": "jwt_token"}
```

---

#### 7.1.2 Workspace Endpoints

##### POST /workspaces

**Purpose**: Create new workspace

**Request**:
```json
{
    "name": "My Startup"
}
```

**Response (201)**:
```json
{
    "workspace_id": "uuid",
    "name": "My Startup",
    "owner_user_id": "uuid",
    "created_at": "2026-02-04T10:00:00Z"
}
```

---

##### GET /workspaces

**Purpose**: List user's workspaces

**Response (200)**:
```json
{
    "workspaces": [
        {
            "workspace_id": "uuid",
            "name": "My Startup",
            "role": "owner",
            "member_count": 3,
            "project_count": 5
        }
    ]
}
```

---

##### GET /workspaces/{workspace_id}

**Purpose**: Get workspace details

**Response (200)**:
```json
{
    "workspace_id": "uuid",
    "name": "My Startup",
    "owner": {"user_id": "uuid", "name": "Alice"},
    "created_at": "2026-02-04T10:00:00Z",
    "settings": {
        "branch_protection": true,
        "validation_strictness": "standard",
        "retention_policy": "paid_indefinite"
    },
    "plan_tier": "pro"
}
```

---

##### PATCH /workspaces/{workspace_id}

**Purpose**: Update workspace settings

**Request**:
```json
{
    "name": "My Updated Startup",
    "settings": {
        "branch_protection": true,
        "validation_strictness": "strict"
    }
}
```

**Response (200)**:
```json
{"status": "updated"}
```

---

##### DELETE /workspaces/{workspace_id}

**Purpose**: Delete workspace (owner only)

**Response (200)**:
```json
{"status": "deleted", "deletion_scheduled_at": "2026-03-04T10:00:00Z"}
```

---

##### POST /workspaces/{workspace_id}/members

**Purpose**: Invite member to workspace

**Request**:
```json
{
    "email": "colleague@example.com",
    "role": "editor"
}
```

**Response (201)**:
```json
{
    "member_id": "uuid",
    "status": "invited",
    "invite_sent_to": "colleague@example.com"
}
```

---

##### GET /workspaces/{workspace_id}/members

**Purpose**: List workspace members

**Response (200)**:
```json
{
    "members": [
        {
            "user_id": "uuid",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "role": "owner",
            "joined_at": "2026-02-04T10:00:00Z"
        }
    ]
}
```

---

##### PATCH /workspaces/{workspace_id}/members/{user_id}

**Purpose**: Update member role

**Request**:
```json
{"role": "admin"}
```

**Response (200)**:
```json
{"status": "updated"}
```

---

##### DELETE /workspaces/{workspace_id}/members/{user_id}

**Purpose**: Remove member from workspace

**Response (200)**:
```json
{"status": "removed"}
```

---

#### 7.1.3 Project Endpoints

##### POST /projects

**Purpose**: Create new project

**Request (Greenfield)**:
```json
{
    "workspace_id": "uuid",
    "name": "Customer Portal",
    "type": "greenfield",
    "time_investment": "standard",
    "template_id": "uuid"
}
```

**Request (Brownfield)**:
```json
{
    "workspace_id": "uuid",
    "name": "Add OAuth2",
    "type": "brownfield",
    "codebase_url": "https://github.com/user/repo",
    "change_intent": "add_feature",
    "scope_selection": {
        "directories": ["src/auth", "src/api"]
    }
}
```

**Response (201)**:
```json
{
    "project_id": "uuid",
    "branch_id": "uuid",
    "status": "active",
    "next_question": {
        "question_id": "uuid",
        "text": "Who can create an account?",
        "options": [
            {"value": "anyone", "label": "Anyone with email"},
            {"value": "invite_only", "label": "Invite-only"},
            {"value": "domain", "label": "Anyone with @company.com"}
        ],
        "format": "radio",
        "context": "This determines user registration flow"
    }
}
```

---

##### GET /projects

**Purpose**: List workspace projects

**Query Parameters**:
- `status`: filter by status (active, paused, archived, completed)
- `type`: filter by type (greenfield, brownfield)
- `limit`: default 20
- `offset`: default 0

**Response (200)**:
```json
{
    "projects": [
        {
            "project_id": "uuid",
            "name": "Customer Portal",
            "type": "greenfield",
            "status": "active",
            "created_at": "2026-02-04T10:00:00Z",
            "last_activity_at": "2026-02-04T12:00:00Z",
            "decision_count": 25,
            "artifact_count": 3
        }
    ],
    "total": 10,
    "limit": 20,
    "offset": 0
}
```

---

##### GET /projects/{project_id}

**Purpose**: Get project details

**Response (200)**:
```json
{
    "project_id": "uuid",
    "name": "Customer Portal",
    "type": "greenfield",
    "status": "active",
    "time_investment": "standard",
    "template_id": "uuid",
    "created_by": {"user_id": "uuid", "name": "Alice"},
    "created_at": "2026-02-04T10:00:00Z",
    "last_activity_at": "2026-02-04T12:00:00Z",
    "settings": {
        "tech_stack": {
            "backend_lang": "python",
            "frontend_lang": "react",
            "database": "postgresql"
        }
    },
    "stats": {
        "decision_count": 25,
        "question_count": 28,
        "artifact_count": 3,
        "branch_count": 2
    }
}
```

---

##### PATCH /projects/{project_id}

**Purpose**: Update project

**Request**:
```json
{
    "status": "paused",
    "settings": {
        "tech_stack": {
            "backend_lang": "python",
            "frontend_lang": "react",
            "database": "postgresql",
            "cache": "redis"
        }
    }
}
```

**Response (200)**:
```json
{"status": "updated"}
```

---

##### DELETE /projects/{project_id}

**Purpose**: Delete project

**Response (200)**:
```json
{"status": "deleted"}
```

---

#### 7.1.4 Question and Answer Endpoints

##### GET /projects/{project_id}/questions/pending

**Purpose**: List pending questions

**Response (200)**:
```json
{
    "questions": [
        {
            "question_id": "uuid",
            "text": "Database technology?",
            "category": "database",
            "options": [
                {"value": "postgresql", "label": "PostgreSQL"},
                {"value": "mysql", "label": "MySQL"},
                {"value": "mongodb", "label": "MongoDB"}
            ],
            "format": "radio",
            "asked_at": "2026-02-04T10:30:00Z",
            "depends_on_decisions": []
        }
    ],
    "parked": []
}
```

---

##### POST /projects/{project_id}/answers

**Purpose**: Submit answer to question

**Request**:
```json
{
    "branch_id": "uuid",
    "question_id": "uuid",
    "answer": "postgresql"
}
```

**Response (200 - no contradiction)**:
```json
{
    "decision_id": "uuid",
    "contradiction_detected": false,
    "next_question": {
        "question_id": "uuid",
        "text": "Database connection pooling?",
        "options": [...],
        "format": "checkbox"
    }
}
```

**Response (200 - contradiction detected)**:
```json
{
    "contradiction_detected": true,
    "conflict": {
        "previous_decision": {
            "decision_id": "uuid",
            "question": "Require authentication?",
            "answer": "no"
        },
        "current_answer": "Users have profiles",
        "prompt": "Users can't have profiles without auth. Which is correct?"
    }
}
```

---

##### POST /projects/{project_id}/defer-question

**Purpose**: Defer question to "ask later"

**Request**:
```json
{
    "branch_id": "uuid",
    "question_id": "uuid"
}
```

**Response (200)**:
```json
{
    "status": "deferred",
    "next_question": {...}
}
```

---

##### POST /projects/{project_id}/parked/{question_id}

**Purpose**: Resurface parked question

**Response (200)**:
```json
{
    "question": {...}
}
```

---

#### 7.1.5 Branch Endpoints

##### POST /projects/{project_id}/branches

**Purpose**: Create feature branch

**Request**:
```json
{
    "name": "feature/improve-auth",
    "parent_branch_id": "uuid"
}
```

**Response (201)**:
```json
{
    "branch_id": "uuid",
    "name": "feature/improve-auth",
    "created_at": "2026-02-04T10:30:00Z"
}
```

---

##### GET /projects/{project_id}/branches

**Purpose**: List project branches

**Response (200)**:
```json
{
    "branches": [
        {
            "branch_id": "uuid",
            "name": "main",
            "is_protected": true,
            "created_at": "2026-02-04T10:00:00Z",
            "merged_at": null
        },
        {
            "branch_id": "uuid",
            "name": "feature/improve-auth",
            "parent_branch_id": "uuid",
            "is_protected": false,
            "created_at": "2026-02-04T10:30:00Z",
            "merged_at": null,
            "created_by": {"user_id": "uuid", "name": "Bob"}
        }
    ]
}
```

---

##### POST /projects/{project_id}/branches/{branch_id}/merge

**Purpose**: Merge branch to target

**Request**:
```json
{
    "target_branch_id": "uuid"
}
```

**Response (200 - no conflicts)**:
```json
{
    "status": "merged",
    "merged_at": "2026-02-04T10:35:00Z"
}
```

**Response (200 - conflicts)**:
```json
{
    "status": "conflicts",
    "conflicts": [
        {
            "decision_id": "uuid",
            "question": "Authentication method?",
            "main_answer": "JWT",
            "feature_answer": "OAuth2"
        }
    ]
}
```

---

##### POST /projects/{project_id}/branches/{branch_id}/resolve-conflicts

**Purpose**: Resolve merge conflicts

**Request**:
```json
{
    "resolutions": [
        {
            "decision_id": "uuid",
            "chosen_answer": "OAuth2"
        }
    ]
}
```

**Response (200)**:
```json
{
    "status": "conflicts_resolved",
    "ready_to_merge": true
}
```

---

#### 7.1.6 Decision Endpoints

##### GET /projects/{project_id}/decisions

**Purpose**: Retrieve decision graph

**Response (200)**:
```json
{
    "decisions": [
        {
            "decision_id": "uuid",
            "question": "Authentication method?",
            "answer": "OAuth2",
            "category": "auth",
            "dependencies": ["uuid1", "uuid2"],
            "answered_by": {"user_id": "uuid", "name": "Alice"},
            "answered_at": "2026-02-04T10:00:00Z",
            "is_assumption": false,
            "version": 1
        }
    ],
    "graph": {
        "nodes": [
            {"id": "uuid", "label": "Auth: OAuth2", "category": "auth"}
        ],
        "edges": [
            {"source": "uuid1", "target": "uuid", "label": "depends on"}
        ]
    },
    "statistics": {
        "total_decisions": 25,
        "by_category": {
            "auth": 5,
            "database": 4,
            "api": 8,
            "ui": 3,
            "deployment": 5
        }
    }
}
```

---

##### GET /projects/{project_id}/decisions/{decision_id}

**Purpose**: Get specific decision with history

**Response (200)**:
```json
{
    "decision_id": "uuid",
    "current_version": {
        "question": "Authentication method?",
        "answer": "OAuth2",
        "answered_by": {"user_id": "uuid", "name": "Alice"},
        "answered_at": "2026-02-04T10:00:00Z",
        "version": 1
    },
    "history": [
        {
            "version": 1,
            "answer": "OAuth2",
            "changed_by": {"user_id": "uuid", "name": "Alice"},
            "changed_at": "2026-02-04T10:00:00Z"
        }
    ]
}
```

---

##### PATCH /projects/{project_id}/decisions/{decision_id}

**Purpose**: Update decision (if not locked)

**Request**:
```json
{
    "answer": "OAuth2 + Google",
    "reasoning": "Adding Google as second OAuth provider"
}
```

**Response (200)**:
```json
{
    "decision_id": "uuid",
    "version": 2,
    "affected_artifacts": ["prd", "api_contract"]
}
```

---

##### POST /projects/{project_id}/decisions/{decision_id}/lock

**Purpose**: Lock decision (prevent changes)

**Response (200)**:
```json
{"status": "locked"}
```

---

#### 7.1.7 Artifact Endpoints

##### POST /projects/{project_id}/artifacts

**Purpose**: Generate artifact

**Request**:
```json
{
    "branch_id": "uuid",
    "type": "prd",
    "formats": ["markdown", "pdf", "html"],
    "tech_stack": {
        "backend_lang": "python",
        "frontend_lang": "react"
    }
}
```

**Response (202 - async)**:
```json
{
    "job_id": "uuid",
    "status": "generating",
    "estimated_seconds": 30
}
```

**Poll at**: `GET /jobs/{job_id}`

---

##### GET /jobs/{job_id}

**Purpose**: Check artifact generation status

**Response (200 - in-progress)**:
```json
{
    "job_id": "uuid",
    "status": "generating",
    "progress": 45,
    "message": "Generating API specifications..."
}
```

**Response (200 - complete)**:
```json
{
    "job_id": "uuid",
    "status": "complete",
    "artifact_id": "uuid",
    "download_urls": {
        "markdown": "https://...",
        "pdf": "https://...",
        "html": "https://..."
    }
}
```

**Response (200 - failed)**:
```json
{
    "job_id": "uuid",
    "status": "failed",
    "error": "LLM timeout",
    "partial_artifact_id": "uuid"
}
```

---

##### GET /projects/{project_id}/artifacts

**Purpose**: List project artifacts

**Response (200)**:
```json
{
    "artifacts": [
        {
            "artifact_id": "uuid",
            "type": "prd",
            "format": "markdown",
            "version": 3,
            "is_stale": false,
            "generated_at": "2026-02-04T12:00:00Z",
            "generated_by_agent": "specification"
        }
    ]
}
```

---

##### GET /artifacts/{artifact_id}

**Purpose**: Get artifact content

**Response (200)**:
```json
{
    "artifact_id": "uuid",
    "project_id": "uuid",
    "type": "prd",
    "content": "# Product Requirements Document\n\n...",
    "format": "markdown",
    "version": 3,
    "based_on_decisions": ["uuid1", "uuid2", ...],
    "generated_at": "2026-02-04T12:00:00Z",
    "is_stale": false
}
```

---

##### GET /artifacts/{artifact_id}/versions

**Purpose**: List artifact versions

**Response (200)**:
```json
{
    "versions": [
        {
            "version_id": "uuid",
            "version_number": 3,
            "created_at": "2026-02-04T12:00:00Z",
            "created_by": {"user_id": "uuid", "name": "Alice"}
        },
        {
            "version_id": "uuid",
            "version_number": 2,
            "created_at": "2026-02-04T11:30:00Z",
            "created_by": {"user_id": "uuid", "name": "Alice"}
        }
    ]
}
```

---

##### POST /artifacts/{artifact_id}/regenerate

**Purpose**: Regenerate artifact from decisions

**Response (202)**:
```json
{
    "job_id": "uuid",
    "status": "generating"
}
```

---

##### GET /artifacts/{artifact_id}/diff

**Purpose**: Get diff between versions

**Query Parameters**:
- `from_version`: 2
- `to_version`: 3

**Response (200)**:
```json
{
    "from_version": 2,
    "to_version": 3,
    "diff": "...",
    "changes": {
        "additions": 50,
        "deletions": 20,
        "modifications": 5
    }
}
```

---

##### POST /artifacts/{artifact_id}/rollback

**Purpose**: Rollback to previous version

**Request**:
```json
{"version_number": 2}
```

**Response (200)**:
```json
{
    "artifact_id": "uuid",
    "version": 4,
    "rolled_back_from": 3
}
```

---

##### POST /artifacts/{artifact_id}/export

**Purpose**: Export artifact in specific format

**Request**:
```json
{
    "format": "github_issues",
    "options": {
        "labels": ["backend", "high-priority"],
        "assignees": []
    }
}
```

**Response (200)**:
```json
{
    "export": [
        {
            "title": "Create User model",
            "body": "...",
            "labels": ["backend", "high-priority"]
        }
    ]
}
```

---

#### 7.1.8 Comment Endpoints

##### POST /artifacts/{artifact_id}/comments

**Purpose**: Add comment to artifact

**Request**:
```json
{
    "section": "line 45-60",
    "type": "issue",
    "text": "Missing CSRF protection for this endpoint"
}
```

**Response (201)**:
```json
{
    "comment_id": "uuid",
    "agent_action": "re_questioning",
    "new_question": {
        "question_id": "uuid",
        "text": "Should CSRF protection be added for API endpoints?",
        "options": [...]
    }
}
```

---

##### GET /artifacts/{artifact_id}/comments

**Purpose**: List artifact comments

**Response (200)**:
```json
{
    "comments": [
        {
            "comment_id": "uuid",
            "section": "Authentication section",
            "user": {"user_id": "uuid", "name": "Bob"},
            "comment_type": "issue",
            "text": "We need API key rotation",
            "replies": [...],
            "created_at": "2026-02-04T14:00:00Z",
            "resolved_at": null
        }
    ]
}
```

---

##### POST /comments/{comment_id}/resolve

**Purpose**: Mark comment as resolved

**Response (200)**:
```json
{"status": "resolved"}
```

---

#### 7.1.9 Codebase Analysis Endpoints (Brownfield)

##### POST /codebase/analyze

**Purpose**: Trigger brownfield analysis

**Request**:
```json
{
    "project_id": "uuid",
    "source": "github",
    "repo_url": "https://github.com/user/repo",
    "scope_selection": {
        "directories": ["src/auth", "src/api"]
    }
}
```

**Response (202)**:
```json
{
    "analysis_id": "uuid",
    "status": "cloning",
    "estimated_minutes": 5
}
```

---

##### GET /codebase/analyses/{analysis_id}

**Purpose**: Check analysis status and results

**Response (200 - in-progress)**:
```json
{
    "analysis_id": "uuid",
    "status": "analyzing",
    "progress": 45,
    "current_phase": "dependency_graph"
}
```

**Response (200 - complete)**:
```json
{
    "analysis_id": "uuid",
    "status": "complete",
    "codebase_url": "https://github.com/user/repo",
    "codebase_size_loc": 250000,
    "languages_detected": [
        {"language": "typescript", "loc_count": 150000},
        {"language": "python", "loc_count": 100000}
    ],
    "architecture_derived": "Microservices architecture with API gateway...",
    "architecture_diagram": "```mermaid\ngraph TD\n...\n```",
    "dependency_graph": {
        "nodes": [...],
        "edges": [...]
    },
    "analyzed_at": "2026-02-04T15:00:00Z",
    "analysis_duration_seconds": 285
}
```

---

##### GET /projects/{project_id}/impact-analysis

**Purpose**: Get impact analysis for proposed change

**Request**:
```json
{
    "change_description": "Add OAuth2 authentication",
    "affected_files": ["src/auth/oauth2.py", "src/api/users.py"]
}
```

**Response (200)**:
```json
{
    "impact_analysis_id": "uuid",
    "change_description": "Add OAuth2 authentication",
    "files": {
        "create": ["src/auth/providers/oauth2.py"],
        "modify": ["src/auth/handlers.py", "src/api/users.py", "tests/auth/"],
        "delete": []
    },
    "risk_assessment": {
        "overall": "high",
        "breaking_changes": [],
        "affected_features": ["User login", "API authentication"],
        "tests_affected": {
            "new_tests_needed": 5,
            "tests_to_modify": 18
        }
    },
    "downstream_dependencies": [
        {"file": "src/api/orders.py", "impact": "medium"}
    ],
    "migration_requirements": {
        "database": [],
        "api_contract": [],
        "configuration": ["Add OAuth2 provider credentials"]
    }
}
```

---

##### GET /projects/{project_id}/change-plan

**Purpose**: Get change plan for proposed change

**Response (200)**:
```json
{
    "change_plan_id": "uuid",
    "impact_analysis_id": "uuid",
    "git_workflow": {
        "branch": "feature/add-oauth2",
        "commit_sequence": [
            "feat: Add OAuth2 provider configuration",
            "feat: Implement OAuth2 login handler",
            "feat: Update user model for OAuth2",
            "feat: Add OAuth2 tests",
            "refactor: Update API authentication middleware",
            "feat: Add OAuth2 to settings UI",
            "docs: Update API documentation",
            "chore: Update dependencies"
        ],
        "pull_request": {
            "title": "feat: Add OAuth2 authentication",
            "body": "...",
            "labels": ["authentication", "feature"]
        }
    },
    "detailed_procedure": [
        {
            "step": 1,
            "description": "Create OAuth2 provider configuration",
            "code_snippet": "...",
            "rationale": "Define OAuth2 settings structure",
            "warnings": ["Ensure client_secret is stored securely"]
        }
    ],
    "rollback_procedure": [
        {
            "step": 1,
            "description": "Remove OAuth2 provider configuration",
            "code_snippet": "..."
        }
    ],
    "feature_flag_strategy": {
        "recommended": true,
        "implementation": "...",
        "rollout_percentage": 10
    },
    "regression_test_requirements": {
        "existing_tests": [...],
        "new_test_cases": [
            {
                "id": "TEST-OAUTH2-001",
                "title": "OAuth2 login with Google",
                "gherkin": "Given User is on login page\nWhen User clicks 'Login with Google'..."
            }
        ],
        "manual_qa_checklist": [...]
    }
}
```

---

### 7.2 WebSocket API

**Endpoint**: `wss://api.agenticspecbuilder.com/v1/ws`

**Authentication**: Token in initial handshake query parameter (`?token=...`)

#### 7.2.1 Connection Establishment

```
Client → Server:
GET /v1/ws?token={jwt_token}
Upgrade: websocket

Server → Client (success):
{
    "event": "connected",
    "connection_id": "uuid",
    "user_id": "uuid",
    "server_time": "2026-02-04T15:00:00Z"
}

Server → Client (error):
{
    "event": "error",
    "code": "401",
    "message": "Invalid or expired token"
}
```

#### 7.2.2 Subscription Management

**Subscribe to project**:
```json
{
    "event": "subscribe",
    "project_id": "uuid"
}
```

**Unsubscribe from project**:
```json
{
    "event": "unsubscribe",
    "project_id": "uuid"
}
```

**List subscriptions**:
```json
{"event": "list"}
```

**Response**:
```json
{
    "event": "subscriptions",
    "projects": ["uuid1", "uuid2"]
}
```

#### 7.2.3 Server-to-Client Events

**Question ready**:
```json
{
    "event": "question_ready",
    "project_id": "uuid",
    "question": {
        "question_id": "uuid",
        "text": "Database technology?",
        "options": [...],
        "format": "radio",
        "category": "database"
    }
}
```

**Answer submitted (collaboration)**:
```json
{
    "event": "answer_submitted",
    "project_id": "uuid",
    "question_id": "uuid",
    "decision_id": "uuid",
    "user_id": "uuid",
    "user_name": "Alice"
}
```

**Artifact progress**:
```json
{
    "event": "artifact_progress",
    "artifact_id": "uuid",
    "progress": 65,
    "message": "Generating API specifications..."
}
```

**Artifact complete**:
```json
{
    "event": "artifact_complete",
    "artifact_id": "uuid",
    "type": "prd",
    "download_urls": {
        "markdown": "https://...",
        "pdf": "https://..."
    }
}
```

**Comment added**:
```json
{
    "event": "comment_added",
    "artifact_id": "uuid",
    "comment": {
        "comment_id": "uuid",
        "user_name": "Bob",
        "comment_type": "issue",
        "section": "Authentication"
    }
}
```

**Branch created**:
```json
{
    "event": "branch_created",
    "project_id": "uuid",
    "branch": {
        "branch_id": "uuid",
        "name": "feature/improve-auth",
        "created_by": {"user_id": "uuid", "name": "Bob"}
    }
}
```

**Branch merged**:
```json
{
    "event": "branch_merged",
    "project_id": "uuid",
    "branch_id": "uuid",
    "target_branch_id": "uuid",
    "merged_by": {"user_id": "uuid", "name": "Alice"}
}
```

**Contradiction detected**:
```json
{
    "event": "contradiction_detected",
    "project_id": "uuid",
    "conflict": {
        "decision_id": "uuid",
        "question": "Require authentication?",
        "existing_answer": "no",
        "new_answer": "Users have profiles"
    }
}
```

#### 7.2.4 Client-to-Server Events

**Typing indicator**:
```json
{
    "event": "typing",
    "project_id": "uuid",
    "is_composing": true
}
```

**Heartbeat**:
```json
{
    "event": "heartbeat",
    "timestamp": "2026-02-04T15:00:00Z"
}
```

**Response**:
```json
{
    "event": "heartbeat_ack",
    "server_time": "2026-02-04T15:00:00Z"
}
```

---

### 7.3 AI Agent Export Formats

#### 7.3.1 Cursor Format (JSON)

```json
{
    "tasks": [
        {
            "id": "TASK-001",
            "title": "Create User model",
            "description": "Create a User model with email, name, and OAuth provider references",
            "files": [
                "src/models/user.ts"
            ],
            "acceptance_criteria": [
                "User model has email field (required, unique)",
                "User model has OAuth provider reference",
                "User model timestamps (created_at, updated_at)",
                "Index on email for fast lookups"
            ],
            "dependencies": [],
            "priority": "high",
            "estimated_effort": "2h"
        },
        {
            "id": "TASK-002",
            "title": "Implement magic link authentication",
            "description": "Implement passwordless login using time-limited magic links sent via email",
            "files": [
                "src/auth/magic-link.ts",
                "src/services/email.ts"
            ],
            "acceptance_criteria": [
                "Users can request magic link with email",
                "Magic link valid for 15 minutes",
                "One-time use only",
                "Rate limited to 3 requests per hour"
            ],
            "dependencies": ["TASK-001"],
            "priority": "high",
            "estimated_effort": "4h"
        }
    ],
    "metadata": {
        "project": "Customer Portal",
        "exported_at": "2026-02-04T15:00:00Z",
        "export_format": "cursor",
        "version": "1.0"
    }
}
```

#### 7.3.2 Claude Code Format (Markdown + YAML Frontmatter)

```yaml
---
task_id: AUTH-001
priority: high
estimated_effort: 2h
files: 
  - src/models/user.ts
  - src/types/auth.ts
depends_on: []
context: |
  This task is part of the Customer Portal authentication feature.
  Decision: Use magic links for passwordless authentication.
  Decision: Store tokens in PostgreSQL with 15-minute expiration.
---

## Objective

Create a User model with email, OAuth provider references, and authentication fields.

## Requirements

### Data Model

1. **User fields:**
   - `id`: UUID primary key
   - `email`: String (required, unique, indexed)
   - `name`: String (required)
   - `oauth_provider`: Enum (google, github, null)
   - `oauth_id`: String (nullable)
   - `created_at`: Timestamp
   - `updated_at`: Timestamp

2. **Indexes:**
   - Unique index on `(email)`
   - Index on `(oauth_provider, oauth_id)`

### Validation

- Email format validation (RFC 5322)
- Unique email constraint
- OAuth provider requires oauth_id

### Related Decisions

- DEC-001: Authentication method = Magic links
- DEC-002: Database = PostgreSQL

## Implementation Notes

Use Prisma schema syntax:

```prisma
model User {
  id             UUID   @id @default(uuid())
  email          String @unique
  name           String
  oauth_provider String?
  oauth_id       String?
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  @@index([oauth_provider, oauth_id])
}
```

## Testing

- Unit tests for email validation
- Integration test for unique constraint
- Mock OAuth provider for testing
```

#### 7.3.3 GitHub Issues Format (JSON)

```json
[
    {
        "title": "[Backend] Create User model",
        "body": "## Overview\n\nCreate a User model for the Customer Portal authentication system.\n\n## Requirements\n\n### Fields\n- `id`: UUID primary key\n- `email`: String (required, unique)\n- `name`: String (required)\n- `oauth_provider`: google | github | null\n- `oauth_id`: String (nullable)\n\n### Indexes\n- Unique index on email\n- Index on (oauth_provider, oauth_id)\n\n## Acceptance Criteria\n- [ ] User model created with all fields\n- [ ] Email validation implemented\n- [ ] Unique constraint on email\n- [ ] Migration script created\n- [ ] Tests added",
        "labels": ["backend", "enhancement", "auth"],
        "assignees": [],
        "milestone": "Authentication v1.0"
    },
    {
        "title": "[Backend] Implement magic link authentication",
        "body": "## Overview\n\nImplement passwordless login using time-limited magic links sent via email.\n\n## Requirements\n\n### Flow\n1. User enters email on login page\n2. System sends magic link to email\n3. User clicks link (valid 15 min)\n4. User redirected to dashboard\n\n### Technical\n- Token stored in database (15-min TTL)\n- One-time use only\n- Rate limited: 3 requests/hour/email\n\n## Acceptance Criteria\n- [ ] Magic link endpoint created\n- [ ] Email sending integration (SendGrid)\n- [ ] Token generation and validation\n- [ ] Rate limiting implemented\n- [ ] Tests added",
        "labels": ["backend", "feature", "auth", "high-priority"],
        "assignees": [],
        "milestone": "Authentication v1.0"
    }
]
```

#### 7.3.4 Linear Format (JSON)

```json
{
    "issues": [
        {
            "title": "Create User model",
            "description": "## Overview\n\nCreate a User model for authentication system.\n\n## Requirements\n- User model with email, name, OAuth fields\n- Unique email constraint\n- Index on OAuth provider",
            "priority": 1,
            "labelNames": ["Backend", "Auth"],
            "assigneeId": null,
            "cycleId": null
        },
        {
            "title": "Implement magic link authentication",
            "description": "## Overview\n\nImplement passwordless login via magic links.\n\n## Requirements\n- 15-minute token expiration\n- Rate limiting (3/hour)\n- Email integration",
            "priority": 1,
            "labelNames": ["Backend", "Auth", "Feature"],
            "assigneeId": null,
            "cycleId": null
        }
    ]
}
```

#### 7.3.5 Aider Format (YAML)

```yaml
tasks:
  - task_id: AUTH-001
    title: Create User model
    description: |
      Create a User model with email, name, and OAuth provider references.
      This model is the foundation for the authentication system.
    subtasks:
      - id: AUTH-001-1
        title: Define User interface/type
        status: pending
      - id: AUTH-001-2
        title: Create Prisma schema
        status: pending
      - id: AUTH-001-3
        title: Add email validation
        status: pending
      - id: AUTH-001-4
        title: Write unit tests
        status: pending
    dependencies: []
    implementation_notes: |
      - Use Prisma ORM for database interactions
      - Email validation using validator.js
      - Store OAuth IDs as nullable strings
    priority: high
    estimated_hours: 4

  - task_id: AUTH-002
    title: Implement magic link authentication
    description: |
      Implement passwordless login using time-limited magic links.
    subtasks:
      - id: AUTH-002-1
        title: Create token generation service
        status: pending
      - id: AUTH-002-2
        title: Implement email sending
        status: pending
      - id: AUTH-002-3
        title: Create login endpoint
        status: pending
      - id: AUTH-002-4
        title: Add rate limiting
        status: pending
    dependencies: ["AUTH-001"]
    implementation_notes: |
      - Use crypto.randomBytes() for token generation
      - Store tokens with created_at timestamp
      - Delete token after successful login
      - Use SendGrid for email sending
    priority: high
    estimated_hours: 8
```

---

## 8. Security Architecture

### 8.1 Authentication Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| **Email/Password** | bcrypt hashing (cost 12), JWT sessions | Primary authentication |
| **Magic Links** | One-time email links (15-min expiry) | Passwordless access |
| **OAuth 2.0** | Google, GitHub, Microsoft providers | Social/Enterprise login |
| **2FA (TOTP)** | Time-based one-time passwords | Enhanced security |
| **SSO** | SAML/OIDC (Okta, Azure AD, Google) | Enterprise deployment |

### 8.2 Password Requirements

- Minimum 8 characters
- Mixed uppercase and lowercase
- At least one number
- At least one special character
- bcrypt cost factor: 12

### 8.3 Session Management

```
JWT Token Claims:
{
    "user_id": "uuid",
    "email": "user@example.com",
    "workspace_id": "uuid",
    "permissions": ["read", "write", "admin"],
    "exp": 3600,        // 1 hour
    "iat": "timestamp"
}

Refresh Token:
- 7-day expiry
- Stored in HTTP-only cookie
- Single-device option available
- Blacklist on logout (Redis)
```

### 8.4 Role-Based Access Control

| Role | Workspaces | Projects | Decisions | Artifacts | Members |
|------|------------|----------|-----------|-----------|---------|
| **Owner** | All + Delete | All + Delete | All + Lock | All + Delete | All + Invite |
| **Admin** | All | All + Create | All | All + Generate | Invite + Manage |
| **Editor** | Read | Create + Edit | Answer + Create | Generate + Export | - |
| **Viewer** | Read | Read | Read | Read | - |

### 8.5 Data Encryption

**In Transit**:
- TLS 1.3 for all connections
- Certificate rotation (Let's Encrypt or cloud provider)

**At Rest**:
- AES-256 for PostgreSQL
- AES-256 for S3/GCS bucket encryption
- AES-256 for backups

**Key Management**:
- Production: AWS KMS / GCP Cloud KMS
- Development: Environment variables
- Rotation: 90 days (automatic in production)

### 8.6 Tenant Isolation

```
Workspace-Level Isolation:
1. Database: Row-level security (RLS) on all tables
2. Cache: Prefix keys with workspace_id
3. Vector DB: Collection per workspace
4. File Storage: Path prefix by workspace_id
5. API: Filter all queries by workspace_id from JWT
```

### 8.7 Security Headers

```
HTTP Security Headers:
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Content-Security-Policy: default-src 'self'
- Referrer-Policy: strict-origin-when-cross-origin
```

### 8.8 API Rate Limiting

| Tier | Questions/Day | Projects | Active Conversations | Artifact Gens/Day |
|------|---------------|----------|----------------------|-------------------|
| **Free** | 50 | 10 | 5 | 10 |
| **Pro** | 200 | 50 | 20 | 50 |
| **Enterprise** | Unlimited | Unlimited | Unlimited | Unlimited |

**Additional Limits**:
- 100 requests/minute per IP (DDoS protection)
- 10 MB upload per file
- 100 files per upload

### 8.9 Audit Logging

**Logged Events**:
- Authentication (login, logout, 2FA)
- Project operations (create, delete)
- Decision operations (answer, modify)
- Artifact operations (generate, export)
- Workspace operations (member invite, settings change)

**Retention**:
- Free tier: 30 days
- Paid tier: 1 year
- Enterprise: Indefinite

---

## 9. Scalability and Performance

### 9.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Question presentation | 3-5s (initial), 1-2s (cached) | P95 |
| Answer validation | < 500ms | P95 |
| Artifact generation | 30s (standard PRD), 2min (complex) | P95 |
| Decision graph render | < 3s for 1000 nodes | P95 |
| Context retrieval | < 500ms | P95 |
| Auth request | < 2s | P95 |

### 9.2 Horizontal Scaling

```
API Servers:
- Stateless design (any server handles any request)
- Session state in Redis
- Auto-scaling based on CPU (>70%) or request count
- Health checks for automatic failover

Agent Workers:
- Scale based on queue depth
- Maximum workers per queue to limit costs
- Queue monitoring for capacity planning

Database:
- Read replicas for query-heavy workloads
- Writes route to primary
- Connection pooling (PgBouncer)
```

### 9.3 Caching Strategy

| Cache Type | TTL | Invalidation |
|------------|-----|--------------|
| Project metadata | 1 hour | On modification |
| Recent decisions | 30 minutes | On decision change |
| Artifact summaries | 1 hour | On artifact regeneration |
| User sessions | 7 days | On logout |
| Rate limit counters | Daily reset | Auto |
| Query results (complex) | 5 minutes | On data change |

### 9.4 Database Sharding

**Sharding Strategy**: Workspace-based sharding

```
Shard Assignment:
- Consistent hashing on workspace_id
- Default shard for new workspaces
- Migration for load balancing

Cross-Shard Queries:
- Minimized through application-level joins
- Distributed transactions for necessary cases
- Read replicas per shard
```

---

## 10. Deployment Architecture

### 10.1 Kubernetes Architecture

```
Cluster Structure:
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                           │
├─────────────────────────────────────────────────────────────────┤
│  Namespace: production                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Ingress Controller (nginx/Traefik)                         ││
│  │ - TLS termination                                          ││
│  │ - SSL offload                                              ││
│  │ - DDoS protection                                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ API Gateway Deployment (3+ replicas)                        ││
│  │ - HPA: 3-50 replicas                                        ││
│  │ - Resources: 1-4 CPU, 1-8GB RAM                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Orchestration Service (2+ replicas)                         ││
│  │ - HPA: 2-20 replicas                                        ││
│  │ - Resources: 1-2 CPU, 2-4GB RAM                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐│
│  │ Agent Layer  │ │ Auth Svc     │ │ Code Analysis            ││
│  │ (auto-scale) │ │ (2+ reps)    │ │ (on-demand)              ││
│  └──────────────┘ └──────────────┘ └──────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Data Services                                               ││
│  │ - PostgreSQL (primary + 2 replicas)                        ││
│  │ - Redis Cluster (3 master + 3 replicas)                    ││
│  │ - Vector DB (Pinecone/Weaviate)                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Secrets: External (Vault/Secrets Manager)                      │
│  ConfigMaps: Environment-specific configurations                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Multi-AZ Deployment

```
Availability Zones:
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   AZ-1      │ │   AZ-2      │ │   AZ-3      │
├─────────────┤ ├─────────────┤ ├─────────────┤
│ API (2 reps)│ │ API (2 reps)│ │ API (1 rep) │
│ Agent (2)   │ │ Agent (2)   │ │ Agent (1)   │
│ PG Primary  │ │ PG Replica  │ │ PG Replica  │
│ Redis M     │ │ Redis Rep   │ │ Redis Rep   │
└─────────────┘ └─────────────┘ └─────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
                   Load Balancer
```

### 10.3 Blue-Green Deployment

```
Blue-Green Switch:
┌─────────────┐     ┌─────────────┐
│   Blue      │     │   Green     │
│  (current)  │     │  (new ver)  │
│    v1.0     │     │    v1.1     │
├─────────────┤     ├─────────────┤
│ Traffic →   │     │   Health    │
│             │     │   Check     │
└─────────────┘     └─────────────┘
                        │
                        ▼
                  Traffic Switch
                  (atomic cutover)
                        │
                        ▼
                 ┌─────────────┐
                 │   Green     │
                 │  (active)   │
                 └─────────────┘
```

### 10.4 Disaster Recovery

| Metric | Target | Strategy |
|--------|--------|----------|
| **RTO** | 15 minutes | Automated failover, runbooks |
| **RPO** | 5 minutes | Continuous WAL archiving |
| **Backup Frequency** | Continuous | WAL + daily snapshots |
| **Retention** | 30 days | Point-in-time recovery |
| **Geographic** | Cross-region | Replicated backups |

---

## 11. Integration Patterns

### 11.1 GitHub Integration

```
OAuth Flow:
1. User clicks "Connect GitHub"
2. Redirect to GitHub OAuth authorize page
3. User grants repo permissions
4. Callback receives authorization code
5. Exchange code for access token
6. Store encrypted token

Repository Operations:
- Clone: Authenticated API to avoid rate limits
- Webhook: Notify of repo changes (optional)
- Scope Selection: User selects specific repos
```

### 11.2 GitLab Integration

```
OAuth Flow: Same as GitHub, GitLab-specific
Self-hosted Support: Configure GitLab instance URL
Project Discovery: List available projects with group filtering
Visibility Rules: Respect project visibility settings
```

### 11.3 LLM Provider Integration

```
Provider Abstraction Layer:

┌─────────────────────────────────────────────────────────────┐
│                    Agent Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐│
│  │ Interrogation   │  │ Specification   │  │ Validation  ││
│  │ Agent           │  │ Agent           │  │ Agent       ││
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘│
│           │                    │                   │      │
│           └────────────────────┼───────────────────┘      │
│                               │                          │
│                    ┌──────────▼──────────┐               │
│                    │ LLM Provider Adapter │               │
│                    │ (Unified Interface)  │               │
│                    └──────────┬──────────┘               │
│                               │                          │
│         ┌─────────────────────┼─────────────────────┐    │
│         │                     │                     │    │
│  ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐│
│  │  Claude     │      │   GPT-4      │      │  Open-Source││
│  │ (Primary)   │      │  (Fallback)  │      │  (Cost Opt) ││
│  └─────────────┘      └─────────────┘      └─────────────┘│
└─────────────────────────────────────────────────────────────┘

Provider Selection:
- Primary: Claude Sonnet 4 (specification quality)
- Fallback: GPT-4 (provider outage)
- Cost optimization: Open-source models (Replicate/Together)
```

### 11.4 Email Integration

```
Email Providers: SendGrid (primary), AWS SES (fallback)
Transactional Emails:
- Magic links
- Workspace invitations
- Artifact notifications
- Comment notifications
Template-Based Sending:
- Consistent formatting
- Localization support
- Unsubscribe handling
Delivery Tracking:
- Bounce detection
- Spam complaint monitoring
```

### 11.5 File Storage Integration

```
S3-Compatible Storage:
- AWS S3 (primary)
- Google Cloud Storage (fallback)
- MinIO (development)

Multi-Part Uploads:
- Files > 100MB
- Progress tracking
- Resume capability

Presigned URLs:
- Upload URLs: 15-minute expiry
- Download URLs: 1-hour expiry
- Signature-based authentication
```

---

## 12. Error Handling and Resilience

### 12.1 Failure Modes

| Failure | Frequency | Impact | Handling |
|---------|-----------|--------|----------|
| **LLM Provider Timeout** | ~1% | Stalled generation | Retry 3x, fallback provider, queue for retry |
| **Database Connection Loss** | <0.01% | Cannot save | Retry with pool refresh, degraded mode |
| **Vector DB Unavailable** | Rare | Slow context | Fallback to full history, warn user |
| **Artifact Generation OOM** | <1% | Partial artifact | Checkpoint every section, return partial |
| **Codebase Clone Timeout** | <5% | Analysis blocked | Narrow scope, shallow clone |

### 12.2 Retry Strategies

```
Exponential Backoff:
- Initial delay: 1 second
- Maximum delay: 60 seconds
- Jitter: ±20% random
- Maximum attempts: 3

Retry Budget:
- User-facing: 5 attempts (patience)
- Background: 3 attempts (stability)
- Dead letter queue: Permanent failure capture
```

### 12.3 Circuit Breaker

```
Circuit Breaker States:
┌─────────┐     Failure threshold: 5 failures/minute
│  OPEN   │◄────────────────────────────────────────┐
│ (block) │                                             │
└────┬────┘                                           │
     │ Timeout: 60 seconds                            │
     ▼                                               │
┌─────────┐     Success: Close circuit                │
│  HALF   │◄────────────────────────────────────────┐
│  OPEN   │                                             │
│(test)   │                                             │
└────┬────┘                                           │
     │ Success                                       │
     ▼                                               │
┌─────────┐                                           │
│ CLOSED  │───────────────────────────────────────────┘
│(normal) │  Return to OPEN if failure
└─────────┘

Fallback Behaviors:
- Question gen: Return cached questions
- Artifact gen: Queue for later processing
- Context retrieval: Use simplified summary
```

### 12.4 Partial Success Handling

```
Artifact Generation:
┌─────────────────────────────────────────────────────────┐
│  Success Sections: Save immediately                      │
│  Failed Sections: Mark with "TODO: [reason]"            │
│  User Interface: Show completion percentage              │
│  Retry: Target specific failed sections                  │
└─────────────────────────────────────────────────────────┘

Merge Operations:
- Automatic rollback on validation failure
- User notification with error details
- Retry after conflict resolution

Codebase Analysis:
- Successful languages: Save immediately
- Failed languages: Error explanation
- User decision: Proceed or abort
```

---

## 13. Monitoring and Observability

### 13.1 Metrics Collection

```
Application Metrics:
- Request rate, latency (P50, P95, P99)
- Error rate by endpoint
- Active users/workspaces/projects
- Questions asked per project
- Time to first artifact
- Artifact regeneration frequency

LLM-Specific Metrics:
- Token consumption per project
- Provider latency
- Error rates by provider
- Model selection frequency

Infrastructure Metrics:
- CPU, Memory, Network per service
- Database connection pool usage
- Cache hit/miss rates
- Queue depth
- Storage capacity and IOPS
```

### 13.2 Dashboards

| Dashboard | Audience | Refresh | Content |
|----------|----------|---------|---------|
| **System Health** | SRE/Ops | 10s | Infrastructure status, error rates |
| **Application** | Engineers | 30s | Request rates, latencies, queue depth |
| **Business** | Product | 1m | User activity, project metrics |
| **Cost** | Finance/Ops | 1h | LLM spending by project/user |
| **SLAs** | Leadership | 5m | Target vs actual performance |

### 13.3 Logging

```
Structured Log Format:
{
    "timestamp": "2026-02-04T15:00:00Z",
    "level": "ERROR",
    "service": "orchestration",
    "request_id": "uuid",
    "user_id": "uuid",
    "workspace_id": "uuid",
    "action": "generate_artifact",
    "error": "LLM timeout",
    "trace_id": "uuid"
}

Log Levels:
- ERROR: Failures requiring attention
- WARN: Unexpected but handled gracefully
- INFO: Significant business events
- DEBUG: Detailed tracing (dev only)

Centralized Logging:
- CloudWatch (AWS)
- Stackdriver (GCP)
- ELK Stack (self-hosted)
```

### 13.4 Tracing

```
Distributed Tracing:
- Trace ID: Propagates across all services
- Span: Individual operation
- Parent Span: Orchestrates child spans

Critical Path Tracing:
- Question answering: Validation → Generation → Storage
- Artifact generation: Check deps → Generate → Validate
- Database queries: Slow query detection

Sampling:
- Production: 10% sampling (adjustable)
- Debug: 100% sampling (short-lived)
- Error traces: Always sampled
```

### 13.5 Alerting

```
Alert Rules:

Critical (PagerDuty):
- Error rate > 5%
- Service health check failure
- Database connection exhaustion

Warning (Slack):
- Latency > P95 target
- Cache hit rate < 80%
- Queue depth growing

Info (Email):
- Daily summary
- Weekly capacity report

Runbooks:
- Documented response procedures
- Post-incident review process
```

---

## 14. Development and CI/CD Pipeline

### 14.1 GitOps Workflow

```
Branch Strategy:
┌─────────────────────────────────────────────────────────────┐
│  Main Branch (protected)                                     │
│  - Direct commits forbidden                                  │
│  - Requires PR review                                        │
│  - Auto-deploy to production on merge                        │
│                                                              │
│  Feature Branches: feature/*                                 │
│  - Short-lived (< 1 week)                                   │
│  - Merge via PR                                              │
│                                                              │
│  Bugfix Branches: bugfix/*                                    │
│  - Hotfixes bypass feature branch                            │
│  - Fast-track PR review                                      │
│                                                              │
│  Chore Branches: chore/*                                      │
│  - Maintenance tasks                                         │
│  - Smaller PR review requirements                            │
└─────────────────────────────────────────────────────────────┘

Commit Messages: Conventional Commits
- feat: New feature
- fix: Bug fix
- docs: Documentation
- refactor: Code restructuring
- test: Tests
- chore: Maintenance
```

### 14.2 Automated Testing

```
Testing Pyramid:

                    ┌─────────────────┐
                    │   E2E Tests     │  (5%)
                    │  (Selenium/     │
                    │   Playwright)   │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │ Integration │   │ Integration │   │ Integration │
    │   Tests     │   │   Tests     │   │   Tests     │
    │    (20%)    │   │    (20%)    │   │    (20%)    │
    └─────────────┘   └─────────────┘   └─────────────┘
           │                 │                 │
           └─────────────────┴─────────────────┘
                             │
           ┌─────────────────┴─────────────────┐
           │                                   │
    ┌──────▼──────┐                   ┌──────▼──────┐
    │  Unit Tests │                   │  Unit Tests │
    │    (55%)   │                   │    (55%)    │
    └─────────────┘                   └─────────────┘

Coverage Requirements:
- Unit tests: 80% coverage
- Integration tests: 50% coverage
- Critical paths: 100% coverage
```

### 14.3 Code Quality

```
Static Analysis:
┌─────────────────────────────────────────────────────────────┐
│  Linting: ESLint (TypeScript), Ruff (Python)               │
│  - Enforce style rules                                     │
│  - Auto-fix on save                                        │
│                                                             │
│  Type Checking: TypeScript compiler                        │
│  - Strict mode                                              │
│  - No any types                                             │
│                                                             │
│  Security Scanning:                                        │
│  - Snyk/Dependabot for dependencies                        │
│  - Semgrep for code patterns                               │
│  - Secret detection (hardcoded keys)                       │
│                                                             │
│  Code Review:                                              │
│  - Minimum 1 reviewer for all changes                      │
│  - Automated review comments                                │
│  - Checklist: functionality, performance, security          │
└─────────────────────────────────────────────────────────────┘
```

### 14.4 CI/CD Pipeline

```
Pipeline Stages:

┌─────────────────────────────────────────────────────────────────┐
│ 1. Pull Request Pipeline (on every PR to main/feature)          │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Lint & Type Check                                        │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Unit Tests (coverage report)                             │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Security Scan (dependencies, secrets)                     │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Build Docker image                                       │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Push to registry (if all checks pass)                    │ │
│    └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 2. Merge Pipeline (on PR merge to main)                         │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Deploy to staging                                        │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Integration tests                                        │ │
│    └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Deploy to production (blue-green)                        │ │
│    └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 14.5 Artifact Promotion

```
Environment Promotion:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Development │ -> │   Staging   │ -> │ Production  │
│  (auto)     │    │  (auto)     │    │ (manual)    │
└─────────────┘    └─────────────┘    └─────────────┘
      │                 │                   │
      ▼                 ▼                   ▼
   Every push     Release candidate      Approved
                  to main                promotion

Image Promotion:
- Semantic versioning (MAJOR.MINOR.PATCH)
- Git tags trigger releases
- Image scanning before promotion
- Rollback capability for all versions
```

### 14.6 Infrastructure as Code

```
Terraform Modules:
┌─────────────────────────────────────────────────────────────┐
│  Core Modules:                                               │
│  ├── network/                                               │
│  │   ├── vpc.tf                                             │
│  │   ├── subnets.tf                                         │
│  │   └── security-groups.tf                                │
│  ├── database/                                              │
│  │   ├── postgres.tf                                        │
│  │   ├── redis.tf                                           │
│  │   └── vector-db.tf                                       │
│  ├── kubernetes/                                            │
│  │   ├── cluster.tf                                         │
│  │   ├── namespaces.tf                                      │
│  │   └── addons.tf                                          │
│  └── services/                                              │
│      ├── api-gateway.tf                                     │
│      ├── orchestration.tf                                   │
│      └── agents.tf                                          │
└─────────────────────────────────────────────────────────────┘

State Management:
- Remote state (S3 + DynamoDB locking)
- State locking for team collaboration
- Drift detection (terraform plan)
```

---

## 15. Risk Assessment and Mitigations

### 15.1 Risk Register

| Risk | Level | Impact | Mitigation |
|------|-------|--------|------------|
| **LLM Hallucination** | High | Incorrect specs | Validation against decision graph, human review |
| **Provider Dependency** | Medium | Service availability | Multi-provider architecture, caching |
| **Data Privacy** | Medium | Compliance violations | Encryption, access controls, audit logging |
| **Security** | Medium | Platform compromise | Security testing, WAF, incident response |
| **Operational** | Medium | Availability | HA architecture, monitoring, runbooks |
| **Cost Overrun** | Low | Financial impact | Rate limits, cost tracking, tiered pricing |

### 15.2 Mitigation Strategies

```
LLM Hallucination:
- Validate artifacts against decision graph
- Human-in-the-loop for critical artifacts
- User feedback for reporting hallucinations
- Confidence scoring on low-certainty generations
- Model selection: prefer lower-hallucination models

Provider Dependency:
- Claude (primary), GPT-4 (fallback), Open-source (cost)
- Caching common responses
- Contractual SLAs with providers
- Self-hosted option for enterprise

Data Privacy:
- Encryption at rest and in transit
- Role-based access controls
- Audit logging for all data access
- GDPR compliance (EU data residency option)
- Data processing agreements

Security:
- Regular penetration testing
- Dependency vulnerability scanning
- Input validation and sanitization
- WAF for attack filtering
- Incident response plan with SLA

Operational:
- Multi-AZ deployment
- Automated monitoring and alerting
- Documented runbooks
- Disaster recovery procedures
- Chaos engineering tests
```

---

## 16. Future Roadmap

### 16.1 Phase 1: MVP (Months 1-4)

**Goal**: Prove core value proposition (ambiguity → clarity)

**Scope**:
- Greenfield mode only
- Simple question flow (templates, no dynamic reasoning)
- Generate: PRD, basic tickets (markdown)
- Single user per project (no collaboration)
- Email/password auth only
- Download exports only (no Git integration)
- Basic security (HTTPS, password hashing, SQL injection prevention)
- US-only hosting
- Hard rate limits (50 questions/day, 10 projects)

**Success Criteria**:
- 100 users complete 1 project each
- 80% satisfaction ("would recommend")
- <5% hallucination rate

### 16.2 Phase 2: Collaboration & Quality (Months 5-7)

**Goal**: Enable teams, improve artifact quality

**Scope**:
- Workspaces & members (invite via email)
- Branching & merging (Git-style workflow)
- Comments on artifacts (structured feedback)
- Improved artifact generation (Claude + open-source hybrid)
- Export to GitHub Issues, Linear
- Magic links auth
- Decision graph visualization
- Auto-archiving (30 days)

**Success Criteria**:
- 50 teams (3+ members) using collaboration features
- 90% of merges successful without conflicts

### 16.3 Phase 3: Brownfield & Enterprise (Months 8-11)

**Goal**: Support legacy systems, attract enterprise

**Scope**:
- Brownfield mode (codebase ingestion, analysis, change plans)
- Multi-language support (JS, TS, Python, Java, Go, C#, PHP)
- Impact analysis & regression test requirements
- SSO (Google Workspace, Okta, Azure AD)
- 2FA (TOTP)
- Multi-region data residency (EU option)
- GDPR compliance
- Paid tier launch

**Success Criteria**:
- 20 brownfield projects completed
- 10 enterprise customers signed

### 16.4 Phase 4: Scale & Intelligence (Ongoing)

**Goal**: Handle large projects, smarter agents

**Scope**:
- Dynamic question generation (goal-oriented reasoning)
- Enhanced context management (RAG improvements)
- Templates (workspace-level, community marketplace)
- Self-hosted option (Docker/K8s)
- Advanced observability (full audit trail, reasoning traces)
- Cost optimization (smarter model routing)

---

## 17. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Artifact** | Formal specification document generated from the decision graph (PRD, schema, API contract, tickets, tests) |
| **Branch** | Isolated copy of a project enabling parallel exploration of alternative decisions |
| **Decision** | Captured answer to a question, stored in structured format with full provenance |
| **Decision Graph** | Structured representation of all decisions and their dependencies within a project |
| **Greenfield** | New project created without existing codebase context |
| **Brownfield** | Project initialized from an existing codebase requiring analysis |
| **Vector Database** | Database optimized for similarity search using embedding vectors |
| **RAG** | Retrieval-Augmented Generation - technique combining retrieval with LLM generation |
| **Checkpoint** | Saved intermediate state during artifact generation enabling resume after failures |
| **Staleness** | Condition when an artifact's source decisions have changed, requiring regeneration |
| **Tenant Isolation** | Architectural separation ensuring one workspace cannot access another's data |

### Appendix B: Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Engineering Specification | `specgenerator.md` | Detailed capability definitions |
| OpenAPI Specification | `openapi.yaml` | Complete API definitions |
| Database Schema | `pt_core_mvp_v1.yaml`, `qb_core_mvp_v1.yaml` | Entity relationship diagrams |
| Docker Compose | `docker-compose.yml` | Local development environment |
| CI/CD Pipeline | `ci.yml` | Automated testing and deployment |

### Appendix C: Compliance Matrix

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| **GDPR** | Data export, deletion, EU residency option | Privacy policy, DPA |
| **SOC 2** | Access controls, audit logging, encryption | Audit reports |
| **HIPAA** (optional) | Business Associate Agreement | Enterprise tier only |
| **PCI DSS** | No cardholder data stored | Architecture review |

### Appendix D: Error Codes Reference

| Code | Meaning | Resolution |
|------|---------|------------|
| 400 | Bad Request | Validate input format |
| 401 | Unauthorized | Re-authenticate |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Verify resource exists |
| 409 | Conflict | Resolve contradiction/conflict |
| 422 | Unprocessable Entity | Validate business rules |
| 429 | Rate Limited | Wait and retry |
| 500 | Internal Error | Contact support |
| 502 | Bad Gateway | Retry request |
| 503 | Service Unavailable | Retry later |

### Appendix E: Open Questions and Assumptions

#### E.1 Open Questions (Unresolved)

| ID | Question | Blocker Level | Resolution Target |
|----|----------|---------------|-------------------|
| OQ-001 | What is the acceptable cost per project? | Medium | Before pricing model finalization |
| OQ-002 | Should we support self-hosted deployment? | Low | Defer to Enterprise tier |
| OQ-003 | How to handle multi-language codebases with unsupported languages? | Low | Edge case handling |
| OQ-004 | Should artifact comments support rich media (screenshots, videos)? | Low | Nice-to-have, defer |
| OQ-005 | What's the maximum context window we can support? | Medium | Test with real projects |

#### E.2 Explicit Assumptions

| ID | Assumption | Basis | Risk | Validation |
|----|------------|-------|------|------------|
| ASM-001 | LLM hallucination rate <5% | Industry benchmarks for Claude/GPT-4 | High | Track user-reported hallucinations in beta |
| ASM-002 | GitHub/GitLab cover 95% of brownfield use cases | Market share data | Low | Survey beta users |
| ASM-003 | Users tolerate 30s artifact generation | Similar tools (Notion AI, GitHub Copilot) | Medium | Track "cancel generation" rate |
| ASM-004 | Static analysis sufficient for brownfield derivation | 80% of systems have clear structure | Medium | Test on diverse repos in beta |
| ASM-005 | Email-based invites acceptable for MVP | Standard practice | Low | Enterprise customers request SSO |
| ASM-006 | Decision graph visualization scales to 1000 nodes | D3.js capabilities | Medium | Test with large projects |
| ASM-007 | Users resolve merge conflicts manually (no AI mediation) | Git workflow familiarity | Low | Track conflict resolution time |
| ASM-008 | Vector DB (Pinecone/Weaviate) is reliable | Managed services have 99.9% uptime | Low | Monitor downtime |
| ASM-009 | Users trust AI-generated test cases | Growing AI acceptance in dev tools | Medium | Track test case adoption rate |
| ASM-010 | Industry best practices acceptable defaults for "decide for me" | Most users follow conventions | Low | Track "change default" rate |

### Appendix F: Implementation Readiness Checklist

#### F.1 Fully Specified Components

| Component | Status | Notes |
|-----------|--------|-------|
| Problem Definition | ✅ Complete | Clear, measurable objectives |
| User Personas | ✅ Complete | Primary, secondary, system actors |
| Core Capabilities | ✅ Complete | 22 atomic capabilities with triggers, inputs, outputs |
| User Journeys | ✅ Complete | Greenfield, brownfield, collaboration, recovery |
| System Architecture | ✅ Complete | Components, responsibilities, data flow |
| Data Model | ✅ Complete | Entities, relationships, constraints, lifecycle |
| REST API | ✅ Complete | All endpoints defined |
| WebSocket API | ✅ Complete | Real-time events specified |
| Security Architecture | ✅ Complete | Auth, encryption, tenant isolation |
| Deployment Architecture | ✅ Complete | Kubernetes, multi-AZ, disaster recovery |

#### F.2 Requires Validation

| Item | Status | Validation Method |
|------|--------|-------------------|
| LLM Hallucination Rate | ⚠️ <5% assumed | Measure in beta |
| Latency Targets | ⚠️ TBD | Measure real usage, set after MVP |
| Cost Per Project | ⚠️ TBD | Measure token usage |
| Context Window Limits | ⚠️ TBD | Test with large projects |
| Decision Graph UX at Scale | ⚠️ TBD | Test with >500 nodes |
| Artifact Generation Quality | ⚠️ TBD | User feedback iteration |
| Brownfield Architecture Accuracy | ⚠️ TBD | Test on diverse repos |

#### F.3 Blocks Development

| Blocker | Status | Owner |
|---------|--------|-------|
| LLM Provider API Keys | 🚫 Required | DevOps |
| Database Schema Finalized | 🚫 Required | Backend Lead |
| Decision Graph Structure | 🚫 Required | Backend Lead |
| Agent Orchestration Protocol | 🚫 Required | Architecture Team |
| Export Format Schemas | 🚫 Required | Backend Lead |

#### F.4 Can Be Parallelized

| Track | Components | Dependencies |
|-------|------------|--------------|
| **Track A (Backend Core)** | Auth, Workspace, Project Management, Decision Graph | None |
| **Track B (Agent System)** | Interrogation, Context Memory, Specification, Validation, Delivery | Track A (partial) |
| **Track C (Brownfield)** | Codebase Ingestion, Static Analysis, Impact Analysis | Track A, Track B |
| **Track D (Frontend)** | React UI, WebSocket, Graph Visualization | Track A (API contracts) |
| **Track E (Infrastructure)** | Cloud Setup, Database, Monitoring | None |

### Appendix G: Maintenance and Operational Tasks

#### G.1 Daily Tasks

| Task | Responsible | Acceptance Criteria |
|------|--------------|---------------------|
| Database backup | Automated | Full backup completes, 30-day retention verified |
| Integrity checks | Automated | Orphaned decisions, artifact versions validated |
| Error log review | SRE | Critical errors flagged and addressed |
| LLM provider health check | Automated | All providers operational |

#### G.2 Weekly Tasks

| Task | Responsible | Acceptance Criteria |
|------|--------------|---------------------|
| Slow query analysis | Database Admin | Queries >1s optimized or explained |
| Audit log cleanup | Automated | Retention policy enforced |
| Cost review (LLM tokens) | Finance/Ops | Spending within budget |
| Security dependency scan | Security | No critical vulnerabilities |

#### G.3 Monthly Tasks

| Task | Responsible | Acceptance Criteria |
|------|--------------|---------------------|
| Security patches | DevOps | All dependencies updated |
| Secret rotation | DevOps | Keys rotated per policy |
| Rate limit adjustment | Product | Limits tuned based on usage |
| Capacity planning review | Architecture | Resources scaled as needed |

#### G.4 Quarterly Tasks

| Task | Responsible | Acceptance Criteria |
|------|--------------|---------------------|
| Load testing | QA/SRE | System handles 10x user growth |
| Disaster recovery drill | SRE | Restore from backup validated |
| Architecture review | Engineering | Document updates completed |
| User feedback synthesis | Product | Insights incorporated into roadmap |

### Appendix H: Decision History and Change Tracking

#### H.1 Decision Versioning

| Field | Description |
|-------|-------------|
| `decision_id` | Unique identifier (UUID) |
| `version` | Integer, incremented on each change |
| `previous_version` | Reference to prior version |
| `changed_by` | User who made the change |
| `changed_at` | Timestamp of change |
| `change_reason` | Explanation for modification |
| `content_hash` | SHA-256 of decision content |

#### H.2 Change Detection

| Trigger | Action |
|---------|--------|
| Decision modified | Create new version, update `based_on_decisions` in affected artifacts |
| Artifact regenerated | Create new version, mark previous as stale |
| Branch merged | Propagate decisions to target branch |

#### H.3 Audit Trail

All changes are logged to `audit_logs` table:

```sql
CREATE TABLE decision_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decisions(decision_id),
    version INTEGER NOT NULL,
    previous_content JSONB,
    new_content JSONB,
    changed_by UUID REFERENCES users(user_id),
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    change_reason TEXT,
    change_type TEXT CHECK (change_type IN ('create', 'update', 'merge', 'rollback'))
);

CREATE INDEX idx_decision_history_decision ON decision_history(decision_id);
```

### Appendix I: Brownfield Analysis Patterns

#### I.1 Supported Languages and Analysis Depth

| Tier | Languages | Analysis Type | LOC Limit |
|------|-----------|---------------|-----------|
| **Primary** | TypeScript, JavaScript, Python, Java, Go | Full AST + type-aware |
| **Secondary** | C#, Rust, Ruby, PHP | AST + heuristic inference |
| **Community** | Kotlin, Swift, Scala | AST (plugins) |

#### I.2 Analysis Phases

| Phase | Duration | Output |
|-------|----------|--------|
| **Phase 1: Cloning** | 1-5 min | Repository contents |
| **Phase 2: Language Detection** | 30s | Language inventory |
| **Phase 3: AST Parsing** | 2-5 min | Abstract syntax trees |
| **Phase 4: Dependency Mapping** | 2-5 min | Import/export graph |
| **Phase 5: Architecture Inference** | 1-3 min | C4 model (LLM-assisted) |
| **Phase 6: Validation** | 30s | User confirmation UI |

#### I.3 Large Repository Handling

| Scenario | Strategy |
|----------|----------|
| >500K LOC | Prompt user to narrow scope |
| >1GB repo | Shallow clone (last 100 commits) |
| Multi-module | Analyze each module separately |
| Monorepo | Parse workspace configuration |

---

**Document Status**: Complete  
**Next Review Date**: Upon completion of Phase 1 implementation  
**Document Owner**: Engineering Leadership  
**Last Major Update**: 2026-02-04  
**Version**: 1.0  

---

*This document is the authoritative source for the Agentic Spec Builder architecture. All implementation decisions should align with the specifications outlined herein. For questions or clarifications, contact Engineering Leadership.*
