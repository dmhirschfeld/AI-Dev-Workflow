# AI-Dev-Workflow Setup Guide

## Prerequisites

- Python 3.11+
- Git
- Anthropic API key

## Quick Start (Windows PowerShell)

```powershell
# 1. Navigate to install location
cd C:\Users\david

# 2. Extract the zip (if not already done)
Expand-Archive -Path "AI-Dev-Workflow.zip" -DestinationPath "." -Force

# 3. Enter directory
cd AI-Dev-Workflow

# 4. Create virtual environment
python -m venv venv

# 5. Activate it
.\venv\Scripts\Activate

# 6. Install dependencies
pip install -r requirements.txt

# 7. Configure environment
Copy-Item .env.example .env
notepad .env
# Add your ANTHROPIC_API_KEY=sk-ant-...

# 8. Test installation
python cli.py --help
```

## Quick Start (Mac/Linux)

```bash
# 1. Extract and enter directory
unzip AI-Dev-Workflow.zip
cd AI-Dev-Workflow

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. Test installation
python cli.py --help
```

## Optional: GitHub CLI (for PR integration)

```powershell
# Windows
winget install GitHub.cli
# Restart terminal after install
gh auth login
```

```bash
# Mac
brew install gh
gh auth login
```

## Basic Usage

```bash
# Launch CLI (autonomy selection first, then main menu)
python cli.py

# Ingest a codebase (includes 3-phase workflow)
python cli.py ingest /path/to/your/project

# Or from GitHub
python cli.py ingest owner/repo
```

## Ingest Workflow (3 Phases)

When you ingest a codebase, you'll be offered a comprehensive workflow:

### Phase 1: Assessment
- Architecture analysis
- Code quality metrics
- Security audit
- UX/Navigation review
- Accessibility check
- Testing coverage
- Documentation review
- **Generates: assessment_report.html**

### Phase 2: Planning
- Prioritized improvement roadmap
- AI enhancement opportunities
- Milestone breakdown
- Effort estimates
- **Generates: planning_report.html**

### Phase 3: Execution
- Work by milestone
- Quick wins first
- Critical issues focus
- Individual item selection
- Track progress as you complete items

## Troubleshooting

### "Module not found" errors
Ensure venv is activated (you should see `(venv)` in your prompt).

### API errors
Verify your `.env` file contains a valid `ANTHROPIC_API_KEY`.

### PowerShell execution policy errors
Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
