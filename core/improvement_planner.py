"""
Improvement Planner Module

Creates and executes improvement plans for codebases.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import yaml


@dataclass
class ImprovementTask:
    """A single improvement task"""
    id: str
    category: str
    title: str
    description: str
    priority: int  # 1=highest
    effort: str
    status: str = "pending"  # pending, in_progress, completed, skipped
    agent: str = ""  # Which agent handles this
    result: str = ""


@dataclass
class ImprovementPlan:
    """Complete improvement plan"""
    project_name: str
    created_at: str
    target_score: int
    current_score: int
    phases: list
    total_tasks: int
    total_effort: str


class ImprovementPlanner:
    """Creates and manages improvement plans"""
    
    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
    
    def create_plan(
        self,
        project_name: str,
        health_report: dict,
        improvement_type: str = "all"
    ) -> ImprovementPlan:
        """
        Create an improvement plan from a health report.
        
        Args:
            project_name: Name of the project
            health_report: Health report dictionary
            improvement_type: Type of improvements (all, critical, security, tests, etc.)
            
        Returns:
            ImprovementPlan
        """
        tasks = []
        task_id = 1
        
        # Extract issues from health report
        critical_issues = health_report.get("critical_issues", [])
        high_issues = health_report.get("high_issues", [])
        categories = health_report.get("categories", [])
        
        # Process critical issues
        for issue in critical_issues:
            if self._should_include(issue, improvement_type):
                tasks.append(ImprovementTask(
                    id=f"IMP-{task_id:03d}",
                    category=issue.get("category", "general"),
                    title=issue.get("title", ""),
                    description=issue.get("description", ""),
                    priority=1,
                    effort=issue.get("effort", "unknown"),
                    agent=self._get_agent_for_category(issue.get("category"))
                ))
                task_id += 1
        
        # Process high issues
        for issue in high_issues:
            if self._should_include(issue, improvement_type):
                tasks.append(ImprovementTask(
                    id=f"IMP-{task_id:03d}",
                    category=issue.get("category", "general"),
                    title=issue.get("title", ""),
                    description=issue.get("description", ""),
                    priority=2,
                    effort=issue.get("effort", "unknown"),
                    agent=self._get_agent_for_category(issue.get("category"))
                ))
                task_id += 1
        
        # Process recommendations from categories
        for cat in categories:
            recommendations = cat.get("recommendations", [])
            for rec in recommendations:
                if self._should_include({"category": cat.get("name", "").lower()}, improvement_type):
                    tasks.append(ImprovementTask(
                        id=f"IMP-{task_id:03d}",
                        category=cat.get("name", "").lower().replace(" ", "_"),
                        title=rec,
                        description=rec,
                        priority=3,
                        effort="2-4 hours",
                        agent=self._get_agent_for_category(cat.get("name", "").lower())
                    ))
                    task_id += 1
        
        # Sort by priority
        tasks.sort(key=lambda t: t.priority)
        
        # Group into phases
        phases = self._create_phases(tasks)
        
        # Calculate total effort
        total_effort = self._calculate_total_effort(tasks)
        
        plan = ImprovementPlan(
            project_name=project_name,
            created_at=datetime.now().isoformat(),
            target_score=80,
            current_score=health_report.get("overall_score", 0),
            phases=[{
                "name": p["name"],
                "description": p["description"],
                "tasks": [asdict(t) for t in p["tasks"]],
                "effort": p["effort"]
            } for p in phases],
            total_tasks=len(tasks),
            total_effort=total_effort
        )
        
        # Save plan
        self._save_plan(project_name, plan)
        
        return plan
    
    def _should_include(self, issue: dict, improvement_type: str) -> bool:
        """Check if issue should be included based on improvement type"""
        if improvement_type == "all":
            return True
        
        category = issue.get("category", "").lower()
        
        type_mapping = {
            "critical": lambda c: issue.get("severity") == "critical",
            "security": lambda c: c in ["security"],
            "tests": lambda c: c in ["test_coverage", "tests", "testing"],
            "dependencies": lambda c: c in ["dependencies"],
            "code_quality": lambda c: c in ["code_quality", "code"],
            "documentation": lambda c: c in ["documentation", "docs"],
            "architecture": lambda c: c in ["architecture"],
        }
        
        check = type_mapping.get(improvement_type, lambda c: True)
        return check(category)
    
    def _get_agent_for_category(self, category: str) -> str:
        """Get the appropriate agent for a category"""
        category = category.lower().replace(" ", "_")
        
        agent_mapping = {
            "security": "security_specialist",
            "test_coverage": "test_writer",
            "tests": "test_writer",
            "code_quality": "code_reviewer",
            "dependencies": "modernization_specialist",
            "documentation": "technical_writer",
            "architecture": "solutions_architect",
        }
        
        return agent_mapping.get(category, "developer")
    
    def _create_phases(self, tasks: list) -> list:
        """Group tasks into phases"""
        phases = []
        
        # Phase 1: Critical fixes
        critical_tasks = [t for t in tasks if t.priority == 1]
        if critical_tasks:
            phases.append({
                "name": "Phase 1: Critical Fixes",
                "description": "Address critical issues immediately",
                "tasks": critical_tasks,
                "effort": self._calculate_total_effort(critical_tasks)
            })
        
        # Phase 2: High priority
        high_tasks = [t for t in tasks if t.priority == 2]
        if high_tasks:
            phases.append({
                "name": "Phase 2: High Priority",
                "description": "Fix high-impact issues",
                "tasks": high_tasks,
                "effort": self._calculate_total_effort(high_tasks)
            })
        
        # Phase 3: Improvements
        medium_tasks = [t for t in tasks if t.priority == 3]
        if medium_tasks:
            phases.append({
                "name": "Phase 3: Improvements",
                "description": "General improvements and recommendations",
                "tasks": medium_tasks,
                "effort": self._calculate_total_effort(medium_tasks)
            })
        
        return phases
    
    def _calculate_total_effort(self, tasks: list) -> str:
        """Calculate total effort for a list of tasks"""
        total_hours = 0
        
        for task in tasks:
            effort = task.effort if isinstance(task, ImprovementTask) else task.get("effort", "")
            try:
                if "-" in effort:
                    parts = effort.lower().replace("hours", "").replace("hour", "").strip()
                    low, high = parts.split("-")
                    total_hours += (float(low.strip()) + float(high.strip())) / 2
                elif "hour" in effort.lower():
                    num = effort.lower().replace("hours", "").replace("hour", "").strip()
                    total_hours += float(num)
                elif "minute" in effort.lower():
                    total_hours += 0.5
                else:
                    total_hours += 2  # Default
            except:
                total_hours += 2
        
        if total_hours <= 8:
            return f"{int(total_hours)} hours"
        elif total_hours <= 40:
            return f"{int(total_hours)}-{int(total_hours * 1.2)} hours"
        else:
            weeks = total_hours / 40
            return f"{weeks:.1f} weeks"
    
    def _save_plan(self, project_name: str, plan: ImprovementPlan):
        """Save improvement plan to project directory"""
        project_dir = self.projects_dir / project_name
        project_dir.mkdir(exist_ok=True)
        
        plan_dict = asdict(plan)
        
        with open(project_dir / "improvement_plan.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plan_dict, f, default_flow_style=False, sort_keys=False)
    
    def load_plan(self, project_name: str) -> Optional[dict]:
        """Load existing improvement plan"""
        plan_path = self.projects_dir / project_name / "improvement_plan.yaml"
        
        if plan_path.exists():
            with open(plan_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return None
    
    def update_task_status(
        self,
        project_name: str,
        task_id: str,
        status: str,
        result: str = ""
    ):
        """Update the status of a task"""
        plan = self.load_plan(project_name)
        if not plan:
            return
        
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                if task.get("id") == task_id:
                    task["status"] = status
                    task["result"] = result
                    break
        
        project_dir = self.projects_dir / project_name
        with open(project_dir / "improvement_plan.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plan, f, default_flow_style=False, sort_keys=False)
    
    def get_next_task(self, project_name: str) -> Optional[dict]:
        """Get the next pending task"""
        plan = self.load_plan(project_name)
        if not plan:
            return None
        
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                if task.get("status") == "pending":
                    return task
        
        return None
    
    def get_progress(self, project_name: str) -> dict:
        """Get improvement progress"""
        plan = self.load_plan(project_name)
        if not plan:
            return {"error": "No plan found"}
        
        total = 0
        completed = 0
        in_progress = 0
        
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                total += 1
                status = task.get("status", "pending")
                if status == "completed":
                    completed += 1
                elif status == "in_progress":
                    in_progress += 1
        
        return {
            "total_tasks": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "percent_complete": (completed / total * 100) if total > 0 else 0
        }


def create_improvement_plan(
    project_name: str,
    health_report: dict,
    improvement_type: str = "all"
) -> ImprovementPlan:
    """
    Convenience function to create an improvement plan.
    
    Args:
        project_name: Project name
        health_report: Health report dict
        improvement_type: Type of improvements
        
    Returns:
        ImprovementPlan
    """
    planner = ImprovementPlanner()
    return planner.create_plan(project_name, health_report, improvement_type)
