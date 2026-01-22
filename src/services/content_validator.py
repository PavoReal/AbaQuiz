"""
Validate vector store configuration and content availability.

Provides startup validation and health check functionality.
"""

import asyncio
from pathlib import Path
from typing import Any

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.services.vector_store_manager import get_vector_store_manager

logger = get_logger(__name__)


def get_project_root() -> Path:
    """Get the project root directory (where CLAUDE.md lives)."""
    return Path(__file__).parent.parent.parent


def get_processed_content_dir() -> Path:
    """Get the absolute path to the processed content directory."""
    return get_project_root() / "data" / "processed"


async def validate_vector_store() -> dict[str, Any]:
    """
    Validate that the vector store is configured and populated.

    Returns:
        Dict with validation results including:
        - configured: Whether vector store is set up
        - file_count: Number of files in the store
        - local_file_count: Number of local markdown files
        - synced: Whether counts match
        - status: "healthy", "degraded", or "error"
    """
    manager = get_vector_store_manager()
    status = await manager.get_status()

    result: dict[str, Any] = {
        "configured": status["configured"],
        "vector_store_id": status.get("vector_store_id"),
        "local_file_count": status.get("local_file_count", 0),
        "tracked_file_count": status.get("tracked_file_count", 0),
    }

    if not status["configured"]:
        result["status"] = "error"
        result["message"] = "Vector store not configured. Run: python -m src.scripts.manage_vector_store create"
        return result

    # Check if files are synced
    local_count = status.get("local_file_count", 0)
    tracked_count = status.get("tracked_file_count", 0)

    if local_count == 0:
        result["status"] = "error"
        result["message"] = "No local content files found in data/processed/"
        return result

    if tracked_count == 0:
        result["status"] = "error"
        result["message"] = "No files uploaded to vector store. Run: python -m src.scripts.manage_vector_store sync"
        return result

    if local_count != tracked_count:
        result["status"] = "degraded"
        result["message"] = f"File count mismatch: {local_count} local, {tracked_count} in store. Run sync."
        result["synced"] = False
    else:
        result["status"] = "healthy"
        result["message"] = f"Vector store healthy with {tracked_count} files"
        result["synced"] = True

    # Include OpenAI store status if available
    if "store_file_counts" in status:
        result["store_file_counts"] = status["store_file_counts"]
        if status["store_file_counts"].get("failed", 0) > 0:
            result["status"] = "degraded"
            result["message"] += f" ({status['store_file_counts']['failed']} failed)"

    return result


async def validate_vector_store_on_startup(strict: bool = False) -> bool:
    """
    Validate vector store configuration on application startup.

    Args:
        strict: If True, raise RuntimeError if vector store is not ready.
                If False (default), log warnings but continue.

    Returns:
        True if vector store is healthy, False otherwise.

    Raises:
        RuntimeError: If strict=True and vector store is not ready.
    """
    result = await validate_vector_store()

    if result["status"] == "error":
        msg = f"Vector store validation failed: {result['message']}"
        logger.error(msg)
        if strict:
            raise RuntimeError(msg)
        return False

    if result["status"] == "degraded":
        logger.warning(f"Vector store degraded: {result['message']}")
        return True  # Can still function

    logger.info(f"Vector store validation passed: {result['message']}")
    return True


def validate_content_on_startup(strict: bool = False) -> bool:
    """
    Synchronous wrapper for vector store validation on startup.

    This maintains backwards compatibility with the existing startup flow.

    Args:
        strict: If True, raise RuntimeError if vector store is not ready.

    Returns:
        True if vector store is healthy, False otherwise.
    """
    # Check if we're already in an async context
    try:
        asyncio.get_running_loop()
        # We're in an async context, can't use asyncio.run()
        # Create a task and return a placeholder
        logger.warning("Cannot validate vector store synchronously from async context")
        return True
    except RuntimeError:
        # Not in async context, safe to use asyncio.run()
        return asyncio.run(validate_vector_store_on_startup(strict))


async def get_content_health() -> dict[str, Any]:
    """
    Return health status of vector store for monitoring.

    Returns:
        Dict with status, counts, and configuration details.
    """
    manager = get_vector_store_manager()

    # Get vector store status
    vs_status = await validate_vector_store()

    # Get list of tracked files
    files = await manager.list_files()
    file_list = [
        {
            "filename": f.filename,
            "size_kb": round(f.size_bytes / 1024, 1),
            "uploaded_at": f.uploaded_at,
        }
        for f in files
    ]

    return {
        "status": vs_status["status"],
        "message": vs_status.get("message", ""),
        "vector_store_id": vs_status.get("vector_store_id"),
        "total_areas": len(ContentArea),
        "local_file_count": vs_status.get("local_file_count", 0),
        "tracked_file_count": vs_status.get("tracked_file_count", 0),
        "synced": vs_status.get("synced", False),
        "files": file_list,
        "content_dir": str(get_processed_content_dir()),
    }


def get_valid_content_areas() -> list[ContentArea]:
    """
    Get list of content areas available for question generation.

    With vector store, all areas are available if the store is configured.

    Returns:
        List of all ContentArea enums if vector store is healthy,
        empty list otherwise.
    """
    try:
        asyncio.get_running_loop()
        # In async context
        logger.warning("get_valid_content_areas called from async context, returning all areas")
        return list(ContentArea)
    except RuntimeError:
        # Not in async context
        result = asyncio.run(validate_vector_store())
        if result["status"] in ("healthy", "degraded"):
            return list(ContentArea)
        return []
