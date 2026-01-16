"""
Interactive Session Handler for AI-Dev-Workflow

Provides menu-driven interaction for checkpoint reviews and feedback.
"""

import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.layout import Layout
from rich.live import Live

from core.checkpoints import (
    CheckpointManager,
    CheckpointState,
    CheckpointStatus,
    CheckpointType,
    AutonomyLevel,
    Milestone,
    get_autonomy_description,
    get_checkpoint_summary
)


console = Console()


class SessionAction(Enum):
    """Actions available during interactive session"""
    APPROVE = "approve"
    FEEDBACK = "feedback"
    REVISE = "revise"
    VIEW = "view"
    SAVE_PAUSE = "save"
    ABORT = "abort"
    SKIP = "skip"
    OVERRIDE = "override"


@dataclass
class SessionContext:
    """Context for current interactive session"""
    project_dir: Path
    project_name: str
    checkpoint_manager: CheckpointManager
    current_phase: str
    started_at: str
    artifacts_dir: Path


class InteractiveSession:
    """Manages interactive workflow sessions"""
    
    def __init__(
        self,
        project_dir: Path,
        project_name: str,
        autonomy_level: AutonomyLevel = AutonomyLevel.BALANCED
    ):
        self.project_dir = Path(project_dir)
        self.project_name = project_name
        self.autonomy_level = autonomy_level
        
        self.checkpoint_manager = CheckpointManager(
            project_dir=self.project_dir,
            autonomy_level=autonomy_level
        )
        
        self.context = SessionContext(
            project_dir=self.project_dir,
            project_name=project_name,
            checkpoint_manager=self.checkpoint_manager,
            current_phase="initialization",
            started_at=datetime.now().isoformat(),
            artifacts_dir=self.project_dir / "artifacts"
        )
        
        self.artifacts_dir = self.project_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # SESSION LIFECYCLE
    # =========================================================================
    
    def start(self):
        """Start a new interactive session"""
        self._print_header()
        self._print_autonomy_info()
        
        if not Confirm.ask("\nReady to begin?", default=True):
            console.print("[yellow]Session cancelled.[/yellow]")
            return
        
        self._run_session_loop()
    
    def resume(self):
        """Resume a paused session"""
        progress = self.checkpoint_manager.get_progress_summary()
        
        console.print(Panel(
            f"[bold]Resuming: {self.project_name}[/bold]\n\n"
            f"Progress: {progress['completed']}/{progress['total']} checkpoints complete\n"
            f"Current: {progress['current'] or 'None'}\n"
            f"Autonomy: {progress['autonomy_level']}",
            title="Resume Session"
        ))
        
        if Confirm.ask("\nContinue from where you left off?", default=True):
            self._run_session_loop()
    
    def _run_session_loop(self):
        """Main session loop"""
        while True:
            next_checkpoint = self.checkpoint_manager.get_next_checkpoint()
            
            if not next_checkpoint:
                self._print_completion()
                break
            
            # Check for auto-approve
            if self.checkpoint_manager.should_auto_approve(next_checkpoint.definition.checkpoint_type):
                self._auto_approve_checkpoint(next_checkpoint)
                continue
            
            # Run checkpoint interactively
            result = self._run_checkpoint(next_checkpoint)
            
            if result == SessionAction.ABORT:
                if Confirm.ask("\n[red]Abort session?[/red]", default=False):
                    console.print("[red]Session aborted.[/red]")
                    break
            elif result == SessionAction.SAVE_PAUSE:
                self.checkpoint_manager.save_state()
                console.print("\n[green]Session saved. Run 'resume' to continue.[/green]")
                break
    
    # =========================================================================
    # CHECKPOINT HANDLING
    # =========================================================================
    
    def _run_checkpoint(self, checkpoint: CheckpointState) -> SessionAction:
        """Run a single checkpoint interactively"""
        defn = checkpoint.definition
        
        # Mark as in progress
        self.checkpoint_manager.start_checkpoint(defn.checkpoint_type)
        
        # Display checkpoint header
        self._print_checkpoint_header(checkpoint)
        
        # Generate/display artifacts
        self._display_artifacts(checkpoint)
        
        # Show review prompts
        self._print_review_prompts(defn.review_prompts)
        
        # Get human decision
        return self._get_checkpoint_decision(checkpoint)
    
    def _auto_approve_checkpoint(self, checkpoint: CheckpointState):
        """Auto-approve a checkpoint based on confidence"""
        defn = checkpoint.definition
        
        console.print(f"\n[dim]Auto-approving: {defn.name} "
                     f"(confidence: {checkpoint.agent_confidence:.0%})[/dim]")
        
        self.checkpoint_manager.record_feedback(
            defn.checkpoint_type,
            decision="approve",
            comments="Auto-approved based on confidence threshold"
        )
    
    def _get_checkpoint_decision(self, checkpoint: CheckpointState) -> SessionAction:
        """Get human decision for checkpoint"""
        defn = checkpoint.definition
        
        # Build action menu
        self._print_action_menu(checkpoint)
        
        while True:
            choice = Prompt.ask(
                "\nYour choice",
                choices=["a", "f", "r", "v", "s", "x", "o", "?"],
                default="a"
            )
            
            if choice == "a":  # Approve
                comments = Prompt.ask("Comments (optional)", default="")
                self.checkpoint_manager.record_feedback(
                    defn.checkpoint_type,
                    decision="approve",
                    comments=comments
                )
                console.print("[green]✓ Checkpoint approved[/green]")
                return SessionAction.APPROVE
            
            elif choice == "f":  # Feedback
                feedback = Prompt.ask("Enter your feedback")
                console.print(f"[blue]Feedback recorded:[/blue] {feedback}")
                # Continue loop - feedback doesn't end checkpoint
            
            elif choice == "r":  # Revise
                instructions = Prompt.ask("Revision instructions")
                self.checkpoint_manager.record_feedback(
                    defn.checkpoint_type,
                    decision="revise",
                    revision_instructions=instructions
                )
                console.print("[yellow]→ Sending for revision...[/yellow]")
                return SessionAction.REVISE
            
            elif choice == "v":  # View artifacts
                self._open_artifacts(checkpoint)
            
            elif choice == "s":  # Save & pause
                return SessionAction.SAVE_PAUSE
            
            elif choice == "x":  # Abort
                return SessionAction.ABORT
            
            elif choice == "o":  # Override (proceed despite low confidence)
                if checkpoint.agent_confidence < defn.auto_approve_threshold:
                    if Confirm.ask(
                        f"[yellow]Confidence is {checkpoint.agent_confidence:.0%} "
                        f"(threshold: {defn.auto_approve_threshold:.0%}). "
                        f"Override and approve?[/yellow]"
                    ):
                        self.checkpoint_manager.record_feedback(
                            defn.checkpoint_type,
                            decision="approve",
                            comments="Human override - approved despite low confidence",
                            confidence_override=True
                        )
                        return SessionAction.APPROVE
            
            elif choice == "?":  # Help
                self._print_help()
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def _print_header(self):
        """Print session header"""
        console.print()
        console.print(Panel(
            f"[bold cyan]AI-Dev-Workflow[/bold cyan]\n"
            f"[dim]Interactive Development Session[/dim]\n\n"
            f"Project: [bold]{self.project_name}[/bold]\n"
            f"Location: {self.project_dir}",
            title="🤖 Session Start",
            border_style="cyan"
        ))
    
    def _print_autonomy_info(self):
        """Print autonomy level information"""
        counts = self.checkpoint_manager.get_checkpoint_count_by_level()
        
        table = Table(title="Autonomy Levels", show_header=True)
        table.add_column("Level", style="cyan")
        table.add_column("Checkpoints", justify="center")
        table.add_column("Description")
        
        for level in AutonomyLevel:
            marker = "→ " if level == self.autonomy_level else "  "
            style = "bold green" if level == self.autonomy_level else ""
            table.add_row(
                f"{marker}{level.value}",
                str(counts[level.value]),
                get_autonomy_description(level)[:60] + "...",
                style=style
            )
        
        console.print(table)
        console.print(f"\n[bold]Selected:[/bold] {self.autonomy_level.value.upper()}")
    
    def _print_checkpoint_header(self, checkpoint: CheckpointState):
        """Print checkpoint header"""
        defn = checkpoint.definition
        progress = self.checkpoint_manager.get_progress_summary()
        
        console.print()
        console.print("═" * 70)
        console.print(f"  [bold cyan]CHECKPOINT: {defn.name}[/bold cyan]")
        console.print(f"  [dim]Phase: {defn.phase} | "
                     f"Progress: {progress['completed']}/{progress['total']}[/dim]")
        console.print("═" * 70)
        console.print()
        console.print(f"[italic]{defn.description}[/italic]")
        console.print()
        
        # Show confidence if available
        if checkpoint.agent_confidence > 0:
            confidence_color = (
                "green" if checkpoint.agent_confidence >= defn.auto_approve_threshold
                else "yellow" if checkpoint.agent_confidence >= 0.7
                else "red"
            )
            console.print(
                f"Agent Confidence: [{confidence_color}]"
                f"{checkpoint.agent_confidence:.0%}[/{confidence_color}] "
                f"(threshold: {defn.auto_approve_threshold:.0%})"
            )
        
        # Show attempt count if retrying
        if checkpoint.attempts > 1:
            console.print(f"[yellow]Attempt: {checkpoint.attempts}[/yellow]")
    
    def _display_artifacts(self, checkpoint: CheckpointState):
        """Display generated artifacts"""
        defn = checkpoint.definition
        artifacts = checkpoint.artifacts_generated or defn.artifacts
        
        console.print("\n[bold]Generated Artifacts:[/bold]")
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="dim")
        table.add_column("")
        
        for i, artifact in enumerate(artifacts, 1):
            # Check if artifact exists
            artifact_path = self.artifacts_dir / artifact
            exists = artifact_path.exists() or "*" in artifact
            status = "✓" if exists else "○"
            style = "" if exists else "dim"
            table.add_row(f"[{i}]", f"{status} {artifact}", style=style)
        
        console.print(table)
    
    def _print_review_prompts(self, prompts: List[str]):
        """Print review prompts"""
        console.print("\n[bold]Review Questions:[/bold]")
        for prompt in prompts:
            console.print(f"  • {prompt}")
    
    def _print_action_menu(self, checkpoint: CheckpointState):
        """Print available actions"""
        console.print("\n" + "─" * 70)
        console.print("[bold]Actions:[/bold]")
        console.print()
        console.print("  [green][A][/green] Approve    - Accept and proceed")
        console.print("  [blue][F][/blue] Feedback   - Add notes without deciding")
        console.print("  [yellow][R][/yellow] Revise     - Request changes")
        console.print("  [cyan][V][/cyan] View       - Open artifacts in browser")
        console.print("  [magenta][S][/magenta] Save       - Save progress and pause")
        console.print("  [red][X][/red] Abort      - Cancel workflow")
        
        if checkpoint.agent_confidence < checkpoint.definition.auto_approve_threshold:
            console.print("  [yellow][O][/yellow] Override   - Approve despite low confidence")
        
        console.print("  [dim][?][/dim] Help       - Show detailed help")
        console.print("─" * 70)
    
    def _print_help(self):
        """Print detailed help"""
        help_text = """
## Checkpoint Actions

**Approve (A)**: Accept the current output and move to the next checkpoint.
The workflow will continue to the next stage.

**Feedback (F)**: Add comments or notes without making a decision.
Use this to record thoughts while still reviewing.

**Revise (R)**: Request changes to the current output.
You'll provide instructions, and the agent will regenerate.

**View (V)**: Open generated artifacts in your default browser.
Useful for reviewing designs, wireframes, and code.

**Save (S)**: Save current progress and pause the session.
You can resume later with `python cli.py resume <project>`.

**Abort (X)**: Cancel the entire workflow.
Progress will be saved but marked as incomplete.

**Override (O)**: Approve despite low agent confidence.
Use when you've reviewed and are satisfied even if the AI is uncertain.

## Confidence Scores

The agent provides a confidence score (0-100%) for each checkpoint.
- **Green (≥85%)**: High confidence, auto-approve in autonomous mode
- **Yellow (70-84%)**: Medium confidence, review recommended  
- **Red (<70%)**: Low confidence, careful review needed

## Tips

- Use feedback to build context before deciding
- View artifacts before approving visual checkpoints
- Save frequently on long sessions
- Override only after thorough review
        """
        console.print(Markdown(help_text))
    
    def _print_completion(self):
        """Print session completion"""
        progress = self.checkpoint_manager.get_progress_summary()
        
        console.print()
        console.print(Panel(
            f"[bold green]Session Complete![/bold green]\n\n"
            f"Checkpoints: {progress['completed']}/{progress['total']}\n"
            f"Project: {self.project_name}",
            title="✅ Complete",
            border_style="green"
        ))
    
    # =========================================================================
    # ARTIFACT HANDLING
    # =========================================================================
    
    def _open_artifacts(self, checkpoint: CheckpointState):
        """Open artifacts in browser"""
        defn = checkpoint.definition
        artifacts = checkpoint.artifacts_generated or defn.artifacts
        
        console.print("\n[bold]Opening artifacts...[/bold]")
        
        opened = 0
        for artifact in artifacts:
            if "*" in artifact:
                # Glob pattern
                pattern_path = self.artifacts_dir / artifact
                for match in pattern_path.parent.glob(pattern_path.name):
                    if match.suffix in [".html", ".htm", ".pdf"]:
                        self._open_in_browser(match)
                        opened += 1
            else:
                artifact_path = self.artifacts_dir / artifact
                if artifact_path.exists():
                    if artifact_path.suffix in [".html", ".htm", ".pdf"]:
                        self._open_in_browser(artifact_path)
                        opened += 1
                    elif artifact_path.suffix == ".md":
                        self._display_markdown(artifact_path)
                        opened += 1
                    else:
                        console.print(f"  [dim]Skipping non-viewable: {artifact}[/dim]")
        
        if opened == 0:
            console.print("  [yellow]No viewable artifacts found.[/yellow]")
        else:
            console.print(f"  [green]Opened {opened} artifact(s)[/green]")
    
    def _open_in_browser(self, path: Path):
        """Open file in default browser"""
        try:
            url = path.as_uri()
            webbrowser.open(url)
            console.print(f"  [green]Opened:[/green] {path.name}")
        except Exception as e:
            console.print(f"  [red]Error opening {path.name}: {e}[/red]")
    
    def _display_markdown(self, path: Path):
        """Display markdown file in console"""
        try:
            content = path.read_text()
            console.print(Panel(
                Markdown(content),
                title=path.name,
                border_style="blue"
            ))
        except Exception as e:
            console.print(f"  [red]Error reading {path.name}: {e}[/red]")


