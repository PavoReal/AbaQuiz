"""
Database table definitions for AbaQuiz.

Uses SQLite with async support via aiosqlite.
"""

# SQL statements for creating tables

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    timezone TEXT DEFAULT 'America/Los_Angeles',
    is_subscribed BOOLEAN DEFAULT 1,
    daily_extra_count INTEGER DEFAULT 0,
    focus_preferences TEXT,  -- JSON array of content areas
    onboarding_complete BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_QUESTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    question_type TEXT NOT NULL,  -- 'multiple_choice' or 'true_false'
    options TEXT NOT NULL,  -- JSON object
    correct_answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    content_area TEXT NOT NULL,
    model TEXT,  -- AI model ID used to generate this question
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_USER_ANSWERS_TABLE = """
CREATE TABLE IF NOT EXISTS user_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
)
"""

CREATE_USER_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS user_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    total_points INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_answer_date DATE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

CREATE_ACHIEVEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    achievement_type TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, achievement_type)
)
"""

CREATE_BANNED_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS banned_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    banned_by INTEGER,
    reason TEXT,
    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_ADMIN_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS admin_settings (
    telegram_id INTEGER PRIMARY KEY,
    summary_enabled BOOLEAN DEFAULT 1,
    alerts_enabled BOOLEAN DEFAULT 1
)
"""

CREATE_API_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    model TEXT NOT NULL,
    content_area TEXT,
    estimated_cost REAL NOT NULL
)
"""

CREATE_SENT_QUESTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sent_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    message_id INTEGER,  -- Telegram message ID for reference
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_scheduled BOOLEAN DEFAULT 0,  -- True for daily questions, False for /quiz
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
)
"""

# Question reports table - user reports about problematic questions
CREATE_QUESTION_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS question_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    report_type TEXT NOT NULL,  -- 'incorrect_answer', 'confusing_wording', 'outdated_content', 'other'
    details TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'reviewed', 'resolved', 'dismissed'
    reviewed_by TEXT,
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

# Aggregate stats per question
CREATE_QUESTION_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS question_stats (
    question_id INTEGER PRIMARY KEY,
    times_shown INTEGER DEFAULT 0,
    times_answered INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    incorrect_count INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    option_a_count INTEGER DEFAULT 0,
    option_b_count INTEGER DEFAULT 0,
    option_c_count INTEGER DEFAULT 0,
    option_d_count INTEGER DEFAULT 0,
    option_true_count INTEGER DEFAULT 0,
    option_false_count INTEGER DEFAULT 0,
    report_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
)
"""

# Expert review decisions
CREATE_QUESTION_REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS question_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL,  -- 'approved', 'rejected', 'needs_edit'
    notes TEXT,
    review_data TEXT,  -- JSON for structured feedback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
)
"""

# Admins table - database-backed admin management
CREATE_ADMINS_TABLE = """
CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_super_admin BOOLEAN DEFAULT 0
)
"""

# Granular per-event notification settings
CREATE_ADMIN_NOTIFICATION_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS admin_notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_telegram_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    realtime_enabled BOOLEAN DEFAULT 1,
    summary_enabled BOOLEAN DEFAULT 1,
    UNIQUE(admin_telegram_id, event_type)
)
"""

# Event log for notification summaries and tracking
CREATE_NOTIFICATION_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT,
    sent_at TIMESTAMP,
    included_in_summary_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Broadcast queue - web admin writes, bot reads/processes
CREATE_BROADCAST_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS broadcast_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_text TEXT NOT NULL,
    message_format TEXT DEFAULT 'text',
    target_filter TEXT DEFAULT 'all',
    target_user_ids TEXT,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    processed_at TIMESTAMP,
    sent_count INTEGER DEFAULT 0,
    error_message TEXT
)
"""

# Generation queue - web admin writes, bot reads/processes
CREATE_GENERATION_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS generation_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_count INTEGER NOT NULL,
    skip_dedup BOOLEAN DEFAULT FALSE,
    distribution TEXT,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    generated_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_message TEXT
)
"""

# Generation progress - bot writes, web reads for real-time updates
CREATE_GENERATION_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS generation_progress (
    queue_id INTEGER PRIMARY KEY REFERENCES generation_queue(id),
    current_area TEXT,
    area_progress TEXT,
    total_generated INTEGER DEFAULT 0,
    total_duplicates INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_SYSTEM_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER
)
"""

