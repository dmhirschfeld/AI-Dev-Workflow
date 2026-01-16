"""
Checkpoint System for AI-Dev-Workflow

Defines checkpoints for different autonomy levels and manages
checkpoint state throughout the workflow.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
from datetime import datetime
from pathlib import Path
import json
import yaml


class AutonomyLevel(Enum):
    """Three levels of human involvement"""
    FULLY_AUTONOMOUS = "autonomous"      # Only critical checkpoints
    BALANCED = "balanced"                 # Moderate checkpoints (default)
    PAIR_PROGRAMMING = "pair"            # Maximum checkpoints


class CheckpointType(Enum):
    """Types of checkpoints in the workflow"""
    # Design Phase
    REQUIREMENTS = "requirements"
    INFORMATION_ARCHITECTURE = "info_architecture"
    WIREFRAMES = "wireframes"
    STYLE_SYSTEM = "style_system"
    HIGH_FIDELITY = "high_fidelity"
    DESIGN_SIGNOFF = "design_signoff"
    
    # Development Phase
    MILESTONE_PLAN = "milestone_plan"
    FOUNDATION = "foundation"
    FEATURE_COMPLETE = "feature_complete"
    INTEGRATION = "integration"
    TESTING = "testing"
    
    # Delivery Phase
    PR_REVIEW = "pr_review"
    FINAL_SIGNOFF = "final_signoff"


class CheckpointStatus(Enum):
    """Status of a checkpoint"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    SKIPPED = "skipped"


@dataclass
class CheckpointFeedback:
    """Feedback provided at a checkpoint"""
    timestamp: str
    decision: str  # approve, revise, skip, abort
    comments: str
    revision_instructions: Optional[str] = None
    confidence_override: bool = False


@dataclass
class CheckpointDefinition:
    """Definition of a checkpoint"""
    checkpoint_type: CheckpointType
    name: str
    description: str
    phase: str  # design, development, delivery
    
    # Which autonomy levels include this checkpoint
    required_for: List[AutonomyLevel]
    
    # What artifacts are produced
    artifacts: List[str]
    
    # Review prompts for human
    review_prompts: List[str]
    
    # Actions available at this checkpoint
    available_actions: List[str] = field(default_factory=lambda: [
        "approve", "feedback", "revise", "save_pause", "abort"
    ])
    
    # Minimum confidence score to auto-approve (if autonomy allows)
    auto_approve_threshold: float = 0.85


@dataclass
class CheckpointState:
    """Runtime state of a checkpoint"""
    definition: CheckpointDefinition
    status: CheckpointStatus = CheckpointStatus.PENDING
    attempts: int = 0
    artifacts_generated: List[str] = field(default_factory=list)
    feedback_history: List[CheckpointFeedback] = field(default_factory=list)
    agent_confidence: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# CHECKPOINT DEFINITIONS BY PHASE
# =============================================================================

