# Feature 2: Admin Web GUI

## Overview

A minimal admin web GUI for AbaQuiz using HTMX, Alpine.js, and Pico CSS. Integrated into the main bot process, localhost only (no auth initially).

## Scope

**Initial Implementation (this plan):**
- Core web server integrated with bot
- Table browser: list tables, row counts, browse/search/paginate records

**Future (noted, not implemented):**
- User activity visualization
- User stats dashboard
- Leaderboards
- Settings management

---

## Technical Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Web Framework | aiohttp | Async-native, simple, integrates with existing asyncio loop |
| Templating | Jinja2 (aiohttp-jinja2) | Standard, powerful templating |
| Interactivity | HTMX | Server-driven, minimal JS |
| Client reactivity | Alpine.js | Lightweight, declarative |
| Styling | Pico CSS | Classless, semantic HTML |

---

## File Structure

```
src/
├── web/
│   ├── __init__.py
│   ├── server.py              # aiohttp app factory, middleware
│   ├── routes.py              # All route handlers
│   ├── templates/
│   │   ├── base.html          # Layout with HTMX/Alpine/Pico
│   │   ├── index.html         # Home/dashboard
│   │   ├── tables.html        # Table list
│   │   ├── table_browse.html  # Single table browser
│   │   ├── partials/
│   │   │   ├── table_rows.html    # HTMX partial: rows
│   │   │   └── pagination.html    # HTMX partial: pagination
│   │   └── record.html        # Single record detail
│   └── static/
│       └── custom.css         # Minimal overrides
├── database/
│   └── repository.py          # Add generic table methods
├── config/
│   └── settings.py            # Add web config
└── main.py                    # Start web server
```

---

## Implementation Plan

### Phase 1: Configuration (settings.py)

Add web server settings:

```python
# In Settings class
self.web_enabled = self._get_env_bool("WEB_ENABLED", True)
self.web_host = os.getenv("WEB_HOST", "127.0.0.1")
self.web_port = int(os.getenv("WEB_PORT", "8080"))
```

---

### Phase 2: Database Methods (repository.py)

Add generic table browsing methods:

```python
async def get_all_tables(self) -> list[dict]:
    """Get all table names with row counts."""
    async with self._get_connection() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = []
        for row in await cursor.fetchall():
            name = row[0]
            count_cursor = await db.execute(f"SELECT COUNT(*) FROM [{name}]")
            count = (await count_cursor.fetchone())[0]
            tables.append({"name": name, "count": count})
        return tables

async def get_table_schema(self, table_name: str) -> list[dict]:
    """Get column info for a table."""
    # Validate table name first
    tables = await self.get_all_tables()
    if table_name not in [t["name"] for t in tables]:
        raise ValueError(f"Invalid table: {table_name}")

    async with self._get_connection() as db:
        cursor = await db.execute(f"PRAGMA table_info([{table_name}])")
        return [
            {"name": row[1], "type": row[2], "nullable": not row[3], "pk": bool(row[5])}
            for row in await cursor.fetchall()
        ]

async def browse_table(
    self,
    table_name: str,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    sort_col: str | None = None,
    sort_dir: str = "asc",
) -> dict:
    """Browse table with pagination, search, sorting."""
    # Validate table
    tables = await self.get_all_tables()
    if table_name not in [t["name"] for t in tables]:
        raise ValueError(f"Invalid table: {table_name}")

    schema = await self.get_table_schema(table_name)
    columns = [c["name"] for c in schema]

    async with self._get_connection() as db:
        # Base query
        query = f"SELECT * FROM [{table_name}]"
        params = []

        # Search (across text columns)
        if search:
            text_cols = [c["name"] for c in schema if "TEXT" in c["type"].upper()]
            if text_cols:
                conditions = " OR ".join(f"[{col}] LIKE ?" for col in text_cols)
                query += f" WHERE ({conditions})"
                params.extend([f"%{search}%"] * len(text_cols))

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]

        # Sort
        if sort_col and sort_col in columns:
            direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
            query += f" ORDER BY [{sort_col}] {direction}"

        # Paginate
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"

        cursor = await db.execute(query, params)
        rows = [dict(zip(columns, row)) for row in await cursor.fetchall()]

        return {
            "rows": rows,
            "columns": columns,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }

async def get_record(self, table_name: str, record_id: int) -> dict | None:
    """Get single record by id."""
    schema = await self.get_table_schema(table_name)
    pk_col = next((c["name"] for c in schema if c["pk"]), "id")

    async with self._get_connection() as db:
        cursor = await db.execute(
            f"SELECT * FROM [{table_name}] WHERE [{pk_col}] = ?",
            [record_id]
        )
        row = await cursor.fetchone()
        if row:
            columns = [c["name"] for c in schema]
            return dict(zip(columns, row))
        return None
```

