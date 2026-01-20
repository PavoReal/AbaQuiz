# AbaQuiz - Project Design Document

## Overview

AbaQuiz is a Telegram bot that helps users prepare for the BCBA (Board Certified Behavior Analyst) exam by delivering daily quiz questions on Applied Behavior Analysis (ABA). The bot uses Claude AI to generate high-quality questions based on the BCBA 5th Edition Task List.

---

## Core Features

### 1. Scheduled Daily Questions
- **Two questions per day**: Delivered at 8:00 AM and 8:00 PM
- **Timezone handling**: Auto-detect from Telegram user settings, default to Pacific Standard Time (PST)
- **Question formats**: Multiple choice (A/B/C/D) and True/False
- **Content coverage**: All BCBA 5th Edition Task List areas

### 2. On-Demand Practice
- Users can request extra practice questions via command
- Daily limit on extra questions (configurable, e.g., 5-10 per day)
- Option to request questions from specific content areas

### 3. Interactive Answering
- **Inline keyboard buttons** for answer selection (A, B, C, D or True/False)
- Instant feedback upon answering
- **Explanations**:
  - Brief confirmation on correct answers
  - Detailed explanation with rationale on incorrect answers

### 4. Gamification
- **Streaks**: Track consecutive days of answering questions
- **Points**: Earn points for correct answers (bonus for streaks)
- **Achievements/Badges**: Unlock for milestones:
  - First question answered
  - 7-day streak, 30-day streak, 100-day streak
  - 100 questions answered, 500 questions answered
  - Perfect week (all correct)
  - Content area mastery badges

### 5. Analytics & Progress Tracking
- Overall accuracy percentage
- Performance breakdown by BCBA Task List content area
- Strengths and weaknesses identification
- Historical progress charts (text-based in Telegram)
- Total questions answered, current streak, longest streak

---

## Technical Architecture

### Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Bot Framework | python-telegram-bot (v20+) |
| LLM Provider | Anthropic Claude API |
| Database | SQLite |
| Scheduling | APScheduler |
| Containerization | Docker |
| Hosting | Self-hosted |

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        AbaQuiz System                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Telegram   │◄──►│  Bot Handler │◄──►│   SQLite     │      │
│  │   Bot API    │    │   (python-   │    │   Database   │      │
│  └──────────────┘    │  telegram-bot)│    └──────────────┘      │
│                      └──────┬───────┘                           │
│                             │                                   │
│                             ▼                                   │
│                      ┌──────────────┐                           │
│                      │  Scheduler   │                           │
│                      │ (APScheduler)│                           │
│                      └──────┬───────┘                           │
│                             │                                   │
│                             ▼                                   │
│                      ┌──────────────┐    ┌──────────────┐      │
│                      │  Question    │◄──►│  Claude API  │      │
│                      │  Generator   │    │  (Anthropic) │      │
│                      └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
AbaQuiz/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py         # Telegram command/callback handlers
│   │   ├── admin_handlers.py   # Admin command handlers
│   │   ├── middleware.py       # dm_only, ban_check, rate_limit, admin
│   │   ├── notifications.py    # NotificationService class
│   │   ├── keyboards.py        # Inline keyboard builders
│   │   └── messages.py         # Message templates
│   ├── services/
│   │   ├── __init__.py
│   │   ├── question_generator.py   # Claude API integration
│   │   ├── scheduler.py            # APScheduler setup
│   │   ├── analytics.py            # Stats calculation
│   │   └── usage_tracker.py        # API usage tracking
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py           # SQLite table definitions
│   │   ├── repository.py       # Database operations
│   │   └── migrations.py       # Schema migrations
│   ├── gamification/
│   │   ├── __init__.py
│   │   ├── streaks.py          # Streak tracking
│   │   ├── points.py           # Point calculations
│   │   └── achievements.py     # Badge/achievement logic
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py    # PDF text extraction (pdfplumber/PyMuPDF)
│   │   ├── content_processor.py # Claude-based content cleanup
│   │   └── run_preprocessing.py # One-time preprocessing script
│   └── config/
│       ├── __init__.py
│       ├── settings.py         # Configuration management
│       └── constants.py        # App constants
├── data/
│   ├── raw/                    # Original PDF files (gitignored)
│   │   └── *.pdf
│   ├── processed/              # Pre-processed markdown content
│   │   ├── section_1_foundations.md
│   │   ├── section_2_applications.md
│   │   ├── ethics_code.md
│   │   └── ...
│   └── abaquiz.db              # SQLite database (generated)
├── tests/
│   ├── __init__.py
│   ├── test_handlers.py
│   ├── test_question_generator.py
│   └── test_gamification.py
├── config/
│   ├── config.json             # Bot settings (non-secrets)
│   └── .gitkeep
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example                # Environment variables template (secrets)
├── requirements.txt
├── IDEA.md
├── DESIGN.md
└── README.md
```

---

## Database Schema

### Tables

#### `users`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| telegram_id | INTEGER UNIQUE | Telegram user ID |
| username | TEXT | Telegram username |
| timezone | TEXT | User timezone (default: 'America/Los_Angeles') |
| is_subscribed | BOOLEAN | Receiving daily questions |
| daily_extra_count | INTEGER | Extra questions used today |
| focus_preferences | TEXT (JSON) | List of preferred content areas (for weighting) |
| onboarding_complete | BOOLEAN | Has completed onboarding flow |
| created_at | TIMESTAMP | Registration date |
| updated_at | TIMESTAMP | Last update |

#### `questions`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| content | TEXT | Full question text |
| question_type | TEXT | 'multiple_choice' or 'true_false' |
| options | TEXT (JSON) | Answer options |
| correct_answer | TEXT | Correct answer key |
| explanation | TEXT | Detailed explanation |
| content_area | TEXT | BCBA Task List area |
| created_at | TIMESTAMP | Generation date |

#### `user_answers`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER FK | Reference to users |
| question_id | INTEGER FK | Reference to questions |
| user_answer | TEXT | User's selected answer |
| is_correct | BOOLEAN | Whether answer was correct |
| answered_at | TIMESTAMP | When answered |

#### `user_stats`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER FK UNIQUE | Reference to users |
| total_points | INTEGER | Accumulated points |
| current_streak | INTEGER | Current daily streak |
| longest_streak | INTEGER | Best streak achieved |
| last_answer_date | DATE | Last day user answered |

#### `achievements`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER FK | Reference to users |
| achievement_type | TEXT | Achievement identifier |
| unlocked_at | TIMESTAMP | When earned |

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and subscribe to daily questions |
| `/stop` | Unsubscribe from daily questions |
| `/quiz` | Request an extra practice question (shows area menu) |
| `/quiz [area]` | Request question from specific content area (e.g., `/quiz ethics`) |
| `/stats` | View personal statistics and progress |
| `/streak` | View current and longest streak |
| `/achievements` | View unlocked badges |
| `/areas` | List available BCBA content areas |
| `/settings` | Manage timezone and preferences |
| `/help` | Show available commands |

---

## BCBA 5th Edition Task List Content Areas

Questions will cover all sections of the BCBA 5th Edition Task List:

1. **Section 1: Foundations**
   - Philosophical Underpinnings
   - Concepts and Principles
   - Measurement, Data Display, and Interpretation
   - Experimental Design

2. **Section 2: Applications**
   - Ethics
   - Behavior Assessment
   - Behavior-Change Procedures
   - Selecting and Implementing Interventions
   - Personnel Supervision and Management

---

## PDF Preprocessing Pipeline

### Overview

Reference materials (BCBA study guides, task lists, ethics codes) are provided as PDF files. These are pre-processed **once** into structured markdown files for efficient use during question generation.

### Pipeline Steps

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Raw PDFs   │────►│   Python    │────►│   Claude    │────►│  Markdown   │
│  (input)    │     │  Extraction │     │   Cleanup   │     │   Files     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                     pdfplumber/          Structure &         Organized by
                     PyMuPDF              format content      content area
```

### Step 1: Python Extraction

Using `pdfplumber` (preferred for tables) or `PyMuPDF` (faster for text):

```python
# src/preprocessing/pdf_extractor.py
import pdfplumber

def extract_pdf_text(pdf_path: str) -> list[dict]:
    """Extract text and tables from PDF, page by page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            pages.append({
                "page_num": i + 1,
                "text": page.extract_text(),
                "tables": page.extract_tables()
            })
    return pages
```

