#!/usr/bin/env python3
"""
AI-Dev-Workflow - Unified Interactive CLI

A unified interface for:
- Creating new projects
- Opening existing projects
- Ingesting external codebases
- Evaluating and improving code
- Running AI agents
"""

import os
import sys
import re
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in the script directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from {env_path}")
except ImportError:
    # dotenv not installed, try to load manually
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print(f"✓ Loaded environment from {env_path}")

# Import core modules
try:
    from core.codebase_ingest import CodebaseIngestor, ingest_codebase
    from core.health_evaluator import HealthEvaluator, evaluate_project
    from core.improvement_planner import ImprovementPlanner, create_improvement_plan
    from core.context_graph import get_context_graph, find_precedents, capture_decision
except ImportError:
    # Allow running from project directory
    sys.path.insert(0, str(Path(__file__).parent))
    from core.codebase_ingest import CodebaseIngestor, ingest_codebase
    from core.health_evaluator import HealthEvaluator, evaluate_project
    from core.improvement_planner import ImprovementPlanner, create_improvement_plan
    try:
        from core.context_graph import get_context_graph, find_precedents, capture_decision
    except ImportError:
        pass  # Context graph is optional


class InteractiveCLI:
    """Unified interactive CLI"""
    
    HEADER = "═" * 60
    SUBHEADER = "─" * 60
    
    TECH_STACKS = {
        "1": {
            "name": "React + Node + PostgreSQL",
            "frontend": ["React 19", "TypeScript", "Vite"],
            "backend": ["Node.js 20", "Express", "TypeScript"],
            "database": ["PostgreSQL"],
            "validation": ["Zod"],
            "testing": ["Playwright"],
            "deployment": ["Google Cloud Run"],
        },
        "2": {
            "name": "React + Python + PostgreSQL",
            "frontend": ["React 19", "TypeScript", "Vite"],
            "backend": ["Python 3.12", "FastAPI"],
            "database": ["PostgreSQL"],
            "validation": ["Pydantic"],
            "testing": ["pytest", "Playwright"],
            "deployment": ["Google Cloud Run"],
        },
        "3": {
            "name": "Custom",
            "custom": True,
        },
    }
    
    def __init__(self, verbose: bool = True):
        self.projects_dir = Path("projects")
        self.projects_dir.mkdir(exist_ok=True)
        self.current_project = None
        self.current_config = None
        self.autonomy_level = "balanced"  # Default autonomy level
        self.verbose = verbose  # Verbose mode shows all steps (default: on)

        # Initialize components
        self.ingestor = CodebaseIngestor(str(self.projects_dir))
        self.evaluator = HealthEvaluator(str(self.projects_dir))
        self.planner = ImprovementPlanner(str(self.projects_dir))

        # Start web dashboard server in background
        self._start_dashboard_server()

    def _start_dashboard_server(self):
        """Start the web dashboard server in a background thread"""
        try:
            from core.monitor import StandaloneServer

            def run_server():
                server = StandaloneServer(self.projects_dir, port=8765)
                server.start(open_browser=False)

            self.dashboard_thread = threading.Thread(target=run_server, daemon=True)
            self.dashboard_thread.start()
            print("📊 Dashboard: http://localhost:8765/admin")
        except Exception as e:
            print(f"⚠️  Dashboard server failed to start: {e}")

    def clear_screen(self):
        """Clear terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str):
        """Print header"""
        print(f"\n{self.HEADER}")
        print(f"  {title}")
        print(f"{self.HEADER}\n")
    
    def print_subheader(self, title: str):
        """Print subheader"""
        print(f"\n{self.SUBHEADER}")
        print(f"  {title}")
        print(f"{self.SUBHEADER}\n")
    
    def print_menu(self, options: list, show_back_hint: bool = True):
        """Print menu options"""
        for key, label in options:
            print(f"  [{key}] {label}")
        if show_back_hint:
            print("\n  [Enter] Back")
        print()

    def log_verbose(self, message: str, level: str = "info", indent: int = 0):
        """Print verbose output like Claude CLI does"""
        if not self.verbose:
            return

        prefix_map = {
            "info": "ℹ️ ",
            "step": "▶ ",
            "substep": "  → ",
            "success": "✅ ",
            "warning": "⚠️ ",
            "error": "❌ ",
            "thinking": "🤔 ",
            "agent": "🤖 ",
            "vote": "🗳️ ",
            "result": "📊 ",
        }
        prefix = prefix_map.get(level, "  ")
        indent_str = "  " * indent
        print(f"{indent_str}{prefix}{message}")

    def get_input(self, prompt: str = "Choice: ", allow_back: bool = True) -> str:
        """Get user input. Empty input returns 'b' for back navigation."""
        try:
            user_input = input(prompt).strip()
            # Empty input (just Enter) means go back
            if allow_back and user_input == "":
                return "b"
            return user_input
        except (KeyboardInterrupt, EOFError):
            print("\n")
            return "q"

    def get_multiline(self, prompt: str) -> str:
        """Get multiline input"""
        print(f"{prompt} (blank line to finish):")
        lines = []
        while True:
            try:
                line = input()
                if not line:
                    break
                lines.append(line)
            except (KeyboardInterrupt, EOFError):
                break
        return "\n".join(lines)

    # ════════════════════════════════════════════════════════════
    # AUTONOMY SELECTION (First Menu)
    # ════════════════════════════════════════════════════════════
    
    def autonomy_menu(self):
        """First menu - select autonomy level"""
        self.clear_screen()
        self.print_header("AI-DEV-WORKFLOW")
        
        print("Select your working style:\n")
        
        print("  [1] 🤝 Pair Programming    (13 checkpoints)")
        print("      Maximum control. Review at every stage.")
        print("      Best for: Complex projects, learning the system\n")
        
        print("  [2] ⚖️  Balanced            (9 checkpoints)")
        print("      Moderate oversight at key decision points.")
        print("      Best for: Most projects (recommended)\n")
        
        print("  [3] 🚀 Fully Autonomous    (4 checkpoints)")
        print("      Minimal interruption. Only critical gates.")
        print("      Best for: Well-defined tasks, experienced users\n")
        
        print("  [q] Quit\n")
        
        while True:
            choice = self.get_input("Select autonomy level (1-3): ").lower()
            
            if choice == "1":
                self.autonomy_level = "pair"
                print("\n✓ Pair Programming mode - maximum checkpoints\n")
                break
            elif choice == "2":
                self.autonomy_level = "balanced"
                print("\n✓ Balanced mode - key checkpoints only\n")
                break
            elif choice == "3":
                self.autonomy_level = "autonomous"
                print("\n✓ Fully Autonomous mode - minimal interruption\n")
                break
            elif choice in ["q", "quit", "exit"]:
                print("Goodbye!")
                sys.exit(0)
            else:
                print("Please enter 1, 2, or 3")

        self.main_menu()
    
    # ════════════════════════════════════════════════════════════
    # MAIN MENU
    # ════════════════════════════════════════════════════════════
    
    def main_menu(self):
        """Main menu"""
        while True:
            self.clear_screen()
            self.print_header("AI-DEV-WORKFLOW")
            
            # Show current autonomy level
            autonomy_labels = {
                "pair": "🤝 Pair Programming",
                "balanced": "⚖️  Balanced",
                "autonomous": "🚀 Autonomous"
            }
            print(f"Mode: {autonomy_labels.get(self.autonomy_level, 'Not set')}")
            print()
            
            # Show recent projects
            projects = self._list_projects()
            if projects:
                print("Recent Projects:")
                for p in projects[:5]:
                    status_icon = "🟢" if p.get("status") == "active" else "⏸️"
                    ptype = p.get("type", "new")
                    print(f"  {status_icon} {p['name']} ({ptype})")
                print()
            
            self.print_menu([
                ("1", "New project         (start from scratch)"),
                ("2", "Open project        (continue existing)"),
                ("3", "Ingest codebase     (import external code)"),
                ("4", "Quick task          (one-off agent task)"),
                ("5", "Context graph       (precedents & decisions)"),
                ("6", "Usage report        (costs across projects)"),
                ("7", "Web dashboard       (monitor & admin)"),
                ("c", "Change autonomy     (switch working style)"),
                ("q", "Quit"),
            ])

            choice = self.get_input().lower()

            if choice == "1":
                self.new_project_flow()
            elif choice == "2":
                self.open_project_flow()
            elif choice == "3":
                self.ingest_flow()
            elif choice == "4":
                self.quick_task_flow()
            elif choice == "5":
                self.context_graph_flow()
            elif choice == "6":
                self.global_usage_flow()
            elif choice == "7":
                self.web_dashboard_flow()
            elif choice == "c":
                self.autonomy_menu()
                return  # autonomy_menu will call main_menu again
            elif choice in ["q", "quit", "exit"]:
                print("Goodbye!")
                sys.exit(0)
    
    # ════════════════════════════════════════════════════════════
    # NEW PROJECT
    # ════════════════════════════════════════════════════════════
    
    def new_project_flow(self):
        """Create new project with GitHub integration"""
        self.clear_screen()
        self.print_header("NEW PROJECT")
        
        # Get project name
        name = self.get_input("Project name: ")
        if not name:
            return
        
        # Generate ID
        project_id = name.lower().replace(" ", "-")
        project_id = "".join(c for c in project_id if c.isalnum() or c == "-")
        
        # Check if local project exists
        project_dir = self.projects_dir / project_id
        if project_dir.exists():
            print(f"\n⚠️  Local project '{project_id}' already exists.")
            choice = self.get_input("Open it instead? [Y/n]: ").lower()
            if choice != "n":
                self.current_project = project_id
                with open(project_dir / "project.yaml", encoding="utf-8") as f:
                    self.current_config = yaml.safe_load(f)
                self.project_menu()
            return
        
        # ── GitHub Integration ──────────────────────────────────
        github_repo = None
        github_action = None
        
        try:
            from core.github_integration import get_github, GitHubRepo
            gh = get_github()
            
            if gh.is_gh_available() and gh.is_authenticated():
                print("\n🔍 Searching GitHub for existing repos...")
                
                similar_repos = gh.find_similar_repos(name, limit=8)
                
                if similar_repos:
                    print(f"\nFound {len(similar_repos)} similar repositories:\n")
                    
                    for i, (repo, similarity) in enumerate(similar_repos, 1):
                        sim_bar = "█" * int(similarity * 10) + "░" * (10 - int(similarity * 10))
                        private_icon = "🔒" if repo.private else "🌐"
                        lang = f"[{repo.language}]" if repo.language else ""
                        
                        print(f"  [{i}] {repo.full_name} {private_icon} {lang}")
                        print(f"      {sim_bar} {similarity:.0%} match")
                        if repo.description:
                            print(f"      {repo.description[:60]}...")
                        print()
                    
                    print(f"  [C] Create NEW repo: {project_id}")
                    print(f"  [S] Skip GitHub (local only)")
                    print(f"  [O] Connect to OTHER repo (enter name)")
                    
                    choice = self.get_input("\nChoice: ").strip()
                    
                    if choice.upper() == "C":
                        github_action = "create"
                    elif choice.upper() == "S":
                        github_action = "skip"
                    elif choice.upper() == "O":
                        other_name = self.get_input("Full repo name (owner/repo): ").strip()
                        if other_name:
                            other_repo = gh.get_repo(other_name)
                            if other_repo:
                                github_repo = other_repo
                                github_action = "connect"
                            else:
                                print(f"❌ Repo '{other_name}' not found")
                                github_action = "skip"
                    else:
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(similar_repos):
                                github_repo = similar_repos[idx][0]
                                github_action = "connect"
                        except ValueError:
                            github_action = "skip"
                else:
                    print("\nNo existing repos found with similar names.\n")
                    print(f"  [C] Create NEW repo: {project_id}")
                    print(f"  [S] Skip GitHub (local only)")
                    print(f"  [O] Connect to OTHER repo (enter name)")
                    
                    choice = self.get_input("\nChoice [C]: ").strip().upper() or "C"
                    
                    if choice == "C":
                        github_action = "create"
                    elif choice == "O":
                        other_name = self.get_input("Full repo name (owner/repo): ").strip()
                        if other_name:
                            other_repo = gh.get_repo(other_name)
                            if other_repo:
                                github_repo = other_repo
                                github_action = "connect"
                            else:
                                print(f"❌ Repo '{other_name}' not found")
                                github_action = "skip"
                    else:
                        github_action = "skip"
            else:
                if not gh.is_gh_available():
                    print("\n⚠️  GitHub CLI (gh) not installed. Skipping GitHub integration.")
                    print("   Install: winget install GitHub.cli")
                elif not gh.is_authenticated():
                    print("\n⚠️  Not authenticated with GitHub. Skipping GitHub integration.")
                    print("   Run: gh auth login")
                github_action = "skip"
                
        except ImportError:
            print("\n⚠️  GitHub integration not available.")
            github_action = "skip"
        
        # ── Handle GitHub Action ────────────────────────────────
        
        if github_action == "connect" and github_repo:
            print(f"\n📥 Cloning {github_repo.full_name}...")
            
            if gh.clone_repo(github_repo.full_name, str(project_dir)):
                print(f"✅ Cloned to {project_dir}")
                
                # Check for existing project.yaml
                if not (project_dir / "project.yaml").exists():
                    # Create project.yaml for existing repo
                    config = self._create_project_config(
                        project_id, name, "existing",
                        f"Connected from {github_repo.full_name}",
                        github_repo
                    )
                    with open(project_dir / "project.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                else:
                    with open(project_dir / "project.yaml", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    # Add GitHub info if not present
                    if "github" not in config:
                        config["github"] = {
                            "repo": github_repo.full_name,
                            "url": github_repo.url,
                            "connected": datetime.now().strftime("%Y-%m-%d"),
                        }
                        with open(project_dir / "project.yaml", "w", encoding="utf-8") as f:
                            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            else:
                print(f"❌ Failed to clone. Creating local project instead.")
                github_action = "skip"
                github_repo = None
        
        elif github_action == "create":
            print(f"\n📦 Creating GitHub repo: {project_id}...")
            
            # Ask for visibility
            vis = self.get_input("Private repo? [Y/n]: ").lower()
            private = vis != "n"
            
            github_repo = gh.create_repo(project_id, private=private)
            
            if github_repo:
                print(f"✅ Created: {github_repo.url}")
            else:
                print("❌ Failed to create repo. Continuing locally.")
        
        # ── Create Local Project (if not cloned) ────────────────
        
        if not project_dir.exists():
            project_dir.mkdir(parents=True)
            (project_dir / "docs").mkdir()
            (project_dir / "src").mkdir()
        
        # Select tech stack
        print("\nTech stack:")
        for key, stack in self.TECH_STACKS.items():
            print(f"  [{key}] {stack['name']}")
        
        stack_choice = self.get_input("\nChoice [1]: ") or "1"
        stack = self.TECH_STACKS.get(stack_choice, self.TECH_STACKS["1"])
        
        if stack.get("custom"):
            print("\nCustom stack - you'll configure this in project.yaml")
            stack = {"name": "Custom", "custom": True}
        
        # Get description
        print("\nWhat are you building? (Enter twice to finish)")
        description = self.get_multiline("")
        
        # Create/update project.yaml
        config_file = project_dir / "project.yaml"
        
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            # Update with new info
            config["project"]["description"] = description
            config["tech_stack"] = stack if not stack.get("custom") else config.get("tech_stack", {})
        else:
            config = self._create_project_config(
                project_id, name, "new", description, github_repo
            )
            config["tech_stack"] = stack if not stack.get("custom") else {}
        
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # ── Initialize Git & Push (if created new repo) ─────────
        
        if github_action == "create" and github_repo:
            print("\n📝 Initializing git repository...")
            
            if not gh.is_git_repo(str(project_dir)):
                gh.init_local_repo(str(project_dir))
            
            # Create .gitignore if missing
            gitignore = project_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    "__pycache__/\n*.pyc\n.env\nvenv/\nnode_modules/\n.DS_Store\n"
                )
            
            gh.add_remote(str(project_dir), github_repo)
            gh.commit_all(str(project_dir), "Initial commit from AI-Dev-Workflow")
            
            print("📤 Pushing to GitHub...")
            if gh.push(str(project_dir), branch=github_repo.default_branch):
                print(f"✅ Pushed to {github_repo.url}")
            else:
                print("⚠️  Push failed - you may need to push manually")
        
        # ── Summary ─────────────────────────────────────────────
        
        print(f"\n{'═' * 50}")
        print(f"✅ Project ready: {project_id}")
        print(f"{'═' * 50}")
        print(f"\n📁 Location: {project_dir}")
        
        if github_repo:
            print(f"🔗 GitHub: {github_repo.url}")
        
        print("\nStructure:")
        for item in project_dir.iterdir():
            icon = "📁" if item.is_dir() else "📄"
            print(f"  {icon} {item.name}")
        
        self.get_input("\nPress Enter to open project...")
        
        self.current_project = project_id
        self.current_config = config
        self.project_menu()
    
    def _create_project_config(
        self,
        project_id: str,
        name: str,
        project_type: str,
        description: str,
        github_repo=None
    ) -> dict:
        """Create a new project configuration"""
        config = {
            "project": {
                "id": project_id,
                "name": name,
                "type": project_type,
                "description": description,
                "created": datetime.now().strftime("%Y-%m-%d"),
                "status": "active",
                "stage": "ideation" if project_type == "new" else "analysis",
            },
            "tech_stack": {},
            "features": [],
            "history": [],
        }
        
        if github_repo:
            config["github"] = {
                "repo": github_repo.full_name,
                "url": github_repo.url,
                "default_branch": github_repo.default_branch,
                "connected": datetime.now().strftime("%Y-%m-%d"),
            }
        
        return config
    
    # ════════════════════════════════════════════════════════════
    # OPEN PROJECT
    # ════════════════════════════════════════════════════════════
    
    def open_project_flow(self):
        """Open existing project"""
        projects = self._list_projects()
        
        if not projects:
            print("\nNo projects found.")
            self.get_input("Press Enter to continue...")
            return
        
        self.clear_screen()
        self.print_header("OPEN PROJECT")
        
        print("Available projects:")
        for i, p in enumerate(projects, 1):
            ptype = p.get("type", "new")
            status = p.get("status", "active")
            icon = "🟢" if status == "active" else "⏸️"
            print(f"  [{i}] {icon} {p['name']} ({ptype})")
        print(f"  [c] Cancel")
        
        choice = self.get_input("\nChoice: ")
        if choice.lower() in ["c", "cancel", ""]:
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                self.current_project = projects[idx]["id"]
                self._load_project(self.current_project)
                self.project_menu()
        except (ValueError, IndexError):
            print("Invalid selection.")
            self.get_input("Press Enter to continue...")
    
    # ════════════════════════════════════════════════════════════
    # INGEST CODEBASE
    # ════════════════════════════════════════════════════════════
    
    def ingest_flow(self):
        """Ingest external codebase with comprehensive assessment workflow"""
        self.clear_screen()
        self.print_header("INGEST CODEBASE")
        
        print("Source can be:")
        print("  • Local path:  C:\\path\\to\\project or ~/projects/myapp")
        print("  • GitHub repo: owner/repo or https://github.com/owner/repo")
        print()
        
        source = self.get_input("Source: ").strip()
        if not source:
            return
        
        source_path = None
        github_repo = None
        
        # ── Detect Source Type ──────────────────────────────────
        
        # GitHub URL pattern
        github_patterns = [
            r'^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/.*)?$',
            r'^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$',
            r'^([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)$',  # owner/repo format
        ]
        
        is_github = False
        repo_name = None
        
        for pattern in github_patterns:
            match = re.match(pattern, source)
            if match:
                repo_name = match.group(1)
                is_github = True
                break
        
        if is_github:
            # ── Clone from GitHub ───────────────────────────────
            try:
                from core.github_integration import get_github
                gh = get_github()
                
                if not gh.is_gh_available():
                    print("\n❌ GitHub CLI (gh) not installed.")
                    print("   Install: winget install GitHub.cli")
                    self.get_input("Press Enter...")
                    return
                
                if not gh.is_authenticated():
                    print("\n❌ Not authenticated with GitHub.")
                    print("   Run: gh auth login")
                    self.get_input("Press Enter...")
                    return
                
                print(f"\n🔍 Looking up {repo_name}...")
                github_repo = gh.get_repo(repo_name)
                
                if not github_repo:
                    print(f"\n❌ Repository not found: {repo_name}")
                    
                    # Offer to search
                    search_term = repo_name.split("/")[-1]
                    search = self.get_input(f"Search for similar repos? [Y/n]: ").lower()
                    
                    if search != "n":
                        similar = gh.find_similar_repos(search_term, limit=5)
                        if similar:
                            print("\nSimilar repos found:")
                            for i, (r, sim) in enumerate(similar, 1):
                                print(f"  [{i}] {r.full_name} ({sim:.0%} match)")
                            
                            choice = self.get_input("\nChoice (or Enter to cancel): ")
                            try:
                                idx = int(choice) - 1
                                if 0 <= idx < len(similar):
                                    github_repo = similar[idx][0]
                            except:
                                pass
                    
                    if not github_repo:
                        self.get_input("Press Enter to continue...")
                        return
                
                # Generate local project name
                project_id = github_repo.name.lower()
                project_id = "".join(c for c in project_id if c.isalnum() or c == "-")
                project_dir = self.projects_dir / project_id
                
                # Check if already exists locally
                if project_dir.exists():
                    print(f"\n⚠️  Project '{project_id}' already exists locally.")
                    choice = self.get_input("Overwrite and re-clone? [y/N]: ").lower()
                    if choice != "y":
                        # Open existing
                        self._load_project(project_id)
                        self.current_project = project_id
                        self.project_menu()
                        return
                    else:
                        import shutil
                        shutil.rmtree(project_dir)
                
                print(f"\n📥 Cloning {github_repo.full_name}...")
                
                if gh.clone_repo(github_repo.full_name, str(project_dir)):
                    print(f"✅ Cloned to {project_dir}")
                    source_path = str(project_dir)
                else:
                    print(f"\n❌ Clone failed")
                    self.get_input("Press Enter...")
                    return
                    
            except ImportError:
                print("\n❌ GitHub integration not available.")
                self.get_input("Press Enter...")
                return
        else:
            # ── Local Path ──────────────────────────────────────
            source_path = os.path.expanduser(source)
            
            if not os.path.exists(source_path):
                print(f"\n❌ Path not found: {source_path}")
                self.get_input("Press Enter to continue...")
                return
            
            # Check if it's a git repo and get remote
            try:
                from core.github_integration import get_github
                gh = get_github()
                
                if gh.is_git_repo(source_path):
                    remote_url = gh.get_remote_url(source_path)
                    if remote_url and "github.com" in remote_url:
                        # Extract repo name from URL
                        for pattern in github_patterns[:2]:
                            match = re.match(pattern, remote_url)
                            if match:
                                repo_name = match.group(1)
                                github_repo = gh.get_repo(repo_name)
                                if github_repo:
                                    print(f"\n🔗 Found GitHub remote: {github_repo.full_name}")
                                break
            except ImportError:
                pass
        
        # ── Run Basic Ingest ──────────────────────────────────
        
        print(f"\n📂 Scanning {source_path}...")
        
        try:
            result = self.ingestor.ingest(source_path)
            
            self.clear_screen()
            self.print_header(f"INGESTED: {result.project_name}")
            
            print(f"📁 Source files: {result.source_file_count}")
            print(f"📄 Total lines: {result.total_lines:,}")
            print()
            
            # Show detected stack
            stack = result.tech_stack
            if stack.frontend:
                print(f"Frontend: {', '.join(stack.frontend)}")
            if stack.backend:
                print(f"Backend: {', '.join(stack.backend)}")
            if stack.database:
                print(f"Database: {', '.join(stack.database)}")
            if stack.infrastructure:
                print(f"Infrastructure: {', '.join(stack.infrastructure)}")
            if stack.testing:
                print(f"Testing: {', '.join(stack.testing)}")
            
            print()
            print(f"✅ Tests: {'Yes' if result.has_tests else 'No'}")
            print(f"✅ CI/CD: {'Yes' if result.has_ci else 'No'}")
            print(f"✅ Docker: {'Yes' if result.has_docker else 'No'}")
            
            # Add GitHub info to project config if we have it
            if github_repo:
                print(f"\n🔗 GitHub: {github_repo.url}")
                self._update_project_github(result.project_name, github_repo)
            
            # Set current project
            self.current_project = result.project_name
            self._load_project(result.project_name)
            
            # ── Offer Comprehensive Workflow ────────────────────
            print()
            print(self.SUBHEADER)
            print("  What would you like to do?")
            print(self.SUBHEADER)
            print()
            print("  [1] Full Assessment Workflow (Recommended)")
            print("      Phase 1: Assessment → Phase 2: Planning → Phase 3: Execution")
            print()
            print("  [2] Quick Health Check")
            print("      Basic evaluation only")
            print()
            print("  [3] Skip to Project Menu")
            print("      Open project without analysis")
            print()
            
            choice = self.get_input("Choice [1]: ") or "1"
            
            if choice == "1":
                self._run_comprehensive_workflow(result.project_name, source_path)
            elif choice == "2":
                self.evaluate_flow()
            else:
                self.project_menu()
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.get_input("Press Enter to continue...")

    def _select_assessment_mode(self) -> tuple[str, list | None]:
        """Let user choose assessment mode for the ingest workflow."""
        print("\n" + "=" * 60)
        print("ASSESSMENT MODE")
        print("=" * 60)
        print("\nSelect how the assessment should run:")
        print()
        print("  [1] Standard (Recommended)")
        print("      Fast assessment using current knowledge.")
        print("      Uses learned patterns and rules, no per-step voting.")
        print()
        print("  [2] Self-Improvement (Training Mode)")
        print("      Voters review EACH step (30 voter calls instead of 5).")
        print("      Failed steps capture feedback to improve future assessments.")
        print("      More expensive, but makes the system smarter.")
        print()
        print("  [3] Rules Only (Quick Scan)")
        print("      Only runs deterministic rules, skips AI entirely.")
        print("      Fastest and cheapest, but least comprehensive.")
        print()
        print("  [4] Quick Test (Architecture + Tech Debt only)")
        print("      Runs only 2 assessment steps for faster testing.")
        print("      Useful for verifying agent mappings work correctly.")
        print()

        while True:
            choice = input("Select mode (1-4) [1]: ").strip() or "1"

            mode_map = {
                "1": ("standard", None),
                "2": ("self_improvement", None),
                "3": ("rules_only", None),
                "4": ("standard", ["architecture", "tech_debt"])
            }

            if choice in mode_map:
                mode, test_steps = mode_map[choice]
                mode_names = {
                    "standard": "Standard",
                    "self_improvement": "Self-Improvement (Training)",
                    "rules_only": "Rules Only"
                }
                if test_steps:
                    print(f"\n✓ Quick Test mode selected (steps: {', '.join(test_steps)})\n")
                else:
                    print(f"\n✓ {mode_names[mode]} mode selected\n")
                return mode, test_steps

            print("Invalid choice. Please enter 1, 2, 3, or 4.")

    def _setup_verbose_callbacks(self, orchestrator):
        """Set up verbose logging callbacks on the orchestrator"""
        cli = self  # Capture self for closures

        # Store original callbacks
        original_phase_change = orchestrator.on_phase_change
        original_gate_result = orchestrator.on_gate_result
        original_agent_response = orchestrator.on_agent_response

        def verbose_phase_change(old_phase, new_phase):
            cli.log_verbose(f"Phase transition: {old_phase.value} → {new_phase.value}", "step")
            if original_phase_change:
                original_phase_change(old_phase, new_phase)

        def verbose_gate_result(result):
            cli.log_verbose(f"Gate '{result.gate_id}' completed", "result")
            cli.log_verbose(f"Result: {'PASSED' if result.passed else 'FAILED'}", "success" if result.passed else "warning")

            # Show each voter's decision
            for vote in result.votes:
                is_pass = vote.vote == "pass"
                status = "success" if is_pass else "warning"
                cli.log_verbose(f"{vote.voter_id}: {'PASS' if is_pass else 'FAIL'} ({vote.confidence}% confidence)", status, indent=1)
                cli.log_verbose(f"Reasoning: {vote.reasoning[:150]}...", "thinking", indent=2)
                if vote.concerns:
                    concerns_str = ", ".join(vote.concerns) if isinstance(vote.concerns, list) else str(vote.concerns)
                    cli.log_verbose(f"Concerns: {concerns_str[:100]}...", "warning", indent=2)

            if result.aggregated_feedback:
                cli.log_verbose(f"Summary: {result.aggregated_feedback[:200]}...", "info")

            if original_gate_result:
                original_gate_result(result)

        def verbose_agent_response(response):
            cli.log_verbose(f"Agent '{response.agent_id}' ({response.role}) completed", "agent")
            cli.log_verbose(f"Status: {'Success' if response.success else 'Failed'}", "success" if response.success else "error")
            if response.input_tokens or response.output_tokens:
                cli.log_verbose(f"Tokens: {response.input_tokens} in / {response.output_tokens} out", "info", indent=1)
            if response.error:
                cli.log_verbose(f"Error: {response.error}", "error", indent=1)
            if original_agent_response:
                original_agent_response(response)

        def verbose_progress(step_name: str, current: int, total: int):
            """Show progress during assessment/planning"""
            bar_width = 20
            filled = int(bar_width * current / total)
            bar = "█" * filled + "░" * (bar_width - filled)
            cli.log_verbose(f"[{bar}] {current}/{total} Analyzing: {step_name}", "substep")

            # Show special message when Final Assessment Review starts
            if "Final Assessment Review" in step_name:
                print("\nNow confirming assessment with AI voters...")
                print("Each voter will review the complete assessment:\n")

        def verbose_voter_progress(voter_id: str, vote, total: int, completed: int):
            """Show progress as each voter completes their review"""
            # Format voter name nicely
            voter_name = voter_id.replace("voter_", "").replace("_", " ").title()
            if vote:
                result = "PASS" if vote.vote == "pass" else "FAIL"
                confidence = vote.confidence
                print(f"  ✓ Confirmed {voter_name} review... {result} ({confidence}% confidence) [{completed}/{total}]")
            else:
                print(f"  ✓ Confirmed {voter_name} review... (no response) [{completed}/{total}]")

        def verbose_lesson_learned(step_name: str, pattern: str):
            """Show when a lesson is learned in self-improvement mode"""
            print(f"  📚 Lesson learned in {step_name}: {pattern[:60]}...")

        # Set callbacks
        orchestrator.on_phase_change = verbose_phase_change
        orchestrator.on_gate_result = verbose_gate_result
        orchestrator.on_agent_response = verbose_agent_response
        orchestrator.on_progress = verbose_progress
        orchestrator.on_voter_progress = verbose_voter_progress
        orchestrator.on_lesson_learned = verbose_lesson_learned

    def _run_comprehensive_workflow(self, project_name: str, source_path: str):
        """Run the full 3-phase assessment and improvement workflow using Orchestrator"""
        import asyncio
        import time
        import threading
        import webbrowser
        import json
        from dataclasses import asdict

        project_dir = self.projects_dir / project_name

        try:
            from core.orchestrator import Orchestrator, WorkflowPhase
            from core.report_generator import ReportGenerator
            from core.monitor import WebMonitor
        except ImportError as e:
            print(f"\n❌ Required modules not available: {e}")
            self.get_input("Press Enter...")
            return

        # Initialize Orchestrator (includes audit logging)
        orchestrator = Orchestrator(
            project_id=project_name,
            project_dir=project_dir,
            enable_audit=True
        )

        # Set up verbose callbacks if verbose mode enabled
        if self.verbose:
            self._setup_verbose_callbacks(orchestrator)

        # Select assessment mode
        assessment_mode, test_steps = self._select_assessment_mode()

        # Start the ingest workflow
        state = orchestrator.start_ingest(
            source_path,
            f"Analyzing {source_path}",
            assessment_mode=assessment_mode
        )

        # Set test_steps if specified (for Quick Test mode)
        if test_steps:
            state.test_steps = test_steps

        self.log_verbose(f"Starting ingest workflow for {source_path}", "step")
        self.log_verbose(f"Session ID: {orchestrator.audit_logger.session_id if orchestrator.audit_logger else 'N/A'}", "info")
        self.log_verbose(f"Assessment mode: {assessment_mode}", "info")
        if test_steps:
            self.log_verbose(f"Test steps: {', '.join(test_steps)}", "info")

        # Show self-improvement mode notice
        if assessment_mode == "self_improvement":
            print("\n🎓 SELF-IMPROVEMENT MODE ACTIVE")
            print("   Voters will review each assessment step.")
            print("   Feedback from rejections will be captured as lessons.")
            print("   This makes future assessments more accurate.\n")

        # Auto-start web monitor in background
        if orchestrator.audit_logger:
            session_id = orchestrator.audit_logger.session_id
            audit_dir = project_dir / "audit"
            session_file = audit_dir / f"session_{session_id}.jsonl"

            # Debug: show monitor setup info
            print(f"\n📊 Setting up web monitor:")
            print(f"   Project dir: {project_dir}")
            print(f"   Session ID: {session_id}")
            print(f"   Audit dir exists: {audit_dir.exists()}")
            print(f"   Session file: {session_file}")
            print(f"   Session file exists: {session_file.exists()}")

            monitor = WebMonitor(
                project_dir,
                session_id=session_id,
                port=8765
            )
            monitor_thread = threading.Thread(
                target=lambda: monitor.start(open_browser=False),
                daemon=True
            )
            monitor_thread.start()
            time.sleep(0.5)
            webbrowser.open("http://localhost:8765")
            print(f"   Web URL: http://localhost:8765")

            # Auto-launch console monitor in separate terminal window
            cli_path = Path(__file__).resolve()
            console_cmd = f'python "{cli_path}" monitor {project_name} --follow'
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    f'start "AI-Dev Monitor" cmd /k {console_cmd}',
                    shell=True
                )
            else:  # Linux/Mac
                try:
                    subprocess.Popen(
                        ['gnome-terminal', '--', 'bash', '-c', console_cmd],
                        start_new_session=True
                    )
                except FileNotFoundError:
                    # Try xterm as fallback
                    try:
                        subprocess.Popen(
                            ['xterm', '-e', console_cmd],
                            start_new_session=True
                        )
                    except FileNotFoundError:
                        print("📺 Console monitor: Unable to open terminal")
            print("📺 Console monitor launched in separate terminal\n")

        # Start quit listener thread
        def quit_listener():
            """Background thread to listen for 'q' key to request quit."""
            while not orchestrator.quit_requested:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                            if key == 'q':
                                print("\n⏹️  Quit requested. Finishing current step...")
                                orchestrator.request_quit()
                                break
                    else:
                        import select
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.read(1).lower()
                            if key == 'q':
                                print("\n⏹️  Quit requested. Finishing current step...")
                                orchestrator.request_quit()
                                break
                    time.sleep(0.1)
                except Exception:
                    break

        quit_thread = threading.Thread(target=quit_listener, daemon=True)
        quit_thread.start()
        print("💡 Press [Q] at any time to quit gracefully\n")

        # Run the workflow phase by phase
        reports_dir = project_dir / "reports"
        generator = ReportGenerator(reports_dir)

        while state.current_phase not in (
            WorkflowPhase.COMPLETE,
            WorkflowPhase.FAILED,
            WorkflowPhase.ESCALATED,
            WorkflowPhase.INGEST_EXECUTION  # Stop before execution for interactive mode
        ):
            phase = state.current_phase

            if not self.verbose:
                self.clear_screen()
            self.print_header(f"PHASE: {phase.value.upper().replace('_', ' ')}")

            if phase == WorkflowPhase.INGEST_ASSESSMENT:
                print("Running comprehensive codebase assessment...")
                print("Analyzing: Architecture, Code Quality, Security, UX,")
                print("           Navigation, Accessibility, Testing, Documentation")
                print()
                self.log_verbose("Starting codebase analysis...", "step")

            elif phase == WorkflowPhase.INGEST_ASSESSMENT_REVIEW:
                print("AI Voters are reviewing the assessment...")
                print("Voters: Completeness, Clarity, Feasibility, Security, Code Quality")
                print()
                self.log_verbose("Initiating voting gate: assessment_approval", "step")

            elif phase == WorkflowPhase.INGEST_PLANNING:
                print("Generating improvement roadmap...")
                print()
                self.log_verbose("Starting improvement planning...", "step")

            elif phase == WorkflowPhase.INGEST_PLANNING_REVIEW:
                print("AI Voters are reviewing the plan...")
                print("Voters: Feasibility, User Value, Maintainability, Scalability, Integration")
                print()
                self.log_verbose("Initiating voting gate: planning_approval", "step")

            # Run the phase
            success, output = asyncio.run(orchestrator.run_phase())

            # Check for quit request
            if output == "QUIT_REQUESTED":
                print("\n⏹️  Workflow stopped by user request.")
                print("   Progress has been logged to the audit trail.")
                orchestrator.finalize_audit()
                return

            if not success:
                print(f"\n⚠️  Phase issue: {output[:200]}")
                if state.current_phase == WorkflowPhase.ESCALATED:
                    print("\n🚨 Workflow escalated - requires human review")
                    self.get_input("Press Enter to continue...")
                    break

            # Show results after assessment
            if phase == WorkflowPhase.INGEST_ASSESSMENT and orchestrator.ingest_assessment:
                assessment = orchestrator.ingest_assessment
                self._show_assessment_summary(assessment)

                # Generate and save report
                assessment_report_path = generator.generate_assessment_report(assessment)
                assessment_file = project_dir / "assessment.json"
                with open(assessment_file, "w", encoding="utf-8") as f:
                    json.dump(asdict(assessment), f, indent=2, default=str)

                print(f"\n📄 Full report: {assessment_report_path}")

                # Human checkpoint for pair/balanced modes
                if self.autonomy_level in ["pair", "balanced"]:
                    print()
                    print(self.SUBHEADER)
                    print("  [V] View report  [A] Continue  [S] Save & exit  [D] Discard  [Q] Quit")
                    print(self.SUBHEADER)
                    while True:
                        choice = self.get_input("Choice: ").lower()
                        if choice == "v":
                            webbrowser.open(assessment_report_path.resolve().as_uri())
                        elif choice == "a":
                            break
                        elif choice == "s":
                            print("\n✅ Assessment saved.")
                            orchestrator.finalize_audit()
                            return
                        elif choice == "q":
                            print("\n👋 Quitting workflow.")
                            orchestrator.finalize_audit()
                            return
                        elif choice == "d":
                            # Discard - remove generated files
                            if assessment_file.exists():
                                assessment_file.unlink()
                            if assessment_report_path.exists():
                                assessment_report_path.unlink()
                            print("\n🗑️  Assessment discarded.")
                            orchestrator.finalize_audit()
                            return

            # Show results after planning
            elif phase == WorkflowPhase.INGEST_PLANNING and orchestrator.ingest_plan:
                plan = orchestrator.ingest_plan
                self._show_planning_summary(plan)

                # Generate and save report
                planning_report_path = generator.generate_planning_report(plan)
                plan_file = project_dir / "improvement_plan.json"
                with open(plan_file, "w", encoding="utf-8") as f:
                    json.dump(asdict(plan), f, indent=2, default=str)

                print(f"\n📄 Full report: {planning_report_path}")

                # Human checkpoint
                if self.autonomy_level in ["pair", "balanced"]:
                    print()
                    print(self.SUBHEADER)
                    print("  [V] View report  [A] Continue  [S] Save & exit  [D] Discard  [Q] Quit")
                    print(self.SUBHEADER)
                    while True:
                        choice = self.get_input("Choice: ").lower()
                        if choice == "v":
                            webbrowser.open(planning_report_path.resolve().as_uri())
                        elif choice == "a":
                            break
                        elif choice == "s":
                            print("\n✅ Plan saved.")
                            orchestrator.finalize_audit()
                            return
                        elif choice == "q":
                            print("\n👋 Quitting workflow.")
                            orchestrator.finalize_audit()
                            return
                        elif choice == "d":
                            # Discard - remove generated files
                            if plan_file.exists():
                                plan_file.unlink()
                            if planning_report_path.exists():
                                planning_report_path.unlink()
                            print("\n🗑️  Plan discarded.")
                            orchestrator.finalize_audit()
                            return

            # Show gate results
            elif "_review" in phase.value.lower():
                if state.gate_results:
                    last_result = state.gate_results[-1]
                    self._show_gate_result(last_result)
                    if self.autonomy_level == "pair":
                        self.get_input("\nPress Enter to continue...")

        # Execution phase
        if state.current_phase == WorkflowPhase.INGEST_EXECUTION:
            self._run_execution_phase(
                project_name,
                orchestrator.ingest_plan,
                orchestrator.ingest_assessment,
                orchestrator.audit_logger
            )

        # Finalize
        orchestrator.finalize_audit()

    def _show_assessment_summary(self, assessment):
        """Display assessment summary"""
        print(f"\nOverall Score: {assessment.overall_score}/100 ({assessment.overall_status.upper()})")
        print()

        categories = [
            ("Architecture", assessment.architecture.score),
            ("Code Quality", assessment.code_quality.score),
            ("Security", assessment.security.score),
            ("Tech Debt", assessment.tech_debt.score),
            ("UX Styling", assessment.ux_styling.score),
            ("Navigation", assessment.ux_navigation.score),
            ("Accessibility", assessment.ux_accessibility.score),
            ("Performance", assessment.performance.score),
            ("Testing", assessment.testing.score),
            ("Documentation", assessment.documentation.score),
        ]

        for name, score in categories:
            bar = "█" * (score // 10) + "░" * (10 - score // 10)
            status = "🔴" if score < 40 else "🟡" if score < 70 else "🟢"
            print(f"  {status} {name:15} [{bar}] {score}")

        print()
        print(f"📊 Total Findings: {len(assessment.all_findings)}")
        print(f"🚨 Critical: {assessment.critical_count}")
        print(f"⚠️  High: {assessment.high_count}")
        print(f"🤖 AI Can Fix: {assessment.ai_fixable_count}")

    def _show_planning_summary(self, plan):
        """Display planning summary"""
        print(f"\n📋 Roadmap Items: {plan.total_items}")
        print(f"🚨 Critical: {plan.critical_items}")
        print(f"🎯 Quick Wins: {plan.quick_wins}")
        print(f"🤖 AI Opportunities: {plan.ai_opportunities_count}")
        print(f"⏱️  Est. Total Effort: {plan.estimated_total_hours:.0f} hours")
        print()
        print("Milestones:")
        for m in plan.milestones:
            print(f"  {m.id}: {m.name} ({m.estimated_hours:.0f}h) - {m.target_completion}")
        print()
        print("💡 Recommendation:")
        print(f"   {plan.recommended_approach}")

    def _show_gate_result(self, result):
        """Display voting gate result"""
        print()
        print(self.SUBHEADER)
        print(f"  GATE RESULT: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        print(self.SUBHEADER)
        print()
        print(f"Gate: {result.gate_id}")
        pass_count = sum(1 for v in result.votes if v.vote == 'pass')
        fail_count = len(result.votes) - pass_count
        pass_votes = [v for v in result.votes if v.vote == "pass"]
        fail_votes = [v for v in result.votes if v.vote == "fail"]
        pass_conf = sum(v.confidence for v in pass_votes) // len(pass_votes) if pass_votes else 0
        fail_conf = sum(v.confidence for v in fail_votes) // len(fail_votes) if fail_votes else 0

        # Show confidence per outcome with voter roles
        pass_roles = ", ".join(v.voter_role for v in pass_votes)
        fail_roles = ", ".join(v.voter_role for v in fail_votes)

        pass_str = f"{pass_count} pass" + (f" ({pass_conf}%): {pass_roles}" if pass_votes else "")
        fail_str = f"{fail_count} fail" + (f" ({fail_conf}%): {fail_roles}" if fail_votes else "")
        print(f"Votes: {pass_str} / {fail_str}")
        print()
        print("Voter Feedback:")
        for vote in result.votes:
            status = "✅" if vote.vote == "pass" else "❌"
            print(f"  {status} {vote.voter_id} ({vote.confidence}%): {vote.reasoning[:100]}...")
        if result.aggregated_feedback:
            print()
            print(f"Summary: {result.aggregated_feedback[:300]}...")

    def _run_execution_phase(self, project_name: str, plan, assessment, audit=None):
        """Phase 3: Execute improvements"""
        from dataclasses import asdict
        
        project_dir = self.projects_dir / project_name
        
        while True:
            self.clear_screen()
            self.print_header("PHASE 3: EXECUTION")
            
            # Count remaining items
            remaining = [item for item in plan.roadmap if item.status == "pending"]
            completed = [item for item in plan.roadmap if item.status == "completed"]
            
            print(f"📊 Progress: {len(completed)}/{len(plan.roadmap)} items completed")
            print(f"⏱️  Remaining effort: {sum(i.estimated_hours for i in remaining):.0f} hours")
            print()
            
            print("Execution Options:")
            print()
            print("  [1] Work by Milestone")
            print("      Execute items grouped by milestone")
            print()
            print("  [2] Quick Wins First")
            print("      Start with low-effort, high-impact items")
            print()
            print("  [3] Critical Issues Only")
            print("      Focus on critical and high priority items")
            print()
            print("  [4] Select Individual Items")
            print("      Choose specific items from the roadmap")
            print()
            print("  [R] View Reports")
            print("  [Q] Exit to Project Menu")
            print()
            
            choice = self.get_input("Choice: ").lower()
            
            if choice == "1":
                self._execute_by_milestone(project_name, plan)
            elif choice == "2":
                self._execute_quick_wins(project_name, plan)
            elif choice == "3":
                self._execute_critical_items(project_name, plan)
            elif choice == "4":
                self._execute_individual_items(project_name, plan)
            elif choice == "r":
                reports_dir = project_dir / "reports"
                import webbrowser
                for report in reports_dir.glob("*.html"):
                    webbrowser.open(report.resolve().as_uri())
            elif choice == "q":
                # Finalize audit on exit
                if audit:
                    audit.log_phase_change("execution", "exit")
                    audit.finalize()
                self.project_menu()
                return
    
    def _execute_individual_items(self, project_name: str, plan):
        """Select and execute individual roadmap items"""
        project_dir = self.projects_dir / project_name
        
        while True:
            self.clear_screen()
            self.print_header("SELECT ITEMS TO IMPLEMENT")
            
            # Group by status
            pending = [item for item in plan.roadmap if item.status == "pending"]
            completed = [item for item in plan.roadmap if item.status == "completed"]
            
            print(f"Showing {len(pending)} pending items (sorted by priority)\n")
            
            # Sort by priority
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "future": 4}
            sorted_items = sorted(pending, key=lambda x: priority_order.get(x.priority, 5))
            
            # Display items
            for i, item in enumerate(sorted_items[:20], 1):
                priority_icon = {
                    "critical": "🚨",
                    "high": "⚠️",
                    "medium": "📋",
                    "low": "📝",
                    "future": "💭"
                }.get(item.priority, "•")
                
                ai_badge = "🤖" if item.ai_assisted else "  "
                
                print(f"  [{i:2}] {priority_icon} {ai_badge} {item.title[:50]}")
                print(f"       {item.category} | {item.effort} | {item.estimated_hours:.0f}h")
            
            if len(sorted_items) > 20:
                print(f"\n  ... and {len(sorted_items) - 20} more items")
            
            print()
            print(f"  [C] Mark item as Completed")
            print(f"  [S] Skip item")
            print(f"  [B] Back to Execution Menu")
            print()
            
            choice = self.get_input("Select item # or action: ").lower()
            
            if choice == "b":
                return
            elif choice == "c":
                item_num = self.get_input("Item # to mark complete: ")
                try:
                    idx = int(item_num) - 1
                    if 0 <= idx < len(sorted_items):
                        sorted_items[idx].status = "completed"
                        print(f"\n✅ Marked '{sorted_items[idx].title}' as completed")
                        self._save_plan(project_dir, plan)
                        self.get_input("Press Enter...")
                except:
                    pass
            elif choice == "s":
                item_num = self.get_input("Item # to skip: ")
                try:
                    idx = int(item_num) - 1
                    if 0 <= idx < len(sorted_items):
                        sorted_items[idx].status = "skipped"
                        print(f"\n⏭️  Skipped '{sorted_items[idx].title}'")
                        self._save_plan(project_dir, plan)
                        self.get_input("Press Enter...")
                except:
                    pass
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(sorted_items):
                        self._show_item_details(sorted_items[idx], plan)
                except:
                    pass
    
    def _show_item_details(self, item, plan):
        """Show details of a roadmap item"""
        self.clear_screen()
        self.print_header(f"ITEM: {item.id}")
        
        print(f"Title: {item.title}")
        print(f"Category: {item.category}")
        print(f"Priority: {item.priority.upper()}")
        print(f"Effort: {item.effort} ({item.estimated_hours:.0f} hours)")
        print(f"Impact: {item.impact}")
        print()
        
        print("Description:")
        print(f"  {item.description}")
        print()
        
        print("Tasks:")
        for task in item.tasks:
            print(f"  • {task}")
        print()
        
        if item.ai_assisted:
            print("🤖 AI Implementation:")
            print(f"  {item.ai_implementation}")
            print()
        
        if item.affected_files:
            print("Affected Files:")
            for f in item.affected_files:
                print(f"  • {f}")
            print()
        
        print(self.SUBHEADER)
        print("  [C] Mark as Completed")
        print("  [S] Skip this item")
        print("  [B] Back to list")
        print()
        
        choice = self.get_input("Choice: ").lower()
        
        if choice == "c":
            item.status = "completed"
            print(f"\n✅ Marked as completed")
        elif choice == "s":
            item.status = "skipped"
            print(f"\n⏭️  Skipped")
    
    def _execute_by_milestone(self, project_name: str, plan):
        """Execute items grouped by milestone"""
        self.clear_screen()
        self.print_header("EXECUTE BY MILESTONE")
        
        for i, milestone in enumerate(plan.milestones, 1):
            items = [item for item in plan.roadmap if item.id in milestone.items]
            pending = [item for item in items if item.status == "pending"]
            print(f"  [{i}] {milestone.id}: {milestone.name}")
            print(f"      {len(pending)}/{len(items)} pending | {milestone.estimated_hours:.0f}h")
        
        print()
        choice = self.get_input("Select milestone: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plan.milestones):
                milestone = plan.milestones[idx]
                items = [item for item in plan.roadmap if item.id in milestone.items]
                
                print(f"\nMilestone: {milestone.name}")
                print(f"Items: {len(items)}")
                
                for item in items:
                    if item.status == "pending":
                        print(f"\n  → {item.title}")
                        confirm = self.get_input("    Mark complete? [y/N]: ").lower()
                        if confirm == "y":
                            item.status = "completed"
                
                self._save_plan(self.projects_dir / project_name, plan)
        except:
            pass
        
        self.get_input("\nPress Enter to continue...")
    
    def _execute_quick_wins(self, project_name: str, plan):
        """Execute quick win items"""
        quick_wins = [
            item for item in plan.roadmap 
            if item.effort in ["xs", "small"] and item.status == "pending"
        ]
        
        self.clear_screen()
        self.print_header("QUICK WINS")
        
        print(f"Found {len(quick_wins)} quick win items\n")
        
        for i, item in enumerate(quick_wins[:15], 1):
            print(f"  [{i}] {item.title}")
            print(f"      {item.category} | {item.estimated_hours:.0f}h")
        
        print()
        print("Mark items as complete by entering their numbers")
        print("Enter 'done' when finished")
        print()
        
        while True:
            choice = self.get_input("Item # (or 'done'): ").lower()
            if choice == "done":
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(quick_wins):
                    quick_wins[idx].status = "completed"
                    print(f"  ✅ {quick_wins[idx].title}")
            except:
                pass
        
        self._save_plan(self.projects_dir / project_name, plan)
    
    def _execute_critical_items(self, project_name: str, plan):
        """Execute critical and high priority items"""
        critical_items = [
            item for item in plan.roadmap 
            if item.priority in ["critical", "high"] and item.status == "pending"
        ]
        
        self.clear_screen()
        self.print_header("CRITICAL ITEMS")
        
        print(f"Found {len(critical_items)} critical/high priority items\n")
        
        for i, item in enumerate(critical_items[:15], 1):
            priority_icon = "🚨" if item.priority == "critical" else "⚠️"
            print(f"  [{i}] {priority_icon} {item.title}")
            print(f"      {item.category} | {item.estimated_hours:.0f}h")
        
        print()
        print("Mark items as complete by entering their numbers")
        print("Enter 'done' when finished")
        print()
        
        while True:
            choice = self.get_input("Item # (or 'done'): ").lower()
            if choice == "done":
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(critical_items):
                    critical_items[idx].status = "completed"
                    print(f"  ✅ {critical_items[idx].title}")
            except:
                pass
        
        self._save_plan(self.projects_dir / project_name, plan)
    
    def _save_plan(self, project_dir: Path, plan):
        """Save updated plan to disk"""
        from dataclasses import asdict
        import json
        
        plan_file = project_dir / "improvement_plan.json"
        with open(plan_file, "w") as f:
            json.dump(asdict(plan), f, indent=2, default=str)
    
    def _update_project_github(self, project_id: str, github_repo):
        """Update project config with GitHub info"""
        project_dir = self.projects_dir / project_id
        config_file = project_dir / "project.yaml"
        
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            config["github"] = {
                "repo": github_repo.full_name,
                "url": github_repo.url,
                "default_branch": github_repo.default_branch,
                "connected": datetime.now().strftime("%Y-%m-%d"),
            }
            
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    # ════════════════════════════════════════════════════════════
    # QUICK TASK
    # ════════════════════════════════════════════════════════════
    
    def quick_task_flow(self):
        """Run a quick one-off task"""
        self.clear_screen()
        self.print_header("QUICK TASK")
        
        # Select project (optional)
        projects = self._list_projects()
        
        print("Which project? (optional)")
        for i, p in enumerate(projects[:5], 1):
            print(f"  [{i}] {p['name']}")
        print(f"  [0] None (general task)")
        
        choice = self.get_input("\nChoice [0]: ") or "0"
        
        project_context = None
        if choice != "0":
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(projects):
                    project_context = projects[idx]["id"]
            except:
                pass
        
        # Select agent
        print("\nWhich agent?")
        agents = [
            ("1", "Developer        - Write code"),
            ("2", "Code Reviewer    - Review code"),
            ("3", "Architect        - Design decisions"),
            ("4", "Security         - Security review"),
            ("5", "Test Writer      - Write tests"),
            ("6", "DevOps           - Deployment help"),
            ("7", "Tech Debt        - Analyze debt"),
        ]
        
        for key, label in agents:
            print(f"  [{key}] {label}")
        
        agent_choice = self.get_input("\nChoice: ")
        
        agent_map = {
            "1": "developer",
            "2": "code_reviewer",
            "3": "solutions_architect",
            "4": "security_specialist",
            "5": "test_writer",
            "6": "devops",
            "7": "tech_debt_analyst",
        }
        
        agent = agent_map.get(agent_choice, "developer")
        
        # Get task
        task = self.get_input("\nTask: ")
        if not task:
            return
        
        print(f"\n🤖 Running {agent} agent...")
        print(f"   Project: {project_context or 'None'}")
        print(f"   Task: {task}")
        print()
        print("(Agent execution would happen here)")
        print("(In full implementation, this calls the agent orchestrator)")
        
        self.get_input("\nPress Enter to continue...")
    
    # ════════════════════════════════════════════════════════════
    # CONTEXT GRAPH
    # ════════════════════════════════════════════════════════════
    
    def context_graph_flow(self):
        """Explore the context graph - precedents and decision traces"""
        try:
            from core.context_graph import get_context_graph, find_precedents
        except ImportError:
            print("\n❌ Context graph module not available")
            self.get_input("Press Enter...")
            return
        
        graph = get_context_graph()
        
        while True:
            self.clear_screen()
            self.print_header("CONTEXT GRAPH")
            
            # Show stats
            total_traces = len(graph.index.get("traces", {}))
            total_projects = len(graph.index.get("by_project", {}))
            
            print(f"📊 {total_traces} decision traces across {total_projects} projects")
            print()
            
            self.print_menu([
                ("1", "Find precedents     (search similar decisions)"),
                ("2", "View project traces (decisions for a project)"),
                ("3", "Pattern analysis    (insights by decision type)"),
                ("4", "Record outcome      (update decision result)"),
                ("5", "Browse all traces"),
                ("b", "Back"),
            ])
            
            choice = self.get_input().lower()
            
            if choice == "1":
                self._find_precedents_flow(graph)
            elif choice == "2":
                self._view_project_traces_flow(graph)
            elif choice == "3":
                self._pattern_analysis_flow(graph)
            elif choice == "4":
                self._record_outcome_flow(graph)
            elif choice == "5":
                self._browse_traces_flow(graph)
            elif choice in ["b", "back", "q"]:
                return
    
    def _find_precedents_flow(self, graph):
        """Search for similar past decisions"""
        self.clear_screen()
        self.print_subheader("FIND PRECEDENTS")
        
        context = self.get_input("Describe your situation:\n> ")
        if not context:
            return
        
        print("\nDecision type (optional):")
        print("  [1] Architecture")
        print("  [2] Security")
        print("  [3] Code review")
        print("  [4] Requirements")
        print("  [5] Any")
        
        type_choice = self.get_input("\nChoice [5]: ") or "5"
        
        type_map = {
            "1": "architecture",
            "2": "security",
            "3": "code_review",
            "4": "requirements",
        }
        decision_type = type_map.get(type_choice)
        
        print("\n🔍 Searching precedents...")
        
        precedents = graph.find_precedents(
            context=context,
            decision_type=decision_type,
            limit=5,
        )
        
        if not precedents:
            print("\n❌ No relevant precedents found")
        else:
            print(f"\n✅ Found {len(precedents)} relevant precedents:\n")
            
            for i, p in enumerate(precedents, 1):
                outcome_icon = "✅" if p.outcome_score > 0.5 else "⚠️" if p.outcome_score >= 0 else "❌"
                
                print(f"{'─' * 50}")
                print(f"{i}. {p.project} ({p.similarity:.0%} similar)")
                print(f"   Context: {p.context[:60]}...")
                print(f"   Decision: {p.decision[:60]}...")
                print(f"   Outcome: {outcome_icon} {p.outcome} (score: {p.outcome_score:+.1f})")
                print(f"   Trace ID: {p.trace_id}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _view_project_traces_flow(self, graph):
        """View all traces for a project"""
        self.clear_screen()
        self.print_subheader("PROJECT DECISION TRACES")
        
        # List projects with traces
        projects_with_traces = list(graph.index.get("by_project", {}).keys())
        
        if not projects_with_traces:
            print("No projects with decision traces yet.")
            self.get_input("Press Enter...")
            return
        
        print("Projects with traces:")
        for i, pid in enumerate(projects_with_traces[:10], 1):
            trace_count = len(graph.index["by_project"][pid])
            print(f"  [{i}] {pid} ({trace_count} traces)")
        
        choice = self.get_input("\nChoice: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects_with_traces):
                project_id = projects_with_traces[idx]
                traces = graph.get_project_traces(project_id)
                
                print(f"\nDecisions for {project_id}:\n")
                
                for trace in traces[:10]:
                    outcome = trace.get("outcome", "pending")
                    outcome_icon = "✅" if trace.get("outcome_score", 0) > 0.5 else "⚠️" if outcome != "failure" else "❌"
                    
                    print(f"  {outcome_icon} [{trace['trace_id']}]")
                    print(f"     {trace['decision_type']}: {trace['decision_summary'][:50]}")
                    print(f"     Actor: {trace['actor']} | {trace['timestamp'][:10]}")
                    print()
        except:
            pass
        
        self.get_input("Press Enter to continue...")
    
    def _pattern_analysis_flow(self, graph):
        """Analyze patterns by decision type"""
        self.clear_screen()
        self.print_subheader("PATTERN ANALYSIS")
        
        decision_types = list(graph.index.get("by_type", {}).keys())
        
        if not decision_types:
            print("No decision traces yet.")
            self.get_input("Press Enter...")
            return
        
        print("Decision types:")
        for i, dtype in enumerate(decision_types, 1):
            count = len(graph.index["by_type"][dtype])
            print(f"  [{i}] {dtype} ({count} decisions)")
        
        choice = self.get_input("\nChoice: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(decision_types):
                dtype = decision_types[idx]
                summary = graph.get_pattern_summary(dtype)
                
                print(f"\n📊 Pattern Analysis: {dtype}\n")
                print(f"Total decisions: {summary.get('total_traces', 0)}")
                
                outcomes = summary.get("outcome_distribution", {})
                if outcomes:
                    print("\nOutcome distribution:")
                    for outcome, count in outcomes.items():
                        print(f"  {outcome}: {count}")
                
                avg_score = summary.get("average_outcome_score")
                if avg_score is not None:
                    print(f"\nAverage outcome score: {avg_score:+.2f}")
                
                common = summary.get("common_decisions", {})
                if common:
                    print("\nCommon decisions:")
                    for decision, count in list(common.items())[:5]:
                        print(f"  • {decision}... ({count}x)")
        except:
            pass
        
        self.get_input("\nPress Enter to continue...")
    
    def _record_outcome_flow(self, graph):
        """Record outcome for a decision"""
        self.clear_screen()
        self.print_subheader("RECORD OUTCOME")
        
        trace_id = self.get_input("Trace ID: ")
        if not trace_id:
            return
        
        trace = graph.get_trace(trace_id)
        if not trace:
            print(f"\n❌ Trace not found: {trace_id}")
            self.get_input("Press Enter...")
            return
        
        print(f"\nTrace: {trace['context'][:60]}")
        print(f"Decision: {trace['decision_summary']}")
        print(f"Current outcome: {trace.get('outcome', 'pending')}")
        
        print("\nNew outcome:")
        print("  [1] Success")
        print("  [2] Partial success")
        print("  [3] Failure")
        
        choice = self.get_input("\nChoice: ")
        
        outcome_map = {"1": "success", "2": "partial_success", "3": "failure"}
        outcome = outcome_map.get(choice)
        
        if not outcome:
            return
        
        score_map = {"1": 1.0, "2": 0.5, "3": -1.0}
        score = score_map[choice]
        
        notes = self.get_input("Notes (optional): ")
        
        graph.record_outcome(trace_id, outcome, score, notes)
        
        print(f"\n✅ Outcome recorded: {outcome} ({score:+.1f})")
        self.get_input("Press Enter to continue...")
    
    def _browse_traces_flow(self, graph):
        """Browse all decision traces"""
        self.clear_screen()
        self.print_subheader("ALL DECISION TRACES")
        
        all_traces = list(graph.index.get("traces", {}).items())
        
        if not all_traces:
            print("No decision traces yet.")
            print("\nTraces are created when voting gates run.")
            self.get_input("Press Enter...")
            return
        
        print(f"Showing {min(20, len(all_traces))} of {len(all_traces)} traces:\n")
        
        for trace_id, meta in all_traces[:20]:
            print(f"  [{trace_id}]")
            print(f"     {meta.get('decision_type', 'unknown')}: {meta.get('context', '')[:40]}...")
            print(f"     Project: {meta.get('project_id', '?')} | {meta.get('timestamp', '')[:10]}")
            print()
        
        self.get_input("Press Enter to continue...")
    
    # ════════════════════════════════════════════════════════════
    # GLOBAL USAGE
    # ════════════════════════════════════════════════════════════
    
    def global_usage_flow(self):
        """View usage and costs across all projects"""
        try:
            from core.usage_tracker import get_tracker, PRICING
        except ImportError:
            print("\n❌ Usage tracker not available")
            self.get_input("Press Enter...")
            return
        
        tracker = get_tracker(str(self.projects_dir))
        
        self.clear_screen()
        self.print_header("USAGE REPORT")
        
        summaries = tracker.get_all_projects_summary()
        
        if not summaries:
            print("No usage data yet.")
            print("\nUsage is tracked when agents run API calls.")
            print("\nPricing (Claude 3.5 Sonnet):")
            print("  Input:  $3.00 / 1M tokens")
            print("  Output: $15.00 / 1M tokens")
            self.get_input("\nPress Enter to continue...")
            return
        
        # Calculate totals
        total_cost = 0.0
        total_calls = 0
        total_input = 0
        total_output = 0
        
        for summary in summaries.values():
            total_cost += summary.total_cost
            total_calls += summary.call_count
            total_input += summary.total_input_tokens
            total_output += summary.total_output_tokens
        
        # Header stats
        print(f"{'─' * 55}")
        print(f"  Total Cost:         ${total_cost:.4f}")
        print(f"  Total API Calls:    {total_calls:,}")
        print(f"  Total Input Tokens: {total_input:,}")
        print(f"  Total Output Tokens:{total_output:,}")
        print(f"{'─' * 55}")
        print()
        
        # Per-project breakdown
        print(f"{'Project':<25} {'Calls':>10} {'Cost':>15}")
        print(f"{'-'*25} {'-'*10} {'-'*15}")
        
        for project_id, summary in sorted(summaries.items(), key=lambda x: x[1].total_cost, reverse=True):
            print(f"{project_id[:25]:<25} {summary.call_count:>10,} ${summary.total_cost:>13.4f}")
        
        print(f"{'-'*25} {'-'*10} {'-'*15}")
        print(f"{'TOTAL':<25} {total_calls:>10,} ${total_cost:>13.4f}")
        print()
        
        # Cost context
        if total_cost > 0:
            avg_per_call = total_cost / total_calls
            print(f"Average cost per call: ${avg_per_call:.4f}")
            
            # Project costs
            if total_calls > 0:
                features_estimated = total_calls // 10  # Rough estimate
                print(f"Estimated features built: ~{features_estimated}")
        
        self.get_input("\nPress Enter to continue...")

    # ════════════════════════════════════════════════════════════
    # WEB DASHBOARD
    # ════════════════════════════════════════════════════════════

    def web_dashboard_flow(self):
        """Start standalone web dashboard (monitor + admin)"""
        self.clear_screen()
        self.print_header("WEB DASHBOARD")

        print("Starting web dashboard server...")
        print()
        print("  Monitor: http://localhost:8765/")
        print("  Admin:   http://localhost:8765/admin")
        print()
        print("Press Ctrl+C to stop the server.")
        print()

        try:
            from core.monitor import StandaloneServer
            server = StandaloneServer(self.projects_dir, port=8765)
            server.start(open_browser=True)
        except KeyboardInterrupt:
            print("\nServer stopped.")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.get_input("\nPress Enter to continue...")

    # ════════════════════════════════════════════════════════════
    # PROJECT MENU
    # ════════════════════════════════════════════════════════════

    def project_menu(self):
        """Project-level menu"""
        while True:
            self.clear_screen()
            
            project = self.current_config.get("project", {})
            
            self.print_header(f"PROJECT: {project.get('name', 'Unknown')}")
            
            print(f"Type: {project.get('type', 'new')}")
            print(f"Status: {project.get('status', 'active')}")
            print(f"Stage: {project.get('stage', 'unknown')}")
            
            # Show tech stack summary
            stack = self.current_config.get("tech_stack", {})
            if stack and not stack.get("custom"):
                techs = []
                if stack.get("frontend"):
                    techs.append(stack["frontend"][0] if isinstance(stack["frontend"], list) else stack["frontend"])
                if stack.get("backend"):
                    techs.append(stack["backend"][0] if isinstance(stack["backend"], list) else stack["backend"])
                if techs:
                    print(f"Stack: {' + '.join(techs)}")
            
            # Show GitHub if connected
            github = self.current_config.get("github", {})
            if github:
                print(f"GitHub: {github.get('repo', 'connected')}")
            
            # Show usage cost
            try:
                from core.usage_tracker import get_tracker
                tracker = get_tracker(str(self.projects_dir))
                summary = tracker.get_project_summary(self.current_project)
                if summary and summary.total_cost > 0:
                    print(f"API Cost: ${summary.total_cost:.4f} ({summary.call_count} calls)")
            except:
                pass
            
            print()
            
            self.print_menu([
                ("1", "Add feature       (build something new)"),
                ("2", "Fix issue         (bug or problem)"),
                ("3", "Evaluate          (health check)"),
                ("4", "Improve           (refactor, tests, security)"),
                ("5", "Deploy            (push to production)"),
                ("6", "View details      (files, config)"),
                ("7", "Usage report      (tokens, costs)"),
                ("b", "Back to main menu"),
            ])
            
            choice = self.get_input().lower()
            
            if choice == "1":
                self.add_feature_flow()
            elif choice == "2":
                self.fix_issue_flow()
            elif choice == "3":
                self.evaluate_flow()
            elif choice == "4":
                self.improve_flow()
            elif choice == "5":
                self.deploy_flow()
            elif choice == "6":
                self.view_details_flow()
            elif choice == "7":
                self.usage_report_flow()
            elif choice in ["b", "back", "q"]:
                self._save_project()
                return
    
    # ════════════════════════════════════════════════════════════
    # PROJECT ACTIONS
    # ════════════════════════════════════════════════════════════
    
    def add_feature_flow(self):
        """Add a new feature"""
        self.clear_screen()
        self.print_subheader("ADD FEATURE")
        
        description = self.get_input("Describe the feature:\n> ")
        if not description:
            return
        
        print(f"\n🚀 Starting feature development...")
        print(f"   Feature: {description}")
        print()
        print("Workflow:")
        print("  1. Ideation → refine the concept")
        print("  2. Requirements → user stories, acceptance criteria")
        print("  3. Architecture → technical design")
        print("  4. Development → write code")
        print("  5. Review → code review, testing")
        print("  6. Integration → merge and deploy")
        print()
        print("(In full implementation, this runs the agent workflow)")
        
        # Record in history
        self.current_config.setdefault("history", []).append({
            "action": "add_feature",
            "description": description,
            "date": datetime.now().isoformat(),
            "status": "started"
        })
        
        self.get_input("\nPress Enter to continue...")
    
    def fix_issue_flow(self):
        """Fix an issue"""
        self.clear_screen()
        self.print_subheader("FIX ISSUE")
        
        description = self.get_input("Describe the issue:\n> ")
        if not description:
            return
        
        print(f"\n🔧 Analyzing issue...")
        print(f"   Issue: {description}")
        print()
        print("(In full implementation, this runs diagnostic agents)")
        
        self.get_input("\nPress Enter to continue...")
    
    def evaluate_flow(self):
        """Evaluate project health"""
        self.clear_screen()
        self.print_subheader("HEALTH EVALUATION")
        
        print("Running health evaluation...")
        
        try:
            report = self.evaluator.evaluate(self.current_project)
            
            self.clear_screen()
            self.print_header(f"HEALTH REPORT: {self.current_project}")
            
            # Overall score
            score = report.overall_score
            status = report.overall_status
            
            status_icons = {
                "excellent": "✅",
                "good": "🟢",
                "warning": "⚠️",
                "critical": "❌"
            }
            
            print(f"Overall Score: {score}/100  {status_icons.get(status, '')} {status.title()}")
            print()
            
            # Category breakdown
            print("┌─────────────────────────┬───────┬──────────────────────┐")
            print("│ Category                │ Score │ Status               │")
            print("├─────────────────────────┼───────┼──────────────────────┤")
            
            for cat in report.categories:
                name = cat.get("name", "")[:23].ljust(23)
                cat_score = str(cat.get("score", 0)).center(5)
                cat_status = cat.get("status", "unknown")
                icon = status_icons.get(cat_status, "")
                status_str = f"{icon} {cat_status}"[:20].ljust(20)
                print(f"│ {name} │ {cat_score} │ {status_str} │")
            
            print("└─────────────────────────┴───────┴──────────────────────┘")
            
            # Critical issues
            if report.critical_issues:
                print(f"\n❌ CRITICAL ISSUES ({len(report.critical_issues)}):")
                for issue in report.critical_issues[:3]:
                    print(f"   • {issue.get('title', '')}")
            
            # High issues
            if report.high_issues:
                print(f"\n⚠️  HIGH PRIORITY ({len(report.high_issues)}):")
                for issue in report.high_issues[:3]:
                    print(f"   • {issue.get('title', '')}")
            
            # Quick wins
            if report.quick_wins:
                print(f"\n💡 QUICK WINS:")
                for win in report.quick_wins[:3]:
                    print(f"   • {win.get('title', '')} ({win.get('effort', '')})")
            
            print()
            create_plan = self.get_input("Create improvement plan? [Y/n]: ").lower()
            if create_plan != "n":
                self._create_improvement_plan(report)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _create_improvement_plan(self, health_report):
        """Create improvement plan from health report"""
        print("\nImprovement type:")
        print("  [1] All issues")
        print("  [2] Critical only")
        print("  [3] Security")
        print("  [4] Tests")
        print("  [5] Code quality")
        
        choice = self.get_input("\nChoice [1]: ") or "1"
        
        type_map = {
            "1": "all",
            "2": "critical",
            "3": "security",
            "4": "tests",
            "5": "code_quality"
        }
        
        improvement_type = type_map.get(choice, "all")
        
        # Convert report to dict if needed
        report_dict = health_report if isinstance(health_report, dict) else {
            "overall_score": health_report.overall_score,
            "critical_issues": health_report.critical_issues,
            "high_issues": health_report.high_issues,
            "categories": health_report.categories,
        }
        
        plan = self.planner.create_plan(
            self.current_project,
            report_dict,
            improvement_type
        )
        
        print(f"\n✅ Improvement plan created!")
        print(f"   Tasks: {plan.total_tasks}")
        print(f"   Effort: {plan.total_effort}")
        print(f"   Target score: {plan.target_score}")
    
    def improve_flow(self):
        """Run improvements"""
        self.clear_screen()
        self.print_subheader("IMPROVE PROJECT")
        
        # Check for existing plan
        plan = self.planner.load_plan(self.current_project)
        
        if plan:
            progress = self.planner.get_progress(self.current_project)
            print(f"Existing improvement plan found:")
            print(f"  Total tasks: {progress['total_tasks']}")
            print(f"  Completed: {progress['completed']}")
            print(f"  Progress: {progress['percent_complete']:.0f}%")
            print()
        
        print("What would you like to improve?")
        self.print_menu([
            ("1", "Run next task       (from plan)"),
            ("2", "Fix critical issues (immediate)"),
            ("3", "Security fixes"),
            ("4", "Add tests"),
            ("5", "Update dependencies"),
            ("6", "Refactor code"),
            ("b", "Back"),
        ])
        
        choice = self.get_input().lower()
        
        if choice == "1":
            next_task = self.planner.get_next_task(self.current_project)
            if next_task:
                print(f"\nNext task: {next_task.get('title')}")
                print(f"Agent: {next_task.get('agent')}")
                print(f"Effort: {next_task.get('effort')}")
                print("\n(In full implementation, this runs the appropriate agent)")
            else:
                print("\n✅ All tasks completed!")
        elif choice == "b":
            return
        else:
            improvement_types = {
                "2": "critical",
                "3": "security", 
                "4": "tests",
                "5": "dependencies",
                "6": "code_quality"
            }
            imp_type = improvement_types.get(choice, "all")
            print(f"\nRunning {imp_type} improvements...")
            print("(In full implementation, this runs the improvement workflow)")
        
        self.get_input("\nPress Enter to continue...")
    
    def deploy_flow(self):
        """Deploy project"""
        self.clear_screen()
        self.print_subheader("DEPLOY")
        
        print("Deployment target:")
        self.print_menu([
            ("1", "Staging"),
            ("2", "Production"),
            ("b", "Back"),
        ])
        
        choice = self.get_input().lower()
        
        if choice == "b":
            return
        
        target = "staging" if choice == "1" else "production"
        
        print(f"\n🚀 Deploying to {target}...")
        print("(In full implementation, this runs the DevOps agent)")
        
        self.get_input("\nPress Enter to continue...")
    
    def view_details_flow(self):
        """View project details"""
        self.clear_screen()
        self.print_subheader("PROJECT DETAILS")
        
        project = self.current_config.get("project", {})
        
        print("Configuration:")
        print(f"  ID: {project.get('id')}")
        print(f"  Name: {project.get('name')}")
        print(f"  Type: {project.get('type')}")
        print(f"  Created: {project.get('created')}")
        
        if project.get("source_path"):
            print(f"  Source: {project.get('source_path')}")
        
        # Show tech stack
        stack = self.current_config.get("tech_stack", {})
        if stack:
            print("\nTech Stack:")
            for key, value in stack.items():
                if value and key != "custom":
                    if isinstance(value, list):
                        print(f"  {key}: {', '.join(value)}")
                    else:
                        print(f"  {key}: {value}")
        
        # Show files
        project_dir = self.projects_dir / self.current_project
        if project_dir.exists():
            print(f"\nProject directory: {project_dir}")
            
            file_index = project_dir / "file_index.json"
            if file_index.exists():
                with open(file_index, encoding="utf-8") as f:
                    files = json.load(f)
                print(f"Indexed files: {len(files)}")
        
        # Show history
        history = self.current_config.get("history", [])
        if history:
            print(f"\nRecent activity:")
            for h in history[-5:]:
                print(f"  • {h.get('action')}: {h.get('description', '')[:40]}")
        
        self.get_input("\nPress Enter to continue...")
    
    def usage_report_flow(self):
        """View project usage and costs"""
        try:
            from core.usage_tracker import get_tracker
        except ImportError:
            print("\n❌ Usage tracker not available")
            self.get_input("Press Enter...")
            return
        
        tracker = get_tracker(str(self.projects_dir))
        
        while True:
            self.clear_screen()
            self.print_subheader(f"USAGE: {self.current_project}")
            
            summary = tracker.get_project_summary(self.current_project)
            
            if not summary or summary.call_count == 0:
                print("No usage data yet.")
                print("\nUsage is tracked when agents run.")
                self.get_input("\nPress Enter to continue...")
                return
            
            # Show summary
            print(f"{'─' * 50}")
            print(f"  Total Cost:        ${summary.total_cost:.4f}")
            print(f"  Total API Calls:   {summary.call_count:,}")
            print(f"  Input Tokens:      {summary.total_input_tokens:,}")
            print(f"  Output Tokens:     {summary.total_output_tokens:,}")
            if summary.total_cache_read_tokens:
                print(f"  Cache Read:        {summary.total_cache_read_tokens:,}")
            print(f"{'─' * 50}")
            
            if summary.first_call:
                print(f"\n  First: {summary.first_call[:19]}")
            if summary.last_call:
                print(f"  Last:  {summary.last_call[:19]}")
            
            print()
            self.print_menu([
                ("1", "By agent          (cost per agent)"),
                ("2", "By feature        (cost per feature)"),
                ("3", "By date           (daily breakdown)"),
                ("4", "Recent calls      (detailed log)"),
                ("5", "All projects      (global overview)"),
                ("b", "Back"),
            ])
            
            choice = self.get_input().lower()
            
            if choice == "1":
                self._usage_by_agent(summary)
            elif choice == "2":
                self._usage_by_feature(summary)
            elif choice == "3":
                self._usage_by_date(summary)
            elif choice == "4":
                self._usage_recent_calls(tracker)
            elif choice == "5":
                self._usage_all_projects(tracker)
            elif choice in ["b", "back", "q"]:
                return
    
    def _usage_by_agent(self, summary):
        """Show usage breakdown by agent"""
        self.clear_screen()
        self.print_subheader("USAGE BY AGENT")
        
        if not summary.by_agent:
            print("No agent data yet.")
        else:
            print(f"{'Agent':<22} {'Calls':>8} {'Input':>12} {'Output':>12} {'Cost':>12}")
            print(f"{'-'*22} {'-'*8} {'-'*12} {'-'*12} {'-'*12}")
            
            for agent, data in sorted(summary.by_agent.items(), key=lambda x: x[1]["cost"], reverse=True):
                print(f"{agent:<22} {data['calls']:>8,} {data['input_tokens']:>12,} {data['output_tokens']:>12,} ${data['cost']:>10.4f}")
            
            print(f"{'-'*22} {'-'*8} {'-'*12} {'-'*12} {'-'*12}")
            print(f"{'TOTAL':<22} {summary.call_count:>8,} {summary.total_input_tokens:>12,} {summary.total_output_tokens:>12,} ${summary.total_cost:>10.4f}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _usage_by_feature(self, summary):
        """Show usage breakdown by feature"""
        self.clear_screen()
        self.print_subheader("USAGE BY FEATURE")
        
        if not summary.by_feature:
            print("No feature-level data yet.")
            print("\nFeatures are tracked when using 'Add feature' workflow.")
        else:
            print(f"{'Feature':<30} {'Calls':>8} {'Cost':>12}")
            print(f"{'-'*30} {'-'*8} {'-'*12}")
            
            for feature, data in sorted(summary.by_feature.items(), key=lambda x: x[1]["cost"], reverse=True):
                print(f"{feature[:30]:<30} {data['calls']:>8,} ${data['cost']:>10.4f}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _usage_by_date(self, summary):
        """Show usage breakdown by date"""
        self.clear_screen()
        self.print_subheader("USAGE BY DATE")
        
        if not summary.by_date:
            print("No date data yet.")
        else:
            print(f"{'Date':<12} {'Calls':>8} {'Tokens':>15} {'Cost':>12}")
            print(f"{'-'*12} {'-'*8} {'-'*15} {'-'*12}")
            
            for date in sorted(summary.by_date.keys(), reverse=True)[:14]:  # Last 2 weeks
                data = summary.by_date[date]
                total_tokens = data['input_tokens'] + data['output_tokens']
                print(f"{date:<12} {data['calls']:>8,} {total_tokens:>15,} ${data['cost']:>10.4f}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _usage_recent_calls(self, tracker):
        """Show recent API calls"""
        self.clear_screen()
        self.print_subheader("RECENT API CALLS")
        
        entries = tracker.get_project_log(self.current_project, limit=20)
        
        if not entries:
            print("No calls logged yet.")
        else:
            for entry in entries:
                timestamp = entry.timestamp[11:19]  # Just time
                tokens = entry.input_tokens + entry.output_tokens
                print(f"  {timestamp} | {entry.agent:<18} | {tokens:>7} tok | ${entry.cost:.4f}")
                if entry.context:
                    print(f"           └─ {entry.context[:50]}")
        
        self.get_input("\nPress Enter to continue...")
    
    def _usage_all_projects(self, tracker):
        """Show usage for all projects"""
        self.clear_screen()
        self.print_subheader("ALL PROJECTS USAGE")
        
        summaries = tracker.get_all_projects_summary()
        
        if not summaries:
            print("No usage data found.")
        else:
            print(f"{'Project':<25} {'Calls':>10} {'Cost':>15}")
            print(f"{'-'*25} {'-'*10} {'-'*15}")
            
            total_cost = 0.0
            total_calls = 0
            
            for project_id, summary in sorted(summaries.items(), key=lambda x: x[1].total_cost, reverse=True):
                print(f"{project_id[:25]:<25} {summary.call_count:>10,} ${summary.total_cost:>13.4f}")
                total_cost += summary.total_cost
                total_calls += summary.call_count
            
            print(f"{'-'*25} {'-'*10} {'-'*15}")
            print(f"{'TOTAL':<25} {total_calls:>10,} ${total_cost:>13.4f}")
        
        self.get_input("\nPress Enter to continue...")
    
    # ════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════
    
    def _list_projects(self) -> list:
        """List all projects"""
        projects = []
        
        if not self.projects_dir.exists():
            return projects
        
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                config_file = project_dir / "project.yaml"
                if config_file.exists():
                    try:
                        with open(config_file, encoding="utf-8") as f:
                            config = yaml.safe_load(f)
                        project = config.get("project", {})
                        projects.append({
                            "id": project.get("id", project_dir.name),
                            "name": project.get("name", project_dir.name),
                            "type": project.get("type", "new"),
                            "status": project.get("status", "active"),
                            "stage": project.get("stage", "unknown"),
                        })
                    except:
                        pass
        
        return projects
    
    def _load_project(self, project_id: str):
        """Load project configuration"""
        config_file = self.projects_dir / project_id / "project.yaml"
        
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                self.current_config = yaml.safe_load(f)
        else:
            self.current_config = {"project": {"id": project_id, "name": project_id}}
    
    def _save_project(self):
        """Save current project"""
        if self.current_project and self.current_config:
            config_file = self.projects_dir / self.current_project / "project.yaml"
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(self.current_config, f, default_flow_style=False, sort_keys=False)


# ════════════════════════════════════════════════════════════
# DIRECT CLI COMMANDS
# ════════════════════════════════════════════════════════════

def print_usage():
    """Print usage information"""
    print("""
