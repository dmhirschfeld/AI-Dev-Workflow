"""
Orchestrator
Central coordinator for the multi-agent software development workflow.
Routes tasks, manages state, and handles the conversational loop.
"""

import yaml
import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from datetime import datetime
from enum import Enum

from core.agents import AgentFactory, AgentExecutor, AgentResponse
from core.voting import VotingGateSystem, GateManager, GateResult
from core.knowledge_base import KnowledgeBase, ContextManager
from core.audit import AuditLogger
from core.lessons_database import LessonsDatabase
from core.feedback_collector import FeedbackCollector, StepFeedback
from core.ai_assessment import AICodebaseAssessor, AssessmentContext, StepResult, calculate_overall_score


class WorkflowPhase(Enum):
    """Phases in the software development workflow"""
    # Feature development phases
    IDEATION = "ideation"
    PRIORITIZATION = "prioritization"
    REQUIREMENTS = "requirements"
    REQUIREMENTS_REVIEW = "requirements_review"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    ARCHITECTURE_REVIEW = "architecture_review"
    DEVELOPMENT = "development"
    CODE_REVIEW = "code_review"
    SIMPLIFICATION = "simplification"
    TESTING = "testing"
    TEST_REVIEW = "test_review"
    DOCUMENTATION = "documentation"
    RELEASE_REVIEW = "release_review"
    DEPLOYMENT = "deployment"
    # Ingest workflow phases
    INGEST_ASSESSMENT = "ingest_assessment"
    INGEST_ASSESSMENT_REVIEW = "ingest_assessment_review"
    INGEST_PLANNING = "ingest_planning"
    INGEST_PLANNING_REVIEW = "ingest_planning_review"
    INGEST_EXECUTION = "ingest_execution"
    # Terminal phases
    COMPLETE = "complete"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class WorkflowState:
    """Current state of the workflow"""
    project_id: str
    current_phase: WorkflowPhase
    current_feature: str
    retry_counts: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)  # phase -> artifact content
    decisions: list = field(default_factory=list)
    gate_results: list = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Step-based voting state
    current_step: int = 0
    step_retry_count: int = 0
    step_results: dict = field(default_factory=dict)  # step_name -> result
    # Assessment mode: "standard", "self_improvement", or "rules_only"
    assessment_mode: str = "standard"
    self_improvement_mode: bool = False  # Alias for assessment_mode == "self_improvement"
    # Optional: specific steps to run (for testing). None = all steps
    test_steps: list = None
    
    def to_dict(self) -> dict:
        """Convert state to dictionary for persistence"""
        return {
            "project_id": self.project_id,
            "current_phase": self.current_phase.value,
            "current_feature": self.current_feature,
            "retry_counts": self.retry_counts,
            "artifacts": self.artifacts,
            "decisions": self.decisions,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "current_step": self.current_step,
            "step_retry_count": self.step_retry_count,
            "step_results": self.step_results,
            "assessment_mode": self.assessment_mode,
            "self_improvement_mode": self.self_improvement_mode
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        """Create state from dictionary"""
        return cls(
            project_id=data["project_id"],
            current_phase=WorkflowPhase(data["current_phase"]),
            current_feature=data["current_feature"],
            retry_counts=data.get("retry_counts", {}),
            artifacts=data.get("artifacts", {}),
            decisions=data.get("decisions", []),
            started_at=data.get("started_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            current_step=data.get("current_step", 0),
            step_retry_count=data.get("step_retry_count", 0),
            step_results=data.get("step_results", {}),
            assessment_mode=data.get("assessment_mode", "standard"),
            self_improvement_mode=data.get("self_improvement_mode", False)
        )


@dataclass
class Decision:
    """Record of a decision made during the workflow"""
    timestamp: str
    agent_id: str
    phase: str
    decision: str
    rationale: str
    affects: list[str]


class Orchestrator:
    """
    Main orchestrator for the multi-agent workflow.
    Coordinates agents, manages state, and handles quality gates.
    """
    
    # Phase transitions - Feature development workflow
    PHASE_TRANSITIONS = {
        WorkflowPhase.IDEATION: WorkflowPhase.PRIORITIZATION,
        WorkflowPhase.PRIORITIZATION: WorkflowPhase.REQUIREMENTS,
        WorkflowPhase.REQUIREMENTS: WorkflowPhase.REQUIREMENTS_REVIEW,
        WorkflowPhase.REQUIREMENTS_REVIEW: WorkflowPhase.DESIGN,
        WorkflowPhase.DESIGN: WorkflowPhase.ARCHITECTURE,
        WorkflowPhase.ARCHITECTURE: WorkflowPhase.ARCHITECTURE_REVIEW,
        WorkflowPhase.ARCHITECTURE_REVIEW: WorkflowPhase.DEVELOPMENT,
        WorkflowPhase.DEVELOPMENT: WorkflowPhase.CODE_REVIEW,
        WorkflowPhase.CODE_REVIEW: WorkflowPhase.SIMPLIFICATION,
        WorkflowPhase.SIMPLIFICATION: WorkflowPhase.TESTING,
        WorkflowPhase.TESTING: WorkflowPhase.TEST_REVIEW,
        WorkflowPhase.TEST_REVIEW: WorkflowPhase.DOCUMENTATION,
        WorkflowPhase.DOCUMENTATION: WorkflowPhase.RELEASE_REVIEW,
        WorkflowPhase.RELEASE_REVIEW: WorkflowPhase.DEPLOYMENT,
        WorkflowPhase.DEPLOYMENT: WorkflowPhase.COMPLETE,
        # Ingest workflow transitions
        WorkflowPhase.INGEST_ASSESSMENT: WorkflowPhase.INGEST_ASSESSMENT_REVIEW,
        WorkflowPhase.INGEST_ASSESSMENT_REVIEW: WorkflowPhase.INGEST_PLANNING,
        WorkflowPhase.INGEST_PLANNING: WorkflowPhase.INGEST_PLANNING_REVIEW,
        WorkflowPhase.INGEST_PLANNING_REVIEW: WorkflowPhase.INGEST_EXECUTION,
        WorkflowPhase.INGEST_EXECUTION: WorkflowPhase.COMPLETE,
    }

    # Phase to agent mapping
    PHASE_AGENTS = {
        WorkflowPhase.IDEATION: "ideation",
        WorkflowPhase.PRIORITIZATION: "product_owner",
        WorkflowPhase.REQUIREMENTS: "business_analyst",
        WorkflowPhase.DESIGN: "ui_ux_designer",
        WorkflowPhase.ARCHITECTURE: "solutions_architect",
        WorkflowPhase.DEVELOPMENT: "developer",
        WorkflowPhase.SIMPLIFICATION: "code_simplifier",
        WorkflowPhase.TESTING: "test_writer",
        WorkflowPhase.DOCUMENTATION: "technical_writer",
        WorkflowPhase.DEPLOYMENT: "devops",
        # Ingest workflow agents (local analyzers, not AI)
        WorkflowPhase.INGEST_ASSESSMENT: "codebase_assessor",
        WorkflowPhase.INGEST_PLANNING: "improvement_planner",
        WorkflowPhase.INGEST_EXECUTION: "execution_coordinator",
    }

    # Phase to gate mapping
    PHASE_GATES = {
        WorkflowPhase.REQUIREMENTS_REVIEW: "requirements_approval",
        WorkflowPhase.ARCHITECTURE_REVIEW: "architecture_approval",
        WorkflowPhase.CODE_REVIEW: "code_review",
        WorkflowPhase.TEST_REVIEW: "test_coverage",
        WorkflowPhase.RELEASE_REVIEW: "release_readiness",
        # Ingest workflow gates
        WorkflowPhase.INGEST_ASSESSMENT_REVIEW: "assessment_approval",
        WorkflowPhase.INGEST_PLANNING_REVIEW: "planning_approval",
    }

    # Ingest phases (handled specially, not via AI agents)
    INGEST_PHASES = {
        WorkflowPhase.INGEST_ASSESSMENT,
        WorkflowPhase.INGEST_PLANNING,
        WorkflowPhase.INGEST_EXECUTION,
    }
    
    def __init__(
        self,
        project_id: str,
        project_config_path: str | None = None,
        project_dir: str | Path | None = None,
        agents_config_path: str = "agents/definitions.yaml",
        gates_config_path: str = "config/gates.yaml",
        knowledge_base_dir: str = "./data/knowledge_base",
        enable_audit: bool = True
    ):
        self.project_id = project_id
        self.project_dir = Path(project_dir) if project_dir else Path(f"projects/{project_id}")

        # Load project config
        self.project_config = {}
        if project_config_path and Path(project_config_path).exists():
            with open(project_config_path) as f:
                self.project_config = yaml.safe_load(f)

        # Initialize audit logger
        self.audit_logger: Optional[AuditLogger] = None
        if enable_audit:
            self.audit_logger = AuditLogger(self.project_dir, project_id)

        # Initialize components
        self.agent_factory = AgentFactory(agents_config_path)
        self.agent_executor = AgentExecutor(self.agent_factory, audit_logger=self.audit_logger)
        self.gate_system = VotingGateSystem(gates_config_path, agents_config_path)
        self.gate_manager = GateManager(self.gate_system)

        # Knowledge base and context
        self.kb = KnowledgeBase(project_id, knowledge_base_dir)
        self.context_manager = ContextManager(self.kb, self.project_config)

        # State
        self.state: WorkflowState | None = None

        # Lessons database for self-improvement mode
        self.lessons_db = LessonsDatabase()
        self.feedback_collector = FeedbackCollector(self.lessons_db)

        # AI-powered codebase assessor (uses lessons database)
        self.ai_assessor = AICodebaseAssessor(self.lessons_db, agents_config_path, audit_logger=self.audit_logger)

        # Callbacks
        self.on_phase_change: Callable[[WorkflowPhase, WorkflowPhase], None] | None = None
        self.on_gate_result: Callable[[GateResult], None] | None = None
        self.on_agent_response: Callable[[AgentResponse], None] | None = None
        self.on_escalation: Callable[[str, WorkflowState], None] | None = None
        self.on_progress: Callable[[str, int, int], None] | None = None  # (step_name, current, total)
        self.on_voter_progress: Callable[[str, any, int, int], None] | None = None  # (voter_id, vote, total, completed)
        self.on_lesson_learned: Callable[[str, str], None] | None = None  # (step_name, lesson_pattern)

        # Quit flag for graceful exit
        self._quit_requested = False

        # Wire audit logger to callbacks if enabled
        if self.audit_logger:
            self._setup_audit_callbacks()
    
    def start_feature(self, feature_description: str) -> WorkflowState:
        """Start a new feature workflow"""
        self.state = WorkflowState(
            project_id=self.project_id,
            current_phase=WorkflowPhase.IDEATION,
            current_feature=feature_description
        )
        return self.state

    def start_ingest(
        self,
        source_path: str,
        description: str = "",
        assessment_mode: str = "standard"
    ) -> WorkflowState:
        """
        Start an ingest workflow for analyzing existing codebase.

        Args:
            source_path: Path to the codebase to analyze
            description: Optional description of the analysis
            assessment_mode: One of "standard", "self_improvement", or "rules_only"
                - standard: AI assessment with learned knowledge, no per-step voting
                - self_improvement: AI assessment with per-step voting, feedback captured
                - rules_only: Only run deterministic rules, no AI
        """
        self.source_path = source_path
        self.state = WorkflowState(
            project_id=self.project_id,
            current_phase=WorkflowPhase.INGEST_ASSESSMENT,
            current_feature=description or f"Analyzing {source_path}",
            assessment_mode=assessment_mode,
            self_improvement_mode=(assessment_mode == "self_improvement")
        )
        # Store ingest-specific data
        self.ingest_assessment = None
        self.ingest_plan = None

        # Record project in lessons database
        self.lessons_db.record_project(self.project_id)

        return self.state

    def load_state(self, state_dict: dict) -> WorkflowState:
        """Load existing workflow state"""
        self.state = WorkflowState.from_dict(state_dict)
        return self.state

    def request_quit(self) -> None:
        """Request graceful workflow exit. Checked between steps."""
        self._quit_requested = True

    @property
    def quit_requested(self) -> bool:
        """Check if quit has been requested."""
        return self._quit_requested

    def _setup_audit_callbacks(self):
        """Wire audit logger to orchestrator callbacks"""
        # Store original callbacks (if any)
        original_phase_change = self.on_phase_change
        original_gate_result = self.on_gate_result
        original_escalation = self.on_escalation

        def audit_phase_change(old_phase: WorkflowPhase, new_phase: WorkflowPhase):
            # Log to audit trail
            if self.audit_logger:
                checkpoint = None
                if new_phase in self.PHASE_GATES:
                    checkpoint = f"CP-{new_phase.value.upper().replace('_', '-')}"
                self.audit_logger.log_phase_change(
                    old_phase.value,
                    new_phase.value,
                    checkpoint=checkpoint
                )
            # Call original callback if set
            if original_phase_change:
                original_phase_change(old_phase, new_phase)

        def audit_gate_result(result: GateResult):
            # Log to audit trail
            if self.audit_logger:
                # Use gate_name if set (e.g., "Performance Assessment"), else fall back to gate_id
                display_name = getattr(result, 'gate_name', None) or result.gate_id
                self.audit_logger.log_gate_vote(
                    gate_id=display_name,
                    voters=[v.voter_id for v in result.votes],
                    votes_for=sum(1 for v in result.votes if v.vote == "pass"),
                    votes_against=sum(1 for v in result.votes if v.vote == "fail"),
                    passed=result.passed,
                    phase=self.state.current_phase.value if self.state else None,
                    feedback=result.aggregated_feedback
                )
            # Call original callback if set
            if original_gate_result:
                original_gate_result(result)

        def audit_escalation(reason: str, state: WorkflowState):
            # Log to audit trail
            if self.audit_logger:
                self.audit_logger.log_escalation(
                    reason=reason,
                    phase=state.current_phase.value,
                    context=state.current_feature
                )
            # Call original callback if set
            if original_escalation:
                original_escalation(reason, state)

        # Set callbacks
        self.on_phase_change = audit_phase_change
        self.on_gate_result = audit_gate_result
        self.on_escalation = audit_escalation

    def finalize_audit(self):
        """Finalize audit logging for this session"""
        if self.audit_logger:
            self.audit_logger.finalize()

    async def run_phase(self) -> tuple[bool, str]:
        """
        Execute the current phase of the workflow.
        Returns (success, output/feedback)
        """
        if not self.state:
            raise ValueError("No workflow state. Call start_feature() first.")

        # Check for quit request
        if self._quit_requested:
            return False, "QUIT_REQUESTED"

        phase = self.state.current_phase

        # Check if this is a review phase (gate)
        if phase in self.PHASE_GATES:
            return await self._run_gate_phase()

        # Check if this is an ingest phase (local analyzer, not AI)
        if phase in self.INGEST_PHASES:
            return await self._run_ingest_phase()

        # Check if this is an agent phase
        if phase in self.PHASE_AGENTS:
            return await self._run_agent_phase()

        # Terminal phases
        if phase == WorkflowPhase.COMPLETE:
            return True, "Workflow complete!"

        if phase in (WorkflowPhase.FAILED, WorkflowPhase.ESCALATED):
            return False, f"Workflow ended in {phase.value} state"

        return False, f"Unknown phase: {phase}"
    
    async def _run_agent_phase(self) -> tuple[bool, str]:
        """Run a phase that involves an agent producing output"""
        phase = self.state.current_phase
        agent_id = self.PHASE_AGENTS[phase]

        # Set phase on executor for audit logging
        checkpoint = f"CP-{phase.value.upper().replace('_', '-')}"
        self.agent_executor.set_phase(phase.value, checkpoint)

        # Get context for this agent
        context = self.context_manager.get_context_for_agent(
            agent_id,
            self.state.current_feature
        )

        # Build task based on phase and previous artifacts
        task = self._build_task_for_phase(phase)

        # Execute agent
        response = await self.agent_executor.execute(
            agent_id,
            task,
            context
        )
        
        if self.on_agent_response:
            self.on_agent_response(response)
        
        if response.success:
            # Store artifact
            self.state.artifacts[phase.value] = response.content
            
            # Store in knowledge base
            self._store_artifact_in_kb(phase, response.content)
            
            # Record decision
            self._record_decision(
                agent_id=agent_id,
                phase=phase.value,
                decision=f"Completed {phase.value}",
                rationale="Agent task completed successfully"
            )
            
            # Advance phase
            self._advance_phase()
            
            return True, response.content
        
        return False, response.error or "Agent execution failed"
    
    async def _run_gate_phase(self) -> tuple[bool, str]:
        """Run a phase that involves a voting gate"""
        phase = self.state.current_phase
        gate_id = self.PHASE_GATES[phase]
        
        # Get the artifact to review
        artifact = self._get_artifact_for_gate(phase)
        context = self.context_manager.get_context_for_agent("orchestrator", self.state.current_feature)
        
        # Define retry callback
        async def on_fail(current_artifact: str, feedback: str) -> str:
            # Get the responsible agent to revise
            responsible_agent = self._get_agent_for_revision(phase)
            
            revision_task = f"""Your previous work did not pass the quality gate.

## Feedback from reviewers:
{feedback}

## Original work:
{current_artifact}

## Task:
Please revise your work addressing the feedback above.
"""
            response = await self.agent_executor.execute(
                responsible_agent,
                revision_task,
                context
            )
            
            return response.content if response.success else current_artifact
        
        # Run gate with retry
        passed, result, attempts = await self.gate_manager.run_with_retry(
            gate_id,
            artifact,
            context,
            on_fail_callback=on_fail
        )
        
        # Store results
        self.state.gate_results.extend(attempts)
        
        if self.on_gate_result:
            self.on_gate_result(result)
        
        if passed:
            self._record_decision(
                agent_id="voting_committee",
                phase=phase.value,
                decision=f"Approved after {len(attempts)} attempt(s)",
                rationale=result.aggregated_feedback
            )
            self._advance_phase()
            return True, "Gate passed"
        
        # Check for escalation
        if len(attempts) >= 3:
            self.state.current_phase = WorkflowPhase.ESCALATED
            if self.on_escalation:
                self.on_escalation(f"Gate {gate_id} failed after {len(attempts)} attempts", self.state)
            return False, f"Escalated: {result.aggregated_feedback}"
        
        return False, result.aggregated_feedback

    async def _run_step_with_voting(
        self,
        step_name: str,
        step_func: Callable,
        max_retries: int = 3,
        use_ai_voting: bool = False
    ) -> tuple[bool, Any, str]:
        """
        Run a step and validate it. For local analyzers, auto-approve with logging.
        For AI content, use full voting with retry.

        Returns: (success, result, feedback)
        """
        import time

        for attempt in range(max_retries):
            self.state.step_retry_count = attempt

            # Notify progress
            if self.on_progress:
                self.on_progress(f"{step_name} (attempt {attempt + 1}/{max_retries})", self.state.current_step, 10)

            start_time = time.perf_counter()

            # Run the step
            try:
                result = step_func()
            except Exception as e:
                error_msg = str(e)
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                # Log failure
                if self.audit_logger:
                    self.audit_logger.log_agent_call(
                        agent_id=f"step_{step_name.lower().replace(' ', '_')}",
                        model="local",
                        input_text=f"Running step: {step_name}",
                        output_text=f"Error: {error_msg}",
                        input_tokens=0,
                        output_tokens=0,
                        duration_ms=duration_ms,
                        phase=self.state.current_phase.value,
                        success=False,
                        error=error_msg
                    )

                self._record_decision(
                    agent_id=f"step_{step_name.lower().replace(' ', '_')}",
                    phase=self.state.current_phase.value,
                    decision=f"Step '{step_name}' failed (attempt {attempt + 1}/{max_retries})",
                    rationale=f"Execution error: {error_msg}"
                )
                continue

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Generate reasoning summary from result
            reasoning = self._generate_step_reasoning(step_name, result)

            # Log the step execution with reasoning
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id=f"step_{step_name.lower().replace(' ', '_')}",
                    model="local",
                    input_text=f"Analyzing: {step_name}",
                    output_text=reasoning[:500],
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=duration_ms,
                    phase=self.state.current_phase.value,
                    success=True
                )

            # For local analyzers, auto-approve and log
            if not use_ai_voting:
                self.state.step_results[step_name] = result

                # Log auto-approval with reasoning
                self._record_decision(
                    agent_id="local_validator",
                    phase=self.state.current_phase.value,
                    decision=f"Step '{step_name}' auto-approved",
                    rationale=reasoning
                )

                # Trigger gate result callback (which handles audit logging)
                if self.on_gate_result:
                    # Create a synthetic gate result for callbacks
                    from core.voting import GateResult, Vote
                    gate_result = GateResult(
                        gate_id=f"step_{step_name.lower().replace(' ', '_')}_validation",
                        gate_name=f"{step_name} Validation",
                        passed=True,
                        votes=[Vote(
                            voter_id="local_validator",
                            voter_role="Local Analyzer",
                            vote="pass",
                            confidence=100,
                            reasoning=reasoning,
                            concerns=[],
                            suggestions=[]
                        )],
                        approve_count=1,
                        reject_count=0,
                        threshold=1,
                        retry_count=attempt,
                        aggregated_feedback=reasoning
                    )
                    self.on_gate_result(gate_result)

                return True, result, reasoning

            # For AI content, use full voting
            gate_result = await self._vote_on_step(step_name, result)

            if gate_result.passed:
                self.state.step_results[step_name] = result
                self._record_decision(
                    agent_id="step_validation",
                    phase=self.state.current_phase.value,
                    decision=f"Step '{step_name}' passed by voters",
                    rationale=gate_result.aggregated_feedback or "Voters passed the step"
                )
                return True, result, gate_result.aggregated_feedback

            # Log rejection and retry
            self._record_decision(
                agent_id="step_validation",
                phase=self.state.current_phase.value,
                decision=f"Step '{step_name}' rejected (attempt {attempt + 1}/{max_retries})",
                rationale=gate_result.aggregated_feedback or "Voters rejected the step"
            )

            # In self-improvement mode, capture feedback for learning
            if self.state.self_improvement_mode:
                self._capture_step_feedback(step_name, reasoning, gate_result)

        # All retries exhausted
        return False, None, f"Step '{step_name}' failed after {max_retries} attempts"

    def _capture_step_feedback(
        self,
        step_name: str,
        assessment_output: str,
        gate_result: GateResult
    ) -> None:
        """Capture voter feedback and update lessons database (self-improvement mode)."""
        # Normalize step name to match lessons database keys
        normalized_step = step_name.lower().replace(" ", "_")

        # Process the gate result and extract lessons
        feedback = self.feedback_collector.process_gate_result(
            gate_result=gate_result,
            step_name=normalized_step,
            project_id=self.project_id,
            assessment_output=assessment_output
        )

        # Notify callback if set
        if self.on_lesson_learned and feedback.missing_checks:
            for pattern in feedback.missing_checks:
                self.on_lesson_learned(normalized_step, pattern)

        # Log the learning event
        if self.audit_logger and (feedback.missing_checks or feedback.incorrect_findings):
            self.audit_logger.log_decision(
                decision=f"Lesson learned from {step_name} rejection",
                rationale=f"Captured {len(feedback.missing_checks)} missing checks, "
                         f"{len(feedback.incorrect_findings)} incorrect findings",
                agent_id="feedback_collector",
                phase=self.state.current_phase.value
            )

    def _generate_step_reasoning(self, step_name: str, result: Any) -> str:
        """Generate a detailed reasoning summary from a step result (CategoryScore)"""
        if hasattr(result, 'score') and hasattr(result, 'strengths') and hasattr(result, 'weaknesses'):
            # It's a CategoryScore - generate detailed output
            lines = [
                f"## {step_name} Analysis",
                f"**Score: {result.score}/100 ({result.status})**",
                ""
            ]

            if result.strengths:
                lines.append("### Strengths:")
                for s in result.strengths:
                    lines.append(f"  ✓ {s}")
                lines.append("")

            if result.weaknesses:
                lines.append("### Weaknesses:")
                for w in result.weaknesses:
                    lines.append(f"  ✗ {w}")
                lines.append("")

            if hasattr(result, 'findings') and result.findings:
                lines.append(f"### Findings ({len(result.findings)}):")
                for f in result.findings[:5]:  # Show top 5 findings
                    lines.append(f"  [{f.severity.upper()}] {f.title}")
                    if f.recommendation:
                        lines.append(f"    → {f.recommendation[:80]}...")
                if len(result.findings) > 5:
                    lines.append(f"  ... and {len(result.findings) - 5} more findings")

            return "\n".join(lines)
        elif hasattr(result, '__dict__'):
            # Generic object
            return f"Completed analysis: {step_name}"
        else:
            return f"Step completed: {step_name}"

    async def _vote_on_step(self, step_name: str, result: Any) -> GateResult:
        """Have AI voters review a step result"""
        import json
        from dataclasses import asdict, is_dataclass

        # Convert result to string for voting
        # Use asdict for dataclasses to properly serialize nested objects (e.g., Finding inside CategoryScore)
        if is_dataclass(result) and not isinstance(result, type):
            result_dict = asdict(result)
            artifact = json.dumps(result_dict, indent=2, default=str)
            # Log artifact details for debugging
            findings_count = len(result_dict.get('findings', []))
            if self.audit_logger:
                self.audit_logger.log_decision(
                    agent_id="vote_serializer",
                    phase=self.state.current_phase.value,
                    decision=f"Serialized {step_name} for voting",
                    rationale=f"Type: dataclass, Size: {len(artifact)} chars, Findings: {findings_count}"
                )
        elif hasattr(result, '__dict__'):
            artifact = json.dumps(result.__dict__, indent=2, default=str)
        elif isinstance(result, dict):
            artifact = json.dumps(result, indent=2, default=str)
        else:
            artifact = str(result)

        # Get context
        context = f"Reviewing step '{step_name}' in phase {self.state.current_phase.value}"

        # Run the step_validation gate with step name for display
        result = await self.gate_system.run_gate(
            "step_validation",
            artifact,
            context
        )

        # Add step name to result for display purposes
        result.gate_name = f"{step_name} Assessment"

        if self.on_gate_result:
            self.on_gate_result(result)

        return result

    async def _run_ingest_phase(self) -> tuple[bool, str]:
        """Run an ingest phase using local analyzers (not AI agents)"""
        import time
        from dataclasses import asdict

        phase = self.state.current_phase
        checkpoint = f"CP-{phase.value.upper().replace('_', '-')}"

        if phase == WorkflowPhase.INGEST_ASSESSMENT:
            # Run codebase assessment with step-based voting
            from core.assessment import CodebaseAssessor, AssessmentReport, CategoryScore
            from datetime import datetime

            # Get project config if available
            project_config = {}
            config_path = self.project_dir / "config.yaml"
            if config_path.exists():
                import yaml
                with open(config_path) as f:
                    project_config = yaml.safe_load(f) or {}

            # Determine assessment mode
            use_ai = self.state.assessment_mode != "rules_only"

            # Create assessment context for AI assessor (uses lessons database)
            assessment_context = self._build_assessment_context(project_config)

            # Create heuristic assessor for file-level analysis
            assessor = CodebaseAssessor(
                self.source_path,
                project_config,
                on_progress=self.on_progress
            )

            # Reset step state
            self.state.current_step = 0
            self.state.step_results = {}

            # Step definitions - map display names to assessment keys
            step_definitions = [
                ("Architecture", "architecture"),
                ("Code Quality", "code_quality"),
                ("Tech Debt", "tech_debt"),
                ("Security", "security"),
                ("UX Navigation", "ux_navigation"),
                ("UX Styling", "ux_styling"),
                ("Accessibility", "ux_accessibility"),
                ("Performance", "performance"),
                ("Testing", "testing"),
                ("Documentation", "documentation"),
            ]

            # Check for quit request
            if self._quit_requested:
                return False, "QUIT_REQUESTED"

            # Determine mode: parallel (standard) or sequential (self-improvement)
            if not self.state.self_improvement_mode:
                # PARALLEL MODE: Run all 10 assessments concurrently
                if self.on_progress:
                    self.on_progress("Running all assessments in parallel...", 0, 10)

                def on_step_done(step_name: str, result):
                    self.state.current_step += 1
                    self.state.step_results[step_name] = self._step_result_to_category_score(result)
                    if self.on_progress:
                        self.on_progress(f"Completed: {step_name}", self.state.current_step, 10)

                all_results = await self.ai_assessor.assess_all(
                    assessment_context,
                    mode=self.state.assessment_mode,
                    on_step_complete=on_step_done,
                    parallel=True,
                    steps=self.state.test_steps
                )

                # Store converted results
                for step_key, ai_result in all_results.items():
                    self.state.step_results[step_key] = self._step_result_to_category_score(ai_result)

            else:
                # SELF-IMPROVEMENT MODE: Parallel assessments, then parallel voting
                # Phase 1: Run ALL 10 assessments in parallel
                if self.on_progress:
                    self.on_progress("🚀 Phase 1: Running all 10 assessments in parallel...", 0, 10)

                def on_assess_done(step_name: str, result):
                    self.state.current_step += 1
                    if self.on_progress:
                        self.on_progress(f"✓ {step_name} assessed", self.state.current_step, 10)

                all_results = await self.ai_assessor.assess_all(
                    assessment_context,
                    mode=self.state.assessment_mode,
                    on_step_complete=on_assess_done,
                    parallel=True,
                    steps=self.state.test_steps
                )

                # Convert results - keep both original StepResult and CategoryScore
                step_results_map = {}  # CategoryScore for voting display
                ai_results_map = {}    # Original StepResult for revision
                for step_key, ai_result in all_results.items():
                    ai_results_map[step_key] = ai_result
                    step_results_map[step_key] = self._step_result_to_category_score(ai_result)
                    self.state.step_results[step_key] = step_results_map[step_key]

                if self._quit_requested:
                    return False, "QUIT_REQUESTED"

                # Phase 2: Run ALL voting in parallel with retry that re-runs assessment
                if self.on_progress:
                    self.on_progress("🗳️ Phase 2: Running all 10 voting sessions in parallel...", 0, 10)

                async def vote_on_step(step_name: str, step_key: str) -> tuple[str, bool, str]:
                    """Vote on a single step with retry that re-runs assessment on failure."""
                    current_category_score = step_results_map.get(step_key)
                    current_ai_result = ai_results_map.get(step_key)
                    if not current_category_score or not current_ai_result:
                        return step_name, False, "No assessment result"

                    # Get the assessor for potential re-runs
                    assessor = self.ai_assessor.assessors.get(step_key)
                    last_feedback = ""

                    for attempt in range(3):  # max_retries = 3
                        # On retry (attempt > 0), re-run assessment with voter feedback
                        if attempt > 0 and assessor and last_feedback:
                            try:
                                print(f"  🔄 Retry {attempt + 1}: Re-running {step_name} assessment with voter feedback...")
                                # Re-run assessment with voter feedback
                                revised_ai_result = await assessor.assess_with_feedback(
                                    assessment_context,
                                    current_ai_result,
                                    last_feedback
                                )
                                # Update both maps with revised result
                                current_ai_result = revised_ai_result
                                current_category_score = self._step_result_to_category_score(revised_ai_result)
                                ai_results_map[step_key] = current_ai_result
                                step_results_map[step_key] = current_category_score
                                self.state.step_results[step_key] = current_category_score
                                print(f"  ✓ {step_name} revised (new score: {revised_ai_result.score})")
                            except Exception as e:
                                print(f"  ⚠️ Revision failed for {step_name}: {e}, continuing with previous result")
                                # If revision fails, continue with previous result

                        # Vote on current result
                        gate_result = await self._vote_on_step(step_name, current_category_score)

                        if gate_result.passed:
                            self.state.step_results[step_key] = current_category_score
                            self._record_decision(
                                agent_id="step_validation",
                                phase=self.state.current_phase.value,
                                decision=f"Step '{step_name}' passed by voters (attempt {attempt + 1})",
                                rationale=gate_result.aggregated_feedback or "Voters passed the step"
                            )
                            return step_name, True, gate_result.aggregated_feedback

                        # Capture feedback for next retry
                        last_feedback = gate_result.aggregated_feedback

                        # In self-improvement mode, capture feedback for learning
                        if self.state.self_improvement_mode:
                            self._capture_step_feedback(step_name, str(current_category_score), gate_result)

                        self._record_decision(
                            agent_id="step_validation",
                            phase=self.state.current_phase.value,
                            decision=f"Step '{step_name}' rejected (attempt {attempt + 1}/3)",
                            rationale=gate_result.aggregated_feedback or "Voters rejected the step"
                        )

                    return step_name, False, f"Failed after 3 attempts. Last feedback: {last_feedback}"

                # Run all voting in parallel
                import time
                vote_start = time.time()
                vote_tasks = [vote_on_step(name, key) for name, key in step_definitions]
                vote_results = await asyncio.gather(*vote_tasks, return_exceptions=True)
                vote_duration = time.time() - vote_start
                print(f"\n⚡ All voting completed in {vote_duration:.1f}s")

                # Collect failures
                failed_steps = []
                for item in vote_results:
                    if isinstance(item, Exception):
                        failed_steps.append(("Unknown", str(item)))
                    else:
                        step_name, success, feedback = item
                        if not success:
                            failed_steps.append((step_name, feedback))

                if self.on_progress:
                    passed = 10 - len(failed_steps)
                    self.on_progress(f"Voting complete: {passed}/10 passed", 10, 10)

                # Report failures but continue (learning happened)
                if failed_steps:
                    self.state.current_phase = WorkflowPhase.ESCALATED
                    failure_summary = "; ".join([f"{name}" for name, fb in failed_steps])
                    if self.on_escalation:
                        self.on_escalation(
                            f"{len(failed_steps)} step(s) failed voting: {failure_summary}",
                            self.state
                        )
                    return False, f"Assessment completed with {len(failed_steps)} failed step(s): {failure_summary}"

            # All steps passed - combine results into final assessment
            assessment = self._combine_assessment_results(assessor, project_config)
            self.ingest_assessment = assessment

            # Store artifact as JSON string
            import json
            artifact = json.dumps(asdict(assessment), indent=2, default=str)
            self.state.artifacts[phase.value] = artifact

            # Log to audit
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id="codebase_assessor",
                    model="local",
                    input_text=f"Analyzing {self.source_path}",
                    output_text=f"Score: {assessment.overall_score}/100, {len(assessment.all_findings)} findings",
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=0,
                    phase=phase.value,
                    checkpoint=checkpoint,
                    success=True
                )

            self._record_decision(
                agent_id="codebase_assessor",
                phase=phase.value,
                decision=f"Assessment complete: {assessment.overall_score}/100",
                rationale=f"Found {len(assessment.all_findings)} findings across {assessment.files_analyzed} files"
            )

            # Run final AI voting gate to review complete assessment
            if self.on_progress:
                self.on_progress("Final Assessment Review", 10, 10)

            # Create summary for voters
            assessment_summary = f"""## Codebase Assessment Summary

**Overall Score: {assessment.overall_score}/100 ({assessment.overall_status})**

### Category Scores:
- Architecture: {assessment.architecture.score}/100
- Code Quality: {assessment.code_quality.score}/100
- Tech Debt: {assessment.tech_debt.score}/100
- Security: {assessment.security.score}/100
- UX Navigation: {assessment.ux_navigation.score}/100
- UX Styling: {assessment.ux_styling.score}/100
- Accessibility: {assessment.ux_accessibility.score}/100
- Performance: {assessment.performance.score}/100
- Testing: {assessment.testing.score}/100
- Documentation: {assessment.documentation.score}/100

### Key Findings:
- Critical Issues: {assessment.critical_count}
- High Priority Issues: {assessment.high_count}
- AI-Fixable Issues: {assessment.ai_fixable_count}
- Files Analyzed: {assessment.files_analyzed}

### Top Concerns:
"""
            # Add top findings
            for finding in assessment.all_findings[:5]:
                assessment_summary += f"- [{finding.severity.upper()}] {finding.title}\n"

            # Run the assessment_approval gate with AI voters
            gate_result = await self.gate_system.run_gate(
                "assessment_approval",
                assessment_summary,
                f"Review of codebase assessment for {self.project_id}",
                on_voter_progress=self.on_voter_progress
            )

            # Trigger gate result callback (which handles audit logging)
            if self.on_gate_result:
                self.on_gate_result(gate_result)

            if not gate_result.passed:
                # Assessment rejected by voters
                self._record_decision(
                    agent_id="assessment_approval",
                    phase=phase.value,
                    decision="Assessment rejected by voters",
                    rationale=gate_result.aggregated_feedback
                )
                return False, f"Assessment rejected: {gate_result.aggregated_feedback}"

            self._record_decision(
                agent_id="assessment_approval",
                phase=phase.value,
                decision="Assessment passed by voters",
                rationale=gate_result.aggregated_feedback or "Voters passed the assessment"
            )

            self._advance_phase()
            return True, artifact

        elif phase == WorkflowPhase.INGEST_PLANNING:
            # Run improvement planning
            from core.planning import IngestPlanner

            if not self.ingest_assessment:
                return False, "No assessment available. Run INGEST_ASSESSMENT first."

            start_time = time.perf_counter()

            planner = IngestPlanner(self.ingest_assessment)
            plan = planner.create_plan()
            self.ingest_plan = plan

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Store artifact
            import json
            artifact = json.dumps(asdict(plan), indent=2, default=str)
            self.state.artifacts[phase.value] = artifact

            # Log to audit
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id="improvement_planner",
                    model="local",
                    input_text=f"Planning from {len(self.ingest_assessment.all_findings)} findings",
                    output_text=f"{plan.total_items} roadmap items, {plan.ai_opportunities_count} AI opportunities",
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=duration_ms,
                    phase=phase.value,
                    checkpoint=checkpoint,
                    success=True
                )

            self._record_decision(
                agent_id="improvement_planner",
                phase=phase.value,
                decision=f"Plan complete: {plan.total_items} items",
                rationale=f"{plan.quick_wins} quick wins, {plan.ai_opportunities_count} AI opportunities"
            )

            self._advance_phase()
            return True, artifact

        elif phase == WorkflowPhase.INGEST_EXECUTION:
            # Execution phase - this is interactive, just mark as progressing
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id="execution_coordinator",
                    model="local",
                    input_text="Starting execution phase",
                    output_text="Execution phase started - interactive mode",
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=0,
                    phase=phase.value,
                    checkpoint=checkpoint,
                    success=True
                )

            self._record_decision(
                agent_id="execution_coordinator",
                phase=phase.value,
                decision="Execution phase started",
                rationale="Ready for interactive improvement execution"
            )

            # Don't auto-advance - execution is interactive
            return True, "Execution phase ready for interactive work"

        return False, f"Unknown ingest phase: {phase}"

    def _combine_assessment_results(self, assessor, project_config: dict):
        """Combine step results into a final AssessmentReport"""
        from core.assessment import AssessmentReport, CategoryScore
        from datetime import datetime

        # Create a placeholder for missing steps (used in Quick Test mode)
        def make_placeholder(category_name: str) -> CategoryScore:
            return CategoryScore(
                category=category_name,
                score=0,
                status="skipped",
                summary="Step was skipped (Quick Test mode)",
                findings=[],
                strengths=[],
                weaknesses=["Step was skipped (Quick Test mode)"]
            )

        # Get step results (CategoryScore objects) - use step_key (lowercase) not display names
        arch = self.state.step_results.get("architecture")
        quality = self.state.step_results.get("code_quality")
        debt = self.state.step_results.get("tech_debt")
        security = self.state.step_results.get("security")
        nav = self.state.step_results.get("ux_navigation")
        style = self.state.step_results.get("ux_styling")
        a11y = self.state.step_results.get("ux_accessibility")
        perf = self.state.step_results.get("performance")
        test = self.state.step_results.get("testing")
        docs = self.state.step_results.get("documentation")

        # Check for missing results - in Quick Test mode, use placeholders
        is_quick_test = self.state.test_steps is not None
        all_steps = [
            ("architecture", arch), ("code_quality", quality), ("tech_debt", debt),
            ("security", security), ("ux_navigation", nav), ("ux_styling", style),
            ("ux_accessibility", a11y), ("performance", perf), ("testing", test),
            ("documentation", docs)
        ]

        missing = []
        for name, val in all_steps:
            if val is None:
                missing.append(name)

        if missing and not is_quick_test:
            raise ValueError(f"Missing step results: {', '.join(missing)}. Available: {list(self.state.step_results.keys())}")

        # In Quick Test mode, fill in placeholders for missing steps
        if is_quick_test and missing:
            if arch is None: arch = make_placeholder("Architecture")
            if quality is None: quality = make_placeholder("Code Quality")
            if debt is None: debt = make_placeholder("Tech Debt")
            if security is None: security = make_placeholder("Security")
            if nav is None: nav = make_placeholder("UX Navigation")
            if style is None: style = make_placeholder("UX Styling")
            if a11y is None: a11y = make_placeholder("UX Accessibility")
            if perf is None: perf = make_placeholder("Performance")
            if test is None: test = make_placeholder("Testing")
            if docs is None: docs = make_placeholder("Documentation")

        # Calculate overall score (weighted)
        # In Quick Test mode, only average the tested steps
        if is_quick_test:
            tested_steps = self.state.test_steps
            weights = {
                "architecture": 0.12, "code_quality": 0.12, "tech_debt": 0.10,
                "security": 0.15, "ux_navigation": 0.10, "ux_styling": 0.08,
                "ux_accessibility": 0.08, "performance": 0.10, "testing": 0.10,
                "documentation": 0.05
            }
            step_scores = {
                "architecture": arch.score, "code_quality": quality.score, "tech_debt": debt.score,
                "security": security.score, "ux_navigation": nav.score, "ux_styling": style.score,
                "ux_accessibility": a11y.score, "performance": perf.score, "testing": test.score,
                "documentation": docs.score
            }
            # Calculate weighted average of only tested steps
            total_weight = sum(weights[s] for s in tested_steps)
            if total_weight > 0:
                overall = int(sum(step_scores[s] * weights[s] for s in tested_steps) / total_weight * 100 / 100)
            else:
                overall = 0
        else:
            overall = int(
                arch.score * 0.12 +
                quality.score * 0.12 +
                debt.score * 0.10 +
                security.score * 0.15 +
                nav.score * 0.10 +
                style.score * 0.08 +
                a11y.score * 0.08 +
                perf.score * 0.10 +
                test.score * 0.10 +
                docs.score * 0.05
            )

        # Determine status
        if overall >= 80:
            overall_status = "excellent"
        elif overall >= 60:
            overall_status = "good"
        elif overall >= 40:
            overall_status = "warning"
        else:
            overall_status = "critical"

        stats = project_config.get('stats', {})

        return AssessmentReport(
            project_name=project_config.get('project', {}).get('name', 'Unknown'),
            assessed_at=datetime.now().isoformat(),
            source_path=str(self.source_path),
            overall_score=overall,
            overall_status=overall_status,
            architecture=arch,
            code_quality=quality,
            tech_debt=debt,
            security=security,
            ux_navigation=nav,
            ux_styling=style,
            ux_accessibility=a11y,
            performance=perf,
            testing=test,
            documentation=docs,
            all_findings=assessor.findings,
            critical_count=sum(1 for f in assessor.findings if f.severity == 'critical'),
            high_count=sum(1 for f in assessor.findings if f.severity == 'high'),
            ai_fixable_count=sum(1 for f in assessor.findings if f.ai_can_fix),
            files_analyzed=stats.get('source_file_count', 0),
            lines_analyzed=stats.get('total_lines', 0),
        )

    def _build_task_for_phase(self, phase: WorkflowPhase) -> str:
        """Build the task prompt for a given phase"""
        feature = self.state.current_feature
        
        tasks = {
            WorkflowPhase.IDEATION: f"""Analyze this feature request and generate a comprehensive feature breakdown:

## Feature Request:
{feature}

## Your Task:
1. Identify the core value proposition
2. Break down into specific features and capabilities
3. Identify potential MVP scope
4. List technical considerations
5. Suggest comparable products/features for reference
""",
            
            WorkflowPhase.PRIORITIZATION: f"""Prioritize the features from ideation for MVP development:

## Feature Ideas:
{self.state.artifacts.get('ideation', feature)}

## Your Task:
1. Score each feature on value vs effort
2. Define clear MVP boundaries
3. Create prioritized backlog
4. Identify dependencies between features
5. Flag any scope risks
""",
            
            WorkflowPhase.REQUIREMENTS: f"""Create detailed user stories and requirements:

## Prioritized Features:
{self.state.artifacts.get('prioritization', feature)}

## Your Task:
1. Write user stories in standard format (As a... I want... So that...)
2. Define acceptance criteria for each story
3. Document business rules
4. Identify edge cases
5. Create requirements traceability
""",
            
            WorkflowPhase.DESIGN: f"""Design the user interface and experience:

## Requirements:
{self.state.artifacts.get('requirements', feature)}

## Your Task:
1. Create screen/component descriptions
2. Define user flows
3. Specify interaction patterns
4. Document design decisions
5. Ensure accessibility considerations
""",
            
            WorkflowPhase.ARCHITECTURE: f"""Design the system architecture:

## Requirements:
{self.state.artifacts.get('requirements', feature)}

## UI/UX Design:
{self.state.artifacts.get('design', '')}

## Your Task:
1. Define system architecture
2. Select appropriate design patterns
3. Design API contracts
4. Plan data models
5. Document architectural decisions (ADRs)
""",
            
            WorkflowPhase.DEVELOPMENT: f"""Implement the feature code:

## Architecture:
{self.state.artifacts.get('architecture', '')}

## Requirements:
{self.state.artifacts.get('requirements', feature)}

## Your Task:
1. Implement the feature according to specifications
2. Follow the architectural patterns defined
3. Include error handling
4. Add inline documentation
5. Follow coding standards
""",
            
            WorkflowPhase.SIMPLIFICATION: f"""Review and simplify the code:

## Code to Review:
{self.state.artifacts.get('development', '')}

## Your Task:
1. Identify opportunities for simplification
2. Extract reusable components
3. Remove duplication
4. Optimize performance where needed
5. Improve readability
""",
            
            WorkflowPhase.TESTING: f"""Write test scripts for the feature:

## Code:
{self.state.artifacts.get('simplification', self.state.artifacts.get('development', ''))}

## Requirements:
{self.state.artifacts.get('requirements', feature)}

## Your Task:
1. Write Playwright test scripts
2. Cover all acceptance criteria
3. Include edge case tests
4. Create test fixtures/data
5. Document test coverage
""",
            
            WorkflowPhase.DOCUMENTATION: f"""Create documentation for the feature:

## Code:
{self.state.artifacts.get('simplification', '')}

## Architecture:
{self.state.artifacts.get('architecture', '')}

## Your Task:
1. Write API documentation
2. Create usage examples
3. Document configuration options
4. Write troubleshooting guide
5. Update changelog
""",
            
            WorkflowPhase.DEPLOYMENT: f"""Prepare deployment configuration:

## Code:
{self.state.artifacts.get('simplification', '')}

## Documentation:
{self.state.artifacts.get('documentation', '')}

## Your Task:
1. Create/update CI/CD pipeline
2. Configure deployment scripts
3. Set up monitoring/alerting
4. Document deployment process
5. Create rollback plan
""",
        }
        
        return tasks.get(phase, f"Process the following feature: {feature}")
    
    def _get_artifact_for_gate(self, gate_phase: WorkflowPhase) -> str:
        """Get the artifact to be reviewed at a gate"""
        artifact_map = {
            WorkflowPhase.REQUIREMENTS_REVIEW: "requirements",
            WorkflowPhase.ARCHITECTURE_REVIEW: "architecture",
            WorkflowPhase.CODE_REVIEW: "development",
            WorkflowPhase.TEST_REVIEW: "testing",
            WorkflowPhase.RELEASE_REVIEW: "documentation",
            # Ingest workflow gates
            WorkflowPhase.INGEST_ASSESSMENT_REVIEW: "ingest_assessment",
            WorkflowPhase.INGEST_PLANNING_REVIEW: "ingest_planning",
        }

        artifact_key = artifact_map.get(gate_phase)
        return self.state.artifacts.get(artifact_key, "")
    
    def _get_agent_for_revision(self, gate_phase: WorkflowPhase) -> str:
        """Get the agent responsible for revising work that failed a gate"""
        revision_map = {
            WorkflowPhase.REQUIREMENTS_REVIEW: "business_analyst",
            WorkflowPhase.ARCHITECTURE_REVIEW: "solutions_architect",
            WorkflowPhase.CODE_REVIEW: "developer",
            WorkflowPhase.TEST_REVIEW: "test_writer",
            WorkflowPhase.RELEASE_REVIEW: "technical_writer",
            # Ingest gates - these use local analyzers, escalate to human
            WorkflowPhase.INGEST_ASSESSMENT_REVIEW: "codebase_assessor",
            WorkflowPhase.INGEST_PLANNING_REVIEW: "improvement_planner",
        }
        return revision_map.get(gate_phase, "developer")
    
    def _advance_phase(self):
        """Advance to the next phase in the workflow"""
        old_phase = self.state.current_phase
        new_phase = self.PHASE_TRANSITIONS.get(old_phase, WorkflowPhase.COMPLETE)
        
        self.state.current_phase = new_phase
        self.state.updated_at = datetime.now().isoformat()
        
        if self.on_phase_change:
            self.on_phase_change(old_phase, new_phase)
    
    def _record_decision(self, agent_id: str, phase: str, decision: str, rationale: str):
        """Record a decision in the workflow history"""
        self.state.decisions.append({
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "phase": phase,
            "decision": decision,
            "rationale": rationale[:500]  # Truncate long rationales
        })
    
    def _store_artifact_in_kb(self, phase: WorkflowPhase, content: str):
        """Store an artifact in the knowledge base"""
        doc_type_map = {
            WorkflowPhase.IDEATION: "requirements",
            WorkflowPhase.REQUIREMENTS: "requirements",
            WorkflowPhase.ARCHITECTURE: "architecture",
            WorkflowPhase.DEVELOPMENT: "code",
            WorkflowPhase.SIMPLIFICATION: "code",
            WorkflowPhase.TESTING: "test",
            WorkflowPhase.DOCUMENTATION: "documentation",
        }

        doc_type = doc_type_map.get(phase, "documentation")

        self.kb.add_document(
            content=content,
            doc_type=doc_type,
            metadata={
                "phase": phase.value,
                "feature": self.state.current_feature[:100]
            }
        )

    def _build_assessment_context(self, project_config: dict) -> AssessmentContext:
        """Build an AssessmentContext from project config for AI assessment."""
        features = project_config.get("features", {})
        tech = project_config.get("tech", {})
        source_path = Path(self.source_path)

        # Collect file list
        file_list = []
        file_contents = {}

        for p in source_path.rglob("*"):
            if p.is_file():
                rel_path = str(p.relative_to(source_path))
                # Skip common non-source directories
                skip_dirs = ["node_modules", ".git", "__pycache__", ".next", "dist", "build", ".venv", "venv"]
                if any(skip in rel_path for skip in skip_dirs):
                    continue
                file_list.append(rel_path)

                # Sample file contents for smaller source files
                if p.suffix in [".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".html", ".css"]:
                    try:
                        content = p.read_text(errors="ignore")
                        if len(content) < 50000:  # Only include files < 50KB
                            file_contents[rel_path] = content
                    except Exception:
                        pass

        return AssessmentContext(
            project_path=source_path,
            file_list=file_list,
            file_contents=file_contents,
            project_type=features.get("project_type", "unknown"),
            languages=tech.get("languages", []),
            frameworks=tech.get("frameworks", []),
            has_tests=features.get("has_tests", False),
            has_database=features.get("has_database", False),
            has_frontend=features.get("has_frontend", False),
            has_api=features.get("has_api", False)
        )

    def _step_result_to_category_score(self, step_result: StepResult):
        """Convert AI StepResult to CategoryScore-compatible object."""
        from core.assessment import CategoryScore, Finding as AssessmentFinding

        # Convert AI findings to assessment findings
        findings = []
        for f in step_result.findings:
            # Convert evidence list to string for assessment.Finding compatibility
            evidence_str = "; ".join(f.evidence) if f.evidence else ""

            findings.append(AssessmentFinding(
                id=f.rule_id,
                category=step_result.step_name,
                severity=f.severity,
                title=f.rule_name,
                description=f.description,
                location=f.evidence[0] if f.evidence else "",
                evidence=evidence_str,
                impact="",
                recommendation=f.recommendation,
                effort_hours=1.0,
                ai_can_fix=False
            ))

        return CategoryScore(
            category=step_result.step_name,
            score=step_result.score,
            status=step_result.status,
            summary=step_result.summary,
            strengths=step_result.strengths,
            weaknesses=step_result.weaknesses,
            findings=findings
        )

    async def run_full_workflow(self) -> tuple[bool, WorkflowState]:
        """
        Run the complete workflow from current phase to completion.
        Returns (success, final_state)
        """
        while self.state.current_phase not in (
            WorkflowPhase.COMPLETE,
            WorkflowPhase.FAILED,
            WorkflowPhase.ESCALATED
        ):
            success, output = await self.run_phase()
            
            if not success and self.state.current_phase not in (
                WorkflowPhase.FAILED,
                WorkflowPhase.ESCALATED
            ):
                # Non-escalated failure, might be retryable
                print(f"Phase {self.state.current_phase.value} had issues: {output}")
        
        success = self.state.current_phase == WorkflowPhase.COMPLETE
        return success, self.state


# Convenience function
def create_orchestrator(project_id: str, project_config_path: str | None = None) -> Orchestrator:
    """Create an orchestrator for a project"""
    return Orchestrator(
        project_id=project_id,
        project_config_path=project_config_path
    )


if __name__ == "__main__":
    # Example usage
    async def main():
        orchestrator = Orchestrator("test_project")
        
        # Start a feature
        state = orchestrator.start_feature("User authentication with email and password")
        
        print(f"Starting workflow for: {state.current_feature}")
        print(f"Initial phase: {state.current_phase.value}")
        
        # Run first phase as example
        success, output = await orchestrator.run_phase()
        print(f"Phase result: {'Success' if success else 'Failed'}")
        print(f"Output preview: {output[:200]}...")
    
    asyncio.run(main())
