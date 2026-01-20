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


# =============================================================================
# Expert Review Routes
# =============================================================================


@aiohttp_jinja2.template("review.html")
async def review_page(request: web.Request) -> dict:
    """Expert review page for grading questions."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get optional content area filter
    content_area = request.query.get("content_area", "").strip() or None
    question_id = request.query.get("id", "").strip()

    # Get review queue counts
    queue_counts = await repo.get_review_queue_count(content_area)

    # Get distinct content areas for filter
    pool_counts = await repo.get_question_pool_counts()
    content_areas = sorted(pool_counts.keys())

    # Get initial question
    question = None
    if question_id:
        try:
            question = await repo.get_question_with_review_data(int(question_id))
        except ValueError:
            pass
    else:
        # Get next unreviewed question
        question = await repo.get_next_unreviewed_question(content_area=content_area)
        if question:
            question = await repo.get_question_with_review_data(question["id"])

    return {
        "question": question,
        "queue_counts": queue_counts,
        "content_areas": content_areas,
        "current_area": content_area or "",
    }


@aiohttp_jinja2.template("partials/review_question.html")
async def review_question_partial(request: web.Request) -> dict:
    """HTMX partial: load a specific question for review."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    question_id = request.query.get("id", "").strip()
    direction = request.query.get("direction", "").strip()
    content_area = request.query.get("content_area", "").strip() or None

    question = None

    if question_id:
        try:
            qid = int(question_id)
            if direction == "next":
                # Get next unreviewed after this ID
                question = await repo.get_next_unreviewed_question(
                    current_id=qid, content_area=content_area
                )
            elif direction == "prev":
                # Get previous question (any status)
                async with repo.db.execute(
                    """
                    SELECT * FROM questions
                    WHERE id < ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (qid,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        import json
                        question = dict(row)
                        question["options"] = json.loads(question["options"])
                        if question.get("source_citation"):
                            try:
                                question["source_citation"] = json.loads(question["source_citation"])
                            except:
                                pass
            else:
                question = await repo.get_question_by_id(qid)
        except ValueError:
            pass
    else:
        # Get next unreviewed
        question = await repo.get_next_unreviewed_question(content_area=content_area)

    if question:
        question = await repo.get_question_with_review_data(question["id"])

    return {"question": question}


async def submit_review(request: web.Request) -> web.Response:
    """Handle review form submission."""
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse form data
    data = await request.post()
    question_id = data.get("question_id")
    decision = data.get("decision")
    reviewer_id = data.get("reviewer_id", "").strip() or "anonymous"
    difficulty = data.get("difficulty", "").strip()
    notes = data.get("notes", "").strip() or None

    if not question_id or not decision:
        raise web.HTTPBadRequest(text="Missing question_id or decision")

    try:
        qid = int(question_id)
        diff = int(difficulty) if difficulty else None
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid question_id or difficulty")

    # Create the review
    await repo.create_question_review(
        question_id=qid,
        reviewer_id=reviewer_id,
        decision=decision,
        notes=notes,
        difficulty=diff,
    )

    # Return HTMX-compatible redirect or partial reload
    if request.headers.get("HX-Request"):
        # Get next unreviewed question
        content_area = data.get("content_area", "").strip() or None
        next_question = await repo.get_next_unreviewed_question(
            current_id=qid, content_area=content_area
        )
        if next_question:
            next_question = await repo.get_question_with_review_data(next_question["id"])

        # Return the next question partial
        response = aiohttp_jinja2.render_template(
            "partials/review_question.html",
            request,
            {"question": next_question},
        )
        return response
    else:
        # Regular redirect
        raise web.HTTPFound("/review")
