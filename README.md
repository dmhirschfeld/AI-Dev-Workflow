# AI-Dev-Workflow

A multi-agent software development workflow using Claude API with support for both new projects and existing codebases. Features a **Context Graph** for institutional memory - capturing why decisions were made, not just what was decided.

## Key Differentiator: The Context Graph

Unlike traditional development tools that only capture state ("what"), AI-Dev-Workflow captures **decision traces** ("why"):

```
Traditional: status = "Closed Won", amount = $50,000

Context Graph: 
  - Why: Client threatened churn over Feature X
  - Precedent: Similar to Deal #402 last quarter
  - Exception: VP Sales approved 10% discount due to delay
  - Outcome: Success (tracked 6 months later)
```

This enables:
- **Precedent Lookup** - "How did we handle similar situations?"
- **Pattern Recognition** - "What approaches work for healthcare projects?"
- **Outcome Tracking** - "Did this decision lead to success or failure?"
- **Cross-Project Learning** - "What can we learn from all past projects?"

## Features

- **18 Specialized Agents** - Developer, Architect, Reviewer, Security, plus 3 codebase analysis agents
- **16 Voting Agents** - Quality gates with committee-based approval
- **Task Decomposition** - Opus breaks architecture into atomic tasks for Sonnet
- **Multi-Model Strategy** - Opus for design, Sonnet for implementation, Haiku for simple checks
- **Reusable Service Catalog** - auth, admin, RBAC, audit, notifications, billing (NEW)
- **Design System** - Standard UI components with project-level theming (NEW)
- **Context Graph** - Decision traces and precedent lookup
- **Cross-System Synthesis** - Gather context from Slack, Jira, meetings
- **GitHub Integration** - Auto-search, clone, create repos
- **Usage Tracking** - Per-project token/cost tracking
- **New Project Support** - Start from scratch with guided workflow
- **Existing Codebase Support** - Ingest, evaluate, and improve any codebase
- **Health Evaluation** - Score projects across 6 dimensions
- **Improvement Planning** - Prioritized, actionable improvement tasks
- **RAG Knowledge Base** - ChromaDB-powered context retrieval
- **Static Analysis** - Semgrep, ESLint, Trivy integration

## Quick Start

### Installation

```powershell
# Extract and setup
cd C:\Users\david
Expand-Archive -Path "AI-Dev-Workflow.zip" -DestinationPath "." -Force
cd AI-Dev-Workflow

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
Copy-Item .env.example .env
notepad .env  # Add ANTHROPIC_API_KEY=sk-ant-...

# (Recommended) Install GitHub CLI
winget install GitHub.cli
gh auth login
```

### Run Interactive Mode

```powershell
python cli.py
```

```
══════════════════════════════════════════════════════════════
  AI-DEV-WORKFLOW
══════════════════════════════════════════════════════════════

  [1] New project         (start from scratch)
  [2] Open project        (continue existing)
  [3] Ingest codebase     (import external code)
  [4] Quick task          (one-off agent task)
  [5] Context graph       (precedents & decisions)
  [q] Quit

Choice: _
```

## GitHub Integration

AI-Dev-Workflow automatically searches for existing repos when you create or ingest projects.

### New Project Flow

```
Project name: TimeTracker

🔍 Searching GitHub for existing repos...

Found 3 similar repositories:

  [1] dmhirschfeld/timetracker 🔒 [TypeScript]
      ██████████ 100% match

  [2] dmhirschfeld/time-tracker-api 🔒 [Python]
      ████████░░ 80% match

  [C] Create NEW repo: timetracker
  [S] Skip GitHub (local only)
  [O] Connect to OTHER repo (enter name)
```

### Ingest Flow

Source can be a **local path** OR **GitHub repo**:

```
Source: dmhirschfeld/avery-app

🔍 Looking up dmhirschfeld/avery-app...
📥 Cloning dmhirschfeld/avery-app...
✅ Cloned to projects/avery-app
```

### Requirements

- GitHub CLI (`gh`) installed and authenticated
- `winget install GitHub.cli && gh auth login`

## Workflows

### New Project

```powershell
python cli.py
# Choose [1] New project
# Enter project name
# → GitHub search runs automatically
# Select existing repo OR create new OR skip
# Select tech stack
# Describe what you're building
```

