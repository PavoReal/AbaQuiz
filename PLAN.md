# AbaQuiz - Implementation Plan

This document outlines the phased implementation plan for building AbaQuiz. Each phase builds on the previous one, allowing for incremental testing and deployment.

---

## Phase Overview

| Phase | Name | Priority | Dependencies | Status |
|-------|------|----------|--------------|--------|
| 1 | Foundation | Critical | None | COMPLETE |
| 2 | Database Layer | Critical | Phase 1 | COMPLETE |
| 3 | Core Bot Framework | Critical | Phase 2 | COMPLETE |
| 4 | PDF Preprocessing | High | Phase 1 | DEFERRED |
| 5 | Question Generation | High | Phase 2, 4 | COMPLETE |
| 6 | User Commands | High | Phase 3, 5 | COMPLETE |
| 7 | Gamification | Medium | Phase 6 | COMPLETE (integrated into Phase 6) |
| 8 | Admin Features | Medium | Phase 6 | COMPLETE |
| 9 | Scheduling | High | Phase 5, 6 | COMPLETE |
| 10 | Testing & Deployment | Critical | All | COMPLETE |

---

## Phase 1: Foundation

**Goal:** Set up project structure, configuration, and development environment.

### Tasks

- [ ] 1.1 Create directory structure per DESIGN.md
- [ ] 1.2 Set up `requirements.txt` with all dependencies
- [ ] 1.3 Create `.env.example` with all required environment variables
- [ ] 1.4 Implement `src/config/settings.py` - configuration loader
  - Load from `.env` (secrets)
  - Load from `config/config.json` (settings)
  - Support `${ENV_VAR}` substitution in JSON
- [ ] 1.5 Create `config/config.json` with default settings
- [ ] 1.6 Implement `src/config/constants.py` - application constants
  - BCBA content area names
  - Achievement types
  - Default values
- [ ] 1.7 Set up logging configuration

### Deliverables

- Runnable project skeleton
- Configuration system working
- Logging functional

---

## Phase 2: Database Layer

**Goal:** Implement SQLite database with async support.

### Tasks

- [ ] 2.1 Implement `src/database/models.py` - table definitions
  - `users` table (with focus_preferences, onboarding_complete)
  - `questions` table
  - `user_answers` table
  - `user_stats` table
  - `achievements` table
  - `banned_users` table
  - `admin_settings` table
  - `api_usage` table
- [ ] 2.2 Implement `src/database/migrations.py` - schema creation/migration
- [ ] 2.3 Implement `src/database/repository.py` - data access layer
  - User CRUD operations
  - Question CRUD operations
  - Answer recording
  - Stats updates
  - Achievement management
  - Ban management
- [ ] 2.4 Write unit tests for repository functions

### Deliverables

- Database initializes correctly
- All CRUD operations working
- Tests passing

---

## Phase 3: Core Bot Framework

**Goal:** Set up Telegram bot with middleware stack.

### Tasks

- [ ] 3.1 Implement `src/main.py` - application entry point
  - Initialize bot application
  - Register handlers
  - Start polling/webhook
- [ ] 3.2 Implement `src/bot/middleware.py`
  - `dm_only_middleware` - ignore group chats
  - `ban_check_middleware` - block banned users
  - `rate_limit_middleware` - throttle requests
  - `admin_middleware` - restrict admin commands
- [ ] 3.3 Implement `src/bot/keyboards.py` - inline keyboard builders
  - Answer buttons (A, B, C, D / True, False)
  - Content area selection menu
  - Timezone selection menu
  - Settings menu
- [ ] 3.4 Implement `src/bot/messages.py` - message templates
  - Welcome messages
  - Question format
  - Feedback messages (correct/incorrect)
  - Stats display format
  - Rejection messages (banned users)
- [ ] 3.5 Test bot connects and responds to basic commands

### Deliverables

- Bot runs and connects to Telegram
- Middleware stack functional
- Basic /start responds

---

## Phase 4: PDF Preprocessing

**Goal:** Build one-time pipeline to process BCBA study materials.

### Tasks

- [ ] 4.1 Implement `src/preprocessing/pdf_extractor.py`
  - Extract text page by page (pdfplumber)
  - Extract tables
  - Handle multi-column layouts
- [ ] 4.2 Implement `src/preprocessing/content_processor.py`
  - Claude API integration for cleanup
  - Prompt for structuring content
  - Markdown output formatting
  - Content area tagging
- [ ] 4.3 Implement `src/preprocessing/run_preprocessing.py`
  - CLI interface with argparse
  - Process all PDFs in input directory
  - Save to organized output structure
  - Progress reporting
- [ ] 4.4 Create `data/processed/` directory structure
- [ ] 4.5 Run preprocessing on available BCBA materials

### Deliverables

