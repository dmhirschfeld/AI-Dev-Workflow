"""
Token Usage & Cost Tracking Module

Tracks API usage per project, feature, and agent.
Calculates costs based on current Claude pricing.

Usage data stored in:
- projects/<project>/usage.yaml (per-project totals)
- projects/<project>/usage_log.jsonl (detailed log)
"""

import os
import json
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from collections import defaultdict
import yaml


# ════════════════════════════════════════════════════════════
# PRICING (as of Jan 2025)
# ════════════════════════════════════════════════════════════

PRICING = {
    # Claude 3.5 Sonnet (most common for agents)
    "claude-3-5-sonnet-20241022": {
        "input": 3.00 / 1_000_000,   # $3 per 1M input tokens
        "output": 15.00 / 1_000_000,  # $15 per 1M output tokens
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    # Claude 3.5 Haiku (for simple tasks)
    "claude-3-5-haiku-20241022": {
        "input": 0.80 / 1_000_000,   # $0.80 per 1M input tokens
        "output": 4.00 / 1_000_000,   # $4 per 1M output tokens
    },
    # Claude 3 Opus (for complex reasoning)
    "claude-3-opus-20240229": {
        "input": 15.00 / 1_000_000,  # $15 per 1M input tokens
        "output": 75.00 / 1_000_000,  # $75 per 1M output tokens
    },
    # Default fallback
    "default": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
}


@dataclass
class UsageEntry:
    """Single API call usage record"""
    timestamp: str
    project_id: str
    feature_id: Optional[str]
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost: float = 0.0
    context: str = ""  # Brief description of what was being done
    
    def calculate_cost(self) -> float:
        """Calculate cost based on model pricing"""
        pricing = PRICING.get(self.model, PRICING["default"])
        
        # Cache reads are 90% cheaper
        cache_discount = 0.1
        
        input_cost = self.input_tokens * pricing["input"]
        output_cost = self.output_tokens * pricing["output"]
        cache_read_cost = self.cache_read_tokens * pricing["input"] * cache_discount
        
        self.cost = input_cost + output_cost + cache_read_cost
        return self.cost


@dataclass
class ProjectUsageSummary:
    """Aggregated usage for a project"""
    project_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0
    
    # Breakdown by agent
    by_agent: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Breakdown by feature
    by_feature: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Breakdown by date
    by_date: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Breakdown by model
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    first_call: Optional[str] = None
    last_call: Optional[str] = None


class UsageTracker:
    """
    Tracks token usage and costs per project.
    
    Usage:
        tracker = UsageTracker("projects")
        
        # Record API call
        tracker.record(
            project_id="my-project",
            agent="developer",
            model="claude-3-5-sonnet-20241022",
            input_tokens=1500,
            output_tokens=800,
            context="Implementing login feature"
        )
        
        # Get summary
        summary = tracker.get_project_summary("my-project")
        print(f"Total cost: ${summary.total_cost:.2f}")
    """
    
    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
    
    def record(
        self,
        project_id: str,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        feature_id: Optional[str] = None,
        context: str = "",
    ) -> UsageEntry:
        """
        Record a single API call.
        
        Args:
            project_id: Project identifier
            agent: Agent that made the call (developer, architect, etc.)
            model: Model used (claude-3-5-sonnet-20241022, etc.)
            input_tokens: Input token count
            output_tokens: Output token count
            cache_read_tokens: Tokens read from cache
            cache_write_tokens: Tokens written to cache
            feature_id: Optional feature being worked on
            context: Brief description of the task
            
        Returns:
            UsageEntry with calculated cost
        """
        entry = UsageEntry(
            timestamp=datetime.now().isoformat(),
            project_id=project_id,
            feature_id=feature_id,
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            context=context,
        )
        
        entry.calculate_cost()
        
        # Save to log
        self._append_log(project_id, entry)
        
        # Update summary
        self._update_summary(project_id, entry)
        
        return entry
    
    def _append_log(self, project_id: str, entry: UsageEntry):
        """Append entry to project's usage log"""
        project_dir = self.projects_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = project_dir / "usage_log.jsonl"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
    
    def _update_summary(self, project_id: str, entry: UsageEntry):
        """Update project's usage summary"""
        project_dir = self.projects_dir / project_id
        summary_file = project_dir / "usage.yaml"
        
        # Load existing summary
        if summary_file.exists():
            with open(summary_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        
        # Update totals
        data["total_input_tokens"] = data.get("total_input_tokens", 0) + entry.input_tokens
        data["total_output_tokens"] = data.get("total_output_tokens", 0) + entry.output_tokens
        data["total_cache_read_tokens"] = data.get("total_cache_read_tokens", 0) + entry.cache_read_tokens
        data["total_cost"] = data.get("total_cost", 0.0) + entry.cost
        data["call_count"] = data.get("call_count", 0) + 1
        
        # Update timestamps
        if "first_call" not in data:
            data["first_call"] = entry.timestamp
        data["last_call"] = entry.timestamp
        
        # Update by_agent
        if "by_agent" not in data:
            data["by_agent"] = {}
        if entry.agent not in data["by_agent"]:
            data["by_agent"][entry.agent] = {
                "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0
            }
        data["by_agent"][entry.agent]["input_tokens"] += entry.input_tokens
        data["by_agent"][entry.agent]["output_tokens"] += entry.output_tokens
        data["by_agent"][entry.agent]["cost"] += entry.cost
        data["by_agent"][entry.agent]["calls"] += 1
        
        # Update by_feature
        if entry.feature_id:
            if "by_feature" not in data:
                data["by_feature"] = {}
            if entry.feature_id not in data["by_feature"]:
                data["by_feature"][entry.feature_id] = {
                    "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0
                }
            data["by_feature"][entry.feature_id]["input_tokens"] += entry.input_tokens
            data["by_feature"][entry.feature_id]["output_tokens"] += entry.output_tokens
            data["by_feature"][entry.feature_id]["cost"] += entry.cost
            data["by_feature"][entry.feature_id]["calls"] += 1
        
        # Update by_date
        entry_date = entry.timestamp[:10]  # YYYY-MM-DD
        if "by_date" not in data:
            data["by_date"] = {}
        if entry_date not in data["by_date"]:
            data["by_date"][entry_date] = {
                "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0
            }
        data["by_date"][entry_date]["input_tokens"] += entry.input_tokens
        data["by_date"][entry_date]["output_tokens"] += entry.output_tokens
        data["by_date"][entry_date]["cost"] += entry.cost
        data["by_date"][entry_date]["calls"] += 1
        
        # Update by_model
        if "by_model" not in data:
            data["by_model"] = {}
        if entry.model not in data["by_model"]:
            data["by_model"][entry.model] = {
                "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0
            }
        data["by_model"][entry.model]["input_tokens"] += entry.input_tokens
        data["by_model"][entry.model]["output_tokens"] += entry.output_tokens
        data["by_model"][entry.model]["cost"] += entry.cost
        data["by_model"][entry.model]["calls"] += 1
        
        # Save
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get_project_summary(self, project_id: str) -> Optional[ProjectUsageSummary]:
        """Get usage summary for a project"""
        summary_file = self.projects_dir / project_id / "usage.yaml"
        
        if not summary_file.exists():
            return None
        
        with open(summary_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        return ProjectUsageSummary(
            project_id=project_id,
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_cache_read_tokens=data.get("total_cache_read_tokens", 0),
            total_cost=data.get("total_cost", 0.0),
            call_count=data.get("call_count", 0),
            by_agent=data.get("by_agent", {}),
            by_feature=data.get("by_feature", {}),
            by_date=data.get("by_date", {}),
            by_model=data.get("by_model", {}),
            first_call=data.get("first_call"),
            last_call=data.get("last_call"),
        )
    
    def get_project_log(
        self,
        project_id: str,
        limit: int = 100,
        agent: Optional[str] = None,
        feature_id: Optional[str] = None,
    ) -> List[UsageEntry]:
        """Get detailed usage log for a project"""
        log_file = self.projects_dir / project_id / "usage_log.jsonl"
        
        if not log_file.exists():
            return []
        
        entries = []
        
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    entry = UsageEntry(**data)
                    
                    # Filter
                    if agent and entry.agent != agent:
                        continue
                    if feature_id and entry.feature_id != feature_id:
                        continue
                    
                    entries.append(entry)
                except:
                    continue
        
        # Return most recent first
        entries.reverse()
        return entries[:limit]
    
    def get_all_projects_summary(self) -> Dict[str, ProjectUsageSummary]:
        """Get usage summary for all projects"""
        summaries = {}
        
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                summary = self.get_project_summary(project_dir.name)
                if summary:
                    summaries[project_dir.name] = summary
        
        return summaries
    
    def get_total_cost(self) -> float:
        """Get total cost across all projects"""
        total = 0.0
        for summary in self.get_all_projects_summary().values():
            total += summary.total_cost
        return total
    
    def format_summary(self, summary: ProjectUsageSummary) -> str:
        """Format summary for display"""
        lines = []
        lines.append(f"{'═' * 60}")
        lines.append(f"  USAGE REPORT: {summary.project_id}")
        lines.append(f"{'═' * 60}")
        lines.append("")
        lines.append(f"Total Cost:        ${summary.total_cost:.4f}")
        lines.append(f"Total Calls:       {summary.call_count:,}")
        lines.append(f"Input Tokens:      {summary.total_input_tokens:,}")
        lines.append(f"Output Tokens:     {summary.total_output_tokens:,}")
        if summary.total_cache_read_tokens:
            lines.append(f"Cache Read Tokens: {summary.total_cache_read_tokens:,}")
        lines.append("")
        
        if summary.first_call:
            lines.append(f"First Call: {summary.first_call[:19]}")
        if summary.last_call:
            lines.append(f"Last Call:  {summary.last_call[:19]}")
        lines.append("")
        
        # By agent
        if summary.by_agent:
            lines.append("By Agent:")
            lines.append(f"  {'Agent':<20} {'Calls':>8} {'Cost':>12}")
            lines.append(f"  {'-'*20} {'-'*8} {'-'*12}")
            for agent, data in sorted(summary.by_agent.items(), key=lambda x: x[1]["cost"], reverse=True):
                lines.append(f"  {agent:<20} {data['calls']:>8} ${data['cost']:>10.4f}")
            lines.append("")
        
        # By feature
        if summary.by_feature:
            lines.append("By Feature:")
            lines.append(f"  {'Feature':<25} {'Calls':>8} {'Cost':>12}")
            lines.append(f"  {'-'*25} {'-'*8} {'-'*12}")
            for feature, data in sorted(summary.by_feature.items(), key=lambda x: x[1]["cost"], reverse=True):
                lines.append(f"  {feature[:25]:<25} {data['calls']:>8} ${data['cost']:>10.4f}")
            lines.append("")
        
        # By date (last 7 days)
        if summary.by_date:
            lines.append("By Date (Recent):")
            lines.append(f"  {'Date':<12} {'Calls':>8} {'Cost':>12}")
            lines.append(f"  {'-'*12} {'-'*8} {'-'*12}")
            dates = sorted(summary.by_date.keys(), reverse=True)[:7]
            for d in dates:
                data = summary.by_date[d]
                lines.append(f"  {d:<12} {data['calls']:>8} ${data['cost']:>10.4f}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_all_projects(self) -> str:
        """Format summary of all projects"""
        summaries = self.get_all_projects_summary()
        
        if not summaries:
            return "No usage data found."
        
        lines = []
        lines.append(f"{'═' * 60}")
        lines.append(f"  ALL PROJECTS USAGE")
        lines.append(f"{'═' * 60}")
        lines.append("")
        
        total_cost = 0.0
        total_calls = 0
        
        lines.append(f"{'Project':<25} {'Calls':>10} {'Cost':>15}")
        lines.append(f"{'-'*25} {'-'*10} {'-'*15}")
        
        for project_id, summary in sorted(summaries.items(), key=lambda x: x[1].total_cost, reverse=True):
            lines.append(f"{project_id[:25]:<25} {summary.call_count:>10,} ${summary.total_cost:>13.4f}")
            total_cost += summary.total_cost
            total_calls += summary.call_count
        
        lines.append(f"{'-'*25} {'-'*10} {'-'*15}")
        lines.append(f"{'TOTAL':<25} {total_calls:>10,} ${total_cost:>13.4f}")
        lines.append("")
        
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════

_tracker = None

def get_tracker(projects_dir: str = "projects") -> UsageTracker:
    """Get or create the global usage tracker"""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker(projects_dir)
    return _tracker


def record_usage(
    project_id: str,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs
) -> UsageEntry:
    """Convenience function to record usage"""
    tracker = get_tracker()
    return tracker.record(
        project_id=project_id,
        agent=agent,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        **kwargs
    )


def get_project_cost(project_id: str) -> float:
    """Get total cost for a project"""
    tracker = get_tracker()
    summary = tracker.get_project_summary(project_id)
    return summary.total_cost if summary else 0.0


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-3-5-sonnet-20241022"
) -> float:
    """Estimate cost for a given token count"""
    pricing = PRICING.get(model, PRICING["default"])
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
