"""
Live Monitor Module for AI-Dev-Workflow

Provides real-time monitoring of workflow progress via:
- ConsoleMonitor: Terminal-based live feed (tail -f style)
- WebMonitor: Browser-based dashboard with Server-Sent Events
"""

import json
import time
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from core.audit import read_session_events, get_latest_session


@dataclass
class MonitorStats:
    """Running statistics for monitoring"""
    session_id: str
    project_id: str
    started_at: str
    current_phase: str = "unknown"
    agent_calls: int = 0
    gate_votes: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    events: List[Dict] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []


class ConsoleMonitor:
    """
    Terminal-based monitor that tails the audit JSONL file.
    Usage: python cli.py monitor [project] --follow
    """

    def __init__(self, project_dir: Path, session_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.audit_dir = self.project_dir / "audit"
        self.session_id = session_id or get_latest_session(self.project_dir)
        self.running = False
        self.stats = None

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def _get_session_file(self) -> Optional[Path]:
        """Get the session JSONL file path"""
        if not self.session_id:
            return None
        return self.audit_dir / f"session_{self.session_id}.jsonl"

    def _load_stats(self) -> MonitorStats:
        """Load and compute stats from session file"""
        events = read_session_events(self.project_dir, self.session_id) if self.session_id else []

        stats = MonitorStats(
            session_id=self.session_id or "none",
            project_id=self.project_dir.name,
            started_at=events[0]["timestamp"] if events else datetime.now().isoformat()
        )

        for event in events:
            stats.events.append(event)
            stats.total_input_tokens += event.get("input_tokens", 0)
            stats.total_output_tokens += event.get("output_tokens", 0)
            stats.total_cost += event.get("cost_usd", 0)

            if event.get("status") == "success":
                stats.success_count += 1
            elif event.get("status") == "failure":
                stats.failure_count += 1

            if event.get("event_type") == "agent_call":
                stats.agent_calls += 1
            elif event.get("event_type") == "gate_vote":
                stats.gate_votes += 1
            elif event.get("event_type") == "phase_change":
                stats.current_phase = event.get("phase", stats.current_phase)

        return stats

    def follow(self):
        """Follow the audit file and display live updates"""
        session_file = self._get_session_file()

        if not session_file:
            print("No active session found. Start a workflow first.")
            return

        print(f"Monitoring session: {self.session_id}")
        print(f"Project: {self.project_dir.name}")
        print(f"Session file: {session_file}")
        print("-" * 60)
        print("Watching for events... (Ctrl+C to stop)\n")

        self.running = True
        last_position = 0

        # Load existing events
        if session_file.exists():
            with open(session_file, "r", encoding="utf-8") as f:
                for line in f:
                    self._display_event(json.loads(line.strip()))
                last_position = f.tell()

        # Watch for new events
        try:
            while self.running:
                if session_file.exists():
                    with open(session_file, "r", encoding="utf-8") as f:
                        f.seek(last_position)
                        for line in f:
                            line = line.strip()
                            if line:
                                self._display_event(json.loads(line))
                        last_position = f.tell()
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
            self.running = False

    def _display_event(self, event: Dict):
        """Display a single event in the console"""
        timestamp = event.get("timestamp", "")[:19].replace("T", " ")
        event_type = event.get("event_type", "unknown")
        agent = event.get("agent", "-")
        status = event.get("status", "")
        duration = event.get("duration_ms", 0)
        cost = event.get("cost_usd", 0)

        # Status indicator
        if status == "success":
            status_icon = "[OK]"
        elif status == "failure":
            status_icon = "[FAIL]"
        elif status == "pending":
            status_icon = "[...]"
        else:
            status_icon = "[--]"

        # Format based on event type
        if event_type == "agent_call":
            tokens = event.get("input_tokens", 0) + event.get("output_tokens", 0)
            output = event.get("output_summary", "")[:60]
            print(f"{timestamp} {status_icon} {agent:25} {duration:5}ms ${cost:.4f} ({tokens} tok)")
            if output:
                print(f"{'':20} -> {output}...")

        elif event_type == "gate_vote":
            meta = event.get("metadata", {})
            votes_for = meta.get("votes_for", 0)
            votes_against = meta.get("votes_against", 0)
            passed = "PASS" if meta.get("passed") else "FAIL"
            print(f"{timestamp} {status_icon} GATE: {agent:20} {passed} ({votes_for} for / {votes_against} against)")

        elif event_type == "phase_change":
            meta = event.get("metadata", {})
            old_phase = meta.get("old_phase", "?")
            new_phase = meta.get("new_phase", "?")
            print(f"{timestamp} [>>>] PHASE: {old_phase} -> {new_phase}")

        elif event_type == "escalation":
            print(f"{timestamp} [!!!] ESCALATION: {event.get('input_summary', '')}")

        elif event_type == "decision":
            print(f"{timestamp} [DEC] {agent}: {event.get('input_summary', '')[:50]}")

        else:
            print(f"{timestamp} [{event_type}] {agent}")

    def display_summary(self):
        """Display summary statistics"""
        stats = self._load_stats()

        print("\n" + "=" * 60)
        print(f"SESSION SUMMARY: {stats.session_id}")
        print("=" * 60)
        print(f"Project:      {stats.project_id}")
        print(f"Started:      {stats.started_at}")
        print(f"Phase:        {stats.current_phase}")
        print(f"Agent Calls:  {stats.agent_calls}")
        print(f"Gate Votes:   {stats.gate_votes}")
        print(f"Success:      {stats.success_count}")
        print(f"Failures:     {stats.failure_count}")
        print(f"Tokens:       {stats.total_input_tokens:,} in / {stats.total_output_tokens:,} out")
        print(f"Total Cost:   ${stats.total_cost:.4f}")
        print("=" * 60)


class WebMonitor:
    """
    Web-based monitor with live dashboard.
    Usage: python cli.py monitor [project] --web
    """

    def __init__(self, project_dir: Path, port: int = 8765, session_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.port = port
        self.session_id = session_id  # If provided, watch this specific session
        self.server = None
        self.running = False

    def start(self, open_browser: bool = True):
        """Start the web monitor server"""
        handler = self._create_handler()
        self.server = HTTPServer(("localhost", self.port), handler)
        self.running = True

        print(f"Starting web monitor at http://localhost:{self.port}")
        print(f"Project: {self.project_dir.name}")
        print("Press Ctrl+C to stop.\n")

        if open_browser:
            webbrowser.open(f"http://localhost:{self.port}")

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping web monitor...")
            self.running = False
            self.server.shutdown()

    def _create_handler(self):
        """Create HTTP request handler with closure over project_dir"""
        project_dir = self.project_dir
        fixed_session_id = self.session_id  # Capture session_id for closure

        class MonitorHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress default logging

            def do_GET(self):
                if self.path == "/":
                    self._serve_dashboard()
                elif self.path == "/events":
                    self._serve_sse()
                elif self.path == "/api/summary":
                    self._serve_summary()
                elif self.path == "/api/events":
                    self._serve_events()
                else:
                    self.send_error(404)

            def _serve_dashboard(self):
                """Serve the HTML dashboard"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

            def _serve_sse(self):
                """Server-Sent Events endpoint for live updates"""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Use fixed session if provided, otherwise find latest
                session_id = fixed_session_id or get_latest_session(project_dir)
                if not session_id:
                    self.wfile.write(b"data: {\"error\": \"no_session\", \"message\": \"No active session found\"}\n\n")
                    self.wfile.flush()
                    return

                session_file = project_dir / "audit" / f"session_{session_id}.jsonl"
                last_position = 0

                # Send initial connection message
                self.wfile.write(f"data: {{\"event_type\": \"connected\", \"session_id\": \"{session_id}\", \"file\": \"{session_file.name}\"}}\n\n".encode("utf-8"))
                self.wfile.flush()

                try:
                    while True:
                        if session_file.exists():
                            with open(session_file, "r", encoding="utf-8") as f:
                                f.seek(last_position)
                                for line in f:
                                    line = line.strip()
                                    if line:
                                        self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                                        self.wfile.flush()
                                last_position = f.tell()
                        time.sleep(0.5)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _serve_summary(self):
                """Serve JSON summary"""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                session_id = fixed_session_id or get_latest_session(project_dir)
                events = read_session_events(project_dir, session_id) if session_id else []

                summary = {
                    "session_id": session_id or "none",
                    "project_id": project_dir.name,
                    "event_count": len(events),
                    "agent_calls": sum(1 for e in events if e.get("event_type") == "agent_call"),
                    "gate_votes": sum(1 for e in events if e.get("event_type") == "gate_vote"),
                    "total_tokens": sum(e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in events),
                    "total_cost": sum(e.get("cost_usd", 0) for e in events),
                    "current_phase": next((e.get("phase") for e in reversed(events) if e.get("event_type") == "phase_change"), "unknown")
                }

                self.wfile.write(json.dumps(summary).encode("utf-8"))

            def _serve_events(self):
                """Serve all events as JSON"""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                session_id = fixed_session_id or get_latest_session(project_dir)
                events = read_session_events(project_dir, session_id) if session_id else []
                self.wfile.write(json.dumps(events).encode("utf-8"))

        return MonitorHandler


# Embedded HTML Dashboard
DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Dev-Workflow Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #334155;
        }
        .header h1 { font-size: 1.5rem; color: #f1f5f9; }
        .live-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #10b981;
            font-size: 0.9rem;
        }
        .live-dot {
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #1e293b;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #f1f5f9;
        }
        .stat-label {
            font-size: 0.85rem;
            color: #94a3b8;
            margin-top: 5px;
        }
        .stat-card.success .stat-value { color: #10b981; }
        .stat-card.cost .stat-value { color: #f59e0b; }
        .info-bar {
            display: flex;
            gap: 30px;
            background: #1e293b;
            border-radius: 10px;
            padding: 15px 20px;
            margin-bottom: 20px;
            font-size: 0.9rem;
        }
        .info-item { display: flex; gap: 8px; }
        .info-label { color: #64748b; }
        .info-value { color: #e2e8f0; font-weight: 500; }
        .activity-section {
            background: #1e293b;
            border-radius: 10px;
            padding: 20px;
        }
        .activity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .activity-header h2 { font-size: 1.1rem; color: #f1f5f9; }
        .activity-feed {
            max-height: 500px;
            overflow-y: auto;
        }
        .event {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px;
            border-bottom: 1px solid #334155;
        }
        .event:last-child { border-bottom: none; }
        .event-time {
            font-size: 0.8rem;
            color: #64748b;
            white-space: nowrap;
            font-family: monospace;
        }
        .event-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            flex-shrink: 0;
        }
        .event-icon.success { background: #064e3b; color: #10b981; }
        .event-icon.failure { background: #7f1d1d; color: #f87171; }
        .event-icon.pending { background: #1e3a8a; color: #60a5fa; }
        .event-icon.phase { background: #4c1d95; color: #a78bfa; }
        .event-content { flex: 1; min-width: 0; }
        .event-title { color: #e2e8f0; font-size: 0.9rem; }
        .event-meta {
            display: flex;
            gap: 15px;
            margin-top: 4px;
            font-size: 0.8rem;
            color: #64748b;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI-Dev-Workflow Monitor</h1>
        <div class="live-indicator">
            <div class="live-dot"></div>
            <span>LIVE</span>
            <span id="current-time"></span>
        </div>
    </div>

    <div class="info-bar">
        <div class="info-item">
            <span class="info-label">Project:</span>
            <span class="info-value" id="project-name">-</span>
        </div>
        <div class="info-item">
            <span class="info-label">Session:</span>
            <span class="info-value" id="session-id">-</span>
        </div>
        <div class="info-item">
            <span class="info-label">Phase:</span>
            <span class="info-value" id="current-phase">-</span>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" id="agent-count">0</div>
            <div class="stat-label">Agent Calls</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="gate-count">0</div>
            <div class="stat-label">Gate Votes</div>
        </div>
        <div class="stat-card success">
            <div class="stat-value" id="success-rate">0%</div>
            <div class="stat-label">Success Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="total-tokens">0</div>
            <div class="stat-label">Tokens</div>
        </div>
        <div class="stat-card cost">
            <div class="stat-value" id="total-cost">$0.00</div>
            <div class="stat-label">Total Cost</div>
        </div>
    </div>

    <div class="activity-section">
        <div class="activity-header">
            <h2>Activity Feed</h2>
        </div>
        <div class="activity-feed" id="activity-feed">
            <div class="empty-state">Waiting for events...</div>
        </div>
    </div>

    <script>
        // State
        let stats = {
            agentCalls: 0,
            gateVotes: 0,
            success: 0,
            failure: 0,
            tokens: 0,
            cost: 0
        };
        let events = [];

        // Update clock
        function updateClock() {
            const now = new Date();
            document.getElementById('current-time').textContent =
                now.toLocaleTimeString('en-US', { hour12: false });
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Load initial summary
        fetch('/api/summary')
            .then(r => r.json())
            .then(data => {
                document.getElementById('project-name').textContent = data.project_id || '-';
                document.getElementById('session-id').textContent = data.session_id || '-';
                document.getElementById('current-phase').textContent = data.current_phase || '-';
                stats.agentCalls = data.agent_calls || 0;
                stats.gateVotes = data.gate_votes || 0;
                stats.tokens = data.total_tokens || 0;
                stats.cost = data.total_cost || 0;
                updateStats();
            });

        // Load existing events
        fetch('/api/events')
            .then(r => r.json())
            .then(data => {
                events = data;
                renderEvents();
            });

        // SSE for live updates
        const evtSource = new EventSource('/events');
        evtSource.onmessage = (e) => {
            try {
                const event = JSON.parse(e.data);
                if (event.error) {
                    console.warn('SSE error:', event.error, event.message);
                    return;
                }

                // Handle connection event
                if (event.event_type === 'connected') {
                    console.log('SSE connected to session:', event.session_id);
                    document.getElementById('current-phase').textContent = 'Connected';
                    return;
                }

                events.push(event);
                stats.tokens += (event.input_tokens || 0) + (event.output_tokens || 0);
                stats.cost += event.cost_usd || 0;

                if (event.event_type === 'agent_call') stats.agentCalls++;
                if (event.event_type === 'gate_vote') stats.gateVotes++;
                if (event.status === 'success') stats.success++;
                if (event.status === 'failure') stats.failure++;
                if (event.event_type === 'phase_change') {
                    document.getElementById('current-phase').textContent =
                        event.metadata?.new_phase || event.phase || '-';
                }

                updateStats();
                addEventToFeed(event);
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        };

        function updateStats() {
            document.getElementById('agent-count').textContent = stats.agentCalls;
            document.getElementById('gate-count').textContent = stats.gateVotes;
            document.getElementById('total-tokens').textContent =
                stats.tokens > 1000 ? Math.round(stats.tokens/1000) + 'k' : stats.tokens;
            document.getElementById('total-cost').textContent = '$' + stats.cost.toFixed(2);

            const total = stats.success + stats.failure;
            const rate = total > 0 ? Math.round((stats.success / total) * 100) : 100;
            document.getElementById('success-rate').textContent = rate + '%';
        }

        function renderEvents() {
            const feed = document.getElementById('activity-feed');
            if (events.length === 0) {
                feed.innerHTML = '<div class="empty-state">Waiting for events...</div>';
                return;
            }
            feed.innerHTML = '';
            events.slice(-50).reverse().forEach(e => addEventToFeed(e, false));
        }

        function addEventToFeed(event, prepend = true) {
            const feed = document.getElementById('activity-feed');

            // Remove empty state if present
            const empty = feed.querySelector('.empty-state');
            if (empty) empty.remove();

            const div = document.createElement('div');
            div.className = 'event';

            const time = (event.timestamp || '').substring(11, 19);
            const type = event.event_type || 'unknown';
            const agent = event.agent || '-';
            const status = event.status || '';

            let iconClass = 'pending';
            let iconText = '?';

            if (status === 'success') { iconClass = 'success'; iconText = '\\u2713'; }
            else if (status === 'failure') { iconClass = 'failure'; iconText = '\\u2717'; }
            else if (type === 'phase_change') { iconClass = 'phase'; iconText = '\\u279C'; }

            let title = agent;
            let meta = [];

            if (type === 'agent_call') {
                meta.push((event.duration_ms || 0) + 'ms');
                meta.push('$' + (event.cost_usd || 0).toFixed(4));
                meta.push((event.input_tokens || 0) + (event.output_tokens || 0) + ' tok');
            } else if (type === 'gate_vote') {
                const m = event.metadata || {};
                title = 'GATE: ' + agent;
                meta.push(m.passed ? 'PASSED' : 'FAILED');
                meta.push(m.votes_for + ' for / ' + m.votes_against + ' against');
            } else if (type === 'phase_change') {
                const m = event.metadata || {};
                title = 'Phase: ' + (m.old_phase || '?') + ' \\u2192 ' + (m.new_phase || '?');
            } else if (type === 'escalation') {
                title = 'ESCALATION: ' + (event.input_summary || '').substring(0, 50);
            } else if (type === 'session_start') {
                iconClass = 'success';
                iconText = '\\u25B6';
                title = 'Session Started';
                meta.push('Project: ' + event.project_id);
            } else if (type === 'decision') {
                iconClass = 'phase';
                iconText = '\\u2714';
                title = 'Decision: ' + (event.output_summary || '').substring(0, 50);
            }

            div.innerHTML = ` + "`" + `
                <span class="event-time">${time}</span>
                <div class="event-icon ${iconClass}">${iconText}</div>
                <div class="event-content">
                    <div class="event-title">${title}</div>
                    <div class="event-meta">${meta.map(m => '<span>' + m + '</span>').join('')}</div>
                </div>
            ` + "`" + `;

            if (prepend) {
                feed.insertBefore(div, feed.firstChild);
                // Keep only last 50 events in DOM
                while (feed.children.length > 50) {
                    feed.removeChild(feed.lastChild);
                }
            } else {
                feed.appendChild(div);
            }
        }
    </script>
</body>
</html>
"""
