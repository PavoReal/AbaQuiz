#!/usr/bin/env python3
"""
Backfill analytics data from historical raw tables.

Usage:
    python -m src.scripts.backfill_analytics --all
    python -m src.scripts.backfill_analytics --start 2024-01-01 --end 2024-12-31
    python -m src.scripts.backfill_analytics --dry-run

This script computes and stores analytics snapshots for historical data.
"""

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.migrations import run_migrations
from src.database.repository import get_repository
from src.services.analytics_service import AnalyticsService

logger = get_logger(__name__)


async def get_date_range(repo) -> tuple[date, date]:
    """Get the date range from the earliest data to yesterday."""
    # Find earliest user_answer date
    async with repo.db.execute(
        "SELECT MIN(DATE(answered_at)) as min_date FROM user_answers"
    ) as cursor:
        row = await cursor.fetchone()
        if row and row["min_date"]:
            start_date = datetime.strptime(row["min_date"], "%Y-%m-%d").date()
        else:
            start_date = date.today() - timedelta(days=7)

    # Find earliest user creation date
    async with repo.db.execute(
        "SELECT MIN(DATE(created_at)) as min_date FROM users"
    ) as cursor:
        row = await cursor.fetchone()
        if row and row["min_date"]:
            user_start = datetime.strptime(row["min_date"], "%Y-%m-%d").date()
            start_date = min(start_date, user_start)

    # End at yesterday (today is incomplete)
    end_date = date.today() - timedelta(days=1)

    return start_date, end_date


async def backfill_daily_snapshots(
    service: AnalyticsService,
    start_date: date,
    end_date: date,
    dry_run: bool = False,
) -> dict:
    """Backfill daily system snapshots for a date range."""
    results = {
        "days_processed": 0,
        "snapshots_saved": 0,
        "hourly_records_saved": 0,
        "errors": [],
    }

    current = start_date
    total_days = (end_date - start_date).days + 1
    processed = 0

    logger.info(f"Backfilling system snapshots from {start_date} to {end_date} ({total_days} days)")

    while current <= end_date:
        processed += 1
        if processed % 10 == 0 or processed == total_days:
            logger.info(f"Progress: {processed}/{total_days} days")

        try:
            if not dry_run:
                result = await service.compute_daily_snapshots(current)
                results["snapshots_saved"] += 1
                results["hourly_records_saved"] += result.get("hourly_records_saved", 0)

            results["days_processed"] += 1

        except Exception as e:
            error_msg = f"Error on {current}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        current += timedelta(days=1)

    return results


async def backfill_user_snapshots(
    service: AnalyticsService,
    repo,
    start_date: date,
    end_date: date,
    dry_run: bool = False,
) -> dict:
    """Backfill user daily snapshots for a date range."""
    results = {
        "days_processed": 0,
        "user_snapshots_saved": 0,
        "errors": [],
    }

    # Get all unique timezones
    async with repo.db.execute(
        "SELECT DISTINCT timezone FROM users WHERE timezone IS NOT NULL"
    ) as cursor:
        rows = await cursor.fetchall()
        timezones = [row["timezone"] for row in rows]

    if not timezones:
        timezones = ["America/Los_Angeles"]

    logger.info(f"Backfilling user snapshots for {len(timezones)} timezones")

    current = start_date
    total_days = (end_date - start_date).days + 1
    processed = 0

    while current <= end_date:
        processed += 1
        if processed % 10 == 0 or processed == total_days:
            logger.info(f"Progress: {processed}/{total_days} days")

        for tz in timezones:
            try:
                if not dry_run:
                    result = await service.compute_user_snapshots_for_timezone(tz, current)
                    results["user_snapshots_saved"] += result.get("users_processed", 0)

            except Exception as e:
                error_msg = f"Error on {current} for {tz}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        results["days_processed"] += 1
        current += timedelta(days=1)

    return results


