"""
Health Evaluator Module

Evaluates the health of a codebase across multiple dimensions.
"""

import os
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
import yaml


@dataclass
class CategoryScore:
    """Score for a single category"""
    name: str
    score: int  # 0-100
    status: str  # critical, warning, good, excellent
    issues: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


@dataclass 
class HealthIssue:
    """A specific health issue"""
    id: str
    severity: str  # critical, high, medium, low
    category: str
    title: str
    location: str
    description: str
    fix: str
    effort: str


@dataclass
class HealthReport:
    """Complete health report for a project"""
    project_name: str
    evaluated_at: str
    overall_score: int
    overall_status: str
    categories: list
    critical_issues: list
    high_issues: list
    quick_wins: list
    improvement_summary: dict


# Score thresholds
def get_status(score: int) -> str:
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "warning"
    else:
        return "critical"


class HealthEvaluator:
    """Evaluates codebase health"""
    
    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
    
    def evaluate(self, project_name: str) -> HealthReport:
        """
        Evaluate the health of a project.
        
        Args:
            project_name: Name of the project to evaluate
            
        Returns:
            HealthReport with detailed analysis
        """
        project_dir = self.projects_dir / project_name
        if not project_dir.exists():
            raise ValueError(f"Project not found: {project_name}")
        
        # Load project config
        with open(project_dir / "project.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        source_path = Path(config["project"].get("source_path", ""))
        if not source_path.exists():
            raise ValueError(f"Source path not found: {source_path}")
        
        # Load file index
        file_index = []
        file_index_path = project_dir / "file_index.json"
        if file_index_path.exists():
            with open(file_index_path, encoding="utf-8") as f:
                file_index = json.load(f)
        
        # Run evaluations
        categories = []
        all_issues = []
        
        # Code Quality
        code_quality = self._evaluate_code_quality(source_path, file_index, config)
        categories.append(code_quality)
        
        # Test Coverage
        test_coverage = self._evaluate_test_coverage(source_path, file_index, config)
        categories.append(test_coverage)
        
        # Security
        security = self._evaluate_security(source_path, file_index, config)
        categories.append(security)
        
        # Dependencies
        dependencies = self._evaluate_dependencies(source_path, config)
        categories.append(dependencies)
        
        # Documentation
        documentation = self._evaluate_documentation(source_path, file_index, config)
        categories.append(documentation)
        
        # Architecture
        architecture = self._evaluate_architecture(source_path, file_index, config)
        categories.append(architecture)
        
        # Collect all issues
        for cat in categories:
            for issue in cat.issues:
                if isinstance(issue, dict):
                    all_issues.append(issue)
        
        # Calculate overall score
        overall_score = sum(c.score for c in categories) // len(categories)
        overall_status = get_status(overall_score)
        
        # Separate issues by severity
        critical_issues = [i for i in all_issues if i.get("severity") == "critical"]
        high_issues = [i for i in all_issues if i.get("severity") == "high"]
        
        # Identify quick wins
        quick_wins = self._identify_quick_wins(all_issues, config)
        
        # Create improvement summary
        improvement_summary = {
            "total_issues": len(all_issues),
            "critical": len(critical_issues),
            "high": len(high_issues),
            "estimated_effort": self._estimate_total_effort(all_issues),
        }
        
        from datetime import datetime
        
        return HealthReport(
            project_name=project_name,
            evaluated_at=datetime.now().isoformat(),
            overall_score=overall_score,
            overall_status=overall_status,
            categories=[asdict(c) for c in categories],
            critical_issues=critical_issues,
            high_issues=high_issues,
            quick_wins=quick_wins,
            improvement_summary=improvement_summary,
        )
    
    def _evaluate_code_quality(self, source: Path, files: list, config: dict) -> CategoryScore:
        """Evaluate code quality"""
        score = 70  # Base score
        issues = []
        recommendations = []
        
        # Check for large files
        large_files = [f for f in files if f.get("lines", 0) > 500]
        if large_files:
            score -= min(len(large_files) * 5, 20)
            for lf in large_files[:3]:
                issues.append({
                    "severity": "medium",
                    "category": "code_quality",
                    "title": f"Large file: {lf['relative_path']}",
                    "location": lf["relative_path"],
                    "description": f"File has {lf['lines']} lines",
                    "fix": "Consider breaking into smaller modules",
                    "effort": "2-4 hours"
                })
        
        # Check for very long files (likely god classes)
        god_files = [f for f in files if f.get("lines", 0) > 1000]
        if god_files:
            score -= min(len(god_files) * 10, 30)
            for gf in god_files[:3]:
                issues.append({
                    "severity": "high",
                    "category": "code_quality",
                    "title": f"Potential god class: {gf['relative_path']}",
                    "location": gf["relative_path"],
                    "description": f"File has {gf['lines']} lines - likely doing too much",
                    "fix": "Refactor into smaller, focused classes",
                    "effort": "4-8 hours"
                })
        
        # Check for TypeScript adoption
        ts_files = [f for f in files if f.get("extension") in [".ts", ".tsx"]]
        js_files = [f for f in files if f.get("extension") in [".js", ".jsx"]]
        
        if js_files and not ts_files:
            score -= 10
            recommendations.append("Consider adopting TypeScript for type safety")
        elif js_files and ts_files:
            ts_ratio = len(ts_files) / (len(ts_files) + len(js_files))
            if ts_ratio < 0.5:
                recommendations.append("Continue TypeScript migration")
        
        # Check for linting config
        has_eslint = (source / ".eslintrc").exists() or (source / ".eslintrc.js").exists() or (source / ".eslintrc.json").exists()
        has_prettier = (source / ".prettierrc").exists() or (source / ".prettierrc.js").exists()
        
        if not has_eslint:
            score -= 10
            recommendations.append("Add ESLint for code consistency")
        if not has_prettier:
            score -= 5
            recommendations.append("Add Prettier for formatting")
        
        return CategoryScore(
            name="Code Quality",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_test_coverage(self, source: Path, files: list, config: dict) -> CategoryScore:
        """Evaluate test coverage"""
        score = 50  # Base score (assumes no tests)
        issues = []
        recommendations = []
        
        # Check if tests exist
        has_tests = config.get("features", {}).get("has_tests", False)
        
        test_files = [f for f in files if 
                      ".test." in f.get("relative_path", "") or
                      ".spec." in f.get("relative_path", "") or
                      "_test." in f.get("relative_path", "") or
                      "/test/" in f.get("relative_path", "") or
                      "/tests/" in f.get("relative_path", "")]
        
        source_files = [f for f in files if f.get("language") != "Unknown"]
        
        if not has_tests and not test_files:
            score = 10
            issues.append({
                "severity": "critical",
                "category": "test_coverage",
                "title": "No tests found",
                "location": "project",
                "description": "No test files detected in the project",
                "fix": "Add unit tests for critical business logic",
                "effort": "16-40 hours"
            })
        elif test_files:
            # Estimate coverage based on ratio
            ratio = len(test_files) / max(len(source_files), 1)
            if ratio < 0.1:
                score = 30
                issues.append({
                    "severity": "high",
                    "category": "test_coverage",
                    "title": "Low test coverage",
                    "location": "project",
                    "description": f"Only {len(test_files)} test files for {len(source_files)} source files",
                    "fix": "Add tests for critical paths",
                    "effort": "16-24 hours"
                })
            elif ratio < 0.3:
                score = 50
                recommendations.append("Increase test coverage to at least 60%")
            elif ratio < 0.5:
                score = 70
                recommendations.append("Good test coverage, aim for 80%")
            else:
                score = 85
        
        # Check for testing framework
        tech_stack = config.get("tech_stack", {})
        testing = tech_stack.get("testing", [])
        
        if not testing:
            score -= 10
            recommendations.append("Add a testing framework (Jest, pytest, etc.)")
        
        return CategoryScore(
            name="Test Coverage",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_security(self, source: Path, files: list, config: dict) -> CategoryScore:
        """Evaluate security posture"""
        score = 80  # Base score
        issues = []
        recommendations = []
        
        # Check for .env file committed (should be .env.example)
        if (source / ".env").exists():
            # Check if it's in gitignore
            gitignore = source / ".gitignore"
            env_ignored = False
            if gitignore.exists():
                with open(gitignore, encoding="utf-8") as f:
                    if ".env" in f.read():
                        env_ignored = True
            
            if not env_ignored:
                score -= 20
                issues.append({
                    "severity": "high",
                    "category": "security",
                    "title": ".env file may be committed",
                    "location": ".env",
                    "description": ".env file exists and may not be in .gitignore",
                    "fix": "Add .env to .gitignore, use .env.example for templates",
                    "effort": "30 minutes"
                })
        
        # Check for hardcoded secrets patterns (simplified)
        secret_patterns = ["api_key", "apikey", "secret", "password", "token", "credential"]
        
        for f in files[:100]:  # Check first 100 files
            file_path = source / f.get("relative_path", "")
            if file_path.exists() and f.get("extension") in [".js", ".ts", ".py", ".json"]:
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as fp:
                        content = fp.read().lower()
                        for pattern in secret_patterns:
                            if f'"{pattern}"' in content or f"'{pattern}'" in content:
                                if "example" not in f.get("relative_path", "").lower():
                                    score -= 5
                                    break
                except:
                    pass
        
        # Check for HTTPS usage in configs
        # Check for authentication middleware indicators
        
        has_auth = any("auth" in f.get("relative_path", "").lower() for f in files)
        if not has_auth:
            recommendations.append("Ensure authentication is properly implemented")
        
        return CategoryScore(
            name="Security",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_dependencies(self, source: Path, config: dict) -> CategoryScore:
        """Evaluate dependency health"""
        score = 70  # Base score
        issues = []
        recommendations = []
        
        # Check package.json
        package_json = source / "package.json"
        if package_json.exists():
            try:
                with open(package_json, encoding="utf-8") as f:
                    pkg = json.load(f)
                
                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})
                all_deps = {**deps, **dev_deps}
                
                # Check for very old React
                if "react" in deps:
                    version = deps["react"].replace("^", "").replace("~", "").split(".")[0]
                    try:
                        if int(version) < 18:
                            score -= 15
                            issues.append({
                                "severity": "medium",
                                "category": "dependencies",
                                "title": f"Outdated React version: {deps['react']}",
                                "location": "package.json",
                                "description": "React version is behind current (19)",
                                "fix": "Upgrade React following migration guide",
                                "effort": "4-16 hours"
                            })
                    except:
                        pass
                
                # Check for lock file
                has_lock = (source / "package-lock.json").exists() or (source / "yarn.lock").exists() or (source / "pnpm-lock.yaml").exists()
                if not has_lock:
                    score -= 10
                    issues.append({
                        "severity": "medium",
                        "category": "dependencies",
                        "title": "No lock file found",
                        "location": "project root",
                        "description": "Missing package-lock.json or yarn.lock",
                        "fix": "Run npm install to generate lock file",
                        "effort": "5 minutes"
                    })
                
            except Exception as e:
                pass
        
        # Check requirements.txt for Python
        requirements = source / "requirements.txt"
        if requirements.exists():
            try:
                with open(requirements, encoding="utf-8") as f:
                    lines = f.readlines()
                
                # Check for pinned versions
                unpinned = [l.strip() for l in lines if l.strip() and not any(c in l for c in ["==", ">=", "<=", ">", "<"])]
                if unpinned:
                    score -= 10
                    recommendations.append(f"Pin versions for: {', '.join(unpinned[:5])}")
            except:
                pass
        
        return CategoryScore(
            name="Dependencies",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_documentation(self, source: Path, files: list, config: dict) -> CategoryScore:
        """Evaluate documentation"""
        score = 50  # Base score
        issues = []
        recommendations = []
        
        # Check for README
        has_readme = (source / "README.md").exists() or (source / "README.rst").exists()
        if has_readme:
            score += 20
            # Check README length
            readme_path = source / "README.md" if (source / "README.md").exists() else source / "README.rst"
            try:
                with open(readme_path, encoding="utf-8") as f:
                    readme_lines = len(f.readlines())
                if readme_lines < 20:
                    score -= 10
                    recommendations.append("Expand README with setup instructions and usage")
                elif readme_lines > 50:
                    score += 10
            except:
                pass
        else:
            score -= 20
            issues.append({
                "severity": "medium",
                "category": "documentation",
                "title": "No README found",
                "location": "project root",
                "description": "Missing README.md file",
                "fix": "Add README with project description, setup, and usage",
                "effort": "1-2 hours"
            })
        
        # Check for API documentation
        has_api_docs = any("api" in f.get("relative_path", "").lower() and 
                          ("doc" in f.get("relative_path", "").lower() or
                           "swagger" in f.get("relative_path", "").lower() or
                           "openapi" in f.get("relative_path", "").lower())
                          for f in files)
        
        if not has_api_docs:
            recommendations.append("Add API documentation (OpenAPI/Swagger)")
        else:
            score += 15
        
        # Check for CHANGELOG
        has_changelog = (source / "CHANGELOG.md").exists() or (source / "HISTORY.md").exists()
        if has_changelog:
            score += 10
        else:
            recommendations.append("Add CHANGELOG.md to track changes")
        
        return CategoryScore(
            name="Documentation",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_architecture(self, source: Path, files: list, config: dict) -> CategoryScore:
        """Evaluate architecture"""
        score = 70  # Base score
        issues = []
        recommendations = []
        
        # Check for clear structure
        has_src = (source / "src").exists()
        has_lib = (source / "lib").exists()
        
        if not has_src and not has_lib:
            score -= 10
            recommendations.append("Organize code into src/ directory")
        
        # Check for separation of concerns
        entry_points = config.get("entry_points", [])
        if len(entry_points) > 5:
            score -= 10
            recommendations.append("Too many entry points - consider consolidating")
        
        # Check for config separation
        config_files = config.get("config_files", [])
        has_config_dir = (source / "config").exists() or (source / "src" / "config").exists()
        
        if not has_config_dir and len(config_files) > 3:
            recommendations.append("Consider organizing config files into config/ directory")
        
        return CategoryScore(
            name="Architecture",
            score=max(0, min(100, score)),
            status=get_status(score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _identify_quick_wins(self, issues: list, config: dict) -> list:
        """Identify quick wins from issues"""
        quick_wins = []
        
        for issue in issues:
            effort = issue.get("effort", "")
            if any(x in effort.lower() for x in ["minute", "30 min", "1 hour", "5 min"]):
                quick_wins.append({
                    "title": issue.get("title"),
                    "effort": effort,
                    "impact": f"Fixes {issue.get('severity')} {issue.get('category')} issue"
                })
        
        # Add general quick wins
        tech_stack = config.get("tech_stack", {})
        if not tech_stack.get("testing"):
            quick_wins.append({
                "title": "Add testing framework",
                "effort": "1-2 hours",
                "impact": "Enables automated testing"
            })
        
        return quick_wins[:5]  # Top 5 quick wins
    
    def _estimate_total_effort(self, issues: list) -> str:
        """Estimate total effort to fix all issues"""
        total_hours = 0
        
        for issue in issues:
            effort = issue.get("effort", "")
            # Parse effort string
            if "hour" in effort.lower():
                try:
                    parts = effort.lower().replace("hours", "").replace("hour", "").strip()
                    if "-" in parts:
                        low, high = parts.split("-")
                        total_hours += (int(low.strip()) + int(high.strip())) / 2
                    else:
                        total_hours += int(parts.strip())
                except:
                    total_hours += 4  # Default estimate
            elif "minute" in effort.lower():
                total_hours += 0.5
            else:
                total_hours += 4
        
        if total_hours < 10:
            return f"{int(total_hours)}-{int(total_hours * 1.5)} hours"
        elif total_hours < 40:
            return f"{int(total_hours)}-{int(total_hours * 1.3)} hours"
        else:
            return f"{int(total_hours // 40)}-{int(total_hours * 1.3 // 40)} weeks"


def evaluate_project(project_name: str) -> HealthReport:
    """
    Convenience function to evaluate a project.
    
    Args:
        project_name: Name of the project
        
    Returns:
        HealthReport
    """
    evaluator = HealthEvaluator()
    return evaluator.evaluate(project_name)
