#!/usr/bin/env python3
"""
Vector Store management CLI for AbaQuiz.

Manages the OpenAI vector store containing BCBA study content.

Usage:
    # Create new vector store and upload all files
    python -m src.scripts.manage_vector_store create

    # Link to an existing vector store
    python -m src.scripts.manage_vector_store link <store_id>

    # Sync files (upload new, remove deleted)
    python -m src.scripts.manage_vector_store sync

    # List files in vector store
    python -m src.scripts.manage_vector_store list

    # Show vector store status
    python -m src.scripts.manage_vector_store status

    # Delete vector store
    python -m src.scripts.manage_vector_store delete
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.logging import get_logger, setup_logging
from src.services.vector_store_manager import get_vector_store_manager

logger = get_logger(__name__)


async def cmd_create(_args: argparse.Namespace) -> int:
    """Create a new vector store and upload all files."""
    manager = get_vector_store_manager()

    print("Creating vector store...")
    try:
        store_id = await manager.create_store()
        print(f"  Vector store ID: {store_id}")
    except RuntimeError as e:
        print(f"  Error: {e}")
        return 1

    print("\nUploading files...")
    try:
        file_ids = await manager.upload_files()
        print(f"  Uploaded {len(file_ids)} files")
    except RuntimeError as e:
        print(f"  Error: {e}")
        return 1

    print("\nVector store ready!")
    return 0


async def cmd_link(args: argparse.Namespace) -> int:
    """Link to an existing OpenAI vector store."""
    manager = get_vector_store_manager()

    store_id = args.store_id
    skip_file_sync = args.skip_file_sync
    force = args.force

    print(f"Linking to vector store: {store_id}")

    try:
        result = await manager.link_store(
            store_id=store_id,
            rebuild_file_state=not skip_file_sync,
            force=force,
        )
    except ValueError as e:
        print(f"  Error: {e}")
        return 1
    except RuntimeError as e:
        print(f"  Error: {e}")
        return 1

    print(f"\nLinked successfully!")
    print(f"  Store ID:   {result['store_id']}")
    print(f"  Store Name: {result['store_name']}")
    print(f"  Status:     {result['store_status']}")
    print()
    print(f"Files in OpenAI:")
    print(f"  Total:       {result['file_count']}")
    print(f"  Completed:   {result['files_completed']}")
    print(f"  In Progress: {result['files_in_progress']}")
    if result['files_failed'] > 0:
        print(f"  Failed:      {result['files_failed']}")
    print()
    print(f"Tracked locally: {result['tracked_files']} files")

    # Check for mismatches with local files
    local_files = list((manager.content_dir).glob("*.md"))
    local_files = [f for f in local_files if f.name != "00_index.md"]
    local_count = len(local_files)

    if local_count != result['tracked_files']:
        print()
        print(f"Warning: Local files ({local_count}) != tracked files ({result['tracked_files']})")
        print("  Consider running: python -m src.scripts.manage_vector_store sync")

    return 0


async def cmd_sync(_args: argparse.Namespace) -> int:
    """Synchronize local files with vector store."""
    manager = get_vector_store_manager()

    print("Syncing files with vector store...")
    try:
        result = await manager.sync()
    except RuntimeError as e:
        print(f"  Error: {e}")
        return 1

    print(f"\nSync complete:")
    print(f"  Added:     {len(result.added)}")
    for f in result.added:
        print(f"    + {f}")

    print(f"  Removed:   {len(result.removed)}")
    for f in result.removed:
        print(f"    - {f}")

    print(f"  Unchanged: {len(result.unchanged)}")

    if result.errors:
        print(f"  Errors:    {len(result.errors)}")
        for err in result.errors:
            print(f"    ! {err}")
        return 1

    return 0


async def cmd_list(_args: argparse.Namespace) -> int:
    """List all files in the vector store."""
    manager = get_vector_store_manager()

    files = await manager.list_files()

    if not files:
        print("No files in vector store.")
        print("Run: python -m src.scripts.manage_vector_store create")
        return 0

    print(f"Files in vector store ({len(files)}):\n")

    total_size = 0
    for f in files:
        size_kb = f.size_bytes / 1024
        total_size += f.size_bytes
        print(f"  {f.filename}")
        print(f"    ID: {f.file_id}")
        print(f"    Size: {size_kb:.1f} KB")
        print(f"    Uploaded: {f.uploaded_at}")
        print()

    print(f"Total: {total_size / 1024:.1f} KB")
    return 0


async def cmd_status(_args: argparse.Namespace) -> int:
    """Show vector store status."""
    manager = get_vector_store_manager()

    status = await manager.get_status()

    print("Vector Store Status")
    print("=" * 40)

    if not status["configured"]:
        print("  Status: NOT CONFIGURED")
        print("\nRun: python -m src.scripts.manage_vector_store create")
        return 0

    print(f"  Store ID:    {status['vector_store_id']}")
    if status.get('linked_at'):
        print(f"  Linked:      {status['linked_at']}")
    else:
        print(f"  Created:     {status['created_at']}")
    print(f"  Last Sync:   {status['last_sync'] or 'Never'}")
    print()

    print("File Counts:")
    print(f"  Local files:   {status['local_file_count']}")
    print(f"  Tracked files: {status['tracked_file_count']}")

    if "store_file_counts" in status:
        counts = status["store_file_counts"]
        print(f"  In OpenAI:     {counts['total']} ({counts['completed']} ready, {counts['in_progress']} processing)")
        if counts["failed"] > 0:
            print(f"    Warning: {counts['failed']} files failed")

    if "store_status" in status:
        print(f"\nStore Status: {status['store_status']}")

    if "store_error" in status:
        print(f"  Error: {status['store_error']}")
        return 1

    return 0


async def cmd_delete(args: argparse.Namespace) -> int:
    """Delete the vector store."""
    manager = get_vector_store_manager()

    store_id = await manager.get_store_id()
    if not store_id:
        print("No vector store configured.")
        return 0

    if not args.force:
        confirm = input(f"Delete vector store {store_id}? [y/N] ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0

    print("Deleting vector store...")
    await manager.delete_store()
    print("  Deleted.")
    return 0


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage OpenAI vector store for BCBA content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  create   Create new vector store and upload all files
  link     Link to an existing OpenAI vector store
  sync     Sync files (upload new/changed, remove deleted)
  list     List files in vector store
  status   Show vector store status
  delete   Delete vector store

Examples:
  %(prog)s create              # Initial setup
  %(prog)s link vs_abc123...   # Link to existing store
  %(prog)s sync                # After updating content files
  %(prog)s status              # Check current state
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create command
    subparsers.add_parser("create", help="Create vector store and upload files")

    # Link command
    link_parser = subparsers.add_parser("link", help="Link to an existing OpenAI vector store")
    link_parser.add_argument(
        "store_id",
        help="The OpenAI vector store ID (e.g., vs_abc123...)",
    )
    link_parser.add_argument(
        "--skip-file-sync",
        action="store_true",
        help="Don't fetch file list from OpenAI",
    )
    link_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing state even if linked to different store",
    )

    # Sync command
    subparsers.add_parser("sync", help="Sync files with vector store")

    # List command
    subparsers.add_parser("list", help="List files in vector store")

    # Status command
    subparsers.add_parser("status", help="Show vector store status")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete vector store")
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Delete without confirmation",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging("INFO")

    # Route to command handler
    handlers = {
        "create": cmd_create,
        "link": cmd_link,
        "sync": cmd_sync,
        "list": cmd_list,
        "status": cmd_status,
        "delete": cmd_delete,
    }

    handler = handlers.get(args.command)
    if handler:
        return await handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
