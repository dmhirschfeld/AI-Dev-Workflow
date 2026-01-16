"""
Static Analysis Integration
Integrates Semgrep, ESLint, Trivy and other static analysis tools with the agent workflow.
"""

import subprocess
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime


@dataclass
class Finding:
    """A single finding from static analysis"""
    tool: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    message: str
    file_path: str
    line: int | None = None
    rule_id: str | None = None
    category: str | None = None
    fix_available: bool = False
    
    def to_context(self) -> str:
        """Format finding for agent context"""
        loc = f"{self.file_path}"
        if self.line:
            loc += f":{self.line}"
        return f"[{self.severity.upper()}] {self.message} ({loc})"


@dataclass
class AnalysisResult:
    """Results from a static analysis tool"""
    tool: str
    success: bool
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    
    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")
    
    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")
    
    @property
    def summary(self) -> str:
        if not self.success:
            return f"{self.tool}: Error - {self.error}"
        
        if not self.findings:
            return f"{self.tool}: No issues found ✓"
        
        counts = {
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": sum(1 for f in self.findings if f.severity == "medium"),
            "low": sum(1 for f in self.findings if f.severity == "low"),
        }
        
        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        return f"{self.tool}: {', '.join(parts)}"


class StaticAnalyzer:
    """Runs static analysis tools and aggregates results"""
    
    def __init__(self):
        self.available_tools = self._detect_tools()
    
    def _detect_tools(self) -> dict[str, bool]:
        """Detect which tools are installed"""
        tools = {
            "semgrep": self._check_command("semgrep", "--version"),
            "eslint": self._check_command("eslint", "--version"),
            "trivy": self._check_command("trivy", "--version"),
            "hadolint": self._check_command("hadolint", "--version"),
        }
        return tools
    
    def _check_command(self, *cmd) -> bool:
        """Check if a command is available"""
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def run_semgrep(self, path: str, config: str = "auto") -> AnalysisResult:
        """Run Semgrep security scanner"""
        if not self.available_tools.get("semgrep"):
            return AnalysisResult(
                tool="semgrep",
                success=False,
                error="Semgrep not installed. Run: pip install semgrep"
            )
        
        start = datetime.now()
        
        try:
            result = subprocess.run(
                ["semgrep", "--config", config, "--json", "--quiet", path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            duration = int((datetime.now() - start).total_seconds() * 1000)
            
            if result.returncode not in (0, 1):  # 1 means findings exist
                return AnalysisResult(
                    tool="semgrep",
                    success=False,
                    error=result.stderr,
                    duration_ms=duration
                )
            
            data = json.loads(result.stdout) if result.stdout else {}
            
            findings = []
            for item in data.get("results", []):
                severity_map = {
                    "ERROR": "high",
                    "WARNING": "medium",
                    "INFO": "info"
                }
                
                findings.append(Finding(
                    tool="semgrep",
                    severity=severity_map.get(item.get("extra", {}).get("severity", ""), "medium"),
                    message=item.get("extra", {}).get("message", ""),
                    file_path=item.get("path", ""),
                    line=item.get("start", {}).get("line"),
                    rule_id=item.get("check_id"),
                    category="security"
                ))
            
            return AnalysisResult(
                tool="semgrep",
                success=True,
                findings=findings,
                duration_ms=duration
            )
            
        except subprocess.TimeoutExpired:
            return AnalysisResult(
                tool="semgrep",
                success=False,
                error="Timeout after 300 seconds"
            )
        except Exception as e:
            return AnalysisResult(
                tool="semgrep",
                success=False,
                error=str(e)
            )
    
    def run_eslint(self, path: str) -> AnalysisResult:
        """Run ESLint on JavaScript/TypeScript files"""
        if not self.available_tools.get("eslint"):
            return AnalysisResult(
                tool="eslint",
                success=False,
                error="ESLint not installed. Run: npm install -g eslint"
            )
        
        start = datetime.now()
        
        try:
            result = subprocess.run(
                ["eslint", "--format", "json", "--ext", ".js,.ts,.jsx,.tsx", path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            duration = int((datetime.now() - start).total_seconds() * 1000)
            
            data = json.loads(result.stdout) if result.stdout else []
            
            findings = []
            for file_result in data:
                for msg in file_result.get("messages", []):
                    severity = "high" if msg.get("severity") == 2 else "medium"
                    
                    findings.append(Finding(
                        tool="eslint",
                        severity=severity,
                        message=msg.get("message", ""),
                        file_path=file_result.get("filePath", ""),
                        line=msg.get("line"),
                        rule_id=msg.get("ruleId"),
                        category="style" if "style" in (msg.get("ruleId") or "") else "quality",
                        fix_available=msg.get("fix") is not None
                    ))
            
            return AnalysisResult(
                tool="eslint",
                success=True,
                findings=findings,
                duration_ms=duration
            )
            
        except Exception as e:
            return AnalysisResult(
                tool="eslint",
                success=False,
                error=str(e)
            )
    
    def run_trivy(self, path: str, scan_type: str = "fs") -> AnalysisResult:
        """Run Trivy vulnerability scanner"""
        if not self.available_tools.get("trivy"):
            return AnalysisResult(
                tool="trivy",
                success=False,
                error="Trivy not installed. Run: brew install trivy"
            )
        
        start = datetime.now()
        
        try:
            result = subprocess.run(
                ["trivy", scan_type, "--format", "json", "--quiet", path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            duration = int((datetime.now() - start).total_seconds() * 1000)
            
            data = json.loads(result.stdout) if result.stdout else {}
            
            findings = []
            for result_item in data.get("Results", []):
                target = result_item.get("Target", "")
                
                for vuln in result_item.get("Vulnerabilities", []):
                    severity_map = {
                        "CRITICAL": "critical",
                        "HIGH": "high",
                        "MEDIUM": "medium",
                        "LOW": "low",
                        "UNKNOWN": "info"
                    }
                    
                    pkg = vuln.get("PkgName", "")
                    version = vuln.get("InstalledVersion", "")
                    fixed = vuln.get("FixedVersion", "")
                    
                    message = f"{pkg}@{version} has {vuln.get('VulnerabilityID', 'vulnerability')}"
                    if fixed:
                        message += f" (fix: upgrade to {fixed})"
                    
                    findings.append(Finding(
                        tool="trivy",
                        severity=severity_map.get(vuln.get("Severity", ""), "medium"),
                        message=message,
                        file_path=target,
                        rule_id=vuln.get("VulnerabilityID"),
                        category="vulnerability",
                        fix_available=bool(fixed)
                    ))
            
            return AnalysisResult(
                tool="trivy",
                success=True,
                findings=findings,
                duration_ms=duration
            )
            
        except Exception as e:
            return AnalysisResult(
                tool="trivy",
                success=False,
                error=str(e)
            )
    
    def run_hadolint(self, dockerfile_path: str) -> AnalysisResult:
        """Run Hadolint on Dockerfile"""
        if not self.available_tools.get("hadolint"):
            return AnalysisResult(
                tool="hadolint",
                success=False,
                error="Hadolint not installed. Run: brew install hadolint"
            )
        
        if not Path(dockerfile_path).exists():
            return AnalysisResult(
                tool="hadolint",
                success=False,
                error=f"Dockerfile not found: {dockerfile_path}"
            )
        
        start = datetime.now()
        
        try:
            result = subprocess.run(
                ["hadolint", "--format", "json", dockerfile_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            duration = int((datetime.now() - start).total_seconds() * 1000)
            
            data = json.loads(result.stdout) if result.stdout else []
            
            findings = []
            severity_map = {
                "error": "high",
                "warning": "medium",
                "info": "low",
                "style": "info"
            }
            
            for item in data:
                findings.append(Finding(
                    tool="hadolint",
                    severity=severity_map.get(item.get("level", ""), "medium"),
                    message=item.get("message", ""),
                    file_path=dockerfile_path,
                    line=item.get("line"),
                    rule_id=item.get("code"),
                    category="dockerfile"
                ))
            
            return AnalysisResult(
                tool="hadolint",
                success=True,
                findings=findings,
                duration_ms=duration
            )
            
        except Exception as e:
            return AnalysisResult(
                tool="hadolint",
                success=False,
                error=str(e)
            )
    
    def run_all(self, path: str) -> list[AnalysisResult]:
        """Run all available static analysis tools"""
        results = []
        
        # Semgrep for security
        results.append(self.run_semgrep(path))
        
        # ESLint for JS/TS
        if any(Path(path).rglob("*.ts")) or any(Path(path).rglob("*.js")):
            results.append(self.run_eslint(path))
        
        # Trivy for dependencies
        results.append(self.run_trivy(path))
        
        # Hadolint for Dockerfiles
        dockerfile = Path(path) / "Dockerfile"
        if dockerfile.exists():
            results.append(self.run_hadolint(str(dockerfile)))
        
        return results
    
    def generate_context(self, results: list[AnalysisResult]) -> str:
        """Generate context string for Claude agents"""
        
        lines = ["## Static Analysis Results\n"]
        
        # Summary
        lines.append("### Summary\n")
        for result in results:
            lines.append(f"- {result.summary}")
        lines.append("")
        
        # Critical and High findings
        critical_high = []
        for result in results:
            for finding in result.findings:
                if finding.severity in ("critical", "high"):
                    critical_high.append(finding)
        
        if critical_high:
            lines.append("### Critical/High Priority Issues\n")
            for finding in critical_high:
                lines.append(finding.to_context())
            lines.append("")
        
        # Medium findings (abbreviated)
        medium = []
        for result in results:
            for finding in result.findings:
                if finding.severity == "medium":
                    medium.append(finding)
        
        if medium:
            lines.append(f"### Medium Priority Issues ({len(medium)} total)\n")
            for finding in medium[:10]:  # First 10 only
                lines.append(finding.to_context())
            if len(medium) > 10:
                lines.append(f"... and {len(medium) - 10} more")
            lines.append("")
        
        return "\n".join(lines)


def analyze_project(path: str) -> str:
    """Run full analysis and return context for agents"""
    analyzer = StaticAnalyzer()
    results = analyzer.run_all(path)
    return analyzer.generate_context(results)


if __name__ == "__main__":
    import sys
    
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    analyzer = StaticAnalyzer()
    
    print("Available tools:")
    for tool, available in analyzer.available_tools.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")
    
    print(f"\nRunning analysis on: {path}\n")
    
    results = analyzer.run_all(path)
    print(analyzer.generate_context(results))
