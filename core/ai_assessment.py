"""
AI-Powered Assessment Module

Replaces heuristic-based assessment with AI agents that:
1. Run deterministic rules first (fast, predictable)
2. Use AI to fill gaps with lessons learned context
3. Merge results into comprehensive assessment

Each step can be run independently and voted on.
"""

import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime

from core.lessons_database import LessonsDatabase, Lesson, Example
from core.assessment_rules import RulesEngine, AssessmentContext, Finding
from core.agents import AgentFactory, AgentExecutor


@dataclass
class StepResult:
    """Result of a single assessment step."""
    step_name: str
    score: int                      # 0-100
    status: str                     # "critical", "warning", "good", "excellent"
    summary: str
    findings: list[Finding]
    strengths: list[str]
    weaknesses: list[str]
    rule_findings: list[Finding]    # From rules engine
    ai_findings: list[Finding]      # From AI agent
    raw_ai_response: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "score": self.score,
            "status": self.status,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "rule_findings_count": len(self.rule_findings),
            "ai_findings_count": len(self.ai_findings)
        }

    def format_for_voting(self) -> str:
        """Format result for voter review."""
        findings_str = "\n".join([
            f"- [{f.severity.upper()}] {f.rule_name}: {f.description}"
            for f in self.findings[:10]
        ])
        if len(self.findings) > 10:
            findings_str += f"\n... and {len(self.findings) - 10} more findings"

        strengths_str = "\n".join([f"- {s}" for s in self.strengths])
        weaknesses_str = "\n".join([f"- {w}" for w in self.weaknesses])

        return f"""# {self.step_name.replace('_', ' ').title()} Assessment

## Score: {self.score}/100 ({self.status})

## Summary
{self.summary}

## Strengths
{strengths_str if strengths_str else "None identified"}

## Weaknesses
{weaknesses_str if weaknesses_str else "None identified"}

## Findings ({len(self.findings)} total)
{findings_str if findings_str else "No findings"}
"""


