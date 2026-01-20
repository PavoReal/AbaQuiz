#!/usr/bin/env python3
"""
Question pool seeding script for AbaQuiz.

Seeds the question pool with initial questions distributed by BCBA exam weights.

Usage:
    python -m src.scripts.seed_questions --count 250
    python -m src.scripts.seed_questions --count 250 --skip-dedup  # For initial empty pool
    python -m src.scripts.seed_questions --area "Ethics" --count 50
    python -m src.scripts.seed_questions --dry-run
    python -m src.scripts.seed_questions --resume
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.constants import ContentArea
from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.pool_manager import BCBA_WEIGHTS, PoolManager

logger = get_logger(__name__)

# State file for resume functionality
STATE_FILE = Path("data/.seed_progress.json")


def calculate_distribution(total_count: int) -> dict[ContentArea, int]:
    """Calculate question distribution based on BCBA exam weights."""
    distribution: dict[ContentArea, int] = {}
    remaining = total_count

    sorted_areas = sorted(BCBA_WEIGHTS.items(), key=lambda x: x[1], reverse=True)

    for i, (area, weight) in enumerate(sorted_areas):
        if i == len(sorted_areas) - 1:
            distribution[area] = remaining
        else:
            count = round(total_count * weight)
            distribution[area] = count
            remaining -= count

    return distribution


# State persistence for resume
def save_progress(state: dict[str, Any]) -> None:
    """Save seeding progress to state file."""
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def load_progress() -> Optional[dict[str, Any]]:
    """Load seeding progress from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return None
    return None


def clear_progress() -> None:
    """Clear the progress state file."""
    STATE_FILE.unlink(missing_ok=True)


def estimate_cost(question_count: int, skip_dedup: bool = False) -> dict[str, float]:
    """
    Estimate API cost for generating questions with batch generation.

    With batch generation (5 questions per call):
    - Sonnet for generation: ~2000 input, ~2000 output per batch (5 questions)
    - Haiku for dedup: ~3 calls per question (with early exit optimization)
    """
    settings = get_settings()

    # Sonnet pricing
    sonnet_pricing = settings.get_model_pricing("claude-sonnet-4-5") or {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    }

    # Haiku pricing
    haiku_pricing = settings.get_model_pricing("claude-haiku-4-5") or {
        "input_per_million": 1.00,
        "output_per_million": 5.00,
    }

    # Generation cost (Sonnet) - batch generation: 5 questions per call
    batch_size = 5
    generation_calls = (question_count + batch_size - 1) // batch_size
    gen_input_tokens = generation_calls * 2000  # ~2000 input per batch
    gen_output_tokens = generation_calls * 2000  # ~2000 output per batch (5 questions)
    gen_cost = (
        gen_input_tokens / 1_000_000 * sonnet_pricing["input_per_million"]
        + gen_output_tokens / 1_000_000 * sonnet_pricing["output_per_million"]
    )

    # Dedup cost (Haiku)
    if skip_dedup:
        dedup_cost = 0.0
        dedup_calls = 0
        dedup_input_tokens = 0
        dedup_output_tokens = 0
    else:
        # ~3 Haiku calls per question (with early exit optimization)
        dedup_calls = question_count * 3
        dedup_input_tokens = dedup_calls * 1000
        dedup_output_tokens = dedup_calls * 100
        dedup_cost = (
            dedup_input_tokens / 1_000_000 * haiku_pricing["input_per_million"]
            + dedup_output_tokens / 1_000_000 * haiku_pricing["output_per_million"]
        )

    return {
        "generation_calls": generation_calls,
        "generation_cost": gen_cost,
        "dedup_calls": dedup_calls,
        "dedup_cost": dedup_cost,
        "total_cost": gen_cost + dedup_cost,
        "gen_input_tokens": gen_input_tokens,
        "gen_output_tokens": gen_output_tokens,
        "dedup_input_tokens": dedup_input_tokens,
        "dedup_output_tokens": dedup_output_tokens,
    }


