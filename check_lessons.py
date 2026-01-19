#!/usr/bin/env python3
"""Diagnostic script to check lessons database state."""

from core.lessons_database import LessonsDatabase

def main():
    db = LessonsDatabase()

    print("=" * 70)
    print("LESSONS DATABASE DIAGNOSTIC")
    print("=" * 70)
    print(f"Database path: {db.path}")
    print(f"Path exists: {db.path.exists()}")
    print()

    # Check metadata
    meta = db.data.get("metadata", {})
    print(f"Total lessons: {meta.get('total_lessons', 0)}")
    print(f"Total rules: {meta.get('total_rules', 0)}")
    print(f"Projects analyzed: {meta.get('projects_analyzed', [])}")
    print()

    # Check lessons by step
    print("=" * 70)
    print("LESSONS BY STEP")
    print("=" * 70)
    for step in db.STEP_NAMES:
        lessons = db.get_lessons(step)
        if lessons:
            print(f"\n{step.upper()} ({len(lessons)} lessons):")
            for i, lesson in enumerate(lessons[:5], 1):
                print(f"  {i}. Pattern: {lesson.pattern[:80]}...")
                print(f"     Correction: {lesson.correction[:60] if lesson.correction else 'None'}...")
                print(f"     Occurrences: {lesson.occurrences}, Confidence: {lesson.confidence}%")
            if len(lessons) > 5:
                print(f"     ... and {len(lessons) - 5} more")
        else:
            print(f"\n{step.upper()}: No lessons")

    # Check format rules
    print()
    print("=" * 70)
    print("FORMAT RULES (cross-step)")
    print("=" * 70)
    format_rules = db.get_format_rules()
    if format_rules:
        for i, rule in enumerate(format_rules[:10], 1):
            print(f"  {i}. {rule.get('pattern', 'Unknown')[:70]}...")
        if len(format_rules) > 10:
            print(f"     ... and {len(format_rules) - 10} more")
    else:
        print("  No format rules stored")

    # Check rules by step
    print()
    print("=" * 70)
    print("EXTRACTED RULES BY STEP")
    print("=" * 70)
    for step in db.STEP_NAMES:
        rules = db.get_rules(step)
        if rules:
            print(f"\n{step.upper()} ({len(rules)} rules):")
            for rule in rules[:3]:
                print(f"  - {rule.name}: {rule.action[:60]}...")

if __name__ == "__main__":
    main()