The workflow guides you through:
1. **Ideation** - Refine the concept
2. **Requirements** - User stories, acceptance criteria
3. **Architecture** - Technical design
4. **Development** - AI-assisted coding
5. **Testing** - Automated test generation
6. **Deployment** - Cloud Run deployment

### Existing Codebase

```powershell
python cli.py
# Choose [3] Ingest codebase
# Enter path: C:\path\to\existing\code
```

The system will:
1. **Scan** - Index all source files
2. **Detect** - Identify tech stack automatically
3. **Evaluate** - Generate health report
4. **Plan** - Create improvement roadmap

### Health Evaluation

```
══════════════════════════════════════════════════════════════
  HEALTH REPORT: acme-crm
══════════════════════════════════════════════════════════════

Overall Score: 54/100  ⚠️ Warning

┌─────────────────────────┬───────┬──────────────────────┐
│ Category                │ Score │ Status               │
├─────────────────────────┼───────┼──────────────────────┤
│ Code Quality            │ 61    │ ⚠️ warning           │
│ Test Coverage           │ 12    │ ❌ critical          │
│ Security                │ 48    │ ❌ critical          │
│ Dependencies            │ 39    │ ❌ critical          │
│ Documentation           │ 42    │ ⚠️ warning           │
│ Architecture            │ 71    │ 🟢 good              │
└─────────────────────────┴───────┴──────────────────────┘

❌ CRITICAL ISSUES (3):
   • SQL injection vulnerability in search
   • No test coverage for payment flow
   • 2 dependencies with known CVEs
```

## CLI Commands

### Interactive Mode
```powershell
python cli.py                     # Main menu
```

### Direct Commands
```powershell
python cli.py new "Project Name"          # Create new project
python cli.py list                         # List all projects
python cli.py open <project-id>            # Open project menu
python cli.py ingest C:\path\to\code       # Import codebase
python cli.py evaluate <project-id>        # Run health check
python cli.py improve <project-id>         # Run improvements
python cli.py agent developer "task"       # Run single agent
```

## Agents

### Development Agents (15)
| Agent | Role |
|-------|------|
| Orchestrator | Coordinates workflow |
| Ideation | Concept development |
| Product Owner | Scope & priorities |
| Business Analyst | Requirements |
| Solutions Architect | System design |
| Data Architect | Database design |
| API Designer | API specifications |
| UI/UX Designer | Interface design |
| Developer | Code implementation |
| Code Reviewer | Quality review |
| Code Simplifier | Refactoring |
| Test Writer | Test creation |
| Security Specialist | Security review |
| Technical Writer | Documentation |
| DevOps | Deployment |

### Codebase Analysis Agents (3)
| Agent | Role |
|-------|------|
| Code Archaeologist | Understand existing code |
| Tech Debt Analyst | Identify & prioritize debt |
| Modernization Specialist | Plan upgrades |

### Voting Agents (16)
Quality gate reviewers for requirements, architecture, code, tests, and release readiness.

## Context Graph

The Context Graph captures **decision traces** - complete records of why decisions were made, not just what was decided.

### How It Works

1. **Capture** - Every voting gate records full reasoning, inputs, and precedents considered
2. **Store** - Decision traces are indexed and embedded for similarity search
3. **Query** - Before new decisions, agents look up relevant precedents
4. **Learn** - Outcomes are tracked to improve future recommendations

### Decision Trace Structure

```yaml
decision_trace:
  trace_id: TRACE-A1B2C3D4E5F6
  timestamp: 2025-01-13T12:34:56Z
  project_id: customer-portal
  context: "Architecture review for payment integration"
  
  inputs:
    - type: requirement
      summary: "Must support Stripe and PayPal"
    - type: precedent
      summary: "Project Alpha payment flow (92% similar)"
  
  precedents_matched:
    - trace_id: TRACE-OLDER123
      project: project-alpha
      similarity: 0.92
      outcome: success
      outcome_score: 0.85
  
  reasoning: |
    Based on Project Alpha's successful implementation,
    recommend microservices pattern for payment processing.
    Key difference: this project needs PayPal support.
  
  decision: approved_with_conditions
  decision_summary: "Use microservices pattern, add PayPal adapter"
  
  # Filled in later after deployment
  outcome: success
  outcome_score: 0.9
  outcome_notes: "Deployed successfully, 99.9% uptime"
```

### CLI Commands