### Step 2: Claude Cleanup & Structuring

Send extracted content to Claude for one-time processing:

- Fix OCR/extraction errors
- Structure content into logical sections
- Convert tables to markdown format
- Add section headers and hierarchy
- Identify content areas for tagging

```python
# src/preprocessing/content_processor.py
CLEANUP_PROMPT = """
You are processing BCBA exam study material. Given the raw extracted text below:

1. Fix any extraction errors or garbled text
2. Structure the content with proper markdown headers (# ## ###)
3. Convert any tables to markdown table format
4. Preserve all factual content exactly
5. Tag each major section with its BCBA Task List content area

Raw content:
{raw_content}
"""
```

### Step 3: Output Structure

Processed content is saved as markdown files in `data/processed/`:

```
data/processed/
├── 00_index.md                    # Table of contents / overview
├── section_1_foundations/
│   ├── 1.1_philosophical_underpinnings.md
│   ├── 1.2_concepts_and_principles.md
│   ├── 1.3_measurement.md
│   └── 1.4_experimental_design.md
├── section_2_applications/
│   ├── 2.1_ethics.md
│   ├── 2.2_behavior_assessment.md
│   ├── 2.3_behavior_change_procedures.md
│   ├── 2.4_interventions.md
│   └── 2.5_supervision.md
└── supplementary/
    ├── ethics_code.md
    ├── glossary.md
    └── key_terms.md
```

### Running Preprocessing

```bash
# One-time preprocessing (run when new PDFs are added)
python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
```

### Cost Estimate

For a typical BCBA study guide (~200-300 pages):
- Extraction: Free (Python libraries)
- Claude cleanup: ~$5-15 one-time (depending on content volume)
- Total: Under $20 per document, run once

---

## Question Generation

### Prompt Strategy (Full Context)

The question generator uses Claude API with full context from pre-processed markdown files:

1. **System prompt** includes:
   - Role as BCBA exam question writer
   - Relevant content from `data/processed/` markdown files (loaded based on target area)
   - Question format specifications
   - Quality guidelines

2. **Content loading**:
   - Read relevant markdown file(s) for the target content area
   - Include full section content in the prompt context
   - For random questions, select a random content area first

3. **Generation request** specifies:
   - Target content area (or random selection)
   - Question type (multiple choice or true/false)
   - Difficulty considerations

4. **Response parsing**:
   - Structured JSON output from Claude
   - Validation of question format
   - Storage in database

### Example Generated Question

```json
{
  "question": "A behavior analyst is designing an intervention for a client who engages in self-injurious behavior maintained by automatic reinforcement. Which of the following would be the MOST appropriate first step?",
  "type": "multiple_choice",
  "options": {
    "A": "Implement differential reinforcement of other behavior (DRO)",
    "B": "Conduct a functional analysis to confirm the function",
    "C": "Apply response blocking immediately",
    "D": "Increase the magnitude of social reinforcement"
  },
  "correct_answer": "B",
  "explanation": "Before implementing any intervention, it is essential to confirm the function of the behavior through a functional analysis. While a functional behavior assessment may have suggested automatic reinforcement, a functional analysis provides experimental verification. This aligns with the ethical requirement to use assessment results to guide intervention selection (Ethics Code 2.13).",
  "content_area": "Behavior Assessment"
}
```

---

## Question Pool Management

Questions are **pre-generated** and stored in the database to reduce API latency and costs during delivery.

### Pool Strategy

| Aspect | Approach |
|--------|----------|
| Storage | Questions cached in `questions` table |
| Generation | Scheduled batch job (daily/weekly) |
| Per-area minimum | Configurable threshold (e.g., 20 questions) |
| Deduplication | Track which questions each user has seen in `user_answers` |

### Batch Generation Job

```
┌─────────────────────────────────────────────────────────┐
│  Scheduled Job: generate_question_pool (daily)          │
├─────────────────────────────────────────────────────────┤
│  1. For each content_area:                              │
│     - Count available unseen questions                  │
│     - If below threshold, generate batch via Claude API │
│  2. Validate generated questions (JSON schema check)    │
│  3. Store in questions table                            │
│  4. Log generation stats for admin summary              │
└─────────────────────────────────────────────────────────┘
```

