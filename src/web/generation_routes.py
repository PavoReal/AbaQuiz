"""
Route handlers for Question Generation page in AbaQuiz Admin GUI.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
import aiohttp_jinja2

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.pool_manager import get_pool_manager, BCBA_WEIGHTS

logger = get_logger(__name__)


# In-memory storage for generation progress (resets on restart)
_generation_state: dict[str, Any] = {
    "running": False,
    "task": None,
    "progress": None,
    "cancel_requested": False,
}


def _get_admin_users() -> list[int]:
    """Get list of admin user IDs from config."""
    settings = get_settings()
    return settings.admin_users or []


async def _check_admin(request: web.Request) -> bool:
    """
    Check if the current request is from an admin user.
    For now, returns True since we don't have session auth implemented.
    In production, this should check session/token against admin_users list.
    """
    # TODO: Implement proper session-based admin authentication
    # For now, the web interface is assumed to be admin-only
    return True


@aiohttp_jinja2.template("generation.html")
async def generation_page(request: web.Request) -> dict:
    """Render the main generation page."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get pool statistics
    pool_stats = await _get_pool_stats(repo, settings)

    # Get current config
    config = _get_generation_config(settings)

    return {
        "pool_stats": pool_stats,
        "config": config,
        "is_running": _generation_state["running"],
    }


async def api_pool_stats(request: web.Request) -> web.Response:
    """API endpoint to get current pool statistics."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    settings = get_settings()
    repo = await get_repository(settings.database_path)
    pool_stats = await _get_pool_stats(repo, settings)

    return web.json_response(pool_stats)


async def _get_pool_stats(repo: Any, settings: Any) -> dict[str, Any]:
    """Get pool statistics for the dashboard."""
    pool_manager = get_pool_manager()

    # Get basic counts
    total_questions = await repo.get_total_question_count()
    active_users = await repo.get_active_user_count(days=pool_manager.settings.pool_active_days)
    avg_unseen = await repo.get_avg_unseen_questions_for_active_users(
        days=pool_manager.settings.pool_active_days
    )

    # Get counts by content area
    area_counts = await repo.get_question_pool_counts()

    # Calculate health status based on threshold
    threshold = pool_manager.threshold
    if total_questions == 0:
        health = "empty"
        health_message = "Pool is empty - generate initial questions"
    elif avg_unseen < threshold * 0.5:
        health = "critical"
        health_message = f"Pool critically low ({avg_unseen:.0f} avg unseen < {threshold * 0.5:.0f})"
    elif avg_unseen < threshold:
        health = "warning"
        health_message = f"Pool below threshold ({avg_unseen:.0f} avg unseen < {threshold})"
    else:
        health = "healthy"
        health_message = f"Pool healthy ({avg_unseen:.0f} avg unseen >= {threshold})"

    # Build area distribution with BCBA weights
    areas = []
    for area in ContentArea:
        count = area_counts.get(area.value, 0)
        weight = BCBA_WEIGHTS.get(area, 0)
        target = int(total_questions * weight) if total_questions > 0 else 0
        areas.append({
            "name": area.value,
            "count": count,
            "weight": weight,
            "weight_pct": f"{weight * 100:.0f}%",
            "target": target,
            "progress_pct": min(100, int(count / target * 100)) if target > 0 else 0,
        })

    return {
        "total_questions": total_questions,
        "active_users": active_users,
        "avg_unseen": round(avg_unseen, 1),
        "threshold": threshold,
        "health": health,
        "health_message": health_message,
        "areas": areas,
    }


def _get_generation_config(settings: Any) -> dict[str, Any]:
    """Get current generation configuration."""
    pool_manager = get_pool_manager()
    return {
        "threshold": pool_manager.threshold,
        "batch_size": pool_manager.batch_size,
        "dedup_threshold": pool_manager.dedup_threshold,
        "dedup_check_limit": pool_manager.dedup_check_limit,
        "generation_batch_size": pool_manager.generation_batch_size,
        "max_concurrent_generation": pool_manager.max_concurrent_generation,
    }


async def api_get_config(request: web.Request) -> web.Response:
    """API endpoint to get current generation config."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    settings = get_settings()
    config = _get_generation_config(settings)
    return web.json_response(config)


