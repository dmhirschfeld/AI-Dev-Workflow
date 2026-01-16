"""
Task Decomposition Module

Breaks architecture into atomic, implementable tasks for Sonnet.
Each task should be:
- Single responsibility
- Clear acceptance criteria
- Estimable (S/M/L)
- Independently testable

Task sizes:
- S (Small): < 50 lines, single file, < 30 min
- M (Medium): 50-200 lines, 1-3 files, 30-90 min  
- L (Large): Should be broken down further
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import yaml
import json
from datetime import datetime


class TaskSize(Enum):
    SMALL = "S"      # < 50 lines, single file
    MEDIUM = "M"     # 50-200 lines, 1-3 files
    LARGE = "L"      # Should be decomposed further


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCategory(Enum):
    MODEL = "model"              # Data models, schemas
    API = "api"                  # Endpoints, routes
    SERVICE = "service"         # Business logic
    INTEGRATION = "integration"  # External services
    UI = "ui"                   # Frontend components
    DATABASE = "database"       # Migrations, queries
    CONFIG = "config"           # Configuration, env
    TEST = "test"               # Test files
    DOCS = "docs"               # Documentation
    INFRA = "infra"             # DevOps, deployment


@dataclass
class ImplementationTask:
    """Single atomic implementation task"""
    id: str
    title: str
    description: str
    category: TaskCategory
    size: TaskSize
    
    # What files will be created/modified
    target_files: List[str] = field(default_factory=list)
    
    # Acceptance criteria - specific, testable
    acceptance_criteria: List[str] = field(default_factory=list)
    
    # Dependencies on other tasks
    depends_on: List[str] = field(default_factory=list)
    
    # Technical notes for developer
    implementation_notes: str = ""
    
    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    
    # Assigned agent
    assigned_to: str = "developer"
    
    # Results after completion
    result_files: List[str] = field(default_factory=list)
    result_summary: str = ""
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "size": self.size.value,
            "target_files": self.target_files,
            "acceptance_criteria": self.acceptance_criteria,
            "depends_on": self.depends_on,
            "implementation_notes": self.implementation_notes,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "result_files": self.result_files,
            "result_summary": self.result_summary,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImplementationTask":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            category=TaskCategory(data.get("category", "service")),
            size=TaskSize(data.get("size", "M")),
            target_files=data.get("target_files", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            depends_on=data.get("depends_on", []),
            implementation_notes=data.get("implementation_notes", ""),
            status=TaskStatus(data.get("status", "pending")),
            assigned_to=data.get("assigned_to", "developer"),
            result_files=data.get("result_files", []),
            result_summary=data.get("result_summary", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )
    
    def to_prompt(self) -> str:
        """Format task for developer agent prompt"""
        lines = [
            f"## Task: {self.id}",
            f"**{self.title}**",
            "",
            self.description,
            "",
            f"**Category:** {self.category.value}",
            f"**Size:** {self.size.value}",
            "",
        ]
        
        if self.target_files:
            lines.append("**Files to create/modify:**")
            for f in self.target_files:
                lines.append(f"- `{f}`")
            lines.append("")
        
        if self.acceptance_criteria:
            lines.append("**Acceptance Criteria:**")
            for i, ac in enumerate(self.acceptance_criteria, 1):
                lines.append(f"{i}. {ac}")
            lines.append("")
        
        if self.implementation_notes:
            lines.append("**Implementation Notes:**")
            lines.append(self.implementation_notes)
            lines.append("")
        
        return "\n".join(lines)


@dataclass
class TaskPlan:
    """Collection of tasks for a feature"""
    feature_id: str
    feature_name: str
    description: str
    tasks: List[ImplementationTask] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_task(self, task: ImplementationTask):
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> Optional[ImplementationTask]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_ready_tasks(self) -> List[ImplementationTask]:
        """Get tasks that are ready to execute (dependencies met)"""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready = []
        
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check all dependencies are completed
            deps_met = all(dep in completed_ids for dep in task.depends_on)
            if deps_met:
                ready.append(task)
        
        return ready
    
    def get_next_task(self) -> Optional[ImplementationTask]:
        """Get single next task to execute"""
        ready = self.get_ready_tasks()
        if not ready:
            return None
        
        # Prioritize by: size (S first), then category order
        priority = {
            TaskCategory.DATABASE: 0,
            TaskCategory.MODEL: 1,
            TaskCategory.SERVICE: 2,
            TaskCategory.API: 3,
            TaskCategory.INTEGRATION: 4,
            TaskCategory.UI: 5,
            TaskCategory.CONFIG: 6,
            TaskCategory.TEST: 7,
            TaskCategory.DOCS: 8,
            TaskCategory.INFRA: 9,
        }
        
        def sort_key(t):
            size_order = {"S": 0, "M": 1, "L": 2}
            return (size_order.get(t.size.value, 1), priority.get(t.category, 5))
        
        ready.sort(key=sort_key)
        return ready[0]
    
    def get_blocked_tasks(self) -> List[ImplementationTask]:
        """Get tasks blocked by failed dependencies"""
        failed_ids = {t.id for t in self.tasks if t.status == TaskStatus.FAILED}
        blocked = []
        
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check if any dependency failed
            if any(dep in failed_ids for dep in task.depends_on):
                blocked.append(task)
        
        return blocked
    
    def get_progress(self) -> Dict[str, int]:
        """Get task completion progress"""
        total = len(self.tasks)
        by_status = {}
        
        for task in self.tasks:
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total": total,
            "completed": by_status.get("completed", 0),
            "in_progress": by_status.get("in_progress", 0),
            "pending": by_status.get("pending", 0),
            "failed": by_status.get("failed", 0),
            "blocked": len(self.get_blocked_tasks()),
            "percent_complete": round(by_status.get("completed", 0) / total * 100) if total else 0,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        plan = cls(
            feature_id=data["feature_id"],
            feature_name=data["feature_name"],
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
        
        for task_data in data.get("tasks", []):
            plan.add_task(ImplementationTask.from_dict(task_data))
        
        return plan
    
    def save(self, filepath: str):
        """Save task plan to file"""
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, filepath: str) -> "TaskPlan":
        """Load task plan from file"""
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def format_summary(self) -> str:
        """Format plan summary for display"""
        progress = self.get_progress()
        
        lines = [
            f"{'═' * 60}",
            f"  TASK PLAN: {self.feature_name}",
            f"{'═' * 60}",
            "",
            f"Progress: {progress['completed']}/{progress['total']} tasks ({progress['percent_complete']}%)",
            "",
        ]
        
        # Group by status
        by_status = {}
        for task in self.tasks:
            status = task.status.value
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(task)
        
        status_icons = {
            "completed": "✅",
            "in_progress": "🔄",
            "pending": "⏳",
            "failed": "❌",
            "blocked": "🚫",
            "in_review": "👀",
        }
        
        for status in ["in_progress", "pending", "completed", "failed"]:
            tasks = by_status.get(status, [])
            if tasks:
                icon = status_icons.get(status, "•")
                lines.append(f"{icon} {status.upper()} ({len(tasks)})")
                for task in tasks[:5]:  # Show first 5
                    lines.append(f"   [{task.id}] {task.title} ({task.size.value})")
                if len(tasks) > 5:
                    lines.append(f"   ... and {len(tasks) - 5} more")
                lines.append("")
        
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# TASK DECOMPOSITION PROMPT
# ════════════════════════════════════════════════════════════

DECOMPOSITION_PROMPT = """You are a senior software architect breaking down a feature into atomic implementation tasks.