DESIGN_CHECKPOINTS = [
    CheckpointDefinition(
        checkpoint_type=CheckpointType.REQUIREMENTS,
        name="Requirements Review",
        description="Review extracted requirements, user stories, and acceptance criteria",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "requirements/user_stories.md",
            "requirements/acceptance_criteria.md",
            "requirements/edge_cases.md",
            "requirements/assumptions.md"
        ],
        review_prompts=[
            "Are all user needs captured?",
            "Are acceptance criteria testable?",
            "Any missing edge cases?",
            "Are assumptions valid?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.INFORMATION_ARCHITECTURE,
        name="Information Architecture Review",
        description="Review site map, screen inventory, and navigation structure",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "design/sitemap.html",
            "design/screen_inventory.md",
            "design/navigation_flow.html",
            "design/data_flow.md"
        ],
        review_prompts=[
            "Does the navigation make sense?",
            "Are all necessary screens included?",
            "Is the user flow intuitive?",
            "Any missing data connections?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.WIREFRAMES,
        name="Wireframe Review",
        description="Review low-fidelity layouts and component placement",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING],
        artifacts=[
            "design/wireframes/*.html",
            "design/component_inventory.md",
            "design/interaction_notes.md"
        ],
        review_prompts=[
            "Is the layout logical?",
            "Are components appropriately placed?",
            "Does the flow match requirements?",
            "Any usability concerns?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.STYLE_SYSTEM,
        name="Style System Review",
        description="Review color palette, typography, and component styling",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING],
        artifacts=[
            "design/style_guide.html",
            "design/color_palette.html",
            "design/typography.html",
            "design/components_styled.html"
        ],
        review_prompts=[
            "Does the style match brand guidelines?",
            "Is the color palette accessible?",
            "Is typography readable?",
            "Are components visually consistent?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.HIGH_FIDELITY,
        name="High-Fidelity Design Review",
        description="Review complete mockups with full styling and interactions",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "design/mockups/*.html",
            "design/interaction_specs.md",
            "design/responsive_notes.md"
        ],
        review_prompts=[
            "Do mockups match requirements?",
            "Are interactions clearly specified?",
            "Is responsive behavior defined?",
            "Ready for development?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.DESIGN_SIGNOFF,
        name="Design Sign-off",
        description="Final approval before development begins",
        phase="design",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED, AutonomyLevel.FULLY_AUTONOMOUS],
        artifacts=[
            "design/final_designs.zip",
            "design/handoff_notes.md"
        ],
        review_prompts=[
            "Is the design complete?",
            "All stakeholder feedback addressed?",
            "Ready to begin development?"
        ],
        auto_approve_threshold=0.95  # Higher bar for sign-off
    ),
]

DEVELOPMENT_CHECKPOINTS = [
    CheckpointDefinition(
        checkpoint_type=CheckpointType.MILESTONE_PLAN,
        name="Milestone Plan Review",
        description="Review auto-generated development milestones",
        phase="development",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "milestones/plan.md",
            "milestones/dependency_graph.html",
            "milestones/estimates.md"
        ],
        review_prompts=[
            "Are milestones appropriately sized?",
            "Is the order logical?",
            "Are dependencies correct?",
            "Are estimates reasonable?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.FOUNDATION,
        name="Foundation Milestone Review",
        description="Review project scaffolding, database schema, and core setup",
        phase="development",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "src/",
            "schema/database.sql",
            "docs/architecture.md",
            "tests/foundation/"
        ],
        review_prompts=[
            "Is the project structure correct?",
            "Does the schema match requirements?",
            "Is auth implemented correctly?",
            "Can you run it locally?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.FEATURE_COMPLETE,
        name="Feature Milestone Review",
        description="Review completed feature implementation",
        phase="development",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING],
        artifacts=[
            "src/features/",
            "tests/features/",
            "docs/feature_notes.md"
        ],
        review_prompts=[
            "Does the feature work as designed?",
            "Are edge cases handled?",
            "Is the code quality acceptable?",
            "Are tests passing?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.INTEGRATION,
        name="Integration Review",
        description="Review integration of all features and systems",
        phase="development",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED],
        artifacts=[
            "src/",
            "tests/integration/",
            "docs/integration_notes.md"
        ],
        review_prompts=[
            "Do all features work together?",
            "Are there any conflicts?",
            "Is performance acceptable?",
            "Any integration issues?"
        ]
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.TESTING,
        name="Testing Review",
        description="Review test coverage and results",
        phase="development",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING],
        artifacts=[
            "tests/",
            "coverage/report.html",
            "docs/test_plan.md"
        ],
        review_prompts=[
            "Is test coverage sufficient?",
            "Are all tests passing?",
            "Any flaky tests?",
            "Manual testing needed?"
        ]
    ),
]

DELIVERY_CHECKPOINTS = [
    CheckpointDefinition(
        checkpoint_type=CheckpointType.PR_REVIEW,
        name="Pull Request Review",
        description="Review generated pull request before submission",
        phase="delivery",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED, AutonomyLevel.FULLY_AUTONOMOUS],
        artifacts=[
            "pr/description.md",
            "pr/diff_summary.md",
            "pr/checklist.md"
        ],
        review_prompts=[
            "Is the PR description clear?",
            "Are all changes intentional?",
            "Ready to submit?"
        ],
        auto_approve_threshold=0.90
    ),
    CheckpointDefinition(
        checkpoint_type=CheckpointType.FINAL_SIGNOFF,
        name="Final Sign-off",
        description="Final approval to merge and deploy",
        phase="delivery",
        required_for=[AutonomyLevel.PAIR_PROGRAMMING, AutonomyLevel.BALANCED, AutonomyLevel.FULLY_AUTONOMOUS],
        artifacts=[
            "delivery/summary.md",
            "delivery/deployment_notes.md"
        ],
        review_prompts=[
            "All requirements met?",
            "Ready to merge?",
            "Any deployment concerns?"
        ],
        auto_approve_threshold=0.95
    ),
]

