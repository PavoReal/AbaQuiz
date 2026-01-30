"""
Database migrations for AbaQuiz.

Handles schema creation and updates.
"""

import aiosqlite

from src.config.logging import get_logger
from src.database.models import (
    ALL_TABLES,
    CREATE_ADMINS_TABLE,
    CREATE_ADMIN_NOTIFICATION_SETTINGS_TABLE,
    CREATE_BROADCAST_QUEUE_TABLE,
    CREATE_COMEBACK_BONUSES_TABLE,
    CREATE_CONTENT_MASTERY_TABLE,
    CREATE_GENERATION_PROGRESS_TABLE,
    CREATE_GENERATION_QUEUE_TABLE,
    CREATE_INDEXES,
    CREATE_LEADERBOARD_SNAPSHOTS_TABLE,
    CREATE_NOTIFICATION_LOG_TABLE,
    CREATE_QUESTION_REPORTS_TABLE,
    CREATE_QUESTION_STATS_TABLE,
    CREATE_QUESTION_REVIEWS_TABLE,
    CREATE_SEASONAL_EVENTS_TABLE,
    CREATE_USER_EVENT_PROGRESS_TABLE,
    CREATE_USER_WEEKLY_PROGRESS_TABLE,
    CREATE_WEEKLY_CHALLENGES_TABLE,
)

logger = get_logger(__name__)


async def initialize_database(db_path: str) -> None:
    """
    Initialize the database with all tables and indexes.

    Args:
        db_path: Path to the SQLite database file
    """
    logger.info(f"Initializing database at {db_path}")

    async with aiosqlite.connect(db_path) as db:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")

        # Create all tables
        for table_sql in ALL_TABLES:
            await db.execute(table_sql)

        # Create indexes
        for index_sql in CREATE_INDEXES:
            await db.execute(index_sql)

        await db.commit()

    logger.info("Database initialized successfully")


async def get_schema_version(db: aiosqlite.Connection) -> int:
    """Get current schema version."""
    try:
        async with db.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


async def set_schema_version(db: aiosqlite.Connection, version: int) -> None:
    """Set schema version."""
    await db.execute(f"PRAGMA user_version = {version}")


async def run_migrations(db_path: str) -> None:
    """
    Run any pending migrations.

    Args:
        db_path: Path to the SQLite database file
    """
    async with aiosqlite.connect(db_path) as db:
        current_version = await get_schema_version(db)
        logger.info(f"Current schema version: {current_version}")

        # Migration v1: Add model column to questions table
        if current_version < 1:
            await migrate_to_v1(db)
            await set_schema_version(db, 1)

        # Migration v2: Add question validation tables and columns
        if current_version < 2:
            await migrate_to_v2(db)
            await set_schema_version(db, 2)

        # Migration v3: Add admins table and is_bonus column to sent_questions
        if current_version < 3:
            await migrate_to_v3(db)
            await set_schema_version(db, 3)

        # Migration v4: Add notification system tables
        if current_version < 4:
            await migrate_to_v4(db)
            await set_schema_version(db, 4)

        # Migration v5: Add IPC queue tables for web admin
        if current_version < 5:
            await migrate_to_v5(db)
            await set_schema_version(db, 5)

        # Migration v6: Add difficulty_min column to users table
        if current_version < 6:
            await migrate_to_v6(db)
            await set_schema_version(db, 6)

        # Migration v7: Gamification system overhaul
        if current_version < 7:
            await migrate_to_v7(db)
            await set_schema_version(db, 7)

        await db.commit()


