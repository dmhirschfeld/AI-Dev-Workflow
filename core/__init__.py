"""
AI-Dev-Workflow - Core Module
"""

from core.agents import AgentFactory, AgentExecutor, AgentResponse, run_agent
from core.orchestrator import Orchestrator, WorkflowState, WorkflowPhase
from core.voting import VotingGateSystem, GateManager, GateResult, Vote
from core.knowledge_base import KnowledgeBase, ContextManager
from core.static_analysis import StaticAnalyzer, analyze_project
from core.enhanced_indexing import EnhancedCodeIndexer, index_codebase
from core.codebase_ingest import CodebaseIngestor, ingest_codebase
from core.health_evaluator import HealthEvaluator, evaluate_project
from core.improvement_planner import ImprovementPlanner, create_improvement_plan

# Assessment and Planning (Ingest Workflow)
try:
    from core.assessment import (
        CodebaseAssessor,
        AssessmentReport,
        CategoryAssessment,
        Finding,
        UXPattern,
        NavigationFlow,
        StyleAnalysis,
        run_assessment,
    )
    from core.ingest_planner import (
        IngestPlanner,
        PlanningReport,
        RoadmapItem,
        AIOpportunity,
        Milestone as PlanMilestone,
        create_plan,
    )
    from core.report_generator import (
        ReportGenerator,
        generate_reports,
    )
    HAS_ASSESSMENT = True
except ImportError:
    HAS_ASSESSMENT = False
from core.context_graph import (
    ContextGraph,
    DecisionTrace,
    DecisionInput,
    PrecedentMatch,
    get_context_graph,
    capture_decision,
    find_precedents,
    record_outcome,
)
from core.voting_integration import (
    ContextAwareVoting,
    EnhancedVote,
    EnhancedGateResult,
    create_voter_prompt_with_precedents,
)
from core.cross_system import (
    CrossSystemSynthesizer,
    SimpleSynthesizer,
    ExternalSignal,
    SynthesizedContext,
)

# Checkpoint System (Interactive Workflow)
try:
    from core.checkpoints import (
        CheckpointManager,
        CheckpointState,
        CheckpointDefinition,
        CheckpointType,
        CheckpointStatus,
        AutonomyLevel,
        Milestone,
        MilestoneGenerator,
        ALL_CHECKPOINTS,
        get_autonomy_description,
        get_checkpoint_summary,
    )
    from core.interactive_session import (
        InteractiveSession,
        MilestoneReviewSession,
        SessionAction,
        select_autonomy_level,
    )
    from core.artifact_viewer import ArtifactViewer
    HAS_CHECKPOINT_SYSTEM = True
except ImportError:
    HAS_CHECKPOINT_SYSTEM = False

try:
    from core.github_integration import (
        GitHubIntegration,
        GitHubRepo,
        get_github,
        setup_check,
        find_or_create_repo,
    )
    HAS_GITHUB = True
except ImportError:
    HAS_GITHUB = False

try:
    from core.usage_tracker import (
        UsageTracker,
        UsageEntry,
        ProjectUsageSummary,
        get_tracker,
        record_usage,
        get_project_cost,
        estimate_cost,
        PRICING,
    )
    HAS_USAGE_TRACKER = True
except ImportError:
    HAS_USAGE_TRACKER = False

try:
    from core.task_decomposition import (
        TaskPlan,
        ImplementationTask,
        TaskSize,
        TaskStatus,
        TaskCategory,
        parse_task_yaml,
        validate_task_plan,
        generate_decomposition_prompt,
    )
    from core.task_executor import (
        TaskExecutor,
        TaskResult,
        execute_architecture_tasks,
    )
    HAS_TASK_SYSTEM = True
except ImportError:
    HAS_TASK_SYSTEM = False

__all__ = [
    # Agents
    "AgentFactory",
    "AgentExecutor", 
    "AgentResponse",
    "run_agent",
    
    # Orchestrator
    "Orchestrator",
    "WorkflowState",
    "WorkflowPhase",
    
    # Voting
    "VotingGateSystem",
    "GateManager",
    "GateResult",
    "Vote",
    
    # Knowledge Base
    "KnowledgeBase",
    "ContextManager",
    
    # Static Analysis
    "StaticAnalyzer",
    "analyze_project",
    
    # Enhanced Indexing
    "EnhancedCodeIndexer",
    "index_codebase",
    
    # Codebase Analysis
    "CodebaseIngestor",
    "ingest_codebase",
    "HealthEvaluator",
    "evaluate_project",
    "ImprovementPlanner",
    "create_improvement_plan",
    
    # Assessment & Planning (Ingest Workflow)
    "CodebaseAssessor",
    "AssessmentReport",
    "CategoryAssessment",
    "Finding",
    "UXPattern",
    "NavigationFlow",
    "StyleAnalysis",
    "run_assessment",
    "IngestPlanner",
    "PlanningReport",
    "RoadmapItem",
    "AIOpportunity",
    "PlanMilestone",
    "create_plan",
    "ReportGenerator",
    "generate_reports",
    
    # Context Graph (NEW)
    "ContextGraph",
    "DecisionTrace",
    "DecisionInput",
    "PrecedentMatch",
    "get_context_graph",
    "capture_decision",
    "find_precedents",
    "record_outcome",
    
    # Context-Aware Voting (NEW)
    "ContextAwareVoting",
    "EnhancedVote",
    "EnhancedGateResult",
    "create_voter_prompt_with_precedents",
    
    # Cross-System Synthesis (NEW)
    "CrossSystemSynthesizer",
    "SimpleSynthesizer",
    "ExternalSignal",
    "SynthesizedContext",
]