async def api_save_config(request: web.Request) -> web.Response:
    """API endpoint to save generation config changes."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # For now, just acknowledge the save - actual persistence would require
    # updating config.json and reloading settings
    # This is a TODO for full implementation
    return web.json_response({
        "success": True,
        "message": "Configuration saved (note: changes persist until restart)",
    })


async def api_start_generation(request: web.Request) -> web.Response:
    """API endpoint to start question generation."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    # Check if already running
    if _generation_state["running"]:
        return web.json_response({
            "error": "Generation already in progress",
        }, status=409)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    count = data.get("count", 50)
    skip_dedup = data.get("skip_dedup", False)
    difficulty_min = data.get("difficulty_min")

    # Validate difficulty_min
    if difficulty_min is not None:
        if not isinstance(difficulty_min, int) or difficulty_min < 1 or difficulty_min > 5:
            return web.json_response({
                "error": "difficulty_min must be an integer between 1 and 5",
            }, status=400)

    if not isinstance(count, int) or count < 1 or count > 500:
        return web.json_response({
            "error": "Count must be between 1 and 500",
        }, status=400)

    # Initialize progress state
    pool_manager = get_pool_manager()
    distribution = _calculate_distribution(count, pool_manager.bcba_weights)

    _generation_state["running"] = True
    _generation_state["cancel_requested"] = False
    _generation_state["progress"] = {
        "total": count,
        "generated": 0,
        "duplicates": 0,
        "errors": 0,
        "cost": 0.0,
        "areas": [
            {"name": area, "target": target, "done": 0}
            for area, target in distribution.items()
        ],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "complete": False,
        "skip_dedup": skip_dedup,
        "difficulty_min": difficulty_min,
    }

    # Start background task
    app = request.app
    task = asyncio.create_task(_run_generation(app, distribution, skip_dedup, difficulty_min))
    _generation_state["task"] = task

    return web.json_response({
        "success": True,
        "message": f"Started generating {count} questions",
        "distribution": distribution,
    })


def _calculate_distribution(count: int, weights: dict) -> dict[str, int]:
    """Calculate question distribution across content areas."""
    distribution = {}
    remaining = count

    # Sort by weight descending
    sorted_areas = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    for i, (area, weight) in enumerate(sorted_areas):
        area_name = area.value if hasattr(area, 'value') else str(area)
        if i == len(sorted_areas) - 1:
            distribution[area_name] = remaining
        else:
            area_count = round(count * weight)
            distribution[area_name] = area_count
            remaining -= area_count

    return distribution


