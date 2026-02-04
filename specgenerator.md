# ENGINEERING SPECIFICATION: AGENTIC SPEC BUILDER

**Document Version:** 1.0  
**Last Updated:** 2026-02-04  
**Status:** Engineering Ready (with flagged assumptions)

---

## 1. PROBLEM DEFINITION

### 1.1 Core Problem
Software projects fail due to ambiguous requirements, undocumented assumptions, and misalignment between intent and implementation. This manifests as:
- Wasted engineering cycles building wrong features
- AI coding agents producing incorrect code from fuzzy specs
- Legacy systems too risky to modify due to lack of documentation
- Teams stuck in endless clarification loops

### 1.2 Who Experiences It
**Primary:**
- Founders/Product Owners (ideas without execution clarity)
- Engineering Leads/Architects (need precision, hate assumptions)
- AI Coding Agent Operators (require atomic, unambiguous instructions)
- Legacy System Maintainers (fear brittle systems, need safe change plans)

**Secondary:**
- Development teams consuming specs
- QA teams needing test criteria
- DevOps teams deploying systems

### 1.3 Why Existing Solutions Fail
- **Traditional PRD tools:** Allow prose with hidden ambiguity
- **AI code generators:** Hallucinate when specs are vague
- **Documentation tools:** No enforcement of completeness
- **Project management tools:** Track work, don't validate requirements

### 1.4 Non-Goals
- ❌ Not a code generator (except test scaffolds, migrations)
- ❌ Not a project management tool (no task tracking, time tracking, reporting)
- ❌ Not a replacement for engineering judgment
- ❌ Not a "one prompt → full app" toy
- ❌ Not a deployment platform
- ❌ Not a collaboration/chat tool (Slack alternative)

---

## 2. USERS & PERSONAS

### 2.1 Primary Users

**Founder / Product Owner**
- **Capabilities:** Domain knowledge, business goals
- **Constraints:** Limited technical depth, impatient with process
- **Needs:** Fast translation of vision to actionable specs
- **Success metric:** Can hand specs to developers/AI agents with confidence

**Engineering Lead / Architect**
- **Capabilities:** Deep technical knowledge, system design expertise
- **Constraints:** Time-starved, drowning in meetings
- **Needs:** Precision, traceability, no surprises
- **Success metric:** Specs contain zero assumptions, all edge cases covered

**AI Coding Agent Operator**
- **Capabilities:** Knows how to use Cursor, Devin, Claude Code, etc.
- **Constraints:** Agents fail catastrophically on fuzzy input
- **Needs:** Atomic, unambiguous instructions in agent-compatible format
- **Success metric:** Agent completes task on first try without clarification

**Legacy System Maintainer**
- **Capabilities:** Knows the old system, fears breaking it
- **Constraints:** No documentation, brittle tests, production incidents expensive
- **Needs:** Safe, scoped change plans with rollback procedures
- **Success metric:** Changes deployed without incidents

### 2.2 Secondary Users

**Developer (implementation)**
- Consumes specs, builds features
- Needs: Clear acceptance criteria, no ambiguity

**QA Engineer**
- Writes and executes tests
- Needs: Test cases, expected behaviors

**DevOps Engineer**
- Deploys and operates systems
- Needs: Infrastructure requirements, deployment plans

### 2.3 System Actors

**Interrogation Agent** (asks questions)  
**Context Memory Agent** (maintains state)  
**Specification Agent** (generates artifacts)  
**Validation Agent** (checks consistency)  
**Delivery Agent** (formats outputs)  

**External Systems:**
- LLM providers (Anthropic, OpenAI, open-source via Replicate/Together)
- Git hosting (GitHub, GitLab) for codebase ingestion
- Vector database for RAG
- Blob storage for uploaded files

---

## 3. FUNCTIONAL SCOPE

### 3.1 Core Capabilities

#### CAP-001: Project Creation (Greenfield)
**Description:** Initialize new project from high-level idea  
**Trigger:** User clicks "New Project" → selects "Greenfield"  
**Inputs:**
- Project name
- Optional: description, supporting docs (text, images, audio)
- Time investment preference: Quick (30min), Standard (2hr), Comprehensive (unlimited)
- Optional: project template selection

**Outputs:**
- Active project with initial context
- First set of questions from Interrogation Agent

**Success Criteria:**
- Project created in <2s
- First question appears within 5s
- All uploaded files parsed and indexed

**Failure Cases:**
- Invalid file types → reject with error
- File size exceeds limit → reject with error
- LLM provider unavailable → queue project, notify user

---

#### CAP-002: Project Creation (Brownfield)
**Description:** Initialize project from existing codebase  
**Trigger:** User clicks "New Project" → selects "Brownfield" → provides codebase  
**Inputs:**
- Project name
- Codebase source: GitHub OAuth, GitLab OAuth, zip upload, or Git URL
- Scope selection (optional): specific directories/files to analyze
- Change intent: add feature, optimize, fix bug, refactor, migrate, modernize

**Outputs:**
- Codebase ingested and analyzed
- Current-state architecture (derived from code)
- Initial questions about change scope

**Success Criteria:**
- Codebase cloned/uploaded successfully
- Static analysis completes within 5 min for repos <500K LOC
- First question appears after analysis

**Failure Cases:**
- Authentication fails → prompt re-auth
- Repo too large (exceeds infrastructure limits) → suggest scoping
- Unsupported language detected → notify, proceed with supported languages only
- Analysis timeout → offer manual scope narrowing

---

#### CAP-003: Interrogation (Question Generation)
**Description:** Agent asks questions to resolve ambiguity  
**Trigger:** Project created, or decision changed, or artifact requested  
**Inputs:**
- Current project context (decisions, conversation history)
- Target artifacts (PRD, schema, tickets, etc.)
- User's time investment setting

**Process:**
1. Load decision graph from Context Memory Agent
2. Use goal-oriented reasoning: "What's needed for target artifacts?"
3. Load question templates for project type
4. Identify gaps via dependency analysis
5. Generate next question with 3-4 concrete options
6. Adapt format: radio, checkboxes, form, or free text (LLM decides per question)

**Outputs:**
- Atomic question with options
- Context/rationale for why question matters
- Option to defer ("ask later") or default ("decide for me")

**Success Criteria:**
- Question presented within 3-5s
- Options are mutually exclusive and exhaustive
- No duplicate questions

**Failure Cases:**
- LLM timeout → retry with simpler prompt
- No valid next question → mark project as "ready for artifacts"
- User closes browser mid-question → auto-save state

---

#### CAP-004: Answer Validation & Contradiction Detection
**Description:** Real-time validation of user answers  
**Trigger:** User submits answer  
**Inputs:**
- User answer
- Current decision graph

**Process:**
1. Parse answer
2. Check against existing decisions for contradictions
3. If conflict detected:
   - Flag immediately
   - Show conflicting decisions side-by-side
   - Ask user to resolve: "You said X earlier, now Y. Which is correct?"
4. If no conflict, store decision

**Outputs:**
- Confirmed decision added to graph
- Or conflict resolution prompt

**Success Criteria:**
- Validation completes in <1s
- Contradictions caught before allowing progress

**Failure Cases:**
- Ambiguous answer → ask clarification
- Validation Agent unavailable → queue validation, allow temporary progress with warning

---

#### CAP-005: Context Memory Management
**Description:** Maintain long-lived project state across sessions  
**Trigger:** Continuous (every question, answer, decision)  
**Inputs:**
- Conversation turns
- Decisions
- Artifacts generated

**Process:**
1. Store structured decision graph (not raw text)
2. Embed all decisions in vector DB for semantic retrieval
3. When context window limit approached:
   - Retrieve relevant context via RAG
   - Reconstruct structured summary from decision graph
4. Track dependencies between decisions

**Outputs:**
- Queryable decision graph
- Context available to all agents

**Success Criteria:**
- Context retrieval <500ms
- No decision loss across sessions
- Supports projects with >1000 decisions

**Failure Cases:**
- Vector DB unavailable → fallback to full conversation history (may hit context limits)
- Graph corruption → rebuild from audit log

---

#### CAP-006: Artifact Generation (Specification Agent)
**Description:** Convert decisions into formal artifacts  
**Trigger:** User requests artifact, or project marked "ready"  
**Inputs:**
- Decision graph
- Artifact type (PRD, schema, API contract, etc.)
- Tech stack (just-in-time questioning if needed)

**Process:**
1. Check dependencies: "Can we generate this artifact?"
2. If missing dependencies → list blockers, offer to generate dependencies first
3. Use Claude (Sonnet 4) for specification generation
4. Use hybrid (Claude + open-source) for test cases, large schemas
5. Validate output against decision graph
6. Generate checkpoint every logical section
7. If failure → return partial artifact with clear gaps

**Outputs:**
- Generated artifact in requested format
- Metadata: generated_at, based_on_decisions[], tech_stack

**Success Criteria:**
- Artifact matches all decisions (no hallucinations)
- Generated within 30s for standard PRD
- Checkpoints prevent total loss on failure

**Failure Cases:**
- LLM timeout → retry with checkpoint resume
- Validation fails → flag conflicts, ask user to resolve
- Partial generation → return what succeeded, mark gaps with "TODO: failed"

---

#### CAP-007: Artifact Export (Delivery Agent)
**Description:** Format artifacts for consumption  
**Trigger:** User clicks "Export" or "Download"  
**Inputs:**
- Artifact
- Export format (multiple allowed)
- Target system (AI agent format, Git, download)

**Process:**
1. Detect artifact type
2. Use GPT-4 + open-source models for formatting
3. Generate requested formats:
   - **PRD:** Markdown, HTML, PDF, JSON
   - **Database Schema:** SQL DDL, Mermaid ER diagram
   - **API Contracts:** JSON (abstract) → export to OpenAPI, GraphQL SDL, gRPC protobuf
   - **Tickets:** JSON → export to GitHub Issues, Linear, Markdown, custom agent formats (Cursor, Claude Code, Devin, Copilot, Aider)
   - **Architecture:** C4 model (text) in Mermaid
   - **Test Cases:** Gherkin format

**Outputs:**
- Downloadable files (zip if multiple formats)
- Files copied to `/mnt/user-data/outputs` for user access

**Success Criteria:**
- Export completes in <10s
- All formats valid (parseable by target tools)

**Failure Cases:**
- Format conversion fails → return source format with error
- Partial success → provide available formats, note failures