class AIAssessmentAgent:
    """Base class for AI-powered assessment steps."""

    # Map assessment steps to predefined agent IDs from definitions.yaml
    STEP_TO_AGENT = {
        "architecture": "solutions_architect",
        "code_quality": "code_reviewer",
        "tech_debt": "tech_debt_analyst",
        "security": "security_specialist",
        "ux_navigation": "ux_navigation",
        "ux_styling": "ux_styling",
        "ux_accessibility": "ux_accessibility",
        "performance": "performance",
        "testing": "test_writer",
        "documentation": "technical_writer"
    }

    # Fallback role/focus for prompt building if agent not found
    STEP_METADATA = {
        "architecture": {
            "role": "Architecture Assessor",
            "focus": "code organization, module structure, dependency management, design patterns"
        },
        "code_quality": {
            "role": "Code Quality Assessor",
            "focus": "coding standards, linting, formatting, type safety, code smells"
        },
        "tech_debt": {
            "role": "Tech Debt Assessor",
            "focus": "TODOs, deprecated dependencies, outdated patterns, upgrade paths"
        },
        "security": {
            "role": "Security Assessor",
            "focus": "vulnerabilities, secrets management, authentication, input validation"
        },
        "ux_navigation": {
            "role": "UX Navigation Assessor",
            "focus": "routing, navigation components, user flow, error handling"
        },
        "ux_styling": {
            "role": "UX Styling Assessor",
            "focus": "CSS frameworks, design systems, responsive design, theming"
        },
        "ux_accessibility": {
            "role": "Accessibility Assessor",
            "focus": "ARIA, semantic HTML, screen reader support, keyboard navigation"
        },
        "performance": {
            "role": "Performance Assessor",
            "focus": "code splitting, lazy loading, caching, bundle size, optimization"
        },
        "testing": {
            "role": "Testing Assessor",
            "focus": "test coverage, unit tests, E2E tests, test quality"
        },
        "documentation": {
            "role": "Documentation Assessor",
            "focus": "README, API docs, code comments, architecture docs"
        }
    }

    def __init__(
        self,
        step_name: str,
        lessons_db: LessonsDatabase,
        agent_executor: Optional[AgentExecutor] = None,
        rules_engine: Optional[RulesEngine] = None
    ):
        self.step_name = step_name
        self.lessons_db = lessons_db
        self.rules_engine = rules_engine or RulesEngine(lessons_db)
        self.executor = agent_executor

        # Get step metadata for prompt building
        self.definition = self.STEP_METADATA.get(step_name, {
            "role": f"{step_name.title()} Assessor",
            "focus": step_name
        })

        # Get mapped agent ID for this step
        self.agent_id = self.STEP_TO_AGENT.get(step_name)

    async def assess(self, context: AssessmentContext, use_ai: bool = True) -> StepResult:
        """
        Run assessment using rules + AI.

        Args:
            context: Assessment context with project info
            use_ai: Whether to use AI agent (False = rules only mode)
        """
        # 1. Run deterministic rules first
        rule_findings = self.rules_engine.run_rules(self.step_name, context)

        if not use_ai:
            # Rules-only mode
            return self._create_result_from_rules(rule_findings)

        # 2. Build AI prompt with lessons learned
        prompt = self._build_prompt(context, rule_findings)

        # 3. Call AI agent
        ai_response = ""
        ai_findings = []

        if self.executor:
            try:
                # Use the mapped agent for this assessment step
                agent_id = self.agent_id
                if not agent_id or not self.executor.factory.get_agent(agent_id):
                    # Fallback to developer if mapped agent not found
                    agent_id = "developer"
                    print(f"  ⚠️ {self.step_name}: Using fallback agent '{agent_id}' (mapped agent not found)")

                # Retry loop for inadequate responses
                # Minimum thresholds for an adequate expert assessment
                MIN_RESPONSE_CHARS = 5000  # Expert assessments should be detailed
                MIN_FINDINGS = 3  # Should find at least a few issues or improvements

                max_attempts = 2
                for attempt in range(max_attempts):
                    response = await self.executor.execute(agent_id, prompt, "")

                    if response.success:
                        ai_response = response.content
                        ai_findings = self._parse_ai_response(ai_response)

                        # Check if response meets minimum expert standards
                        has_min_length = len(ai_response) >= MIN_RESPONSE_CHARS
                        has_min_findings = len(ai_findings) >= MIN_FINDINGS
                        is_adequate = has_min_length and has_min_findings

                        if is_adequate or attempt == max_attempts - 1:
                            # Debug: Log AI response quality
                            status = "✓" if is_adequate else "⚠️ BELOW STANDARDS"
                            print(f"  📊 {self.step_name}: {status} response={len(ai_response)} chars, parsed={len(ai_findings)} findings")
                            break
                        else:
                            # Response was inadequate, retry with explicit instruction
                            issues = []
                            if not has_min_length:
                                issues.append(f"only {len(ai_response)} chars (need {MIN_RESPONSE_CHARS}+)")
                            if not has_min_findings:
                                issues.append(f"only {len(ai_findings)} findings (need {MIN_FINDINGS}+)")
                            print(f"  🔄 {self.step_name}: Inadequate response ({', '.join(issues)}), retrying...")
                            prompt = f"""CRITICAL: Your previous response was INADEQUATE for an expert assessment.

Issues with your previous response:
- {chr(10).join('- ' + i for i in issues)}

As an EXPERT {self.definition['role']}, you MUST:
1. Provide a COMPREHENSIVE assessment of at least 10,000 characters
2. Include at least 5 specific findings with file locations and evidence
3. Analyze the actual code provided - not generic observations
4. Be thorough and reproducible - another expert should reach similar conclusions

{prompt}"""
                    else:
                        ai_response = f"Agent error: {response.error}"
                        print(f"  ⚠️ {self.step_name}: Agent failed - {response.error}")
                        break
            except Exception as e:
                ai_response = f"AI assessment failed: {e}"
                print(f"  ❌ {self.step_name}: Exception - {e}")

        # 4. Merge rule findings with AI findings
        result = self._merge_results(rule_findings, ai_findings, ai_response)
        # Debug: Log final result quality
        print(f"  📋 {self.step_name}: Final result - score={result.score}, findings={len(result.findings)}, summary={len(result.summary)} chars")
        return result

    async def assess_with_feedback(
        self,
        context: AssessmentContext,
        previous_result: "StepResult",
        voter_feedback: str
    ) -> "StepResult":
        """
        Re-run assessment incorporating voter feedback.
        Called on retry attempts 2 and 3.

        Args:
            context: Assessment context with project info
            previous_result: The result that was rejected by voters
            voter_feedback: Aggregated feedback from voters explaining rejection
        """
        # 1. Run deterministic rules first (same as original)
        rule_findings = self.rules_engine.run_rules(self.step_name, context)

        # 2. Build revision prompt that includes the feedback
        prompt = self._build_revision_prompt(context, previous_result, voter_feedback)

        # 3. Call AI agent with revision prompt
        ai_response = ""
        ai_findings = []

        print(f"  🔄 {self.step_name}: REVISION - previous had {len(previous_result.findings)} findings")

        if self.executor:
            try:
                # Use the mapped agent for this assessment step
                agent_id = self.agent_id
                if not agent_id or not self.executor.factory.get_agent(agent_id):
                    # Fallback to developer if mapped agent not found
                    agent_id = "developer"

                response = await self.executor.execute(agent_id, prompt, "")

                if response.success:
                    ai_response = response.content
                    ai_findings = self._parse_ai_response(ai_response)
                    print(f"  📊 {self.step_name}: REVISION response={len(ai_response)} chars, parsed={len(ai_findings)} findings")
                else:
                    ai_response = f"Revision agent error: {response.error}"
                    print(f"  ⚠️ {self.step_name}: REVISION failed - {response.error}")
            except Exception as e:
                ai_response = f"Revision assessment failed: {e}"
                print(f"  ❌ {self.step_name}: REVISION exception - {e}")

        # 4. Merge rule findings with AI findings
        result = self._merge_results(rule_findings, ai_findings, ai_response)
        print(f"  📋 {self.step_name}: REVISION result - score={result.score}, findings={len(result.findings)}")
        return result

    def _build_revision_prompt(
        self,
        context: AssessmentContext,
        previous_result: "StepResult",
        voter_feedback: str
    ) -> str:
        """Build prompt for revision attempt that incorporates voter feedback."""
        # Get the base prompt (same structure as original)
        base_prompt = self._build_prompt(context, [])

        # Format previous findings for context
        prev_findings_summary = ""
        if previous_result.findings:
            prev_findings_summary = "\n".join([
                f"- [{f.severity.upper()}] {f.rule_name}: {f.description[:100]}"
                for f in previous_result.findings[:5]
            ])
            if len(previous_result.findings) > 5:
                prev_findings_summary += f"\n- ... and {len(previous_result.findings) - 5} more findings"

        return f"""{base_prompt}

## REVISION REQUIRED - Previous Assessment Was Rejected

Your previous assessment was rejected by voters. Here is their feedback:

{voter_feedback}

### Previous Assessment Summary:
- Score: {previous_result.score}/100 ({previous_result.status})
- Findings count: {len(previous_result.findings)}
- Top findings:
{prev_findings_summary}

### What You Must Fix:
1. Address ALL format issues mentioned in the feedback (empty fields, vague values, etc.)
2. Provide SPECIFIC evidence and locations - no "implied" or "estimated" values
3. Vary effort_hours based on ACTUAL complexity (not uniform 1.0 for all)
4. Fill ALL required fields with meaningful, specific values
5. Include concrete code snippets or file:line references as evidence

### Remember:
- Voters rejected this because the output was not specific enough
- Generic or templated responses will be rejected again
- Each finding must have real evidence from the actual codebase
"""

    def _build_prompt(self, context: AssessmentContext, rule_findings: list[Finding]) -> str:
        """Build prompt incorporating lessons learned."""
        lessons = self.lessons_db.get_lessons(self.step_name)
        examples = self.lessons_db.get_examples(self.step_name)
        rule_guidance = self.rules_engine.get_rule_guidance(self.step_name, context)

        # Get learned format rules from database
        learned_format_rules = self.lessons_db.get_format_rules()

        lessons_text = self._format_lessons(lessons) if lessons else "No previous lessons."
        examples_text = self._format_examples(examples) if examples else ""
        rule_findings_text = self._format_rule_findings(rule_findings) if rule_findings else "No rule-based findings."

        # Build format instructions (hardcoded + learned)
        format_instructions = self._build_format_instructions(learned_format_rules)

        # Create file summary for prompt (limit size)
        files_summary = "\n".join(context.file_list[:50])
        if len(context.file_list) > 50:
            files_summary += f"\n... and {len(context.file_list) - 50} more files"

        # Include actual file contents for assessment (key files based on step)
        code_samples = self._get_relevant_code_samples(context)

        return f"""You are a {self.definition['role']} specializing in {self.definition['focus']}.

## Your Task
Analyze this codebase and provide a comprehensive assessment of {self.step_name.replace('_', ' ')}.

## Project Context
- Project Type: {context.project_type}
- Languages: {', '.join(context.languages)}
- Frameworks: {', '.join(context.frameworks) if context.frameworks else 'None detected'}
- Has Tests: {context.has_tests}
- Has Database: {context.has_database}
- Has Frontend: {context.has_frontend}

## Files in Project
{files_summary}

## Code Samples (analyze these for your assessment)
{code_samples}

## Rules Already Applied (don't duplicate these findings)
{rule_findings_text}

{rule_guidance}

{examples_text}

## CRITICAL: Output Format Requirements
{format_instructions}

## Response Format
Respond with a JSON object:
```json
{{
    "score": <0-100>,
    "score_explanation": "Brief explanation of how score was calculated",
    "summary": "Brief summary of assessment",
    "strengths": ["list", "of", "strengths"],
    "weaknesses": ["list", "of", "weaknesses"],
    "findings": [
        {{
            "severity": "critical|high|medium|low|info",
            "title": "Finding title",
            "description": "What was found",
            "impact": "Specific user/business consequence",
            "effort_hours": <realistic estimate based on severity>,
            "location": "specific/file/path.ts:line",
            "evidence": "Code snippet or specific observation",
            "recommendation": "How to fix"
        }}
    ]
}}
```

IMPORTANT - MINIMUM OUTPUT REQUIREMENTS:
- You MUST provide at least 5 findings (more if issues exist)
- Your response MUST be at least 10,000 characters - brief responses are unacceptable
- Score should reflect actual code quality, not just presence of issues
- Only report findings NOT already covered by the rules
- Be specific with locations and evidence - no "implied" or "estimated" values
- Vary effort_hours based on actual complexity (NOT uniform 1.0 for all)
- Always fill impact field with specific consequences (never empty)
- Provide actionable recommendations
- Include both problems found AND opportunities for improvement

CONSISTENCY REQUIREMENTS:
- As an expert assessor, your analysis should be thorough and reproducible
- Given the same codebase, your findings should be consistent across runs
- Focus on objective, measurable issues rather than subjective opinions
- Prioritize findings by actual impact, not by order discovered

{self._format_critical_checklist(lessons_text)}
"""

    def _build_format_instructions(self, learned_rules: list[dict]) -> str:
        """Combine hardcoded rules with learned format rules."""
        # Start with hardcoded rules
        instructions = [
            "Your assessment MUST follow these formatting rules:",
            "",
            "1. **effort_hours**: Estimate realistically based on complexity:",
            "   - Low (info/low severity): 1-2 hours",
            "   - Medium: 4-8 hours",
            "   - High: 16-40 hours",
            "   - Critical: 40+ hours",
            "",
            "2. **impact**: Always describe specific consequences:",
            "   - BAD: \"\" (empty)",
            "   - GOOD: \"Users cannot complete checkout, causing revenue loss\"",
            "",
            "3. **score**: Explain your methodology:",
            "   - BAD: \"score\": 45",
            "   - GOOD: \"score\": 45, \"score_explanation\": \"2 critical + 5 high findings\"",
            "",
            "4. **severity**: Use consistent definitions:",
            "   - critical: Security vulnerabilities, data loss risk",
            "   - high: Broken functionality, major UX issues",
            "   - medium: Performance issues, code quality",
            "   - low: Minor improvements, style issues",
            "   - info: Observations, suggestions",
            "",
            "5. **location**: Be specific with file paths and line numbers:",
            "   - BAD: \"location\": \"components (implied)\"",
            "   - GOOD: \"location\": \"src/components/Form.tsx:142-156\"",
            "",
            "6. **evidence**: Include specific code snippets or observations:",
            "   - BAD: \"evidence\": \"estimated from patterns\"",
            "   - GOOD: \"evidence\": \"Line 45: `eval(user_input)` - unsafe eval\"",
        ]

        # Add learned rules (high confidence only)
        high_confidence = [r for r in learned_rules if r.get("confidence", 0) >= 70]
        if high_confidence:
            instructions.append("")
            instructions.append("**Additional rules (learned from voter feedback):**")
            for rule in high_confidence[:5]:  # Limit to top 5
                correction = rule.get("correction", rule.get("pattern", ""))
                instructions.append(f"- {correction}")

        return "\n".join(instructions)

    def _format_lessons(self, lessons: list[Lesson]) -> str:
        """Format lessons as MANDATORY requirements."""
        if not lessons:
            return ""

        # Sort by confidence and occurrences to prioritize most important
        sorted_lessons = sorted(lessons, key=lambda l: (l.confidence, l.occurrences), reverse=True)

        lines = []
        for i, lesson in enumerate(sorted_lessons[:10], 1):  # Limit to top 10
            confidence_marker = "🔴" if lesson.confidence >= 80 else "🟡" if lesson.confidence >= 60 else "⚪"
            lines.append(f"{i}. {confidence_marker} {lesson.pattern}")
            if lesson.correction:
                lines.append(f"   → REQUIRED ACTION: {lesson.correction}")
            lines.append(f"   (Failed {lesson.occurrences}x in past assessments - confidence: {lesson.confidence}%)")
            lines.append("")

        return "\n".join(lines)

    def _format_critical_checklist(self, lessons_text: str) -> str:
        """Format lessons as a CRITICAL CHECKLIST at the end of the prompt."""
        if not lessons_text or lessons_text == "No previous lessons.":
            return ""

        return f"""
## ⛔ CRITICAL CHECKLIST - YOU MUST ADDRESS THESE ⛔

The following issues have caused assessment FAILURES in the past. Your assessment
WILL BE REJECTED if you do not explicitly address each item below.

For EACH item in this checklist, your response MUST include:
1. A specific finding OR explicit statement that you checked and it's not applicable
2. Evidence from the actual code (file paths, line numbers, code snippets)
3. If the issue exists: a finding with severity, impact, and recommendation
4. If the issue does NOT exist: mention it in strengths with evidence why

FAILURE TO ADDRESS THESE ITEMS = AUTOMATIC REJECTION BY VOTERS

{lessons_text}

⚠️ REMINDER: Voters will specifically check that EACH item above is addressed.
Assessments that ignore this checklist have been rejected {self._get_rejection_count()} times.
"""

    def _get_rejection_count(self) -> int:
        """Get total rejection count from lessons."""
        lessons = self.lessons_db.get_lessons(self.step_name)
        return sum(l.occurrences for l in lessons) if lessons else 0

    def _format_examples(self, examples: list[Example]) -> str:
        """Format examples for prompt inclusion."""
        if not examples:
            return ""

        lines = ["\n## Assessment Examples"]

        good_examples = [e for e in examples if e.is_good][:2]
        bad_examples = [e for e in examples if not e.is_good][:2]

        if good_examples:
            lines.append("\n### Good Assessment Examples:")
            for ex in good_examples:
                lines.append(f"Input: {ex.input_summary[:200]}...")
                lines.append(f"Output: {ex.output[:300]}...")

        if bad_examples:
            lines.append("\n### What to Avoid:")
            for ex in bad_examples:
                lines.append(f"Don't: {ex.output[:200]}...")

        return "\n".join(lines)

    def _format_rule_findings(self, findings: list[Finding]) -> str:
        """Format rule findings for prompt."""
        if not findings:
            return "No automated findings."

        lines = ["The following issues were already detected by automated rules:"]
        for f in findings:
            lines.append(f"- [{f.severity.upper()}] {f.rule_name}: {f.description}")

        return "\n".join(lines)

    def _get_relevant_code_samples(self, context: AssessmentContext) -> str:
        """Get relevant code samples based on step type."""
        # Define which file patterns are relevant for each step
        step_patterns = {
            "architecture": [".py", ".ts", ".js", "package.json", "pyproject.toml", "requirements.txt"],
            "code_quality": [".py", ".ts", ".tsx", ".js", ".jsx"],
            "tech_debt": [".py", ".ts", ".js", "package.json", "requirements.txt"],
            "security": [".py", ".ts", ".js", ".env", "config"],
            "ux_navigation": [".tsx", ".jsx", "router", "navigation", "page"],
            "ux_styling": [".css", ".scss", ".tsx", ".jsx", "style", "theme"],
            "ux_accessibility": [".tsx", ".jsx", ".html"],
            "performance": [".py", ".ts", ".js", "webpack", "vite", "next.config"],
            "testing": ["test", "spec", ".test.", ".spec.", "pytest", "jest"],
            "documentation": [".md", "README", "docs", ".rst"]
        }

        patterns = step_patterns.get(self.step_name, [".py", ".ts", ".js"])

        # Select relevant files
        selected_files = []
        total_chars = 0
        max_chars = 30000  # Limit total code size

        for file_path, content in context.file_contents.items():
            # Check if file matches any pattern
            if any(p.lower() in file_path.lower() for p in patterns):
                if total_chars + len(content) < max_chars:
                    selected_files.append((file_path, content))
                    total_chars += len(content)

        if not selected_files:
            # Fallback: take representative files from the codebase
            # Prioritize main entry points and config files
            priority_patterns = ["index", "app", "main", "config", "package.json", "tsconfig"]
            fallback_files = []

            for file_path, content in context.file_contents.items():
                if any(p.lower() in file_path.lower() for p in priority_patterns):
                    fallback_files.append((file_path, content))

            # If still nothing, just take first few files
            if not fallback_files:
                fallback_files = list(context.file_contents.items())[:5]

            for file_path, content in fallback_files:
                if total_chars + len(content) < max_chars:
                    selected_files.append((file_path, content))
                    total_chars += len(content)

        no_specific_files = len(selected_files) == 0 or all(
            not any(p.lower() in f[0].lower() for p in patterns) for f in selected_files
        )

        if not selected_files:
            return f"No code samples available. NOTE: This project has no files matching {self.step_name} patterns ({patterns}). Assess based on the project structure and general best practices."

        # Format code samples
        lines = []

        if no_specific_files:
            lines.append(f"**NOTE: No files matching {self.step_name} patterns found. Using general project files for assessment.**\n")
            lines.append(f"**For {self.step_name}, evaluate what's MISSING and recommend what SHOULD be added.**\n")

        for file_path, content in selected_files:
            # Truncate very long files
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            lines.append(f"### {file_path}\n```\n{content}\n```\n")

        return "\n".join(lines)

    def _repair_truncated_json(self, content: str) -> str:
        """Attempt to repair truncated JSON by closing unclosed structures."""
        import re

        # Count open/close brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')

        # Check for unterminated string (odd number of unescaped quotes)
        # Simple heuristic: if we have an odd pattern, try to close it
        in_string = False
        last_char = ''
        for char in content:
            if char == '"' and last_char != '\\':
                in_string = not in_string
            last_char = char

        repaired = content

        # If we're in a string, close it
        if in_string:
            # Find the last complete property and truncate there
            # Look for the last complete "key": "value" or "key": number pattern
            last_complete = max(
                content.rfind('",'),
                content.rfind('"],'),
                content.rfind('},'),
                content.rfind('"}'),
                content.rfind('"]'),
                content.rfind(': '),
            )
            if last_complete > len(content) // 2:  # Only truncate if we have substantial content
                repaired = content[:last_complete + 1]
                # Recount after truncation
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')

        # Close any unclosed brackets/braces
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)

        return repaired

    def _extract_findings_regex(self, response: str) -> list[Finding]:
        """Extract findings using regex when JSON parsing fails."""
        import re
        findings = []

        # Pattern to match finding objects (even partial ones)
        # Look for severity and title at minimum
        finding_pattern = r'"severity"\s*:\s*"(critical|high|medium|low|info)"[^}]*"title"\s*:\s*"([^"]+)"'

        for match in re.finditer(finding_pattern, response, re.IGNORECASE | re.DOTALL):
            severity = match.group(1).lower()
            title = match.group(2)

            # Try to extract more fields from the surrounding context
            context_start = max(0, match.start() - 50)
            context_end = min(len(response), match.end() + 500)
            context = response[context_start:context_end]

            # Extract description if present
            desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', context)
            description = desc_match.group(1) if desc_match else title

            # Extract location if present
            loc_match = re.search(r'"location"\s*:\s*"([^"]+)"', context)
            location = loc_match.group(1) if loc_match else ""

            # Extract recommendation if present
            rec_match = re.search(r'"recommendation"\s*:\s*"([^"]+)"', context)
            recommendation = rec_match.group(1) if rec_match else ""

            findings.append(Finding(
                rule_id=f"ai_{self.step_name}",
                rule_name=title,
                severity=severity,
                description=description,
                evidence=[location] if location else [],
                recommendation=recommendation
            ))

        return findings

    def _parse_ai_response(self, response: str) -> list[Finding]:
        """Parse AI response into findings with robust error handling."""
        findings = []

        try:
            # Extract JSON from response
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # First try direct parsing
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try repairing truncated JSON
                repaired = self._repair_truncated_json(content)
                try:
                    data = json.loads(repaired)
                    print(f"  🔧 {self.step_name}: Repaired truncated JSON successfully")
                except json.JSONDecodeError:
                    # Fall back to regex extraction
                    data = None

            if data:
                for finding_data in data.get("findings", []):
                    findings.append(Finding(
                        rule_id=f"ai_{self.step_name}",
                        rule_name=finding_data.get("title", "AI Finding"),
                        severity=finding_data.get("severity", "medium"),
                        description=finding_data.get("description", ""),
                        evidence=[finding_data.get("location", "")],
                        recommendation=finding_data.get("recommendation", "")
                    ))
            else:
                # JSON parsing failed completely, use regex fallback
                findings = self._extract_findings_regex(response)
                if findings:
                    print(f"  🔧 {self.step_name}: Extracted {len(findings)} findings via regex fallback")

        except (json.JSONDecodeError, KeyError) as e:
            # Log parsing failure and try regex fallback
            preview = response[:200] if len(response) > 200 else response
            print(f"  ⚠️ {self.step_name}: JSON parse failed - {e}")
            print(f"     Response preview: {preview}...")

            # Try regex extraction as last resort
            findings = self._extract_findings_regex(response)
            if findings:
                print(f"  🔧 {self.step_name}: Recovered {len(findings)} findings via regex")

        return findings

    def _extract_metadata_regex(self, response: str) -> dict:
        """Extract score, summary, strengths, weaknesses via regex when JSON fails."""
        import re
        result = {}

        # Extract score
        score_match = re.search(r'"score"\s*:\s*(\d+)', response)
        if score_match:
            result['score'] = int(score_match.group(1))

        # Extract summary
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
        if summary_match:
            result['summary'] = summary_match.group(1)

        # Extract strengths (simple list extraction)
        strengths_match = re.search(r'"strengths"\s*:\s*\[(.*?)\]', response, re.DOTALL)
        if strengths_match:
            strengths_content = strengths_match.group(1)
            strengths = re.findall(r'"([^"]+)"', strengths_content)
            result['strengths'] = strengths[:10]  # Limit to 10

        # Extract weaknesses
        weaknesses_match = re.search(r'"weaknesses"\s*:\s*\[(.*?)\]', response, re.DOTALL)
        if weaknesses_match:
            weaknesses_content = weaknesses_match.group(1)
            weaknesses = re.findall(r'"([^"]+)"', weaknesses_content)
            result['weaknesses'] = weaknesses[:10]  # Limit to 10

        return result

    def _merge_results(
        self,
        rule_findings: list[Finding],
        ai_findings: list[Finding],
        ai_response: str
    ) -> StepResult:
        """Merge rule findings with AI findings."""
        all_findings = rule_findings + ai_findings

        # Try to parse score and other info from AI response
        score = 70  # Default
        summary = f"Assessment of {self.step_name}"
        strengths = []
        weaknesses = []
        data = None

        try:
            content = ai_response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Try direct parsing first
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try repairing truncated JSON
                repaired = self._repair_truncated_json(content)
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError:
                    data = None

            if data:
                score = data.get("score", 70)
                summary = data.get("summary", summary)
                strengths = data.get("strengths", [])
                weaknesses = data.get("weaknesses", [])
            else:
                # Fall back to regex extraction for metadata
                metadata = self._extract_metadata_regex(ai_response)
                score = metadata.get('score', 70)
                summary = metadata.get('summary', summary)
                strengths = metadata.get('strengths', [])
                weaknesses = metadata.get('weaknesses', [])
        except:
            # Last resort: try regex extraction
            metadata = self._extract_metadata_regex(ai_response)
            score = metadata.get('score', 70)
            summary = metadata.get('summary', summary)
            strengths = metadata.get('strengths', [])
            weaknesses = metadata.get('weaknesses', [])

        # Adjust score based on findings severity
        for f in all_findings:
            if f.severity == "critical":
                score = min(score, 30)
            elif f.severity == "high":
                score = min(score, 50)

        status = self._get_status(score)

        return StepResult(
            step_name=self.step_name,
            score=score,
            status=status,
            summary=summary,
            findings=all_findings,
            strengths=strengths,
            weaknesses=weaknesses,
            rule_findings=rule_findings,
            ai_findings=ai_findings,
            raw_ai_response=ai_response
        )

    def _create_result_from_rules(self, rule_findings: list[Finding]) -> StepResult:
        """Create result from rules only (no AI)."""
        # Calculate score based on findings
        score = 80
        for f in rule_findings:
            if f.severity == "critical":
                score -= 30
            elif f.severity == "high":
                score -= 20
            elif f.severity == "medium":
                score -= 10
            elif f.severity == "low":
                score -= 5

        score = max(0, min(100, score))
        status = self._get_status(score)

        weaknesses = [f.description for f in rule_findings]

        return StepResult(
            step_name=self.step_name,
            score=score,
            status=status,
            summary=f"Rules-only assessment of {self.step_name}",
            findings=rule_findings,
            strengths=[],
            weaknesses=weaknesses,
            rule_findings=rule_findings,
            ai_findings=[]
        )

    def _get_status(self, score: int) -> str:
        """Convert score to status."""
        if score >= 80:
            return "excellent"
        if score >= 60:
            return "good"
        if score >= 40:
            return "warning"
        return "critical"


