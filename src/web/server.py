"""
Web server for AbaQuiz Admin GUI.

Uses aiohttp with Jinja2 templating, HTMX, Alpine.js, and Pico CSS.
"""

from pathlib import Path

from aiohttp import web
import aiohttp_jinja2
import jinja2

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> web.Application:
    """Create and configure the web application."""
    app = web.Application()

    # Setup Jinja2 templating
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
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
    )

    app.router.add_get("/", index)
    app.router.add_get("/tables", tables_list)
    app.router.add_get("/tables/{name}", table_browse)
    app.router.add_get("/tables/{name}/rows", table_rows)  # HTMX partial
    app.router.add_get("/tables/{name}/{id}", record_detail)
    app.router.add_get("/questions", questions_list)
    app.router.add_get("/questions/cards", questions_cards)  # HTMX partial
