"""
Monitor Module - Real-time monitoring for AI-Dev-Workflow

Provides:
- ConsoleMonitor: Terminal-based event viewer with --follow mode
- WebMonitor: Browser-based dashboard with live updates
"""

import json
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from core.audit import get_latest_session, read_session_events


class ConsoleMonitor:
    """Terminal-based monitor that displays events in real-time"""

    def __init__(self, project_dir: Path, session_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.audit_dir = self.project_dir / "audit"
        self.session_id = session_id or get_latest_session(self.project_dir)
        self.running = False

    def follow(self):
        """Follow mode - continuously display new events"""
        if not self.session_id:
            print("No session found to monitor")
            return

        session_file = self.audit_dir / f"session_{self.session_id}.jsonl"
        print(f"Console: Monitoring session: {self.session_id}")
        print(f"Project: {self.project_dir.name}")
        print(f"Session file: {session_file}")
        print("-" * 60)
        print("Watching for events... (Ctrl+C to stop)\n")

        self.running = True
        last_position = 0

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
        """Display a single event in the console with detailed output"""
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
            output = event.get("output_summary", "")
            print(f"{timestamp} {status_icon} {agent:25} {duration:5}ms ${cost:.4f} ({tokens} tok)")

            # Show detailed output for step analysis
            if output and agent.startswith("step_"):
                lines = output.split("\n")
                for line in lines[:15]:
                    if line.strip():
                        print(f"{'':20} {line}")
                if len(lines) > 15:
                    print(f"{'':20} ... ({len(lines) - 15} more lines)")
            elif output:
                print(f"{'':20} -> {output[:100]}...")

        elif event_type == "gate_vote":
            meta = event.get("metadata", {})
            votes_for = meta.get("votes_for", 0)
            votes_against = meta.get("votes_against", 0)
            passed = "PASS" if meta.get("passed") else "FAIL"
            feedback = event.get("output_summary", "")
            print(f"{timestamp} {status_icon} GATE: {agent:20} {passed} ({votes_for} for / {votes_against} against)")
            if feedback and len(feedback) > 10:
                max_lines = 30 if not meta.get("passed") else 5
                lines = feedback.split("\n")
                for line in lines[:max_lines]:
                    if line.strip():
                        print(f"{'':20} {line}")
                if len(lines) > max_lines:
                    print(f"{'':20} ... ({len(lines) - max_lines} more lines)")

        elif event_type == "phase_change":
            meta = event.get("metadata", {})
            old_phase = meta.get("old_phase", "?")
            new_phase = meta.get("new_phase", "?")
            print(f"{timestamp} [>>>] PHASE: {old_phase} -> {new_phase}")

        elif event_type == "escalation":
            print(f"{timestamp} [!!!] ESCALATION: {event.get('input_summary', '')}")

        elif event_type == "decision":
            decision = event.get("input_summary", "")
            rationale = event.get("output_summary", "")
            print(f"{timestamp} [DEC] {agent}: {decision}")
            if rationale:
                lines = rationale.split("\n")
                for line in lines[:5]:
                    if line.strip():
                        print(f"{'':20} {line}")

        else:
            print(f"{timestamp} [{event_type}] {agent}")

    def display_summary(self):
        """Display summary statistics"""
        if not self.session_id:
            print("No session found")
            return

        events = read_session_events(self.project_dir, self.session_id)

        agent_calls = sum(1 for e in events if e.get("event_type") == "agent_call")
        gate_votes = sum(1 for e in events if e.get("event_type") == "gate_vote")
        total_tokens = sum(e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in events)
        total_cost = sum(e.get("cost_usd", 0) for e in events)

        print(f"\nSession Summary: {self.session_id}")
        print(f"  Events: {len(events)}")
        print(f"  Agent Calls: {agent_calls}")
        print(f"  Gate Votes: {gate_votes}")
        print(f"  Total Tokens: {total_tokens}")
        print(f"  Total Cost: ${total_cost:.4f}")


class WebMonitor:
    """Web-based monitor with live dashboard"""

    def __init__(self, project_dir: Path, port: int = 8765, session_id: Optional[str] = None):
        self.project_dir = Path(project_dir)
        self.port = port
        self.session_id = session_id
        self.server = None
        self.running = False

    def start(self, open_browser: bool = True):
        """Start the web monitor server"""
        handler = self._create_handler()
        self.server = HTTPServer(("localhost", self.port), handler)
        self.running = True

        print(f"Web monitor: http://localhost:{self.port}")
        print(f"Project: {self.project_dir.name}")
        print(f"Session: {self.session_id}")

        if open_browser:
            webbrowser.open(f"http://localhost:{self.port}")

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping web monitor...")
            self.running = False

    def stop(self):
        """Stop the web monitor server"""
        if self.server:
            self.server.shutdown()
            self.running = False

    def _create_handler(self):
        """Create HTTP request handler"""
        project_dir = self.project_dir
        fixed_session_id = self.session_id

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == "/":
                    self._serve_html()
                elif self.path == "/admin":
                    self._serve_admin_html()
                elif self.path == "/api/data":
                    self._serve_data()
                elif self.path == "/api/events":
                    self._serve_events()
                elif self.path == "/api/admin":
                    self._serve_admin_data()
                else:
                    self.send_error(404)

            def _serve_html(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()

                html = """<!DOCTYPE html>
<html>
<head>
    <title>AI-Dev Monitor</title>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        h1 { color: #00d4ff; margin-bottom: 20px; }
        .status { background: #252545; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .status span { margin-right: 30px; }
        .status .label { color: #888; }
        .status .value { color: #fff; font-weight: bold; }
        .stats { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        .stat { background: #252545; padding: 15px 25px; border-radius: 8px; text-align: center; min-width: 120px; }
        .stat .num { font-size: 2em; font-weight: bold; color: #00d4ff; }
        .stat .lbl { color: #888; font-size: 0.9em; }
        .stat.cost .num { color: #00ff88; }
        .stat .sub { color: #666; font-size: 0.75em; margin-top: 4px; }
        .events { background: #252545; border-radius: 8px; padding: 15px; }
        .events h2 { margin-bottom: 15px; color: #00d4ff; }
        .event { padding: 10px; border-bottom: 1px solid #333; font-family: monospace; font-size: 0.9em; }
        .event:last-child { border-bottom: none; }
        .event .time { color: #888; }
        .event .type { color: #00d4ff; font-weight: bold; }
        .event .agent { color: #ffd700; }
        .event .ok { color: #00ff88; }
        .event .fail { color: #ff6b6b; }
        .event .detail { color: #aaa; margin-top: 5px; white-space: pre-wrap; }
        .event .tokens { color: #888; font-size: 0.85em; }
        .event .cost { color: #00ff88; font-size: 0.85em; }
        .refresh { color: #888; font-size: 0.8em; margin-top: 10px; }
        #error { color: #ff6b6b; padding: 10px; display: none; }
    </style>
</head>
<body>
    <h1>AI-Dev-Workflow Monitor</h1>
    <div id="error"></div>
    <div class="status">
        <span><span class="label">Project:</span> <span class="value" id="project">-</span></span>
        <span><span class="label">Session:</span> <span class="value" id="session">-</span></span>
        <span><span class="label">Phase:</span> <span class="value" id="phase">-</span></span>
    </div>
    <div class="stats">
        <div class="stat"><div class="num" id="agents">0</div><div class="lbl">Agent Calls</div></div>
        <div class="stat"><div class="num" id="gates">0</div><div class="lbl">Gate Votes</div></div>
        <div class="stat">
            <div class="num" id="tokens">0</div>
            <div class="lbl">Total Tokens</div>
            <div class="sub" id="token-breakdown">In: 0 | Out: 0</div>
        </div>
        <div class="stat cost">
            <div class="num" id="cost">$0.00</div>
            <div class="lbl">Session Cost</div>
            <div class="sub" id="cost-rate">$0.00/min</div>
        </div>
    </div>
    <div class="events">
        <h2>Activity Feed</h2>
        <div id="feed">Loading...</div>
    </div>
    <div class="refresh">Auto-refreshes every 2 seconds | <a href="/admin" style="color:#00d4ff">Admin Console</a></div>
    <script>
        var startTime = null;
        function formatNumber(n) {
            if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n/1000).toFixed(1) + 'K';
            return n.toString();
        }
        function load() {
            fetch('/api/data')
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    document.getElementById('error').style.display = 'none';
                    document.getElementById('project').textContent = d.project || '-';
                    document.getElementById('session').textContent = d.session || '-';
                    document.getElementById('phase').textContent = d.phase || '-';
                    document.getElementById('agents').textContent = d.agent_calls || 0;
                    document.getElementById('gates').textContent = d.gate_votes || 0;
                    document.getElementById('tokens').textContent = formatNumber(d.tokens || 0);
                    document.getElementById('token-breakdown').textContent = 'In: ' + formatNumber(d.input_tokens || 0) + ' | Out: ' + formatNumber(d.output_tokens || 0);
                    document.getElementById('cost').textContent = '$' + (d.cost || 0).toFixed(4);

                    // Calculate cost rate
                    if (d.session_start && d.cost > 0) {
                        var elapsed = (Date.now() - new Date(d.session_start).getTime()) / 60000;
                        if (elapsed > 0.1) {
                            var rate = d.cost / elapsed;
                            document.getElementById('cost-rate').textContent = '$' + rate.toFixed(4) + '/min';
                        }
                    }

                    var feed = document.getElementById('feed');
                    if (d.events && d.events.length > 0) {
                        var html = '';
                        var recent = d.events.slice(-50).reverse();
                        for (var i = 0; i < recent.length; i++) {
                            var e = recent[i];
                            var time = (e.timestamp || '').substring(11, 19);
                            var type = e.event_type || 'unknown';
                            var agent = e.agent || '-';
                            var status = e.status === 'success' ? 'ok' : (e.status === 'failure' ? 'fail' : '');
                            var statusText = e.status === 'success' ? '[OK]' : (e.status === 'failure' ? '[FAIL]' : '[-]');
                            var detail = e.output_summary || '';
                            var inTok = e.input_tokens || 0;
                            var outTok = e.output_tokens || 0;
                            var evtCost = e.cost_usd || 0;

                            html += '<div class="event">';
                            html += '<span class="time">' + time + '</span> ';
                            html += '<span class="' + status + '">' + statusText + '</span> ';
                            html += '<span class="type">' + type + '</span> ';
                            html += '<span class="agent">' + agent + '</span>';
                            if (inTok > 0 || outTok > 0 || evtCost > 0) {
                                html += ' <span class="tokens">[' + inTok + '/' + outTok + ' tok]</span>';
                                html += ' <span class="cost">$' + evtCost.toFixed(4) + '</span>';
                            }
                            if (detail) {
                                html += '<div class="detail">' + detail.substring(0, 500) + '</div>';
                            }
                            html += '</div>';
                        }
                        feed.innerHTML = html;
                    } else {
                        feed.innerHTML = '<div class="event">Waiting for events...</div>';
                    }
                })
                .catch(function(err) {
                    document.getElementById('error').textContent = 'Error: ' + err.message;
                    document.getElementById('error').style.display = 'block';
                });
        }
        load();
        setInterval(load, 2000);
    </script>
</body>
</html>"""
                self.wfile.write(html.encode())

            def _serve_data(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                session_id = fixed_session_id or get_latest_session(project_dir)
                events = read_session_events(project_dir, session_id) if session_id else []

                # Find current phase and session start
                phase = "unknown"
                session_start = None
                for e in events:
                    if not session_start and e.get("timestamp"):
                        session_start = e.get("timestamp")
                for e in reversed(events):
                    if e.get("event_type") == "phase_change":
                        phase = e.get("metadata", {}).get("new_phase", "unknown")
                        break

                input_tokens = sum(e.get("input_tokens", 0) for e in events)
                output_tokens = sum(e.get("output_tokens", 0) for e in events)

                data = {
                    "project": project_dir.name,
                    "session": session_id or "none",
                    "phase": phase,
                    "session_start": session_start,
                    "agent_calls": sum(1 for e in events if e.get("event_type") == "agent_call"),
                    "gate_votes": sum(1 for e in events if e.get("event_type") == "gate_vote"),
                    "tokens": input_tokens + output_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": sum(e.get("cost_usd", 0) for e in events),
                    "events": events
                }

                self.wfile.write(json.dumps(data).encode())

            def _serve_events(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                session_id = fixed_session_id or get_latest_session(project_dir)
                events = read_session_events(project_dir, session_id) if session_id else []
                self.wfile.write(json.dumps(events).encode())

            def _serve_admin_html(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                admin_html = """<!DOCTYPE html>
<html>
<head>
    <title>AI-Dev Admin Console</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #0f0f1a; color: #eee; display: flex; }
        .sidebar { width: 200px; background: #1a1a2e; min-height: 100vh; padding: 20px 0; border-right: 1px solid #252545; position: fixed; }
        .sidebar h2 { color: #00d4ff; font-size: 1.1em; padding: 0 20px; margin-bottom: 20px; }
        .sidebar a { display: block; padding: 12px 20px; color: #aaa; text-decoration: none; border-left: 3px solid transparent; }
        .sidebar a:hover { background: #252545; color: #fff; }
        .sidebar a.active { background: #252545; color: #00d4ff; border-left-color: #00d4ff; }
        .sidebar .icon { margin-right: 10px; }
        .main { margin-left: 200px; padding: 20px; flex: 1; }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 20px; }
        .totals { display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }
        .total { background: linear-gradient(135deg, #252545 0%, #1a1a2e 100%); padding: 20px 30px; border-radius: 12px; min-width: 180px; border: 1px solid #333; }
        .total .num { font-size: 2.5em; font-weight: bold; color: #00ff88; }
        .total .lbl { color: #888; font-size: 0.9em; margin-top: 5px; }
        .total .sub { color: #666; font-size: 0.8em; margin-top: 8px; }
        .total.tokens .num { color: #00d4ff; }
        .section { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #252545; }
        .section h2 { color: #00d4ff; margin-bottom: 15px; font-size: 1.2em; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 12px; color: #888; border-bottom: 1px solid #333; font-weight: normal; }
        td { padding: 12px; border-bottom: 1px solid #252545; }
        tr:hover { background: #252545; }
        .cost { color: #00ff88; font-weight: bold; }
        .tokens { color: #00d4ff; }
        .date { color: #888; }
        .project-name { color: #ffd700; }
        .refresh { color: #888; font-size: 0.8em; margin-top: 10px; }
        a { color: #00d4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .chart { height: 200px; background: #252545; border-radius: 8px; margin-top: 15px; display: flex; align-items: flex-end; padding: 10px; gap: 2px; }
        .bar { background: linear-gradient(180deg, #00d4ff 0%, #0088aa 100%); min-width: 20px; border-radius: 3px 3px 0 0; transition: height 0.3s; }
        .bar:hover { background: linear-gradient(180deg, #00ff88 0%, #00aa66 100%); }
        .chart-label { text-align: center; color: #666; font-size: 0.7em; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>AI-Dev Workflow</h2>
        <a href="/"><span class="icon">&#9776;</span> Monitor</a>
        <a href="/admin" class="active"><span class="icon">&#9881;</span> Admin</a>
    </div>
    <div class="main">
    <h1>Admin Console</h1>
    <div class="subtitle">Claude API Usage Tracking Across All Projects</div>

    <div class="totals">
        <div class="total">
            <div class="num" id="total-cost">$0.00</div>
            <div class="lbl">Total Cost (All Time)</div>
            <div class="sub" id="today-cost">Today: $0.00</div>
        </div>
        <div class="total tokens">
            <div class="num" id="total-tokens">0</div>
            <div class="lbl">Total Tokens</div>
            <div class="sub" id="token-split">In: 0 | Out: 0</div>
        </div>
        <div class="total">
            <div class="num" id="total-sessions">0</div>
            <div class="lbl">Total Sessions</div>
            <div class="sub" id="projects-count">0 projects</div>
        </div>
        <div class="total">
            <div class="num" id="avg-cost">$0.00</div>
            <div class="lbl">Avg Cost/Session</div>
            <div class="sub" id="cost-range">-</div>
        </div>
    </div>

    <div class="section">
        <h2>Daily Cost (Last 7 Days)</h2>
        <div class="chart" id="daily-chart"></div>
    </div>

    <div class="section">
        <h2>Projects</h2>
        <table>
            <thead>
                <tr>
                    <th>Project</th>
                    <th>Sessions</th>
                    <th>Total Tokens</th>
                    <th>Total Cost</th>
                    <th>Last Activity</th>
                </tr>
            </thead>
            <tbody id="projects-table">
                <tr><td colspan="5">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Recent Sessions</h2>
        <table>
            <thead>
                <tr>
                    <th>Session</th>
                    <th>Project</th>
                    <th>Date</th>
                    <th>Agent Calls</th>
                    <th>Tokens</th>
                    <th>Cost</th>
                </tr>
            </thead>
            <tbody id="sessions-table">
                <tr><td colspan="6">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <div class="refresh">Auto-refreshes every 10 seconds</div>

    <script>
        function formatNumber(n) {
            if (n >= 1000000) return (n/1000000).toFixed(2) + 'M';
            if (n >= 1000) return (n/1000).toFixed(1) + 'K';
            return n.toString();
        }
        function formatDate(d) {
            if (!d) return '-';
            return d.substring(0, 10) + ' ' + d.substring(11, 16);
        }
        function load() {
            fetch('/api/admin')
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    // Totals
                    document.getElementById('total-cost').textContent = '$' + (d.total_cost || 0).toFixed(4);
                    document.getElementById('today-cost').textContent = 'Today: $' + (d.today_cost || 0).toFixed(4);
                    document.getElementById('total-tokens').textContent = formatNumber(d.total_tokens || 0);
                    document.getElementById('token-split').textContent = 'In: ' + formatNumber(d.total_input_tokens || 0) + ' | Out: ' + formatNumber(d.total_output_tokens || 0);
                    document.getElementById('total-sessions').textContent = d.total_sessions || 0;
                    document.getElementById('projects-count').textContent = (d.total_projects || 0) + ' projects';
                    var avgCost = d.total_sessions > 0 ? d.total_cost / d.total_sessions : 0;
                    document.getElementById('avg-cost').textContent = '$' + avgCost.toFixed(4);
                    if (d.min_session_cost !== undefined && d.max_session_cost !== undefined) {
                        document.getElementById('cost-range').textContent = 'Range: $' + d.min_session_cost.toFixed(4) + ' - $' + d.max_session_cost.toFixed(4);
                    }

                    // Daily chart
                    var chartHtml = '';
                    var dailyCosts = d.daily_costs || [];
                    var maxCost = Math.max.apply(null, dailyCosts.map(function(x) { return x.cost; })) || 1;
                    for (var i = 0; i < dailyCosts.length; i++) {
                        var day = dailyCosts[i];
                        var height = Math.max(5, (day.cost / maxCost) * 180);
                        chartHtml += '<div style="flex:1;text-align:center;">';
                        chartHtml += '<div class="bar" style="height:' + height + 'px" title="' + day.date + ': $' + day.cost.toFixed(4) + '"></div>';
                        chartHtml += '<div class="chart-label">' + day.date.substring(5) + '</div>';
                        chartHtml += '</div>';
                    }
                    document.getElementById('daily-chart').innerHTML = chartHtml || '<div style="color:#666;padding:20px;">No data</div>';

                    // Projects table
                    var projectsHtml = '';
                    var projects = d.projects || [];
                    for (var i = 0; i < projects.length; i++) {
                        var p = projects[i];
                        projectsHtml += '<tr>';
                        projectsHtml += '<td class="project-name">' + p.name + '</td>';
                        projectsHtml += '<td>' + p.sessions + '</td>';
                        projectsHtml += '<td class="tokens">' + formatNumber(p.tokens) + '</td>';
                        projectsHtml += '<td class="cost">$' + p.cost.toFixed(4) + '</td>';
                        projectsHtml += '<td class="date">' + formatDate(p.last_activity) + '</td>';
                        projectsHtml += '</tr>';
                    }
                    document.getElementById('projects-table').innerHTML = projectsHtml || '<tr><td colspan="5">No projects</td></tr>';

                    // Sessions table
                    var sessionsHtml = '';
                    var sessions = d.sessions || [];
                    for (var i = 0; i < Math.min(sessions.length, 20); i++) {
                        var s = sessions[i];
                        sessionsHtml += '<tr>';
                        sessionsHtml += '<td>' + s.session_id.substring(0, 16) + '</td>';
                        sessionsHtml += '<td class="project-name">' + s.project + '</td>';
                        sessionsHtml += '<td class="date">' + formatDate(s.started_at) + '</td>';
                        sessionsHtml += '<td>' + s.agent_calls + '</td>';
                        sessionsHtml += '<td class="tokens">' + formatNumber(s.tokens) + '</td>';
                        sessionsHtml += '<td class="cost">$' + s.cost.toFixed(4) + '</td>';
                        sessionsHtml += '</tr>';
                    }
                    document.getElementById('sessions-table').innerHTML = sessionsHtml || '<tr><td colspan="6">No sessions</td></tr>';
                })
                .catch(function(err) {
                    console.error('Admin data error:', err);
                });
        }
        load();
        setInterval(load, 10000);
    </script>
    </div>
</body>
</html>"""
                self.wfile.write(admin_html.encode())

            def _serve_admin_data(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                # Collect data from all projects
                from core.admin import AdminTracker
                tracker = AdminTracker(project_dir.parent)
                data = tracker.get_summary()
                self.wfile.write(json.dumps(data).encode())

        return Handler


class StandaloneServer:
    """Standalone web server for dashboard access without active workflow"""

    def __init__(self, projects_dir: Path, port: int = 8765):
        self.projects_dir = Path(projects_dir)
        self.port = port
        self.server = None

    def start(self, open_browser: bool = True):
        """Start the standalone server"""
        handler = self._create_handler()
        self.server = HTTPServer(("localhost", self.port), handler)

        print(f"Dashboard server running on http://localhost:{self.port}")

        if open_browser:
            webbrowser.open(f"http://localhost:{self.port}/admin")

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

    def _create_handler(self):
        """Create HTTP request handler for standalone mode"""
        projects_dir = self.projects_dir

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress logging

            def do_GET(self):
                if self.path == "/":
                    self._serve_monitor_html()
                elif self.path == "/admin":
                    self._serve_admin_html()
                elif self.path == "/api/data":
                    self._serve_monitor_data()
                elif self.path == "/api/admin":
                    self._serve_admin_data()
                else:
                    self.send_error(404)

            def _serve_monitor_html(self):
                """Serve monitor page - shows waiting state or active session"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                html = """<!DOCTYPE html>
<html>
<head>
    <title>AI-Dev Monitor</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; display: flex; }
        .sidebar { width: 200px; background: #151525; min-height: 100vh; padding: 20px 0; border-right: 1px solid #252545; position: fixed; }
        .sidebar h2 { color: #00d4ff; font-size: 1.1em; padding: 0 20px; margin-bottom: 20px; }
        .sidebar a { display: block; padding: 12px 20px; color: #aaa; text-decoration: none; border-left: 3px solid transparent; }
        .sidebar a:hover { background: #252545; color: #fff; }
        .sidebar a.active { background: #252545; color: #00d4ff; border-left-color: #00d4ff; }
        .sidebar .icon { margin-right: 10px; }
        .main { margin-left: 200px; padding: 20px; flex: 1; }
        h1 { color: #00d4ff; margin-bottom: 20px; }
        .status { background: #252545; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .status span { margin-right: 30px; }
        .status .label { color: #888; }
        .status .value { color: #fff; font-weight: bold; }
        .stats { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        .stat { background: #252545; padding: 15px 25px; border-radius: 8px; text-align: center; min-width: 120px; }
        .stat .num { font-size: 2em; font-weight: bold; color: #00d4ff; }
        .stat .lbl { color: #888; font-size: 0.9em; }
        .stat.cost .num { color: #00ff88; }
        .stat .sub { color: #666; font-size: 0.75em; margin-top: 4px; }
        .events { background: #252545; border-radius: 8px; padding: 15px; }
        .events h2 { margin-bottom: 15px; color: #00d4ff; }
        .event { padding: 10px; border-bottom: 1px solid #333; font-family: monospace; font-size: 0.9em; }
        .event:last-child { border-bottom: none; }
        .event .time { color: #888; }
        .event .type { color: #00d4ff; font-weight: bold; }
        .event .agent { color: #ffd700; }
        .event .ok { color: #00ff88; }
        .event .fail { color: #ff6b6b; }
        .event .tokens { color: #888; font-size: 0.85em; }
        .event .cost { color: #00ff88; font-size: 0.85em; }
        .event .detail { color: #aaa; margin-top: 8px; white-space: pre-wrap; font-size: 0.85em; line-height: 1.4; background: #1a1a2e; padding: 10px; border-radius: 4px; }
        .waiting { text-align: center; padding: 60px 20px; }
        .waiting .icon { font-size: 4em; margin-bottom: 20px; }
        .waiting h2 { color: #888; margin-bottom: 10px; }
        .waiting p { color: #666; }
        .refresh { color: #888; font-size: 0.8em; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>AI-Dev Workflow</h2>
        <a href="/" class="active"><span class="icon">&#9776;</span> Monitor</a>
        <a href="/admin"><span class="icon">&#9881;</span> Admin</a>
    </div>
    <div class="main">
    <h1>Session Monitor</h1>
    <div id="content">
        <div class="waiting">
            <div class="icon">&#128260;</div>
            <h2>Waiting for workflow...</h2>
            <p>Start a workflow to see real-time activity</p>
        </div>
    </div>
    <div class="refresh">Auto-refreshes every 2 seconds</div>
    </div>
    <script>
        var lastEventCount = 0;
        function formatNumber(n) {
            if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n/1000).toFixed(1) + 'K';
            return n.toString();
        }
        function load() {
            var scrollY = window.scrollY;
            fetch('/api/data')
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (!d.session || d.session === 'none' || !d.events || d.events.length === 0) {
                        document.getElementById('content').innerHTML = '<div class="waiting"><div class="icon">&#128260;</div><h2>Waiting for workflow...</h2><p>Start a workflow to see real-time activity</p></div>';
                        return;
                    }
                    var eventCount = d.events ? d.events.length : 0;
                    var html = '<div class="status">';
                    html += '<span><span class="label">Project:</span> <span class="value">' + (d.project || '-') + '</span></span>';
                    html += '<span><span class="label">Session:</span> <span class="value">' + (d.session || '-') + '</span></span>';
                    html += '<span><span class="label">Phase:</span> <span class="value">' + (d.phase || '-') + '</span></span>';
                    html += '</div>';
                    html += '<div class="stats">';
                    html += '<div class="stat"><div class="num">' + (d.agent_calls || 0) + '</div><div class="lbl">Agent Calls</div></div>';
                    html += '<div class="stat"><div class="num">' + (d.gate_votes || 0) + '</div><div class="lbl">Gate Votes</div></div>';
                    html += '<div class="stat"><div class="num">' + formatNumber(d.tokens || 0) + '</div><div class="lbl">Total Tokens</div><div class="sub">In: ' + formatNumber(d.input_tokens || 0) + ' | Out: ' + formatNumber(d.output_tokens || 0) + '</div></div>';
                    html += '<div class="stat cost"><div class="num">$' + (d.cost || 0).toFixed(4) + '</div><div class="lbl">Session Cost</div></div>';
                    html += '</div>';
                    html += '<div class="events"><h2>Activity Feed (' + eventCount + ' events)</h2><div id="feed">';
                    if (d.events && d.events.length > 0) {
                        var recent = d.events.slice(-100).reverse();
                        for (var i = 0; i < recent.length; i++) {
                            var e = recent[i];
                            var time = (e.timestamp || '').substring(11, 19);
                            var type = e.event_type || 'unknown';
                            var agent = e.agent || '-';
                            var status = e.status === 'success' ? 'ok' : (e.status === 'failure' ? 'fail' : '');
                            var statusText = e.status === 'success' ? '[OK]' : (e.status === 'failure' ? '[FAIL]' : '[-]');
                            var inTok = e.input_tokens || 0;
                            var outTok = e.output_tokens || 0;
                            var evtCost = e.cost_usd || 0;
                            var detail = e.output_summary || '';
                            var duration = e.duration_ms || 0;
                            html += '<div class="event">';
                            html += '<span class="time">' + time + '</span> ';
                            html += '<span class="' + status + '">' + statusText + '</span> ';
                            html += '<span class="type">' + type + '</span> ';
                            html += '<span class="agent">' + agent + '</span>';
                            if (duration > 0) html += ' <span class="tokens">' + duration + 'ms</span>';
                            if (inTok > 0 || outTok > 0) html += ' <span class="tokens">[' + inTok + '/' + outTok + ' tok]</span>';
                            if (evtCost > 0) html += ' <span class="cost">$' + evtCost.toFixed(4) + '</span>';
                            if (detail) html += '<div class="detail">' + detail.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</div>';
                            html += '</div>';
                        }
                    }
                    html += '</div></div>';
                    document.getElementById('content').innerHTML = html;
                    // Restore scroll position
                    window.scrollTo(0, scrollY);
                    lastEventCount = eventCount;
                })
                .catch(function(err) { console.error(err); });
        }
        load();
        setInterval(load, 2000);
    </script>
</body>
</html>"""
                self.wfile.write(html.encode())

            def _serve_monitor_data(self):
                """Serve monitor data - find most recent active session"""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                # Find most recent session across all projects
                best_session = None
                best_project = None
                best_time = None

                for project_dir in projects_dir.iterdir():
                    if project_dir.is_dir():
                        audit_dir = project_dir / "audit"
                        if audit_dir.exists():
                            for session_file in audit_dir.glob("session_*.jsonl"):
                                # Get modification time
                                mtime = session_file.stat().st_mtime
                                if best_time is None or mtime > best_time:
                                    best_time = mtime
                                    best_session = session_file.stem.replace("session_", "")
                                    best_project = project_dir

                if not best_session or not best_project:
                    self.wfile.write(json.dumps({"session": None, "events": []}).encode())
                    return

                # Read the session
                events = read_session_events(best_project, best_session)

                # Find phase
                phase = "unknown"
                session_start = None
                for e in events:
                    if not session_start and e.get("timestamp"):
                        session_start = e.get("timestamp")
                for e in reversed(events):
                    if e.get("event_type") == "phase_change":
                        phase = e.get("metadata", {}).get("new_phase", "unknown")
                        break

                input_tokens = sum(e.get("input_tokens", 0) for e in events)
                output_tokens = sum(e.get("output_tokens", 0) for e in events)

                data = {
                    "project": best_project.name,
                    "session": best_session,
                    "phase": phase,
                    "session_start": session_start,
                    "agent_calls": sum(1 for e in events if e.get("event_type") == "agent_call"),
                    "gate_votes": sum(1 for e in events if e.get("event_type") == "gate_vote"),
                    "tokens": input_tokens + output_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": sum(e.get("cost_usd", 0) for e in events),
                    "events": events[-100:] if events else []  # Last 100 events
                }
                self.wfile.write(json.dumps(data).encode())

            def _serve_admin_html(self):
                """Serve admin page"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                admin_html = """<!DOCTYPE html>
<html>
<head>
    <title>AI-Dev Admin Console</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #0f0f1a; color: #eee; display: flex; }
        .sidebar { width: 200px; background: #1a1a2e; min-height: 100vh; padding: 20px 0; border-right: 1px solid #252545; position: fixed; }
        .sidebar h2 { color: #00d4ff; font-size: 1.1em; padding: 0 20px; margin-bottom: 20px; }
        .sidebar a { display: block; padding: 12px 20px; color: #aaa; text-decoration: none; border-left: 3px solid transparent; }
        .sidebar a:hover { background: #252545; color: #fff; }
        .sidebar a.active { background: #252545; color: #00d4ff; border-left-color: #00d4ff; }
        .sidebar .icon { margin-right: 10px; }
        .main { margin-left: 200px; padding: 20px; flex: 1; }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 20px; }
        .totals { display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }
        .total { background: linear-gradient(135deg, #252545 0%, #1a1a2e 100%); padding: 20px 30px; border-radius: 12px; min-width: 180px; border: 1px solid #333; }
        .total .num { font-size: 2.5em; font-weight: bold; color: #00ff88; }
        .total .lbl { color: #888; font-size: 0.9em; margin-top: 5px; }
        .total .sub { color: #666; font-size: 0.8em; margin-top: 8px; }
        .total.tokens .num { color: #00d4ff; }
        .section { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #252545; }
        .section h2 { color: #00d4ff; margin-bottom: 15px; font-size: 1.2em; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 12px; color: #888; border-bottom: 1px solid #333; font-weight: normal; }
        td { padding: 12px; border-bottom: 1px solid #252545; }
        tr:hover { background: #252545; }
        .cost { color: #00ff88; font-weight: bold; }
        .tokens { color: #00d4ff; }
        .date { color: #888; }
        .project-name { color: #ffd700; }
        .refresh { color: #888; font-size: 0.8em; margin-top: 10px; }
        a { color: #00d4ff; text-decoration: none; }
        .chart { height: 200px; background: #252545; border-radius: 8px; margin-top: 15px; display: flex; align-items: flex-end; padding: 10px; gap: 2px; }
        .bar { background: linear-gradient(180deg, #00d4ff 0%, #0088aa 100%); min-width: 20px; border-radius: 3px 3px 0 0; }
        .bar:hover { background: linear-gradient(180deg, #00ff88 0%, #00aa66 100%); }
        .chart-label { text-align: center; color: #666; font-size: 0.7em; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>AI-Dev Workflow</h2>
        <a href="/"><span class="icon">&#9776;</span> Monitor</a>
        <a href="/admin" class="active"><span class="icon">&#9881;</span> Admin</a>
    </div>
    <div class="main">
    <h1>Admin Console</h1>
    <div class="subtitle">Claude API Usage Tracking Across All Projects</div>
    <div class="totals">
        <div class="total"><div class="num" id="total-cost">$0.00</div><div class="lbl">Total Cost</div><div class="sub" id="today-cost">Today: $0.00</div></div>
        <div class="total tokens"><div class="num" id="total-tokens">0</div><div class="lbl">Total Tokens</div><div class="sub" id="token-split">In: 0 | Out: 0</div></div>
        <div class="total"><div class="num" id="total-sessions">0</div><div class="lbl">Sessions</div><div class="sub" id="projects-count">0 projects</div></div>
        <div class="total"><div class="num" id="avg-cost">$0.00</div><div class="lbl">Avg/Session</div></div>
    </div>
    <div class="section"><h2>Daily Cost (Last 7 Days)</h2><div class="chart" id="daily-chart"></div></div>
    <div class="section"><h2>Projects</h2>
        <table><thead><tr><th>Project</th><th>Sessions</th><th>Tokens</th><th>Cost</th><th>Last Activity</th></tr></thead>
        <tbody id="projects-table"><tr><td colspan="5">Loading...</td></tr></tbody></table>
    </div>
    <div class="section"><h2>Recent Sessions</h2>
        <table><thead><tr><th>Session</th><th>Project</th><th>Date</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr></thead>
        <tbody id="sessions-table"><tr><td colspan="6">Loading...</td></tr></tbody></table>
    </div>
    <div class="refresh">Auto-refreshes every 10 seconds</div>
    </div>
    <script>
        function fmt(n) { return n >= 1e6 ? (n/1e6).toFixed(2)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : n.toString(); }
        function fmtDate(d) { return d ? d.substring(0,10)+' '+d.substring(11,16) : '-'; }
        function load() {
            fetch('/api/admin').then(r=>r.json()).then(d=>{
                document.getElementById('total-cost').textContent = '$'+(d.total_cost||0).toFixed(4);
                document.getElementById('today-cost').textContent = 'Today: $'+(d.today_cost||0).toFixed(4);
                document.getElementById('total-tokens').textContent = fmt(d.total_tokens||0);
                document.getElementById('token-split').textContent = 'In: '+fmt(d.total_input_tokens||0)+' | Out: '+fmt(d.total_output_tokens||0);
                document.getElementById('total-sessions').textContent = d.total_sessions||0;
                document.getElementById('projects-count').textContent = (d.total_projects||0)+' projects';
                document.getElementById('avg-cost').textContent = '$'+(d.total_sessions>0?d.total_cost/d.total_sessions:0).toFixed(4);
                var ch='',dc=d.daily_costs||[],mx=Math.max.apply(null,dc.map(x=>x.cost))||1;
                for(var i=0;i<dc.length;i++){var h=Math.max(5,(dc[i].cost/mx)*180);ch+='<div style="flex:1;text-align:center"><div class="bar" style="height:'+h+'px" title="'+dc[i].date+': $'+dc[i].cost.toFixed(4)+'"></div><div class="chart-label">'+dc[i].date.substring(5)+'</div></div>';}
                document.getElementById('daily-chart').innerHTML=ch||'<div style="color:#666;padding:20px">No data</div>';
                var ph='',ps=d.projects||[];for(var i=0;i<ps.length;i++){var p=ps[i];ph+='<tr><td class="project-name">'+p.name+'</td><td>'+p.sessions+'</td><td class="tokens">'+fmt(p.tokens)+'</td><td class="cost">$'+p.cost.toFixed(4)+'</td><td class="date">'+fmtDate(p.last_activity)+'</td></tr>';}
                document.getElementById('projects-table').innerHTML=ph||'<tr><td colspan="5">No projects</td></tr>';
                var sh='',ss=d.sessions||[];for(var i=0;i<Math.min(ss.length,20);i++){var s=ss[i];sh+='<tr><td>'+s.session_id.substring(0,16)+'</td><td class="project-name">'+s.project+'</td><td class="date">'+fmtDate(s.started_at)+'</td><td>'+s.agent_calls+'</td><td class="tokens">'+fmt(s.tokens)+'</td><td class="cost">$'+s.cost.toFixed(4)+'</td></tr>';}
                document.getElementById('sessions-table').innerHTML=sh||'<tr><td colspan="6">No sessions</td></tr>';
            }).catch(e=>console.error(e));
        }
        load();setInterval(load,10000);
    </script>
</body>
</html>"""
                self.wfile.write(admin_html.encode())

            def _serve_admin_data(self):
                """Serve admin data"""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                from core.admin import AdminTracker
                tracker = AdminTracker(projects_dir)
                data = tracker.get_summary()
                self.wfile.write(json.dumps(data).encode())

        return Handler