### Question Type Distribution

- **80% Multiple Choice** (4 options: A, B, C, D)
- **20% True/False**

Configurable in `config.json`:
```json
{
  "question_generation": {
    "pool_threshold_per_area": 20,
    "batch_size": 10,
    "type_distribution": {
      "multiple_choice": 0.8,
      "true_false": 0.2
    }
  }
}
```

---

## Question Selection Algorithm

Questions are selected using a **hybrid approach**: mostly random across content areas, with periodic targeting of user weak areas.

### Selection Logic

```
┌─────────────────────────────────────────────────────────┐
│  select_question_for_user(user_id):                     │
├─────────────────────────────────────────────────────────┤
│  1. Get user's answer history and focus preferences     │
│  2. Roll random number (1-5)                            │
│     - If roll == 1: target weak area (lowest accuracy)  │
│     - Else: weighted random (favor focus preferences)   │
│  3. Select content_area based on step 2                 │
│  4. Query unseen questions for user in that area        │
│  5. Return random question from result set              │
└─────────────────────────────────────────────────────────┘
```

### Weak Area Targeting

- **Trigger ratio**: 1 in 5 questions (20%) - configurable
- **Calculation**: Content area with lowest accuracy (minimum 5 answers required)
- **Fallback**: If no weak area identified, use random selection

### Focus Preferences

During onboarding, users select content areas to emphasize:
- Selected areas receive **2x weight** in random selection
- Non-selected areas still included (1x weight)
- All areas remain in rotation to ensure comprehensive coverage

### Configuration

```json
{
  "question_selection": {
    "weak_area_ratio": 0.2,
    "min_answers_for_weak_calc": 5,
    "focus_preference_weight": 2.0
  }
}
```

---

## User Onboarding Flow

New users go through a **guided onboarding** after `/start`:

### Flow Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   /start     │────►│   Timezone   │────►│    Focus     │────►│  How It      │
│   Welcome    │     │   Selection  │     │    Areas     │     │  Works       │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                       │
                                                                       ▼
                                                               ┌──────────────┐
                                                               │ First Quiz   │
                                                               │ Question     │
                                                               └──────────────┘
```

### Step Details

#### 1. Welcome Message
```
Welcome to AbaQuiz! 🎓

I'll help you prepare for the BCBA exam with daily quiz questions
on Applied Behavior Analysis.

Let's set up your preferences...
```

#### 2. Timezone Selection
- Inline keyboard with common US timezones
- Option to type timezone manually
- Default: America/Los_Angeles (PST)

#### 3. Focus Area Selection
- Multi-select inline keyboard showing all BCBA content areas
- Users can select multiple areas to emphasize
- "All areas equally" option available
- Affects question weighting (see Selection Algorithm)

#### 4. How It Works
```
Here's how AbaQuiz works:

📅 Daily Questions: 8 AM and 8 PM (your time)
📝 On-demand: Use /quiz anytime for extra practice
📊 Track progress: Use /stats to see your performance
🔥 Build streaks: Answer at least one question daily!

Ready for your first question?
```

#### 5. First Question
- Immediately deliver first quiz question
- Starts the user's journey

---

## Streak Rules

### Day-Based Streaks

Streaks are calculated on a **calendar day basis** in the user's timezone:

| Scenario | Streak Result |
|----------|---------------|
| Answer morning AND evening question | Streak continues |
| Answer only morning question | Streak continues |
| Answer only evening question | Streak continues |
| Answer no questions that day | Streak resets to 0 |

### Streak Calculation

```python
def update_streak(user_id: int, answer_date: date) -> int:
    last_answer = get_last_answer_date(user_id)

    if last_answer is None:
        return 1  # First answer ever

    days_diff = (answer_date - last_answer).days

    if days_diff == 0:
        return current_streak  # Same day, no change
    elif days_diff == 1:
        return current_streak + 1  # Consecutive day
    else:
        return 1  # Streak broken, start fresh