async def migrate_to_v1(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 1.

    Adds 'model' column to questions table to track which AI model
    generated each question.
    """
    logger.info("Running migration v1: Adding model column to questions table")

    # Check if column already exists (in case of partial migration)
    async with db.execute("PRAGMA table_info(questions)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

    if "model" not in column_names:
        await db.execute("ALTER TABLE questions ADD COLUMN model TEXT")
        logger.info("Added 'model' column to questions table")
    else:
        logger.info("Column 'model' already exists in questions table")


async def migrate_to_v2(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 2.

    Adds question validation features:
    - New columns: questions.source_citation, questions.review_status, questions.difficulty
    - New columns: user_answers.response_time_ms
    - New tables: question_reports, question_stats, question_reviews
    - Backfills question_stats from existing user_answers data
    """
    logger.info("Running migration v2: Adding question validation features")

    # Get existing columns for questions table
    async with db.execute("PRAGMA table_info(questions)") as cursor:
        columns = await cursor.fetchall()
        question_columns = [col[1] for col in columns]

    # Add new columns to questions table
    if "source_citation" not in question_columns:
        await db.execute("ALTER TABLE questions ADD COLUMN source_citation TEXT")
        logger.info("Added 'source_citation' column to questions table")

    if "review_status" not in question_columns:
        await db.execute(
            "ALTER TABLE questions ADD COLUMN review_status TEXT DEFAULT 'unreviewed'"
        )
        logger.info("Added 'review_status' column to questions table")

    if "difficulty" not in question_columns:
        await db.execute("ALTER TABLE questions ADD COLUMN difficulty INTEGER")
        logger.info("Added 'difficulty' column to questions table")

    # Get existing columns for user_answers table
    async with db.execute("PRAGMA table_info(user_answers)") as cursor:
        columns = await cursor.fetchall()
        answer_columns = [col[1] for col in columns]

    # Add response_time_ms to user_answers
    if "response_time_ms" not in answer_columns:
        await db.execute("ALTER TABLE user_answers ADD COLUMN response_time_ms INTEGER")
        logger.info("Added 'response_time_ms' column to user_answers table")

    # Create new tables (IF NOT EXISTS is safe for re-runs)
    await db.execute(CREATE_QUESTION_REPORTS_TABLE)
    logger.info("Created question_reports table")

    await db.execute(CREATE_QUESTION_STATS_TABLE)
    logger.info("Created question_stats table")

    await db.execute(CREATE_QUESTION_REVIEWS_TABLE)
    logger.info("Created question_reviews table")

    # Create new indexes
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_question_reports_question_id ON question_reports(question_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_question_reports_user_id ON question_reports(user_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_question_reports_status ON question_reports(status)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_question_reviews_question_id ON question_reviews(question_id)"
    )
    logger.info("Created indexes for new tables")

    # Backfill question_stats from existing user_answers data
    await db.execute("""
        INSERT OR IGNORE INTO question_stats (question_id, times_answered, correct_count, incorrect_count)
        SELECT
            question_id,
            COUNT(*) as times_answered,
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
            SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as incorrect_count
        FROM user_answers
        GROUP BY question_id
    """)

    # Backfill option counts from existing user_answers
    await db.execute("""
        UPDATE question_stats SET
            option_a_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'A'
            ),
            option_b_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'B'
            ),
            option_c_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'C'
            ),
            option_d_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'D'
            ),
            option_true_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'TRUE'
            ),
            option_false_count = (
                SELECT COUNT(*) FROM user_answers
                WHERE user_answers.question_id = question_stats.question_id
                AND UPPER(user_answer) = 'FALSE'
            ),
            last_updated = CURRENT_TIMESTAMP
    """)

    async with db.execute("SELECT COUNT(*) FROM question_stats") as cursor:
        row = await cursor.fetchone()
        backfill_count = row[0] if row else 0

    logger.info(f"Backfilled question_stats for {backfill_count} questions")

    # Also populate times_shown from sent_questions
    await db.execute("""
        UPDATE question_stats SET
            times_shown = (
                SELECT COUNT(*) FROM sent_questions
                WHERE sent_questions.question_id = question_stats.question_id
            )
    """)
    logger.info("Updated times_shown from sent_questions")

    logger.info("Migration v2 complete")


async def migrate_to_v3(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 3.

    Adds admin management features:
    - New table: admins (database-backed admin management)
    - New column: sent_questions.is_bonus (track bonus questions)
    """
    logger.info("Running migration v3: Adding admin management features")

    # Create admins table
    await db.execute(CREATE_ADMINS_TABLE)
    logger.info("Created admins table")

    # Create index for admins
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_admins_telegram_id ON admins(telegram_id)"
    )
    logger.info("Created index for admins table")

    # Add is_bonus column to sent_questions
    async with db.execute("PRAGMA table_info(sent_questions)") as cursor:
        columns = await cursor.fetchall()
        sent_columns = [col[1] for col in columns]

    if "is_bonus" not in sent_columns:
        await db.execute(
            "ALTER TABLE sent_questions ADD COLUMN is_bonus BOOLEAN DEFAULT 0"
        )
        logger.info("Added 'is_bonus' column to sent_questions table")
    else:
        logger.info("Column 'is_bonus' already exists in sent_questions table")

    logger.info("Migration v3 complete")


async def migrate_to_v4(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 4.

    Adds admin notification system:
    - New table: admin_notification_settings (per-event granular controls)
    - New table: notification_log (event log for summaries and tracking)
    """
    logger.info("Running migration v4: Adding notification system tables")

    # Create admin_notification_settings table
    await db.execute(CREATE_ADMIN_NOTIFICATION_SETTINGS_TABLE)
    logger.info("Created admin_notification_settings table")

    # Create notification_log table
    await db.execute(CREATE_NOTIFICATION_LOG_TABLE)
    logger.info("Created notification_log table")

    # Create indexes for new tables
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_notification_settings_admin "
        "ON admin_notification_settings(admin_telegram_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_log_event_type "
        "ON notification_log(event_type)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_log_created_at "
        "ON notification_log(created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_log_summary "
        "ON notification_log(included_in_summary_at)"
    )
    logger.info("Created indexes for notification tables")

    logger.info("Migration v4 complete")


async def migrate_to_v5(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 5.

    Adds IPC queue tables for web admin communication:
    - New table: broadcast_queue (web admin writes, bot processes)
    - New table: generation_queue (web admin writes, bot processes)
    - New table: generation_progress (bot writes, web admin reads)
    """
    logger.info("Running migration v5: Adding IPC queue tables for web admin")

    # Create broadcast_queue table
    await db.execute(CREATE_BROADCAST_QUEUE_TABLE)
    logger.info("Created broadcast_queue table")

    # Create generation_queue table
    await db.execute(CREATE_GENERATION_QUEUE_TABLE)
    logger.info("Created generation_queue table")

    # Create generation_progress table
    await db.execute(CREATE_GENERATION_PROGRESS_TABLE)
    logger.info("Created generation_progress table")

    # Create indexes for queue tables
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcast_queue_status "
        "ON broadcast_queue(status)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcast_queue_created_at "
        "ON broadcast_queue(created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_generation_queue_status "
        "ON generation_queue(status)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_generation_queue_created_at "
        "ON generation_queue(created_at)"
    )
    logger.info("Created indexes for queue tables")

    logger.info("Migration v5 complete")


async def migrate_to_v6(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 6.

    Adds user difficulty preference:
    - New column: users.difficulty_min (minimum difficulty level 1-5)
    """
    logger.info("Running migration v6: Adding difficulty_min column to users table")

    # Check if column already exists (in case of partial migration)
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

    if "difficulty_min" not in column_names:
        await db.execute(
            "ALTER TABLE users ADD COLUMN difficulty_min INTEGER DEFAULT 1"
        )
        logger.info("Added 'difficulty_min' column to users table")
    else:
        logger.info("Column 'difficulty_min' already exists in users table")

    logger.info("Migration v6 complete")


async def migrate_to_v7(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 7.

    Gamification system overhaul:
    - New columns: user_stats.peak_streak, user_stats.challenges_completed, user_stats.comebacks
    - New columns: users.leaderboard_opted_in, users.display_name
    - New columns: achievements.tier, achievements.progress
    - New tables: content_mastery, weekly_challenges, user_weekly_progress,
                  comeback_bonuses, seasonal_events, user_event_progress, leaderboard_snapshots
    - Backfill content_mastery from existing user_answers data
    - Migrate old achievements to new tiered system
    """
    logger.info("Running migration v7: Gamification system overhaul")

    # =========================================================================
    # Add new columns to user_stats
    # =========================================================================
    async with db.execute("PRAGMA table_info(user_stats)") as cursor:
        columns = await cursor.fetchall()
        stats_columns = [col[1] for col in columns]

    if "peak_streak" not in stats_columns:
        await db.execute("ALTER TABLE user_stats ADD COLUMN peak_streak INTEGER DEFAULT 0")
        # Backfill peak_streak from longest_streak
        await db.execute("UPDATE user_stats SET peak_streak = longest_streak")
        logger.info("Added 'peak_streak' column to user_stats table")

    if "challenges_completed" not in stats_columns:
        await db.execute(
            "ALTER TABLE user_stats ADD COLUMN challenges_completed INTEGER DEFAULT 0"
        )
        logger.info("Added 'challenges_completed' column to user_stats table")

    if "comebacks" not in stats_columns:
        await db.execute("ALTER TABLE user_stats ADD COLUMN comebacks INTEGER DEFAULT 0")
        logger.info("Added 'comebacks' column to user_stats table")

    # =========================================================================
    # Add new columns to users
    # =========================================================================
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = await cursor.fetchall()
        users_columns = [col[1] for col in columns]

    if "leaderboard_opted_in" not in users_columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN leaderboard_opted_in BOOLEAN DEFAULT 0"
        )
        logger.info("Added 'leaderboard_opted_in' column to users table")

    if "display_name" not in users_columns:
        await db.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
        logger.info("Added 'display_name' column to users table")

    # =========================================================================
    # Add new columns to achievements
    # =========================================================================
    async with db.execute("PRAGMA table_info(achievements)") as cursor:
        columns = await cursor.fetchall()
        achievement_columns = [col[1] for col in columns]

    if "tier" not in achievement_columns:
        await db.execute(
            "ALTER TABLE achievements ADD COLUMN tier TEXT DEFAULT 'bronze'"
        )
        logger.info("Added 'tier' column to achievements table")

    if "progress" not in achievement_columns:
        await db.execute("ALTER TABLE achievements ADD COLUMN progress INTEGER DEFAULT 0")
        logger.info("Added 'progress' column to achievements table")

    # =========================================================================
    # Create new gamification tables
    # =========================================================================
    await db.execute(CREATE_CONTENT_MASTERY_TABLE)
    logger.info("Created content_mastery table")

    await db.execute(CREATE_WEEKLY_CHALLENGES_TABLE)
    logger.info("Created weekly_challenges table")

    await db.execute(CREATE_USER_WEEKLY_PROGRESS_TABLE)
    logger.info("Created user_weekly_progress table")

    await db.execute(CREATE_COMEBACK_BONUSES_TABLE)
    logger.info("Created comeback_bonuses table")

    await db.execute(CREATE_SEASONAL_EVENTS_TABLE)
    logger.info("Created seasonal_events table")

    await db.execute(CREATE_USER_EVENT_PROGRESS_TABLE)
    logger.info("Created user_event_progress table")

    await db.execute(CREATE_LEADERBOARD_SNAPSHOTS_TABLE)
    logger.info("Created leaderboard_snapshots table")

    # =========================================================================
    # Create indexes for new tables
    # =========================================================================
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_mastery_user_id ON content_mastery(user_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_mastery_area ON content_mastery(content_area)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week ON weekly_challenges(week_start)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_weekly_progress_user_id "
        "ON user_weekly_progress(user_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_weekly_progress_challenge "
        "ON user_weekly_progress(challenge_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_comeback_bonuses_user_id ON comeback_bonuses(user_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_comeback_bonuses_expires ON comeback_bonuses(expires_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_seasonal_events_dates "
        "ON seasonal_events(start_date, end_date)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_event_progress_user_id "
        "ON user_event_progress(user_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_event_progress_event "
        "ON user_event_progress(event_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_period "
        "ON leaderboard_snapshots(period_type, period_start)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_user "
        "ON leaderboard_snapshots(user_id)"
    )
    logger.info("Created indexes for gamification tables")

    # =========================================================================
    # Backfill content_mastery from existing user_answers data
    # =========================================================================
    await db.execute("""
        INSERT OR IGNORE INTO content_mastery (user_id, content_area, questions_answered, correct_answers, current_accuracy)
        SELECT
            ua.user_id,
            q.content_area,
            COUNT(*) as questions_answered,
            SUM(CASE WHEN ua.is_correct = 1 THEN 1 ELSE 0 END) as correct_answers,
            CAST(SUM(CASE WHEN ua.is_correct = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) as current_accuracy
        FROM user_answers ua
        JOIN questions q ON ua.question_id = q.id
        GROUP BY ua.user_id, q.content_area
    """)

    # Calculate and set mastery levels based on requirements:
    # BEGINNER (1): 10+ questions, 60%+ accuracy
    # INTERMEDIATE (2): 30+ questions, 75%+ accuracy
    # MASTER (3): 50+ questions, 85%+ accuracy
    await db.execute("""
        UPDATE content_mastery SET mastery_level = CASE
            WHEN questions_answered >= 50 AND current_accuracy >= 0.85 THEN 3
            WHEN questions_answered >= 30 AND current_accuracy >= 0.75 THEN 2
            WHEN questions_answered >= 10 AND current_accuracy >= 0.60 THEN 1
            ELSE 0
        END
    """)

    async with db.execute("SELECT COUNT(*) FROM content_mastery") as cursor:
        row = await cursor.fetchone()
        mastery_count = row[0] if row else 0

    logger.info(f"Backfilled content_mastery for {mastery_count} user/area combinations")

    # =========================================================================
    # Migrate old achievements to new tiered system
    # =========================================================================
    # Map old achievement types to new tiered types with appropriate tier
    achievement_mappings = [
        # Old type, new type, new tier
        ("first_steps", "scholar", "bronze"),
        ("century_club", "scholar", "silver"),
        ("knowledge_seeker", "scholar", "gold"),
        ("week_warrior", "consistent", "bronze"),
        ("monthly_master", "consistent", "silver"),
        ("streak_legend", "consistent", "gold"),
    ]

    for old_type, new_type, tier in achievement_mappings:
        await db.execute("""
            UPDATE achievements
            SET achievement_type = ?, tier = ?
            WHERE achievement_type = ?
        """, (new_type, tier, old_type))

    # Set progress to max for migrated achievements (they're complete)
    # Scholar: bronze=25, silver=100, gold=500
    await db.execute("""
        UPDATE achievements SET progress = 25 WHERE achievement_type = 'scholar' AND tier = 'bronze'
    """)
    await db.execute("""
        UPDATE achievements SET progress = 100 WHERE achievement_type = 'scholar' AND tier = 'silver'
    """)
    await db.execute("""
        UPDATE achievements SET progress = 500 WHERE achievement_type = 'scholar' AND tier = 'gold'
    """)

    # Consistent: bronze=7, silver=30, gold=100
    await db.execute("""
        UPDATE achievements SET progress = 7 WHERE achievement_type = 'consistent' AND tier = 'bronze'
    """)
    await db.execute("""
        UPDATE achievements SET progress = 30 WHERE achievement_type = 'consistent' AND tier = 'silver'
    """)
    await db.execute("""
        UPDATE achievements SET progress = 100 WHERE achievement_type = 'consistent' AND tier = 'gold'
    """)

    # Remove old content mastery achievements that don't map to new system
    # (ethics_expert, assessment_ace, procedures_pro, foundations_master, design_specialist, perfect_week)
    await db.execute("""
        DELETE FROM achievements WHERE achievement_type IN (
            'ethics_expert', 'assessment_ace', 'procedures_pro',
            'foundations_master', 'design_specialist', 'perfect_week'
        )
    """)

    logger.info("Migrated old achievements to new tiered system")

    logger.info("Migration v7 complete")
