"""
Report Generator - Creates HTML reports for Assessment and Planning phases
"""

from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from typing import List

from core.assessment import AssessmentReport, CategoryScore, Finding
from core.ingest_planner import PlanningReport, RoadmapItem, AIOpportunity, Milestone


class ReportGenerator:
    """Generates beautiful HTML reports"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_assessment_report(self, report: AssessmentReport) -> Path:
        """Generate Phase 1 Assessment Report HTML"""
        
        html = self._header(f"Assessment Report: {report.project_name}")
        
        # Executive Summary
        html += f'''
        <div class="section">
            <h2>📊 Executive Summary</h2>
            <div class="summary-grid">
                <div class="card {report.overall_status}">
                    <div class="big-number">{report.overall_score}</div>
                    <div class="label">Overall Score</div>
                    <div class="status">{report.overall_status.upper()}</div>
                </div>
                <div class="card">
                    <div class="big-number">{len(report.all_findings)}</div>
                    <div class="label">Total Findings</div>
                </div>
                <div class="card critical">
                    <div class="big-number">{report.critical_count}</div>
                    <div class="label">Critical</div>
                </div>
                <div class="card warning">
                    <div class="big-number">{report.high_count}</div>
                    <div class="label">High Priority</div>
                </div>
                <div class="card ai">
                    <div class="big-number">{report.ai_fixable_count}</div>
                    <div class="label">AI Can Fix</div>
                </div>
            </div>
        </div>
        '''
        
        # Category Scores
        html += '<div class="section"><h2>📈 Category Scores</h2><div class="categories">'
        
        categories = [
            ("🏗️ Architecture", report.architecture),
            ("💎 Code Quality", report.code_quality),
            ("📦 Tech Debt", report.tech_debt),
            ("🔒 Security", report.security),
            ("🧭 Navigation", report.ux_navigation),
            ("🎨 Styling", report.ux_styling),
            ("♿ Accessibility", report.ux_accessibility),
            ("⚡ Performance", report.performance),
            ("🧪 Testing", report.testing),
            ("📚 Documentation", report.documentation),
        ]
        
        for icon_name, cat in categories:
            html += self._category_card(icon_name, cat)
        
        html += '</div></div>'
        
        # Critical Findings
        critical = [f for f in report.all_findings if f.severity == 'critical']
        if critical:
            html += '<div class="section critical-bg"><h2>🚨 Critical Findings</h2>'
            html += '<p class="muted">These must be addressed immediately.</p>'
            html += '<div class="findings">'
            for f in critical:
                html += self._finding_card(f)
            html += '</div></div>'
        
        # High Priority
        high = [f for f in report.all_findings if f.severity == 'high']
        if high:
            html += '<div class="section"><h2>⚠️ High Priority</h2><div class="findings">'
            for f in high[:10]:
                html += self._finding_card(f)
            html += '</div></div>'
        
        # AI Opportunities
        ai = [f for f in report.all_findings if f.ai_can_fix]
        if ai:
            html += '<div class="section ai-bg"><h2>🤖 AI Can Help</h2>'
            html += '<p class="muted">These issues can be addressed with AI assistance.</p>'
            html += '<div class="findings">'
            for f in ai[:10]:
                html += self._finding_card(f, show_ai=True)
            html += '</div></div>'
        
        # All Findings Table
        html += '<div class="section"><h2>📋 All Findings</h2>'
        html += '<table class="findings-table"><thead><tr>'
        html += '<th>ID</th><th>Category</th><th>Severity</th><th>Title</th><th>Effort</th><th>AI</th>'
        html += '</tr></thead><tbody>'
        
        for f in report.all_findings:
            ai_badge = '🤖' if f.ai_can_fix else ''
            html += f'''<tr class="{f.severity}">
                <td>{f.id}</td>
                <td>{f.category.replace('_', ' ').title()}</td>
                <td><span class="badge {f.severity}">{f.severity}</span></td>
                <td>{f.title}</td>
                <td>{f.effort_hours}h</td>
                <td>{ai_badge}</td>
            </tr>'''
        
        html += '</tbody></table></div>'
        
        html += self._footer(report.assessed_at)
        
        path = self.output_dir / "assessment_report.html"
        path.write_text(html, encoding="utf-8")
        return path
    
    def generate_planning_report(self, plan: PlanningReport) -> Path:
        """Generate Phase 2 Planning Report HTML"""
        
        html = self._header(f"Improvement Plan: {plan.project_name}")
        
        # Summary
        html += f'''
        <div class="section">
            <h2>📋 Planning Summary</h2>
            <div class="summary-grid">
                <div class="card">
                    <div class="big-number">{plan.total_items}</div>
                    <div class="label">Roadmap Items</div>
                </div>
                <div class="card critical">
                    <div class="big-number">{plan.critical_count}</div>
                    <div class="label">Critical</div>
                </div>
                <div class="card good">
                    <div class="big-number">{plan.quick_wins_count}</div>
                    <div class="label">Quick Wins</div>
                </div>
                <div class="card ai">
                    <div class="big-number">{plan.ai_opportunities_count}</div>
                    <div class="label">AI Opportunities</div>
                </div>
                <div class="card">
                    <div class="big-number">{plan.total_hours:.0f}h</div>
                    <div class="label">Total Effort</div>
                </div>
                <div class="card">
                    <div class="big-number">{len(plan.milestones)}</div>
                    <div class="label">Milestones</div>
                </div>
            </div>
            <div class="recommendation">
                <h3>💡 Recommendation</h3>
                <p>{plan.recommended_approach}</p>
            </div>
        </div>
        '''
        
        # Milestones
        html += '<div class="section"><h2>🎯 Milestones</h2><div class="milestones">'
        for m in plan.milestones:
            html += f'''
            <div class="milestone">
                <div class="m-header">
                    <span class="m-id">{m.id}</span>
                    <span class="m-name">{m.name}</span>
                    <span class="m-target">{m.target}</span>
                </div>
                <div class="m-desc">{m.description}</div>
                <div class="m-stats">
                    <span>📦 {len(m.items)} items</span>
                    <span>⏱️ {m.estimated_hours:.0f}h</span>
                    {f'<span>⬅️ After: {", ".join(m.dependencies)}</span>' if m.dependencies else ''}
                </div>
                <div class="m-deliverables">
                    <strong>Deliverables:</strong> {', '.join(m.deliverables)}
                </div>
            </div>
            '''
        html += '</div></div>'
        
        # Roadmap by Priority
        html += '<div class="section"><h2>📍 Roadmap</h2>'
        
        for priority in ['critical', 'high', 'medium', 'low']:
            items = [i for i in plan.roadmap if i.priority == priority]
            if items:
                icons = {'critical': '🚨', 'high': '⚠️', 'medium': '📋', 'low': '📝'}
                html += f'<h3>{icons[priority]} {priority.title()} Priority</h3>'
                html += '<div class="roadmap-items">'
                for item in items[:10]:
                    html += self._roadmap_card(item)
                html += '</div>'
        
        html += '</div>'
        
        # AI Opportunities
        html += '<div class="section ai-bg"><h2>🤖 AI Enhancement Opportunities</h2>'
        html += '<p class="muted">Opportunities to add AI features for user value and efficiency.</p>'
        html += '<div class="ai-grid">'
        
        for opp in plan.ai_opportunities[:12]:
            html += f'''
            <div class="ai-card">
                <div class="ai-header">
                    <span class="ai-id">{opp.id}</span>
                    <span class="ai-title">{opp.title}</span>
                    <span class="badge {opp.complexity}">{opp.complexity}</span>
                </div>
                <div class="ai-desc">{opp.description}</div>
                <div class="ai-value"><strong>👤 User:</strong> {opp.user_benefit}</div>
                <div class="ai-value"><strong>💼 Business:</strong> {opp.business_value}</div>
                <div class="ai-approach"><strong>Approach:</strong> {opp.approach}</div>
                <div class="ai-meta">
                    <span>⏱️ {opp.estimated_hours:.0f}h</span>
                    <span class="badge {opp.priority}">{opp.priority}</span>
                    {'<span class="badge quick">Quick Win</span>' if opp.quick_win else ''}
                </div>
            </div>
            '''
        
        html += '</div></div>'
        
        # Risks
        if plan.risk_factors:
            html += '<div class="section warning-bg"><h2>⚠️ Risk Factors</h2><ul>'
            for risk in plan.risk_factors:
                html += f'<li>{risk}</li>'
            html += '</ul></div>'
        
        # Full Roadmap Table
        html += '<div class="section"><h2>📋 Complete Roadmap</h2>'
        html += '<table class="findings-table"><thead><tr>'
        html += '<th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Effort</th><th>Impact</th><th>AI</th><th>Status</th>'
        html += '</tr></thead><tbody>'
        
        for item in plan.roadmap:
            ai_badge = '🤖' if item.ai_can_implement else ''
            html += f'''<tr>
                <td>{item.id}</td>
                <td>{item.title[:40]}...</td>
                <td>{item.category.replace('_', ' ')}</td>
                <td><span class="badge {item.priority}">{item.priority}</span></td>
                <td>{item.effort_hours}h</td>
                <td>{item.impact}</td>
                <td>{ai_badge}</td>
                <td>{item.status}</td>
            </tr>'''
        
        html += '</tbody></table></div>'
        
        html += self._footer(plan.planned_at)
        
        path = self.output_dir / "planning_report.html"
        path.write_text(html, encoding="utf-8")
        return path
    
    def _category_card(self, name: str, cat: CategoryScore) -> str:
        return f'''
        <div class="category-card">
            <div class="cat-header">
                <span>{name}</span>
                <span class="cat-score {cat.status}">{cat.score}</span>
            </div>
            <div class="progress"><div class="bar {cat.status}" style="width:{cat.score}%"></div></div>
            <div class="cat-summary">{cat.summary}</div>
            <div class="cat-lists">
                <div class="strengths">
                    <strong>✓ Strengths</strong>
                    <ul>{''.join(f'<li>{s}</li>' for s in cat.strengths) or '<li class="none">None identified</li>'}</ul>
                </div>
                <div class="weaknesses">
                    <strong>✗ Issues</strong>
                    <ul>{''.join(f'<li>{w}</li>' for w in cat.weaknesses) or '<li class="none">None identified</li>'}</ul>
                </div>
            </div>
        </div>
        '''
    
    def _finding_card(self, f: Finding, show_ai: bool = False) -> str:
        html = f'''
        <div class="finding {f.severity}">
            <div class="f-header">
                <span class="f-id">{f.id}</span>
                <span class="f-title">{f.title}</span>
                <span class="badge {f.severity}">{f.severity}</span>
            </div>
            <div class="f-body">
                <p>{f.description}</p>
                {f'<div class="f-loc">📍 {f.location}</div>' if f.location else ''}
                {f'<div class="f-impact"><strong>Impact:</strong> {f.impact}</div>' if f.impact else ''}
                {f'<div class="f-rec"><strong>Fix:</strong> {f.recommendation}</div>' if f.recommendation else ''}
                <div class="f-meta">
                    <span>{f.category.replace("_", " ").title()}</span>
                    <span>⏱️ {f.effort_hours}h</span>
                </div>
        '''
        if show_ai and f.ai_approach:
            html += f'<div class="f-ai">🤖 <strong>AI Approach:</strong> {f.ai_approach}</div>'
        html += '</div></div>'
        return html
    
    def _roadmap_card(self, item: RoadmapItem) -> str:
        return f'''
        <div class="roadmap-card {'ai-assisted' if item.ai_can_implement else ''}">
            <div class="r-header">
                <span class="r-id">{item.id}</span>
                <span class="r-title">{item.title}</span>
                <span class="badge">{item.effort_hours}h</span>
            </div>
            <div class="r-body">
                <p>{item.description}</p>
                <div class="r-tasks">
                    <strong>Tasks:</strong>
                    <ul>{''.join(f'<li>{t}</li>' for t in item.tasks[:3])}</ul>
                </div>
                <div class="r-meta">
                    <span>📂 {item.category.replace("_", " ")}</span>
                    <span>📈 {item.impact} impact</span>
                    {'<span class="ai-badge">🤖 AI</span>' if item.ai_can_implement else ''}
                </div>
                {f'<div class="r-ai">{item.ai_approach}</div>' if item.ai_approach else ''}
            </div>
        </div>
        '''
    
    def _header(self, title: str) -> str:
        return f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 20px; }}
h1 {{ text-align: center; margin-bottom: 30px; color: #f1f5f9; }}
h2 {{ color: #e2e8f0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #334155; }}
h3 {{ color: #cbd5e1; margin: 20px 0 15px; }}
.section {{ background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
.muted {{ color: #94a3b8; margin-bottom: 16px; }}

.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; }}
.card {{ background: #0f172a; border-radius: 10px; padding: 20px; text-align: center; border: 2px solid #334155; }}
.card.critical {{ border-color: #ef4444; }}
.card.warning {{ border-color: #f59e0b; }}
.card.good {{ border-color: #10b981; }}
.card.excellent {{ border-color: #3b82f6; }}
.card.ai {{ border-color: #8b5cf6; }}
.big-number {{ font-size: 2.5rem; font-weight: 700; color: #f1f5f9; }}
.label {{ color: #94a3b8; font-size: 0.9rem; margin-top: 5px; }}
.status {{ margin-top: 8px; font-weight: 600; text-transform: uppercase; font-size: 0.85rem; }}
.card.critical .status {{ color: #ef4444; }}
.card.warning .status {{ color: #f59e0b; }}
.card.good .status {{ color: #10b981; }}
.card.excellent .status {{ color: #3b82f6; }}

.categories {{ display: flex; flex-direction: column; gap: 16px; }}
.category-card {{ background: #0f172a; border-radius: 10px; padding: 16px; }}
.cat-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-weight: 600; }}
.cat-score {{ font-size: 1.4rem; padding: 4px 12px; border-radius: 6px; }}
.cat-score.critical {{ background: #7f1d1d; color: #fca5a5; }}
.cat-score.warning {{ background: #78350f; color: #fcd34d; }}
.cat-score.good {{ background: #064e3b; color: #6ee7b7; }}
.cat-score.excellent {{ background: #1e3a8a; color: #93c5fd; }}
.progress {{ height: 6px; background: #334155; border-radius: 3px; overflow: hidden; margin-bottom: 10px; }}
.bar {{ height: 100%; border-radius: 3px; }}
.bar.critical {{ background: #ef4444; }}
.bar.warning {{ background: #f59e0b; }}
.bar.good {{ background: #10b981; }}
.bar.excellent {{ background: #3b82f6; }}
.cat-summary {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px; }}
.cat-lists {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.85rem; }}
.strengths ul, .weaknesses ul {{ margin-left: 16px; color: #94a3b8; }}
.strengths li {{ color: #10b981; }}
.weaknesses li {{ color: #f59e0b; }}
.none {{ color: #64748b !important; }}

.findings {{ display: flex; flex-direction: column; gap: 12px; }}
.finding {{ background: #0f172a; border-radius: 10px; border-left: 4px solid #334155; }}
.finding.critical {{ border-left-color: #ef4444; }}
.finding.high {{ border-left-color: #f59e0b; }}
.finding.medium {{ border-left-color: #3b82f6; }}
.finding.low {{ border-left-color: #10b981; }}
.f-header {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: rgba(0,0,0,0.3); }}
.f-id {{ font-family: monospace; color: #64748b; }}
.f-title {{ flex: 1; font-weight: 600; }}
.f-body {{ padding: 16px; }}
.f-body p {{ color: #cbd5e1; margin-bottom: 10px; }}
.f-loc {{ color: #64748b; font-size: 0.85rem; margin-bottom: 8px; }}
.f-impact, .f-rec {{ font-size: 0.9rem; margin-bottom: 8px; color: #94a3b8; }}
.f-meta {{ display: flex; gap: 16px; font-size: 0.85rem; color: #64748b; margin-top: 12px; }}
.f-ai {{ margin-top: 12px; padding: 12px; background: rgba(139,92,246,0.1); border-radius: 6px; border: 1px solid rgba(139,92,246,0.3); color: #c4b5fd; }}

.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
.badge.critical {{ background: #7f1d1d; color: #fca5a5; }}
.badge.high {{ background: #78350f; color: #fcd34d; }}
.badge.medium {{ background: #1e3a8a; color: #93c5fd; }}
.badge.low {{ background: #064e3b; color: #6ee7b7; }}
.badge.quick {{ background: #059669; color: white; }}

.findings-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
.findings-table th {{ text-align: left; padding: 12px; background: #0f172a; border-bottom: 2px solid #334155; }}
.findings-table td {{ padding: 10px 12px; border-bottom: 1px solid #334155; }}
.findings-table tr:hover {{ background: rgba(255,255,255,0.02); }}

.recommendation {{ background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3); border-radius: 10px; padding: 20px; margin-top: 20px; }}
.recommendation h3 {{ color: #60a5fa; margin-bottom: 10px; }}

.milestones {{ display: flex; flex-direction: column; gap: 16px; }}
.milestone {{ background: #0f172a; border-radius: 10px; padding: 20px; }}
.m-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.m-id {{ background: #3b82f6; color: white; padding: 4px 12px; border-radius: 6px; font-weight: 600; }}
.m-name {{ flex: 1; font-size: 1.1rem; font-weight: 600; }}
.m-target {{ color: #94a3b8; }}
.m-desc {{ color: #94a3b8; margin-bottom: 12px; }}
.m-stats {{ display: flex; gap: 20px; font-size: 0.9rem; color: #64748b; margin-bottom: 12px; }}
.m-deliverables {{ font-size: 0.9rem; color: #94a3b8; }}

.roadmap-items {{ display: flex; flex-direction: column; gap: 12px; }}
.roadmap-card {{ background: #0f172a; border-radius: 10px; border: 1px solid #334155; }}
.roadmap-card.ai-assisted {{ border-color: rgba(139,92,246,0.5); }}
.r-header {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: rgba(0,0,0,0.3); }}
.r-id {{ font-family: monospace; color: #64748b; }}
.r-title {{ flex: 1; font-weight: 600; }}
.r-body {{ padding: 16px; }}
.r-body p {{ color: #cbd5e1; margin-bottom: 12px; }}
.r-tasks ul {{ margin: 8px 0 12px 20px; color: #94a3b8; }}
.r-meta {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 0.85rem; color: #64748b; }}
.ai-badge {{ background: rgba(139,92,246,0.2); color: #c4b5fd; padding: 2px 8px; border-radius: 4px; }}
.r-ai {{ margin-top: 12px; padding: 12px; background: rgba(139,92,246,0.1); border-radius: 6px; color: #c4b5fd; font-size: 0.9rem; }}

.ai-bg {{ background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%); }}
.warning-bg {{ background: linear-gradient(135deg, #1e293b 0%, #422006 100%); }}
.critical-bg {{ background: linear-gradient(135deg, #1e293b 0%, #450a0a 100%); }}

.ai-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 16px; }}
.ai-card {{ background: rgba(0,0,0,0.3); border-radius: 10px; padding: 20px; border: 1px solid rgba(139,92,246,0.3); }}
.ai-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.ai-id {{ background: #8b5cf6; color: white; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; }}
.ai-title {{ flex: 1; font-weight: 600; }}
.ai-desc {{ color: #94a3b8; margin-bottom: 12px; }}
.ai-value {{ font-size: 0.9rem; color: #94a3b8; margin-bottom: 6px; }}
.ai-approach {{ font-size: 0.9rem; color: #64748b; margin: 12px 0; }}
.ai-meta {{ display: flex; gap: 12px; margin-top: 12px; }}

.footer {{ text-align: center; color: #64748b; font-size: 0.85rem; margin-top: 40px; padding-top: 20px; border-top: 1px solid #334155; }}

@media (max-width: 768px) {{
    .categories, .ai-grid {{ grid-template-columns: 1fr; }}
    .cat-lists {{ grid-template-columns: 1fr; }}
}}
</style>
</head><body>
<h1>{title}</h1>
'''
    
    def _footer(self, timestamp: str) -> str:
        return f'''
<div class="footer">
    Generated by AI-Dev-Workflow on {timestamp[:10]}<br>
    Phase 1 Assessment & Phase 2 Planning Reports
</div>
</body></html>
'''


def generate_reports(assessment: AssessmentReport, plan: PlanningReport, output_dir: Path):
    """Generate both reports"""
    gen = ReportGenerator(output_dir)
    assess_path = gen.generate_assessment_report(assessment)
    plan_path = gen.generate_planning_report(plan)
    return assess_path, plan_path