```

---

## Question Answer Expiration

**Questions never expire.** Users can answer any previously delivered question at any time.

### Behavior

- Unanswered questions remain interactive (inline buttons stay active)
- Users can scroll back in chat history and answer old questions
- All answers count toward stats regardless of when answered
- Streak only considers the calendar day the answer was submitted (not when question was sent)

### Database Tracking

The `user_answers` table tracks `answered_at` timestamp, enabling:
- Analytics on response time (immediate vs delayed)
- Identification of users who batch-answer old questions

---

## Error Handling

### Claude API Failures

When question generation or delivery fails:

```
┌─────────────────────────────────────────────────────────┐
│  API Call Failure Handling                              │
├─────────────────────────────────────────────────────────┤
│  1. Retry up to 3 times with exponential backoff        │
│     - Attempt 1: immediate                              │
│     - Attempt 2: wait 5 seconds                         │
│     - Attempt 3: wait 15 seconds                        │
│  2. If all retries fail:                                │
│     - Log error with full context                       │
│     - Notify admins (if alerts enabled)                 │
│     - Skip this delivery slot for affected user         │
│     - User receives question at next scheduled time     │
│  3. Do NOT send error message to user                   │
└─────────────────────────────────────────────────────────┘
```

### Telegram Delivery Failures

| Error Type | Action |
|------------|--------|
| User blocked bot | Mark user as unsubscribed, stop deliveries |
| Rate limited | Queue and retry with backoff |
| Network error | Retry 3x, then skip and log |
| Invalid chat_id | Log error, notify admin |

### Admin Notifications

Failed operations trigger real-time alerts to admins (if enabled):
```
⚠️ Delivery Failed

User: @username (123456789)
Error: Claude API timeout after 3 retries
Time: 2026-01-13 08:00:05 PST
Action: Skipped morning delivery
```

---

## Gamification Details

### Points System
| Action | Points |
|--------|--------|
| Correct answer | 10 |
| Correct with active streak (7+ days) | 15 |
| Correct with active streak (30+ days) | 20 |
| First question of the day | +5 bonus |

### Achievements

| Achievement | Requirement | Badge |
|-------------|-------------|-------|
| First Steps | Answer first question | 🎯 |
| Week Warrior | 7-day streak | 🔥 |
| Monthly Master | 30-day streak | ⭐ |
| Century Club | 100 questions answered | 💯 |
| Knowledge Seeker | 500 questions answered | 📚 |
| Perfect Week | 14/14 correct in a week | 🏆 |
| Ethics Expert | 90%+ in Ethics area | ⚖️ |
| Assessment Ace | 90%+ in Assessment area | 📊 |
| (Additional per content area) | ... | ... |

---

## Configuration

### Python Dependencies

```txt
# requirements.txt
python-telegram-bot>=20.0
anthropic>=0.18.0
apscheduler>=3.10.0
pdfplumber>=0.10.0      # PDF extraction
python-dotenv>=1.0.0
aiosqlite>=0.19.0       # Async SQLite support
```

### Environment Variables

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Anthropic
ANTHROPIC_API_KEY=your_api_key_here

# Schedule (24-hour format)
MORNING_QUIZ_HOUR=8
EVENING_QUIZ_HOUR=20

# Limits
DAILY_EXTRA_QUESTION_LIMIT=5

# Database
DATABASE_PATH=./data/abaquiz.db

# Timezone
DEFAULT_TIMEZONE=America/Los_Angeles
```

---

## Deployment

### Docker Setup

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/

