# AbaQuiz CLI Tools Guide

This document covers the command-line tools for preprocessing BCBA study materials and managing the question pool.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [PDF Preprocessing](#pdf-preprocessing)
3. [Question Seeding](#question-seeding)
4. [Admin Management](#admin-management)
5. [Database CLI](#database-cli)
6. [Health Checks](#health-checks)
7. [Workflow Examples](#workflow-examples)

---

## Prerequisites

All commands should be run from the project root directory with the virtual environment activated:

```bash
cd /path/to/AbaQuiz
source .venv/bin/activate
```

Required environment variables (in `.env`):
- `OPENAI_API_KEY` - Your OpenAI API key
- `TELEGRAM_BOT_TOKEN` - Telegram bot token (for bot/DB commands)

---

## PDF Preprocessing

The preprocessing pipeline extracts content from BCBA study PDFs and converts them to structured markdown using GPT 5.2's native PDF support.

### Basic Usage

```bash
# Interactive mode (prompts before each file)
python -m src.preprocessing.run_preprocessing

# Process all PDFs without prompts
python -m src.preprocessing.run_preprocessing -y

# Process a single PDF file
python -m src.preprocessing.run_preprocessing -f data/raw/Ethics-Code-for-Behavior-Analysts.pdf

# Dry run (see what would be processed without calling API)
python -m src.preprocessing.run_preprocessing --dry-run
```

### Options

| Flag | Short | Description |
|------|-------|-------------|
| `--input DIR` | `-i` | Input directory with PDFs (default: `data/raw/`) |
| `--output DIR` | `-o` | Output directory for markdown (default: `data/processed/`) |
| `--file FILE` | `-f` | Process a single PDF file |
| `--dry-run` | | Show plan without calling OpenAI API |
| `--verbose` | `-v` | Show detailed progress |
| `--force` | | Reprocess all PDFs (ignore manifest) |
| `--yes` | `-y` | Skip prompts, process all without asking |

### How It Works

1. **Discovery**: Finds all PDFs in input directory
2. **Mapping**: Checks each PDF against `BCBA_DOCUMENTS` in `pdf_processor.py`
3. **Processing**: Sends PDF to GPT 5.2 for extraction and structuring
4. **Deduplication**: Content is hashed to prevent duplicates on re-runs
5. **Output**: Markdown saved to appropriate subdirectory

### Supported Documents

The following PDFs are mapped to output files:

| PDF File | Output Path |
|----------|-------------|
| `BCBA-Task-List-5th-Edition.pdf` | `core/task_list.md` |
| `BCBA-Handbook.pdf` | `core/handbook.md` |
| `BCBA-TCO-6th-Edition.pdf` | `core/tco.md` |
| `BCBA-6th-Edition-Test-Content-Outline-*.pdf` | `core/tco.md` |
| `Ethics-Code-for-Behavior-Analysts.pdf` | `ethics/ethics_code.md` |
| `Supervisor-Training-Curriculum.pdf` | `supervision/curriculum.md` |
| `ABA-Glossary-Workbook.pdf` | `reference/glossary.md` |
| `ABA-Terminology-Acronyms.pdf` | `reference/key_terms.md` |
| `PECS-Glossary.pdf` | `reference/glossary.md` |

### Resume Support

Processing state is saved in `data/processed/preprocessing_manifest.json`. If interrupted:
- Already-processed PDFs are skipped automatically
- Use `--force` to reprocess everything

### Adding New PDFs

To add a new BCBA-relevant PDF:

1. Place the PDF in `data/raw/` or a subdirectory
2. Edit `src/preprocessing/pdf_processor.py`:
   ```python
   BCBA_DOCUMENTS: dict[str, str] = {
       # ... existing entries ...
       "Your-New-PDF.pdf": "category/output_file.md",
   }
   ```
3. Run preprocessing: `python -m src.preprocessing.run_preprocessing -y`

---

## Question Seeding

The seeding script populates the question pool with AI-generated questions distributed according to BCBA exam weights.

### Basic Usage

```bash
# Generate 250 questions (default) with BCBA exam distribution
python -m src.scripts.seed_questions

# Initial seeding for empty pool (skip deduplication)
python -m src.scripts.seed_questions --count 250 --skip-dedup

# Generate questions for a specific content area
python -m src.scripts.seed_questions --area "Ethics" --count 50

# Dry run (show plan and cost estimate without generating)
python -m src.scripts.seed_questions --dry-run

# Resume/fill gaps to reach target count
python -m src.scripts.seed_questions --resume --count 300
```

### Options

| Flag | Short | Description |
|------|-------|-------------|
| `--count N` | `-c` | Number of questions to generate (default: 250) |
| `--area NAME` | `-a` | Generate for specific content area only |
| `--skip-dedup` | `-s` | Skip deduplication (for empty pool) |
| `--dry-run` | `-d` | Show plan without generating |
| `--resume` | `-r` | Check existing counts and fill gaps |
| `--verbose` | `-v` | Enable verbose logging |

### BCBA Exam Weight Distribution

Questions are distributed according to official BCBA exam weights:

| Content Area | Weight |
|--------------|--------|
| Behavior-Change Procedures | 14% |
| Concepts and Principles | 14% |
| Ethics | 13% |
| Behavior Assessment | 13% |
| Measurement | 12% |
| Selecting and Implementing Interventions | 11% |
| Personnel Supervision and Management | 11% |
| Experimental Design | 7% |
| Philosophical Underpinnings | 5% |

### Cost Estimation

The `--dry-run` flag shows estimated API costs:

```
============================================================
QUESTION SEEDING PLAN
============================================================

Total questions to generate: 250

Distribution by content area:
  Behavior-Change Procedures: 35 (14% weight)
  Concepts and Principles: 35 (14% weight)
  Ethics: 33 (13% weight)
  ...

Estimated cost:
  Generation (Sonnet): $3.60
    (50 API calls)
  Deduplication (Haiku): $1.13
    (~750 API calls)
  Total: $4.73
============================================================
```

**Approximate costs:**
- Initial seed (250 questions): ~$4-5
- Weekly batch (50 questions): ~$1
- With `--skip-dedup`: ~40% less

### Deduplication

By default, new questions are checked against existing questions in the same content area using OpenAI embeddings. This prevents generating near-duplicate questions.

- Use `--skip-dedup` for initial seeding on an empty pool
- Dedup checks the 50 most recent questions per area
- Uses early-exit optimization (stops at first duplicate found)

### Resume Support

Progress is saved to `data/.seed_progress.json`. If interrupted:
- Use `--resume` to continue where you left off
- Existing question counts are checked against targets
- Only missing questions are generated

### Content Areas

Valid content area names (case-insensitive, partial match supported):

- `Ethics`
- `Behavior Assessment`
- `Behavior-Change Procedures`
- `Concepts and Principles`
- `Measurement` (or `Measurement, Data Display, and Interpretation`)
- `Experimental Design`
- `Interventions` (or `Selecting and Implementing Interventions`)
- `Supervision` (or `Personnel Supervision and Management`)
- `Philosophical Underpinnings`

---

## Admin Management

The admin management CLI tool allows you to manage bot administrators via the database.

### Basic Usage

```bash
# Add a regular admin
python -m src.scripts.manage_admins add 123456789

# Add a super admin (can manage other admins)
python -m src.scripts.manage_admins add 123456789 --super

# Remove an admin
python -m src.scripts.manage_admins remove 123456789

# List all admins
python -m src.scripts.manage_admins list

# Migrate admins from config.json to database (one-time)
python -m src.scripts.manage_admins migrate
```

### Commands

| Command | Description |
|---------|-------------|
| `add <id>` | Add an admin (use `--super` for super admin privileges) |
| `remove <id>` | Remove an admin (prevents removing last super admin) |
| `list` | List all admins with their type and added date |
| `migrate` | One-time migration from config.json to database |

### Admin Types

- **Regular Admin**: Can use admin commands (`/ban`, `/users`, `/bonus`, etc.)
- **Super Admin**: Can also manage other admins via the CLI tool

### Migration from config.json

If you have existing admins in `config.json` under `admin.admin_users`, use the migrate command:

```bash
python -m src.scripts.manage_admins migrate
```

This will:
1. Read the `admin_users` array from config.json
2. Add them to the database (first one becomes super admin)
3. The database becomes the source of truth

After migration, the `admin_users` array in config.json can be left empty but serves as a fallback.

### Example Output

```bash
$ python -m src.scripts.manage_admins list

Admins (2 total):

Telegram ID     Type         Added By        Added At
------------------------------------------------------------
123456789       super        CLI             2025-01-21 10:30:15
987654321       regular      123456789       2025-01-21 11:45:22
```

---

## Database CLI

The main module includes database inspection commands for debugging and monitoring.

### Usage

```bash
# Show pool statistics
python -m src.main --db-stats

# List recent questions
python -m src.main --db-list
python -m src.main --db-list --limit 50

# Show specific question by ID
python -m src.main --db-show 123

# Validate all questions have proper options
python -m src.main --db-validate

# Output as JSON (for scripting)
python -m src.main --db-stats --json
python -m src.main --db-list --json
```

### Options

| Flag | Description |
|------|-------------|
| `--db-stats` | Show question pool counts by content area |
| `--db-list` | List recent questions |
| `--db-show ID` | Show full details of question by ID |
| `--db-validate` | Check all questions have valid options |
| `--limit N` | Limit for `--db-list` (default: 20) |
| `--json` | Output as JSON for external tools |

### Example Output

```bash
$ python -m src.main --db-stats

Question Pool Stats (247 total)
========================================
  Behavior Assessment: 32
  Behavior-Change Procedures: 35
  Concepts and Principles: 35
  Ethics: 33
  Experimental Design: 17
  Measurement: 30
  Philosophical Underpinnings: 12
  Personnel Supervision and Management: 28
  Selecting and Implementing Interventions: 25
```

---

## Health Checks

### Content Validation CLI

Check if all required content files exist:

```python
# In Python
from src.services.content_validator import get_content_health, validate_content_on_startup

# Quick check
health = get_content_health()
print(health["status"])  # "healthy", "degraded", or "error"

# Startup validation (logs warnings)
validate_content_on_startup(strict=False)
```

### Bot Health Command

If the bot is running, use the `/health` command in Telegram to check:
- Content file status
- Number of valid content areas
- Missing files (if any)

---

## Workflow Examples

### Initial Setup (New Installation)

```bash
# 1. Preprocess all PDFs
python -m src.preprocessing.run_preprocessing -y

# 2. Verify content files were created
python -c "from src.services.content_validator import get_content_health; print(get_content_health())"

# 3. Seed initial questions (skip dedup for empty pool)
python -m src.scripts.seed_questions --count 250 --skip-dedup

# 4. Verify pool statistics
python -m src.main --db-stats
```

### Adding a New PDF

```bash
# 1. Add PDF to data/raw/
cp ~/Downloads/New-BCBA-Material.pdf data/raw/

# 2. Update BCBA_DOCUMENTS mapping in pdf_processor.py
# 3. Process the new PDF
python -m src.preprocessing.run_preprocessing -f data/raw/New-BCBA-Material.pdf -v

# 4. Verify content health
python -c "from src.services.content_validator import get_content_health; print(get_content_health())"
```

### Weekly Question Replenishment

```bash
# Check current pool status
python -m src.main --db-stats

# Generate 50 new questions to top up pool
python -m src.scripts.seed_questions --count 50

# Or use resume to reach a target
python -m src.scripts.seed_questions --resume --count 300
```

### Troubleshooting

```bash
# Check for malformed questions
python -m src.main --db-validate

# List recent questions to inspect
python -m src.main --db-list --limit 10

# Check specific question
python -m src.main --db-show 42

# Reprocess a specific PDF if content is missing
python -m src.preprocessing.run_preprocessing -f data/raw/BCBA-Handbook.pdf --force -v
```

---

## File Locations

| File | Purpose |
|------|---------|
| `data/raw/` | Input PDFs for preprocessing |
| `data/processed/` | Generated markdown files |
| `data/processed/preprocessing_manifest.json` | Tracks processed PDFs |
| `data/.seed_progress.json` | Question seeding progress (temporary) |
| `data/abaquiz.db` | SQLite database with questions and user data |
| `config/config.json` | Application configuration |
| `.env` | Environment variables (API keys) |
