#!/usr/bin/env python3
"""
Question cleanup script for AbaQuiz.

Reviews questions with invalid options and lets the user decide to delete each one.

Usage:
    python -m src.scripts.cleanup_questions           # Interactive review
    python -m src.scripts.cleanup_questions --auto    # Delete all invalid without prompts
    python -m src.scripts.cleanup_questions --dry-run # Show invalid questions only
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.repository import get_repository

logger = get_logger(__name__)


def validate_question(question: dict) -> tuple[bool, str]:
    """
    Validate a question has proper options.

    Returns:
        Tuple of (is_valid, reason)
    """
    opts = question.get("options", {})
    qtype = question.get("question_type", "multiple_choice")

    if qtype == "multiple_choice":
        expected = {"A", "B", "C", "D"}
        if not opts:
            return False, "No options present"
        if set(opts.keys()) != expected:
            missing = expected - set(opts.keys())
            extra = set(opts.keys()) - expected
            reason = []
            if missing:
                reason.append(f"missing {missing}")
            if extra:
                reason.append(f"unexpected {extra}")
            return False, ", ".join(reason)
        if any(not v or not v.strip() for v in opts.values()):
            empty_keys = [k for k, v in opts.items() if not v or not v.strip()]
            return False, f"empty values for {empty_keys}"

    elif qtype == "true_false":
        if not opts:
            return False, "No options present"
        if "True" not in opts or "False" not in opts:
            return False, f"missing True/False keys, got {set(opts.keys())}"
        if not opts.get("True") or not opts.get("False"):
            return False, "empty True/False values"

    return True, "valid"


def format_question_detail(q: dict) -> str:
    """Format a question for detailed display."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"ID: {q['id']}  |  Type: {q.get('question_type', 'unknown')}")
    lines.append(f"Content Area: {q.get('content_area', 'unknown')}")
    lines.append(f"Created: {q.get('created_at', 'unknown')}")
    lines.append("-" * 70)
    lines.append("QUESTION:")
    lines.append(q.get("content", "(no content)"))
    lines.append("-" * 70)
    lines.append("OPTIONS:")
    opts = q.get("options", {})
    if opts:
        for key, val in sorted(opts.items()):
            lines.append(f"  {key}: {val}")
    else:
        lines.append("  (none)")
    lines.append("-" * 70)
    lines.append(f"CORRECT ANSWER: {q.get('correct_answer', '(none)')}")
    lines.append("-" * 70)
    lines.append("EXPLANATION:")
    explanation = q.get("explanation", "(no explanation)")
    # Wrap long explanations
    if len(explanation) > 200:
        lines.append(explanation[:200] + "...")
    else:
        lines.append(explanation)
    lines.append("=" * 70)
    return "\n".join(lines)


async def find_invalid_questions(repo) -> list[tuple[dict, str]]:
    """Find all questions with invalid options."""
    result = await repo.browse_questions(page=1, per_page=9999)
    invalid = []

    for q in result["rows"]:
        is_valid, reason = validate_question(q)
        if not is_valid:
            invalid.append((q, reason))

    return invalid


async def delete_question(repo, question_id: int) -> bool:
    """Delete a question by ID."""
    try:
        await repo.db.execute(
            "DELETE FROM questions WHERE id = ?",
            (question_id,),
        )
        await repo.db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete question {question_id}: {e}")
        return False


async def cleanup_questions(
    dry_run: bool = False,
    auto_delete: bool = False,
) -> dict:
    """
    Review and optionally delete invalid questions.

    Args:
        dry_run: If True, only show invalid questions without deleting
        auto_delete: If True, delete all invalid questions without prompts

    Returns:
        Dict with results
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        # Find invalid questions
        print("\nScanning for invalid questions...")
        invalid = await find_invalid_questions(repo)

        if not invalid:
            print("\nNo invalid questions found. All questions have valid options.")
            return {"found": 0, "deleted": 0, "kept": 0, "status": "clean"}

        print(f"\nFound {len(invalid)} invalid question(s).\n")

        if dry_run:
            print("=" * 70)
            print("DRY RUN - Showing invalid questions (no deletions)")
            print("=" * 70)
            for q, reason in invalid:
                print(f"\n[ID {q['id']}] {reason}")
                print(f"  Type: {q.get('question_type')}")
                print(f"  Area: {q.get('content_area')}")
                text = q.get("content", "")[:80]
                print(f"  Text: {text}...")
            print(f"\nTotal: {len(invalid)} invalid questions")
            return {
                "found": len(invalid),
                "deleted": 0,
                "kept": len(invalid),
                "status": "dry_run",
            }

        deleted = 0
        kept = 0
        skipped = 0

        for i, (q, reason) in enumerate(invalid, 1):
            print(f"\n[{i}/{len(invalid)}] Invalid: {reason}\n")
            print(format_question_detail(q))

            if auto_delete:
                confirm = "y"
                print("Auto-delete: y")
            else:
                print("\nDelete this question? [y/n/q] (q=quit): ", end="", flush=True)
                try:
                    confirm = input().strip().lower()
                except EOFError:
                    confirm = "q"

            if confirm == "q":
                skipped = len(invalid) - i
                print(f"\nQuitting. Skipped {skipped} remaining questions.")
                break
            elif confirm == "y":
                if await delete_question(repo, q["id"]):
                    print(f"  Deleted question {q['id']}")
                    deleted += 1
                else:
                    print(f"  Failed to delete question {q['id']}")
                    kept += 1
            else:
                print(f"  Kept question {q['id']}")
                kept += 1

        # Summary
        print("\n" + "=" * 70)
        print("CLEANUP SUMMARY")
        print("=" * 70)
        print(f"  Found:   {len(invalid)}")
        print(f"  Deleted: {deleted}")
        print(f"  Kept:    {kept}")
        if skipped:
            print(f"  Skipped: {skipped}")
        print("=" * 70)

        return {
            "found": len(invalid),
            "deleted": deleted,
            "kept": kept,
            "skipped": skipped,
            "status": "complete",
        }

    finally:
        await repo.close()


def main():
    parser = argparse.ArgumentParser(
        description="Review and delete questions with invalid options.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.scripts.cleanup_questions
      Interactive review - see each invalid question and decide y/n

  python -m src.scripts.cleanup_questions --dry-run
      Show all invalid questions without deleting any

  python -m src.scripts.cleanup_questions --auto
      Delete all invalid questions without prompts
        """,
    )

    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Show invalid questions without deleting",
    )

    parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Delete all invalid questions without prompts",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "WARNING"
    setup_logging(log_level)

    # Run cleanup
    try:
        result = asyncio.run(
            cleanup_questions(
                dry_run=args.dry_run,
                auto_delete=args.auto,
            )
        )

        if result.get("status") in ("complete", "clean", "dry_run"):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
