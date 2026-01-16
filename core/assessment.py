"""
Assessment Module for Codebase Ingestion - Phase 1

Comprehensive analysis covering:
- Architecture & Structure
- Code Quality  
- Tech Debt
- Security & Risk
- UX Review (Navigation, Styling, Accessibility)
- Performance
- Testing
- Documentation
"""

import os
import json
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Finding:
    """A single assessment finding"""
    id: str
    category: str
    severity: str  # critical, high, medium, low, info
    title: str
    description: str
    location: str
    evidence: str
    impact: str
    recommendation: str
    effort_hours: float
    ai_can_fix: bool = False
    ai_approach: str = ""


@dataclass
class CategoryScore:
    """Score for an assessment category"""
    category: str
    score: int  # 0-100
    status: str  # critical, warning, good, excellent
    summary: str
    findings: List[Finding] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class AssessmentReport:
    """Complete Phase 1 Assessment Report"""
    project_name: str
    assessed_at: str
    source_path: str
    
    # Overall
    overall_score: int
    overall_status: str
    
    # Category scores
    architecture: CategoryScore
    code_quality: CategoryScore
    tech_debt: CategoryScore
    security: CategoryScore
    ux_navigation: CategoryScore
    ux_styling: CategoryScore
    ux_accessibility: CategoryScore
    performance: CategoryScore
    testing: CategoryScore
    documentation: CategoryScore
    
    # Aggregated
    all_findings: List[Finding] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    ai_fixable_count: int = 0
    
    # Stats
    files_analyzed: int = 0
    lines_analyzed: int = 0