---

### Phase 3: Web Server Core (src/web/server.py)

```python
from aiohttp import web
import aiohttp_jinja2
import jinja2
from pathlib import Path

from src.config.settings import get_settings
from src.database.repository import get_repository

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> web.Application:
    """Create and configure the web application."""
    app = web.Application()

    # Setup Jinja2
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
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
    )

    app.router.add_get("/", index)
    app.router.add_get("/tables", tables_list)
    app.router.add_get("/tables/{name}", table_browse)
    app.router.add_get("/tables/{name}/rows", table_rows)  # HTMX partial
    app.router.add_get("/tables/{name}/{id}", record_detail)
```

---

### Phase 4: Route Handlers (src/web/routes.py)

```python
from aiohttp import web
import aiohttp_jinja2

from src.config.settings import get_settings
from src.database.repository import get_repository


@aiohttp_jinja2.template("index.html")
async def index(request: web.Request) -> dict:
    """Home page."""
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
    """Browse a single table."""
    table_name = request.match_info["name"]
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse query params
    page = int(request.query.get("page", 1))
    search = request.query.get("search", "").strip() or None
    sort_col = request.query.get("sort")
    sort_dir = request.query.get("dir", "asc")

    schema = await repo.get_table_schema(table_name)
    data = await repo.browse_table(
        table_name, page, 25, search, sort_col, sort_dir
    )

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
    """HTMX partial: just the table rows."""
    # Same logic as table_browse but returns partial
    table_name = request.match_info["name"]
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    page = int(request.query.get("page", 1))
    search = request.query.get("search", "").strip() or None
    sort_col = request.query.get("sort")
    sort_dir = request.query.get("dir", "asc")

    data = await repo.browse_table(
        table_name, page, 25, search, sort_col, sort_dir
    )

    return {"table_name": table_name, **data}


@aiohttp_jinja2.template("record.html")
async def record_detail(request: web.Request) -> dict:
    """View single record."""
    table_name = request.match_info["name"]
    record_id = int(request.match_info["id"])
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    schema = await repo.get_table_schema(table_name)
    record = await repo.get_record(table_name, record_id)

    return {
        "table_name": table_name,
        "record_id": record_id,
        "schema": schema,
        "record": record,
    }
```

---

### Phase 5: Templates

#### base.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AbaQuiz Admin{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <link rel="stylesheet" href="/static/custom.css">
</head>
<body>
    <nav class="container">
        <ul><li><strong>AbaQuiz Admin</strong></li></ul>
        <ul>
            <li><a href="/">Home</a></li>
            <li><a href="/tables">Tables</a></li>
        </ul>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

#### table_browse.html
```html
{% extends "base.html" %}
{% block title %}{{ table_name }} - AbaQuiz Admin{% endblock %}
{% block content %}
<h1>{{ table_name }}</h1>
<p>{{ total }} records</p>

<input type="search"
       name="search"
       placeholder="Search..."
       value="{{ search }}"
       hx-get="/tables/{{ table_name }}/rows"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#table-body"
       hx-include="this">

<table>
    <thead>
        <tr>
            {% for col in columns %}
            <th>
                <a href="?sort={{ col }}&dir={% if sort_col == col and sort_dir == 'asc' %}desc{% else %}asc{% endif %}&search={{ search }}"
                   hx-get="/tables/{{ table_name }}/rows?sort={{ col }}&dir={% if sort_col == col and sort_dir == 'asc' %}desc{% else %}asc{% endif %}&search={{ search }}"
                   hx-target="#table-body">
                    {{ col }}
                    {% if sort_col == col %}{% if sort_dir == 'asc' %}▲{% else %}▼{% endif %}{% endif %}
                </a>
            </th>
            {% endfor %}
        </tr>
    </thead>
    <tbody id="table-body">
        {% include "partials/table_rows.html" %}
    </tbody>
</table>

{% include "partials/pagination.html" %}
{% endblock %}
```

