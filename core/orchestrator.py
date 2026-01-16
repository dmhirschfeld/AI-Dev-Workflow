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
            "updated_at": self.updated_at
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
            updated_at=data.get("updated_at", datetime.now().isoformat())
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

        # Callbacks
        self.on_phase_change: Callable[[WorkflowPhase, WorkflowPhase], None] | None = None
        self.on_gate_result: Callable[[GateResult], None] | None = None
        self.on_agent_response: Callable[[AgentResponse], None] | None = None
        self.on_escalation: Callable[[str, WorkflowState], None] | None = None
        self.on_progress: Callable[[str, int, int], None] | None = None  # (step_name, current, total)

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

    def start_ingest(self, source_path: str, description: str = "") -> WorkflowState:
        """Start an ingest workflow for analyzing existing codebase"""
        self.source_path = source_path
        self.state = WorkflowState(
            project_id=self.project_id,
            current_phase=WorkflowPhase.INGEST_ASSESSMENT,
            current_feature=description or f"Analyzing {source_path}"
        )
        # Store ingest-specific data
        self.ingest_assessment = None
        self.ingest_plan = None
        return self.state

    def load_state(self, state_dict: dict) -> WorkflowState:
        """Load existing workflow state"""
        self.state = WorkflowState.from_dict(state_dict)
        return self.state

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
                self.audit_logger.log_gate_vote(
                    gate_id=result.gate_id,
                    voters=[v.voter_id for v in result.votes],
                    votes_for=sum(1 for v in result.votes if v.approved),
                    votes_against=sum(1 for v in result.votes if not v.approved),
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

    async def _run_ingest_phase(self) -> tuple[bool, str]:
        """Run an ingest phase using local analyzers (not AI agents)"""
        import time
        from dataclasses import asdict

        phase = self.state.current_phase
        checkpoint = f"CP-{phase.value.upper().replace('_', '-')}"

        if phase == WorkflowPhase.INGEST_ASSESSMENT:
            # Run codebase assessment
            from core.assessment import CodebaseAssessor

            start_time = time.perf_counter()

            # Get project config if available
            project_config = {}
            config_path = self.project_dir / "config.yaml"
            if config_path.exists():
                import yaml
                with open(config_path) as f:
                    project_config = yaml.safe_load(f) or {}

            # Run assessment with progress callback
            assessor = CodebaseAssessor(
                self.source_path,
                project_config,
                on_progress=self.on_progress
            )
            assessment = assessor.assess()
            self.ingest_assessment = assessment

            duration_ms = int((time.perf_counter() - start_time) * 1000)

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
                    duration_ms=duration_ms,
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