class CodebaseAssessor:
    """Performs comprehensive codebase assessment"""

    def __init__(self, source_path: Path, project_config: Dict, on_progress: Optional[callable] = None):
        self.source = Path(source_path)
        self.config = project_config
        self.findings: List[Finding] = []
        self.counter = 0
        self.on_progress = on_progress  # Callback: (category_name, step, total_steps) -> None

    def _notify_progress(self, category: str, step: int, total: int = 10):
        """Notify progress callback if set"""
        if self.on_progress:
            self.on_progress(category, step, total)

    def assess(self) -> AssessmentReport:
        """Run complete assessment"""

        # Run all category assessments with progress notifications
        self._notify_progress("Architecture", 1)
        arch = self._assess_architecture()

        self._notify_progress("Code Quality", 2)
        quality = self._assess_code_quality()

        self._notify_progress("Tech Debt", 3)
        debt = self._assess_tech_debt()

        self._notify_progress("Security", 4)
        security = self._assess_security()

        self._notify_progress("UX Navigation", 5)
        nav = self._assess_ux_navigation()

        self._notify_progress("UX Styling", 6)
        style = self._assess_ux_styling()

        self._notify_progress("Accessibility", 7)
        a11y = self._assess_ux_accessibility()

        self._notify_progress("Performance", 8)
        perf = self._assess_performance()

        self._notify_progress("Testing", 9)
        test = self._assess_testing()

        self._notify_progress("Documentation", 10)
        docs = self._assess_documentation()
        
        # Calculate overall (weighted)
        overall = int(
            arch.score * 0.12 +
            quality.score * 0.12 +
            debt.score * 0.10 +
            security.score * 0.15 +
            nav.score * 0.10 +
            style.score * 0.08 +
            a11y.score * 0.08 +
            perf.score * 0.10 +
            test.score * 0.10 +
            docs.score * 0.05
        )
        
        stats = self.config.get('stats', {})
        
        return AssessmentReport(
            project_name=self.config.get('project', {}).get('name', 'Unknown'),
            assessed_at=datetime.now().isoformat(),
            source_path=str(self.source),
            overall_score=overall,
            overall_status=self._status(overall),
            architecture=arch,
            code_quality=quality,
            tech_debt=debt,
            security=security,
            ux_navigation=nav,
            ux_styling=style,
            ux_accessibility=a11y,
            performance=perf,
            testing=test,
            documentation=docs,
            all_findings=self.findings,
            critical_count=sum(1 for f in self.findings if f.severity == 'critical'),
            high_count=sum(1 for f in self.findings if f.severity == 'high'),
            ai_fixable_count=sum(1 for f in self.findings if f.ai_can_fix),
            files_analyzed=stats.get('source_file_count', 0),
            lines_analyzed=stats.get('total_lines', 0),
        )
    
    def _add(self, cat: str, sev: str, title: str, desc: str, 
             loc: str = "", evidence: str = "", impact: str = "",
             rec: str = "", hours: float = 1.0, 
             ai: bool = False, ai_how: str = "") -> Finding:
        """Create and track a finding"""
        self.counter += 1
        f = Finding(
            id=f"F{self.counter:03d}",
            category=cat,
            severity=sev,
            title=title,
            description=desc,
            location=loc,
            evidence=evidence,
            impact=impact,
            recommendation=rec,
            effort_hours=hours,
            ai_can_fix=ai,
            ai_approach=ai_how
        )
        self.findings.append(f)
        return f
    
    def _status(self, score: int) -> str:
        if score >= 80: return "excellent"
        if score >= 60: return "good"
        if score >= 40: return "warning"
        return "critical"
    
    def _has_dir(self, names: List[str]) -> bool:
        for n in names:
            if (self.source / n).is_dir():
                return True
        return False
    
    def _has_file(self, names: List[str]) -> bool:
        for n in names:
            if (self.source / n).exists():
                return True
        return False
    
    def _has_ext(self, ext: str) -> bool:
        return any(self.source.rglob(f"*{ext}"))
    
    def _search(self, terms: List[str], exts: List[str] = None) -> bool:
        exts = exts or ['.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.html', '.css']
        for p in self.source.rglob("*"):
            if p.is_file() and p.suffix in exts:
                try:
                    content = p.read_text(errors='ignore').lower()
                    for t in terms:
                        if t.lower() in content:
                            return True
                except:
                    pass
        return False
    
    def _count_pattern(self, pattern: str) -> int:
        count = 0
        for p in self.source.rglob("*"):
            if p.is_file() and p.suffix in ['.py', '.js', '.ts', '.tsx', '.jsx']:
                try:
                    content = p.read_text(errors='ignore')
                    count += len(re.findall(pattern, content, re.IGNORECASE))
                except:
                    pass
        return count
    
    # ═══════════════════════════════════════════════════════════════
    # ARCHITECTURE
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_architecture(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # Source structure
        if self._has_dir(['src', 'lib', 'app']):
            strengths.append("Clear source directory")
            s += 5
        else:
            weaks.append("No organized source directory")
            self._add("architecture", "medium", "No source directory structure",
                     "Code not organized into src/, lib/, or app/",
                     rec="Create src/ directory for application code", hours=2)
            s -= 10
        
        # Separation of concerns
        has_comp = self._has_dir(['components', 'ui', 'views', 'pages'])
        has_svc = self._has_dir(['services', 'api', 'controllers', 'handlers'])
        has_model = self._has_dir(['models', 'entities', 'types', 'schemas'])
        
        if has_comp and has_svc:
            strengths.append("UI and business logic separated")
            s += 10
        elif has_comp or has_svc:
            s -= 5
        else:
            weaks.append("No separation of concerns")
            self._add("architecture", "high", "Missing separation of concerns",
                     "No clear separation between UI, services, and models",
                     impact="Harder to maintain and test",
                     rec="Refactor into components/, services/, models/",
                     hours=8, ai=True, ai_how="AI can analyze dependencies and suggest module boundaries")
            s -= 15
        
        # Config management
        if self._has_file(['.env.example', 'config.py', 'config/index.js']):
            strengths.append("Configuration management present")
        else:
            weaks.append("No configuration management")
            self._add("architecture", "medium", "Missing .env.example",
                     "No environment configuration template",
                     rec="Create .env.example with required variables", hours=0.5)
            s -= 5
        
        return CategoryScore("architecture", max(0, min(100, s)), self._status(s),
                            f"{len(strengths)} strengths, {len(weaks)} issues",
                            [f for f in self.findings if f.category == "architecture"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # CODE QUALITY
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_code_quality(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # Linting
        lint_files = ['.eslintrc', '.eslintrc.js', '.eslintrc.json', 'pylint.ini', '.flake8', 'ruff.toml']
        if self._has_file(lint_files):
            strengths.append("Linting configured")
            s += 10
        else:
            weaks.append("No linting")
            self._add("code_quality", "medium", "No linter configuration",
                     "No ESLint, Pylint, or Ruff config found",
                     rec="Add linting for consistent code style", hours=1,
                     ai=True, ai_how="AI can generate optimal lint rules from code patterns")
            s -= 10
        
        # Formatting
        if self._has_file(['.prettierrc', 'pyproject.toml', '.editorconfig']):
            strengths.append("Code formatting configured")
            s += 5
        
        # TypeScript
        if self._has_ext('.ts') or self._has_ext('.tsx'):
            strengths.append("TypeScript for type safety")
            s += 10
        elif self._has_ext('.js'):
            weaks.append("JavaScript without TypeScript")
            self._add("code_quality", "medium", "No TypeScript",
                     "Project uses JavaScript without type checking",
                     impact="Higher risk of runtime errors",
                     rec="Consider TypeScript migration", hours=16,
                     ai=True, ai_how="AI can auto-generate TS types and convert files")
            s -= 10
        
        # Large files
        large = []
        for p in self.source.rglob("*"):
            if p.is_file() and p.suffix in ['.py', '.js', '.ts', '.tsx', '.jsx']:
                try:
                    lines = len(p.read_text().splitlines())
                    if lines > 500:
                        large.append((p.name, lines))
                except:
                    pass
        
        if large:
            weaks.append(f"{len(large)} files over 500 lines")
            for name, lines in large[:3]:
                self._add("code_quality", "low", f"Large file: {name}",
                         f"File has {lines} lines",
                         loc=name,
                         rec="Consider splitting into smaller modules", hours=3,
                         ai=True, ai_how="AI can identify logical split points")
            s -= min(15, len(large) * 3)
        
        return CategoryScore("code_quality", max(0, min(100, s)), self._status(s),
                            f"Code quality analysis complete",
                            [f for f in self.findings if f.category == "code_quality"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # TECH DEBT
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_tech_debt(self) -> CategoryScore:
        s, strengths, weaks = 75, [], []
        
        # TODO/FIXME count
        todo_count = self._count_pattern(r'(TODO|FIXME|HACK|XXX)[:\s]')
        if todo_count > 20:
            weaks.append(f"{todo_count} TODO/FIXME comments")
            self._add("tech_debt", "low", f"{todo_count} unresolved TODOs",
                     "Large number of TODO/FIXME markers",
                     rec="Review and resolve or create tickets", hours=4,
                     ai=True, ai_how="AI can categorize TODOs and suggest implementations")
            s -= min(20, todo_count // 2)
        elif todo_count == 0:
            strengths.append("No TODO/FIXME markers")
        
        # Check package.json for old deps
        pkg = self.source / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                old = []
                for dep, ver in deps.items():
                    v = re.sub(r'[\^~>=<]', '', ver)
                    if v and v[0].isdigit():
                        major = int(v.split('.')[0])
                        if dep == 'react' and major < 18: old.append(f"react@{ver}")
                        if dep == 'vue' and major < 3: old.append(f"vue@{ver}")
                        if dep == 'angular' and major < 14: old.append(f"angular@{ver}")
                
                if old:
                    weaks.append(f"Outdated: {', '.join(old[:3])}")
                    self._add("tech_debt", "medium", "Outdated major dependencies",
                             f"Found: {', '.join(old)}",
                             rec="Plan upgrade path", hours=8,
                             ai=True, ai_how="AI can analyze breaking changes and create migration plan")
                    s -= len(old) * 5
            except:
                pass
        
        return CategoryScore("tech_debt", max(0, min(100, s)), self._status(s),
                            "Tech debt analysis complete",
                            [f for f in self.findings if f.category == "tech_debt"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # SECURITY
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_security(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # .env in gitignore
        gi = self.source / ".gitignore"
        if gi.exists():
            try:
                if '.env' in gi.read_text():
                    strengths.append(".env excluded from git")
                    s += 10
                else:
                    weaks.append(".env may be committed")
                    self._add("security", "high", ".env not in .gitignore",
                             "Environment files may be in version control",
                             impact="Secrets could be exposed",
                             rec="Add .env* to .gitignore", hours=0.1)
                    s -= 20
            except:
                pass
        
        # Hardcoded secrets
        secret_patterns = [
            r'api[_-]?key\s*[=:]\s*["\'][A-Za-z0-9]{20,}',
            r'password\s*[=:]\s*["\'][^"\']+["\']',
            r'secret\s*[=:]\s*["\'][^"\']+["\']',
            r'sk-[a-zA-Z0-9]{20,}',
            r'ghp_[a-zA-Z0-9]{36}',
        ]
        
        secrets_found = 0
        for p in self.source.rglob("*"):
            if p.is_file() and p.suffix in ['.py', '.js', '.ts', '.env', '.json']:
                try:
                    content = p.read_text(errors='ignore')
                    for pat in secret_patterns:
                        if re.search(pat, content, re.IGNORECASE):
                            secrets_found += 1
                            break
                except:
                    pass
        
        if secrets_found:
            weaks.append(f"{secrets_found} potential hardcoded secrets")
            self._add("security", "critical", "Hardcoded secrets detected",
                     f"Found {secrets_found} files with potential credentials",
                     impact="Credentials could be exposed in git history",
                     rec="Move to environment variables, rotate exposed credentials",
                     hours=2, ai=True, ai_how="AI can identify and migrate secrets to env vars")
            s -= 25
        else:
            strengths.append("No obvious hardcoded secrets")
        
        # Auth library
        if self._search(['passport', 'jwt', 'auth0', 'clerk', 'nextauth', 'django.contrib.auth']):
            strengths.append("Authentication library detected")
            s += 5
        
        return CategoryScore("security", max(0, min(100, s)), self._status(s),
                            "Security analysis complete",
                            [f for f in self.findings if f.category == "security"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # UX - NAVIGATION
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_ux_navigation(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # Router
        routers = ['react-router', 'next/router', 'vue-router', 'useNavigate', '@angular/router']
        if self._search(routers):
            strengths.append("Router implementation present")
            s += 10
        elif self._has_dir(['pages', 'views', 'screens']):
            weaks.append("Multiple pages without router")
            self._add("ux_navigation", "medium", "No router detected",
                     "Multi-page structure without routing library",
                     rec="Implement client-side routing", hours=6,
                     ai=True, ai_how="AI can analyze pages and generate route config")
            s -= 15
        
        # Navigation components
        if self._search(['<nav', 'navbar', 'sidebar', 'header', 'navigation']):
            strengths.append("Navigation components present")
        else:
            weaks.append("No clear navigation structure")
            self._add("ux_navigation", "medium", "Missing navigation",
                     "No navbar/sidebar components detected",
                     rec="Add consistent navigation component", hours=4)
            s -= 10
        
        # Breadcrumbs
        if self._search(['breadcrumb']):
            strengths.append("Breadcrumb navigation")
            s += 5
        
        # Error pages
        if self._search(['404', 'not-found', 'error-page']):
            strengths.append("Error pages present")
            s += 5
        else:
            weaks.append("No error pages")
            self._add("ux_navigation", "low", "Missing 404 page",
                     "No custom error handling pages",
                     rec="Add user-friendly error pages", hours=2)
        
        # Back navigation / history
        if self._search(['goback', 'history.back', 'router.back', 'navigate(-1)']):
            strengths.append("Back navigation implemented")
        
        return CategoryScore("ux_navigation", max(0, min(100, s)), self._status(s),
                            "Navigation UX analysis complete",
                            [f for f in self.findings if f.category == "ux_navigation"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # UX - STYLING
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_ux_styling(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # CSS frameworks
        frameworks = []
        if self._search(['tailwindcss', 'tailwind.config']): frameworks.append("Tailwind")
        if self._search(['bootstrap']): frameworks.append("Bootstrap")
        if self._search(['@mui', 'material-ui']): frameworks.append("MUI")
        if self._search(['@chakra-ui']): frameworks.append("Chakra")
        if self._search(['styled-components', '@emotion']): frameworks.append("CSS-in-JS")
        if self._has_ext('.module.css'): frameworks.append("CSS Modules")
        
        if len(frameworks) == 1:
            strengths.append(f"Consistent styling: {frameworks[0]}")
            s += 15
        elif len(frameworks) > 1:
            weaks.append(f"Mixed: {', '.join(frameworks)}")
            self._add("ux_styling", "medium", "Inconsistent styling",
                     f"Multiple systems: {', '.join(frameworks)}",
                     impact="Inconsistent look, harder maintenance",
                     rec="Consolidate to single approach", hours=12,
                     ai=True, ai_how="AI can migrate styles to unified system")
            s -= 10
        else:
            weaks.append("No CSS framework")
            self._add("ux_styling", "low", "No CSS framework",
                     "Plain CSS without design system",
                     rec="Consider Tailwind or component library", hours=16)
        
        # Design tokens
        if self._search(['--color', '--spacing', ':root', 'theme.colors', 'theme.spacing']):
            strengths.append("Design tokens/CSS variables")
            s += 10
        else:
            weaks.append("No design tokens")
            self._add("ux_styling", "low", "No design tokens",
                     "No CSS variables or theme system",
                     rec="Implement design tokens for consistency", hours=4,
                     ai=True, ai_how="AI can extract colors/fonts and create token system")
        
        # Dark mode
        if self._search(['dark:', 'darkmode', 'dark-mode', 'prefers-color-scheme']):
            strengths.append("Dark mode support")
            s += 5
        
        # Responsive
        if self._search(['@media', 'sm:', 'md:', 'lg:', 'xl:', 'breakpoint']):
            strengths.append("Responsive breakpoints")
            s += 10
        else:
            weaks.append("No responsive design")
            self._add("ux_styling", "medium", "Missing responsive design",
                     "No media queries or responsive utilities",
                     impact="Poor mobile experience",
                     rec="Implement responsive breakpoints", hours=8,
                     ai=True, ai_how="AI can analyze layouts and add responsive styles")
            s -= 15
        
        return CategoryScore("ux_styling", max(0, min(100, s)), self._status(s),
                            "Styling analysis complete",
                            [f for f in self.findings if f.category == "ux_styling"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # UX - ACCESSIBILITY
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_ux_accessibility(self) -> CategoryScore:
        s, strengths, weaks = 55, [], []  # Lower default
        
        # ARIA
        if self._search(['aria-', 'role=']):
            strengths.append("ARIA attributes used")
            s += 15
        else:
            weaks.append("No ARIA attributes")
            self._add("ux_accessibility", "medium", "Missing ARIA attributes",
                     "No aria-label, aria-describedby found",
                     impact="Screen readers cannot interpret UI",
                     rec="Add ARIA to interactive elements", hours=6,
                     ai=True, ai_how="AI can analyze components and add ARIA attributes")
            s -= 10
        
        # Alt text
        if self._search(['alt=', 'alt:']):
            strengths.append("Image alt text present")
            s += 10
        else:
            weaks.append("Missing alt text")
            self._add("ux_accessibility", "high", "Missing alt text",
                     "Images without alt attributes",
                     impact="Screen readers cannot describe images",
                     rec="Add alt text to all images", hours=3,
                     ai=True, ai_how="AI can generate contextual alt text")
        
        # Semantic HTML
        semantic = ['<main', '<header', '<footer', '<article', '<section', '<nav']
        if self._search(semantic):
            strengths.append("Semantic HTML used")
            s += 10
        else:
            weaks.append("Limited semantic HTML")
            self._add("ux_accessibility", "low", "Missing semantic HTML",
                     "Limited use of main, header, nav, etc.",
                     rec="Replace divs with semantic elements", hours=4)
        
        # Focus states
        if self._search(['focus:', ':focus', 'tabindex', 'focus-visible']):
            strengths.append("Focus states implemented")
            s += 5
        
        # Skip links
        if self._search(['skip-to', 'skiplink', 'skip-nav']):
            strengths.append("Skip navigation link")
            s += 5
        
        return CategoryScore("ux_accessibility", max(0, min(100, s)), self._status(s),
                            "Accessibility analysis complete",
                            [f for f in self.findings if f.category == "ux_accessibility"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # PERFORMANCE
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_performance(self) -> CategoryScore:
        s, strengths, weaks = 70, [], []
        
        # Lazy loading
        if self._search(['lazy', 'suspense', 'dynamic(', 'loadable', 'code.split']):
            strengths.append("Code splitting/lazy loading")
            s += 15
        else:
            weaks.append("No code splitting")
            self._add("performance", "medium", "Missing code splitting",
                     "No lazy loading detected",
                     impact="Larger initial bundle",
                     rec="Implement lazy loading for routes", hours=4,
                     ai=True, ai_how="AI can identify split points and implement")
        
        # Memoization
        if self._search(['usememo', 'usecallback', 'memo(', 'memoize', 'lru_cache']):
            strengths.append("Memoization used")
            s += 5
        
        # Image optimization  
        if self._search(['next/image', 'srcset', 'webp', 'avif', 'imageoptim']):
            strengths.append("Image optimization")
            s += 5
        else:
            weaks.append("No image optimization")
            self._add("performance", "low", "No image optimization",
                     "No optimized image handling detected",
                     rec="Use next/image or srcset", hours=3)
        
        # Bundle analysis
        if self._has_file(['webpack-bundle-analyzer', 'source-map-explorer']):
            strengths.append("Bundle analysis tooling")
        
        return CategoryScore("performance", max(0, min(100, s)), self._status(s),
                            "Performance analysis complete",
                            [f for f in self.findings if f.category == "performance"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # TESTING
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_testing(self) -> CategoryScore:
        s, strengths, weaks = 50, [], []
        
        has_tests = self.config.get('features', {}).get('has_tests', False)
        
        if has_tests:
            strengths.append("Test files present")
            s += 20
            
            # Unit tests
            if self._search(['describe(', 'test(', 'it(', 'def test_', '@test']):
                strengths.append("Unit tests detected")
                s += 10
            
            # E2E tests
            if self._search(['playwright', 'cypress', 'e2e', 'selenium']):
                strengths.append("E2E tests detected")
                s += 15
            else:
                weaks.append("No E2E tests")
                self._add("testing", "medium", "No E2E tests",
                         "Missing integration/E2E testing",
                         rec="Add Playwright or Cypress", hours=12,
                         ai=True, ai_how="AI can generate E2E tests from user flows")
        else:
            weaks.append("No tests")
            self._add("testing", "high", "No test coverage",
                     "No test files found",
                     impact="High risk of regressions",
                     rec="Implement testing starting with critical paths", hours=20,
                     ai=True, ai_how="AI can generate initial test suite")
            s -= 20
        
        return CategoryScore("testing", max(0, min(100, s)), self._status(s),
                            "Testing analysis complete",
                            [f for f in self.findings if f.category == "testing"],
                            strengths, weaks)
    
    # ═══════════════════════════════════════════════════════════════
    # DOCUMENTATION
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_documentation(self) -> CategoryScore:
        s, strengths, weaks = 60, [], []
        
        # README
        readme = self.source / "README.md"
        if readme.exists():
            strengths.append("README present")
            s += 15
            try:
                content = readme.read_text()
                if len(content) > 2000:
                    strengths.append("Comprehensive README")
                    s += 10
                elif len(content) < 500:
                    weaks.append("README is minimal")
                    self._add("documentation", "low", "Minimal README",
                             "README is too short",
                             rec="Add setup, usage, architecture", hours=2,
                             ai=True, ai_how="AI can generate comprehensive README")
            except:
                pass
        else:
            weaks.append("No README")
            self._add("documentation", "medium", "Missing README",
                     "No README.md found",
                     rec="Create project documentation", hours=2,
                     ai=True, ai_how="AI can generate README from code")
            s -= 15
        
        # API docs
        if self._has_dir(['docs', 'api-docs']) or self._search(['swagger', 'openapi']):
            strengths.append("API documentation")
            s += 10
        
        # Code comments
        if self._search(['/**', '@param', '@returns', 'args:', 'returns:']):
            strengths.append("Code comments present")
            s += 5
        
        return CategoryScore("documentation", max(0, min(100, s)), self._status(s),
                            "Documentation analysis complete",
                            [f for f in self.findings if f.category == "documentation"],
                            strengths, weaks)


def run_assessment(source_path: str, project_config: Dict) -> AssessmentReport:
    """Run complete assessment"""
    assessor = CodebaseAssessor(Path(source_path), project_config)
    return assessor.assess()