- Preprocessing script runnable
- Markdown files generated per content area
- Content ready for question generation

---

## Phase 5: Question Generation

**Goal:** Implement Claude-powered question generation with pool management.

### Tasks

- [ ] 5.1 Implement `src/services/question_generator.py`
  - Load content from processed markdown files
  - Build system prompt for question writing
  - Generate single question via Claude API
  - Parse and validate JSON response
  - Handle 80/20 MC/TF distribution
- [ ] 5.2 Implement question pool management
  - Check pool levels per content area
  - Batch generation function
  - Store questions in database
- [ ] 5.3 Implement `src/services/usage_tracker.py`
  - Track token counts per API call
  - Calculate estimated costs
  - Store in `api_usage` table
- [ ] 5.4 Implement question selection algorithm
  - Hybrid random/weak-area targeting
  - Focus preference weighting
  - Ensure user doesn't see same question twice
- [ ] 5.5 Write tests for question generation and selection

### Deliverables

- Questions generate correctly
- Pool management working
- Selection algorithm implemented
- Token usage tracked

---

## Phase 6: User Commands

**Goal:** Implement all user-facing bot commands.

### Tasks

- [ ] 6.1 Implement `src/bot/handlers.py` - `/start` command
  - New user registration
  - Guided onboarding flow (timezone, focus areas, how-it-works)
  - First question delivery
  - Returning user handling
- [ ] 6.2 Implement `/stop` command
  - Unsubscribe user from daily questions
  - Confirmation message
- [ ] 6.3 Implement `/quiz` command
  - Show content area menu (no argument)
  - Accept area argument (e.g., `/quiz ethics`)
  - Check daily extra question limit
  - Select and send question
- [ ] 6.4 Implement answer callback handler
  - Process inline button clicks
  - Check if correct
  - Show feedback with explanation
  - Update stats and streaks
  - Check for new achievements
- [ ] 6.5 Implement `/stats` command
  - Overall accuracy
  - Per-area breakdown
  - Questions answered count
  - Current/longest streak
- [ ] 6.6 Implement `/streak` command
  - Current streak display
  - Longest streak
  - Visual streak indicator
- [ ] 6.7 Implement `/achievements` command
  - List unlocked badges
  - Show progress toward next achievements
- [ ] 6.8 Implement `/areas` command
  - List all BCBA content areas
  - Show user's accuracy per area
- [ ] 6.9 Implement `/settings` command
  - Timezone change
  - Focus area update
  - Subscription toggle
- [ ] 6.10 Implement `/help` command
  - List all available commands
  - Brief descriptions

### Deliverables

- All user commands functional
- Onboarding flow complete
- Question answering works end-to-end

---

## Phase 7: Gamification

**Goal:** Implement points, streaks, and achievements system.

### Tasks

- [ ] 7.1 Implement `src/gamification/streaks.py`
  - Day-based streak calculation (user timezone)
  - Streak update on answer
  - Streak reset detection
- [ ] 7.2 Implement `src/gamification/points.py`
  - Base points for correct answer
  - Streak bonuses (7+, 30+ days)
  - First question of day bonus
  - Point calculation function
- [ ] 7.3 Implement `src/gamification/achievements.py`
  - Achievement definitions (from DESIGN.md)
  - Check conditions on each answer
  - Award new achievements
  - Notification message on unlock
- [ ] 7.4 Implement `src/services/analytics.py`
  - Calculate user stats
  - Per-area accuracy
  - Identify weak areas
  - Progress over time data

### Deliverables

- Points awarded correctly
- Streaks track properly
- Achievements unlock
- Analytics calculate correctly

---

## Phase 8: Admin Features

**Goal:** Implement admin commands, notifications, and user management.

**Status:** COMPLETE

### Tasks

- [x] 8.1 Implement `src/bot/admin_handlers.py` - user management
  - `/users` - list users
  - `/ban` - ban user
  - `/unban` - unban user
  - `/delete` - delete user data (deferred - not critical for MVP)
- [ ] 8.2 Implement user data access commands (deferred - not critical for MVP)
  - `/history <user>` - view user progress
  - `/stats <user>` - view user stats
  - `/reset streak <user>` - reset streak
  - `/grant achievement` - grant badge
  - `/adjust points` - modify points
- [x] 8.3 Implement `/broadcast` command
  - Send message to all subscribers
  - Progress indicator
  - Failure handling
- [x] 8.4 Implement `/usage` command
  - 24h API usage stats
  - Token counts
  - Cost estimates
  - Per-area breakdown
- [ ] 8.5 Implement `src/bot/notifications.py` - NotificationService (deferred - can be added later)
  - Real-time alerts (new users, errors, rate limits)
  - Daily summary generation
  - Per-admin preferences
