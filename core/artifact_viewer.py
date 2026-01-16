"""
Artifact Viewer for AI-Dev-Workflow

Generates viewable artifacts (HTML, diagrams) and opens them for review.
"""

import webbrowser
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class ArtifactViewer:
    """Generates and displays artifacts for checkpoint review"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.artifacts_dir = self.project_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # DESIGN ARTIFACTS
    # =========================================================================
    
    def generate_sitemap(
        self,
        screens: List[Dict[str, Any]],
        title: str = "Site Map"
    ) -> Path:
        """Generate interactive sitemap HTML"""
        
        html = self._get_html_template(title)
        
        # Build sitemap visualization
        nodes_html = []
        for i, screen in enumerate(screens):
            nodes_html.append(f'''
                <div class="screen-node" data-id="{screen.get('id', i)}">
                    <div class="screen-icon">{screen.get('icon', '📄')}</div>
                    <div class="screen-name">{screen.get('name', f'Screen {i+1}')}</div>
                    <div class="screen-desc">{screen.get('description', '')}</div>
                </div>
            ''')
        
        html += f'''
            <div class="sitemap-container">
                <h1>{title}</h1>
                <div class="screens-grid">
                    {''.join(nodes_html)}
                </div>
            </div>
            <style>
                .sitemap-container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
                .screens-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 1.5rem;
                }}
                .screen-node {{
                    background: #1e293b;
                    border: 2px solid #334155;
                    border-radius: 12px;
                    padding: 1.5rem;
                    text-align: center;
                    transition: all 0.2s;
                    cursor: pointer;
                }}
                .screen-node:hover {{
                    border-color: #3b82f6;
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(59, 130, 246, 0.2);
                }}
                .screen-icon {{ font-size: 2rem; margin-bottom: 0.5rem; }}
                .screen-name {{ font-weight: 600; color: #e2e8f0; margin-bottom: 0.25rem; }}
                .screen-desc {{ font-size: 0.85rem; color: #94a3b8; }}
            </style>
        </body></html>
        '''
        
        output_path = self.artifacts_dir / "design" / "sitemap.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        
        return output_path
    
    def generate_wireframe(
        self,
        screen_name: str,
        components: List[Dict[str, Any]],
        layout: str = "single"
    ) -> Path:
        """Generate wireframe HTML for a screen"""
        
        html = self._get_html_template(f"Wireframe: {screen_name}")
        
        # Build component blocks
        components_html = []
        for comp in components:
            comp_type = comp.get('type', 'block')
            comp_class = f"wireframe-{comp_type}"
            
            components_html.append(f'''
                <div class="wireframe-component {comp_class}" 
                     style="grid-area: {comp.get('area', 'auto')}">
                    <div class="component-label">{comp.get('label', comp_type)}</div>
                    {self._get_component_placeholder(comp)}
                </div>
            ''')
        
        html += f'''
            <div class="wireframe-container">
                <div class="wireframe-header">
                    <h1>{screen_name}</h1>
                    <span class="wireframe-badge">WIREFRAME</span>
                </div>
                <div class="wireframe-canvas layout-{layout}">
                    {''.join(components_html)}
                </div>
            </div>
            <style>
                .wireframe-container {{ 
                    max-width: 1000px; 
                    margin: 0 auto; 
                    padding: 2rem;
                }}
                .wireframe-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 1.5rem;
                }}
                .wireframe-badge {{
                    background: #f59e0b;
                    color: #000;
                    padding: 0.25rem 0.75rem;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }}
                .wireframe-canvas {{
                    background: #1e293b;
                    border: 2px dashed #475569;
                    border-radius: 8px;
                    padding: 1.5rem;
                    min-height: 600px;
                    display: grid;
                    gap: 1rem;
                }}
                .layout-single {{ grid-template-columns: 1fr; }}
                .layout-sidebar {{ grid-template-columns: 250px 1fr; }}
                .layout-dashboard {{ 
                    grid-template-columns: repeat(3, 1fr);
                    grid-template-rows: auto 1fr 1fr;
                }}
                .wireframe-component {{
                    background: #0f172a;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 1rem;
                    position: relative;
                }}
                .component-label {{
                    position: absolute;
                    top: -10px;
                    left: 10px;
                    background: #1e293b;
                    padding: 0 0.5rem;
                    font-size: 0.7rem;
                    color: #94a3b8;
                    text-transform: uppercase;
                }}
                .wireframe-header-comp {{ background: #1e3a5f; min-height: 60px; }}
                .wireframe-nav {{ background: #1e3a5f; }}
                .wireframe-content {{ min-height: 300px; }}
                .wireframe-sidebar {{ background: #172033; }}
                .wireframe-card {{ min-height: 150px; }}
                .wireframe-table {{ min-height: 200px; }}
                .wireframe-form {{ min-height: 250px; }}
                .wireframe-button {{
                    background: #3b82f6;
                    text-align: center;
                    padding: 0.75rem;
                    border-radius: 4px;
                    color: white;
                }}
                .placeholder-lines {{
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                }}
                .placeholder-line {{
                    height: 12px;
                    background: #334155;
                    border-radius: 2px;
                }}
                .placeholder-line.short {{ width: 60%; }}
                .placeholder-line.medium {{ width: 80%; }}
            </style>
        </body></html>
        '''
        
        output_path = self.artifacts_dir / "design" / "wireframes" / f"{self._slugify(screen_name)}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        
        return output_path
    
    def generate_style_guide(
        self,
        colors: Dict[str, str],
        fonts: Dict[str, str],
        components: List[Dict[str, Any]]
    ) -> Path:
        """Generate style guide HTML"""
        
        html = self._get_html_template("Style Guide")
        
        # Color swatches
        color_swatches = []
        for name, value in colors.items():
            color_swatches.append(f'''
                <div class="color-swatch">
                    <div class="swatch-preview" style="background: {value}"></div>
                    <div class="swatch-name">{name}</div>
                    <div class="swatch-value">{value}</div>
                </div>
            ''')
        
        # Typography
        font_samples = []
        for name, spec in fonts.items():
            font_samples.append(f'''
                <div class="font-sample">
                    <div class="font-name">{name}</div>
                    <div class="font-preview" style="font: {spec}">
                        The quick brown fox jumps over the lazy dog
                    </div>
                    <div class="font-spec">{spec}</div>
                </div>
            ''')
        
        html += f'''
            <div class="style-guide">
                <h1>Style Guide</h1>
                
                <section class="section-colors">
                    <h2>Colors</h2>
                    <div class="color-grid">
                        {''.join(color_swatches)}
                    </div>
                </section>
                
                <section class="section-typography">
                    <h2>Typography</h2>
                    <div class="font-list">
                        {''.join(font_samples)}
                    </div>
                </section>
                
                <section class="section-components">
                    <h2>Components</h2>
                    <div class="components-preview">
                        <div class="component-demo">
                            <h3>Buttons</h3>
                            <button class="btn btn-primary">Primary</button>
                            <button class="btn btn-secondary">Secondary</button>
                            <button class="btn btn-outline">Outline</button>
                        </div>
                        <div class="component-demo">
                            <h3>Inputs</h3>
                            <input type="text" class="input" placeholder="Text input">
                            <select class="input"><option>Select option</option></select>
                        </div>
                        <div class="component-demo">
                            <h3>Cards</h3>
                            <div class="card">
                                <div class="card-header">Card Title</div>
                                <div class="card-body">Card content goes here.</div>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
            <style>
                .style-guide {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
                section {{ margin-bottom: 3rem; }}
                h2 {{ 
                    color: #e2e8f0; 
                    border-bottom: 1px solid #334155;
                    padding-bottom: 0.5rem;
                    margin-bottom: 1.5rem;
                }}
                .color-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 1rem;
                }}
                .color-swatch {{
                    background: #1e293b;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .swatch-preview {{
                    height: 80px;
                }}
                .swatch-name, .swatch-value {{
                    padding: 0.5rem;
                    font-size: 0.85rem;
                }}
                .swatch-name {{ font-weight: 600; }}
                .swatch-value {{ color: #94a3b8; font-family: monospace; }}
                .font-sample {{
                    background: #1e293b;
                    padding: 1.5rem;
                    border-radius: 8px;
                    margin-bottom: 1rem;
                }}
                .font-name {{ font-weight: 600; margin-bottom: 0.5rem; }}
                .font-preview {{ font-size: 1.25rem; margin-bottom: 0.5rem; color: #e2e8f0; }}
                .font-spec {{ font-size: 0.85rem; color: #94a3b8; font-family: monospace; }}
                .components-preview {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 1.5rem;
                }}
                .component-demo {{
                    background: #1e293b;
                    padding: 1.5rem;
                    border-radius: 8px;
                }}
                .component-demo h3 {{ margin-bottom: 1rem; font-size: 1rem; }}
                .btn {{
                    padding: 0.5rem 1rem;
                    border-radius: 6px;
                    border: none;
                    cursor: pointer;
                    margin-right: 0.5rem;
                    font-size: 0.9rem;
                }}
                .btn-primary {{ background: {colors.get('primary', '#3b82f6')}; color: white; }}
                .btn-secondary {{ background: #475569; color: white; }}
                .btn-outline {{ background: transparent; border: 1px solid #475569; color: #e2e8f0; }}
                .input {{
                    width: 100%;
                    padding: 0.5rem;
                    border-radius: 6px;
                    border: 1px solid #475569;
                    background: #0f172a;
                    color: #e2e8f0;
                    margin-bottom: 0.5rem;
                }}
                .card {{
                    background: #0f172a;
                    border-radius: 8px;
                    border: 1px solid #334155;
                }}
                .card-header {{
                    padding: 1rem;
                    border-bottom: 1px solid #334155;
                    font-weight: 600;
                }}
                .card-body {{ padding: 1rem; color: #94a3b8; }}
            </style>
        </body></html>
        '''
        
        output_path = self.artifacts_dir / "design" / "style_guide.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        
        return output_path
    
    # =========================================================================
    # DEVELOPMENT ARTIFACTS
    # =========================================================================
    
    def generate_milestone_plan(self, milestones: List[Dict[str, Any]]) -> Path:
        """Generate milestone plan visualization"""
        
        html = self._get_html_template("Development Milestones")
        
        milestone_cards = []
        for m in milestones:
            tasks_html = ''.join([f'<li>{t}</li>' for t in m.get('tasks', [])])
            deps = ', '.join(m.get('dependencies', [])) or 'None'
            
            milestone_cards.append(f'''
                <div class="milestone-card">
                    <div class="milestone-header">
                        <span class="milestone-id">{m.get('id', '?')}</span>
                        <span class="milestone-hours">{m.get('hours', 0):.1f}h</span>
                    </div>
                    <h3>{m.get('name', 'Untitled')}</h3>
                    <p class="milestone-desc">{m.get('description', '')}</p>
                    <div class="milestone-tasks">
                        <strong>Tasks:</strong>
                        <ul>{tasks_html}</ul>
                    </div>
                    <div class="milestone-deps">
                        <strong>Dependencies:</strong> {deps}
                    </div>
                </div>
            ''')
        
        total_hours = sum(m.get('hours', 0) for m in milestones)
        
        html += f'''
            <div class="milestone-plan">
                <div class="plan-header">
                    <h1>Development Milestones</h1>
                    <div class="plan-stats">
                        <span>{len(milestones)} milestones</span>
                        <span>{total_hours:.1f} total hours</span>
                    </div>
                </div>
                <div class="milestones-grid">
                    {''.join(milestone_cards)}
                </div>
            </div>
            <style>
                .milestone-plan {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
                .plan-header {{ 
                    display: flex; 
                    justify-content: space-between; 
                    align-items: center;
                    margin-bottom: 2rem;
                }}
                .plan-stats {{
                    display: flex;
                    gap: 1.5rem;
                    color: #94a3b8;
                }}
                .milestones-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                    gap: 1.5rem;
                }}
                .milestone-card {{
                    background: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 12px;
                    padding: 1.5rem;
                }}
                .milestone-header {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 0.75rem;
                }}
                .milestone-id {{
                    background: #3b82f6;
                    color: white;
                    padding: 0.25rem 0.75rem;
                    border-radius: 4px;
                    font-weight: 600;
                    font-size: 0.85rem;
                }}
                .milestone-hours {{
                    color: #94a3b8;
                    font-size: 0.9rem;
                }}
                .milestone-card h3 {{
                    color: #e2e8f0;
                    margin-bottom: 0.5rem;
                }}
                .milestone-desc {{
                    color: #94a3b8;
                    font-size: 0.9rem;
                    margin-bottom: 1rem;
                }}
                .milestone-tasks ul {{
                    margin: 0.5rem 0 1rem 1.25rem;
                    color: #cbd5e1;
                    font-size: 0.9rem;
                }}
                .milestone-deps {{
                    font-size: 0.85rem;
                    color: #64748b;
                }}
            </style>
        </body></html>
        '''
        
        output_path = self.artifacts_dir / "milestones" / "plan.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        
        return output_path
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_html_template(self, title: str) -> str:
        """Get base HTML template"""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - AI-Dev-Workflow</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }}
        h1 {{ color: #f1f5f9; margin-bottom: 1rem; }}
        h2 {{ color: #e2e8f0; }}
        h3 {{ color: #cbd5e1; }}
    </style>
</head>
<body>
        '''
    
    def _get_component_placeholder(self, comp: Dict[str, Any]) -> str:
        """Get placeholder content for wireframe component"""
        comp_type = comp.get('type', 'block')
        
        if comp_type in ['text', 'content']:
            return '''
                <div class="placeholder-lines">
                    <div class="placeholder-line"></div>
                    <div class="placeholder-line medium"></div>
                    <div class="placeholder-line short"></div>
                </div>
            '''
        elif comp_type == 'button':
            return f'<div class="wireframe-button">{comp.get("label", "Button")}</div>'
        elif comp_type == 'image':
            return '<div style="background:#334155;height:150px;display:flex;align-items:center;justify-content:center;">🖼️ Image</div>'
        else:
            return ''
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug"""
        return text.lower().replace(' ', '_').replace('-', '_')
    
    def open_artifact(self, path: Path) -> bool:
        """Open artifact in browser"""
        try:
            webbrowser.open(path.as_uri())
            return True
        except Exception:
            return False
    
    def open_all_in_directory(self, directory: Path) -> int:
        """Open all HTML files in a directory"""
        count = 0
        for html_file in directory.glob("*.html"):
            if self.open_artifact(html_file):
                count += 1
        return count