ALL_CHECKPOINTS = DESIGN_CHECKPOINTS + DEVELOPMENT_CHECKPOINTS + DELIVERY_CHECKPOINTS


# =============================================================================
# CHECKPOINT MANAGER
# =============================================================================

class CheckpointManager:
    """Manages checkpoint flow and state"""
    
    def __init__(
        self,
        project_dir: Path,
        autonomy_level: AutonomyLevel = AutonomyLevel.BALANCED
    ):
        self.project_dir = Path(project_dir)
        self.autonomy_level = autonomy_level
        self.state_file = self.project_dir / ".workflow" / "checkpoint_state.json"
        self.checkpoints: Dict[CheckpointType, CheckpointState] = {}
        self.current_checkpoint: Optional[CheckpointType] = None
        
        self._initialize_checkpoints()
        self._load_state()
    
    def _initialize_checkpoints(self):
        """Initialize checkpoints based on autonomy level"""
        for defn in ALL_CHECKPOINTS:
            if self.autonomy_level in defn.required_for:
                self.checkpoints[defn.checkpoint_type] = CheckpointState(
                    definition=defn
                )
    
    def _load_state(self):
        """Load saved state if exists"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                for cp_type_str, state_data in data.get("checkpoints", {}).items():
                    cp_type = CheckpointType(cp_type_str)
                    if cp_type in self.checkpoints:
                        state = self.checkpoints[cp_type]
                        state.status = CheckpointStatus(state_data["status"])
                        state.attempts = state_data.get("attempts", 0)
                        state.artifacts_generated = state_data.get("artifacts_generated", [])
                        state.agent_confidence = state_data.get("agent_confidence", 0.0)
                        state.started_at = state_data.get("started_at")
                        state.completed_at = state_data.get("completed_at")
                        # Reconstruct feedback history
                        for fb_data in state_data.get("feedback_history", []):
                            state.feedback_history.append(CheckpointFeedback(**fb_data))
                
                self.current_checkpoint = CheckpointType(data["current"]) if data.get("current") else None
            except Exception as e:
                print(f"Warning: Could not load checkpoint state: {e}")
    
    def save_state(self):
        """Persist state to disk"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "autonomy_level": self.autonomy_level.value,
            "current": self.current_checkpoint.value if self.current_checkpoint else None,
            "checkpoints": {}
        }
        
        for cp_type, state in self.checkpoints.items():
            data["checkpoints"][cp_type.value] = {
                "status": state.status.value,
                "attempts": state.attempts,
                "artifacts_generated": state.artifacts_generated,
                "agent_confidence": state.agent_confidence,
                "started_at": state.started_at,
                "completed_at": state.completed_at,
                "feedback_history": [
                    {
                        "timestamp": fb.timestamp,
                        "decision": fb.decision,
                        "comments": fb.comments,
                        "revision_instructions": fb.revision_instructions,
                        "confidence_override": fb.confidence_override
                    }
                    for fb in state.feedback_history
                ]
            }
        
        self.state_file.write_text(json.dumps(data, indent=2))
    
    def get_active_checkpoints(self) -> List[CheckpointState]:
        """Get checkpoints for current autonomy level"""
        return list(self.checkpoints.values())
    
    def get_checkpoints_for_phase(self, phase: str) -> List[CheckpointState]:
        """Get checkpoints for a specific phase"""
        return [
            state for state in self.checkpoints.values()
            if state.definition.phase == phase
        ]
    
    def get_next_checkpoint(self) -> Optional[CheckpointState]:
        """Get next pending checkpoint"""
        for state in self.checkpoints.values():
            if state.status in [CheckpointStatus.PENDING, CheckpointStatus.REVISION_REQUESTED]:
                return state
        return None
    
    def start_checkpoint(self, checkpoint_type: CheckpointType):
        """Mark a checkpoint as in progress"""
        if checkpoint_type in self.checkpoints:
            state = self.checkpoints[checkpoint_type]
            state.status = CheckpointStatus.IN_PROGRESS
            state.started_at = datetime.now().isoformat()
            state.attempts += 1
            self.current_checkpoint = checkpoint_type
            self.save_state()
    
    def submit_for_review(
        self,
        checkpoint_type: CheckpointType,
        artifacts: List[str],
        confidence: float
    ):
        """Submit checkpoint artifacts for review"""
        if checkpoint_type in self.checkpoints:
            state = self.checkpoints[checkpoint_type]
            state.status = CheckpointStatus.AWAITING_REVIEW
            state.artifacts_generated = artifacts
            state.agent_confidence = confidence
            self.save_state()
    
    def should_auto_approve(self, checkpoint_type: CheckpointType) -> bool:
        """Check if checkpoint can be auto-approved based on confidence"""
        if checkpoint_type not in self.checkpoints:
            return False
        
        state = self.checkpoints[checkpoint_type]
        
        # Fully autonomous mode auto-approves if confidence is high enough
        if self.autonomy_level == AutonomyLevel.FULLY_AUTONOMOUS:
            return state.agent_confidence >= state.definition.auto_approve_threshold
        
        return False
    
    def record_feedback(
        self,
        checkpoint_type: CheckpointType,
        decision: str,
        comments: str = "",
        revision_instructions: Optional[str] = None,
        confidence_override: bool = False
    ):
        """Record human feedback for a checkpoint"""
        if checkpoint_type not in self.checkpoints:
            return
        
        state = self.checkpoints[checkpoint_type]
        
        feedback = CheckpointFeedback(
            timestamp=datetime.now().isoformat(),
            decision=decision,
            comments=comments,
            revision_instructions=revision_instructions,
            confidence_override=confidence_override
        )
        state.feedback_history.append(feedback)
        
        if decision == "approve":
            state.status = CheckpointStatus.APPROVED
            state.completed_at = datetime.now().isoformat()
        elif decision == "revise":
            state.status = CheckpointStatus.REVISION_REQUESTED
        elif decision == "skip":
            state.status = CheckpointStatus.SKIPPED
            state.completed_at = datetime.now().isoformat()
        
        self.save_state()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get summary of checkpoint progress"""
        total = len(self.checkpoints)
        completed = sum(
            1 for s in self.checkpoints.values()
            if s.status in [CheckpointStatus.APPROVED, CheckpointStatus.SKIPPED]
        )
        in_progress = sum(
            1 for s in self.checkpoints.values()
            if s.status in [CheckpointStatus.IN_PROGRESS, CheckpointStatus.AWAITING_REVIEW]
        )
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "percent_complete": (completed / total * 100) if total > 0 else 0,
            "current": self.current_checkpoint.value if self.current_checkpoint else None,
            "autonomy_level": self.autonomy_level.value
        }
    
    def get_checkpoint_count_by_level(self) -> Dict[str, int]:
        """Show how many checkpoints each autonomy level has"""
        counts = {}
        for level in AutonomyLevel:
            count = sum(
                1 for defn in ALL_CHECKPOINTS
                if level in defn.required_for
            )
            counts[level.value] = count
        return counts


# =============================================================================
# MILESTONE GENERATOR
# =============================================================================

@dataclass
class Milestone:
    """A development milestone"""
    id: str
    name: str
    description: str
    tasks: List[str]
    estimated_hours: float
    dependencies: List[str]
    checkpoint_type: CheckpointType
    deliverables: List[str]


class MilestoneGenerator:
    """Generates development milestones from design artifacts"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
    
    def generate_milestones(
        self,
        screens: List[str],
        features: List[str],
        autonomy_level: AutonomyLevel
    ) -> List[Milestone]:
        """Generate milestones based on project scope and autonomy level"""
        
        milestones = []
        milestone_id = 0
        
        # Foundation milestone (always included)
        milestone_id += 1
        milestones.append(Milestone(
            id=f"M{milestone_id}",
            name="Foundation",
            description="Project scaffolding, database schema, authentication",
            tasks=[
                "Initialize project structure",
                "Set up database and ORM",
                "Implement authentication system",
                "Configure development environment",
                "Set up CI/CD pipeline"
            ],
            estimated_hours=4.0,
            dependencies=[],
            checkpoint_type=CheckpointType.FOUNDATION,
            deliverables=[
                "Working project scaffold",
                "Database migrations",
                "Auth flow working",
                "README with setup instructions"
            ]
        ))
        
        # Feature milestones based on autonomy level
        if autonomy_level == AutonomyLevel.PAIR_PROGRAMMING:
            # One milestone per screen/feature for maximum granularity
            for screen in screens:
                milestone_id += 1
                milestones.append(Milestone(
                    id=f"M{milestone_id}",
                    name=f"Screen: {screen}",
                    description=f"Implement {screen} screen with full functionality",
                    tasks=[
                        f"Create {screen} UI components",
                        f"Implement {screen} API endpoints",
                        f"Add {screen} business logic",
                        f"Write {screen} tests"
                    ],
                    estimated_hours=2.0,
                    dependencies=[f"M{milestone_id-1}"],
                    checkpoint_type=CheckpointType.FEATURE_COMPLETE,
                    deliverables=[
                        f"{screen} screen functional",
                        f"{screen} tests passing"
                    ]
                ))
        else:
            # Group screens into logical chunks
            chunk_size = 3 if autonomy_level == AutonomyLevel.BALANCED else 5
            for i in range(0, len(screens), chunk_size):
                chunk = screens[i:i+chunk_size]
                milestone_id += 1
                milestones.append(Milestone(
                    id=f"M{milestone_id}",
                    name=f"Features: {', '.join(chunk[:2])}{'...' if len(chunk) > 2 else ''}",
                    description=f"Implement screens: {', '.join(chunk)}",
                    tasks=[f"Implement {s}" for s in chunk],
                    estimated_hours=2.0 * len(chunk),
                    dependencies=[f"M{milestone_id-1}"],
                    checkpoint_type=CheckpointType.FEATURE_COMPLETE,
                    deliverables=[f"{s} functional" for s in chunk]
                ))
        
        # Integration milestone
        milestone_id += 1
        milestones.append(Milestone(
            id=f"M{milestone_id}",
            name="Integration & Polish",
            description="Integrate all features, error handling, loading states",
            tasks=[
                "Integration testing",
                "Error handling",
                "Loading states",
                "Performance optimization",
                "Final polish"
            ],
            estimated_hours=4.0,
            dependencies=[f"M{i}" for i in range(1, milestone_id)],
            checkpoint_type=CheckpointType.INTEGRATION,
            deliverables=[
                "All features integrated",
                "Error handling complete",
                "Performance acceptable"
            ]
        ))
        
        return milestones


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_autonomy_description(level: AutonomyLevel) -> str:
    """Get human-readable description of autonomy level"""
    descriptions = {
        AutonomyLevel.FULLY_AUTONOMOUS: (
            "Minimal interruptions. Only critical checkpoints (design sign-off, "
            "PR review, final sign-off). Best for well-defined tasks with clear requirements."
        ),
        AutonomyLevel.BALANCED: (
            "Moderate checkpoints at key decision points. Reviews requirements, "
            "architecture, designs, and milestones. Good balance of speed and control."
        ),
        AutonomyLevel.PAIR_PROGRAMMING: (
            "Maximum collaboration. Checkpoints at every stage including wireframes, "
            "styling, and each feature. Best for complex projects or learning the system."
        )
    }
    return descriptions.get(level, "")


def get_checkpoint_summary() -> str:
    """Get summary of checkpoints by autonomy level"""
    lines = ["Checkpoint Summary by Autonomy Level:", ""]
    
    for level in AutonomyLevel:
        checkpoints = [d for d in ALL_CHECKPOINTS if level in d.required_for]
        lines.append(f"  {level.value.upper()} ({len(checkpoints)} checkpoints):")
        for cp in checkpoints:
            lines.append(f"    • {cp.name}")
        lines.append("")
    
    return "\n".join(lines)