```
══════════════════════════════════════════════════════════════
  CONTEXT GRAPH
══════════════════════════════════════════════════════════════

📊 47 decision traces across 12 projects

  [1] Find precedents     (search similar decisions)
  [2] View project traces (decisions for a project)
  [3] Pattern analysis    (insights by decision type)
  [4] Record outcome      (update decision result)
  [5] Browse all traces
  [b] Back
```

### The Compounding Effect

| Projects Completed | Precedent Value | Decision Quality |
|--------------------|-----------------|------------------|
| 1-5 | Minimal | Base agent reasoning |
| 10-20 | Growing | Pattern recognition starts |
| 50+ | Rich | Strong precedent matching |
| 100+ | Deep | Institutional memory |

After 100 projects, the system knows:
- "Healthcare projects need HIPAA review at architecture gate"
- "Microservices pattern has 87% success rate for payment integrations"
- "Friday deployments have 2.3x incident rate"

**The moat isn't the AI. It's the accumulated institutional reasoning.**

## Project Structure

```
AI-Dev-Workflow/
├── agents/
│   ├── definitions.yaml      # Agent configurations
│   └── prompts/              # Agent system prompts
│       └── voters/           # Voter prompts
├── config/
│   ├── gates.yaml            # Quality gate definitions
│   └── evaluation_criteria.yaml
├── core/
│   ├── agents.py             # Agent execution
│   ├── orchestrator.py       # Workflow coordination
│   ├── voting.py             # Voting system
│   ├── knowledge_base.py     # RAG implementation
│   ├── static_analysis.py    # Code analysis
│   ├── codebase_ingest.py    # Import existing code
│   ├── health_evaluator.py   # Project health scoring
│   ├── improvement_planner.py # Improvement roadmaps
│   ├── context_graph.py      # Decision traces & precedents (NEW)
│   ├── voting_integration.py # Context-aware voting (NEW)
│   └── cross_system.py       # Multi-system synthesis (NEW)
├── context_graph/             # Decision trace storage
├── projects/                  # Your projects
├── cli.py                     # Interactive CLI
└── requirements.txt
```

## Tech Stack (Default)

- **Frontend**: React 19 + TypeScript + Vite
- **Backend**: Node.js 20 + Express + TypeScript
- **Database**: PostgreSQL (Cloud SQL)
- **Validation**: Zod
- **Testing**: Playwright
- **Deployment**: Google Cloud Run
- **AI**: Claude API (Anthropic)
- **Vector DB**: ChromaDB

## Requirements

- Python 3.10+
- Anthropic API key
- (Optional) Semgrep, ESLint, Trivy for static analysis

## Configuration

### .env
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Custom Tech Stack

Edit `projects/<your-project>/project.yaml`:

```yaml
tech_stack:
  frontend:
    - Vue 3
    - TypeScript
  backend:
    - Python 3.12
    - FastAPI
  database:
    - MongoDB
```

## Integration with Launch1st

This workflow is designed to be called by Launch1st after market validation is complete. Launch1st handles:
- Concept development
- Market validation
- Design prototypes
- Traction measurement

When traction is proven, Launch1st invokes AI-Dev-Workflow to build the MVP.

## Model Strategy: Opus + Sonnet + Haiku

AI-Dev-Workflow uses different Claude models based on task complexity:

### Model Assignment

```
┌─────────────────────────────────────────────────────────────┐
│  OPUS (Complex Design)                                      │
│  - Solutions Architect    - Data Architect                  │
│  - API Designer          - Code Archaeologist               │
│  - Tech Debt Analyst     - Modernization Specialist         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Produces architecture + task breakdown
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SONNET (Implementation)                                    │
│  - Developer (atomic tasks)   - Code Reviewer               │
│  - Test Writer               - Security Specialist          │
│  - DevOps                    - Technical Writer             │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 16 voters evaluate output
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  VOTERS                                                     │
│  Sonnet: security, code_quality, architecture, logic...     │
│  Haiku:  completeness, clarity, documentation, standards... │
└─────────────────────────────────────────────────────────────┘
```

### Task Decomposition

The key insight: **Opus designs the system, but Sonnet builds it task by task.**

Solutions Architect (Opus) outputs:
1. Architecture design
2. **Implementation tasks** - atomic, 30-90 minute tasks

