# Agentic Spec Builder - UI Design Document

**Document Version:** 1.0  
**Last Updated:** 2026-02-04  
**Status:** UI Design Ready  
**Document Owner:** Frontend Team

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Design System](#2-design-system)
3. [Screen Inventory](#3-screen-inventory)
4. [Component Architecture](#4-component-architecture)
5. [User Flow Diagrams](#5-user-flow-diagrams)
6. [State Management](#6-state-management)
7. [API Integration Requirements](#7-api-integration-requirements)
8. [Accessibility Requirements](#8-accessibility-requirements)
9. [Responsive Design](#9-responsive-design)
10. [Performance Requirements](#10-performance-requirements)
11. [Appendix A: Component Checklist](#appendix-a-component-checklist)
12. [Appendix B: File Structure](#appendix-b-file-structure)
13. [Appendix C: Testing Requirements](#appendix-c-testing-requirements)
14. [Appendix D: Browser Support](#appendix-d-browser-support)

---

## 1. Design Principles

### 1.1 Core UX Principles

The UI design follows these foundational principles to ensure an intuitive and efficient user experience:

**Clarity First**

Every screen has a single, clear purpose. Information hierarchy follows user attention patterns, with primary actions being visually dominant and secondary actions accessible but unobtrusive. Empty states provide guidance and context to help users understand what to do next.

**Progressive Disclosure**

The interface shows only what is needed at each step, with advanced options revealed on demand. Contextual help is available throughout the application, and keyboard shortcuts power users can discover. Complexity is managed through organization rather than being hidden away.

**Feedback and Response**

All actions receive immediate visual feedback to keep users informed. Loading states are clear and informative, errors are descriptive and provide recovery paths, and success states confirm completion clearly. Long-running operations show progress indicators to manage expectations.

**Consistency**

Similar actions use similar patterns across the entire UI. Terminology is consistent throughout the application, visual patterns repeat for similar functions, and navigation follows predictable patterns. User mental models are respected and reinforced with each interaction.

**User Agency**

Users can undo or reverse most actions, and confirmation is required for destructive operations. Auto-save prevents data loss without requiring user action, users control their pace through the system, and clear escape routes are provided from any path.

### 1.2 Accessibility Principles

**Perceivable**

All non-text content has text alternatives for screen readers. Color is not the only means of conveying information, with icons and text labels supplementing color cues. Text has sufficient contrast following WCAG AA standards with 4.5:1 ratio for body text and 3:1 ratio for large text. Content can be resized without loss of functionality, and media can be paused, stopped, or adjusted by users.

**Operable**

All functionality is keyboard accessible with visible focus states. No content causes seizures or physical reactions. Users have enough time to read and use content without pressure. Navigation is consistent and predictable throughout the application.

**Understandable**

Text is readable and understandable at appropriate reading levels. Content appears and operates in predictable ways. Users are helped to avoid and correct mistakes with clear error messages and undo capabilities. Input assistance is available throughout the forms and inputs.

**Robust**

Content is compatible with assistive technologies. Standard HTML elements are used where possible for maximum compatibility. ARIA attributes are used correctly on custom components. Name, role, and value are properly exposed for all custom interactive components.

---

## 2. Design System

### 2.1 Color Palette

#### Primary Colors

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| Primary 900 | #0D1B2A | 13, 27, 42 | Text on light backgrounds, headers |
| Primary 800 | #1B263B | 27, 38, 59 | Primary text, dark borders |
| Primary 700 | #415A77 | 65, 90, 119 | Secondary text, icons |
| Primary 600 | #778DA9 | 119, 141, 169 | Muted text, disabled states |
| Primary 500 | #E0E1DD | 224, 225, 221 | Page backgrounds, cards |
| Primary 400 | #FFFFFF | 255, 255, 255 | White backgrounds, text on dark |

#### Accent Colors

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| Accent Blue | #3B82F6 | 59, 130, 246 | Primary buttons, links, active states |
| Accent Green | #10B981 | 16, 185, 129 | Success states, confirmations |
| Accent Yellow | #F59E0B | 245, 158, 11 | Warning states, attention |
| Accent Red | #EF4444 | 239, 68, 68 | Error states, destructive actions |
| Accent Purple | #8B5CF6 | 139, 92, 246 | AI/agent indicators, premium features |

#### Semantic Colors

| Usage | Color | CSS Variable |
|-------|-------|--------------|
| Success | Green | `--color-success` |
| Warning | Yellow | `--color-warning` |
| Error | Red | `--color-error` |
| Info | Blue | `--color-info` |
| Decision Category - Auth | Purple | `--category-auth` |
| Decision Category - Database | Blue | `--category-database` |
| Decision Category - API | Green | `--category-api` |
| Decision Category - UI | Orange | `--category-ui` |
| Decision Category - Deployment | Teal | `--category-deployment` |
| Decision Category - Security | Red | `--category-security` |

### 2.2 Typography

#### Font Family

```css
:root {
  --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
}
```

#### Type Scale

| Level | Font Size | Line Height | Letter Spacing | Usage |
|-------|-----------|-------------|----------------|-------|
| Display | 48px / 3rem | 1.1 | -0.02em | Hero headlines |
| H1 | 36px / 2.25rem | 1.2 | -0.01em | Page titles |
| H2 | 30px / 1.875rem | 1.25 | 0 | Section headings |
| H3 | 24px / 1.5rem | 1.3 | 0 | Subsection headings |
| H4 | 20px / 1.25rem | 1.4 | 0 | Component headings |
| Body Large | 18px / 1.125rem | 1.5 | 0 | Lead paragraphs |
| Body | 16px / 1rem | 1.5 | 0 | Body text |
| Body Small | 14px / 0.875rem | 1.5 | 0 | Secondary text |
| Caption | 12px / 0.75rem | 1.4 | 0.04em | Labels, metadata |
| Code | 14px / 0.875rem | 1.5 | 0 | Code snippets |

### 2.3 Spacing Scale

```css
:root {
  --space-0: 0;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
}
```

### 2.4 Border Radius

```css
:root {
  --radius-none: 0;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;
}
```

### 2.5 Shadows

```css
:root {
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
}
```

### 2.6 Component Variants

#### Buttons

| Variant | Background | Text | Border | Usage |
|---------|-------------|------|--------|-------|
| Primary | Accent Blue | White | None | Main actions |
| Secondary | Primary 500 | Primary 800 | 1px solid Primary 600 | Secondary actions |
| Ghost | Transparent | Accent Blue | None | Tertiary actions |
| Danger | Accent Red | White | None | Destructive actions |
| Icon | Transparent | Primary 700 | None | Icon-only buttons |
| Disabled | Primary 500 | Primary 600 | None | Disabled state |

#### Input Fields

| State | Border | Icon | Message |
|-------|--------|------|---------|
| Default | Primary 600 | None | None |
| Focus | Accent Blue | None | None |
| Error | Accent Red | Error icon | Error message |
| Success | Accent Green | Check icon | None |
| Disabled | Primary 500 | None | Helper text |

### 2.7 Animation Tokens

```css
:root {
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 3. Screen Inventory

### 3.1 Authentication Screens

#### 3.1.1 Login Screen

**Route:** `/login`

**Purpose:** Authenticate existing users into the system

**Layout:** Centered card on neutral background

**Elements:**

The login screen features the product logo and name at the top. The main form includes an email input field with built-in validation for format checking, a password input field with a show/hide toggle for accessibility, and a remember me checkbox for session persistence. A forgot password link is provided for password recovery. The primary call to action is a large login button with loading state. A visual divider with the word "or" separates the main form from alternative authentication methods. OAuth buttons for Google, GitHub, and Microsoft are displayed for users who prefer social login. A link to the signup page is provided for new users.

**User Actions:**

Users can enter their credentials and submit the form, click on an OAuth provider to initiate social authentication, click the forgot password link to initiate password recovery, or navigate to the signup page for account creation.

**Error States:**

The interface handles invalid email format, incorrect password, account lockout due to multiple failed attempts, and network connectivity issues.

**Responsive Behavior:**

On mobile devices, inputs span the full width and OAuth buttons stack vertically. On desktop, the card is constrained to 400px wide with side-by-side OAuth buttons.

#### 3.1.2 Signup Screen

**Route:** `/signup`

**Purpose:** Create a new user account

**Layout:** Centered card on neutral background

**Elements:**

The signup form collects the user's full name, email address, password with real-time strength indicator, and password confirmation. A checkbox for accepting terms of service is required. The signup button is the primary call to action. Social authentication options are provided below the form, and a link to the login page is available for existing users.

**Validation:**

Name requires at least 2 characters. Email must be in valid format. Password requires 8+ characters with mixed case, number, and special character. Password confirmation must match the original password exactly.

#### 3.1.3 Forgot Password Screen

**Route:** `/forgot-password`

**Purpose:** Initiate password reset flow

**Layout:** Centered card

**Elements:**

A heading invites users to reset their password, followed by descriptive text explaining the process. An email input field accepts the user's registered email address. A send reset link button triggers the password reset email. A back to login link provides a return path.

**States:**

The initial state displays the email input. A loading state shows a spinner on the button during email sending. A success state displays a confirmation message with the email address to which the reset link was sent. An error state appears if the email is not found in the system.

#### 3.1.4 Magic Link Screen

**Route:** `/magic-link`

**Purpose:** Passwordless authentication via email

**Layout:** Centered card

**Elements:**

A heading indicates the user should check their email. The email input field is pre-filled if arriving from the login screen. A send magic link button initiates the passwordless authentication flow. A back to login link is provided.

---

### 3.2 Workspace Screens

#### 3.2.1 Workspace List Screen

**Route:** `/workspaces`

**Purpose:** Display and manage user's workspaces

**Layout:** Sidebar navigation with main content grid

**Sidebar Elements:**

The user avatar and name appear at the top of the sidebar. A workspace switcher dropdown allows quick navigation between workspaces. Main navigation items include Projects and Settings. A secondary navigation includes Members. A prominent create new workspace button is available. The user menu at the bottom provides access to Profile, Billing, and Logout options.

**Main Content Elements:**

The page header displays the title with action buttons. Workspace cards are arranged in a responsive grid (1-3 columns based on screen width). An empty state with a creation call-to-action is shown when no workspaces exist.

**Workspace Card Elements:**

Each card displays the workspace name, owner avatar, member count badge, project count badge, role badge indicating the current user's permission level, and a last activity timestamp. A menu provides access to edit, delete, and settings options.

#### 3.2.2 Create Workspace Modal

**Purpose:** Create a new workspace

**Modal Elements:**

A modal header announces "Create Workspace". A name input field collects the workspace name. A description textarea allows optional entry of workspace purpose. A template selector offers Personal, Team, or Enterprise options. Cancel and Create buttons are provided.

**Validation:** Workspace name requires at least 3 characters and must be unique.

#### 3.2.3 Workspace Settings Screen

**Route:** `/workspaces/:id/settings`

**Purpose:** Configure workspace settings

**Layout:** Settings page with sidebar navigation

**Sidebar Sections:**

General settings, Members management, Billing information, Integrations with external services, and a Danger Zone for sensitive operations.

**General Tab:**

Editable workspace name, read-only workspace slug, optional description textarea, default branch protection toggle, validation strictness dropdown with minimal/standard/strict options, auto-archive days input, and a save button.

**Members Tab:**

A member list table displays name, email, role, and status for each member. An invite member button opens the invitation flow. Per-member role selectors and remove member buttons are available. A pending invites section shows outstanding invitations.

**Billing Tab:**

Current plan display with upgrade or downgrade options. Usage statistics showing projects, questions, and artifacts usage. Payment method management link.

**Integrations Tab:**

GitHub connection status with connect/disconnect button. GitLab connection status with connect/disconnect button. Connected accounts list.

**Danger Zone:**

A prominent delete workspace button with confirmation dialog.

---

### 3.3 Project Screens

#### 3.3.1 Project List Screen

**Route:** `/workspaces/:id/projects`

**Purpose:** Display and manage projects in a workspace

**Layout:** Standard page with filters and list

**Header Elements:**

Page title "Projects", create new project button, search input field, filter dropdown for All/Active/Paused/Archived/Completed status, sort dropdown for Last Activity/Created/Name ordering, and a view toggle between grid and list layouts.

**Main Content Elements:**

Project cards arranged in grid or list view. An empty state with creation call-to-action displays when no projects exist.

**Project Card Elements:**

Project name, type badge (Greenfield or Brownfield), status badge (Active/Paused/Archived/Completed), decision count, artifact count, last activity timestamp, team member avatars, and quick action buttons for Open, Edit, Archive, and Delete.

**List View Additional Elements:**

Project description, creator information, and branch count.

#### 3.3.2 Create Project Flow

**Purpose:** Initialize a new project with guided steps

**Layout:** Multi-step modal or full-page wizard

**Step 1: Project Type Selection**

A heading announces "Create a New Project". Two large cards present the options:

The Greenfield card features a blank canvas icon and description "Create specifications for new software" with a select button.

The Brownfield card features a code icon and description "Generate change plans for existing systems" with a select button.

**Step 2: Basic Info (Greenfield)**

Project name input field. Description textarea (optional). Template selector with options: SaaS Web Application (default), REST API Service, Mobile App, and Custom.

Time investment selector with options: Quick (30 min), Standard (2 hours), Comprehensive (unlimited).

Upload area for supporting documentation (optional drag-and-drop and file selection).

**Step 2: Codebase Connection (Brownfield)**

Project name input field. Source selector with options: GitHub (triggers OAuth flow with repository picker), GitLab (triggers OAuth flow with repository picker), Git URL (text input for repository URL), and Zip Upload (file upload interface).

For GitHub/GitLab: OAuth flow initiates with repository selection modal.

For Git URL: URL input field accepts repository address.

Change intent selector with options: Add feature, Optimize, Fix bug, Refactor, Migrate, Modernize.

Scope selection (optional): Directory picker interface for specifying which parts of the codebase to analyze.

**Step 3: Review and Create**

Summary of all selections displayed for review. Pricing estimate shown if applicable. Create project button initiates project creation.

#### 3.3.3 Project Detail Screen

**Route:** `/projects/:id`

**Purpose:** Main workspace for working on a project

**Layout:** Full application shell with sidebar tabs

**Header Elements:**

Breadcrumb navigation showing Workspace > Project Name. Project status badge. Project menu with Edit, Archive, Delete, and Export options. Share button for collaboration. Branch selector dropdown.

**Main Navigation Tabs:**

Conversation (default), Decisions, Artifacts, and Analysis (brownfield only).

**Content Area:** Changes dynamically based on the selected tab.

---

### 3.4 Conversation Screens

#### 3.4.1 Conversation Interface

**Route:** `/projects/:id/conversation`

**Purpose:** Interactive question-answering interface

**Layout:** Main conversation area with question panel

**Conversation Stream (Left/Main):**

Question bubbles displayed from the AI agent. Answer bubbles showing user responses. Timestamps for each conversation turn. Loading indicators during AI processing. Continue button when ready for next question.

**Question Panel (Right):**

Current question card prominently displayed. Question text in large, readable font. Category badge identifying the decision type. Answer options in appropriate format (radio buttons, checkboxes, text input, or form fields). Context and rationale explaining why this question matters.

**Question Card Elements:**

Question text prominently displayed. Category icon and label. Context/rationale section explaining the importance of this decision. Options list with appropriate input type: Radio buttons for single choice, Checkboxes for multiple choices, Text input for free-form responses, Form fields for structured answers.

An "Other" option with text field allows custom answers. A defer button (park icon) moves the question to parked state. An "AI Decide" button (lightning icon) requests the system to make a default decision.

**Progress Indicator:**

Shows questions answered versus total required. Questions pending for each artifact type (PRD, API Contract, etc.). Visual progress bar indicating overall completion percentage.

**User Actions:**

Users can select one or more options, type free-form text, click defer to park the question, or click AI decide for automatic resolution.

**Validation Feedback:**

Inline validation confirms inputs are valid. Contradiction alerts appear if the answer conflicts with previous decisions. Success confirmation appears on successful submission.

**Contradiction Detection UI:**

A warning alert banner announces "Potential contradiction detected". A side-by-side comparison shows the previous decision (from the decision graph) and the current answer being submitted. Resolution options include keeping the previous answer, using the new answer, or editing both answers. An acknowledgment checkbox confirms the user understands the conflict.

#### 3.4.2 Pending Questions Screen

**Purpose:** View and manage all pending questions

**Layout:** Sidebar panel or full-page list

**Sections:**

Blocking Questions section lists decisions required for the next artifact. By Artifact section organizes questions by target output type (PRD, API, Schema, etc.). Parked Questions section displays deferred questions. Optional Questions section shows nice-to-have but non-blocking decisions.

**Each Question Card:**

Question text preview. Category badge. Blocking status indicator. Artifact dependencies list. Answer button. Defer button.

**User Actions:**

Click to answer directly from the list. Click defer to park again. Filter by category or blocking status.

#### 3.4.3 Deferred Questions Panel

**Purpose:** Manage parked questions

**Layout:** Drawer or modal

**Elements:**

List of deferred questions with original context. Each question displays the question text, the context when it was deferred, a resurface button to return to conversation, and a delete button to remove permanently. A "Resurface All" button returns all deferred questions to the conversation.

---

### 3.5 Decision Graph Screens

#### 3.5.1 Decision Graph View

**Route:** `/projects/:id/decisions`

**Purpose:** Visualize and navigate all project decisions

**Layout:** Full-page interactive graph

**Graph Visualization (Main):**

Force-directed or tree graph rendering. Nodes represent decisions with color-coding by category. Edges show dependencies between decisions with arrows indicating relationships. Node interactions include click to open decision detail panel, hover to show tooltip with summary, and drag to reposition nodes. Zoom and pan controls are available. A fit to view button resets the display.

**Control Bar (Top):**

View selector with Graph, List, and Timeline options. Filter by category with multi-select dropdown. Filter by status with answered/pending/deferred options. Search input for finding specific decisions. Export button for PNG, SVG, or JSON formats.

**Decision Detail Panel (Side/Modal):**

Decision question, selected answer, category, dependencies, answered by and timestamp, history and version list, edit button, lock button (for protected branches), and comments count.

**List View Alternative:**

Searchable and sortable table with columns for Question, Answer, Category, Dependencies, Answered By, and Actions. Bulk actions for export and archive.

**Timeline View Alternative:**

Chronological display with grouping by date. Filtering by user. Expandable details for each decision.

#### 3.5.2 Decision Detail Modal

**Purpose:** View and edit a single decision

**Modal Elements:**

Decision question displayed read-only in answered state. Selected answer shown (or current selection in editable state). Answered by avatar and name with timestamp. Category badge. Dependencies section listing dependent decisions. History dropdown showing version list with dates and authors. Diff view comparing any two versions. Rollback to version button. Lock decision toggle. Comments section at the bottom.

**History View:**

Version timeline with each version displaying answer text, author, timestamp, and reason for change (if provided). Click any version to view the complete diff. Rollback option available for any previous version.

---

### 3.6 Artifact Screens

#### 3.6.1 Artifact List

**Route:** `/projects/:id/artifacts`

**Purpose:** Display all generated artifacts

**Layout:** Cards grid or list view

**Header:**

"Artifacts" title. Generate new artifact button. Filter dropdown for All/By Type/By Status. Sort dropdown for Generated/Updated/Type ordering.

**Artifact Cards:**

Type icon and name (PRD, Schema, API Contract, etc.). Format badge (Markdown, PDF, OpenAPI, etc.). Version number. Status indicator: Complete (green), Stale (yellow), Generating (blue). Generated timestamp. Based on decisions count. Stale indicator with regenerate button. Actions: View, Export, Edit, Delete.

**Stale Artifacts Section:**

Highlighted section showing artifacts that need regeneration. "Regenerate All" button available. Per-artifact regenerate buttons with individual confirmation.

#### 3.6.2 Artifact Viewer

**Route:** `/artifacts/:id`

**Purpose:** View and interact with artifact content

**Layout:** Split view with preview and metadata

**Header:**

Artifact title and type. Version selector dropdown. Download button. Export button. Regenerate button (if stale). Close button.

**Preview Area (Main):**

Markdown or HTML renderer with syntax highlighting for code blocks. Table of contents sidebar for navigation through long documents. Section numbers for easy reference. Copy code button for code snippets. Image zoom capability.

**Metadata Panel (Right):**

Generated by agent indicator. Generated timestamp. Based on decisions list (each clickable to view decision). Tech stack information. Format details. Version history dropdown. Comments section.

**Toolbar:**

Find in page functionality. Zoom controls for PDF and images. Fullscreen toggle. Print button. Share link button.

#### 3.6.3 Artifact Export Modal

**Purpose:** Export artifact in various formats

**Modal Elements:**

Title "Export Artifact". Format selection grid with descriptions:

Markdown: Download .md file for documentation. HTML: Download .html file for web publishing. PDF: Download .pdf file for printing. JSON: Download structured data file. OpenAPI: Download .yaml file for API contracts (specific to API Contract artifacts).

GitHub Issues: Copy JSON formatted for GitHub import. Linear: Copy JSON formatted for Linear import. Cursor: Download .json file for Cursor AI agent. Claude Code: Download .md file with YAML frontmatter for Claude Code. Aider: Download .yaml file for Aider AI agent.

Format details section provides descriptions, example usage, and any required settings. Export button shows progress and provides download link on success.

#### 3.6.4 Artifact Version Diff View

**Purpose:** Compare artifact versions

**Layout:** Side-by-side diff view

**Header:**

Artifact name. Version selectors for "From" and "To" versions. View options: Inline or Split toggle. Export diff button.

**Diff Display:**

Green highlights for additions. Red highlights for deletions. Gray highlighting for unchanged content. Line numbers for reference. Chunk navigation with previous/next buttons.

**Summary Statistics:**

Lines added count. Lines deleted count. Total changes count.

#### 3.6.5 Artifact Generation Modal

**Purpose:** Request new artifact generation

**Modal Elements:**

Title "Generate Artifact". Artifact type selector with options: PRD, Database Schema, API Contract, Engineering Tickets, Architecture Diagram, Test Cases, Deployment Plan, Change Plan (brownfield).

Format selector with multi-select for Markdown, HTML, PDF, JSON, OpenAPI, YAML, Gherkin, Mermaid, and other applicable formats.

Tech stack section auto-filled from project settings but editable with fields for Backend language, Frontend language, Database, and Frameworks.

Required decisions missing section lists blocking decisions with options to generate them first. Estimated generation time displayed. Generate and Cancel buttons.

---

### 3.7 Artifact Comment Screens

#### 3.7.1 Comments Panel

**Purpose:** View and add comments on artifacts

**Layout:** Sidebar panel or inline annotations

**Comments List:**

Each comment displays user avatar and name. Timestamp showing when comment was made. Section reference if the comment is attached to a specific part of the artifact. Comment type badge: Question (blue), Issue (red), Suggestion (green), Approval (purple). Comment text content. Reply button to respond to the thread. Resolve button (for issues and questions). Actions menu with edit and delete options.

**Thread Structure:**

Main comments displayed at top level. Replies indented below parent comments. Collapsible threads for long discussions. Reply form at bottom of each thread.

**Add Comment Form:**

Section selector (optional) for attaching comment to specific artifact section. Type selector for Question, Issue, Suggestion, or Approval. Text area for comment content. Submit and Cancel buttons.

**Comment Type Behavior:**

Questions and Issues trigger agent re-questioning to address the concern. Suggestions are logged for manual review by project owners. Approvals mark the section as reviewed and can lock sections based on workspace settings.

**Filter and Sort:**

Filter by comment type (Question/Issue/Suggestion/Approval). Filter by resolved status (all/resolved/unresolved). Sort by date or relevance.

---

### 3.8 Branching Screens

#### 3.8.1 Branch Selector

**Location:** Project header

**Purpose:** Select and manage branches

**Elements:**

Current branch name displayed. Dropdown arrow to expand the list. Branch list on click showing Main branch (with protected indicator), Feature branches, and Merge status indicators. Create Branch option in the dropdown. Search input for finding branches.

**Branch List Item:**

Branch name. Decision count in branch. Last activity timestamp. Protection status (shield icon for protected). Merge status (merged checkmark, conflict warning, or active indicator). Actions: Switch to branch, Create PR, Delete.

#### 3.8.2 Create Branch Modal

**Purpose:** Create a new feature branch

**Modal Elements:**

Title "Create Branch". Branch name input with Git-compatible validation and auto-prefix suggestion. Parent branch selector (defaults to current branch). Description textarea (optional). Toggle for copying decisions from parent (default: yes). Create and Cancel buttons.

**Branch Name Validation:**

Git-compatible names only (no spaces, special characters limited). Auto-prefix with "feature/" if not present. Validation feedback for invalid names.

#### 3.8.3 Branch Merge Screen

**Purpose:** Review and merge branches

**Layout:** Multi-section review page

**Header:**

Source branch name. Arrow icon indicating direction. Target branch name. Merge button (if no conflicts). Resolve Conflicts button (if conflicts exist).

**Changes Summary:**

Decisions added count. Decisions modified count. Artifacts affected count. No conflicts indicator (green check) or Conflicts detected indicator (red warning).

**Conflicts Section (when conflicts exist):**

List of conflicting decisions. Each conflict displays the question text, source answer (from feature branch), and target answer (from main branch). Resolution options: Keep source, Keep target, or Custom answer.

**Diff View:**

Side-by-side comparison of conflicting decisions. Highlighted differences. Navigation between conflicts.

**Merge Actions:**

Merge with Conflicts button. Cancel button. Optional comment input for merge commit message.

#### 3.8.4 Branch List Screen

**Route:** `/projects/:id/branches`

**Purpose:** Manage all project branches

**Layout:** Table or card list

**Header:**

"Branches" title. Create Branch button. Filter: All, Active, Merged. Search branches input.

**Branch Table Columns:**

Name (sortable). Status (Active/Merged/Conflict with badge colors). Decisions count. Created by user. Created timestamp. Last activity timestamp. Actions dropdown.

**Status Badges:**

Active (blue), Merged (green), Conflict (red).

**Actions per Branch:**

Switch to branch. View decisions in branch. Create merge request. Delete (if not protected, not main).

---

### 3.9 Brownfield Analysis Screens

#### 3.9.1 Analysis Dashboard

**Route:** `/projects/:id/analysis`

**Purpose:** View codebase analysis results

**Layout:** Dashboard with multiple panels

**Header:**

"Codebase Analysis" title. Re-analyze button. Analysis status indicator.

**Summary Cards:**

Repository URL with link. Total lines of code. Languages detected with percentages. Architecture type inferred. Analysis date and duration.

**Architecture Section:**

Architecture diagram in Mermaid C4 format. Component inventory list showing services, modules, and their relationships. Dependency graph visualization. "Confirm/Edit Architecture" button.

**Components Panel:**

List of components with Name, Path, Language, Dependencies count, and Dependencies list. Click component for detailed view.

**Languages Panel:**

Language distribution chart (bar or pie). LOC per language breakdown. File counts.

**User Actions:**

Click component for detailed information. Click architecture diagram to expand. Click confirm/edit to verify or modify the inferred architecture. Click re-analyze to run a fresh analysis.

#### 3.9.2 Impact Analysis Screen

**Purpose:** View impact of proposed changes

**Layout:** Report format

**Header:**

"Impact Analysis" title. Change description input field. Analyze button.

**Summary Section:**

Files to create count. Files to modify count. Files to delete count. Overall risk level with explanation: Low (green), Medium (yellow), High (orange), Critical (red).

**Files Section (Tabbed Interface):**

Create tab listing new files to create with path and rationale. Modify tab listing existing files to change with path, change type, and risk per file. Delete tab listing files to remove with path and impact warning.

**Risk Assessment:**

Risk level with detailed explanation. Breaking changes list with affected APIs or interfaces. Affected features list. Downstream dependencies with impact level.

**Tests Impact:**

Tests that need modification. New tests required. Regression test suite checklist.

#### 3.9.3 Change Plan Screen

**Purpose:** View and export detailed change plan

**Layout:** Document format

**Sections:**

Overview with change summary and risk level. Git Workflow section with branch name suggestion, commit sequence with conventional commits, and PR template.

Detailed Procedure with numbered steps, each including step number, description, code snippets, rationale, and warnings.

Rollback Procedure with numbered steps to undo changes if needed. Feature Flag Strategy with recommendations and rollout plan. Test Requirements section with Gherkin scenarios, manual QA checklist, and coverage targets.

**Export Options:**

Download as Markdown. Export to GitHub Issues. Export to Linear.

---

### 3.10 Settings Screens

#### 3.10.1 User Profile Screen

**Route:** `/settings/profile`

**Purpose:** Manage user account settings

**Layout:** Settings page

**Sections:**

Profile Information with avatar upload, name input, email input (read-only if OAuth account), and bio textarea.

Password section with current password, new password, and confirm password inputs, plus update password button.

Two-Factor Authentication showing status (Enabled/Disabled) with Enable/Disable button, QR code display when enabling, and backup codes display.

Connected Accounts listing connected OAuth providers with connect/disconnect buttons.

Danger Zone with Delete Account button and confirmation dialog.

#### 3.10.2 Notifications Settings

**Route:** `/settings/notifications`

**Purpose:** Configure notification preferences

**Sections:**

Email Notifications for Project updates (all/important/none), Comments and mentions (all/none), Artifact ready (all/none), and Weekly digest (on/off).

In-App Notifications for Question ready (on/off), Artifact progress (on/off), Branch updates (on/off), and Team activity (on/off).

Notification Schedule with Do not disturb toggle and Start/End time pickers.

---

### 3.11 Empty States and Onboarding

#### 3.11.1 First Project Empty State

**Purpose:** Guide users to create their first project

**Layout:** Centered message with illustration

**Elements:**

Illustration or icon representing project creation. Heading "Create Your First Project". Description text explaining the value proposition. Primary CTA button "Create Project". Secondary CTA button "Watch Demo". Links to Documentation and Examples.

#### 3.11.2 First Question Empty State

**Purpose:** Welcome users to the conversation

**Layout:** Centered message in conversation area

**Elements:**

"Welcome to your project!" heading. Brief explanation of the process. "Let's get started" button. Tips for effective specification.

#### 3.11.3 First Decision Empty State

**Purpose:** Celebrate first completed decision

**Layout:** Toast or banner notification

**Elements:**

Success icon. "First decision made!" message. "X more to go for your first artifact" progress indicator. Continue button.

#### 3.11.4 First Artifact Empty State

**Purpose:** Celebrate first artifact generation

**Layout:** Modal or celebration screen

**Elements:**

Confetti animation. "Your first artifact is ready!" heading. Preview of the generated artifact. Export options. "Generate Another" button. "Share Success" button for social sharing.

---

## 4. Component Architecture

### 4.1 Component Hierarchy

```
App (App.tsx)
├── Router
│   ├── AuthLayout
│   │   ├── LoginPage
│   │   ├── SignupPage
│   │   └── ForgotPasswordPage
│   └── MainLayout
│       ├── Header
│       │   ├── Logo
│       │   ├── Breadcrumb
│       │   ├── ProjectMenu
│       │   └── UserMenu
│       ├── Sidebar
│       │   ├── WorkspaceSwitcher
│       │   ├── MainNav
│       │   └── SecondaryNav
│       └── PageContainer
│           ├── WorkspaceListPage
│           ├── WorkspaceSettingsPage
│           ├── ProjectListPage
│           ├── ProjectDetailPage
│           │   ├── ConversationView
│           │   │   ├── ConversationStream
│           │   │   │   └── ConversationTurn
│           │   │   ├── QuestionPanel
│           │   │   │   └── QuestionCard
│           │   │   └── ProgressIndicator
│           │   ├── DecisionGraphView
│           │   │   ├── GraphVisualization
│           │   │   └── DecisionDetail
│           │   ├── ArtifactListView
│           │   │   ├── ArtifactCard
│           │   │   └── GenerateArtifactModal
│           │   ├── ArtifactViewer
│           │   │   ├── ArtifactPreview
│           │   │   ├── MetadataPanel
│           │   │   └── ExportModal
│           │   ├── AnalysisDashboard
│           │   │   ├── ArchitectureDiagram
│           │   │   └── ComponentList
│           │   ├── BranchView
│           │   │   ├── BranchList
│           │   │   └── MergeView
│           │   └── CommentsPanel
│           └── SettingsPage
│               ├── ProfileSettings
│               ├── NotificationsSettings
│               └── BillingSettings
└── SharedComponents
    ├── Button
    ├── Input
    ├── Select
    ├── Modal
    ├── Toast
    ├── Avatar
    ├── Badge
    ├── Card
    ├── Dropdown
    ├── Tooltip
    ├── LoadingSpinner
    ├── EmptyState
    └── ErrorBoundary
```

### 4.2 Shared Components

#### Button Component

```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'icon';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  iconPosition?: 'left' | 'right';
  fullWidth?: boolean;
  onClick?: () => void;
  children: ReactNode;
}
```

#### Input Component

```typescript
interface InputProps {
  label?: string;
  placeholder?: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'search';
  value: string;
  onChange: (value: string) => void;
  error?: string;
  helperText?: string;
  disabled?: boolean;
  required?: boolean;
  icon?: ReactNode;
  iconPosition?: 'left' | 'right';
}
```

#### Modal Component

```typescript
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  showCloseButton?: boolean;
  closeOnOverlayClick?: boolean;
  closeOnEscape?: boolean;
  children: ReactNode;
}
```

#### Card Component

```typescript
interface CardProps {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
  onClick?: () => void;
  children: ReactNode;
}
```

#### Badge Component

```typescript
interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md' | 'lg';
  icon?: ReactNode;
  children: ReactNode;
}
```

### 4.3 Feature Components

#### QuestionCard Component

```typescript
interface QuestionCardProps {
  question: Question;
  onAnswer: (answer: Answer) => void;
  onDefer: () => void;
  onAIDecide: () => void;
  isCurrent?: boolean;
}
```

**Internal State:** Selected options, custom input value, validation errors.

#### ConversationStream Component

```typescript
interface ConversationStreamProps {
  turns: ConversationTurn[];
  onContinue?: () => void;
  loading?: boolean;
}
```

#### GraphVisualization Component

```typescript
interface GraphVisualizationProps {
  nodes: DecisionNode[];
  edges: DependencyEdge[];
  onNodeClick?: (node: DecisionNode) => void;
  onNodeHover?: (node: DecisionNode) => void;
  selectedNodeId?: string;
  highlightedNodeIds?: string[];
  showFilters?: boolean;
}
```

**Libraries:** D3.js for graph rendering. Zoom/Pan behavior with mouse and touch support. Collision detection for node positioning.

#### ArtifactPreview Component

```typescript
interface ArtifactPreviewProps {
  artifact: Artifact;
  format: 'markdown' | 'html' | 'pdf';
  onFormatChange?: (format: string) => void;
  showMetadata?: boolean;
}
```

### 4.4 Custom Hooks

```typescript
// Authentication
useAuth() -> { user, login, logout, isAuthenticated }

// Projects
useProjects(workspaceId) -> { projects, loading, error, create, update, delete }
useProject(projectId) -> { project, loading, error, update }

// Decisions
useDecisions(projectId) -> { decisions, graph, loading, error, answer, update }
useQuestion(projectId) -> { currentQuestion, submitAnswer, loading }

// Artifacts
useArtifacts(projectId) -> { artifacts, loading, error, generate, export }
useArtifact(artifactId) -> { artifact, loading, error, regenerate }

// WebSocket
useRealtime(projectId) -> { connection, subscribe, events }

// Graph
useDecisionGraph(projectId) -> { nodes, edges, loading, operations }

// Branches
useBranches(projectId) -> { branches, currentBranch, create, merge }

// Analysis
useAnalysis(projectId) -> { analysis, loading, reAnalyze, impactAnalysis }
```

### 4.5 State Management

**Global State (Context/Redux):** Authentication state, current workspace, current project, user preferences, theme settings.

**Server State (React Query):** Projects list, decisions, artifacts, users/members, branches, analysis results.

**Local State (useState/useReducer):** UI state (modals, drawers), form state, filter/sort preferences, temporary selections.

---

## 5. User Flow Diagrams

### 5.1 Greenfield Project Creation Flow

```
User lands on dashboard
         │
         ▼
Click "Create Project"
         │
         ▼
Select "Greenfield"
         │
         ▼
Enter project details:
- Name
- Description (optional)
- Template selection
- Time investment
- Upload docs (optional)
         │
         ▼
Review & confirm
         │
         ▼
Project created
System loads first question
         │
         ▼
User sees welcome screen
         │
         ▼
Start answering questions
```

### 5.2 Question Answering Flow

```
Current question displayed
         │
         ▼
User reviews question
    ├─► Select option(s)
    ├─► Enter free text
    ├─► Click "Ask later"
    └─► Click "Decide for me"
         │
         ▼
Submit answer
         │
         ▼
Validation check
    ├─► Invalid input ──► Show error ──► User corrects
    │
    └─► Valid input
         │
         ▼
Contradiction check
    ├─► Contradiction detected
    │        │
    │        ▼
    │   Show conflict resolution UI
    │        │
    │        ▼
    │   User resolves conflict
    │        │
    └──────┴──────►
                 │
                 ▼
         Save decision
         (show success)
                 │
                 ▼
         Next question loaded
         (show progress)
```

### 5.3 Artifact Generation Flow

```
User clicks "Generate"
         │
         ▼
Select artifact type
         │
         ▼
Select format(s)
         │
         ▼
Tech stack auto-filled
(User can override)
         │
         ▼
Check dependencies
    ├─► Missing dependencies
    │        │
    │        ▼
    │   Show blocker list
    │        │
    │        ▼
    │   Option: Generate dependencies first
    │        │
    │        └──────► Return to questions
    │
    └─► All dependencies met
         │
         ▼
Start generation
Show progress
         │
         ├─► Progress updates
         │
         ├─► Partial completion ──► Save checkpoint
         │
         └─► Complete
              │
              ▼
         Show success
         Display artifact
         │
         ▼
User actions:
    ├─► View artifact
    ├─► Export
    └─► Generate another
```

### 5.4 Brownfield Analysis Flow

```
User selects "Brownfield"
         │
         ▼
Connect codebase
    ├─► GitHub OAuth ──► Select repo
    ├─► GitLab OAuth ──► Select repo
    ├─► Git URL ──► Enter URL
    └─► Zip Upload
         │
         ▼
Select scope (optional)
         │
         ▼
Select change intent
         │
         ▼
Start analysis
Show progress indicator
         │
         ├─► Cloning repo
         ├─► Detecting languages
         ├─► Parsing code
         ├─► Building dependency graph
         └─► Inferring architecture
         │
         ▼
Analysis complete
Display results:
    ├─► Architecture diagram
    ├─► Component inventory
    ├─► Language breakdown
    └─► Dependency graph
         │
         ▼
User reviews and confirms
         │
         ▼
System asks follow-up questions
         │
         ▼
User answers scope questions
         │
         ▼
Generate impact analysis
         │
         ▼
Display impact report
         │
         ▼
Generate change plan
         │
         ▼
Export plan
```

---

## 6. State Management

### 6.1 Application State

**Authentication State:**

```typescript
interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
  loading: boolean;
  error: string | null;
}
```

**Workspace State:**

```typescript
interface WorkspaceState {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  members: Member[];
  loading: boolean;
}
```

**Project State:**

```typescript
interface ProjectState {
  currentProject: Project | null;
  projects: Project[];
  branches: Branch[];
  currentBranch: Branch | null;
  loading: boolean;
}
```

### 6.2 Conversation State

```typescript
interface ConversationState {
  turns: ConversationTurn[];
  currentQuestion: Question | null;
  pendingQuestions: Question[];
  parkedQuestions: Question[];
  progress: {
    answered: number;
    total: number;
    byArtifact: Record<string, { answered: number; total: number }>;
  };
  loading: boolean;
  error: string | null;
}
```

### 6.3 Decision Graph State

```typescript
interface GraphState {
  nodes: DecisionNode[];
  edges: DependencyEdge[];
  selectedNodeId: string | null;
  filters: {
    categories: string[];
    status: ('answered' | 'pending' | 'deferred')[];
  };
  layout: 'graph' | 'list' | 'timeline';
  loading: boolean;
}
```

### 6.4 Artifact State

```typescript
interface ArtifactState {
  artifacts: Artifact[];
  currentArtifact: Artifact | null;
  generating: {
    jobId: string;
    type: string;
    progress: number;
    message: string;
  } | null;
  loading: boolean;
}
```

### 6.5 UI State

```typescript
interface UIState {
  theme: 'light' | 'dark' | 'system';
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  modals: ModalState[];
  toasts: Toast[];
  activeDropdown: string | null;
  scrollPosition: Record<string, number>;
}
```

---

## 7. API Integration Requirements

### 7.1 REST API Endpoints

| Method | Endpoint | Description | State Key |
|--------|----------|-------------|-----------|
| POST | /auth/login | User login | auth.user |
| POST | /auth/signup | User registration | auth.user |
| POST | /auth/logout | User logout | auth |
| GET | /workspaces | List workspaces | workspace.workspaces |
| POST | /workspaces | Create workspace | workspace.workspaces |
| GET | /workspaces/:id | Get workspace | workspace.current |
| PATCH | /workspaces/:id | Update workspace | workspace.current |
| GET | /projects | List projects | project.projects |
| POST | /projects | Create project | project.projects |
| GET | /projects/:id | Get project | project.current |
| PATCH | /projects/:id | Update project | project.current |
| DELETE | /projects/:id | Delete project | project.projects |
| GET | /projects/:id/questions/pending | Get pending questions | conversation.pending |
| POST | /projects/:id/answers | Submit answer | conversation.turns |
| POST | /projects/:id/defer | Defer question | conversation.pending |
| GET | /projects/:id/decisions | Get decisions | graph.nodes, graph.edges |
| POST | /projects/:id/artifacts | Generate artifact | artifact.generating |
| GET | /jobs/:id | Check job status | artifact.generating |
| GET | /artifacts/:id | Get artifact | artifact.current |
| GET | /artifacts/:id/versions | Get artifact versions | artifact.current |
| GET | /projects/:id/branches | List branches | project.branches |
| POST | /projects/:id/branches | Create branch | project.branches |
| POST | /projects/:id/branches/:id/merge | Merge branch | project.branches |
| POST | /codebase/analyze | Start analysis | analysis |
| GET | /codebase/analyses/:id | Get analysis results | analysis |
| GET | /projects/:id/impact-analysis | Get impact analysis | analysis |

### 7.2 WebSocket Events

**Client to Server:**

```typescript
{
  event: 'subscribe' | 'unsubscribe',
  project_id: string;
}

{
  event: 'typing',
  project_id: string,
  is_composing: boolean;
}

{
  event: 'heartbeat',
  timestamp: string;
}
```

**Server to Client:**

```typescript
{
  event: 'connected',
  connection_id: string,
  user_id: string,
  server_time: string;
}

{
  event: 'question_ready',
  project_id: string,
  question: Question;
}

{
  event: 'answer_submitted',
  project_id: string,
  question_id: string,
  decision_id: string,
  user_id: string;
}

{
  event: 'artifact_progress',
  artifact_id: string,
  progress: number,
  message: string;
}

{
  event: 'artifact_complete',
  artifact_id: string,
  type: string,
  download_urls: Record<string, string>;
}

{
  event: 'contradiction_detected',
  project_id: string,
  conflict: Contradiction;
}

{
  event: 'branch_created' | 'branch_merged',
  project_id: string,
  branch: Branch;
}

{
  event: 'comment_added',
  artifact_id: string,
  comment: Comment;
}
```

### 7.3 Error Handling

**Global Error Boundary:**

Catches React errors, shows friendly error UI, reports to error tracking service.

**API Error Handling:**

```typescript
interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id: string;
  timestamp: string;
}

const errorHandlers: Record<string, (error: APIError) => void> = {
  VALIDATION_ERROR: showValidationErrors,
  UNAUTHORIZED: redirectToLogin,
  FORBIDDEN: showPermissionDenied,
  NOT_FOUND: show404Page,
  CONFLICT: showConflictResolution,
  RATE_LIMITED: showRateLimitWarning,
  INTERNAL_ERROR: showGenericError,
};
```

### 7.4 Loading States

**Skeleton Loaders:** Project card skeleton, artifact card skeleton, question card skeleton, graph skeleton, table skeleton.

**Spinner Usage:** Button loading spinner, page loading overlay, inline loading indicator, progress bar with percentage.

---

## 8. Accessibility Requirements

### 8.1 Keyboard Navigation

**Global Shortcuts:**

| Key | Action |
|-----|--------|
| Tab | Move to next focusable element |
| Shift+Tab | Move to previous focusable element |
| Escape | Close modal/drawer |
| Enter/Space | Activate button |
| Arrow keys | Navigate within components |
| ? | Show keyboard shortcuts help |

**Component Shortcuts:**

| Context | Key | Action |
|---------|-----|--------|
| Conversation | Ctrl+Enter | Submit answer |
| Graph | +/- | Zoom in/out |
| Graph | Arrow keys | Pan |
| Graph | F | Fit to view |
| Search | / | Focus search |
| Any | Ctrl+/ | Toggle sidebar |

### 8.2 ARIA Attributes

**Buttons:**

```tsx
<button
  aria-label="Submit answer"
  aria-describedby="answer-help"
  aria-disabled={isDisabled}
>
  Submit
</button>
```

**Modals:**

```tsx
<div
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
  aria-describedby="modal-description"
>
  <h1 id="modal-title">Submit Answer</h1>
  <p id="modal-description">Press Enter to submit your answer.</p>
</div>
```

**Live Regions:**

```tsx
<div
  role="status"
  aria-live="polite"
  aria-atomic="true"
>
  {notification}
</div>

<div
  role="alert"
  aria-live="assertive"
>
  {error}
</div>
```

### 8.3 Screen Reader Support

**Announcements:**

Question ready announces "New question available". Answer submitted announces "Answer recorded". Contradiction detected announces "Warning: Contradiction detected". Artifact complete announces "Artifact generation complete". Errors announce error message with suggestion.

**Heading Structure:** H1 for page title, H2 for major sections, H3 for subsections, H4 for components.

### 8.4 Color Contrast

**Minimum Contrast Ratios:**

Text on background: 4.5:1 (WCAG AA). Large text: 3:1 (WCAG AA). UI components: 3:1 (WCAG AA). Graphical objects: 3:1 (WCAG AA).

**Don't Use Color Alone:**

Validation uses icon plus color plus text. Status uses badge plus color plus label. Links include underline plus color.

---

## 9. Responsive Design

### 9.1 Breakpoints

```css
/* Tailwind-style breakpoints */
--breakpoint-sm: 640px;   /* Mobile landscape */
--breakpoint-md: 768px;   /* Tablet portrait */
--breakpoint-lg: 1024px;  /* Tablet landscape / Small laptop */
--breakpoint-xl: 1280px;  /* Desktop */
--breakpoint-2xl: 1536px; /* Large desktop */
```

### 9.2 Responsive Layouts

**Mobile (less than 640px):**

Sidebar hidden behind hamburger menu. Main content full width with no side panels. Cards in single column. Modals full screen. Graph in simplified view. Navigation in bottom tab bar.

**Tablet (640px to 1024px):**

Sidebar collapsible. Main content with one side panel. Cards in 2 columns. Modals large size. Graph with legend visible.

**Desktop (more than 1024px):**

Sidebar visible. Main content with side panels. Cards in 3 columns. Modals standard size. Graph with full features.

### 9.3 Touch Targets

**Minimum Sizes:**

Buttons: 44x44px. Inputs: 44px height. Cards: 44x44px touch area. Menu items: 44px height. Icons: 24x24px with padding.

### 9.4 Responsive Typography

```css
/* Base font size: 16px */

@media (max-width: 640px) {
  :root {
    --font-size-base: 14px;
    --font-size-h1: 28px;
    --font-size-h2: 24px;
    --font-size-h3: 20px;
  }
}

@media (min-width: 641px) and (max-width: 1024px) {
  :root {
    --font-size-base: 15px;
    --font-size-h1: 32px;
    --font-size-h2: 28px;
    --font-size-h3: 24px;
  }
}

@media (min-width: 1025px) {
  :root {
    --font-size-base: 16px;
    --font-size-h1: 36px;
    --font-size-h2: 30px;
    --font-size-h3: 24px;
  }
}
```

### 9.5 Responsive Components

**Conversation Interface:**

Mobile: Stacked with conversation above and question below. Desktop: Side-by-side with conversation left and question right.

**Graph Visualization:**

Mobile: Simplified node view with list toggle. Desktop: Full interactive graph with all controls.

**Decision Cards:**

Mobile: Full width cards with horizontal scrolling. Desktop: Grid with hover details.

**Modals:**

Mobile: Full screen with close button. Desktop: Centered dialog.

---

## 10. Performance Requirements

### 10.1 Loading Performance

**Core Web Vitals Targets:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| LCP (Largest Contentful Paint) | Less than 2.5s | 95th percentile |
| FID (First Input Delay) | Less than 100ms | 95th percentile |
| CLS (Cumulative Layout Shift) | Less than 0.1 | 95th percentile |

**Loading States:**

First paint: Less than 1s. First contentful paint: Less than 1.5s. Time to interactive: Less than 3s. Route change: Less than 300ms.

### 10.2 Runtime Performance

**Frame Rate:**

Animations: 60fps. Graph interactions: 30fps minimum. Scrolling: 60fps.

**Memory:**

Initial bundle: Less than 200KB gzipped. Total bundle: Less than 500KB gzipped. Runtime memory: Less than 50MB.

### 10.3 Optimization Strategies

**Code Splitting:**

```typescript
// Route-based code splitting
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));
const DecisionGraph = lazy(() => import('./pages/DecisionGraph'));
const ArtifactViewer = lazy(() => import('./pages/ArtifactViewer'));

// Component lazy loading
const GraphVisualization = lazy(() => import('./components/GraphVisualization'));
```

**Image Optimization:**

WebP format with fallbacks. Responsive images with srcset. Lazy loading below fold. Icon sprites or inline SVGs.

**Caching:**

API responses with React Query cache. Static assets with service worker. Graph layout with memoization.

**Rendering Optimization:**

Virtual scrolling for long lists. Memo for expensive computations. useCallback for event handlers. Virtualized graph for large projects.

### 10.4 Offline Support

**Service Worker:**

Cache static assets. Cache API responses with stale-while-revalidate strategy. Offline fallback page. Background sync for actions.

**Data Persistence:**

Local storage for user preferences. IndexedDB for large datasets. Optimistic UI updates. Queue for offline actions.

---

## Appendix A: Component Checklist

### Core Components

- Button (all variants)
- Input (all types)
- Select/Dropdown
- Modal (all sizes)
- Toast/Notification
- Avatar
- Badge
- Card
- Dropdown Menu
- Tooltip
- Loading Spinner
- Skeleton Loader
- Empty State
- Error Boundary
- Form
- Checkbox
- Radio Group
- Toggle/Switch
- Progress Bar
- Tabs
- Accordion
- Alert/Banner

### Feature Components

- QuestionCard
- AnswerOption
- ConversationTurn
- ConversationStream
- ProgressIndicator
- DecisionNode
- DecisionEdge
- GraphVisualization
- ArtifactCard
- ArtifactPreview
- ArtifactExport
- BranchSelector
- BranchCard
- ConflictResolver
- CommentThread
- CommentItem
- AnalysisDashboard
- ArchitectureDiagram
- ComponentList
- ImpactReport
- ChangePlan

### Page Layouts

- Auth Layout
- Main Layout
- Dashboard Page
- Project List Page
- Project Detail Page
- Settings Page
- Error Pages (404, 500)

---

## Appendix B: File Structure

```
src/
├── components/
│   ├── ui/                    # Shared UI components
│   │   ├── Button/
│   │   │   ├── index.tsx
│   │   │   ├── Button.tsx
│   │   │   ├── Button.module.css
│   │   │   └── Button.stories.tsx
│   │   ├── Input/
│   │   ├── Modal/
│   │   ├── Card/
│   │   └── ...
│   ├── features/              # Feature-specific components
│   │   ├── conversation/
│   │   ├── decisions/
│   │   ├── artifacts/
│   │   ├── branches/
│   │   └── analysis/
│   └── layout/                # Layout components
│       ├── Header/
│       ├── Sidebar/
│       └── PageContainer/
├── pages/                     # Page components
│   ├── auth/
│   │   ├── Login/
│   │   ├── Signup/
│   │   └── ForgotPassword/
│   ├── workspaces/
│   │   ├── WorkspaceList/
│   │   └── WorkspaceSettings/
│   ├── projects/
│   │   ├── ProjectList/
│   │   └── ProjectDetail/
│   └── settings/
├── hooks/                     # Custom hooks
│   ├── useAuth.ts
│   ├── useProjects.ts
│   ├── useDecisions.ts
│   ├── useArtifacts.ts
│   ├── useGraph.ts
│   └── useWebSocket.ts
├── context/                   # React context
│   ├── AuthContext.tsx
│   ├── WorkspaceContext.tsx
│   └── UIContext.tsx
├── services/                   # API services
│   ├── api.ts
│   ├── auth.ts
│   ├── projects.ts
│   ├── decisions.ts
│   └── artifacts.ts
├── utils/                      # Utilities
│   ├── formatters.ts
│   ├── validators.ts
│   └── helpers.ts
├── styles/                     # Global styles
│   ├── variables.css
│   ├── typography.css
│   └── reset.css
├── types/                       # TypeScript types
│   ├── user.ts
│   ├── project.ts
│   ├── decision.ts
│   └── artifact.ts
├── App.tsx
└── index.tsx
```

---

## Appendix C: Testing Requirements

### Unit Testing

All shared components require 100% coverage. Feature components require 80% coverage. Hooks require 100% coverage. Utilities require 100% coverage.

### Integration Testing

User flows cover critical paths. API integration tests verify response handling. WebSocket connection tests verify reconnection logic.

### E2E Testing (Cypress/Playwright)

Authentication flow testing. Project creation flow testing. Question answering flow testing. Artifact generation flow testing. Export flow testing. Brownfield analysis flow testing.

### Visual Regression Testing

Chromatic or Percy integration. Critical component testing. Responsive layout testing. Dark mode testing.

---

## Appendix D: Browser Support

| Browser | Version | Support Level |
|---------|---------|---------------|
| Chrome | 90+ | Full |
| Firefox | 88+ | Full |
| Safari | 14+ | Full |
| Edge | 90+ | Full |
| Chrome Mobile | 90+ | Full |
| Safari Mobile | 14+ | Full |

**Note:** Internet Explorer 11 is not supported.

---

**Document Status:** Complete  
**Next Review Date:** Upon Phase 1 implementation completion  
**Document Owner:** Frontend Team  
**Last Major Update:** 2026-02-04  
**Version:** 1.0

---

*This document serves as the authoritative UI design source for the Agentic Spec Builder frontend implementation. All component designs, user flows, and accessibility requirements should align with these specifications.*