AI-Dev-Workflow CLI

Usage:
  python cli.py                     Interactive mode (main menu)
  python cli.py new "Name"          Create new project
  python cli.py list                List all projects
  python cli.py open <project>      Open project menu
  python cli.py ingest <path>       Import external codebase
  python cli.py evaluate <project>  Run health evaluation
  python cli.py improve <project>   Run improvements
  python cli.py agent <type> "task" Run single agent

Monitoring:
  python cli.py monitor <project>          Console monitor (tail -f style)
  python cli.py monitor <project> --web    Web dashboard at localhost:8765

Interactive Development (with checkpoints):
  python cli.py start               Start new session (select autonomy level)
  python cli.py resume <project>    Resume paused session
  python cli.py checkpoints         Show checkpoint info for all levels

Autonomy Levels:
  pair        - Maximum checkpoints (12), review everything
  balanced    - Moderate checkpoints (8), key decision points  
  autonomous  - Minimal checkpoints (4), critical gates only

Examples:
  python cli.py new "Customer Portal"
  python cli.py start                    # Interactive with autonomy selection
  python cli.py resume my-project        # Continue paused session
  python cli.py ingest C:\\code\\legacy-app
  python cli.py evaluate customer-portal
  python cli.py agent developer "Add login endpoint"
""")


def run_monitor(cli, args):
    """Run the live monitor"""
    try:
        from core.monitor import ConsoleMonitor, WebMonitor
    except ImportError as e:
        print(f"Error: Monitor module not available: {e}")
        return

    # Parse arguments
    project_id = None
    web_mode = False
    port = 8765

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--web":
            web_mode = True
        elif arg == "--port" and i + 1 < len(args):
            i += 1
            port = int(args[i])
        elif not arg.startswith("-"):
            project_id = arg
        i += 1

    # If no project specified, try to find most recent
    if not project_id:
        projects = cli._list_projects()
        if projects:
            project_id = projects[0]["id"]
            print(f"Using most recent project: {project_id}")
        else:
            print("No project specified and no projects found.")
            print("Usage: python cli.py monitor <project> [--web] [--port 8765]")
            return

    project_dir = cli.projects_dir / project_id
    if not project_dir.exists():
        print(f"Project not found: {project_id}")
        return

    # Get latest session for this project
    from core.audit import get_latest_session
    session_id = get_latest_session(project_dir)

    if web_mode:
        monitor = WebMonitor(project_dir, port=port, session_id=session_id)
        monitor.start()
    else:
        monitor = ConsoleMonitor(project_dir, session_id=session_id)
        monitor.follow()


def main():
    """Main entry point"""
    # Verbose is default, --quiet or -q to disable
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    if quiet:
        sys.argv = [a for a in sys.argv if a not in ("--quiet", "-q")]

    verbose = not quiet
    cli = InteractiveCLI(verbose=verbose)

    if verbose:
        print("🔊 Verbose mode (use --quiet for less output)\n")

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command in ["-h", "--help", "help"]:
            print_usage()
            return

        elif command == "new" and len(sys.argv) > 2:
            name = " ".join(sys.argv[2:])
            print(f"Creating project: {name}")
            # Quick create
            cli.new_project_flow()
            return
        
        elif command == "list":
            projects = cli._list_projects()
            if projects:
                print("\nProjects:")
                for p in projects:
                    print(f"  {p['id']}: {p['name']} ({p['type']})")
            else:
                print("No projects found.")
            return
        
        elif command == "open" and len(sys.argv) > 2:
            project_id = sys.argv[2]
            cli.current_project = project_id
            cli._load_project(project_id)
            cli.project_menu()
            return
        
        elif command == "ingest" and len(sys.argv) > 2:
            source_path = sys.argv[2]
            result = cli.ingestor.ingest(source_path)
            print(f"✅ Ingested: {result.project_name}")
            print(f"   Files: {result.source_file_count}")
            print(f"   Lines: {result.total_lines:,}")
            return
        
        elif command == "evaluate" and len(sys.argv) > 2:
            project_id = sys.argv[2]
            report = cli.evaluator.evaluate(project_id)
            print(f"\nHealth Report: {project_id}")
            print(f"Score: {report.overall_score}/100 ({report.overall_status})")
            return
        
        elif command == "start":
            # Start new interactive session with autonomy selection
            run_interactive_start(cli)
            return
        
        elif command == "resume" and len(sys.argv) > 2:
            # Resume paused session
            project_name = sys.argv[2]
            run_interactive_resume(cli, project_name)
            return
        
        elif command == "checkpoints":
            # Show checkpoint information
            show_checkpoint_info()
            return

        elif command == "monitor":
            # Live monitoring
            run_monitor(cli, sys.argv[2:])
            return

        else:
            print(f"Unknown command: {command}")
            print_usage()
            return
    
    # Default: interactive mode - start with autonomy selection
    cli.autonomy_menu()


def run_interactive_start(cli):
    """Start a new interactive development session"""
    try:
        from rich.console import Console
        from rich.prompt import Prompt, Confirm
        from rich.panel import Panel
        from core.checkpoints import AutonomyLevel, get_checkpoint_summary
        from core.interactive_session import InteractiveSession, select_autonomy_level
    except ImportError as e:
        print(f"Error: Required modules not installed. Run: pip install rich")
        print(f"Details: {e}")
        return
    
    console = Console()
    
    console.print(Panel(
        "[bold cyan]AI-Dev-Workflow[/bold cyan]\n"
        "[dim]Interactive Development Session[/dim]",
        title="🚀 New Session",
        border_style="cyan"
    ))
    
    # Get project name
    project_name = Prompt.ask("\nProject name")
    if not project_name:
        console.print("[red]Project name required[/red]")
        return
    
    # Select autonomy level
    autonomy = select_autonomy_level()
    
    # Get project directory
    project_dir = cli.projects_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Start session
    session = InteractiveSession(
        project_dir=project_dir,
        project_name=project_name,
        autonomy_level=autonomy
    )
    
    session.start()


def run_interactive_resume(cli, project_name: str):
    """Resume a paused interactive session"""
    try:
        from rich.console import Console
        from core.checkpoints import AutonomyLevel
        from core.interactive_session import InteractiveSession
    except ImportError as e:
        print(f"Error: Required modules not installed. Run: pip install rich")
        print(f"Details: {e}")
        return
    
    console = Console()
    
    project_dir = cli.projects_dir / project_name
    state_file = project_dir / ".workflow" / "checkpoint_state.json"
    
    if not state_file.exists():
        console.print(f"[red]No saved session found for '{project_name}'[/red]")
        console.print(f"[dim]Looking for: {state_file}[/dim]")
        return
    
    # Load autonomy level from state
    import json
    state_data = json.loads(state_file.read_text())
    autonomy = AutonomyLevel(state_data.get("autonomy_level", "balanced"))
    
    session = InteractiveSession(
        project_dir=project_dir,
        project_name=project_name,
        autonomy_level=autonomy
    )
    
    session.resume()


def show_checkpoint_info():
    """Display checkpoint information for all autonomy levels"""
    try:
        from rich.console import Console
        from rich.table import Table
        from core.checkpoints import (
            AutonomyLevel, 
            ALL_CHECKPOINTS, 
            get_autonomy_description,
            get_checkpoint_summary
        )
    except ImportError as e:
        print(f"Error: Required modules not installed.")
        print(f"Details: {e}")
        return
    
    console = Console()
    
    console.print("\n[bold cyan]AI-Dev-Workflow Checkpoint System[/bold cyan]\n")
    
    # Summary table
    summary_table = Table(title="Autonomy Levels Overview", show_header=True)
    summary_table.add_column("Level", style="cyan", width=20)
    summary_table.add_column("Checkpoints", justify="center", width=12)
    summary_table.add_column("Description", width=50)
    
    for level in AutonomyLevel:
        count = sum(1 for d in ALL_CHECKPOINTS if level in d.required_for)
        summary_table.add_row(
            level.value,
            str(count),
            get_autonomy_description(level)[:50] + "..."
        )
    
    console.print(summary_table)
    
    # Detailed checkpoint list
    console.print("\n[bold]Checkpoints by Phase:[/bold]\n")
    
    phases = ["design", "development", "delivery"]
    level_symbols = {
        AutonomyLevel.PAIR_PROGRAMMING: "P",
        AutonomyLevel.BALANCED: "B", 
        AutonomyLevel.FULLY_AUTONOMOUS: "A"
    }
    
    for phase in phases:
        console.print(f"[bold yellow]{phase.upper()}[/bold yellow]")
        phase_checkpoints = [c for c in ALL_CHECKPOINTS if c.phase == phase]
        
        for cp in phase_checkpoints:
            levels = "".join([
                f"[green]{level_symbols[l]}[/green]" if l in cp.required_for else "[dim]-[/dim]"
                for l in AutonomyLevel
            ])
            console.print(f"  [{levels}] {cp.name}")
        
        console.print()
    
    console.print("[dim]Legend: P=Pair Programming, B=Balanced, A=Autonomous[/dim]")


if __name__ == "__main__":
    main()