- [x] 8.6 Implement `/notify` command
  - View notification settings
  - Toggle summaries
  - Toggle alerts
- [x] 8.7 Implement `/admin` command
  - List all admin commands

### Deliverables

- [x] Core admin commands working
- [ ] Advanced notifications (deferred)
- [x] Usage tracking visible

---

## Phase 9: Scheduling

**Goal:** Set up APScheduler for automated tasks.

**Status:** COMPLETE

### Tasks

- [x] 9.1 Implement `src/services/scheduler.py`
  - Initialize APScheduler with AsyncIOScheduler
  - Job store configuration
- [x] 9.2 Implement morning/evening quiz jobs
  - Per-user timezone handling
  - Question selection and delivery
  - Error handling with retry
- [x] 9.3 Implement pool generation job
  - Check pool levels
  - Batch generate as needed
  - Run daily/weekly
- [ ] 9.4 Implement daily summary job (deferred - can be added later)
  - Compile stats
  - Send to admins with summaries enabled
- [x] 9.5 Implement daily limit reset job
  - Reset `daily_extra_count` at midnight
  - Per-user timezone
- [ ] 9.6 Implement streak check job (streaks are updated on answer, not needed as job)
  - Identify broken streaks
  - Update stats accordingly

### Deliverables

- [x] Scheduled questions deliver on time
- [x] Pool maintains healthy levels
- [x] Daily tasks run reliably

---

## Phase 10: Testing & Deployment

**Goal:** Comprehensive testing and production deployment.

**Status:** COMPLETE

### Tasks

- [x] 10.1 Write unit tests
  - Repository functions
  - Question generator
  - Gamification logic (integrated into repository tests)
  - Selection algorithm
- [ ] 10.2 Write integration tests (can be added later)
  - Bot handler flows
  - Onboarding flow
  - Question answering flow
- [x] 10.3 Create `docker/Dockerfile`
- [x] 10.4 Create `docker/docker-compose.yml`
- [x] 10.5 Set up volume mounts for data persistence
- [ ] 10.6 Test Docker deployment locally (requires Docker runtime)
- [ ] 10.7 Document deployment process in README.md (can be added later)
- [ ] 10.8 Production deployment (user's responsibility)

### Deliverables

- [x] Basic tests created
- [x] Docker configuration ready
- [ ] Bot running in production (user's responsibility)

---

## Implementation Order (Recommended)

For a solo developer, this order allows functional milestones:

```
Week 1-2: Phases 1-3 (Foundation + Database + Bot Framework)
          → Milestone: Bot responds to commands

Week 3:   Phase 4 (PDF Preprocessing)
          → Milestone: Content ready for questions

Week 4:   Phase 5 (Question Generation)
          → Milestone: Can generate and store questions

Week 5:   Phase 6 (User Commands)
          → Milestone: Full user experience working

Week 6:   Phases 7-8 (Gamification + Admin)
          → Milestone: Points, streaks, admin controls

Week 7:   Phase 9 (Scheduling)
          → Milestone: Automated daily delivery

Week 8:   Phase 10 (Testing + Deployment)
          → Milestone: Production ready
```

---

## MVP Scope

For fastest time-to-users, implement in this order:

### MVP-1: Core Quiz (Phases 1-6)
- Users can `/start`, receive questions, answer them
- Basic stats tracking
- No gamification, no scheduling

### MVP-2: Automation (Phase 9)
- Scheduled daily questions
- Pool management

### MVP-3: Full Features (Phases 7-8)
- Points and achievements
- Admin features

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Claude API costs | Pre-generate question pool, monitor usage |
| Telegram rate limits | Implement proper backoff, batch broadcasts |
| PDF extraction quality | Manual review of processed content |
| User timezone complexity | Use pytz, test DST transitions |
| Database growth | Implement data retention policies post-MVP |

---

## Dependencies Between Phases

```
Phase 1 (Foundation)
    │
    ├──► Phase 2 (Database)
    │        │
    │        ├──► Phase 3 (Bot Framework)
    │        │        │
    │        │        ├──► Phase 6 (User Commands)
    │        │        │        │
    │        │        │        ├──► Phase 7 (Gamification)
    │        │        │        │
    │        │        │        ├──► Phase 8 (Admin Features)
    │        │        │        │
    │        │        │        └──► Phase 9 (Scheduling)
    │        │        │
    │        │        └──► Phase 8 (Admin Features)
    │        │
    │        └──► Phase 5 (Question Generation)
    │                 │
    │                 └──► Phase 6 (User Commands)
    │
    └──► Phase 4 (PDF Preprocessing)
             │
             └──► Phase 5 (Question Generation)

Phase 10 (Testing & Deployment) ← All phases
```

---

*Document Version: 1.0*
*Created: 2026-01-16*
