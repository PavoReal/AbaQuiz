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