async def seed_questions(
    total_count: int,
    specific_area: Optional[ContentArea] = None,
    dry_run: bool = False,
    resume: bool = False,
    skip_dedup: bool = False,
) -> dict[str, Any]:
    """
    Seed the question pool with initial questions.

    Args:
        total_count: Total number of questions to generate
        specific_area: If set, only generate for this content area
        dry_run: If True, show plan without generating
        resume: If True, check existing counts and fill gaps
        skip_dedup: If True, skip deduplication (for initial seeding on empty pool)

    Returns:
        Dict with results
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)
    pool_manager = PoolManager()

    try:
        return await _seed_questions_impl(
            repo, pool_manager, total_count, specific_area, dry_run, resume, skip_dedup
        )
    finally:
        await repo.close()


async def _seed_questions_impl(
    repo,
    pool_manager,
    total_count: int,
    specific_area: Optional[ContentArea] = None,
    dry_run: bool = False,
    resume: bool = False,
    skip_dedup: bool = False,
) -> dict[str, Any]:
    """Implementation of seed_questions with repository passed in."""

    # Calculate distribution
    if specific_area:
        distribution = {specific_area: total_count}
    else:
        distribution = calculate_distribution(total_count)

    # If resuming, adjust for existing questions
    if resume:
        existing_counts = await repo.get_question_pool_counts()
        logger.info(f"Existing question counts: {existing_counts}")

        adjusted_distribution: dict[ContentArea, int] = {}
        for area, target_count in distribution.items():
            existing = existing_counts.get(area.value, 0)
            needed = max(0, target_count - existing)
            if needed > 0:
                adjusted_distribution[area] = needed

        distribution = adjusted_distribution

        if not distribution:
            logger.info("Pool already meets target counts. Nothing to generate.")
            return {"generated": 0, "by_area": {}, "status": "already_complete"}

    # Estimate cost
    total_to_generate = sum(distribution.values())
    cost_estimate = estimate_cost(total_to_generate, skip_dedup=skip_dedup)

    # Print plan
    print("\n" + "=" * 60)
    print("QUESTION SEEDING PLAN")
    print("=" * 60)
    print(f"\nTotal questions to generate: {total_to_generate}")
    print("  (Parallel generation: ENABLED - all content areas processed simultaneously)")
    if skip_dedup:
        print("  (Deduplication: SKIPPED)")
    print(f"\nDistribution by content area:")

    for area in ContentArea:
        count = distribution.get(area, 0)
        weight = BCBA_WEIGHTS.get(area, 0)
        if count > 0:
            print(f"  {area.value}: {count} ({weight*100:.0f}% weight)")

    print(f"\nEstimated cost:")
    print(f"  Generation (Sonnet): ${cost_estimate['generation_cost']:.2f}")
    print(f"    ({cost_estimate['generation_calls']} API calls)")
    if skip_dedup:
        print(f"  Deduplication: $0.00 (skipped)")
    else:
        print(f"  Deduplication (Haiku): ${cost_estimate['dedup_cost']:.2f}")
        print(f"    (~{cost_estimate['dedup_calls']} API calls)")
    print(f"  Total: ${cost_estimate['total_cost']:.2f}")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN] No questions generated.")
        return {
            "generated": 0,
            "planned": total_to_generate,
            "by_area": {a.value: c for a, c in distribution.items()},
            "cost_estimate": cost_estimate,
            "status": "dry_run",
        }

    # Confirm before proceeding
    print("\nProceed with generation? [y/N]: ", end="", flush=True)
    try:
        response = input().strip().lower()
    except EOFError:
        response = "y"  # Non-interactive mode

    if response not in ("y", "yes"):
        print("Aborted.")
        return {"generated": 0, "status": "aborted"}

    # Initialize state for persistence
    state = {
        "started_at": datetime.now().isoformat(),
        "target_total": total_to_generate,
        "skip_dedup": skip_dedup,
        "completed_areas": [],
        "in_progress_areas": list(distribution.keys()),
        "stats": {"generated": 0, "rejected": 0},
    }
    save_progress(state)

    # Generate questions with parallel content area processing
    print("\nStarting parallel generation across all content areas...\n")
    start_time = datetime.now()

    # Define async task for each content area
    async def generate_for_area(
        area: ContentArea, count: int
    ) -> tuple[ContentArea, list[dict[str, Any]], Optional[str]]:
        """Generate questions for a single content area."""
        if count <= 0:
            return (area, [], None)

        print(f"[{area.value}] Starting generation of {count} questions...")
        try:
            if skip_dedup:
                questions = await pool_manager.generate_without_dedup(area, count)
            else:
                questions = await pool_manager.generate_with_dedup(area, count)
            print(f"[{area.value}] Generated {len(questions)}/{count} questions")
            return (area, questions, None)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error generating for {area.value}: {e}")
            print(f"[{area.value}] Error: {e}")
            return (area, [], error_msg)

    # Launch all content areas in parallel
    tasks = [generate_for_area(area, count) for area, count in distribution.items()]
    area_results = await asyncio.gather(*tasks)

    # Process results and store questions
    print("\nStoring questions to database...")
    results_by_area: dict[str, int] = {}
    total_generated = 0

    for area, questions, error in area_results:
        if error:
            results_by_area[area.value] = 0
            continue

        # Store questions
        stored_count = 0
        if questions:
            logger.info(
                f"Storing batch for {area.value}: {len(questions)} questions generated"
            )
            for q in questions:
                await repo.create_question(
                    content=q["question"],
                    question_type=q.get("type", "multiple_choice"),
                    options=q["options"],
                    correct_answer=q["correct_answer"],
                    explanation=q["explanation"],
                    content_area=q["content_area"],
                    model=q.get("model"),
                )
                stored_count += 1

            print(f"[{area.value}] Stored {stored_count} questions")
            logger.info(
                f"Batch complete for {area.value}: {stored_count} stored"
            )

        results_by_area[area.value] = len(questions)
        total_generated += len(questions)

        # Update state
        state["completed_areas"].append(area.value)
        state["stats"]["generated"] = total_generated
        save_progress(state)

    # Clear state on completion
    clear_progress()

    # Summary
    elapsed = datetime.now() - start_time
    print("\n" + "=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)
    print(f"\nTotal generated: {total_generated}/{total_to_generate}")
    print(f"Time elapsed: {elapsed}")
    print(f"\nResults by area:")
    for area_name, count in results_by_area.items():
        print(f"  {area_name}: {count}")

    # Verify final pool counts
    final_counts = await repo.get_question_pool_counts()
    final_total = sum(final_counts.values())
    print(f"\nFinal pool size: {final_total} questions")

    return {
        "generated": total_generated,
        "by_area": results_by_area,
        "elapsed_seconds": elapsed.total_seconds(),
        "final_pool_size": final_total,
        "status": "complete",
    }


def parse_content_area(area_str: str) -> Optional[ContentArea]:
    """Parse content area from string input."""
    area_lower = area_str.lower().strip()

    # Try exact match
    for area in ContentArea:
        if area.value.lower() == area_lower:
            return area

    # Try partial match
    for area in ContentArea:
        if area_lower in area.value.lower():
            return area

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Seed the AbaQuiz question pool with initial questions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.scripts.seed_questions --count 250
      Generate 250 questions distributed by BCBA exam weights

  python -m src.scripts.seed_questions --count 250 --skip-dedup
      Initial seeding without deduplication (for empty pool)

  python -m src.scripts.seed_questions --area "Ethics" --count 50
      Generate 50 questions for Ethics only

  python -m src.scripts.seed_questions --dry-run
      Show plan without generating

  python -m src.scripts.seed_questions --resume --count 300
      Fill gaps to reach 300 questions total
        """,
    )

    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=250,
        help="Number of questions to generate (default: 250)",
    )

    parser.add_argument(
        "--area",
        "-a",
        type=str,
        help="Generate for specific content area only (e.g., 'Ethics', 'Measurement')",
    )

    parser.add_argument(
        "--skip-dedup",
        "-s",
        action="store_true",
        help="Skip deduplication checks (for initial seeding on empty pool)",
    )

    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Show plan without generating questions",
    )

    parser.add_argument(
        "--resume",
        "-r",
        action="store_true",
        help="Check existing counts and fill gaps to reach target",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Parse content area if specified
    specific_area = None
    if args.area:
        specific_area = parse_content_area(args.area)
        if not specific_area:
            print(f"Error: Unknown content area '{args.area}'")
            print("\nValid content areas:")
            for area in ContentArea:
                print(f"  - {area.value}")
            sys.exit(1)

    # Run seeding
    try:
        result = asyncio.run(
            seed_questions(
                total_count=args.count,
                specific_area=specific_area,
                dry_run=args.dry_run,
                resume=args.resume,
                skip_dedup=args.skip_dedup,
            )
        )

        if result.get("status") == "complete":
            sys.exit(0)
        elif result.get("status") in ("dry_run", "already_complete"):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
