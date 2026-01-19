"""
Route handlers for AbaQuiz Admin GUI.
"""

from aiohttp import web
import aiohttp_jinja2

from src.config.settings import get_settings
from src.database.repository import get_repository


@aiohttp_jinja2.template("index.html")
async def index(request: web.Request) -> dict:
    """Home page with dashboard overview."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)
    tables = await repo.get_all_tables()
    total_rows = sum(t["count"] for t in tables)
    return {
        "tables": tables,
        "total_tables": len(tables),
        "total_rows": total_rows,
    }


@aiohttp_jinja2.template("tables.html")
async def tables_list(request: web.Request) -> dict:
    """List all tables."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)
    tables = await repo.get_all_tables()
    return {"tables": tables}


@aiohttp_jinja2.template("table_browse.html")
async def table_browse(request: web.Request) -> dict:
    """Browse a single table with pagination, search, and sorting."""
    table_name = request.match_info["name"]
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse query params
    page = int(request.query.get("page", 1))
    search = request.query.get("search", "").strip() or None
    sort_col = request.query.get("sort")
    sort_dir = request.query.get("dir", "asc")

    try:
        schema = await repo.get_table_schema(table_name)
        data = await repo.browse_table(
            table_name, page, 25, search, sort_col, sort_dir
        )
    except ValueError as e:
        raise web.HTTPNotFound(text=str(e))

    return {
        "table_name": table_name,
        "schema": schema,
        "search": search or "",
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        **data,
    }


@aiohttp_jinja2.template("partials/table_rows.html")
async def table_rows(request: web.Request) -> dict:
    """HTMX partial: just the table rows and pagination."""
    table_name = request.match_info["name"]
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    page = int(request.query.get("page", 1))
    search = request.query.get("search", "").strip() or None
    sort_col = request.query.get("sort")
    sort_dir = request.query.get("dir", "asc")

    try:
        data = await repo.browse_table(
            table_name, page, 25, search, sort_col, sort_dir
        )
    except ValueError as e:
        raise web.HTTPNotFound(text=str(e))

    return {
        "table_name": table_name,
        "search": search or "",
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        **data,
    }


@aiohttp_jinja2.template("record.html")
async def record_detail(request: web.Request) -> dict:
    """View single record details."""
    table_name = request.match_info["name"]
    record_id = int(request.match_info["id"])
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        schema = await repo.get_table_schema(table_name)
        record = await repo.get_record(table_name, record_id)
    except ValueError as e:
        raise web.HTTPNotFound(text=str(e))

    if record is None:
        raise web.HTTPNotFound(text=f"Record {record_id} not found in {table_name}")

    return {
        "table_name": table_name,
        "record_id": record_id,
        "schema": schema,
        "record": record,
    }


@aiohttp_jinja2.template("questions.html")
async def questions_list(request: web.Request) -> dict:
    """Browse questions with card-based UI."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse query params
    page = int(request.query.get("page", 1))
    content_area = request.query.get("content_area", "").strip() or None
    difficulty = request.query.get("difficulty", "").strip()
    search = request.query.get("search", "").strip() or None

    # Parse difficulty filter
    difficulty_min = None
    difficulty_max = None
    if difficulty == "easy":
        difficulty_min, difficulty_max = 1, 2
    elif difficulty == "medium":
        difficulty_min = difficulty_max = 3
    elif difficulty == "hard":
        difficulty_min, difficulty_max = 4, 5

    data = await repo.browse_questions(
        page=page,
        per_page=20,
        content_area=content_area,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        search=search,
    )

    return {
        "search": search or "",
        "content_area": content_area or "",
        "difficulty": difficulty or "",
        **data,
    }


@aiohttp_jinja2.template("partials/question_cards.html")
async def questions_cards(request: web.Request) -> dict:
    """HTMX partial: just the question cards and pagination."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    page = int(request.query.get("page", 1))
    content_area = request.query.get("content_area", "").strip() or None
    difficulty = request.query.get("difficulty", "").strip()
    search = request.query.get("search", "").strip() or None

    # Parse difficulty filter
    difficulty_min = None
    difficulty_max = None
    if difficulty == "easy":
        difficulty_min, difficulty_max = 1, 2
    elif difficulty == "medium":
        difficulty_min = difficulty_max = 3
    elif difficulty == "hard":
        difficulty_min, difficulty_max = 4, 5

    data = await repo.browse_questions(
        page=page,
        per_page=20,
        content_area=content_area,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        search=search,
    )

    return {
        "search": search or "",
        "content_area": content_area or "",
        "difficulty": difficulty or "",
        **data,
    }