# User tier stats - per-difficulty statistics
CREATE_USER_TIER_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS user_tier_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    difficulty_tier TEXT NOT NULL,
    questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0.0,
    avg_response_time REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, difficulty_tier)
)
"""

# =============================================================================
# GAMIFICATION SYSTEM v2 TABLES
# =============================================================================

# Content mastery tracking per content area per user
CREATE_CONTENT_MASTERY_TABLE = """
CREATE TABLE IF NOT EXISTS content_mastery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content_area TEXT NOT NULL,
    mastery_level INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    current_accuracy REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, content_area)
)
"""

# Weekly challenges - generated each week
CREATE_WEEKLY_CHALLENGES_TABLE = """
CREATE TABLE IF NOT EXISTS weekly_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    challenge_type TEXT NOT NULL,
    target_value INTEGER NOT NULL,
    target_area TEXT,
    bonus_points INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week_start, challenge_type, target_area)
)
"""

# User progress on weekly challenges
CREATE_USER_WEEKLY_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS user_weekly_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    challenge_id INTEGER NOT NULL,
    current_value INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT 0,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES weekly_challenges(id) ON DELETE CASCADE,
    UNIQUE(user_id, challenge_id)
)
"""

# Comeback bonuses for returning users
CREATE_COMEBACK_BONUSES_TABLE = """
CREATE TABLE IF NOT EXISTS comeback_bonuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    days_inactive INTEGER NOT NULL,
    bonus_type TEXT NOT NULL,
    bonus_value INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    claimed BOOLEAN DEFAULT 0,
    claimed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

# Seasonal events
CREATE_SEASONAL_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS seasonal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    focus_area TEXT,
    bonus_multiplier REAL DEFAULT 1.0,
    description TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# User progress in seasonal events
CREATE_USER_EVENT_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS user_event_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    points_earned INTEGER DEFAULT 0,
    badge_earned TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES seasonal_events(id) ON DELETE CASCADE,
    UNIQUE(user_id, event_id)
)
"""

# Leaderboard snapshots for different periods
CREATE_LEADERBOARD_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    user_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    score INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

# =============================================================================
# ANALYTICS TABLES
# =============================================================================

CREATE_DAILY_SYSTEM_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_system_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL UNIQUE,
    total_users INTEGER DEFAULT 0,
    subscribed_users INTEGER DEFAULT 0,
    active_users_7d INTEGER DEFAULT 0,
    active_users_1d INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    churned_users INTEGER DEFAULT 0,
    scheduled_sent INTEGER DEFAULT 0,
    scheduled_answered INTEGER DEFAULT 0,
    ondemand_answered INTEGER DEFAULT 0,
    bonus_answered INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    total_incorrect INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    response_count INTEGER DEFAULT 0,
    content_area_stats TEXT,
    tier_stats TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_HOURLY_ACTIVITY_TABLE = """
CREATE TABLE IF NOT EXISTS hourly_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_date DATE NOT NULL,
    hour_utc INTEGER NOT NULL,
    answers_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    tier_breakdown TEXT,
    UNIQUE(activity_date, hour_utc)
)
"""

