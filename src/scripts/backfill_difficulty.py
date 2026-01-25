#!/usr/bin/env python3
"""
Backfill difficulty ratings for legacy questions using GPT 5.2.

Rates questions with difficulty = NULL on a 1-5 scale using minimal thinking budget.

Usage:
    python -m src.scripts.backfill_difficulty --dry-run
    python -m src.scripts.backfill_difficulty
    python -m src.scripts.backfill_difficulty --batch-size 10 --verbose
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.migrations import initialize_database, run_migrations
from src.database.repository import get_repository

logger = get_logger(__name__)

# System prompt for difficulty rating (~150 tokens)
RATING_SYSTEM_PROMPT = """You are an expert BCBA exam analyst. Rate question difficulty from 1-5:
1: Basic recall of a single concept
2: Understanding with straightforward application
3: Integration of 2+ concepts
4: Complex scenario with multiple variables
5: Multi-step reasoning and nuanced judgment

Respond with ONLY a JSON array of integers (ratings). Example: [2, 3, 1, 4, 2]
Do not include any other text or explanation."""


def format_question_for_rating(q: dict[str, Any], index: int) -> str:
    """Format a question for the rating prompt."""
    options_text = "\n".join(
        f"  {key}) {value}" for key, value in q["options"].items()
    )
    return f"""Question {index + 1}:
Content Area: {q["content_area"]}
Question: {q["content"]}
Options:
{options_text}
Correct Answer: {q["correct_answer"]}
"""


def build_user_prompt(questions: list[dict[str, Any]]) -> str:
    """Build the user prompt with all questions to rate."""
    formatted = [
        format_question_for_rating(q, i) for i, q in enumerate(questions)
    ]
    return f"""Rate the difficulty (1-5) for each of the following {len(questions)} questions.
Return a JSON array with exactly {len(questions)} integer ratings.