# =============================================================================
# MILESTONE REVIEW SESSION
# =============================================================================

class MilestoneReviewSession:
    """Interactive session for reviewing development milestones"""
    
    def __init__(self, project_dir: Path, milestones: List[Milestone]):
        self.project_dir = Path(project_dir)
        self.milestones = milestones
        self.approved_milestones: List[str] = []
        self.modified_milestones: Dict[str, Milestone] = {}
    
    def run(self) -> List[Milestone]:
        """Run milestone review and return approved milestones"""
        self._print_milestone_overview()
        
        if Confirm.ask("\nReview milestones individually?", default=True):
            return self._review_individually()
        elif Confirm.ask("Approve all milestones as-is?", default=False):
            return self.milestones
        else:
            return self._quick_edit()
    
    def _print_milestone_overview(self):
        """Print overview of all milestones"""
        table = Table(title="Development Milestones", show_header=True)
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Name", width=30)
        table.add_column("Tasks", justify="center", width=6)
        table.add_column("Hours", justify="center", width=6)
        table.add_column("Dependencies", width=15)
        
        total_hours = 0
        for m in self.milestones:
            table.add_row(
                m.id,
                m.name,
                str(len(m.tasks)),
                f"{m.estimated_hours:.1f}",
                ", ".join(m.dependencies) or "—"
            )
            total_hours += m.estimated_hours
        
        console.print(table)
        console.print(f"\n[bold]Total estimated time:[/bold] {total_hours:.1f} hours")
    
    def _review_individually(self) -> List[Milestone]:
        """Review each milestone individually"""
        approved = []
        
        for milestone in self.milestones:
            console.print(f"\n{'═' * 60}")
            console.print(f"[bold cyan]Milestone: {milestone.name}[/bold cyan]")
            console.print(f"[dim]{milestone.description}[/dim]")
            console.print()
            
            console.print("[bold]Tasks:[/bold]")
            for task in milestone.tasks:
                console.print(f"  • {task}")
            
            console.print(f"\n[bold]Deliverables:[/bold]")
            for d in milestone.deliverables:
                console.print(f"  ✓ {d}")
            
            console.print(f"\n[bold]Estimate:[/bold] {milestone.estimated_hours:.1f} hours")
            
            choice = Prompt.ask(
                "\nAction",
                choices=["approve", "edit", "skip", "abort"],
                default="approve"
            )
            
            if choice == "approve":
                approved.append(milestone)
            elif choice == "edit":
                edited = self._edit_milestone(milestone)
                approved.append(edited)
            elif choice == "skip":
                console.print(f"[yellow]Skipping {milestone.name}[/yellow]")
            elif choice == "abort":
                break
        
        return approved
    
    def _edit_milestone(self, milestone: Milestone) -> Milestone:
        """Edit a milestone interactively"""
        console.print("\n[bold]Editing milestone...[/bold]")
        
        new_name = Prompt.ask("Name", default=milestone.name)
        new_hours = float(Prompt.ask("Estimated hours", default=str(milestone.estimated_hours)))
        
        console.print("\nCurrent tasks (enter new tasks one per line, empty to finish):")
        for task in milestone.tasks:
            console.print(f"  • {task}")
        
        if Confirm.ask("\nReplace tasks?", default=False):
            new_tasks = []
            while True:
                task = Prompt.ask("Task (empty to finish)", default="")
                if not task:
                    break
                new_tasks.append(task)
            if new_tasks:
                milestone.tasks = new_tasks
        
        milestone.name = new_name
        milestone.estimated_hours = new_hours
        
        return milestone
    
    def _quick_edit(self) -> List[Milestone]:
        """Quick edit mode - adjust estimates only"""
        console.print("\n[bold]Quick Edit Mode[/bold]")
        console.print("Adjust estimates (press Enter to keep current):\n")
        
        for milestone in self.milestones:
            new_hours = Prompt.ask(
                f"{milestone.id} {milestone.name}",
                default=str(milestone.estimated_hours)
            )
            try:
                milestone.estimated_hours = float(new_hours)
            except ValueError:
                pass
        
        return self.milestones


