"""
Lessons Database - Persistent storage for lessons learned across all projects.

Stores:
- Lessons: Patterns learned from voter feedback
- Rules: Deterministic checks extracted from high-confidence lessons
- Examples: Good/bad assessment examples for training
"""

import yaml
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Lesson:
    """A lesson learned from voter feedback."""
    id: str
    pattern: str                    # What was missing or wrong
    learned_from: list[str]         # Project IDs where this was learned
    voter_feedback: str             # Original voter reasoning
    correction: str                 # How to fix/improve
    confidence: int                 # 1-100, increases with occurrences
    occurrences: int                # How many times this pattern was seen
    extracted_as_rule: bool = False # Whether this became a rule
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(**data)


@dataclass
class Rule:
    """A deterministic rule extracted from lessons or built-in."""
    id: str
    name: str
    condition: str                  # When to apply: "always", "has_database", etc.
    action: str                     # What to check for
    source_lesson: Optional[str]    # Lesson ID this was extracted from, or None for built-in
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        return cls(**data)


@dataclass
class Example:
    """An example of good or bad assessment output."""
    input_summary: str              # What was analyzed
    output: str                     # The assessment output
    is_good: bool                   # True for good example, False for bad

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Example":
        return cls(**data)


class LessonsDatabase:
    """Manages the lessons learned YAML database."""

    DEFAULT_PATH = Path.home() / ".ai-dev-workflow" / "lessons_learned.yaml"

    # Assessment step names (must match orchestrator steps)
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

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self.data = self._load()

    def _load(self) -> dict:
        """Load lessons from YAML file."""
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        return data
            except (yaml.YAMLError, IOError) as e:
                print(f"Warning: Could not load lessons database: {e}")

        # Return default structure
        return {
            "version": "1.0",
            "lessons": {step: [] for step in self.STEP_NAMES},
            "rules": {step: [] for step in self.STEP_NAMES},
            "examples": {step: {"good": [], "bad": []} for step in self.STEP_NAMES},
            "format_rules": [],  # Format-related lessons (cross-step)
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_lessons": 0,
                "total_rules": 0,
                "projects_analyzed": []
            }
        }

    def save(self) -> None:
        """Save lessons to YAML file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Update metadata
        self.data["metadata"]["total_lessons"] = sum(
            len(self.data["lessons"].get(step, []))
            for step in self.STEP_NAMES
        )
        self.data["metadata"]["total_rules"] = sum(
            len(self.data["rules"].get(step, []))
            for step in self.STEP_NAMES
        )

        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ========== Lessons ==========

    def get_lessons(self, step_name: str) -> list[Lesson]:
        """Get all lessons for a step."""
        lessons_data = self.data["lessons"].get(step_name, [])
        return [Lesson.from_dict(d) for d in lessons_data]

    def add_lesson(self, step_name: str, lesson: Lesson) -> None:
        """Add a new lesson."""
        if step_name not in self.data["lessons"]:
            self.data["lessons"][step_name] = []
        self.data["lessons"][step_name].append(lesson.to_dict())
        self.save()

    def update_lesson(self, step_name: str, lesson: Lesson) -> None:
        """Update an existing lesson."""
        lessons = self.data["lessons"].get(step_name, [])
        for i, l in enumerate(lessons):
            if l["id"] == lesson.id:
                lesson.updated_at = datetime.now().isoformat()
                lessons[i] = lesson.to_dict()
                self.save()
                return
        # If not found, add it
        self.add_lesson(step_name, lesson)

    def find_similar_lesson(self, step_name: str, pattern: str) -> Optional[Lesson]:
        """Find a lesson with a similar pattern (simple substring match)."""
        pattern_lower = pattern.lower()
        for lesson in self.get_lessons(step_name):
            # Simple similarity: check if key words overlap
            lesson_words = set(lesson.pattern.lower().split())
            pattern_words = set(pattern_lower.split())
            overlap = len(lesson_words & pattern_words)
            if overlap >= 2 or pattern_lower in lesson.pattern.lower():
                return lesson
        return None

    def create_lesson(
        self,
        step_name: str,
        pattern: str,
        voter_feedback: str,
        correction: str,
        project_id: str
    ) -> Lesson:
        """Create and add a new lesson."""
        lesson = Lesson(
            id=f"{step_name}_{uuid.uuid4().hex[:8]}",
            pattern=pattern,
            learned_from=[project_id],
            voter_feedback=voter_feedback,
            correction=correction,
            confidence=50,  # Start at 50%
            occurrences=1
        )
        self.add_lesson(step_name, lesson)
        return lesson

    def increment_lesson(self, step_name: str, lesson: Lesson, project_id: str) -> None:
        """Increment occurrence count and confidence for an existing lesson."""
        lesson.occurrences += 1
        lesson.confidence = min(100, lesson.confidence + 5)
        if project_id not in lesson.learned_from:
            lesson.learned_from.append(project_id)
        self.update_lesson(step_name, lesson)

    # ========== Rules ==========

    def get_rules(self, step_name: str) -> list[Rule]:
        """Get all rules for a step."""
        rules_data = self.data["rules"].get(step_name, [])
        return [Rule.from_dict(d) for d in rules_data]

    def add_rule(self, step_name: str, rule: Rule) -> None:
        """Add a new rule."""
        if step_name not in self.data["rules"]:
            self.data["rules"][step_name] = []
        self.data["rules"][step_name].append(rule.to_dict())
        self.save()

    def create_rule_from_lesson(self, step_name: str, lesson: Lesson) -> Rule:
        """Create a rule from a high-confidence lesson."""
        rule = Rule(
            id=f"rule_{step_name}_{uuid.uuid4().hex[:8]}",
            name=f"Check: {lesson.pattern[:50]}",
            condition="always",  # Could be smarter based on pattern analysis
            action=lesson.correction,
            source_lesson=lesson.id
        )
        self.add_rule(step_name, rule)

        # Mark lesson as extracted
        lesson.extracted_as_rule = True
        self.update_lesson(step_name, lesson)

        return rule

    # ========== Examples ==========

    def get_examples(self, step_name: str, good_only: bool = False, bad_only: bool = False) -> list[Example]:
        """Get examples for a step."""
        examples_data = self.data["examples"].get(step_name, {"good": [], "bad": []})
        result = []

        if not bad_only:
            result.extend([Example.from_dict({**d, "is_good": True}) for d in examples_data.get("good", [])])
        if not good_only:
            result.extend([Example.from_dict({**d, "is_good": False}) for d in examples_data.get("bad", [])])

        return result

    def add_example(self, step_name: str, example: Example) -> None:
        """Add a new example."""
        if step_name not in self.data["examples"]:
            self.data["examples"][step_name] = {"good": [], "bad": []}

        category = "good" if example.is_good else "bad"
        example_dict = {"input_summary": example.input_summary, "output": example.output}
        self.data["examples"][step_name][category].append(example_dict)
        self.save()

    # ========== Format Rules ==========

    def get_format_rules(self) -> list[dict]:
        """Get all format rules."""
        # Ensure format_rules exists (for legacy databases)
        if "format_rules" not in self.data:
            self.data["format_rules"] = []
        return self.data.get("format_rules", [])

    def find_similar_format_rule(self, pattern: str) -> Optional[dict]:
        """Find a format rule with a similar pattern."""
        pattern_lower = pattern.lower()
        for rule in self.get_format_rules():
            rule_pattern = rule.get("pattern", "").lower()
            # Simple similarity: check if key words overlap
            rule_words = set(rule_pattern.split())
            pattern_words = set(pattern_lower.split())
            overlap = len(rule_words & pattern_words)
            if overlap >= 2 or pattern_lower in rule_pattern:
                return rule
        return None

    def add_format_rule(self, pattern: str, correction: str, project_id: str) -> None:
        """Add a format-related lesson."""
        # Ensure format_rules exists (for legacy databases)
        if "format_rules" not in self.data:
            self.data["format_rules"] = []

        existing = self.find_similar_format_rule(pattern)
        if existing:
            existing["occurrences"] = existing.get("occurrences", 1) + 1
            existing["confidence"] = min(100, existing.get("confidence", 50) + 5)
            if project_id not in existing.get("learned_from", []):
                existing.setdefault("learned_from", []).append(project_id)
        else:
            self.data["format_rules"].append({
                "id": f"fmt_{uuid.uuid4().hex[:8]}",
                "pattern": pattern,
                "correction": correction,
                "occurrences": 1,
                "confidence": 50,
                "learned_from": [project_id],
                "created_at": datetime.now().isoformat()
            })
        self.save()

    # ========== Metadata & Utilities ==========

    def record_project(self, project_id: str) -> None:
        """Record that a project was analyzed."""
        if project_id not in self.data["metadata"]["projects_analyzed"]:
            self.data["metadata"]["projects_analyzed"].append(project_id)
            self.save()

    def get_stats(self) -> dict:
        """Get statistics about the lessons database."""
        return {
            "total_lessons": self.data["metadata"]["total_lessons"],
            "total_rules": self.data["metadata"]["total_rules"],
            "projects_analyzed": len(self.data["metadata"]["projects_analyzed"]),
            "lessons_by_step": {
                step: len(self.data["lessons"].get(step, []))
                for step in self.STEP_NAMES
            },
            "rules_by_step": {
                step: len(self.data["rules"].get(step, []))
                for step in self.STEP_NAMES
            }
        }

    def clear_lessons(self, keep_rules: bool = True) -> None:
        """Clear all lessons (optionally keep rules)."""
        for step in self.STEP_NAMES:
            self.data["lessons"][step] = []
            if not keep_rules:
                self.data["rules"][step] = []
        self.save()

    def export_to_file(self, path: Path) -> None:
        """Export lessons database to a file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def import_from_file(self, path: Path, merge: bool = True) -> None:
        """Import lessons from a file."""
        with open(path, encoding="utf-8") as f:
            imported = yaml.safe_load(f)

        if merge:
            # Merge lessons
            for step in self.STEP_NAMES:
                existing_ids = {l["id"] for l in self.data["lessons"].get(step, [])}
                for lesson in imported.get("lessons", {}).get(step, []):
                    if lesson["id"] not in existing_ids:
                        self.data["lessons"][step].append(lesson)

            # Merge rules
            for step in self.STEP_NAMES:
                existing_ids = {r["id"] for r in self.data["rules"].get(step, [])}
                for rule in imported.get("rules", {}).get(step, []):
                    if rule["id"] not in existing_ids:
                        self.data["rules"][step].append(rule)
        else:
            # Replace entirely
            self.data = imported

        self.save()