#### partials/table_rows.html
```html
{% for row in rows %}
<tr>
    {% for col in columns %}
    <td>
        {% if loop.first %}
        <a href="/tables/{{ table_name }}/{{ row[col] }}">{{ row[col] | truncate(50) }}</a>
        {% else %}
        {{ row[col] | truncate(50) if row[col] else '-' }}
        {% endif %}
    </td>
    {% endfor %}
</tr>
{% endfor %}
```

#### partials/pagination.html
```html
<nav aria-label="Pagination">
    <ul>
        {% if page > 1 %}
        <li><a href="?page={{ page - 1 }}&search={{ search }}&sort={{ sort_col }}&dir={{ sort_dir }}"
               hx-get="/tables/{{ table_name }}/rows?page={{ page - 1 }}&search={{ search }}&sort={{ sort_col }}&dir={{ sort_dir }}"
               hx-target="#table-body">Previous</a></li>
        {% endif %}

        <li>Page {{ page }} of {{ pages }}</li>

        {% if page < pages %}
        <li><a href="?page={{ page + 1 }}&search={{ search }}&sort={{ sort_col }}&dir={{ sort_dir }}"
               hx-get="/tables/{{ table_name }}/rows?page={{ page + 1 }}&search={{ search }}&sort={{ sort_col }}&dir={{ sort_dir }}"
               hx-target="#table-body">Next</a></li>
        {% endif %}
    </ul>
</nav>
```

---

### Phase 6: Main Integration (main.py)

```python
async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting AbaQuiz bot...")

    await initialize_database(settings.database_path)

    # Build telegram application
    application = Application.builder().token(settings.telegram_bot_token).build()
    register_handlers(application)

    # Start web server if enabled
    web_runner = None
    if settings.web_enabled:
        from aiohttp import web
        from src.web.server import create_app

        web_app = create_app()
        web_runner = web.AppRunner(web_app)
        await web_runner.setup()
        site = web.TCPSite(web_runner, settings.web_host, settings.web_port)
        await site.start()
        logger.info(f"Admin web UI: http://{settings.web_host}:{settings.web_port}")

    # Start scheduler
    await start_scheduler(application)

    # Run bot
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is running. Press Ctrl+C to stop.")

        await stop_event.wait()

        # Graceful shutdown
        logger.info("Shutting down...")
        await application.updater.stop()
        await application.stop()

    # Cleanup web server
    if web_runner:
        await web_runner.cleanup()

    stop_scheduler()
    logger.info("Bot stopped")
```

---

## Dependencies

Add to `requirements.txt`:
```
aiohttp>=3.9.0
aiohttp-jinja2>=1.6.0
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/web/__init__.py` | Create (empty) |
| `src/web/server.py` | Create |
| `src/web/routes.py` | Create |
| `src/web/templates/*.html` | Create (6 files) |
| `src/web/static/custom.css` | Create |
| `src/database/repository.py` | Add 4 methods |
| `src/config/settings.py` | Add web config |
| `src/main.py` | Add web server startup |
| `requirements.txt` | Add aiohttp deps |

---

## Future Scope (Not Implemented)

- **User Activity**: Charts of daily active users, question response rates
- **User Stats**: Filterable user list, individual user pages
- **Leaderboards**: Top users by streaks, points, accuracy
- **Settings**: Edit config values, manage admins, compose broadcasts

---

*Plan Version: 1.0*
*Created: 2026-01-18*