{chr(10).join(formatted)}
Return ONLY a JSON array like [{", ".join(["N"] * len(questions))}] where N is 1-5."""


def estimate_cost(question_count: int, batch_size: int) -> dict[str, float]:
    """Estimate API cost for rating questions."""
    settings = get_settings()

    # GPT 5.2 pricing
    gpt_pricing = settings.get_model_pricing("gpt-5.2") or {
        "input_per_million": 1.75,
        "output_per_million": 14.00,
    }

    # Estimate tokens per batch
    # System prompt: ~150 tokens
    # User prompt header: ~50 tokens per batch
    # Per question: ~350 tokens (content area, question text, 4 options with text, answer)
    #   - Question text: ~100-200 tokens
    #   - 4 options with labels: ~100-150 tokens
    #   - Formatting/labels: ~50 tokens
    # Output: ~3 tokens per question (single digit + comma + space)
    tokens_per_question = 350
    system_tokens = 150
    user_prompt_header_tokens = 50
    output_tokens_per_question = 3

    num_batches = (question_count + batch_size - 1) // batch_size
    total_input_tokens = (
        num_batches * (system_tokens + user_prompt_header_tokens)
        + question_count * tokens_per_question
    )
    total_output_tokens = question_count * output_tokens_per_question

    input_cost = total_input_tokens / 1_000_000 * gpt_pricing["input_per_million"]
    output_cost = total_output_tokens / 1_000_000 * gpt_pricing["output_per_million"]

    return {
        "num_batches": num_batches,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + output_cost,
    }


def parse_ratings_response(response_text: str, expected_count: int) -> list[int] | None:
    """Parse the JSON array of ratings from GPT response."""
    try:
        # Try to extract JSON array from response
        text = response_text.strip()

        # Handle case where response has extra text around JSON
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            text = text[start:end]

        ratings = json.loads(text)

        if not isinstance(ratings, list):
            logger.error(f"Response is not a list: {type(ratings)}")
            return None

        if len(ratings) != expected_count:
            logger.warning(
                f"Got {len(ratings)} ratings, expected {expected_count}"
            )
            # If we got fewer, pad with None; if more, truncate
            if len(ratings) < expected_count:
                return None
            ratings = ratings[:expected_count]

        # Validate each rating is 1-5
        validated = []
        for r in ratings:
            if isinstance(r, int) and 1 <= r <= 5:
                validated.append(r)
            elif isinstance(r, (int, float)) and 1 <= r <= 5:
                validated.append(int(r))
            else:
                logger.warning(f"Invalid rating value: {r}")
                validated.append(None)

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.debug(f"Response text: {response_text}")
        return None


async def rate_batch(
    client: AsyncOpenAI,
    questions: list[dict[str, Any]],
    verbose: bool = False,
) -> list[tuple[int, int | None]]:
    """
    Rate a batch of questions using GPT 5.2.

    Args:
        client: OpenAI async client
        questions: List of question dicts
        verbose: If True, print detailed output

    Returns:
        List of (question_id, rating) tuples. Rating is None if failed.
    """
    user_prompt = build_user_prompt(questions)

    if verbose:
        print(f"  Prompt length: ~{len(user_prompt)} chars")

    try:
        response = await client.responses.create(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": RATING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            reasoning={"effort": "low"},
        )

        # Extract text from response
        response_text = ""
        if hasattr(response, "output") and response.output:
            for item in response.output:
                if hasattr(item, "content") and item.content:
                    for content_item in item.content:
                        if hasattr(content_item, "text"):
                            response_text += content_item.text

        if verbose:
            print(f"  Response: {response_text[:100]}...")

        ratings = parse_ratings_response(response_text, len(questions))

        if ratings is None:
            logger.error("Failed to parse ratings from response")
            return [(q["id"], None) for q in questions]

        return [(q["id"], r) for q, r in zip(questions, ratings)]

    except Exception as e:
        logger.error(f"API error: {e}")
        return [(q["id"], None) for q in questions]


async def backfill_difficulty(
    dry_run: bool = False,
    batch_size: int = 20,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Backfill difficulty ratings for questions with NULL difficulty.

    Args:
        dry_run: If True, show plan without making changes
        batch_size: Number of questions per API call
        verbose: If True, print detailed progress

    Returns:
        Dict with results
    """
    settings = get_settings()

    # Initialize database
    await initialize_database(settings.database_path)
    await run_migrations(settings.database_path)

    repo = await get_repository(settings.database_path)

    try:
        # Get questions with NULL difficulty
        questions = await repo.get_questions_with_null_difficulty()
        total_questions = len(questions)

        if total_questions == 0:
            print("\nNo questions with NULL difficulty found.")
            return {"status": "already_complete", "total": 0, "updated": 0}

        # Estimate cost
        cost = estimate_cost(total_questions, batch_size)

        # Print plan
        print("\n" + "=" * 60)
        print("DIFFICULTY BACKFILL PLAN")
        print("=" * 60)
        print(f"\nQuestions to rate: {total_questions}")
        print(f"Batch size: {batch_size}")
        print(f"API calls: {cost['num_batches']}")
        print(f"\nEstimated tokens:")
        print(f"  Input:  ~{cost['total_input_tokens']:,}")
        print(f"  Output: ~{cost['total_output_tokens']:,}")
        print(f"\nEstimated cost: ${cost['total_cost']:.2f}")
        print("=" * 60)

        if dry_run:
            print("\n[DRY RUN] No changes made.")
            return {
                "status": "dry_run",
                "total": total_questions,
                "cost_estimate": cost,
            }

        # Confirm before proceeding
        print("\nProceed with rating? [y/N]: ", end="", flush=True)
        try:
            response = input().strip().lower()
        except EOFError:
            response = "y"

        if response not in ("y", "yes"):
            print("Aborted.")
            return {"status": "aborted", "total": total_questions}

        # Initialize OpenAI client
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            max_retries=3,
        )

        # Process in batches
        print(f"\nRating {total_questions} questions in batches of {batch_size}...")
        start_time = datetime.now()

        all_updates: list[tuple[int, int]] = []
        failed_count = 0
        batch_num = 0

        for i in range(0, total_questions, batch_size):
            batch = questions[i : i + batch_size]
            batch_num += 1

            print(f"\nBatch {batch_num}/{cost['num_batches']}: questions {i + 1}-{i + len(batch)}")

            results = await rate_batch(client, batch, verbose=verbose)

            # Collect successful ratings
            batch_updates = []
            for question_id, rating in results:
                if rating is not None:
                    batch_updates.append((question_id, rating))
                else:
                    failed_count += 1

            if batch_updates:
                # Update database
                updated = await repo.bulk_update_difficulty(batch_updates)
                all_updates.extend(batch_updates)
                print(f"  Updated {updated} questions")

                if verbose:
                    ratings_summary = [r for _, r in batch_updates]
                    print(f"  Ratings: {ratings_summary}")

        # Summary
        elapsed = datetime.now() - start_time
        total_updated = len(all_updates)

        print("\n" + "=" * 60)
        print("BACKFILL COMPLETE")
        print("=" * 60)
        print(f"\nTotal questions: {total_questions}")
        print(f"Successfully rated: {total_updated}")
        print(f"Failed: {failed_count}")
        print(f"Time elapsed: {elapsed}")

        # Show distribution
        if all_updates:
            distribution = {i: 0 for i in range(1, 6)}
            for _, rating in all_updates:
                distribution[rating] += 1

            print(f"\nDifficulty distribution:")
            for level, count in sorted(distribution.items()):
                pct = count / total_updated * 100 if total_updated > 0 else 0
                bar = "#" * int(pct / 2)
                print(f"  {level}: {count:3d} ({pct:5.1f}%) {bar}")

        return {
            "status": "complete",
            "total": total_questions,
            "updated": total_updated,
            "failed": failed_count,
            "elapsed_seconds": elapsed.total_seconds(),
        }

    finally:
        await repo.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill difficulty ratings for legacy questions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.scripts.backfill_difficulty --dry-run
      Show plan and cost estimate without making changes

  python -m src.scripts.backfill_difficulty
      Rate all questions with NULL difficulty (batch size 20)

  python -m src.scripts.backfill_difficulty --batch-size 10 --verbose
      Use smaller batches with detailed output
        """,
    )

    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Show plan without making changes",
    )

    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=20,
        help="Questions per API call (default: 20)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    try:
        result = asyncio.run(
            backfill_difficulty(
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                verbose=args.verbose,
            )
        )

        if result.get("status") in ("complete", "dry_run", "already_complete"):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