CMD ["python", "-m", "src.main"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  abaquiz:
    build: .
    container_name: abaquiz-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
```

---

## Future Considerations (Out of Scope for MVP)

- [ ] Web-based admin dashboard
- [ ] Question review/approval workflow
- [ ] Spaced repetition algorithm
- [ ] Multiple language support
- [ ] Premium tier with additional features
- [ ] Study groups/cohorts
- [ ] Mock exam mode

> **Note:** Leaderboards are intentionally excluded to keep individual progress private.

---

## Admin Features

### Access Model

**Open Registration** with admin tier:
- Anyone can `/start` and auto-subscribe to daily questions
- Admins have additional management commands
- Admins can ban/unban users
- Banned users receive quiz-themed rejection messages

### User Tiers

| Tier | Access |
|------|--------|
| `admin_users` | Full bot access + all admin commands |
| Regular users | Standard quiz features |
| Banned users | Rejected with ABA-themed message |

### Rejection Messages (for banned users)

```json
{
  "rejection_messages": [
    "Your access has been extinguished. No reinforcement for you! (ID: {user_id})",
    "This interaction is on extinction. Your ID ({user_id}) has been noted.",
    "Access denied. Consider this a punishment procedure. (ID: {user_id})",
    "You've been placed on a DRO schedule... of zero access. (ID: {user_id})"
  ]
}
```

---

### Middleware Architecture

```python
@dm_only_middleware           # 1. Only allow private chats
@ban_check_middleware         # 2. Check if user is banned
@rate_limit_middleware(...)   # 3. Enforce rate limits
async def handler(update, context):
    ...
```

| Middleware | Purpose |
|------------|---------|
| `dm_only_middleware` | Silently ignore group chats |
| `ban_check_middleware` | Block banned users with rejection message |
| `admin_middleware` | Restrict to admin users only |
| `rate_limit_middleware` | Enforce per-user rate limits |

---

### Admin Notification System

#### Real-time Alerts
- New user registrations
- Users hitting rate limits repeatedly
- Error/exception notifications

#### Daily Summary (sent at configurable time)

```
📊 Daily Summary - 01/13/2026

📈 Quiz Engagement (Last 24h):
• Questions sent: 156
• Answers received: 142 (91% response rate)
• Correct answers: 98 (69% accuracy)
• Active users: 47
• New subscribers: 3

💰 API Usage:
• Input tokens: 45,230
• Output tokens: 23,456
• Estimated cost: $0.42

🏆 Top Performers:
• @user1: 14/14 correct (100%)
• @user2: 13/14 correct (93%)

🔥 Streak Leaders:
• @user3: 45 day streak
• @user4: 32 day streak
```

#### Per-Admin Preferences

| Command | Description |
|---------|-------------|
| `/notify status` | Show current notification settings |
| `/notify summary on\|off` | Toggle daily summaries |
| `/notify alerts on\|off` | Toggle real-time alerts |

---

### Token Usage Tracking

Track API costs per question generation:

| Field | Description |
|-------|-------------|
| `input_tokens` | Tokens sent to Claude |
| `output_tokens` | Tokens received from Claude |
| `cache_creation_tokens` | Prompt cache write tokens |
| `cache_read_tokens` | Prompt cache hit tokens |
| `model` | Model used |
| `estimated_cost` | Calculated cost |

#### Admin Command

`/usage` - Shows rolling 24h stats:
- Total questions generated
- Token counts by type
- Estimated cost
- Per-content-area breakdown

---

### Rate Limiting

**Two-tier system:**

1. **Daily Extra Question Limit** (existing)
   - Limits on-demand `/quiz` requests
   - Configurable (default: 5/day)
   - Resets at midnight user's timezone

2. **Overall Rate Limit Middleware**
   - Prevents abuse/spam
   - Per-user request throttling
   - Protects against rapid-fire requests

```json
{
  "rate_limit": {
    "extra_questions_per_day": 5,
    "requests_per_minute": 10
  }
}
```

---

### Admin Commands

#### User Management

| Command | Description |
|---------|-------------|
| `/users` | List all registered users |
| `/users active` | List users active in last 7 days |
| `/ban <user_id\|@username>` | Ban a user |
| `/unban <user_id\|@username>` | Unban a user |
| `/delete <user_id\|@username>` | Delete user and all their data |

#### User Data Access

| Command | Description |
|---------|-------------|
| `/history <user_id\|@username>` | View user's progress summary |
| `/stats <user_id\|@username>` | View user's detailed statistics |
| `/reset streak <user_id\|@username>` | Reset user's streak |
| `/grant achievement <user> <badge>` | Grant achievement to user |
| `/adjust points <user> <amount>` | Add/subtract points |

#### Broadcast & System

| Command | Description |
|---------|-------------|
| `/broadcast <message>` | Send message to all subscribers |
| `/usage` | View 24h API usage and costs |
| `/notify` | Manage notification preferences |
| `/admin` | List all admin commands |

---

### Telegram Command Menus

Different command autocomplete for different user types:

**Regular Users:**
```
/start - Subscribe to daily questions
/stop - Unsubscribe
/quiz - Get a practice question
/stats - View your statistics
/streak - View your streak
/achievements - View your badges
/areas - List content areas
/settings - Manage preferences
/help - Show help
```

**Admins (additional):**
```
/users - User management
/ban - Ban a user
/unban - Unban a user
/broadcast - Send broadcast
/usage - API usage stats
/notify - Notification settings
/history - View user progress
/admin - Admin help
```

---

### Database Additions for Admin Features

#### `banned_users`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| telegram_id | INTEGER UNIQUE | Banned user's Telegram ID |
| banned_by | INTEGER | Admin who banned |
| reason | TEXT | Ban reason (optional) |
| banned_at | TIMESTAMP | When banned |

#### `admin_settings`
| Column | Type | Description |
|--------|------|-------------|
| telegram_id | INTEGER PRIMARY KEY | Admin's Telegram ID |
| summary_enabled | BOOLEAN | Receive daily summaries |
| alerts_enabled | BOOLEAN | Receive real-time alerts |

#### `api_usage`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| timestamp | TIMESTAMP | When API was called |
| input_tokens | INTEGER | Tokens sent |
| output_tokens | INTEGER | Tokens received |
| cache_write_tokens | INTEGER | Cache write tokens |
| cache_read_tokens | INTEGER | Cache read tokens |
| model | TEXT | Model used |
| content_area | TEXT | Question content area |
| estimated_cost | REAL | Calculated cost |

---

### Configuration System

**Hybrid approach:** Secrets in `.env`, settings in `config.json`

#### .env (secrets)
```env
TELEGRAM_BOT_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
```

#### config/config.json (settings)
```json
{
  "bot": {
    "default_timezone": "America/Los_Angeles",
    "morning_quiz_hour": 8,
    "evening_quiz_hour": 20
  },
  "admin": {
    "admin_users": [123456789],
    "summary_time": "09:00",
    "default_summary_enabled": true,
    "default_alerts_enabled": true
  },
  "rate_limit": {
    "extra_questions_per_day": 5,
    "requests_per_minute": 10
  },
  "rejection_messages": [
    "Your access has been extinguished. No reinforcement for you! (ID: {user_id})"
  ],
  "pricing": {
    "anthropic": {
      "claude-sonnet-4-5": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "cache_write_per_million": 3.75,
        "cache_read_per_million": 0.30
      },
      "claude-haiku-4-5": {
        "input_per_million": 1.00,
        "output_per_million": 5.00
      }
    }
  }
}
```

#### Environment Variable Substitution

```json
{
  "api_key": "${ANTHROPIC_API_KEY}"
}
```

---

### Logging

#### Message Format
```
[user_id] >> /quiz ethics
[user_id] << [Question about ethics code 2.01...]
```

#### Log Events
- User registrations
- Ban/unban actions
- Rate limit hits
- API errors
- Admin command usage

---

### Scheduled Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| `morning_quiz` | Daily 8:00 AM (per timezone) | Send morning question |
| `evening_quiz` | Daily 8:00 PM (per timezone) | Send evening question |
| `daily_summary` | Daily (configurable) | Send admin summaries |
| `reset_daily_limits` | Midnight | Reset extra question counts |
| `streak_check` | Daily | Update streak statuses |

---

### Directory Structure Updates

```
src/
├── bot/
│   ├── middleware.py       # dm_only, ban_check, rate_limit, admin
│   ├── notifications.py    # NotificationService class
│   └── admin_handlers.py   # Admin command handlers
├── services/
│   └── usage_tracker.py    # API usage tracking
└── ...

config/
├── config.json             # Bot settings
└── .gitkeep
```

---

## Success Metrics

1. **User Engagement**: Daily active users, answer rate
2. **Retention**: Streak maintenance, 7-day/30-day retention
3. **Learning Outcomes**: Accuracy improvement over time
4. **Growth**: New subscriptions per week

---

*Document Version: 1.2*
*Last Updated: 2026-01-16*