async def backfill_weekly_retention(
    service: AnalyticsService,
    start_date: date,
    end_date: date,
    dry_run: bool = False,
) -> dict:
    """Backfill weekly retention snapshots for a date range."""
    results = {
        "weeks_processed": 0,
        "errors": [],
    }

    # Find the first Monday on or after start_date
    days_until_monday = (7 - start_date.weekday()) % 7
    if days_until_monday == 0 and start_date.weekday() != 0:
        days_until_monday = 7
    current_monday = start_date + timedelta(days=days_until_monday)
    if start_date.weekday() == 0:
        current_monday = start_date

    logger.info(f"Backfilling weekly retention from {current_monday} to {end_date}")

    while current_monday <= end_date:
        try:
            if not dry_run:
                await service.compute_weekly_retention(current_monday)
            results["weeks_processed"] += 1
            logger.info(f"Processed week starting {current_monday}")

        except Exception as e:
            error_msg = f"Error for week {current_monday}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        current_monday += timedelta(days=7)

    return results


async def main():
    parser = argparse.ArgumentParser(
        description="Backfill analytics data from historical records"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all historical data from earliest record to yesterday",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing to database",
    )
    parser.add_argument(
        "--skip-system",
        action="store_true",
        help="Skip system daily snapshots",
    )
    parser.add_argument(
        "--skip-users",
        action="store_true",
        help="Skip user daily snapshots",
    )
    parser.add_argument(
        "--skip-retention",
        action="store_true",
        help="Skip weekly retention snapshots",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not (args.start and args.end):
        print("Error: Must specify either --all or both --start and --end")
        sys.exit(1)

    # Initialize
    settings = get_settings()
    await run_migrations(settings.database_path)
    repo = await get_repository(settings.database_path)
    service = AnalyticsService(repo)

    # Determine date range
    if args.all:
        start_date, end_date = await get_date_range(repo)
        logger.info(f"Auto-detected date range: {start_date} to {end_date}")
    else:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    if start_date > end_date:
        print("Error: Start date must be before end date")
        sys.exit(1)

    total_days = (end_date - start_date).days + 1

    if args.dry_run:
        print(f"\n=== DRY RUN MODE ===")
        print(f"Would backfill analytics from {start_date} to {end_date}")
        print(f"Total days: {total_days}")
        print(f"Skip system snapshots: {args.skip_system}")
        print(f"Skip user snapshots: {args.skip_users}")
        print(f"Skip retention: {args.skip_retention}")
        print(f"====================\n")

    # Backfill system snapshots
    if not args.skip_system:
        print(f"\n--- System Daily Snapshots ---")
        system_results = await backfill_daily_snapshots(
            service, start_date, end_date, args.dry_run
        )
        print(f"Days processed: {system_results['days_processed']}")
        if not args.dry_run:
            print(f"Snapshots saved: {system_results['snapshots_saved']}")
            print(f"Hourly records: {system_results['hourly_records_saved']}")
        if system_results["errors"]:
            print(f"Errors: {len(system_results['errors'])}")

    # Backfill user snapshots
    if not args.skip_users:
        print(f"\n--- User Daily Snapshots ---")
        user_results = await backfill_user_snapshots(
            service, repo, start_date, end_date, args.dry_run
        )
        print(f"Days processed: {user_results['days_processed']}")
        if not args.dry_run:
            print(f"User snapshots saved: {user_results['user_snapshots_saved']}")
        if user_results["errors"]:
            print(f"Errors: {len(user_results['errors'])}")

    # Backfill weekly retention
    if not args.skip_retention:
        print(f"\n--- Weekly Retention ---")
        retention_results = await backfill_weekly_retention(
            service, start_date, end_date, args.dry_run
        )
        print(f"Weeks processed: {retention_results['weeks_processed']}")
        if retention_results["errors"]:
            print(f"Errors: {len(retention_results['errors'])}")

    print(f"\n=== Backfill Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
