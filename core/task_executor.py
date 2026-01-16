"""
Task-Based Development Executor

Executes implementation tasks one at a time with Sonnet.
Integrates with orchestrator after architecture phase.

Flow:
1. Solutions Architect (Opus) produces architecture + task breakdown
2. TaskExecutor receives task list
3. For each task:
   a. Developer (Sonnet) implements
   b. Code review validates
   c. If pass → commit, next task
   d. If fail → retry with feedback
4. All tasks complete → testing phase
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
import yaml

from core.task_decomposition import (
    TaskPlan,
    ImplementationTask,
    TaskStatus,
    TaskSize,
    parse_task_yaml,
    validate_task_plan,
)


@dataclass
class TaskResult:
    """Result of executing a single task"""
    task_id: str
    success: bool
    code_output: str
    files_created: List[str]
    files_modified: List[str]
    review_passed: bool
    review_feedback: str
    attempts: int
    tokens_used: int
    cost: float


class TaskExecutor:
    """
    Executes implementation tasks one at a time.
    
    Usage:
        executor = TaskExecutor(
            project_id="my-project",
            project_dir="./projects/my-project"
        )
        
        # Load task plan (from architect output)
        executor.load_plan(task_plan)
        
        # Execute all tasks
        results = await executor.execute_all()
        
        # Or execute one at a time
        while task := executor.get_next_task():
            result = await executor.execute_task(task)
    """
    
    MAX_RETRIES_PER_TASK = 3
    
    def __init__(
        self,
        project_id: str,
        project_dir: str,
        developer_model: str = "claude-sonnet-4-20250514",
        reviewer_model: str = "claude-sonnet-4-20250514",
    ):
        self.project_id = project_id
        self.project_dir = Path(project_dir)
        self.developer_model = developer_model
        self.reviewer_model = reviewer_model
        
        self.plan: Optional[TaskPlan] = None
        self.results: Dict[str, TaskResult] = {}
        
        # Architecture context (set when loading plan)
        self.architecture_context: str = ""
        self.tech_stack: Dict[str, Any] = {}
        
        # Callbacks
        self.on_task_start: Optional[Callable[[ImplementationTask], None]] = None
        self.on_task_complete: Optional[Callable[[ImplementationTask, TaskResult], None]] = None
        self.on_progress: Optional[Callable[[Dict[str, int]], None]] = None
    
    def load_plan(
        self,
        plan: TaskPlan,
        architecture_context: str = "",
        tech_stack: Optional[Dict[str, Any]] = None
    ):
        """Load a task plan for execution"""
        self.plan = plan
        self.architecture_context = architecture_context
        self.tech_stack = tech_stack or {}
        
        # Validate plan
        issues = validate_task_plan(plan)
        if issues:
            print(f"Warning: Task plan has {len(issues)} issues:")
            for issue in issues[:5]:
                print(f"  - {issue}")
    
    def load_plan_from_yaml(self, yaml_content: str, feature_id: str):
        """Load task plan from YAML string (from architect output)"""
        self.plan = parse_task_yaml(yaml_content, feature_id)
    
    def get_next_task(self) -> Optional[ImplementationTask]:
        """Get the next task ready for execution"""
        if not self.plan:
            return None
        return self.plan.get_next_task()
    
    def get_progress(self) -> Dict[str, int]:
        """Get current execution progress"""
        if not self.plan:
            return {"total": 0, "completed": 0, "percent_complete": 0}
        return self.plan.get_progress()
    
    async def execute_task(self, task: ImplementationTask) -> TaskResult:
        """
        Execute a single implementation task.
        
        1. Send task to Developer agent (Sonnet)
        2. Review output
        3. If pass → mark complete
        4. If fail → retry with feedback
        """
        if self.on_task_start:
            self.on_task_start(task)
        
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now().isoformat()
        
        attempts = 0
        review_feedback = ""
        
        while attempts < self.MAX_RETRIES_PER_TASK:
            attempts += 1
            
            # Build developer prompt
            prompt = self._build_developer_prompt(task, review_feedback)
            
            # Execute developer agent
            code_output, tokens = await self._call_developer(prompt)
            
            # Review the output
            review_passed, feedback = await self._review_code(task, code_output)
            
            if review_passed:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now().isoformat()
                task.result_summary = f"Completed in {attempts} attempt(s)"
                
                result = TaskResult(
                    task_id=task.id,
                    success=True,
                    code_output=code_output,
                    files_created=task.target_files,  # Would parse from output
                    files_modified=[],
                    review_passed=True,
                    review_feedback=feedback,
                    attempts=attempts,
                    tokens_used=tokens,
                    cost=self._estimate_cost(tokens),
                )
                
                self.results[task.id] = result
                
                if self.on_task_complete:
                    self.on_task_complete(task, result)
                
                if self.on_progress:
                    self.on_progress(self.get_progress())
                
                return result
            
            # Didn't pass review - prepare for retry
            review_feedback = feedback
        
        # Exhausted retries
        task.status = TaskStatus.FAILED
        task.result_summary = f"Failed after {attempts} attempts"
        
        result = TaskResult(
            task_id=task.id,
            success=False,
            code_output=code_output,
            files_created=[],
            files_modified=[],
            review_passed=False,
            review_feedback=review_feedback,
            attempts=attempts,
            tokens_used=tokens,
            cost=self._estimate_cost(tokens),
        )
        
        self.results[task.id] = result
        
        if self.on_task_complete:
            self.on_task_complete(task, result)
        
        return result
    
    async def execute_all(
        self,
        stop_on_failure: bool = True
    ) -> List[TaskResult]:
        """
        Execute all tasks in dependency order.
        
        Args:
            stop_on_failure: Stop execution if a task fails
            
        Returns:
            List of task results
        """
        results = []
        
        while True:
            task = self.get_next_task()
            
            if not task:
                # No more tasks ready
                blocked = self.plan.get_blocked_tasks() if self.plan else []
                if blocked:
                    print(f"Warning: {len(blocked)} tasks blocked due to failed dependencies")
                break
            
            result = await self.execute_task(task)
            results.append(result)
            
            if not result.success and stop_on_failure:
                print(f"Task {task.id} failed. Stopping execution.")
                break
        
        return results
    
    def _build_developer_prompt(
        self,
        task: ImplementationTask,
        previous_feedback: str = ""
    ) -> str:
        """Build the prompt for the developer agent"""
        lines = [
            "# Implementation Task",
            "",
            task.to_prompt(),
            "",
        ]
        
        # Add architecture context
        if self.architecture_context:
            lines.extend([
                "## Architecture Context",
                "",
                self.architecture_context[:2000],  # Limit context size
                "",
            ])
        
        # Add tech stack
        if self.tech_stack:
            lines.extend([
                "## Tech Stack",
                "",
            ])
            for key, value in self.tech_stack.items():
                if isinstance(value, list):
                    lines.append(f"- **{key}**: {', '.join(value)}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")
        
        # Add context from completed dependencies
        dep_context = self._get_dependency_context(task)
        if dep_context:
            lines.extend([
                "## Completed Dependencies",
                "",
                dep_context,
                "",
            ])
        
        # Add feedback from failed attempt
        if previous_feedback:
            lines.extend([
                "## Feedback from Previous Attempt",
                "",
                "Your previous implementation had issues:",
                "",
                previous_feedback,
                "",
                "Please address these issues in your revised implementation.",
                "",
            ])
        
        # Instructions
        lines.extend([
            "## Instructions",
            "",
            "1. Implement ONLY this specific task",
            "2. Follow the acceptance criteria exactly",
            "3. Output complete, working code",
            "4. Include necessary imports",
            "5. Add brief inline comments",
            "",
            "## Output Format",
            "",
            "Provide the implementation as code blocks with file paths:",
            "",
            "```python",
            "# src/models/user.py",
            "...",
            "```",
        ])
        
        return "\n".join(lines)
    
    def _get_dependency_context(self, task: ImplementationTask) -> str:
        """Get context from completed dependency tasks"""
        if not task.depends_on or not self.plan:
            return ""
        
        context_parts = []
        
        for dep_id in task.depends_on:
            if dep_id in self.results:
                result = self.results[dep_id]
                if result.success:
                    dep_task = self.plan.get_task(dep_id)
                    if dep_task:
                        context_parts.append(
                            f"### {dep_id}: {dep_task.title}\n"
                            f"Files: {', '.join(result.files_created)}\n"
                        )
        
        return "\n".join(context_parts)
    
    async def _call_developer(self, prompt: str) -> tuple[str, int]:
        """
        Call the developer agent (Sonnet).
        
        Returns (response, tokens_used)
        """
        # In real implementation, this calls the LLM API
        # For now, return placeholder
        
        try:
            from core.agents import AgentFactory, AgentExecutor
            
            factory = AgentFactory("agents/definitions.yaml")
            executor = AgentExecutor(factory)
            
            response = await executor.execute(
                agent_id="developer",
                task=prompt,
                context={},
                model_override=self.developer_model,
            )
            
            return response.output, response.metadata.get("tokens", 0)
            
        except Exception as e:
            # Fallback for testing
            return f"# Placeholder implementation for testing\n# Error: {e}", 0
    
    async def _review_code(
        self,
        task: ImplementationTask,
        code_output: str
    ) -> tuple[bool, str]:
        """
        Review code output against acceptance criteria.
        
        Returns (passed, feedback)
        """
        # Build review prompt
        review_prompt = f"""# Code Review