## Rules for Task Decomposition

1. **Atomic Tasks**: Each task should be completable in 30-90 minutes
2. **Single Responsibility**: One task = one thing (one model, one endpoint, one component)
3. **Clear Boundaries**: Task should not depend on decisions made during implementation
4. **Testable**: Each task should have clear acceptance criteria
5. **Size Limits**:
   - S (Small): < 50 lines, single file, < 30 min
   - M (Medium): 50-200 lines, 1-3 files, 30-90 min
   - L (Large): Break this down further!

## Task Categories

- `database`: Migrations, schema changes
- `model`: Data models, entities
- `service`: Business logic, use cases
- `api`: Endpoints, routes, controllers
- `integration`: External service connections
- `ui`: Frontend components
- `config`: Configuration, environment
- `test`: Test files (usually paired with implementation)
- `docs`: Documentation
- `infra`: DevOps, deployment

## Output Format

For each task, provide:

```yaml
- id: FEATURE-001
  title: Short descriptive title
  description: |
    What this task accomplishes.
    Be specific about inputs/outputs.
  category: model
  size: S
  target_files:
    - src/models/user.py
  acceptance_criteria:
    - User model has email, password_hash, created_at fields
    - Email field has unique constraint
    - Password is hashed before storage
  depends_on: []  # List of task IDs this depends on
  implementation_notes: |
    Optional technical guidance.
    Reference architectural decisions.
```

