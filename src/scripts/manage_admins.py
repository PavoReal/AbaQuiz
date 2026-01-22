#!/usr/bin/env python3
"""
Admin management CLI for AbaQuiz.

Manages bot administrators via the database.

Usage:
    # Add a regular admin
    python -m src.scripts.manage_admins add 123456789

    # Add a super admin (can manage other admins)
    python -m src.scripts.manage_admins add 123456789 --super

    # Remove an admin
    python -m src.scripts.manage_admins remove 123456789

    # List all admins
    python -m src.scripts.manage_admins list

    # Migrate from config.json to database (one-time)
    python -m src.scripts.manage_admins migrate
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
from src.database.migrations import run_migrations
from src.database.repository import close_repository, get_repository

logger = get_logger(__name__)


async def cmd_add(args: argparse.Namespace) -> int:
    """Add an admin to the database."""
    settings = get_settings()
    await run_migrations(settings.database_path)
    repo = await get_repository(settings.database_path)

    telegram_id = args.telegram_id
    is_super = args.super

    print(f"Adding admin: {telegram_id} (super_admin={is_super})")

    # Check if already an admin
    if await repo.is_admin(telegram_id):
        print(f"  User {telegram_id} is already an admin.")
        return 1

    # Add the admin
    success = await repo.add_admin(
        telegram_id=telegram_id,
        added_by=None,  # CLI doesn't have a "by" user
        is_super_admin=is_super,
    )

    if success:
        admin_type = "super admin" if is_super else "admin"
        print(f"  Added {telegram_id} as {admin_type}.")
        return 0
    else:
        print(f"  Failed to add admin.")
        return 1


async def cmd_remove(args: argparse.Namespace) -> int:
    """Remove an admin from the database."""
    settings = get_settings()
    await run_migrations(settings.database_path)
    repo = await get_repository(settings.database_path)

    telegram_id = args.telegram_id

    print(f"Removing admin: {telegram_id}")

    # Check if this is a super admin and if they're the last one
    if await repo.is_super_admin(telegram_id):
        super_count = await repo.get_super_admin_count()
        if super_count <= 1:
            print("  Error: Cannot remove the last super admin.")
            print("  Add another super admin first, then remove this one.")
            return 1

    # Remove the admin
    success = await repo.remove_admin(telegram_id)

    if success:
        print(f"  Removed {telegram_id} from admins.")
        return 0
    else:
        print(f"  User {telegram_id} was not an admin.")
        return 1


async def cmd_list(_args: argparse.Namespace) -> int:
    """List all admins in the database."""
    settings = get_settings()
    await run_migrations(settings.database_path)
    repo = await get_repository(settings.database_path)

    admins = await repo.get_all_admins()

    if not admins:
        print("No admins in database.")
        print("\nTo add an admin:")
        print("  python -m src.scripts.manage_admins add <telegram_id>")
        print("\nTo migrate from config.json:")
        print("  python -m src.scripts.manage_admins migrate")
        return 0

    print(f"Admins ({len(admins)} total):\n")
    print(f"{'Telegram ID':<15} {'Type':<12} {'Added By':<15} {'Added At'}")
    print("-" * 60)

    for admin in admins:
        telegram_id = admin["telegram_id"]
        admin_type = "super" if admin["is_super_admin"] else "regular"
        added_by = admin.get("added_by") or "CLI"
        added_at = str(admin.get("added_at", ""))[:19]
        print(f"{telegram_id:<15} {admin_type:<12} {str(added_by):<15} {added_at}")

    return 0


async def cmd_migrate(_args: argparse.Namespace) -> int:
    """Migrate admins from config.json to database."""
    settings = get_settings()
    await run_migrations(settings.database_path)
    repo = await get_repository(settings.database_path)

    config_admins = settings.admin_users

    if not config_admins:
        print("No admins found in config.json (admin.admin_users is empty).")
        return 0

    print(f"Migrating {len(config_admins)} admin(s) from config.json to database...\n")

    migrated = 0
    skipped = 0

    for i, telegram_id in enumerate(config_admins):
        # First admin becomes super admin
        is_super = i == 0

        if await repo.is_admin(telegram_id):
            print(f"  Skip: {telegram_id} (already in database)")
            skipped += 1
            continue

        success = await repo.add_admin(
            telegram_id=telegram_id,
            added_by=None,
            is_super_admin=is_super,
        )

        if success:
            admin_type = "super admin" if is_super else "admin"
            print(f"  Added: {telegram_id} as {admin_type}")
            migrated += 1
        else:
            print(f"  Failed: {telegram_id}")

    print(f"\nMigration complete: {migrated} added, {skipped} skipped")

    if migrated > 0:
        print("\nYou can now remove 'admin_users' from config.json if desired.")
        print("The database is now the source of truth for admin status.")

    return 0


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage AbaQuiz bot administrators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  add <id>    Add an admin (use --super for super admin)
  remove <id> Remove an admin (prevents removing last super admin)
  list        List all admins
  migrate     One-time migration from config.json to database

Examples:
  %(prog)s add 123456789              # Add regular admin
  %(prog)s add 123456789 --super      # Add super admin
  %(prog)s remove 123456789           # Remove admin
  %(prog)s list                       # List all admins
  %(prog)s migrate                    # Migrate from config.json
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add an admin")
    add_parser.add_argument(
        "telegram_id",
        type=int,
        help="Telegram user ID to add as admin",
    )
    add_parser.add_argument(
        "--super",
        action="store_true",
        help="Make this a super admin (can manage other admins)",
    )

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove an admin")
    remove_parser.add_argument(
        "telegram_id",
        type=int,
        help="Telegram user ID to remove from admins",
    )

    # List command
    subparsers.add_parser("list", help="List all admins")

    # Migrate command
    subparsers.add_parser("migrate", help="Migrate admins from config.json to database")

    args = parser.parse_args()

    # Setup logging
    setup_logging("INFO")

    # Route to command handler
    handlers = {
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "migrate": cmd_migrate,
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            return await handler(args)
        finally:
            await close_repository()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