CREATE_USER_DAILY_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS user_daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    user_timezone TEXT,
    scheduled_received INTEGER DEFAULT 0,
    scheduled_answered INTEGER DEFAULT 0,
    ondemand_answered INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    incorrect_count INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    content_area_breakdown TEXT,
    tier_breakdown TEXT,
    streak_value INTEGER DEFAULT 0,
    was_active BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, snapshot_date)
)
"""

CREATE_WEEKLY_RETENTION_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS weekly_retention_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL UNIQUE,
    active_users INTEGER DEFAULT 0,
    retained_from_last_week INTEGER DEFAULT 0,
    churned_this_week INTEGER DEFAULT 0,
    reactivated_this_week INTEGER DEFAULT 0,
    new_this_week INTEGER DEFAULT 0,
    retention_rate REAL DEFAULT 0.0,
    churn_rate REAL DEFAULT 0.0,
    tier_retention TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Indexes for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_answers_user_id ON user_answers(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_answers_question_id ON user_answers(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_answers_answered_at ON user_answers(answered_at)",
    "CREATE INDEX IF NOT EXISTS idx_questions_content_area ON questions(content_area)",
    "CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_banned_users_telegram_id ON banned_users(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_sent_questions_user_id ON sent_questions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sent_questions_question_id ON sent_questions(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_reports_question_id ON question_reports(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_reports_user_id ON question_reports(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_reports_status ON question_reports(status)",
    "CREATE INDEX IF NOT EXISTS idx_question_reviews_question_id ON question_reviews(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_admins_telegram_id ON admins(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_admin_notification_settings_admin ON admin_notification_settings(admin_telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_notification_log_event_type ON notification_log(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_notification_log_created_at ON notification_log(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_notification_log_summary ON notification_log(included_in_summary_at)",
    # Gamification v2 indexes
    "CREATE INDEX IF NOT EXISTS idx_content_mastery_user_id ON content_mastery(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_content_mastery_area ON content_mastery(content_area)",
    "CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week ON weekly_challenges(week_start)",
    "CREATE INDEX IF NOT EXISTS idx_user_weekly_progress_user_id ON user_weekly_progress(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_weekly_progress_challenge ON user_weekly_progress(challenge_id)",
    "CREATE INDEX IF NOT EXISTS idx_comeback_bonuses_user_id ON comeback_bonuses(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_comeback_bonuses_expires ON comeback_bonuses(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_seasonal_events_dates ON seasonal_events(start_date, end_date)",
    "CREATE INDEX IF NOT EXISTS idx_user_event_progress_user_id ON user_event_progress(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_event_progress_event ON user_event_progress(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_period ON leaderboard_snapshots(period_type, period_start)",
    "CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_user ON leaderboard_snapshots(user_id)",
]

# All table creation statements in order
ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_QUESTIONS_TABLE,
    CREATE_USER_ANSWERS_TABLE,
    CREATE_USER_STATS_TABLE,
    CREATE_ACHIEVEMENTS_TABLE,
    CREATE_BANNED_USERS_TABLE,
    CREATE_ADMIN_SETTINGS_TABLE,
    CREATE_API_USAGE_TABLE,
    CREATE_SENT_QUESTIONS_TABLE,
    CREATE_QUESTION_REPORTS_TABLE,
    CREATE_QUESTION_STATS_TABLE,
    CREATE_QUESTION_REVIEWS_TABLE,
    CREATE_ADMINS_TABLE,
    CREATE_ADMIN_NOTIFICATION_SETTINGS_TABLE,
    CREATE_NOTIFICATION_LOG_TABLE,
    CREATE_BROADCAST_QUEUE_TABLE,
    CREATE_GENERATION_QUEUE_TABLE,
    CREATE_GENERATION_PROGRESS_TABLE,
    # Gamification v2 tables
    CREATE_CONTENT_MASTERY_TABLE,
    CREATE_WEEKLY_CHALLENGES_TABLE,
    CREATE_USER_WEEKLY_PROGRESS_TABLE,
    CREATE_COMEBACK_BONUSES_TABLE,
    CREATE_SEASONAL_EVENTS_TABLE,
    CREATE_USER_EVENT_PROGRESS_TABLE,
    CREATE_LEADERBOARD_SNAPSHOTS_TABLE,
    CREATE_USER_TIER_STATS_TABLE,
    CREATE_SYSTEM_SETTINGS_TABLE,
    # Analytics tables (v7)
    CREATE_DAILY_SYSTEM_SNAPSHOTS_TABLE,
    CREATE_HOURLY_ACTIVITY_TABLE,
    CREATE_USER_DAILY_SNAPSHOTS_TABLE,
    CREATE_WEEKLY_RETENTION_SNAPSHOTS_TABLE,
]