# Built-in rules that ship with the system
BUILT_IN_RULES = {
    "security": [
        Rule(
            id="builtin_sec_001",
            name="Check Hardcoded Secrets",
            condition="always",
            action="Scan for hardcoded API keys, passwords, tokens, and credentials in code",
            source_lesson=None
        ),
        Rule(
            id="builtin_sec_002",
            name="Check SQL Injection",
            condition="has_database",
            action="Check for SQL injection vulnerabilities in database queries",
            source_lesson=None
        ),
        Rule(
            id="builtin_sec_003",
            name="Check XSS Vulnerabilities",
            condition="has_frontend",
            action="Check for cross-site scripting vulnerabilities in user input handling",
            source_lesson=None
        ),
    ],
    "architecture": [
        Rule(
            id="builtin_arch_001",
            name="Check Circular Dependencies",
            condition="always",
            action="Check for circular import/dependency issues between modules",
            source_lesson=None
        ),
        Rule(
            id="builtin_arch_002",
            name="Check Layer Violations",
            condition="has_layers",
            action="Check that dependencies flow in the correct direction between architectural layers",
            source_lesson=None
        ),
    ],
    "code_quality": [
        Rule(
            id="builtin_cq_001",
            name="Check Code Duplication",
            condition="always",
            action="Identify significant code duplication that should be refactored",
            source_lesson=None
        ),
        Rule(
            id="builtin_cq_002",
            name="Check Function Complexity",
            condition="always",
            action="Flag functions with excessive cyclomatic complexity",
            source_lesson=None
        ),
    ],
    "testing": [
        Rule(
            id="builtin_test_001",
            name="Check Test Coverage",
            condition="has_tests",
            action="Verify critical paths have test coverage",
            source_lesson=None
        ),
    ],
}


def initialize_database(path: Optional[Path] = None) -> LessonsDatabase:
    """Initialize a new lessons database with built-in rules."""
    db = LessonsDatabase(path)

    # Add built-in rules if they don't exist
    for step_name, rules in BUILT_IN_RULES.items():
        existing_ids = {r.id for r in db.get_rules(step_name)}
        for rule in rules:
            if rule.id not in existing_ids:
                db.add_rule(step_name, rule)

    return db


if __name__ == "__main__":
    # Quick test
    db = initialize_database()
    print(f"Lessons database at: {db.path}")
    print(f"Stats: {db.get_stats()}")
