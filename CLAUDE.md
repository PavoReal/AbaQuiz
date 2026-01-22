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
- **GPT 5.2** for question generation with file search (400K context, 128K output)
- **OpenAI File Search API** for retrieving BCBA content from vector store
- **OpenAI Embeddings** (text-embedding-3-large) for deduplication
- **SQLite + aiosqlite** for async database
- **APScheduler** for scheduled delivery
- **aiohttp + Jinja2 + HTMX** for web admin interface
- **Native PDF support** via OpenAI API (GPT 5.2)
- **Docker** for deployment

## Commands

```bash
# Always use the venv
source .venv/bin/activate

# Run bot
.venv/bin/python -m src.main

# Run web admin only (port 8070)
.venv/bin/python -m src.main --web-only

# Vector store management
.venv/bin/python -m src.scripts.manage_vector_store create   # Initial setup
.venv/bin/python -m src.scripts.manage_vector_store link <id> # Link to existing store
.venv/bin/python -m src.scripts.manage_vector_store sync     # Sync after content changes
.venv/bin/python -m src.scripts.manage_vector_store status   # Check status
.venv/bin/python -m src.scripts.manage_vector_store list     # List files
.venv/bin/python -m src.scripts.manage_vector_store delete   # Delete store

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

# Admin management
.venv/bin/python -m src.scripts.manage_admins list            # List all admins
.venv/bin/python -m src.scripts.manage_admins add <id>        # Add admin
.venv/bin/python -m src.scripts.manage_admins add <id> --super # Add super admin
.venv/bin/python -m src.scripts.manage_admins remove <id>     # Remove admin
.venv/bin/python -m src.scripts.manage_admins migrate         # Migrate from config.json

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
3. **Question Generator** → uses file_search to retrieve content from vector store, calls GPT 5.2 API
4. **Bot Handler** → sends question with inline keyboard
5. **Callback Handler** → processes answer, updates stats, awards achievements

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/bot/handlers.py` | User commands (/start, /quiz, /stats) |
| `src/bot/admin_handlers.py` | Admin commands (/ban, /broadcast, /bonus, /usage) |
| `src/bot/middleware.py` | DM-only, ban check, rate limiting decorators |
| `src/services/question_generator.py` | GPT 5.2 + file_search for question generation |
| `src/services/vector_store_manager.py` | OpenAI vector store management |
| `src/services/dedup_service.py` | Embedding-based deduplication |
| `src/services/pool_manager.py` | Threshold checks, BCBA weights, dedup |
| `src/services/scheduler.py` | APScheduler job setup |
| `src/services/content_validator.py` | Validates vector store at startup |
| `src/services/usage_tracker.py` | API cost tracking |
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
| `.env` | Secrets: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY |
| `config/config.json` | All settings (supports `${ENV_VAR}` substitution) |

Key config sections:
- `question_generation.openai_model` - GPT model for question generation (default: gpt-5.2)
- `pool_management.threshold` - Min unseen questions per active user (default: 20)
- `pool_management.active_days` - Days to consider user "active" (default: 7)
- `pool_management.dedup_threshold` - Embedding similarity threshold (default: 0.85)
- `pool_management.bcba_weights` - Distribution across 9 content areas
- `pricing` - Token costs for GPT-5.2 and embeddings

## Database

Core tables:
- `users` - Telegram users, timezone, focus_preferences (JSON)
- `questions` - Generated questions with model tracking
- `user_answers` - Answer history
- `user_stats` - Points, streaks
- `achievements` - Unlocked badges

Admin tables:
- `admins` - Bot administrators (DB-backed, replaces config.json)
- `banned_users`, `admin_settings`, `api_usage`
- `sent_questions` - With is_scheduled and is_bonus flags
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
- Dedup: Embedding similarity check (threshold: 0.85)

### Seeding
```bash
# Full seed with cost estimate
.venv/bin/python -m src.scripts.seed_questions --dry-run

# Generate 250 distributed by BCBA weights
.venv/bin/python -m src.scripts.seed_questions --count 250

# Resume interrupted seeding (uses state file)
.venv/bin/python -m src.scripts.seed_questions --resume
```

## Vector Store Setup

Before running the bot, set up the vector store:

```bash
# 1. Preprocess PDFs to markdown (if not done)
.venv/bin/python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/

# 2. Create vector store and upload content
.venv/bin/python -m src.scripts.manage_vector_store create

# 3. Verify setup
.venv/bin/python -m src.scripts.manage_vector_store status
```

To link to an existing vector store (e.g., after state file loss):
```bash
.venv/bin/python -m src.scripts.manage_vector_store link vs_abc123...
```

After updating content files, run sync:
```bash
.venv/bin/python -m src.scripts.manage_vector_store sync
```

## PDF Preprocessing

Uses **GPT 5.2's native PDF support** - sends PDFs directly to API (not pdfplumber extraction).
Leverages GPT 5.2's 400K context window for complete document processing.

Pipeline:
1. Load PDF from `data/raw/`
2. Send to GPT 5.2 API for structured markdown extraction
3. Output to `data/processed/` as markdown files

## Key Design Decisions

- **Pre-generated pool** - Batch refreshed, not on-demand
- **Vector store** - Content stored in OpenAI for file_search retrieval
- **Embedding dedup** - Fast, cheap cosine similarity vs LLM-based
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
- `data/.vector_store_state.json` - Vector store state (auto-managed)
- `config/config.json` - All runtime configuration
- `data/processed/` - Markdown content for vector store