---

#### CAP-008: Brownfield - Current State Architecture Derivation
**Description:** Generate architecture from existing code  
**Trigger:** Brownfield project created  
**Inputs:**
- Codebase (parsed)
- Existing architecture docs (if provided via import)

**Process:**
1. **Attempt A:** Import existing architecture docs if available
2. **Attempt B:** Static analysis + LLM inference
   - Parse syntax (AST) for all supported languages
   - Build dependency graph
   - For typed languages (Go, Java, TS, C#): type-aware analysis
   - For dynamic languages (Python, JS, PHP, Ruby): syntax + runtime heuristics
   - LLM (Claude) infers patterns: "Looks like microservices, API gateway at /api"
3. **Attempt C:** User-guided annotation
   - Present inferred architecture
   - Ask confirmation: "Is /api a separate service?" (radio: yes/no/unsure)
   - Correct hallucinations
4. Generate C4 model (Context, Container, Component diagrams)

**Outputs:**
- Current-state architecture (text + Mermaid C4 diagrams)
- Component inventory
- Dependency graph

**Success Criteria:**
- Architecture generated within 5 min for <500K LOC
- User confirms accuracy

**Failure Cases:**
- Unsupported language → skip, document gap
- Inference wrong → user corrections captured, re-analyze

---

#### CAP-009: Brownfield - Impact Analysis
**Description:** Assess blast radius of proposed changes  
**Trigger:** User proposes change in brownfield project  
**Inputs:**
- Change description
- Current-state architecture
- Codebase

**Process:**
1. Identify files to modify/create/delete
2. Trace downstream dependencies (who imports this?)
3. Detect breaking changes:
   - API contract comparison (removed endpoints, changed signatures)
   - Type system analysis (changed function signatures)
   - Dependency analysis (internal code affected)
   - Test impact (which tests will break)
4. Assess risk per change:
   - **Low:** Isolated, no external consumers
   - **Medium:** Internal dependencies, well-tested
   - **High:** Public API, auth logic, data loss risk
5. Flag affected features/users

**Outputs:**
- **Impact Report:**
  - Files affected (create/modify/delete)
  - Dependency ripple (downstream components)
  - Risk assessment per change
  - Breaking changes flagged
  - Migration requirements
  - Database schema changes
  - API contract changes
  - Affected tests

**Success Criteria:**
- Analysis completes in <2 min
- Risk assessment matches reality (validated post-deploy)

**Failure Cases:**
- Cannot trace dependencies → warn "incomplete analysis"
- Ambiguous change → ask clarifying questions

---

#### CAP-010: Brownfield - Change Plan Generation
**Description:** Step-by-step plan for safe changes  
**Trigger:** Impact analysis complete  
**Inputs:**
- Impact analysis
- User's risk tolerance (from questions)

**Process:**
1. Generate detailed procedure document:
   - Numbered steps with explanations
   - Code snippets, rationale, warnings
2. Generate Git workflow format:
   - Branch strategy (GitHub Flow: `main` + `feature/*`)
   - Commit sequence
   - PR strategy
3. For high-risk changes:
   - Multi-phase rollout (zero-downtime migrations)
   - Rollback procedures (undo steps)
4. For medium-risk:
   - Feature flag recommendations (code snippets)
5. Database migrations (risk-tiered):
   - Low risk: Direct DDL or framework migrations
   - High risk: Multi-phase (add nullable → backfill → remove old)
   - All include rollback/down migrations

**Outputs:**
- **Detailed procedure document** (markdown with code snippets)
- **Git workflow format** (branch, commits, PRs)
- Rollback procedures for high/medium risk changes
- Feature flag strategy for high-risk changes

**Success Criteria:**
- Plan is executable without clarification
- Rollback procedures tested (mentally validated by agent)

**Failure Cases:**
- Incomplete analysis → flag blockers, cannot generate plan

---

#### CAP-011: Brownfield - Regression Test Requirements
**Description:** Define testing needed for changes  
**Trigger:** Change plan generated  
**Inputs:**
- Change plan
- Existing test suite (if detectable)
- Coverage data (if available)

**Process:**
1. Analyze existing test coverage:
   - Parse coverage reports (Jest, pytest, coverage.py, etc.)
   - Identify untested code paths in affected files
2. Specify:
   - **Existing tests that must pass** (regression suite)
   - **New tests needed** (Gherkin format)
   - **Tests to modify** (updated assertions)
   - **Manual QA checklist** (exploratory scenarios)
3. Generate test case specifications (Gherkin: Given/When/Then)

**Outputs:**
- **Test Requirements Document:**
  - Existing tests (must stay green)
  - New test cases (Gherkin)
  - Tests to update (with diffs)
  - Manual QA checklist
  - Coverage targets (if applicable)

**Success Criteria:**
- All affected code paths have test coverage
- QA team can execute without clarification

**Failure Cases:**
- Cannot detect tests → ask user to provide test directory
- No existing tests → recommend comprehensive test suite

---

#### CAP-012: Branching & Merging (Git-style Workflow)
**Description:** Support parallel decision exploration  
**Trigger:** User creates branch  
**Inputs:**
- Current project state
- Branch name (GitHub Flow: `feature/<name>`)

**Process:**
1. Snapshot current decision graph
2. Create branch with isolated decision space
3. User works in branch (answers questions, generates artifacts)
4. When ready to merge:
   - Detect conflicts (same question answered differently)
   - Show side-by-side diff of conflicting decisions
   - User manually resolves (pick A, pick B, or write new answer)
   - Agent re-validates consistency after merge
5. Update main branch, mark feature branch as merged

**Outputs:**
- Isolated branch workspace
- Merge conflict UI (when applicable)
- Updated main branch after successful merge

**Success Criteria:**
- Branches isolated (no crosstalk)
- Merge conflicts clearly presented
- Post-merge consistency validated

**Failure Cases:**
- Merge conflict unresolved → block merge, require resolution
- Validation fails post-merge → rollback merge, flag issues

---

#### CAP-013: Decision Locking (Branch Protection)
**Description:** Prevent accidental changes to finalized decisions  
**Trigger:** User protection settings, or automatic on main branch  
**Inputs:**
- Branch name
- Protection rules

**Process:**
1. On `main` branch: decisions can be locked
2. Locked decisions require branch workflow to change:
   - Create `feature/update-auth` branch
   - Modify decision in branch
   - Merge back to main (with review if team)
3. Owner/Admin can configure protection rules per workspace

**Outputs:**
- Protected branch indicator
- Error message if trying to modify locked decision

**Success Criteria:**
- Cannot directly edit locked decisions on main
- Branch workflow enforced

**Failure Cases:**
- User tries to bypass → hard block, log attempt

---

#### CAP-014: Artifact Versioning (Git-like)
**Description:** Full version control for artifacts  
**Trigger:** Every decision change, artifact generation  
**Inputs:**
- Artifact
- Decision that triggered change

**Process:**
1. Every artifact change creates new version (commit-like)
2. Store: artifact_id, version_number, content, based_on_decisions[], timestamp, author
3. User can:
   - View history (all versions)
   - Diff between versions (inline, red/green highlights)
   - Rollback to prior version
   - Branch from any version
4. Maintain decision → artifact traceability

**Outputs:**
- Version history per artifact
- Diff view between any two versions
- Rollback capability

**Success Criteria:**
- No data loss
- Diffs render correctly
- Rollback is instant

**Failure Cases:**
- Storage corruption → rebuild from audit log

---

#### CAP-015: Artifact Dependency Tracking & Regeneration
**Description:** Maintain consistency across artifacts  
**Trigger:** Decision changes that affect multiple artifacts  
**Inputs:**
- Changed decision
- Dependency graph

**Process:**
1. Track dependencies: "API contract depends on data model"
2. When user changes data model decision:
   - Detect stale artifacts (API contract now outdated)
   - Alert user: "API contract is stale. Regenerate?"
3. User can:
   - Regenerate immediately
   - Defer regeneration
   - Review diff before accepting
4. Block artifact generation if dependencies missing:
   - User requests "API contract"
   - System: "Need data model first" → offer to generate data model

**Outputs:**
- Staleness alerts
- Regeneration prompts
- Dependency blocker messages

**Success Criteria:**
- Stale artifacts flagged within 1s of decision change
- Dependencies clear and actionable

**Failure Cases:**
- Circular dependencies → flag error, require user intervention

---

#### CAP-016: Collaboration - Comments on Artifacts
**Description:** Structured feedback mechanism  
**Trigger:** User clicks "Comment" on artifact  
**Inputs:**
- Artifact section
- Comment text
- Comment type: Question, Issue, Suggestion, Approval

**Process:**
1. Attach comment to artifact (specific line/section if applicable)
2. **Question/Issue** types:
   - Notify project owner/admin
   - Agent re-opens relevant questions
   - Asks: "Commenter says X is wrong. What should it be?"
3. **Suggestion** type:
   - Logged, does not trigger agent action
   - Owner can incorporate manually
4. **Approval** type:
   - Marks section as reviewed/approved
   - Can lock section if workspace settings allow
5. Thread-based: multiple users can reply

**Outputs:**
- Comment thread on artifact
- Re-questioning if Issue/Question
- Approval status if Approval

**Success Criteria:**
- Comments visible to all workspace members
- Issues trigger agent follow-up within 5s

**Failure Cases:**
- Comment fails to save → retry, log error

---

#### CAP-017: Workspace Management
**Description:** Organize projects and members  
**Trigger:** User creates workspace, invites members  
**Inputs:**
- Workspace name
- Member email(s)
- Role(s): Owner, Admin, Editor, Viewer

**Process:**
1. **Create workspace:**
   - User becomes Owner
   - Can invite members via email
2. **Invite members:**
   - Send email invitation
   - Invitee clicks link, joins workspace
3. **Permissions (4-tier):**
   - **Owner:** All permissions + delete workspace + billing
   - **Admin:** Manage members + all project actions
   - **Editor:** Create/edit projects + answer questions + generate artifacts
   - **Viewer:** Read-only access to projects + artifacts
4. **Workspace settings:**
   - Default branch protection rules
   - Retention policies (based on plan tier)
   - Validation strictness (minimal/standard/strict)

**Outputs:**
- Workspace created
- Members added with roles
- Settings configured

**Success Criteria:**
- Invite emails delivered
- Roles enforced

**Failure Cases:**
- Email bounce → notify inviter
- User already in workspace → error "already a member"

---

#### CAP-018: Authentication
**Description:** User identity management  
**Trigger:** User visits site  
**Inputs:**
- Email, password (or OAuth token)

**Process:**
1. **Email/password:**
   - bcrypt/argon2 password hashing
   - Session token (JWT, 7-day expiry)
2. **Magic links:**
   - User enters email
   - Send one-time login link (valid 15 min)
   - Click link → authenticated
3. **OAuth social providers:**
   - "Sign in with Google/GitHub/Microsoft"
   - OAuth flow, store external ID
4. **2FA (optional, TOTP):**
   - User enables in settings
   - Requires TOTP code after password
   - Google Authenticator, Authy compatible
5. **SSO (paid/enterprise tiers):**
   - Google Workspace, Okta, Azure AD
   - SAML/OAuth, phased rollout

**Outputs:**
- Authenticated session
- User object with roles

**Success Criteria:**
- Login <2s
- Session persists across tabs
- 2FA works with standard apps

**Failure Cases:**
- Invalid credentials → error message
- Magic link expired → regenerate
- OAuth provider down → fallback to email/password

---

#### CAP-019: Data Import (Bootstrap Projects)
**Description:** Ingest existing documentation  
**Trigger:** User uploads docs during project creation  
**Inputs:**
- PRDs (markdown, PDF, Word)
- Tickets/issues (CSV export, JSON from Jira/GitHub/Linear)
- Architecture docs (Confluence, Notion export, markdown)

**Process:**
1. **Parse PRDs:**
   - Extract sections, decisions
   - Agent asks clarifying questions on ambiguities
2. **Parse tickets:**
   - Reverse-engineer requirements
   - "10 tickets mention 'auth' → need OAuth2?"
3. **Parse architecture docs:**
   - Build current-state model
   - Use for brownfield mode
4. Store parsed info in decision graph

**Outputs:**
- Pre-populated decision graph
- Reduced questioning (fewer unknowns)

**Success Criteria:**
- Parsing succeeds for 90% of common formats
- Extracted decisions match source docs

**Failure Cases:**
- Unsupported format → ask user to convert to markdown/PDF
- Parse error → skip, ask questions normally

---

#### CAP-020: Conversation Pause/Resume
**Description:** Long-lived project state  
**Trigger:** Auto-save (continuous)  
**Inputs:**
- Every question, answer, decision, artifact

**Process:**
1. Auto-save every interaction (no user action)
2. Store:
   - Conversation turns
   - Decision graph
   - Pending questions
   - Deferred questions
   - Artifacts (with versions)
3. On resume:
   - Restore exact state
   - Show pending questions
   - Context Memory Agent loads decision graph

**Outputs:**
- Seamless resume (no loss of state)

**Success Criteria:**
- No data loss
- Resume <2s

**Failure Cases:**
- Storage failure → fallback to last checkpoint (warn user of potential loss)

---

#### CAP-021: Open Questions Management
**Description:** Track unanswered questions  
**Trigger:** User defers question, or new questions arise  
**Inputs:**
- Questions (pending, deferred)
- Artifact dependencies

**Process:**
1. **Categorize questions by dependency:**
   - "To generate PRD: 3 questions remaining"
   - "To generate API spec: 7 questions"
2. **Allow deferring:**
   - User clicks "Ask later"
   - Moves to "Parked questions" list
3. **Resurface deferred questions:**
   - When relevant decision context emerges
   - Agent: "Earlier you deferred X. Ready to answer now?"
4. User can manually view/answer deferred questions

**Outputs:**
- Categorized question list (by artifact)
- Parked questions section
- Automatic resurfacing

**Success Criteria:**
- No lost questions
- Resurfacing is contextually relevant

**Failure Cases:**
- Question never resurfaced → user can manually access

---

#### CAP-022: Decision History Visualization
**Description:** Show confirmed decisions as graph  
**Trigger:** User clicks "Decisions" tab  
**Inputs:**
- Decision graph

**Process:**
1. Render interactive dependency graph (D3.js or similar)
   - Nodes = decisions
   - Edges = dependencies
   - Color-code by category (auth, database, API, etc.)
2. User can:
   - Click node → see decision details
   - Filter by category, date, author
   - Search decisions
   - Zoom/pan graph
3. On hover: show decision summary + timestamp + author

**Outputs:**
- Interactive graph UI
- Decision details panel

**Success Criteria:**
- Graph renders in <3s for 1000 decisions
- Interactive (smooth zoom/pan)

**Failure Cases:**
- Too many decisions (>5000) → offer filtered view

---

### 3.2 Supporting Capabilities

#### CAP-S01: Rate Limiting (MVP)
**Hard limits per user:**
- 50 questions/day
- 10 projects
- 5 active conversations
- Block when exceeded, notify user

#### CAP-S02: Usage Analytics (Internal)
**Track:**
- Questions asked per project
- Time to first artifact
- Token usage per agent
- Error rates

#### CAP-S03: Templates (System-Provided)
**Built-in templates (day 1):**
1. SaaS web application
2. REST API service
3. Mobile app (iOS/Android)

**Future:** Workspace-level templates (save project as template), community marketplace

#### CAP-S04: Audit Logging (Phased)
**MVP:** Basic logs (errors, warnings)  
**Beta:** User actions (questions, decisions)  
**Production:** Full audit trail (access, reasoning traces)

---

## 4. USER JOURNEYS & FLOWS

### 4.1 Journey A: Greenfield Project (Founder → AI Agent)

**Scenario:** Founder has idea for SaaS app, wants to hand specs to Claude Code.

**Steps:**
1. **Create workspace** (if first time)
   - Name: "My Startup"
   - Role: Owner
2. **Create project**
   - Click "New Project" → "Greenfield"
   - Name: "Customer Portal"
   - Select template: "SaaS web application"
   - Time investment: "Standard (2 hours)"
   - Upload: whiteboard sketch (PNG)
3. **Answer questions**
   - Agent asks: "Who can create an account?" (radio + options)
   - Founder selects: "Anyone with email"
   - Agent asks: "Authentication method?" (OAuth2 / JWT / Magic links / SSO)
   - Founder selects: "Magic links"
   - Agent asks: "Database?" (PostgreSQL / MySQL / MongoDB)
   - Founder selects: "PostgreSQL"
   - ... (30 more questions over 90 minutes)
4. **Generate artifacts**
   - System: "Ready to generate artifacts"
   - Founder clicks: "Generate PRD"
   - Founder clicks: "Generate API Contract"
   - Founder clicks: "Generate Engineering Tickets"
5. **Export for AI agent**
   - Founder clicks: "Export" → "Claude Code format"
   - Downloads: `customer-portal-tickets.json`
6. **Use in Claude Code**
   - Founder runs: `claude-code import customer-portal-tickets.json`
   - Claude Code builds app

**Alternate Path: Defer question**
- Agent asks: "Rate limiting strategy?"
- Founder: "Ask later" → parked
- Agent continues with other questions

**Error Path: Contradiction detected**
- Founder answers: "No authentication"
- Later answers: "Users have profiles"
- Agent: "Conflict detected. Users can't have profiles without auth. Which is correct?"
- Founder resolves

---

### 4.2 Journey B: Brownfield Project (Architect → Team)

**Scenario:** Architect needs to add OAuth2 to legacy monolith, wants safe change plan.

**Steps:**
1. **Create project**
   - Click "New Project" → "Brownfield"
   - Name: "Add OAuth2"
   - Codebase: GitHub OAuth → select repo
   - Change intent: "Add a feature"
2. **Wait for analysis**
   - System clones repo
   - Runs static analysis (5 min for 200K LOC)
   - Generates current-state architecture
   - Agent asks: "Is `/api` a separate service?" → Architect confirms
3. **Answer scope questions**
   - Agent: "Which OAuth2 providers?" (Google / GitHub / Microsoft / All)
   - Architect: "Google and GitHub"
   - Agent: "Token storage?" (Database / Redis / JWT)
   - Architect: "PostgreSQL (existing DB)"
   - ... (15 questions)
4. **Review impact analysis**
   - Files affected: 12 (3 create, 8 modify, 1 delete)
   - Risk: High (auth logic change)
   - Breaking changes: None (additive feature)
   - Tests affected: 23 (5 new, 18 modify)
5. **Generate change plan**
   - Detailed procedure document (15 steps with code snippets)
   - Git workflow: `feature/oauth2`, 8 commits, 1 PR
   - Rollback procedure (high-risk → included)
   - Feature flag strategy (gradual rollout)
   - Regression test requirements (Gherkin + manual QA)
6. **Share with team**
   - Architect exports: "Download" → zip with all artifacts
   - Shares in Slack
   - Team reviews, comments: "Issue: need CSRF protection"
   - Agent re-questions, adds CSRF to plan

**Error Path: Missing tests**
- Impact analysis: "Cannot detect tests"
- Architect provides test directory path
- Re-analysis includes test impact

---

### 4.3 Journey C: Collaborative Refinement (Product Owner + Eng Lead)

**Scenario:** Product Owner and Eng Lead refine API design together.

**Steps:**
1. **Product Owner creates project**
   - Greenfield, "Payment API"
   - Answers 20 questions about business logic
2. **Generates PRD**
   - Shares with Eng Lead (invites to workspace as Editor)
3. **Eng Lead reviews PRD**
   - Clicks "Comment" on "Authentication" section
   - Type: Issue
   - Text: "We need API key rotation, not just static keys"
4. **Agent re-questions**
   - Agent: "Should API keys expire?" (Yes / No)
   - Product Owner: "Yes, every 90 days"
5. **Eng Lead creates branch**
   - Branch: `feature/improve-auth`
   - Changes authentication decision from "Static API keys" to "Rotating API keys"
   - Generates updated API contract in branch
6. **Merge branch**
   - Eng Lead requests merge to main
   - Product Owner reviews diff
   - Approves merge
   - Agent re-validates consistency
7. **Export final spec**
   - Export to GitHub Issues
   - Development begins

---

### 4.4 Recovery Flows

#### RF-001: User Abandons Project Mid-Questioning
- **Trigger:** 30 days inactivity
- **Action:** Auto-archive project (move to "Archived" section)
- **Recovery:** User clicks "Restore", project resumes with full state

#### RF-002: LLM Provider Outage
- **Trigger:** API call fails 3x
- **Action:** Queue request, show "Service temporarily unavailable, retrying..."
- **Recovery:** Auto-retry every 60s for 10 min, then notify user

#### RF-003: Artifact Generation Fails Midway
- **Trigger:** Timeout or OOM during generation
- **Action:** Return partial artifact with "TODO: Section X failed"
- **Recovery:** User clicks "Retry failed sections"

#### RF-004: Merge Conflict Unresolved
- **Trigger:** User tries to merge branch with conflicts
- **Action:** Block merge, show conflicts
- **Recovery:** User resolves conflicts, retry merge

---

## 5. SYSTEM ARCHITECTURE (CONCEPTUAL)

### 5.1 Major Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Web UI (React)                          │
│  - Conversation Interface                                    │
│  - Decision Graph Visualizer (D3.js)                        │
│  - Artifact Viewer/Editor                                    │
│  - Diff Viewer (inline, red/green)                          │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS/WebSocket
┌────────────────────▼────────────────────────────────────────┐
│              API Gateway / Load Balancer                     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌──▼──────┐ ┌──▼────────────┐
│ Orchestration│ │ Auth    │ │ File Storage  │
│ Service      │ │ Service │ │ (S3/GCS)      │
└───────┬──────┘ └─────────┘ └───────────────┘
        │
        │ Dispatch to agents
        │
┌───────▼──────────────────────────────────────────────────────┐
│                       Agent Layer                             │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Interrogation   │  │ Specification│  │ Validation      │ │
│  │ Agent           │  │ Agent        │  │ Agent           │ │
│  │ (Claude/GPT-4)  │  │ (Claude+OSS) │  │ (Claude)        │ │
│  └─────────────────┘  └──────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌──────────────┐                       │
│  │ Context Memory  │  │ Delivery     │                       │
│  │ Agent (VectorDB)│  │ Agent(GPT-4) │                       │
│  └─────────────────┘  └──────────────┘                       │
└───────────────────────────────────────────────────────────────┘
        │
        │ Store/Retrieve
        │
┌───────▼──────────────────────────────────────────────────────┐
│                     Data Layer                                │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ PostgreSQL  │  │ Vector DB    │  │ Redis (cache)    │    │
│  │ (decisions, │  │ (embeddings) │  │ (sessions)       │    │
│  │  artifacts) │  │              │  │                  │    │
│  └─────────────┘  └──────────────┘  └──────────────────┘    │
└───────────────────────────────────────────────────────────────┘
        │
        │ Ingest code
        │
┌───────▼──────────────────────────────────────────────────────┐
│             Codebase Analysis Service                         │
│  - GitHub/GitLab OAuth client                                 │
│  - Git clone worker                                           │
│  - Multi-language parsers (Tree-sitter)                       │
│  - Dependency graph builder                                   │
└───────────────────────────────────────────────────────────────┘
        │
        │ Call LLMs
        │
┌───────▼──────────────────────────────────────────────────────┐
│              External LLM Providers                           │
│  - Anthropic (Claude)                                         │
│  - OpenAI (GPT-4)                                             │
│  - Replicate/Together (open-source models)                    │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 Component Responsibilities

#### Orchestration Service
- **Owns:** Agent dispatch, workflow state machine
- **Responsibilities:**
  - Route questions to Interrogation Agent
  - Trigger artifact generation
  - Coordinate multi-agent workflows
  - Enforce rate limits
- **Sync/Async:** Async (event-driven)
- **Trust Boundary:** Internal only

#### Interrogation Agent
- **Owns:** Question generation logic
- **Responsibilities:**
  - Load decision graph from Context Memory
  - Use goal-oriented reasoning to identify gaps
  - Generate next question with options
  - Adapt format per question type
- **Sync/Async:** Sync (responds to Orchestration Service calls)
- **Trust Boundary:** Internal, calls Claude API

#### Context Memory Agent
- **Owns:** Decision graph, conversation history
- **Responsibilities:**
  - Store structured decisions (not raw text)
  - Embed decisions in vector DB
  - Retrieve relevant context via RAG
  - Handle context window overflow (summarization + retrieval)
- **Sync/Async:** Sync reads, async writes
- **Trust Boundary:** Internal, no direct user access

#### Specification Agent
- **Owns:** Artifact generation
- **Responsibilities:**
  - Check dependencies before generation
  - Generate artifacts using Claude (primary) + open-source (cost optimization)
  - Validate output against decision graph
  - Checkpoint progress (every logical section)
  - Return partial artifacts on failure
- **Sync/Async:** Async (long-running, 10-60s)
- **Trust Boundary:** Internal, calls multiple LLM APIs

#### Validation Agent
- **Owns:** Consistency checks
- **Responsibilities:**
  - Real-time contradiction detection
  - Validate artifact against decision graph
  - Detect breaking changes (brownfield)
  - Flag impossible constraints
- **Sync/Async:** Sync (must be fast, <1s)
- **Trust Boundary:** Internal, calls Claude API

#### Delivery Agent
- **Owns:** Output formatting
- **Responsibilities:**
  - Convert artifacts to requested formats
  - Generate multiple export formats (Markdown, PDF, JSON, etc.)
  - Adapt to AI agent schemas (Cursor, Devin, etc.)
- **Sync/Async:** Sync (fast, <10s)
- **Trust Boundary:** Internal, calls GPT-4 + open-source

#### Codebase Analysis Service
- **Owns:** Brownfield code ingestion
- **Responsibilities:**
  - OAuth to GitHub/GitLab
  - Clone repos (handle large sizes)
  - Parse code (multi-language via Tree-sitter)
  - Build dependency graphs
  - Detect breaking changes
- **Sync/Async:** Async (long-running, up to 5 min)
- **Trust Boundary:** External (accesses user's GitHub)

#### Auth Service
- **Owns:** User identity
- **Responsibilities:**
  - Email/password, magic links, OAuth, SSO
  - 2FA (TOTP)
  - Session management (JWT)
  - Role-based access control
- **Sync/Async:** Sync
- **Trust Boundary:** External-facing API

#### File Storage
- **Owns:** Uploaded files, generated artifacts
- **Responsibilities:**
  - Store user uploads (docs, images, audio)
  - Store generated artifacts (versioned)
  - Serve download links
- **Sync/Async:** Sync
- **Trust Boundary:** Internal, presigned URLs for user access

---

## 6. DATA MODEL

### 6.1 Core Entities

#### Entity: User
```
user_id: UUID (PK)
email: string (unique, indexed)
password_hash: string (nullable if OAuth-only)
name: string
created_at: timestamp
last_login_at: timestamp
totp_secret: string (nullable, encrypted)
totp_enabled: boolean
oauth_providers: jsonb (array of {provider, external_id})
```

**Relationships:**
- `user_id` → `workspace_members.user_id` (1:N)

**Constraints:**
- Email must be valid format
- Password hash uses bcrypt/argon2

**Lifecycle:**
- Created on signup
- Soft-deleted on account deletion (retain for audit, anonymize PII)

**Retention:**
- Active: indefinite
- Deleted: 90 days (then hard delete)

---

#### Entity: Workspace
```
workspace_id: UUID (PK)
name: string
owner_user_id: UUID (FK → users.user_id)
created_at: timestamp
settings: jsonb {
  branch_protection: boolean,
  validation_strictness: enum(minimal, standard, strict),
  retention_policy: enum(free_90d, paid_indefinite, enterprise_custom)
}
plan_tier: enum(free, pro, enterprise)
```

**Relationships:**
- `workspace_id` → `workspace_members.workspace_id` (1:N)
- `workspace_id` → `projects.workspace_id` (1:N)

**Constraints:**
- Owner must be a member of workspace

**Lifecycle:**
- Created when user creates first workspace
- Deleted only by owner (cascades to projects)

**Retention:**
- Active: indefinite (based on plan tier)
- Deleted: 30 days (then hard delete if free tier)

---

#### Entity: WorkspaceMember
```
member_id: UUID (PK)
workspace_id: UUID (FK → workspaces.workspace_id)
user_id: UUID (FK → users.user_id)
role: enum(owner, admin, editor, viewer)
invited_by: UUID (FK → users.user_id)
invited_at: timestamp
joined_at: timestamp (nullable if not yet accepted)
```

**Relationships:**
- Many-to-many join table (User ↔ Workspace)

**Constraints:**
- Unique(workspace_id, user_id)
- One owner per workspace

**Lifecycle:**
- Created on invite
- `joined_at` set when user accepts
- Deleted when user removed or leaves workspace

---

#### Entity: Project
```
project_id: UUID (PK)
workspace_id: UUID (FK → workspaces.workspace_id)
name: string
type: enum(greenfield, brownfield)
status: enum(active, paused, archived, completed)
time_investment: enum(quick, standard, comprehensive)
template_id: UUID (FK → templates.template_id, nullable)
created_by: UUID (FK → users.user_id)
created_at: timestamp
last_activity_at: timestamp
settings: jsonb {
  tech_stack: {backend_lang, frontend_lang, database, ...},
  codebase_url: string (nullable, for brownfield),
  codebase_size_loc: int (nullable)
}
```

**Relationships:**
- `project_id` → `branches.project_id` (1:N)
- `project_id` → `decisions.project_id` (1:N)
- `project_id` → `artifacts.project_id` (1:N)

**Constraints:**
- Type must match content (greenfield → no codebase_url)

**Lifecycle:**
- Created on project init
- Auto-archived after 30 days inactivity
- Deleted manually or via workspace deletion

**Retention:**
- Active/Paused: based on workspace plan
- Archived: 90 days (then suggest delete)

---

#### Entity: Branch
```
branch_id: UUID (PK)
project_id: UUID (FK → projects.project_id)
name: string (GitHub Flow: main, feature/<name>)
parent_branch_id: UUID (FK → branches.branch_id, nullable for main)
created_by: UUID (FK → users.user_id)
created_at: timestamp
merged_at: timestamp (nullable)
merged_by: UUID (FK → users.user_id, nullable)
is_protected: boolean (true for main)
```

**Relationships:**
- `branch_id` → `decisions.branch_id` (1:N)
- `branch_id` → `artifacts.branch_id` (1:N)

**Constraints:**
- One `main` branch per project
- Branch name unique per project

**Lifecycle:**
- Created on project init (main) or user branch creation
- Marked merged when merged to parent
- Can be deleted after merge (keep for audit)

---

#### Entity: Decision
```
decision_id: UUID (PK)
project_id: UUID (FK → projects.project_id)
branch_id: UUID (FK → branches.branch_id)
question_text: text
answer_text: text
options_presented: jsonb (array of options)
category: enum(auth, database, api, ui, deployment, ...)
is_assumption: boolean (true if "decide for me" was used)
assumption_reasoning: text (nullable, if is_assumption=true)
dependencies: jsonb (array of decision_ids this depends on)
answered_by: UUID (FK → users.user_id)
answered_at: timestamp
version: int (incremented on change)
is_locked: boolean
```

**Relationships:**
- `decision_id` → `decision_dependencies.decision_id` (1:N)
- `decision_id` → `artifact_dependencies.decision_id` (M:N)

**Constraints:**
- Cannot change if is_locked=true and branch is protected

**Lifecycle:**
- Created when user answers question
- Versioned on change (creates new row with version++)
- Never deleted (audit trail)

**Retention:**
- Indefinite (immutable audit log)

---

#### Entity: Artifact
```
artifact_id: UUID (PK)
project_id: UUID (FK → projects.project_id)
branch_id: UUID (FK → branches.branch_id)
type: enum(prd, schema, api_contract, tickets, architecture, tests, deployment_plan)
content: text (or reference to blob storage)
format: enum(markdown, json, yaml, sql, gherkin, mermaid, ...)
version: int
based_on_decisions: jsonb (array of decision_ids)
generated_by_agent: enum(specification, delivery)
generated_at: timestamp
is_stale: boolean (true if decisions changed since generation)
tech_stack: jsonb (nullable, for code-specific artifacts)
```

**Relationships:**
- `artifact_id` → `artifact_versions.artifact_id` (1:N)
- `artifact_id` → `comments.artifact_id` (1:N)

**Constraints:**
- Content or blob_storage_key required (one must be set)

**Lifecycle:**
- Created on generation
- Versioned on regeneration
- Marked stale when dependencies change
- Deleted with project (or can be exported before deletion)

**Retention:**
- Versions: last 10 versions kept (configurable)
- Old versions: 90 days after new version

---

#### Entity: Comment
```
comment_id: UUID (PK)
artifact_id: UUID (FK → artifacts.artifact_id)
section: string (nullable, e.g. "line 45-60" or "Authentication section")
user_id: UUID (FK → users.user_id)
comment_type: enum(question, issue, suggestion, approval)
text: text
parent_comment_id: UUID (FK → comments.comment_id, nullable for thread)
created_at: timestamp
resolved_at: timestamp (nullable)
resolved_by: UUID (FK → users.user_id, nullable)
```

**Relationships:**
- Thread structure via `parent_comment_id`

**Constraints:**
- Type=issue/question → triggers agent action

**Lifecycle:**
- Created on comment submission
- Resolved when issue addressed
- Deleted with artifact

---

#### Entity: ConversationTurn
```
turn_id: UUID (PK)
project_id: UUID (FK → projects.project_id)
branch_id: UUID (FK → branches.branch_id)
turn_number: int (sequential per project)
agent: enum(interrogation, specification, validation, delivery)
message: text (question or status message)
user_response: text (nullable if agent-only turn)
timestamp: timestamp
```

**Relationships:**
- Ordered sequence per project

**Constraints:**
- `turn_number` unique per (project_id, branch_id)

**Lifecycle:**
- Created every interaction
- Never deleted (audit trail)

**Retention:**
- Last 1000 turns in memory
- Older turns: RAG retrieval only

---

#### Entity: CodebaseAnalysis
```
analysis_id: UUID (PK)
project_id: UUID (FK → projects.project_id)
codebase_url: string
codebase_size_loc: int
languages_detected: jsonb (array of {language, loc_count})
architecture_derived: text (C4 model text)
architecture_diagram: text (Mermaid)
dependency_graph: jsonb (nodes, edges)
analyzed_at: timestamp
analysis_duration_seconds: int
```

**Relationships:**
- 1:1 with brownfield projects

**Constraints:**
- Required for brownfield projects

**Lifecycle:**
- Created on brownfield project init
- Re-analyzed if codebase changes (user-triggered)

**Retention:**
- Latest analysis only (overwrite on re-analyze)

---

### 6.2 Supporting Entities

#### Entity: Template
```
template_id: UUID (PK)
name: string
type: enum(system, workspace, community)
workspace_id: UUID (FK, nullable for system templates)
description: text
question_flow: jsonb (decision tree or goal-reasoning config)
default_tech_stack: jsonb
created_by: UUID (FK → users.user_id, nullable for system)
created_at: timestamp
```

**Lifecycle:**
- System templates: seeded on deploy
- Workspace templates: created by users (future)

---

#### Entity: AuditLog
```
log_id: UUID (PK)
workspace_id: UUID (FK)
user_id: UUID (FK)
action: enum(login, create_project, answer_question, generate_artifact, export, ...)
resource_type: enum(project, artifact, decision, ...)
resource_id: UUID
timestamp: timestamp
ip_address: inet
user_agent: string
```

**Retention:**
- Free tier: 30 days
- Paid tier: 1 year
- Enterprise: indefinite

---

## 7. APIs & INTERFACES

### 7.1 REST API (Primary Interface)

**Base URL:** `https://api.agenticspecbuilder.com/v1`

**Authentication:** Bearer token (JWT in `Authorization` header)

---

#### POST /auth/signup
**Purpose:** Create new user account  
**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "Alice Smith"
}
```
**Response (201):**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "token": "jwt_token"
}
```
**Error Codes:**
- 400: Invalid email format
- 409: Email already exists
- 429: Rate limit exceeded

**Idempotency:** No (duplicate email returns 409)

---

#### POST /auth/login
**Purpose:** Authenticate user  
**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```
**Response (200):**
```json
{
  "token": "jwt_token",
  "user_id": "uuid",
  "workspaces": [{"workspace_id": "uuid", "role": "owner"}]
}
```
**Error Codes:**
- 401: Invalid credentials
- 429: Rate limit exceeded

---

#### POST /workspaces
**Purpose:** Create new workspace  
**Request:**
```json
{
  "name": "My Startup"
}
```
**Response (201):**
```json
{
  "workspace_id": "uuid",
  "name": "My Startup",
  "owner_user_id": "uuid",
  "created_at": "2026-02-04T10:00:00Z"
}
```
**Error Codes:**
- 401: Unauthorized
- 400: Invalid name

**AuthZ:** User must be authenticated

---

#### POST /workspaces/{workspace_id}/members
**Purpose:** Invite member to workspace  
**Request:**
```json
{
  "email": "colleague@example.com",
  "role": "editor"
}
```
**Response (201):**
```json
{
  "member_id": "uuid",
  "status": "invited",
  "invite_sent_to": "colleague@example.com"
}
```
**Error Codes:**
- 403: Forbidden (not owner/admin)
- 400: Invalid role

**AuthZ:** Owner or Admin only

---

#### POST /projects
**Purpose:** Create new project  
**Request (Greenfield):**
```json
{
  "workspace_id": "uuid",
  "name": "Customer Portal",
  "type": "greenfield",
  "time_investment": "standard",
  "template_id": "uuid" // optional
}
```
**Response (201):**
```json
{
  "project_id": "uuid",
  "branch_id": "uuid", // main branch created
  "status": "active",
  "next_question": {
    "question_id": "uuid",
    "text": "Who can create an account?",
    "options": [
      {"value": "anyone", "label": "Anyone with email"},
      {"value": "invite_only", "label": "Invite-only"},
      {"value": "domain", "label": "Anyone with @company.com"}
    ],
    "format": "radio"
  }
}
```
**Error Codes:**
- 403: Forbidden (not editor/admin/owner)
- 400: Invalid type or time_investment

**AuthZ:** Editor, Admin, or Owner

---

#### POST /projects/{project_id}/answers
**Purpose:** Submit answer to question  
**Request:**
```json
{
  "branch_id": "uuid",
  "question_id": "uuid",
  "answer": "anyone"
}
```
**Response (200):**
```json
{
  "decision_id": "uuid",
  "contradiction_detected": false,
  "next_question": {
    "question_id": "uuid",
    "text": "Authentication method?",
    "options": [...]
  }
}
```
**Or if contradiction:**
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
**Error Codes:**
- 404: Question not found
- 409: Contradiction (see response body)

**Idempotency:** Answering same question twice with same answer → no-op

---

#### POST /projects/{project_id}/defer-question
**Purpose:** Defer question to "ask later"  
**Request:**
```json
{
  "branch_id": "uuid",
  "question_id": "uuid"
}
```
**Response (200):**
```json
{
  "status": "deferred",
  "next_question": {...}
}
```

---

#### POST /projects/{project_id}/artifacts
**Purpose:** Generate artifact  
**Request:**
```json
{
  "branch_id": "uuid",
  "type": "prd",
  "formats": ["markdown", "pdf"]
}
```
**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "generating",
  "estimated_seconds": 30
}
```
**Poll at:** `GET /jobs/{job_id}`

**Error Codes:**
- 400: Missing dependencies (returns list of required decisions)
- 429: Rate limit exceeded

---

#### GET /jobs/{job_id}
**Purpose:** Check artifact generation status  
**Response (200, in-progress):**
```json
{
  "job_id": "uuid",
  "status": "generating",
  "progress": 60
}
```
**Response (200, complete):**
```json
{
  "job_id": "uuid",
  "status": "complete",
  "artifact_id": "uuid",
  "download_urls": {
    "markdown": "https://...",
    "pdf": "https://..."
  }
}
```
**Response (200, failed):**
```json
{
  "job_id": "uuid",
  "status": "failed",
  "error": "LLM timeout",
  "partial_artifact_id": "uuid" // if partial success
}
```

---

#### POST /projects/{project_id}/branches
**Purpose:** Create feature branch  
**Request:**
```json
{
  "name": "feature/improve-auth",
  "parent_branch_id": "uuid" // main branch
}
```
**Response (201):**
```json
{
  "branch_id": "uuid",
  "name": "feature/improve-auth",
  "created_at": "2026-02-04T10:30:00Z"
}
```

---

#### POST /projects/{project_id}/branches/{branch_id}/merge
**Purpose:** Merge branch  
**Request:**
```json
{
  "target_branch_id": "uuid" // main
}
```
**Response (200, no conflicts):**
```json
{
  "status": "merged",
  "merged_at": "2026-02-04T10:35:00Z"
}
```
**Response (200, conflicts):**
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

**Error Codes:**
- 403: Cannot merge protected branch without resolving conflicts

---

#### POST /projects/{project_id}/branches/{branch_id}/resolve-conflicts
**Purpose:** Resolve merge conflicts  
**Request:**
```json
{
  "resolutions": [
    {
      "decision_id": "uuid",
      "chosen_answer": "OAuth2" // or "JWT" or custom text
    }
  ]
}
```
**Response (200):**
```json
{
  "status": "conflicts_resolved",
  "ready_to_merge": true
}
```

---

#### GET /projects/{project_id}/decisions
**Purpose:** Retrieve decision graph  
**Response (200):**
```json
{
  "decisions": [
    {
      "decision_id": "uuid",
      "question": "Authentication method?",
      "answer": "OAuth2",
      "category": "auth",
      "dependencies": ["uuid1", "uuid2"],
      "answered_by": "user_id",
      "answered_at": "2026-02-04T10:00:00Z",
      "is_assumption": false
    }
  ],
  "graph": {
    "nodes": [...],
    "edges": [...]
  }
}
```

---

#### POST /projects/{project_id}/import
**Purpose:** Import existing documentation  
**Request (multipart/form-data):**
```
files: [prd.pdf, tickets.csv]
type: ["prd", "tickets"]
```
**Response (202):**
```json
{
  "job_id": "uuid",
  "status": "parsing"
}
```

---

#### POST /artifacts/{artifact_id}/comments
**Purpose:** Add comment to artifact  
**Request:**
```json
{
  "section": "line 45-60",
  "type": "issue",
  "text": "Missing CSRF protection"
}
```
**Response (201):**
```json
{
  "comment_id": "uuid",
  "agent_action": "re_questioning", // if type=issue/question
  "new_question": {...}
}
```

---

#### POST /codebase/analyze
**Purpose:** Trigger brownfield analysis  
**Request:**
```json
{
  "project_id": "uuid",
  "source": "github",
  "repo_url": "https://github.com/user/repo"
}
```
**Response (202):**
```json
{
  "analysis_id": "uuid",
  "status": "cloning",
  "estimated_minutes": 5
}
```

---

### 7.2 WebSocket API (Real-time Updates)

**Endpoint:** `wss://api.agenticspecbuilder.com/v1/ws`

**Authentication:** Token in initial handshake

**Events (Server → Client):**

```json
// New question available
{
  "event": "question_ready",
  "project_id": "uuid",
  "question": {...}
}

// Artifact generation progress
{
  "event": "artifact_progress",
  "artifact_id": "uuid",
  "progress": 75
}

// Comment added by teammate
{
  "event": "comment_added",
  "artifact_id": "uuid",
  "comment": {...}
}

// Branch merged
{
  "event": "branch_merged",
  "branch_id": "uuid"
}
```

---

### 7.3 AI Agent Export Formats

#### Cursor Format (JSON)
```json
{
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Create User model",
      "description": "...",
      "files": ["src/models/user.js"],
      "acceptance_criteria": ["..."],
      "dependencies": []
    }
  ]
}
```

#### Claude Code Format (Markdown + YAML)
```yaml
---
task_id: AUTH-123
priority: high
estimated_effort: 3h
files: [src/auth.js, tests/auth.test.js]
---
## Objective
Implement OAuth2 authentication...
```

#### GitHub Issues Format (JSON)
```json
{
  "title": "Create User model",
  "body": "...",
  "labels": ["backend", "high-priority"],
  "assignees": []
}
```

---

## 8. STATE MANAGEMENT

### 8.1 Key System States

#### Project States
- **active:** User actively working (answering questions)
- **paused:** User manually paused
- **archived:** Auto-archived after 30 days inactivity
- **completed:** User marked as done

**Transitions:**
- active → paused (manual)
- active → archived (auto after 30 days)
- paused → active (user resumes)
- archived → active (user restores)
- any → completed (manual)

**Invalid States:**
- Cannot go from completed back to active (immutable)

---

#### Artifact States
- **generating:** In progress
- **complete:** Successfully generated
- **stale:** Decisions changed since generation
- **failed:** Generation failed

**Transitions:**
- generating → complete (success)
- generating → failed (timeout/error)
- complete → stale (dependency decision changed)
- stale → generating (user triggers regenerate)

**Invalid States:**
- Cannot generate from stale without acknowledging changes

---

#### Branch States
- **active:** Can be modified
- **merging:** Merge in progress
- **merged:** Successfully merged (read-only)
- **conflict:** Merge blocked by conflicts

**Transitions:**
- active → merging (user initiates merge)
- merging → merged (success)
- merging → conflict (conflicts detected)
- conflict → merging (conflicts resolved)

**Invalid States:**
- Cannot modify merged branch

---

### 8.2 Concurrency Considerations

#### Decision Answering (Same Branch)
- **Conflict:** Two users answer same question simultaneously
- **Resolution:** Last-write-wins (second answer overwrites first)
- **Mitigation:** WebSocket alerts first user "Decision changed by User B"

#### Artifact Generation (Same Project)
- **Conflict:** Two users request same artifact type
- **Resolution:** Queue requests, generate once, serve to both
- **Mitigation:** Show "User B also requested this" message

#### Branch Merging (Same Project)
- **Conflict:** Two branches merging to main simultaneously
- **Resolution:** Serialize merges (first one wins, second recalculates conflicts)
- **Mitigation:** Lock main branch during merge

#### Codebase Analysis (Brownfield)
- **Conflict:** Multiple users trigger analysis
- **Resolution:** Debounce (only one analysis runs, others wait)
- **Mitigation:** Show "Analysis in progress by User B"

---

## 9. NON-FUNCTIONAL REQUIREMENTS

### 9.1 Performance

**Latency (P95):**
- Question presentation: Define after MVP (measure in beta)
- Answer validation: Define after MVP
- Artifact generation: Define after MVP
- Decision graph render: Define after MVP

**Throughput:**
- 100 concurrent users per workspace
- 1000 questions/hour per project

**Rate Limits (per user, MVP):**
- 50 questions/day
- 10 projects
- 5 active conversations
- 10 artifact generations/day

---

### 9.2 Scalability

**Expected Load (Year 1):**
- 10,000 users
- 50,000 projects
- 5M decisions

**Design Targets:**
- Horizontal scaling of API servers
- Database sharding by workspace_id (future)
- Vector DB scales independently

---

### 9.3 Availability & Fault Tolerance

**Target:** Define after MVP stabilizes

**Fault Tolerance:**
- LLM provider failover (Claude → GPT-4)
- Database: Read replicas for high traffic
- Redis: Clustered for session management
- Auto-retry failed jobs (3 attempts, exponential backoff)

**Graceful Degradation:**
- If Interrogation Agent down → queue questions, notify user
- If Vector DB down → use full conversation history (slower)
- If file storage down → block uploads, serve cached artifacts

---

### 9.4 Security Requirements (MVP: Option C)

**HTTPS:** All traffic encrypted (TLS 1.3)

**Password Security:**
- bcrypt/argon2 hashing (cost factor 12)
- Min 8 chars, complexity requirements

**Session Management:**
- JWT tokens, 7-day expiry
- HTTP-only cookies
- CSRF tokens for state-changing requests

**SQL Injection Prevention:**
- Parameterized queries only (no string concatenation)
- ORM with built-in escaping

**Access Controls:**
- Role-based permissions enforced at API layer
- Workspace isolation (users cannot access other workspaces)

**API Rate Limiting:**
- Per-user: 50 questions/day, 10 projects
- Per-IP: 100 requests/minute (DDoS protection)

**Audit Logging:**
- Phased (MVP: basic logs, production: full audit trail)

**Sensitive Data:**
- Auto-detect secrets (regex for API keys, AWS keys, etc.)
- Warn user, encrypt at rest
- Redact from logs

**Secrets Management:**
- Environment variables for API keys
- AWS Secrets Manager / GCP Secret Manager (for production)

---

### 9.5 Privacy & Compliance

**Phased Approach (Option E):**

**MVP (US-only, basic):**
- Single region (US-East)
- Basic GDPR best-effort (data export, deletion on request)
- Privacy policy, terms of service

**Paid Tier (GDPR compliant):**
- EU data residency option
- Right to access, deletion, portability
- Consent management for cookies

**Enterprise (multi-region):**
- User chooses data region (US, EU, Asia)
- Custom retention policies
- HIPAA/SOC2 compliance (if needed)

---

### 9.6 Observability

**Phased Approach (Option F):**

**MVP:**
- Basic application logs (errors, warnings)
- Centralized logging (CloudWatch / Stackdriver)

**Beta:**
- User action tracking (questions, decisions, artifacts)
- Token usage per LLM call
- Error rates per agent

**Production:**
- Full audit trail (who accessed what)
- Agent reasoning traces (LLM prompts, responses)
- Performance metrics (latency per agent, P95/P99)
- System health dashboards (Grafana)

**Metrics:**
- Questions asked per project
- Time to first artifact
- Artifact regeneration frequency
- User satisfaction (thumbs up/down on questions)

**Alerts:**
- LLM provider downtime
- Database slow queries (>1s)
- Rate limit exceeded (spike detection)
- Artifact generation failures (>10% error rate)

---

## 10. EDGE CASES & FAILURE MODES

### 10.1 User-Induced Failures

**EDGE-001: User answers question with nonsensical text**
- **Example:** Question: "Database?" Answer: "banana"
- **Handling:** Validation Agent rejects, asks "Please select a valid option"
- **Prevention:** Enforce option selection (radio/checkbox), free text only for "Other"

**EDGE-002: User changes decision 50 times in 5 minutes**
- **Example:** Flipping between JWT and OAuth2 repeatedly
- **Handling:** Allow (no assumption of intent), but rate limit artifact generation
- **Prevention:** Warn after 5 changes: "Frequent changes detected. Review before generating artifacts."

**EDGE-003: User uploads 10GB file**
- **Example:** Entire production database dump
- **Handling:** Reject at upload (max 100MB per file)
- **Prevention:** Client-side file size check before upload

**EDGE-004: User provides contradictory answers 100 questions apart**
- **Example:** Q5: "No authentication" ... Q105: "Users have dashboards"
- **Handling:** Validation Agent catches on Q105, flags conflict
- **Prevention:** Real-time validation every answer

**EDGE-005: User creates circular dependencies in brownfield**
- **Example:** "Change A requires Change B" + "Change B requires Change A"
- **Handling:** Dependency graph detects cycle, rejects
- **Prevention:** Topological sort validation before accepting change plan

---

### 10.2 System Failures

**FAIL-001: LLM provider timeout (Claude API)**
- **Frequency:** ~1% of requests (per provider SLA)
- **Impact:** Question generation stalled
- **Handling:**
  1. Retry 3x with exponential backoff (1s, 2s, 4s)
  2. If still fails, fallback to GPT-4
  3. If both fail, queue request, notify user "Retrying in 60s"
- **Recovery:** Auto-retry every 60s for 10 min, then notify user to try later
- **Monitoring:** Alert if >5% requests fail

**FAIL-002: Database connection lost**
- **Frequency:** Rare (<0.01%)
- **Impact:** Cannot save decisions or artifacts
- **Handling:**
  1. Retry connection 3x
  2. If fails, return 503 Service Unavailable
  3. Client auto-retries every 10s
- **Recovery:** Database failover to replica (if configured)
- **Monitoring:** Alert immediately

**FAIL-003: Vector DB unavailable**
- **Frequency:** Rare
- **Impact:** Context retrieval slow/failed
- **Handling:** Fallback to full conversation history (may hit context limits for large projects)
- **Recovery:** Wait for Vector DB recovery
- **Monitoring:** Alert if unavailable >5 min

**FAIL-004: Artifact generation runs out of memory (OOM)**
- **Frequency:** <1% (large complex artifacts)
- **Impact:** Partial artifact or failure
- **Handling:**
  1. Checkpoint every logical section (e.g., every 5 PRD sections)
  2. On OOM, return partial artifact with "TODO: Section X failed"
  3. User can retry failed sections
- **Recovery:** Retry with smaller batch size
- **Monitoring:** Alert if OOM >3% of generations

**FAIL-005: Codebase clone timeout (repo too large)**
- **Frequency:** <5% (very large repos)
- **Impact:** Brownfield analysis blocked
- **Handling:**
  1. Timeout after 10 min
  2. Ask user to narrow scope (specific directories)
  3. Or use Git shallow clone (last 100 commits only)
- **Recovery:** User provides narrower scope, retry
- **Monitoring:** Track clone duration, alert if >10 min

---

### 10.3 External Dependency Failures

**EXT-001: GitHub API rate limit exceeded**
- **Frequency:** Possible if many users clone repos
- **Impact:** Cannot clone repo
- **Handling:**
  1. Detect rate limit (HTTP 429)
  2. Queue request until rate limit resets (1 hour)
  3. Notify user "GitHub rate limit, retry in 60 min"
- **Recovery:** Auto-retry after reset
- **Monitoring:** Track rate limit usage, upgrade to higher tier if needed

**EXT-002: Email delivery failure (invite emails)**
- **Frequency:** Rare (<1%)
- **Impact:** User not notified of invite
- **Handling:**
  1. Retry via different email provider (SendGrid → AWS SES)
  2. If still fails, log error, notify inviter "Email bounce"
- **Recovery:** Inviter can resend manually
- **Monitoring:** Track bounce rate

**EXT-003: LLM hallucination (invents non-existent API)**
- **Frequency:** Low but non-zero
- **Impact:** Artifact contains incorrect info
- **Handling:**
  1. Validation Agent checks brownfield artifacts against actual code
  2. For greenfield, human-in-the-loop review (critical paths only)
  3. User can flag hallucinations via comments → agent re-questions
- **Recovery:** User reviews, corrects
- **Monitoring:** Track user-reported hallucinations

---

### 10.4 Data Corruption Scenarios

**CORRUPT-001: Decision graph has orphaned nodes**
- **Cause:** Bug in merge logic
- **Detection:** Integrity check (daily background job)
- **Handling:** Rebuild graph from audit log
- **Recovery:** Auto-repair, notify admins

**CORRUPT-002: Artifact versions out of sync**
- **Cause:** Race condition in versioning
- **Detection:** Version number gaps detected
- **Handling:** Re-generate missing versions from decision log
- **Recovery:** Auto-repair

**CORRUPT-003: User account soft-deleted but still in workspaces**
- **Cause:** Cascading delete failed
- **Detection:** Orphan detection (weekly job)
- **Handling:** Hard-delete workspace memberships
- **Recovery:** Auto-repair

---

### 10.5 Partial Success Handling

**PARTIAL-001: 80% of artifacts generated, 20% failed**
- **Example:** PRD ✅, API contract ✅, Tickets ✅, Tests ❌, Deployment ❌
- **Handling:** Return successful artifacts, mark failed sections with "TODO: Generation failed"
- **User Action:** Click "Retry failed artifacts"

**PARTIAL-002: Branch merge succeeds but post-merge validation fails**
- **Example:** Merge completes, but Validation Agent detects new contradiction
- **Handling:**
  1. Rollback merge automatically
  2. Notify user "Merge rollback: validation failed"
  3. Show new contradiction
- **User Action:** Resolve contradiction in branch, retry merge

**PARTIAL-003: Codebase analysis succeeds for 5/6 languages**
- **Example:** JavaScript ✅, Python ✅, Go ✅, Java ✅, Rust ✅, PHP ❌
- **Handling:** Return analysis for 5 languages, note "PHP not analyzed (unsupported/error)"
- **User Action:** Proceed with available analysis

---

## 11. CONFIGURATION & ENVIRONMENT

### 11.1 Environments

**Development:**
- Local or cloud-hosted (staging AWS/GCP)
- Mock LLM providers (cached responses for speed)
- SQLite or local PostgreSQL
- No rate limits

**Staging:**
- Cloud-hosted (mirrors production)
- Real LLM providers (sandbox accounts)
- PostgreSQL (small instance)
- Rate limits: 2x production (for testing)
- Test data only

**Production:**
- Cloud-hosted (AWS/GCP, multi-AZ)
- Real LLM providers (production keys)
- PostgreSQL (HA cluster)
- Redis cluster
- Vector DB (managed service)
- Full rate limits

---

### 11.2 Feature Flags

**System:**
- `enable_brownfield_mode` (boolean, default: true)
- `enable_branching` (boolean, default: true)
- `enable_templates` (boolean, default: true)
- `enable_comments` (boolean, default: true)
- `validation_strictness` (enum: minimal/standard/strict, default: standard)

**Per-Workspace:**
- `branch_protection_enabled` (boolean, default: false)
- `auto_archive_days` (int, default: 30)
- `max_projects` (int, based on plan tier)

**Per-User:**
- `beta_features_enabled` (boolean, default: false)

---

### 11.3 Configurable Parameters

**Rate Limits (per-user, MVP):**
- `max_questions_per_day` = 50
- `max_projects` = 10
- `max_active_conversations` = 5
- `max_artifact_generations_per_day` = 10

**Timeouts:**
- `llm_request_timeout_seconds` = 60
- `codebase_clone_timeout_seconds` = 600 (10 min)
- `artifact_generation_timeout_seconds` = 120

**File Limits:**
- `max_file_upload_size_mb` = 100
- `max_files_per_upload` = 10
- `supported_file_types` = [.pdf, .docx, .md, .txt, .png, .jpg, .csv, .json]

**Codebase Limits:**
- `max_repo_size_mb` = 5000 (5GB)
- `max_loc` = no hard limit (chunking strategy)

**Retention:**
- `decision_retention_days` = indefinite (audit log)
- `artifact_version_retention_count` = 10
- `audit_log_retention_days` = 30 (free) / 365 (paid) / indefinite (enterprise)

---

### 11.4 Secrets Management

**Development:**
- `.env` file (not committed)

**Staging/Production:**
- AWS Secrets Manager or GCP Secret Manager
- Secrets rotated every 90 days

**Secrets:**
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `REPLICATE_API_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `VECTOR_DB_URL`
- `JWT_SECRET`
- `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET`
- `SENDGRID_API_KEY` (email)

---

## 12. OPERATIONAL CONSIDERATIONS

### 12.1 Deployment Model

**MVP Decision:** Define after validation (Option F)

**Likely Path:**
1. MVP: Single-region cloud-hosted (AWS/GCP)
2. Beta: Same, monitor for demand
3. Production: Multi-AZ within single region
4. Enterprise: Multi-region option (US, EU)

---

### 12.2 Rollback Strategy

**Code Deployment:**
- Blue/green deployment (zero-downtime)
- Keep previous version running during new version deploy
- Health checks pass → switch traffic
- Rollback = switch back to blue (< 1 min)

**Database Migrations:**
- Forward-only migrations (no schema drops in production)
- Backward-compatible changes only (additive columns)
- Multi-phase for destructive changes:
  1. Add new column (nullable)
  2. Backfill data
  3. Switch code to use new column
  4. Later: drop old column

**Feature Flags:**
- Critical features behind flags
- Can disable instantly without deploy

---

### 12.3 Monitoring

**Metrics (Phased):**

**MVP:**
- Error rate (%)
- Response time (P50, P95)
- Request count
- Database connection pool usage

**Beta:**
- Questions asked per project
- Time to first artifact (median)
- Token usage per LLM call
- User satisfaction (thumbs up/down)

**Production:**
- All of above
- Agent-specific latency (Interrogation, Specification, etc.)
- Cache hit rate (Redis)
- Queue depth (async jobs)
- Cost per user (LLM tokens)

**Dashboards:**
- Real-time system health (Grafana)
- User activity (Mixpanel / Amplitude)
- Cost tracking (LLM spend per project)

---

### 12.4 Incident Response

**On-Call Rotation:**
- 24/7 for production
- PagerDuty for alerts

**Runbooks:**
- "LLM provider down" → failover to backup provider
- "Database slow" → check slow query log, add index
- "High error rate" → check logs, rollback if recent deploy

**Post-Mortems:**
- Required for any incident >15 min downtime
- Document root cause, prevention

---

### 12.5 Maintenance Tasks

**Daily:**
- Backup database (full backup, 30-day retention)
- Integrity checks (orphaned decisions, artifact versions)

**Weekly:**
- Review slow queries, optimize indexes
- Audit log cleanup (delete old logs per retention policy)
- Cost review (LLM token usage)

**Monthly:**
- Security patches (OS, dependencies)
- Rotate secrets (if manual)
- Review rate limits (adjust based on usage)

**Quarterly:**
- Load testing (simulate 10x user growth)
- Disaster recovery drill (restore from backup)

---

## 13. OPEN QUESTIONS & EXPLICIT ASSUMPTIONS

### 13.1 Open Questions (Unresolved)

**Q-OPEN-001: What is the acceptable cost per project?**
- LLM token costs vary widely (Claude: $15/M tokens, GPT-4: $60/M tokens)
- Need to measure actual usage before setting pricing
- **Blocker Level:** Medium (affects pricing model)

**Q-OPEN-002: Should we support self-hosted deployment?**
- Enterprise customers may require air-gapped
- Significantly increases complexity (Docker, K8s, docs, support)
- **Blocker Level:** Low (defer to enterprise tier)

**Q-OPEN-003: How do we handle multi-language codebases with unsupported languages?**
- Example: Monorepo with TypeScript + Rust + Haskell
- Current plan: Skip unsupported, analyze rest
- Alternative: Offer to add language support on request
- **Blocker Level:** Low (edge case)

**Q-OPEN-004: Should artifact comments support rich media (screenshots, videos)?**
- Useful for UI feedback
- Increases storage costs, complexity
- **Blocker Level:** Low (nice-to-have, defer)

**Q-OPEN-005: What's the maximum context window we can support?**
- Claude: 200K tokens, GPT-4: 128K tokens
- Large projects may exceed even with RAG
- Need to test with real projects
- **Blocker Level:** Medium (may limit project size)

---

### 13.2 Explicit Assumptions (Made to Proceed)

**ASSUME-001: LLM hallucination rate is <5%**
- **Basis:** Industry benchmarks for Claude/GPT-4
- **Risk:** High (if >5%, trust erodes)
- **Validation:** Track user-reported hallucinations in beta
- **Mitigation:** Human-in-the-loop for critical paths, fact-checking brownfield

**ASSUME-002: GitHub/GitLab cover 95% of brownfield use cases**
- **Basis:** Market share data
- **Risk:** Low (Bitbucket, self-hosted Git are edge cases)
- **Validation:** Survey beta users
- **Mitigation:** Add Git URL support (covers self-hosted)

**ASSUME-003: Users will tolerate 30s artifact generation**
- **Basis:** Similar tools (Notion AI, GitHub Copilot)
- **Risk:** Medium (impatience may drive churn)
- **Validation:** Track "cancel generation" rate
- **Mitigation:** Show progress bar, stream partial results

**ASSUME-004: Static analysis is sufficient for brownfield architecture derivation**
- **Basis:** 80% of systems have clear structure
- **Risk:** Medium (microservices, dynamic imports may confuse)
- **Validation:** Test on diverse repos in beta
- **Mitigation:** User-guided annotation (fallback)

**ASSUME-005: Email-based invites are acceptable for MVP**
- **Basis:** Standard practice
- **Risk:** Low (some enterprises may require SSO)
- **Validation:** Enterprise customers will request SSO
- **Mitigation:** Add SSO in paid tier

**ASSUME-006: Decision graph visualization scales to 1000 nodes**
- **Basis:** D3.js can handle
- **Risk:** Medium (UX degrades with >500 nodes)
- **Validation:** Test with large projects
- **Mitigation:** Offer filtered/collapsed view

**ASSUME-007: Users will manually resolve merge conflicts (no AI mediation)**
- **Basis:** Git workflow familiar to engineers
- **Risk:** Low (but may frustrate non-technical users)
- **Validation:** Track conflict resolution time
- **Mitigation:** Consider AI-suggested resolution in v2

**ASSUME-008: Vector DB (Pinecone, Weaviate, or similar) is reliable**
- **Basis:** Managed services have 99.9% uptime
- **Risk:** Low
- **Validation:** Monitor downtime
- **Mitigation:** Fallback to full conversation history

**ASSUME-009: Users trust AI-generated test cases**
- **Basis:** Growing acceptance of AI in dev tools
- **Risk:** Medium (critical systems may require human review)
- **Validation:** Track test case adoption rate
- **Mitigation:** Mark AI-generated content clearly, allow edits

**ASSUME-010: Industry best practices are acceptable defaults for "decide for me"**
- **Basis:** Most users follow conventions
- **Risk:** Low (but may not fit niche use cases)
- **Validation:** Track "change default" rate
- **Mitigation:** Allow easy reversal, mark as assumption

---

## 14. IMPLEMENTATION READINESS CHECKLIST

### 14.1 Fully Specified

✅ **Problem definition** (clear, measurable)  
✅ **User personas** (primary, secondary, system actors)  
✅ **Core capabilities** (20+ atomic capabilities with triggers, inputs, outputs, success criteria, failure cases)  
✅ **User journeys** (greenfield, brownfield, collaboration, recovery)  
✅ **System architecture** (components, responsibilities, data flow)  
✅ **Data model** (entities, relationships, constraints, lifecycle, retention)  
✅ **APIs** (REST endpoints, WebSocket events, agent export formats)  
✅ **State management** (states, transitions, concurrency)  
✅ **Non-functional requirements** (performance targets deferred, security/privacy/observability phased)  
✅ **Edge cases & failure modes** (50+ scenarios with handling)  
✅ **Configuration** (environments, feature flags, secrets)  
✅ **Operational considerations** (deployment, rollback, monitoring, incident response, maintenance)  

---

### 14.2 Requires Validation

⚠️ **LLM hallucination rate** (assume <5%, measure in beta)  
⚠️ **Latency targets** (measure real usage, set targets after MVP)  
⚠️ **Cost per project** (measure token usage, adjust pricing)  
⚠️ **Context window limits** (test with large projects, may need enhanced chunking)  
⚠️ **Decision graph UX at scale** (test with >500 nodes, may need filtered views)  
⚠️ **Artifact generation quality** (validate against user expectations, iterate prompts)  
⚠️ **Brownfield architecture derivation accuracy** (test on diverse repos, refine inference)  

---

### 14.3 Can Be Parallelized

**Track A (Backend Core):**
- Auth Service (email/password, magic links, OAuth, 2FA)
- Workspace & Project Management (CRUD APIs)
- Decision graph storage (PostgreSQL schema, Vector DB setup)
- Conversation state management

**Track B (Agent System):**
- Interrogation Agent (question generation, template loading)
- Context Memory Agent (RAG, decision graph querying)
- Specification Agent (artifact generation, checkpointing)
- Validation Agent (contradiction detection, consistency checks)
- Delivery Agent (export formats, AI agent adapters)

**Track C (Brownfield Engine):**
- Codebase ingestion (GitHub OAuth, Git clone)
- Multi-language parsers (Tree-sitter integration)
- Static analysis (dependency graphs, type checking)
- Impact analysis & change planning

**Track D (Frontend):**
- React UI (conversation interface, decision graph viz)
- Artifact viewer/editor
- Diff viewer (inline, red/green)
- WebSocket integration (real-time updates)

**Track E (Infrastructure):**
- Cloud deployment (AWS/GCP setup)
- Database setup (PostgreSQL HA, Redis cluster)
- LLM provider integration (Anthropic, OpenAI, Replicate)
- Monitoring & logging (CloudWatch, Grafana)

---

### 14.4 Blocks Development

🚫 **LLM provider API keys** (need production keys before deploying)  
🚫 **Database schema finalized** (Track A blocks all data operations)  
🚫 **Decision graph structure** (Track B depends on this from Track A)  
🚫 **Agent orchestration protocol** (Track B agents must agree on message format)  
🚫 **Export format specs** (Track B Delivery Agent needs schemas for Cursor, Claude Code, etc.)  

---

## 15. RECOMMENDED IMPLEMENTATION PHASES

### Phase 1: MVP (3-4 months)
**Goal:** Prove core value prop (ambiguity → clarity)

**Scope:**
- Greenfield mode only
- Simple question flow (templates, no dynamic reasoning)
- Generate: PRD, basic tickets (markdown)
- Single user per project (no collaboration)
- Email/password auth only
- Download exports only (no Git integration)
- Basic security (HTTPS, password hashing, SQL injection prevention)
- US-only hosting
- Hard rate limits (50 questions/day, 10 projects)

**Success Criteria:**
- 100 users complete 1 project each
- 80% satisfaction ("would recommend")
- <5% hallucination rate

---

### Phase 2: Collaboration & Quality (2-3 months)
**Goal:** Enable teams, improve artifact quality

**Scope:**
- Workspaces & members (invite via email)
- Branching & merging (Git-style workflow)
- Comments on artifacts (structured feedback)
- Improved artifact generation (Claude + open-source hybrid)
- Export to GitHub Issues, Linear
- Magic links auth
- Decision graph visualization
- Auto-archiving (30 days)

**Success Criteria:**
- 50 teams (3+ members) using collaboration features
- 90% of merges successful without conflicts

---

### Phase 3: Brownfield & Enterprise (3-4 months)
**Goal:** Support legacy systems, attract enterprise

**Scope:**
- Brownfield mode (codebase ingestion, analysis, change plans)
- Multi-language support (JS, TS, Python, Java, Go, C#, PHP)
- Impact analysis & regression test requirements
- SSO (Google Workspace, Okta)
- 2FA (TOTP)
- Multi-region data residency (EU option)
- GDPR compliance
- Paid tier launch

**Success Criteria:**
- 20 brownfield projects completed
- 10 enterprise customers signed

---

### Phase 4: Scale & Intelligence (Ongoing)
**Goal:** Handle large projects, smarter agents

**Scope:**
- Dynamic question generation (goal-oriented reasoning)
- Enhanced context management (RAG improvements)
- Templates (workspace-level, community marketplace)
- Self-hosted option (Docker/K8s)
- Advanced observability (full audit trail, reasoning traces)
- Cost optimization (smarter model routing)

---

## FINAL NOTES

**This specification is engineering-ready for:**
- Backend API development (Track A)
- Agent system implementation (Track B)
- Frontend UI build (Track D)
- Infrastructure setup (Track E)

**Brownfield engine (Track C) can start in Phase 3.**

**All flagged assumptions must be validated in beta. Update spec based on learnings.**

**Open questions should be resolved before Phase 3 (brownfield) begins.**

---

**Document Status:** ✅ Complete  
**Next Step:** Review with engineering team, assign tracks, begin Phase 1 implementation.