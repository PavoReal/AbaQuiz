# CLAUDE.md

Quick reference for Claude Code working with this repository. Keep this concise - see linked docs for details.

## Documentation Map

| Doc | Purpose |
|-----|---------|
| `IDEA.md` | Concept statement (2-3 sentences) |
| `DESIGN.md` | Full technical spec - consult for implementation decisions |
| `PLAN.md` | Phased implementation - track progress here |
| `docs/CLI_TOOLS.md` | Detailed CLI command reference |
| `docs/preprocessing_guide.md` | PDF preprocessing details |

## Tech Stack

- **Python 3.14+** with python-telegram-bot v20+
- **Claude claude-sonnet-4-5** for question generation (configurable in config.json)
- **Claude Haiku** for deduplication checks
- **SQLite + aiosqlite** for async database
- **APScheduler** for scheduled delivery
- **aiohttp + Jinja2 + HTMX** for web admin interface
- **Native PDF support** via Anthropic API (not pdfplumber)
- **Docker** for deployment

## Commands

```bash
# Always use the venv
source .venv/bin/activate

# Run bot
.venv/bin/python -m src.main

# Run web admin only (port 8070)
.venv/bin/python -m src.main --web-only

# Database inspection
.venv/bin/python -m src.main --db-stats           # Pool statistics
.venv/bin/python -m src.main --db-list --limit 20 # Recent questions
.venv/bin/python -m src.main --db-show 123        # Show question by ID
.venv/bin/python -m src.main --db-validate        # Validate integrity
.venv/bin/python -m src.main --json               # JSON output mode

# Seed questions
.venv/bin/python -m src.scripts.seed_questions --count 250
.venv/bin/python -m src.scripts.seed_questions --dry-run      # Cost estimate
.venv/bin/python -m src.scripts.seed_questions --resume       # Continue seeding

# Preprocessing (one-time)
.venv/bin/python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/

# Tests
.venv/bin/pytest tests/
.venv/bin/pytest tests/test_handlers.py -v
```

## Architecture

### Core Flow
1. **Scheduler** → triggers at 8 AM/PM per user timezone
2. **Pool Manager** → checks threshold, triggers batch generation if needed
3. **Question Generator** → loads `data/processed/*.md`, calls Claude API
4. **Bot Handler** → sends question with inline keyboard
5. **Callback Handler** → processes answer, updates stats, awards achievements

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/bot/handlers.py` | User commands (/start, /quiz, /stats) |
| `src/bot/admin_handlers.py` | Admin commands (/ban, /broadcast, /usage) |
| `src/bot/middleware.py` | DM-only, ban check, rate limiting decorators |
| `src/services/question_generator.py` | Claude API integration |
| `src/services/pool_manager.py` | Threshold checks, BCBA weights, dedup |
| `src/services/scheduler.py` | APScheduler job setup |
| `src/services/content_validator.py` | Validates MD files at startup |
| `src/services/usage_tracker.py` | API cost tracking with cache pricing |
| `src/database/repository.py` | All async DB operations |
| `src/database/migrations.py` | Schema versioning |
| `src/config/constants.py` | ContentArea enums, achievements, aliases |

### Web Admin Interface

Located in `src/web/`. Routes:
- `/` - Dashboard with pool stats
- `/tables` - Database browser
- `/tables/{name}` - Table with search/sort/pagination
- `/questions` - Question pool cards
- `/review` - Question quality review
- `/generation` - Real-time generation with progress tracking

Tech: aiohttp server + Jinja2 templates + HTMX for reactivity + Tailwind CSS

### Middleware Stack
```python
@dm_only_middleware        # Ignore group chats
@ban_check_middleware      # Block banned users
@rate_limit_middleware     # Throttle requests
```

## Configuration

| File | Contents |
|------|----------|
| `.env` | Secrets: TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY |
| `config/config.json` | All settings (supports `${ENV_VAR}` substitution) |

Key config sections:
- `question_generation.model` - Claude model for generation
- `pool_management.threshold` - Min unseen questions per active user (default: 20)
- `pool_management.BCBA_WEIGHTS` - Distribution across 9 content areas
- `pricing` - Token costs for Sonnet/Haiku including cache pricing

## Database

Core tables:
- `users` - Telegram users, timezone, focus_preferences (JSON)
- `questions` - Generated questions with model tracking
- `user_answers` - Answer history
- `user_stats` - Points, streaks
- `achievements` - Unlocked badges

Admin tables:
- `banned_users`, `admin_settings`, `api_usage`
- `sent_questions` - With is_scheduled flag
- `question_reports` - User-reported issues
- `question_stats` - Question performance metrics
- `question_reviews` - Admin quality reviews

Schema migrations managed in `src/database/migrations.py`

## Question Generation

### Categories
- **Scenario-based (40%)** - Clinical vignettes
- **Definition/Concept (30%)** - Key terms
- **Application (30%)** - Novel situations

### Pool Management
- Generate when avg unseen questions per active user < 20
- Active user = answered in last 7 days
- Batch size: 50 questions
- Dedup: Haiku checks against 50 most recent in same content area

### Seeding
```bash
# Full seed with cost estimate
.venv/bin/python -m src.scripts.seed_questions --dry-run

# Generate 250 distributed by BCBA weights
.venv/bin/python -m src.scripts.seed_questions --count 250

# Resume interrupted seeding (uses state file)
.venv/bin/python -m src.scripts.seed_questions --resume
```

## PDF Preprocessing

Uses **Claude's native PDF support** - sends PDFs directly to API (not pdfplumber extraction).

Pipeline:
1. Load PDF from `data/raw/`
2. Send to Claude API for structured markdown extraction
3. Output to `data/processed/{area}/` organized by BCBA content area

Output directories: `core/`, `ethics/`, `supervision/`, `reference/`

## Key Design Decisions

- **Pre-generated pool** - Batch refreshed, not on-demand
- **Hybrid question selection** - Mostly random, 1-in-5 targets weak areas
- **Day-based streaks** - One question/day maintains streak
- **No question expiration** - Users can answer anytime
- **Privacy first** - No leaderboards, individual progress only
- **Error handling** - Retry 3x with backoff, notify admins, never show errors to users

## Code Style

- Async-first with `aiosqlite` for all DB operations
- Type hints on all function signatures
- Decorators for middleware (applied in order)
- JSON fields for flexible user preferences
- Config-driven behavior (avoid hardcoding)

## Important Files

- `data/abaquiz.db` - Production database (never delete)
- `data/.seed_progress.json` - Seeding state for resume (auto-managed)
- `config/config.json` - All runtime configuration
- `data/processed/` - Required markdown content (validated at startup)
