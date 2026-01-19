"""
Validate processed content files exist and are readable.

Provides startup validation and health check functionality.
"""

from pathlib import Path
from typing import Any

from src.config.constants import ContentArea
from src.config.logging import get_logger

logger = get_logger(__name__)

# Required files per content area
# Maps each content area to the files it depends on for question generation
REQUIRED_FILES: dict[ContentArea, list[str]] = {
    ContentArea.ETHICS: ["ethics/ethics_code.md", "core/handbook.md"],
    ContentArea.SUPERVISION: ["supervision/curriculum.md", "core/handbook.md"],
    ContentArea.CONCEPTS_AND_PRINCIPLES: ["core/task_list.md", "reference/glossary.md"],
    ContentArea.MEASUREMENT: ["core/task_list.md", "core/tco.md"],
    ContentArea.EXPERIMENTAL_DESIGN: ["core/task_list.md", "core/tco.md"],
    ContentArea.BEHAVIOR_ASSESSMENT: ["core/task_list.md", "core/tco.md"],
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: ["core/task_list.md", "reference/glossary.md"],
    ContentArea.INTERVENTIONS: ["core/task_list.md", "core/tco.md"],
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: ["core/task_list.md", "core/handbook.md"],
}


def get_project_root() -> Path:
    """Get the project root directory (where CLAUDE.md lives)."""
    return Path(__file__).parent.parent.parent


def get_processed_content_dir() -> Path:
    """Get the absolute path to the processed content directory."""
    return get_project_root() / "data" / "processed"


def validate_content_files(content_dir: Path | None = None) -> dict[ContentArea, list[str]]:
    """
    Check all required content files exist.

    Args:
        content_dir: Directory containing processed content. Defaults to project's data/processed.

    Returns:
        Dict of content areas with lists of missing files.
        Empty dict means all files are present.

    Raises:
        RuntimeError: If critical files are missing and generation cannot proceed.
    """
    if content_dir is None:
        content_dir = get_processed_content_dir()

    missing: dict[ContentArea, list[str]] = {}

    for area, files in REQUIRED_FILES.items():
        area_missing = []
        for file_path in files:
            full_path = content_dir / file_path
            if not full_path.exists():
                area_missing.append(file_path)
                logger.warning(f"Missing content file for {area.value}: {file_path}")
            elif full_path.stat().st_size == 0:
                area_missing.append(file_path)
                logger.warning(f"Empty content file for {area.value}: {file_path}")

        if area_missing:
            missing[area] = area_missing

    if missing:
        logger.error(f"Content validation failed: {len(missing)} areas have missing files")
        # List which areas can still generate questions
        valid_areas = [a for a in ContentArea if a not in missing]
        logger.info(f"Valid content areas: {[a.value for a in valid_areas]}")

    return missing


def validate_content_on_startup(strict: bool = False) -> bool:
    """
    Validate content files on application startup.

    Args:
        strict: If True, raise RuntimeError on any missing files.
                If False (default), log warnings but continue.

    Returns:
        True if all files present, False otherwise.

    Raises:
        RuntimeError: If strict=True and files are missing.
    """
    content_dir = get_processed_content_dir()

    if not content_dir.exists():
        msg = (
            f"Processed content directory does not exist: {content_dir}\n"
            f"Run preprocessing first: python -m src.preprocessing.run_preprocessing"
        )
        logger.error(msg)
        if strict:
            raise RuntimeError(msg)
        return False

    missing = validate_content_files(content_dir)

    if missing:
        areas_str = ", ".join(a.value for a in missing.keys())
        msg = (
            f"Content files missing for {len(missing)} area(s): {areas_str}\n"
            f"Question generation will fail for these areas.\n"
            f"Run preprocessing: python -m src.preprocessing.run_preprocessing"
        )
        logger.warning(msg)
        if strict:
            raise RuntimeError(msg)
        return False

    logger.info(f"Content validation passed: all {len(ContentArea)} areas have required files")
    return True


def get_content_health() -> dict[str, Any]:
    """
    Return health status of content files for monitoring.

    Returns:
        Dict with status, counts, and details about missing files.
    """
    content_dir = get_processed_content_dir()

    # Check if directory exists
    if not content_dir.exists():
        return {
            "status": "error",
            "message": f"Content directory not found: {content_dir}",
            "total_areas": len(ContentArea),
            "valid_areas": 0,
            "missing_files": {a.value: REQUIRED_FILES[a] for a in ContentArea},
        }

    missing = validate_content_files(content_dir)

    # Get file stats for present files
    file_stats: dict[str, dict[str, Any]] = {}
    all_files = set()
    for files in REQUIRED_FILES.values():
        all_files.update(files)

    for file_path in all_files:
        full_path = content_dir / file_path
        if full_path.exists():
            stat = full_path.stat()
            file_stats[file_path] = {
                "size_kb": round(stat.st_size / 1024, 1),
                "exists": True,
            }
        else:
            file_stats[file_path] = {"exists": False}

    status = "healthy" if not missing else "degraded"
    valid_count = len(ContentArea) - len(missing)

    return {
        "status": status,
        "total_areas": len(ContentArea),
        "valid_areas": valid_count,
        "missing_files": {k.value: v for k, v in missing.items()},
        "content_dir": str(content_dir),
        "file_stats": file_stats,
    }


def get_valid_content_areas() -> list[ContentArea]:
    """
    Get list of content areas that have all required files.

    Returns:
        List of ContentArea enums that can generate questions.
    """
    missing = validate_content_files()
    return [area for area in ContentArea if area not in missing]
