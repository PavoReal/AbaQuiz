# AbaQuiz

A Telegram bot for BCBA (Board Certified Behavior Analyst) exam preparation. Delivers daily Applied Behavior Analysis quiz questions powered by Claude AI, with gamification features to keep you motivated.

## Features

- **Daily Quiz Delivery** - Receive 2 questions per day at 8 AM and 8 PM (configurable, respects your timezone)
- **AI-Generated Questions** - Claude AI generates questions from official BCBA study materials
- **On-Demand Quizzes** - Request extra questions anytime with `/quiz`
- **Progress Tracking** - Track accuracy overall and per content area
- **Gamification** - Earn points, maintain streaks, unlock achievements
- **Personalized Learning** - Set focus areas for targeted weak-area practice
- **Admin Dashboard** - User management, broadcasting, API usage tracking

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Bot Framework | python-telegram-bot v20+ |
| LLM | Anthropic Claude API |
| Database | SQLite (aiosqlite) |
| Scheduling | APScheduler |
| PDF Processing | pdfplumber |
| Deployment | Docker |

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Anthropic API Key (from [console.anthropic.com](https://console.anthropic.com))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/AbaQuiz.git
   cd AbaQuiz
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

4. Add your credentials to `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

5. Run the bot:
   ```bash
   python -m src.main
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token from BotFather |
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `DATABASE_PATH` | No | `./data/abaquiz.db` | SQLite database path |
| `DEFAULT_TIMEZONE` | No | `America/Los_Angeles` | Default user timezone |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### Application Settings

Additional settings are in `config/config.json`:
- Quiz delivery times
- Rate limits
- Question generation parameters
- Admin user IDs

## User Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and complete onboarding |
| `/quiz` | Get an on-demand quiz question |
| `/stats` | View your accuracy and progress |
| `/streak` | Check your current streak |
| `/achievements` | View unlocked badges |
| `/areas` | List BCBA content areas with your accuracy |
| `/settings` | Update timezone, focus areas, subscription |
| `/help` | Show available commands |
| `/stop` | Unsubscribe from daily questions |

## Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | List admin commands |
| `/users` | List all registered users |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/broadcast <message>` | Send message to all subscribers |
| `/usage` | View 24h API usage and costs |

## Docker Deployment

```bash
# Build and run with docker-compose
docker-compose -f docker/docker-compose.yml up --build

# Run in detached mode
docker-compose -f docker/docker-compose.yml up -d
```

The Docker setup includes:
- Automatic restart on failure
- Persistent volumes for database and logs
- Health checks

## Project Structure

```
AbaQuiz/
├── src/
│   ├── main.py                 # Application entry point
│   ├── bot/
│   │   ├── handlers.py         # User command handlers
│   │   ├── admin_handlers.py   # Admin command handlers
│   │   ├── middleware.py       # Request filtering
│   │   ├── keyboards.py        # Inline keyboards
│   │   └── messages.py         # Message templates
│   ├── services/
│   │   ├── question_generator.py   # Claude API integration
│   │   ├── pool_manager.py         # Question pool management
│   │   ├── scheduler.py            # Quiz scheduling
│   │   └── usage_tracker.py        # API cost tracking
│   ├── scripts/
│   │   ├── seed_questions.py       # Initial pool seeding CLI
│   │   └── cleanup_questions.py    # Invalid question cleanup CLI
│   ├── database/
│   │   ├── models.py           # Table definitions
│   │   ├── migrations.py       # Schema setup
│   │   └── repository.py       # Data access layer
│   ├── preprocessing/          # PDF processing pipeline
│   └── config/                 # Configuration modules
├── config/
│   └── config.json             # Application settings
├── data/
│   ├── processed/              # BCBA study content (markdown)
│   └── raw/                    # Original PDF files
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── tests/                      # Test suite
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_repository.py

# Run with verbose output
pytest tests/ -v
```

### PDF Preprocessing

Process BCBA study materials into structured markdown for question generation:

```bash
# Process interactively (prompts before each file)
python -m src.preprocessing.run_preprocessing

# Process all without prompts
python -m src.preprocessing.run_preprocessing -y

# Dry run to see what would be processed
python -m src.preprocessing.run_preprocessing --dry-run

# Force reprocess all
python -m src.preprocessing.run_preprocessing --force -y
```

**Output structure:**
```
data/processed/
├── core/           # task_list.md, handbook.md, tco.md
├── ethics/         # ethics_code.md
├── supervision/    # curriculum.md
├── reference/      # glossary.md, key_terms.md
└── 00_index.md
```

The pipeline automatically filters BCBA-relevant materials and skips non-exam content (BCaBA, RBT, etc.). See [docs/preprocessing_guide.md](docs/preprocessing_guide.md) for the full guide.

### Question Pool Seeding

Seed the question pool with initial questions before launching:

```bash
# Generate 250 questions distributed by BCBA exam weights
python -m src.scripts.seed_questions --count 250

# Generate for specific content area only
python -m src.scripts.seed_questions --area "Ethics" --count 50

# Preview plan without generating (shows cost estimate)
python -m src.scripts.seed_questions --dry-run

# Fill gaps to reach target count (resumes from existing)
python -m src.scripts.seed_questions --resume --count 300
```

**Cost estimate:** ~$4.50 for 250 questions (Sonnet for generation + Haiku for deduplication)

### Database CLI

Inspect and manage the question pool directly from the command line:

```bash
# Show pool statistics by content area
python -m src.main --db-stats

# List recent questions (default 20)
python -m src.main --db-list
python -m src.main --db-list --limit 50

# Show full details of a specific question
python -m src.main --db-show 42

# Validate all questions have proper options
python -m src.main --db-validate

# Output as JSON for external tools (works with all --db-* commands)
python -m src.main --db-stats --json
python -m src.main --db-list --limit 10 --json
python -m src.main --db-validate --json
```

### Question Cleanup

Review and delete questions with invalid or missing options:

```bash
# Interactive review - see each invalid question and decide y/n to delete
python -m src.scripts.cleanup_questions

# Preview only - show all invalid questions without deleting
python -m src.scripts.cleanup_questions --dry-run

# Auto-delete all invalid questions without prompts
python -m src.scripts.cleanup_questions --auto
```

### Web Admin Server

Run the web admin interface independently:

```bash
# Run only the web server (no Telegram bot)
python -m src.main --web-only
```

### Question Pool Management

The bot automatically maintains the question pool using an active-user-based threshold:

- **Threshold**: Generates new questions when average unseen questions per active user < 20
- **Active user**: Anyone who answered a question in the last 7 days
- **Batch size**: 50 questions per generation cycle
- **Distribution**: Questions distributed by BCBA exam content area weights
- **Deduplication**: Uses Claude Haiku to prevent similar questions
- **Schedule**: Runs daily at 3 AM Pacific

Configuration in `config/config.json`:
```json
{
  "pool_management": {
    "threshold": 20,
    "batch_size": 50,
    "active_days": 7,
    "dedup_model": "claude-haiku-4-5"
  }
}
```

## BCBA Content Areas

Questions cover all areas of the BCBA 6th Edition Task List:
- **Section 1**: Foundations (Measurement, Experimental Design, Behavior-Change Procedures)
- **Section 2**: Applications (Ethics, Assessment, Intervention, Supervision)

## How It Works

1. **Scheduling**: APScheduler triggers quiz delivery at configured times per user timezone
2. **Question Selection**: Hybrid approach - mostly random, with 20% targeting weak areas
3. **Generation**: Claude loads relevant content and generates structured questions
4. **Delivery**: Questions sent via Telegram with inline answer buttons
5. **Feedback**: Immediate feedback with explanations after answering

## Documentation

| Document | Purpose |
|----------|---------|
| `IDEA.md` | Project concept |
| `DESIGN.md` | Technical specification |
| `PLAN.md` | Implementation plan |
| `CLAUDE.md` | Developer reference |

## License

MIT License - See LICENSE file for details.
