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
]
