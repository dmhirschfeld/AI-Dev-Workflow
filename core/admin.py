"""
Admin Tracker - Collects and aggregates usage data across all projects.

Provides:
- Total cost/tokens across all projects
- Per-project breakdowns
- Daily cost tracking
- Session history
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict


class AdminTracker:
    """Tracks Claude API usage across all projects."""

    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir)

    def get_summary(self) -> dict:
        """Get complete usage summary across all projects."""
        all_sessions = []
        project_stats = defaultdict(lambda: {
            "name": "",
            "sessions": 0,
            "tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "last_activity": None
        })
        daily_costs = defaultdict(float)

        # Scan all project directories
        if self.projects_dir.exists():
            for project_dir in self.projects_dir.iterdir():
                if project_dir.is_dir():
                    audit_dir = project_dir / "audit"
                    if audit_dir.exists():
                        self._process_project(
                            project_dir.name,
                            audit_dir,
                            all_sessions,
                            project_stats,
                            daily_costs
                        )

        # Sort sessions by date (newest first)
        all_sessions.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        # Calculate totals
        total_cost = sum(s.get("cost", 0) for s in all_sessions)
        total_tokens = sum(s.get("tokens", 0) for s in all_sessions)
        total_input_tokens = sum(s.get("input_tokens", 0) for s in all_sessions)
        total_output_tokens = sum(s.get("output_tokens", 0) for s in all_sessions)

        # Calculate today's cost
        today = datetime.now().strftime("%Y-%m-%d")
        today_cost = daily_costs.get(today, 0.0)

        # Get session cost range
        session_costs = [s.get("cost", 0) for s in all_sessions if s.get("cost", 0) > 0]
        min_session_cost = min(session_costs) if session_costs else 0
        max_session_cost = max(session_costs) if session_costs else 0

        # Prepare daily costs for last 7 days
        daily_costs_list = []
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_costs_list.append({
                "date": date,
                "cost": daily_costs.get(date, 0.0)
            })

        # Convert project stats to list
        projects_list = []
        for name, stats in project_stats.items():
            stats["name"] = name
            projects_list.append(stats)
        # Sort by cost descending
        projects_list.sort(key=lambda x: x.get("cost", 0), reverse=True)

        return {
            "total_cost": total_cost,
            "today_cost": today_cost,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_sessions": len(all_sessions),
            "total_projects": len(project_stats),
            "min_session_cost": min_session_cost,
            "max_session_cost": max_session_cost,
            "daily_costs": daily_costs_list,
            "projects": projects_list,
            "sessions": all_sessions[:50]  # Limit to 50 most recent
        }

    def _process_project(
        self,
        project_name: str,
        audit_dir: Path,
        all_sessions: list,
        project_stats: dict,
        daily_costs: dict
    ):
        """Process a single project's audit data."""
        # Find all session files
        session_files = list(audit_dir.glob("session_*.jsonl"))

        for session_file in session_files:
            session_data = self._process_session(session_file, project_name)
            if session_data:
                all_sessions.append(session_data)

                # Update project stats
                stats = project_stats[project_name]
                stats["sessions"] += 1
                stats["tokens"] += session_data.get("tokens", 0)
                stats["input_tokens"] += session_data.get("input_tokens", 0)
                stats["output_tokens"] += session_data.get("output_tokens", 0)
                stats["cost"] += session_data.get("cost", 0)

                # Track last activity
                started_at = session_data.get("started_at")
                if started_at:
                    if not stats["last_activity"] or started_at > stats["last_activity"]:
                        stats["last_activity"] = started_at

                    # Track daily cost
                    date = started_at[:10]  # YYYY-MM-DD
                    daily_costs[date] += session_data.get("cost", 0)

    def _process_session(self, session_file: Path, project_name: str) -> Optional[dict]:
        """Process a single session file and return summary."""
        try:
            events = []
            with open(session_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            if not events:
                return None

            # Extract session ID from filename: session_2025-01-15_143022.jsonl
            session_id = session_file.stem.replace("session_", "")

            # Calculate totals
            input_tokens = sum(e.get("input_tokens", 0) for e in events)
            output_tokens = sum(e.get("output_tokens", 0) for e in events)
            cost = sum(e.get("cost_usd", 0) for e in events)
            agent_calls = sum(1 for e in events if e.get("event_type") == "agent_call")

            # Get session start time
            started_at = None
            for e in events:
                if e.get("timestamp"):
                    started_at = e.get("timestamp")
                    break

            return {
                "session_id": session_id,
                "project": project_name,
                "started_at": started_at,
                "tokens": input_tokens + output_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "agent_calls": agent_calls,
                "events_count": len(events)
            }

        except Exception as e:
            print(f"Error processing {session_file}: {e}")
            return None

    def get_project_summary(self, project_name: str) -> dict:
        """Get usage summary for a specific project."""
        project_dir = self.projects_dir / project_name
        audit_dir = project_dir / "audit"

        if not audit_dir.exists():
            return {"error": f"Project {project_name} not found or has no audit data"}

        sessions = []
        total_cost = 0.0
        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for session_file in audit_dir.glob("session_*.jsonl"):
            session_data = self._process_session(session_file, project_name)
            if session_data:
                sessions.append(session_data)
                total_cost += session_data.get("cost", 0)
                total_tokens += session_data.get("tokens", 0)
                total_input_tokens += session_data.get("input_tokens", 0)
                total_output_tokens += session_data.get("output_tokens", 0)

        sessions.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        return {
            "project": project_name,
            "total_sessions": len(sessions),
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "sessions": sessions
        }


def get_global_stats(projects_dir: str = "projects") -> dict:
    """Convenience function to get global stats."""
    tracker = AdminTracker(Path(projects_dir))
    return tracker.get_summary()


if __name__ == "__main__":
    # Quick test
    tracker = AdminTracker(Path("projects"))
    summary = tracker.get_summary()
    print(f"Total Cost: ${summary['total_cost']:.4f}")
    print(f"Total Tokens: {summary['total_tokens']}")
    print(f"Total Sessions: {summary['total_sessions']}")
    print(f"Total Projects: {summary['total_projects']}")
