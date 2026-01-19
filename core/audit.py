"""
Audit Trail Module - Structured event logging for AI-Dev-Workflow

Captures all agent calls, gate votes, phase changes, and decisions
in JSONL format for replay, analysis, and monitoring.
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List


# Pricing per 1M tokens (input/output)
PRICING = {
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.80, 4.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
}


@dataclass
class AuditEvent:
    """A single audit trail event"""
    timestamp: str                          # ISO format
    event_type: str                         # agent_call, gate_vote, phase_change, decision, escalation
    session_id: str
    project_id: str
    agent: Optional[str] = None
    phase: Optional[str] = None
    checkpoint: Optional[str] = None
    input_summary: str = ""                 # First 500 chars of input
    output_summary: str = ""                # First 500 chars of output
    input_tokens: int = 0
    output_tokens: int = 0
    model: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    status: str = "success"                 # success, failure, pending
    metadata: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        data = asdict(self)
        # Remove None values for cleaner output
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data)


@dataclass
class SessionSummary:
    """Summary statistics for a session"""
    session_id: str
    project_id: str
    started_at: str
    ended_at: Optional[str] = None
    event_count: int = 0
    agent_calls: int = 0
    gate_votes: int = 0
    phase_changes: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    success_count: int = 0
    failure_count: int = 0
    phases_completed: List[str] = field(default_factory=list)
    current_phase: Optional[str] = None


class AuditLogger:
    """
    Thread-safe audit logger that writes events to JSONL files.

    File structure:
        projects/{project}/audit/
            session_2025-01-15_143022.jsonl
            index.json
    """

    def __init__(self, project_dir: Path, project_id: str, session_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.project_id = project_id
        self.audit_dir = self.project_dir / "audit"
        self.session_id = session_id or self._generate_session_id()
        self.session_file = self.audit_dir / f"session_{self.session_id}.jsonl"
        self.index_file = self.audit_dir / "index.json"
        self._lock = threading.Lock()
        self._summary = SessionSummary(
            session_id=self.session_id,
            project_id=project_id,
            started_at=datetime.now().isoformat()
        )
        self._ensure_dirs()
        self._update_index()
        self._write_session_start()

    def _write_session_start(self):
        """Write initial session_start event so file exists immediately"""
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="session_start",
            session_id=self.session_id,
            project_id=self.project_id,
            status="success",
            metadata={"message": "Audit session started"}
        )
        self.log_event(event)

    def _generate_session_id(self) -> str:
        """Generate a session ID from current timestamp"""
        return datetime.now().strftime("%Y-%m-%d_%H%M%S")

    def _ensure_dirs(self):
        """Create audit directory if needed"""
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD based on model and token counts"""
        if model not in PRICING:
            # Default to sonnet pricing
            input_price, output_price = 3.0, 15.0
        else:
            input_price, output_price = PRICING[model]

        return (input_tokens * input_price / 1_000_000) + (output_tokens * output_price / 1_000_000)

    def log_event(self, event: AuditEvent) -> None:
        """Append event to session JSONL file (thread-safe)"""
        with self._lock:
            # Write to JSONL
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")

            # Update summary
            self._summary.event_count += 1
            self._summary.total_input_tokens += event.input_tokens
            self._summary.total_output_tokens += event.output_tokens
            self._summary.total_cost_usd += event.cost_usd
            self._summary.total_duration_ms += event.duration_ms

            if event.status == "success":
                self._summary.success_count += 1
            elif event.status == "failure":
                self._summary.failure_count += 1

            if event.event_type == "agent_call":
                self._summary.agent_calls += 1
            elif event.event_type == "gate_vote":
                self._summary.gate_votes += 1
            elif event.event_type == "phase_change":
                self._summary.phase_changes += 1
                if event.phase:
                    self._summary.current_phase = event.phase
                    if event.phase not in self._summary.phases_completed:
                        self._summary.phases_completed.append(event.phase)

    def log_agent_call(
        self,
        agent_id: str,
        model: str,
        input_text: str,
        output_text: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        phase: Optional[str] = None,
        checkpoint: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        cost: Optional[float] = None
    ) -> None:
        """Log an agent API call"""
        # Use provided cost or calculate it
        if cost is None:
            cost = self._calculate_cost(model, input_tokens, output_tokens)

        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="agent_call",
            session_id=self.session_id,
            project_id=self.project_id,
            agent=agent_id,
            phase=phase,
            checkpoint=checkpoint,
            input_summary=input_text[:2000] if input_text else "",
            output_summary=output_text[:2000] if output_text else "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            cost_usd=cost,
            duration_ms=duration_ms,
            status="success" if success else "failure",
            metadata={"error": error} if error else None
        )
        self.log_event(event)

    def log_gate_vote(
        self,
        gate_id: str,
        voters: List[str],
        votes_for: int,
        votes_against: int,
        passed: bool,
        phase: Optional[str] = None,
        feedback: Optional[str] = None,
        total_tokens: int = 0,
        total_cost: float = 0.0,
        duration_ms: int = 0
    ) -> None:
        """Log a voting gate result"""
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="gate_vote",
            session_id=self.session_id,
            project_id=self.project_id,
            agent=gate_id,
            phase=phase,
            output_summary=feedback[:2000] if feedback else "",
            input_tokens=total_tokens,
            output_tokens=0,
            cost_usd=total_cost,
            duration_ms=duration_ms,
            status="success" if passed else "failure",
            metadata={
                "voters": voters,
                "votes_for": votes_for,
                "votes_against": votes_against,
                "passed": passed
            }
        )
        self.log_event(event)

    def log_phase_change(
        self,
        old_phase: str,
        new_phase: str,
        checkpoint: Optional[str] = None
    ) -> None:
        """Log a workflow phase transition"""
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="phase_change",
            session_id=self.session_id,
            project_id=self.project_id,
            phase=new_phase,
            checkpoint=checkpoint,
            input_summary=f"From: {old_phase}",
            output_summary=f"To: {new_phase}",
            status="success",
            metadata={"old_phase": old_phase, "new_phase": new_phase}
        )
        self.log_event(event)

    def log_decision(
        self,
        agent_id: str,
        phase: str,
        decision: str,
        rationale: str
    ) -> None:
        """Log a decision made during workflow"""
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="decision",
            session_id=self.session_id,
            project_id=self.project_id,
            agent=agent_id,
            phase=phase,
            input_summary=decision[:2000],
            output_summary=rationale[:2000],
            status="success"
        )
        self.log_event(event)

    def log_escalation(
        self,
        reason: str,
        phase: str,
        context: Optional[str] = None
    ) -> None:
        """Log an escalation to human review"""
        event = AuditEvent(
            timestamp=datetime.now().isoformat(),
            event_type="escalation",
            session_id=self.session_id,
            project_id=self.project_id,
            phase=phase,
            input_summary=reason[:2000],
            output_summary=context[:2000] if context else "",
            status="pending",
            metadata={"requires_human_review": True}
        )
        self.log_event(event)

    def get_session_summary(self) -> SessionSummary:
        """Get current session summary"""
        self._summary.ended_at = datetime.now().isoformat()
        return self._summary

    def _update_index(self) -> None:
        """Update index.json with session metadata"""
        with self._lock:
            # Load existing index
            if self.index_file.exists():
                try:
                    with open(self.index_file, "r", encoding="utf-8") as f:
                        index = json.load(f)
                except (json.JSONDecodeError, IOError):
                    index = {"sessions": []}
            else:
                index = {"sessions": []}

            # Add/update current session
            session_entry = {
                "session_id": self.session_id,
                "project_id": self.project_id,
                "started_at": self._summary.started_at,
                "file": self.session_file.name
            }

            # Remove existing entry for this session if any
            index["sessions"] = [
                s for s in index["sessions"]
                if s["session_id"] != self.session_id
            ]
            index["sessions"].append(session_entry)

            # Sort by date descending
            index["sessions"].sort(key=lambda x: x["started_at"], reverse=True)

            # Write updated index
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)

    def finalize(self) -> None:
        """Finalize session - update index with final stats"""
        summary = self.get_session_summary()

        with self._lock:
            if self.index_file.exists():
                try:
                    with open(self.index_file, "r", encoding="utf-8") as f:
                        index = json.load(f)
                except (json.JSONDecodeError, IOError):
                    index = {"sessions": []}
            else:
                index = {"sessions": []}

            # Update session entry with final stats
            for session in index["sessions"]:
                if session["session_id"] == self.session_id:
                    session["ended_at"] = summary.ended_at
                    session["event_count"] = summary.event_count
                    session["agent_calls"] = summary.agent_calls
                    session["total_cost_usd"] = round(summary.total_cost_usd, 4)
                    session["total_tokens"] = summary.total_input_tokens + summary.total_output_tokens
                    break

            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)


def get_latest_session(project_dir: Path) -> Optional[str]:
    """Get the most recent session ID for a project, with fallback to scanning audit directory"""
    project_dir = Path(project_dir)
    index_file = project_dir / "audit" / "index.json"

    # Try index first
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            if index.get("sessions"):
                return index["sessions"][0]["session_id"]
        except (json.JSONDecodeError, IOError, KeyError):
            pass

    # Fallback: scan for session files directly
    audit_dir = project_dir / "audit"
    if audit_dir.exists():
        session_files = sorted(audit_dir.glob("session_*.jsonl"), reverse=True)
        if session_files:
            # Extract session_id from filename: session_2025-01-15_143022.jsonl
            return session_files[0].stem.replace("session_", "")

    return None


def read_session_events(project_dir: Path, session_id: str) -> List[Dict]:
    """Read all events from a session JSONL file"""
    session_file = project_dir / "audit" / f"session_{session_id}.jsonl"
    events = []

    if session_file.exists():
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    return events