# =============================================================================
# AUTONOMY SELECTION
# =============================================================================

def select_autonomy_level() -> AutonomyLevel:
    """Interactive autonomy level selection"""
    console.print("\n[bold]Select Autonomy Level:[/bold]\n")
    
    table = Table(show_header=True, box=None)
    table.add_column("Option", style="cyan", width=3)
    table.add_column("Level", width=15)
    table.add_column("Checkpoints", justify="center", width=12)
    table.add_column("Best For")
    
    levels = [
        (AutonomyLevel.PAIR_PROGRAMMING, "Maximum control, learning the system"),
        (AutonomyLevel.BALANCED, "Good balance of speed and oversight"),
        (AutonomyLevel.FULLY_AUTONOMOUS, "Well-defined tasks, minimal interruption"),
    ]
    
    for i, (level, best_for) in enumerate(levels, 1):
        count = sum(
            1 for d in __import__('core.checkpoints', fromlist=['ALL_CHECKPOINTS']).ALL_CHECKPOINTS
            if level in d.required_for
        )
        table.add_row(str(i), level.value, str(count), best_for)
    
    console.print(table)
    
    choice = Prompt.ask(
        "\nSelect option",
        choices=["1", "2", "3"],
        default="2"
    )
    
    level_map = {
        "1": AutonomyLevel.PAIR_PROGRAMMING,
        "2": AutonomyLevel.BALANCED,
        "3": AutonomyLevel.FULLY_AUTONOMOUS
    }
    
    selected = level_map[choice]
    console.print(f"\n[green]Selected: {selected.value}[/green]")
    console.print(f"[dim]{get_autonomy_description(selected)}[/dim]")
    
    return selected