class AICodebaseAssessor:
    """
    AI-powered codebase assessor that runs all 10 assessment steps.

    Supports three modes:
    - standard: AI assessment with learned knowledge, no per-step voting
    - self_improvement: AI assessment with per-step voting and feedback capture
    - rules_only: Only run deterministic rules, no AI
    """

    STEP_NAMES = [
        "architecture",
        "code_quality",
        "tech_debt",
        "security",
        "ux_navigation",
        "ux_styling",
        "ux_accessibility",
        "performance",
        "testing",
        "documentation"
    ]

    def __init__(
        self,
        lessons_db: Optional[LessonsDatabase] = None,
        agents_config_path: str = "agents/definitions.yaml",
        audit_logger: Optional[Any] = None
    ):
        self.lessons_db = lessons_db or LessonsDatabase()
        self.rules_engine = RulesEngine(self.lessons_db)
        self.audit_logger = audit_logger

        # Initialize agent executor with audit logger for token tracking
        try:
            factory = AgentFactory(agents_config_path)
            self.executor = AgentExecutor(factory, audit_logger=audit_logger)
        except Exception:
            self.executor = None

        # Create assessors for each step
        self.assessors = {
            step: AIAssessmentAgent(step, self.lessons_db, self.executor, self.rules_engine)
            for step in self.STEP_NAMES
        }

    async def assess_step(
        self,
        step_name: str,
        context: AssessmentContext,
        use_ai: bool = True
    ) -> StepResult:
        """Run a single assessment step."""
        assessor = self.assessors.get(step_name)
        if not assessor:
            raise ValueError(f"Unknown step: {step_name}")

        return await assessor.assess(context, use_ai=use_ai)

    async def assess_all(
        self,
        context: AssessmentContext,
        mode: str = "standard",
        on_step_complete: Optional[Callable[[str, StepResult], None]] = None,
        parallel: bool = True,
        steps: Optional[list[str]] = None
    ) -> dict[str, StepResult]:
        """
        Run all assessment steps.

        Args:
            context: Assessment context
            mode: "standard", "self_improvement", or "rules_only"
            on_step_complete: Callback after each step completes
            parallel: Run assessments in parallel for faster completion
            steps: Optional list of specific steps to run (default: all steps)
        """
        use_ai = mode != "rules_only"
        steps_to_run = steps if steps else self.STEP_NAMES

        if parallel:
            return await self.assess_all_parallel(context, use_ai=use_ai, on_step_complete=on_step_complete, steps=steps_to_run)

        # Sequential execution (original behavior)
        results = {}
        for step_name in steps_to_run:
            result = await self.assess_step(step_name, context, use_ai=use_ai)
            results[step_name] = result

            if on_step_complete:
                on_step_complete(step_name, result)

        return results

    async def assess_all_parallel(
        self,
        context: AssessmentContext,
        use_ai: bool = True,
        on_step_complete: Optional[Callable[[str, StepResult], None]] = None,
        steps: Optional[list[str]] = None
    ) -> dict[str, StepResult]:
        """
        Run assessment steps in parallel.

        This dramatically speeds up assessment by running steps concurrently.
        """
        import time
        import sys
        steps_to_run = steps if steps else self.STEP_NAMES
        start_time = time.time()
        print(f"\n🚀 PARALLEL MODE: Launching {len(steps_to_run)} assessments concurrently...", flush=True)
        print(f"   Steps: {', '.join(steps_to_run)}", flush=True)

        async def assess_one(step_name: str) -> tuple[str, StepResult]:
            """Assess a single step and return (name, result) tuple."""
            print(f"   → Starting {step_name}...", flush=True)

            # Log start event to monitor
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id=f"step_{step_name}",
                    model="pending",
                    input_text=f"Starting assessment of {step_name}",
                    output_text="",
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=0,
                    phase="ingest_assessment",
                    success=True
                )

            step_start = time.time()
            result = await self.assess_step(step_name, context, use_ai=use_ai)
            step_duration = time.time() - step_start
            print(f"   ✓ {step_name} completed in {step_duration:.1f}s (score: {result.score})", flush=True)

            # Log completion event to monitor
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id=f"step_{step_name}",
                    model="claude-3-5-sonnet",
                    input_text=f"Assessed {step_name}",
                    output_text=f"Score: {result.score}/100 - {result.summary[:200]}",
                    input_tokens=0,  # Actual tokens logged by executor
                    output_tokens=0,
                    duration_ms=int(step_duration * 1000),
                    phase="ingest_assessment",
                    success=True
                )

            if on_step_complete:
                on_step_complete(step_name, result)
            return step_name, result

        # Run assessments in parallel
        tasks = [assess_one(step_name) for step_name in steps_to_run]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results, handling any failures
        results = {}
        errors = []
        for item in completed:
            if isinstance(item, Exception):
                errors.append(str(item))
                continue
            step_name, result = item
            results[step_name] = result

        total_duration = time.time() - start_time
        print(f"\n⚡ PARALLEL COMPLETE: {len(results)}/{len(steps_to_run)} steps in {total_duration:.1f}s total")
        if errors:
            print(f"   ⚠️ {len(errors)} step(s) had errors")

        return results

    def create_context_from_config(self, source_path: Path, project_config: dict) -> AssessmentContext:
        """Create assessment context from project config."""
        features = project_config.get("features", {})
        tech = project_config.get("tech", {})

        # Collect file list
        file_list = []
        file_contents = {}

        for p in source_path.rglob("*"):
            if p.is_file():
                rel_path = str(p.relative_to(source_path))
                # Skip common non-source directories
                if any(skip in rel_path for skip in ["node_modules", ".git", "__pycache__", ".next", "dist", "build"]):
                    continue
                file_list.append(rel_path)

                # Sample file contents for smaller files
                if p.suffix in [".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml"]:
                    try:
                        content = p.read_text(errors="ignore")
                        if len(content) < 50000:  # Only include files < 50KB
                            file_contents[rel_path] = content
                    except:
                        pass

        return AssessmentContext(
            project_path=source_path,
            file_list=file_list,
            file_contents=file_contents,
            project_type=features.get("project_type", "unknown"),
            languages=tech.get("languages", []),
            frameworks=tech.get("frameworks", []),
            has_tests=features.get("has_tests", False),
            has_database=features.get("has_database", False),
            has_frontend=features.get("has_frontend", False),
            has_api=features.get("has_api", False)
        )


def calculate_overall_score(results: dict[str, StepResult]) -> tuple[int, str]:
    """Calculate weighted overall score from step results."""
    weights = {
        "architecture": 0.12,
        "code_quality": 0.12,
        "tech_debt": 0.10,
        "security": 0.15,
        "ux_navigation": 0.10,
        "ux_styling": 0.08,
        "ux_accessibility": 0.08,
        "performance": 0.10,
        "testing": 0.10,
        "documentation": 0.05
    }

    total = 0
    for step_name, result in results.items():
        weight = weights.get(step_name, 0.1)
        total += result.score * weight

    score = int(total)

    if score >= 80:
        status = "excellent"
    elif score >= 60:
        status = "good"
    elif score >= 40:
        status = "warning"
    else:
        status = "critical"

    return score, status