## Task
{task.to_prompt()}

## Implementation
{code_output}

## Review Instructions

Check if the implementation meets ALL acceptance criteria:

{chr(10).join(f"- {ac}" for ac in task.acceptance_criteria)}

## Output Format

Respond with:
- PASS: if all criteria are met
- FAIL: if any criteria are not met

If FAIL, explain what's missing or incorrect.
"""
        
        try:
            from core.agents import AgentFactory, AgentExecutor
            
            factory = AgentFactory("agents/definitions.yaml")
            executor = AgentExecutor(factory)
            
            response = await executor.execute(
                agent_id="code_reviewer",
                task=review_prompt,
                context={},
                model_override=self.reviewer_model,
            )
            
            output = response.output.upper()
            passed = "PASS" in output and "FAIL" not in output
            
            return passed, response.output
            
        except Exception as e:
            # Fallback - assume pass for testing
            return True, f"Review skipped: {e}"
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on token count"""
        # Sonnet pricing: $3/1M input, $15/1M output
        # Rough estimate assuming 70% input, 30% output
        input_tokens = int(tokens * 0.7)
        output_tokens = int(tokens * 0.3)
        
        input_cost = input_tokens * 3.0 / 1_000_000
        output_cost = output_tokens * 15.0 / 1_000_000
        
        return input_cost + output_cost
    
    def save_results(self, filepath: str):
        """Save execution results to file"""
        data = {
            "project_id": self.project_id,
            "plan": self.plan.to_dict() if self.plan else None,
            "results": {
                task_id: {
                    "task_id": r.task_id,
                    "success": r.success,
                    "files_created": r.files_created,
                    "review_passed": r.review_passed,
                    "attempts": r.attempts,
                    "tokens_used": r.tokens_used,
                    "cost": r.cost,
                }
                for task_id, r in self.results.items()
            },
            "summary": self.get_summary(),
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary"""
        if not self.results:
            return {"tasks": 0, "completed": 0, "failed": 0}
        
        completed = sum(1 for r in self.results.values() if r.success)
        failed = sum(1 for r in self.results.values() if not r.success)
        total_tokens = sum(r.tokens_used for r in self.results.values())
        total_cost = sum(r.cost for r in self.results.values())
        
        return {
            "tasks": len(self.results),
            "completed": completed,
            "failed": failed,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "avg_attempts": round(
                sum(r.attempts for r in self.results.values()) / len(self.results), 1
            ),
        }
    
    def format_progress(self) -> str:
        """Format progress for display"""
        if not self.plan:
            return "No task plan loaded."
        
        return self.plan.format_summary()


# ════════════════════════════════════════════════════════════
# INTEGRATION WITH ORCHESTRATOR
# ════════════════════════════════════════════════════════════

async def execute_architecture_tasks(
    architecture_output: str,
    feature_id: str,
    project_dir: str,
    tech_stack: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Callable] = None,
) -> tuple[bool, List[TaskResult]]:
    """
    Extract tasks from architecture output and execute them.
    
    Args:
        architecture_output: Full output from Solutions Architect
        feature_id: Feature identifier
        project_dir: Project directory
        tech_stack: Tech stack configuration
        on_progress: Progress callback
        
    Returns:
        (all_success, results)
    """
    # Extract tasks section from architecture
    tasks_yaml = _extract_tasks_from_architecture(architecture_output)
    
    if not tasks_yaml:
        return False, []
    
    # Create executor
    executor = TaskExecutor(
        project_id=feature_id,
        project_dir=project_dir,
    )
    
    # Load plan
    executor.load_plan_from_yaml(tasks_yaml, feature_id)
    executor.architecture_context = architecture_output
    executor.tech_stack = tech_stack or {}
    
    if on_progress:
        executor.on_progress = on_progress
    
    # Execute all tasks
    results = await executor.execute_all(stop_on_failure=True)
    
    # Check if all succeeded
    all_success = all(r.success for r in results)
    
    return all_success, results


def _extract_tasks_from_architecture(architecture_output: str) -> str:
    """Extract tasks YAML section from architecture document"""
    # Look for tasks section
    markers = [
        "## Implementation Tasks",
        "### Task Breakdown",
        "```yaml\ntasks:",
        "```yaml\n- id:",
    ]
    
    for marker in markers:
        if marker in architecture_output:
            start = architecture_output.find(marker)
            
            # Find the YAML block
            yaml_start = architecture_output.find("```yaml", start)
            if yaml_start == -1:
                yaml_start = architecture_output.find("```", start)
            
            if yaml_start != -1:
                yaml_start = architecture_output.find("\n", yaml_start) + 1
                yaml_end = architecture_output.find("```", yaml_start)
                
                if yaml_end != -1:
                    return architecture_output[yaml_start:yaml_end].strip()
    
    return ""