## Architecture Context

{architecture}

## Feature to Decompose

{feature_description}

## Generate Task Plan

Create a complete task plan with properly ordered, atomic tasks.
Start with database/models, then services, then API, then tests.
Ensure dependencies form a valid DAG (no cycles).
"""


def generate_decomposition_prompt(architecture: str, feature_description: str) -> str:
    """Generate prompt for task decomposition"""
    return DECOMPOSITION_PROMPT.format(
        architecture=architecture,
        feature_description=feature_description,
    )


def parse_task_yaml(yaml_content: str, feature_id: str) -> TaskPlan:
    """Parse YAML task list from LLM response"""
    # Extract YAML block if wrapped in markdown
    if "```yaml" in yaml_content:
        start = yaml_content.find("```yaml") + 7
        end = yaml_content.find("```", start)
        yaml_content = yaml_content[start:end]
    elif "```" in yaml_content:
        start = yaml_content.find("```") + 3
        end = yaml_content.find("```", start)
        yaml_content = yaml_content[start:end]
    
    try:
        tasks_data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse task YAML: {e}")
    
    # Handle if wrapped in a key
    if isinstance(tasks_data, dict):
        if "tasks" in tasks_data:
            tasks_data = tasks_data["tasks"]
        elif "implementation_tasks" in tasks_data:
            tasks_data = tasks_data["implementation_tasks"]
    
    if not isinstance(tasks_data, list):
        raise ValueError("Expected list of tasks")
    
    plan = TaskPlan(
        feature_id=feature_id,
        feature_name=feature_id,
        description="",
    )
    
    for task_data in tasks_data:
        # Normalize category
        category_str = task_data.get("category", "service").lower()
        try:
            category = TaskCategory(category_str)
        except ValueError:
            category = TaskCategory.SERVICE
        
        # Normalize size
        size_str = task_data.get("size", "M").upper()
        try:
            size = TaskSize(size_str)
        except ValueError:
            size = TaskSize.MEDIUM
        
        task = ImplementationTask(
            id=task_data.get("id", f"{feature_id}-{len(plan.tasks)+1:03d}"),
            title=task_data.get("title", "Untitled Task"),
            description=task_data.get("description", ""),
            category=category,
            size=size,
            target_files=task_data.get("target_files", []),
            acceptance_criteria=task_data.get("acceptance_criteria", []),
            depends_on=task_data.get("depends_on", []),
            implementation_notes=task_data.get("implementation_notes", ""),
        )
        
        plan.add_task(task)
    
    return plan


# ════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════

def validate_task_plan(plan: TaskPlan) -> List[str]:
    """Validate task plan, return list of issues"""
    issues = []
    
    task_ids = {t.id for t in plan.tasks}
    
    for task in plan.tasks:
        # Check for large tasks
        if task.size == TaskSize.LARGE:
            issues.append(f"Task {task.id} is size L - should be decomposed further")
        
        # Check dependencies exist
        for dep in task.depends_on:
            if dep not in task_ids:
                issues.append(f"Task {task.id} depends on unknown task: {dep}")
        
        # Check for missing acceptance criteria
        if not task.acceptance_criteria:
            issues.append(f"Task {task.id} has no acceptance criteria")
        
        # Check for self-dependency
        if task.id in task.depends_on:
            issues.append(f"Task {task.id} depends on itself")
    
    # Check for circular dependencies
    def has_cycle(task_id: str, visited: set, path: set) -> bool:
        if task_id in path:
            return True
        if task_id in visited:
            return False
        
        visited.add(task_id)
        path.add(task_id)
        
        task = plan.get_task(task_id)
        if task:
            for dep in task.depends_on:
                if has_cycle(dep, visited, path):
                    return True
        
        path.remove(task_id)
        return False
    
    visited = set()
    for task in plan.tasks:
        if has_cycle(task.id, visited, set()):
            issues.append(f"Circular dependency detected involving task {task.id}")
            break
    
    return issues
