"""
Web server for AbaQuiz Admin GUI.

Uses aiohttp with Jinja2 templating, HTMX, Alpine.js, and Tailwind CSS.
"""

from pathlib import Path

from aiohttp import web
import aiohttp_jinja2
import jinja2

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


async def request_processor(request: web.Request) -> dict:
    """Context processor to add request to all templates."""
    return {"request": request}


def create_app() -> web.Application:
    """Create and configure the web application."""
    app = web.Application()

    # Setup Jinja2 templating with request context processor
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        context_processors=[request_processor],
    )

    # Setup routes
    setup_routes(app)

    # Static files
    app.router.add_static("/static", STATIC_DIR, name="static")

    return app


def setup_routes(app: web.Application) -> None:
    """Register all routes."""
    from src.web.routes import (
        index,
        tables_list,
        table_browse,
        table_rows,
        record_detail,
        questions_list,
        questions_cards,
        review_page,
        review_question_partial,
        submit_review,
    )
    from src.web.generation_routes import (
        generation_page,
        generation_progress_partial,
        api_pool_stats,
        api_get_config,
        api_save_config,
        api_start_generation,
        api_get_progress,
        api_cancel_generation,
        api_calculate_distribution,
    )

    app.router.add_get("/", index)
    app.router.add_get("/tables", tables_list)
    app.router.add_get("/tables/{name}", table_browse)
    app.router.add_get("/tables/{name}/rows", table_rows)  # HTMX partial
    app.router.add_get("/tables/{name}/{id}", record_detail)
    app.router.add_get("/questions", questions_list)
    app.router.add_get("/questions/cards", questions_cards)  # HTMX partial
    # Review routes
    app.router.add_get("/review", review_page)
    app.router.add_get("/review/question", review_question_partial)  # HTMX partial
    app.router.add_post("/review/submit", submit_review)
    # Generation routes
    app.router.add_get("/generation", generation_page)
    app.router.add_get("/generation/progress", generation_progress_partial)  # HTMX partial
    # Generation API routes
    app.router.add_get("/api/generation/pool-stats", api_pool_stats)
    app.router.add_get("/api/generation/config", api_get_config)
    app.router.add_post("/api/generation/config", api_save_config)
    app.router.add_post("/api/generation/start", api_start_generation)
    app.router.add_get("/api/generation/progress", api_get_progress)
    app.router.add_post("/api/generation/cancel", api_cancel_generation)
    app.router.add_get("/api/generation/distribution", api_calculate_distribution)