```yaml
tasks:
  - id: AUTH-001
    title: Create users table migration
    category: database
    size: S
    acceptance_criteria:
      - Table has id, email, password_hash, created_at
      - Email has unique constraint
    depends_on: []

  - id: AUTH-002
    title: Implement User model
    category: model
    size: S
    depends_on: [AUTH-001]

  - id: AUTH-003
    title: Create POST /auth/register endpoint
    category: api
    size: M
    depends_on: [AUTH-002]
```

TaskExecutor then:
1. Picks next ready task (dependencies satisfied)
2. Sends to Developer (Sonnet) with clear acceptance criteria
3. Reviews output
4. If pass → commit, next task
5. If fail → retry with feedback

### Cost Estimate Per Feature

| Component | Model | Cost |
|-----------|-------|------|
| Architecture (4 phases) | Opus | ~$1.80 |
| Implementation (10+ tasks) | Sonnet | ~$1.20 |
| Voting (5 gates × 16 voters) | Sonnet/Haiku | ~$1.75 |
| **Total** | | **~$5.00** |

### Configuration

Edit `config/models.yaml`:

```yaml
agents:
  solutions_architect:
    model: opus
  developer:
    model: sonnet

voters:
  sonnet:
    - security
    - code_quality
  haiku:
    - completeness
    - clarity
```

## Reusable Service Catalog

Before building ANY functionality, the workflow checks for existing services.

### Available Services

| Service | Functionality | Status |
|---------|--------------|--------|
| `auth-service` | Google OAuth, email/password, JWT, sessions | Production |
| `admin-service` | User management, **login-as** (impersonation), dashboard | Stable |
| `rbac-service` | Roles, permissions, access control | Production |
| `audit-service` | Activity logging, compliance, **full history** | Production |
| `user-service` | User CRUD, profiles, preferences | Production |
| `notification-service` | Email, SMS, push, in-app notifications | Stable |
| `file-service` | Upload, storage, CDN, image processing | Production |
| `billing-service` | Stripe subscriptions, invoices, payments | Stable |

### How It Works

1. **Detection**: When requirements mention "login", "authentication", "audit trail", etc., the system detects matching services
2. **Recommendation**: Architect receives recommendations to use existing services
3. **Extraction**: New functionality that could be reusable gets flagged for catalog addition

### Project Configuration

In `project.yaml`, specify which services to use:

```yaml
services:
  auth-service:
    enabled: true
    features: [google-oauth, email-password]
  
  rbac-service:
    enabled: true
    custom_roles:
      - name: project_admin
        permissions: ["projects:*", "users:read"]
  
  audit-service:
    enabled: true
    events_to_log:
      - user.login
      - record.created
      - admin.login_as
  
  admin-service:
    enabled: true
    features: [user-list, login-as, dashboard]
```

### Service Catalog Location

`catalog/services.yaml` - Full service definitions and detection patterns

## Design System

Standard UI components with project-level theming.

### Standard Components

| Component | Use For |
|-----------|---------|
| `data_grid` | Tables with sort, filter, pagination, selection |
| `slide_out_panel` | Details/edit forms (keeps list visible) |
| `modal` | Confirmations, alerts |
| `sidebar_nav` | Admin/dashboard navigation |
| `form` | All data entry with validation |
| `select` | Dropdowns (single, multi, searchable) |
| `toast` | Notifications |

### Standard Layouts

**Admin Layout** (most apps):
```
┌────────────────────────────────────────────────┐
│  Top Nav (breadcrumbs, search, user)           │
├──────────┬─────────────────────────────────────┤
│  Sidebar │  Page Header + Content              │
│  Nav     │                                     │
└──────────┴─────────────────────────────────────┘
```

**List-Detail Layout** (CRUD screens):
```
┌─────────────────────┬──────────────────────┐
│ Data Grid           │ Slide-Out Panel     │
│ • Row 1            │ Details / Edit Form  │
│ • Row 2 (selected) ◀│                      │
└─────────────────────┴──────────────────────┘
```

### Project Theming

Override design tokens per project:

```yaml
design_tokens:
  colors:
    primary:
      default: "#059669"    # Emerald for healthcare
      hover: "#047857"
  typography:
    font_family:
      sans: "Poppins, sans-serif"
```

Components automatically use project tokens while maintaining UX consistency.

### Design System Location

`catalog/design_system.yaml` - Full component and token definitions

## License

MIT
