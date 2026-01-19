"""
Feedback Collector - Processes voter feedback to improve future assessments.

When voters reject an assessment step, this module:
1. Extracts patterns from voter concerns
2. Stores them as lessons learned
3. Checks if patterns should become deterministic rules
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from core.lessons_database import LessonsDatabase, Lesson
from core.voting import Vote, GateResult


@dataclass
class StepFeedback:
    """Complete feedback record for a failed step."""
    step_name: str
    project_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # What was assessed
    assessment_input: str = ""       # Summary of what was analyzed
    assessment_output: str = ""      # What the AI produced

    # Voter decision
    passed: bool = False
    votes: list[Vote] = field(default_factory=list)

    # Extracted insights (populated during processing)
    missing_checks: list[str] = field(default_factory=list)
    incorrect_findings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "project_id": self.project_id,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "vote_count": len(self.votes),
            "missing_checks": self.missing_checks,
            "incorrect_findings": self.incorrect_findings,
            "suggestions": self.suggestions
        }


class FeedbackCollector:
    """Processes voter feedback and updates lessons learned."""

    # Minimum confidence and occurrences to extract as rule
    RULE_EXTRACTION_CONFIDENCE = 80
    RULE_EXTRACTION_OCCURRENCES = 3

    # Keywords that indicate FORMAT issues (not codebase issues)
    FORMAT_KEYWORDS = [
        "effort_hours", "effort estimate", "impact field", "empty field",
        "score lacks", "scoring", "vague", "ambiguous", "placeholder",
        "uniform", "acceptance criteria", "not defined", "unclear scale",
        "missing definition", "truncated", "estimated from", "all findings",
        "output format", "json format", "response format", "score_explanation",
        "missing field", "empty string", "no explanation"
    ]

    def __init__(self, lessons_db: Optional[LessonsDatabase] = None):
        self.lessons_db = lessons_db or LessonsDatabase()

    def process_gate_result(
        self,
        gate_result: GateResult,
        step_name: str,
        project_id: str,
        assessment_output: str = ""
    ) -> StepFeedback:
        """
        Process a gate result and extract feedback.

        Args:
            gate_result: Result from voting gate
            step_name: Assessment step name (e.g., "architecture")
            project_id: Project being assessed
            assessment_output: The assessment output that was voted on

        Returns:
            StepFeedback with extracted insights
        """
        feedback = StepFeedback(
            step_name=step_name,
            project_id=project_id,
            assessment_output=assessment_output,
            passed=gate_result.passed,
            votes=gate_result.votes
        )

        # Extract insights from voter feedback
        self._extract_insights(feedback)

        # If failed, create/update lessons
        if not feedback.passed:
            self._process_failed_feedback(feedback)

        return feedback

    def _extract_insights(self, feedback: StepFeedback) -> None:
        """Extract insights from all votes."""
        for vote in feedback.votes:
            # Collect concerns from all voters (especially failing ones)
            if vote.concerns:
                for concern in vote.concerns:
                    # Categorize concern
                    concern_lower = concern.lower()
                    if any(kw in concern_lower for kw in ["missing", "didn't check", "no analysis", "absent"]):
                        feedback.missing_checks.append(concern)
                    elif any(kw in concern_lower for kw in ["wrong", "incorrect", "inaccurate", "false"]):
                        feedback.incorrect_findings.append(concern)

            # Collect suggestions
            if vote.suggestions:
                feedback.suggestions.extend(vote.suggestions)

    def _process_failed_feedback(self, feedback: StepFeedback) -> None:
        """Process feedback from a failed step and update lessons."""
        # Process concerns as potential lessons
        all_concerns = feedback.missing_checks + feedback.incorrect_findings

        for concern in all_concerns:
            self._process_concern(feedback.step_name, concern, feedback)

        # Check if any lessons should become rules
        self._check_rule_extraction(feedback.step_name)

    def _is_format_concern(self, concern: str) -> bool:
        """Check if concern is about assessment format vs codebase content."""
        concern_lower = concern.lower()
        return any(kw in concern_lower for kw in self.FORMAT_KEYWORDS)

    def _extract_correction(self, concern: str, suggestions: list[str]) -> str:
        """Extract the best correction for a concern from suggestions."""
        if not suggestions:
            return f"Ensure {concern.lower()}"

        # Try to match suggestion to concern
        for suggestion in suggestions:
            if self._suggestions_match_concern(concern, suggestion):
                return suggestion

        return suggestions[0] if suggestions else f"Address: {concern}"

    def _process_concern(
        self,
        step_name: str,
        concern: str,
        feedback: StepFeedback
    ) -> None:
        """Process a single concern - route to format_rules or lessons."""
        # Check if this is a format concern (about output format, not codebase)
        if self._is_format_concern(concern):
            # Format issue → store as format rule (cross-step)
            correction = self._extract_correction(concern, feedback.suggestions)
            self.lessons_db.add_format_rule(concern, correction, feedback.project_id)
            return

        # Codebase issue → existing behavior (step-specific lesson)
        # Check if this matches an existing lesson
        existing = self.lessons_db.find_similar_lesson(step_name, concern)

        if existing:
            # Increment existing lesson
            self.lessons_db.increment_lesson(step_name, existing, feedback.project_id)
        else:
            # Create new lesson
            # Find the best suggestion for this concern
            correction = ""
            if feedback.suggestions:
                # Try to match suggestion to concern
                for suggestion in feedback.suggestions:
                    if self._suggestions_match_concern(concern, suggestion):
                        correction = suggestion
                        break
                if not correction:
                    correction = feedback.suggestions[0]

            # Get voter reasoning for context
            voter_feedback = ""
            for vote in feedback.votes:
                if vote.vote == "fail" and concern in vote.concerns:
                    voter_feedback = vote.reasoning
                    break

            self.lessons_db.create_lesson(
                step_name=step_name,
                pattern=concern,
                voter_feedback=voter_feedback,
                correction=correction,
                project_id=feedback.project_id
            )

    def _suggestions_match_concern(self, concern: str, suggestion: str) -> bool:
        """Check if a suggestion relates to a concern."""
        concern_words = set(concern.lower().split())
        suggestion_words = set(suggestion.lower().split())

        # Simple word overlap check
        overlap = len(concern_words & suggestion_words)
        return overlap >= 2

    def _check_rule_extraction(self, step_name: str) -> None:
        """Check if any lessons should be extracted as rules."""
        lessons = self.lessons_db.get_lessons(step_name)

        for lesson in lessons:
            # Extract as rule if: high confidence AND multiple occurrences AND not already extracted
            if (lesson.confidence >= self.RULE_EXTRACTION_CONFIDENCE and
                lesson.occurrences >= self.RULE_EXTRACTION_OCCURRENCES and
                not lesson.extracted_as_rule):

                self.lessons_db.create_rule_from_lesson(step_name, lesson)

    def process_failed_vote(self, feedback: StepFeedback) -> None:
        """
        Legacy method - process a pre-created StepFeedback.
        Extracts lessons from feedback and updates database.
        """
        self._extract_insights(feedback)
        self._process_failed_feedback(feedback)

    def get_step_summary(self, step_name: str) -> dict:
        """Get summary of lessons and rules for a step."""
        lessons = self.lessons_db.get_lessons(step_name)
        rules = self.lessons_db.get_rules(step_name)

        return {
            "step_name": step_name,
            "lesson_count": len(lessons),
            "rule_count": len(rules),
            "top_patterns": [l.pattern for l in lessons[:5]],
            "total_occurrences": sum(l.occurrences for l in lessons),
            "avg_confidence": sum(l.confidence for l in lessons) / len(lessons) if lessons else 0
        }


class FeedbackAggregator:
    """Aggregates feedback across multiple steps and projects."""

    def __init__(self, lessons_db: Optional[LessonsDatabase] = None):
        self.lessons_db = lessons_db or LessonsDatabase()
        self.collector = FeedbackCollector(self.lessons_db)

    def aggregate_session_feedback(
        self,
        step_feedbacks: list[StepFeedback]
    ) -> dict:
        """Aggregate feedback from an entire assessment session."""
        summary = {
            "total_steps": len(step_feedbacks),
            "passed_steps": sum(1 for f in step_feedbacks if f.passed),
            "failed_steps": sum(1 for f in step_feedbacks if not f.passed),
            "total_concerns": 0,
            "total_suggestions": 0,
            "lessons_created": 0,
            "rules_extracted": 0,
            "by_step": {}
        }

        for feedback in step_feedbacks:
            step_summary = {
                "passed": feedback.passed,
                "concerns": len(feedback.missing_checks) + len(feedback.incorrect_findings),
                "suggestions": len(feedback.suggestions)
            }
            summary["by_step"][feedback.step_name] = step_summary
            summary["total_concerns"] += step_summary["concerns"]
            summary["total_suggestions"] += step_summary["suggestions"]

        return summary

    def get_global_insights(self) -> dict:
        """Get insights across all steps."""
        stats = self.lessons_db.get_stats()

        # Find most common patterns
        all_lessons = []
        for step_name in self.lessons_db.STEP_NAMES:
            lessons = self.lessons_db.get_lessons(step_name)
            for lesson in lessons:
                all_lessons.append((step_name, lesson))

        # Sort by occurrences
        all_lessons.sort(key=lambda x: x[1].occurrences, reverse=True)

        top_patterns = []
        for step_name, lesson in all_lessons[:10]:
            top_patterns.append({
                "step": step_name,
                "pattern": lesson.pattern,
                "occurrences": lesson.occurrences,
                "confidence": lesson.confidence,
                "is_rule": lesson.extracted_as_rule
            })

        return {
            "stats": stats,
            "top_patterns": top_patterns
        }


def create_feedback_from_gate(
    gate_result: GateResult,
    step_name: str,
    project_id: str,
    assessment_output: str = ""
) -> StepFeedback:
    """Convenience function to create feedback from a gate result."""
    collector = FeedbackCollector()
    return collector.process_gate_result(
        gate_result=gate_result,
        step_name=step_name,
        project_id=project_id,
        assessment_output=assessment_output
    )
