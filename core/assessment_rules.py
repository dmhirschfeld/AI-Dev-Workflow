"""
Assessment Rules Engine - Deterministic checks that run before AI assessment.

Rules are either:
- Built-in: Ship with the system (security, architecture basics)
- Learned: Extracted from high-confidence lessons

Rules provide fast, predictable checks. AI fills in the gaps.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime

from core.lessons_database import LessonsDatabase, Rule


@dataclass
class Finding:
    """A finding from a rule check."""
    rule_id: str
    rule_name: str
    severity: str           # "critical", "high", "medium", "low", "info"
    description: str
    evidence: list[str]     # File paths, code snippets, etc.
    recommendation: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation
        }

    def format_markdown(self) -> str:
        """Format finding as markdown."""
        evidence_str = "\n".join(f"  - {e}" for e in self.evidence[:5])
        if len(self.evidence) > 5:
            evidence_str += f"\n  - ... and {len(self.evidence) - 5} more"

        return f"""### {self.severity.upper()}: {self.rule_name}

{self.description}

**Evidence:**
{evidence_str}

**Recommendation:** {self.recommendation}
"""


@dataclass
class AssessmentContext:
    """Context passed to rules for evaluation."""
    project_path: Path
    file_list: list[str]            # All files in project
    file_contents: dict[str, str]   # path -> content (for sampled files)
    project_type: str               # "web", "api", "cli", "library", etc.
    languages: list[str]            # Detected languages
    frameworks: list[str]           # Detected frameworks
    has_tests: bool
    has_database: bool
    has_frontend: bool
    has_api: bool

    @classmethod
    def from_codebase_summary(cls, summary: dict, project_path: Path) -> "AssessmentContext":
        """Create context from a codebase summary dict."""
        return cls(
            project_path=project_path,
            file_list=summary.get("files", []),
            file_contents=summary.get("file_contents", {}),
            project_type=summary.get("project_type", "unknown"),
            languages=summary.get("languages", []),
            frameworks=summary.get("frameworks", []),
            has_tests=summary.get("has_tests", False),
            has_database=summary.get("has_database", False),
            has_frontend=summary.get("has_frontend", False),
            has_api=summary.get("has_api", False)
        )


class RulesEngine:
    """Runs deterministic rules before AI assessment."""

    def __init__(self, lessons_db: Optional[LessonsDatabase] = None):
        self.lessons_db = lessons_db or LessonsDatabase()
        self.condition_checkers = self._build_condition_checkers()

    def _build_condition_checkers(self) -> dict[str, Callable[[AssessmentContext], bool]]:
        """Build condition checker functions."""
        return {
            "always": lambda ctx: True,
            "has_database": lambda ctx: ctx.has_database,
            "has_frontend": lambda ctx: ctx.has_frontend,
            "has_api": lambda ctx: ctx.has_api,
            "has_tests": lambda ctx: ctx.has_tests,
            "has_layers": lambda ctx: self._detect_layers(ctx),
            "is_web": lambda ctx: ctx.project_type == "web",
            "is_python": lambda ctx: "python" in [l.lower() for l in ctx.languages],
            "is_javascript": lambda ctx: any(l.lower() in ["javascript", "typescript"] for l in ctx.languages),
        }

    def _detect_layers(self, ctx: AssessmentContext) -> bool:
        """Detect if project has architectural layers."""
        layer_indicators = ["controller", "service", "repository", "model", "view", "handler", "middleware"]
        file_list_lower = " ".join(ctx.file_list).lower()
        return sum(1 for ind in layer_indicators if ind in file_list_lower) >= 2

    def check_condition(self, condition: str, context: AssessmentContext) -> bool:
        """Check if a rule condition is met."""
        checker = self.condition_checkers.get(condition)
        if checker:
            return checker(context)
        # Default: assume condition is met if not recognized
        return True

    def run_rules(self, step_name: str, context: AssessmentContext) -> list[Finding]:
        """Run all rules for a step and return findings."""
        findings = []

        # Get rules from lessons database (includes built-in rules)
        rules = self.lessons_db.get_rules(step_name)

        for rule in rules:
            if self.check_condition(rule.condition, context):
                rule_findings = self._apply_rule(rule, context, step_name)
                findings.extend(rule_findings)

        return findings

    def _apply_rule(self, rule: Rule, context: AssessmentContext, step_name: str) -> list[Finding]:
        """Apply a single rule and return findings."""
        # Route to specific rule implementation
        rule_impl = self._get_rule_implementation(rule.id, step_name)
        if rule_impl:
            return rule_impl(rule, context)

        # For learned rules without implementation, just return the action as guidance
        # (The AI will use this guidance in its assessment)
        return []

    def _get_rule_implementation(self, rule_id: str, step_name: str) -> Optional[Callable]:
        """Get the implementation function for a built-in rule."""
        implementations = {
            # Security rules
            "builtin_sec_001": self._check_hardcoded_secrets,
            "builtin_sec_002": self._check_sql_injection,
            "builtin_sec_003": self._check_xss,

            # Architecture rules
            "builtin_arch_001": self._check_circular_deps,
            "builtin_arch_002": self._check_layer_violations,

            # Code quality rules
            "builtin_cq_001": self._check_code_duplication,
            "builtin_cq_002": self._check_function_complexity,

            # Testing rules
            "builtin_test_001": self._check_test_coverage,
        }
        return implementations.get(rule_id)

    # ========== Rule Implementations ==========

    def _check_hardcoded_secrets(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for hardcoded secrets in code."""
        findings = []
        secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']{10,}["\']', "API Key"),
            (r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\'][^"\']{6,}["\']', "Password/Secret"),
            (r'(?i)(token|auth[_-]?token)\s*[=:]\s*["\'][^"\']{10,}["\']', "Token"),
            (r'(?i)(aws[_-]?access[_-]?key)\s*[=:]\s*["\'][A-Z0-9]{16,}["\']', "AWS Key"),
            (r'(?i)(private[_-]?key)\s*[=:]\s*["\'][^"\']{20,}["\']', "Private Key"),
        ]

        evidence = []
        for file_path, content in ctx.file_contents.items():
            # Skip common non-code files
            if any(skip in file_path.lower() for skip in [".env.example", "test", "mock", "fixture"]):
                continue

            for pattern, secret_type in secret_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    evidence.append(f"{file_path}: Possible {secret_type}")

        if evidence:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="critical",
                description="Potential hardcoded secrets detected in source code",
                evidence=evidence[:10],  # Limit evidence
                recommendation="Move secrets to environment variables or a secrets manager"
            ))

        return findings

    def _check_sql_injection(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for SQL injection vulnerabilities."""
        findings = []
        # Simple pattern matching for string concatenation in SQL
        sql_patterns = [
            (r'["\']SELECT.*\+.*["\']', "String concatenation in SELECT"),
            (r'["\']INSERT.*\+.*["\']', "String concatenation in INSERT"),
            (r'["\']UPDATE.*\+.*["\']', "String concatenation in UPDATE"),
            (r'["\']DELETE.*\+.*["\']', "String concatenation in DELETE"),
            (r'f["\']SELECT.*\{', "f-string in SQL query"),
            (r'\.format\(.*SELECT', "format() in SQL query"),
        ]

        evidence = []
        for file_path, content in ctx.file_contents.items():
            for pattern, issue_type in sql_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    evidence.append(f"{file_path}: {issue_type}")

        if evidence:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="high",
                description="Potential SQL injection vulnerabilities detected",
                evidence=evidence[:10],
                recommendation="Use parameterized queries or an ORM instead of string concatenation"
            ))

        return findings

    def _check_xss(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for XSS vulnerabilities."""
        findings = []
        xss_patterns = [
            (r'innerHTML\s*=', "Direct innerHTML assignment"),
            (r'document\.write\(', "document.write usage"),
            (r'dangerouslySetInnerHTML', "dangerouslySetInnerHTML in React"),
            (r'v-html\s*=', "v-html directive in Vue"),
            (r'\|\s*safe\s*\}', "safe filter in templates"),
        ]

        evidence = []
        for file_path, content in ctx.file_contents.items():
            if not any(ext in file_path for ext in [".js", ".jsx", ".ts", ".tsx", ".vue", ".html"]):
                continue

            for pattern, issue_type in xss_patterns:
                if re.search(pattern, content):
                    evidence.append(f"{file_path}: {issue_type}")

        if evidence:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="high",
                description="Potential XSS vulnerabilities detected",
                evidence=evidence[:10],
                recommendation="Sanitize user input and use framework-provided escaping"
            ))

        return findings

    def _check_circular_deps(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for circular dependencies (simplified check)."""
        # This is a simplified check - full implementation would require import graph analysis
        findings = []

        # Look for patterns that often indicate circular deps
        evidence = []
        for file_path, content in ctx.file_contents.items():
            # Check for late imports (often used to work around circular deps)
            if re.search(r'def\s+\w+\([^)]*\):\s*\n\s+import\s+', content):
                evidence.append(f"{file_path}: Import inside function (possible circular dep workaround)")

            # Check for TYPE_CHECKING imports (another circular dep pattern)
            if "TYPE_CHECKING" in content and "from __future__" in content:
                evidence.append(f"{file_path}: Uses TYPE_CHECKING (possible circular dep)")

        if evidence:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="medium",
                description="Patterns suggesting circular dependencies detected",
                evidence=evidence[:10],
                recommendation="Review import structure and consider dependency injection or interface segregation"
            ))

        return findings

    def _check_layer_violations(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for architectural layer violations."""
        # Simplified check - would need project-specific layer config for accuracy
        return []  # Placeholder - complex to implement generically

    def _check_code_duplication(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for code duplication (simplified)."""
        # This would need a proper duplication detection algorithm
        # For now, just flag if there are suspiciously similar file names
        findings = []

        file_basenames = [Path(f).stem for f in ctx.file_list]
        duplicates = []
        seen = {}

        for name in file_basenames:
            # Normalize name (remove numbers, common suffixes)
            normalized = re.sub(r'\d+|_old|_new|_backup|_copy', '', name.lower())
            if normalized in seen:
                duplicates.append(f"{name} similar to {seen[normalized]}")
            else:
                seen[normalized] = name

        if len(duplicates) > 3:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="low",
                description="Potentially duplicated files detected",
                evidence=duplicates[:10],
                recommendation="Review for code duplication and consider consolidation"
            ))

        return findings

    def _check_function_complexity(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check for overly complex functions (simplified)."""
        findings = []
        evidence = []

        for file_path, content in ctx.file_contents.items():
            # Count lines per function (very rough approximation)
            # Look for long function definitions
            if ".py" in file_path:
                # Python: find def ... and count until next def or class
                functions = re.findall(r'def\s+(\w+)\([^)]*\):[^\n]*\n((?:(?!def\s|class\s)[^\n]*\n){50,})', content)
                for func_name, _ in functions:
                    evidence.append(f"{file_path}: {func_name}() may be too long")

            elif any(ext in file_path for ext in [".js", ".ts", ".jsx", ".tsx"]):
                # JS/TS: rough check for long functions
                functions = re.findall(r'(?:function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?function)', content)
                # This is a very rough heuristic

        if evidence:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="medium",
                description="Potentially complex functions detected",
                evidence=evidence[:10],
                recommendation="Consider breaking down large functions into smaller, focused functions"
            ))

        return findings

    def _check_test_coverage(self, rule: Rule, ctx: AssessmentContext) -> list[Finding]:
        """Check test coverage (simplified - just checks for test files)."""
        findings = []

        test_files = [f for f in ctx.file_list if "test" in f.lower() or "spec" in f.lower()]
        source_files = [f for f in ctx.file_list
                       if any(ext in f for ext in [".py", ".js", ".ts", ".jsx", ".tsx"])
                       and "test" not in f.lower() and "spec" not in f.lower()]

        if source_files and not test_files:
            findings.append(Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="medium",
                description="No test files found",
                evidence=["No test files detected in the project"],
                recommendation="Add unit tests for critical functionality"
            ))
        elif test_files and source_files:
            ratio = len(test_files) / len(source_files)
            if ratio < 0.3:
                findings.append(Finding(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity="low",
                    description=f"Low test-to-source ratio ({len(test_files)} tests for {len(source_files)} source files)",
                    evidence=[f"Test files: {len(test_files)}", f"Source files: {len(source_files)}"],
                    recommendation="Consider adding more tests to improve coverage"
                ))

        return findings

    def format_findings_markdown(self, findings: list[Finding]) -> str:
        """Format all findings as markdown."""
        if not findings:
            return "No issues found by rules engine."

        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
        for f in findings:
            by_severity.get(f.severity, by_severity["info"]).append(f)

        sections = []
        for severity in ["critical", "high", "medium", "low", "info"]:
            if by_severity[severity]:
                sections.append(f"## {severity.upper()} Issues\n")
                for finding in by_severity[severity]:
                    sections.append(finding.format_markdown())

        return "\n".join(sections)

    def get_rule_guidance(self, step_name: str, context: AssessmentContext) -> str:
        """Get guidance for AI from learned rules (rules without implementations)."""
        rules = self.lessons_db.get_rules(step_name)
        learned_rules = [r for r in rules if not r.id.startswith("builtin_")]

        if not learned_rules:
            return ""

        guidance_lines = ["## Additional Checks (from learned patterns):\n"]
        for rule in learned_rules:
            if self.check_condition(rule.condition, context):
                guidance_lines.append(f"- {rule.name}: {rule.action}")

        return "\n".join(guidance_lines)


if __name__ == "__main__":
    # Quick test
    from core.lessons_database import initialize_database

    db = initialize_database()
    engine = RulesEngine(db)

    # Create a test context
    ctx = AssessmentContext(
        project_path=Path("."),
        file_list=["main.py", "utils.py", "test_main.py"],
        file_contents={
            "main.py": 'API_KEY = "sk-1234567890abcdef"\ndef foo():\n    pass',
        },
        project_type="cli",
        languages=["python"],
        frameworks=[],
        has_tests=True,
        has_database=False,
        has_frontend=False,
        has_api=False
    )

    findings = engine.run_rules("security", ctx)
    print(engine.format_findings_markdown(findings))