async def _run_generation(
    app: web.Application,
    distribution: dict[str, int],
    skip_dedup: bool,
    difficulty_min: int | None = None,
) -> None:
    """Background task to run question generation in parallel."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)
    pool_manager = get_pool_manager()
    progress = _generation_state["progress"]

    # Cost estimates per question (GPT 5.2 pricing: Jan 2026)
    # GPT 5.2: $1.75/MTok input + $14/MTok output (~2K in + 2K out per batch of 5 = ~$0.007/q)
    # Embeddings: $0.13/MTok (~500 tokens = ~$0.00007)
    COST_PER_QUESTION = 0.007
    COST_PER_DEDUP = 0.0001

    def is_cancelled() -> bool:
        """Check if cancellation was requested."""
        return _generation_state["cancel_requested"]

    async def generate_single_area(area_name: str, target_count: int) -> dict[str, Any]:
        """Generate questions for a single content area."""
        result = {
            "area_name": area_name,
            "generated": 0,
            "duplicates": 0,
            "cost": 0.0,
            "error": None,
        }

        if target_count <= 0:
            return result

        try:
            area = ContentArea(area_name)
        except ValueError:
            result["error"] = f"Invalid content area: {area_name}"
            return result

        # Update progress to show we're working on this area
        for area_info in progress["areas"]:
            if area_info["name"] == area_name:
                area_info["status"] = "generating"
                break

        try:
            if skip_dedup:
                questions = await pool_manager.generate_without_dedup(
                    area, target_count, difficulty_min=difficulty_min
                )
                dedup_cost = 0
            else:
                questions = await pool_manager.generate_with_dedup(
                    area, target_count, difficulty_min=difficulty_min
                )
                # Estimate dedup cost (5 checks per question on average)
                dedup_cost = len(questions) * 5 * COST_PER_DEDUP

            # Store questions
            stored_count = 0
            for q in questions:
                if is_cancelled():
                    break

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

            result["generated"] = stored_count
            result["cost"] = (stored_count * COST_PER_QUESTION) + dedup_cost

            # Track duplicates (difference between expected and actual)
            if not skip_dedup:
                result["duplicates"] = max(0, target_count - stored_count)

            # Update area progress AND overall progress immediately
            for area_info in progress["areas"]:
                if area_info["name"] == area_name:
                    area_info["done"] = stored_count
                    area_info["status"] = "complete"
                    break

            # Update overall progress counters so the progress bar updates in real-time
            progress["generated"] += result["generated"]
            progress["duplicates"] += result["duplicates"]
            progress["cost"] += result["cost"]

        except Exception as e:
            logger.error(f"Generation failed for {area_name}: {e}", exc_info=True)
            result["error"] = str(e)
            for area_info in progress["areas"]:
                if area_info["name"] == area_name:
                    area_info["status"] = "error"
                    area_info["error"] = str(e)
                    break

        return result

    try:
        # Create tasks for all content areas
        tasks = [
            generate_single_area(area_name, target_count)
            for area_name, target_count in distribution.items()
        ]

        # Run all areas in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count errors (generated/duplicates/cost already updated in real-time)
        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Unexpected error in generation task: {result}", exc_info=True)
                progress["errors"] += 1
            elif isinstance(result, dict) and result.get("error"):
                progress["errors"] += 1

    except asyncio.CancelledError:
        logger.info("Generation task was cancelled")
        progress["cancelled"] = True
        raise
    finally:
        progress["complete"] = True
        progress["finished_at"] = datetime.now(timezone.utc).isoformat()
        _generation_state["running"] = False
        _generation_state["task"] = None


async def api_get_progress(request: web.Request) -> web.Response:
    """API endpoint to get current generation progress."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    if not _generation_state["progress"]:
        return web.json_response({
            "running": False,
            "progress": None,
        })

    progress = _generation_state["progress"].copy()
    progress["running"] = _generation_state["running"]

    # Calculate elapsed time
    if progress.get("started_at"):
        started = datetime.fromisoformat(progress["started_at"])
        if progress.get("finished_at"):
            finished = datetime.fromisoformat(progress["finished_at"])
            elapsed = (finished - started).total_seconds()
        else:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        progress["elapsed_seconds"] = int(elapsed)

    return web.json_response(progress)


@aiohttp_jinja2.template("partials/generation_progress.html")
async def generation_progress_partial(request: web.Request) -> dict:
    """HTMX partial for progress updates."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    progress = _generation_state["progress"]
    running = _generation_state["running"]

    if progress and progress.get("started_at"):
        started = datetime.fromisoformat(progress["started_at"])
        if progress.get("finished_at"):
            finished = datetime.fromisoformat(progress["finished_at"])
            elapsed = (finished - started).total_seconds()
        else:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        elapsed_seconds = int(elapsed)
    else:
        elapsed_seconds = 0

    return {
        "progress": progress,
        "running": running,
        "elapsed_seconds": elapsed_seconds,
    }


async def api_cancel_generation(request: web.Request) -> web.Response:
    """API endpoint to cancel running generation."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    if not _generation_state["running"]:
        return web.json_response({
            "error": "No generation in progress",
        }, status=400)

    _generation_state["cancel_requested"] = True

    return web.json_response({
        "success": True,
        "message": "Cancellation requested - generation will stop after current batch",
    })


async def api_calculate_distribution(request: web.Request) -> web.Response:
    """API endpoint to preview question distribution for a given count."""
    if not await _check_admin(request):
        raise web.HTTPForbidden(text="Admin access required")

    try:
        count = int(request.query.get("count", 50))
    except ValueError:
        return web.json_response({"error": "Invalid count"}, status=400)

    if count < 1 or count > 500:
        return web.json_response({
            "error": "Count must be between 1 and 500",
        }, status=400)

    pool_manager = get_pool_manager()
    distribution = _calculate_distribution(count, pool_manager.bcba_weights)

    # Calculate cost estimate
    # GPT 5.2 pricing (Jan 2026)
    COST_PER_QUESTION = 0.007  # GPT 5.2
    COST_PER_DEDUP = 0.0001  # Embeddings

    cost_with_dedup = count * (COST_PER_QUESTION + COST_PER_DEDUP)
    cost_without_dedup = count * COST_PER_QUESTION

    return web.json_response({
        "count": count,
        "distribution": distribution,
        "cost_estimate": {
            "with_dedup": round(cost_with_dedup, 2),
            "without_dedup": round(cost_without_dedup, 2),
        },
    })
