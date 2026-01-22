"""
Database migrations for AbaQuiz.

Handles schema creation and updates.
"""

import aiosqlite

from src.config.logging import get_logger
from src.database.models import (
    ALL_TABLES,
    CREATE_INDEXES,
    CREATE_QUESTION_REPORTS_TABLE,
    CREATE_QUESTION_STATS_TABLE,
    CREATE_QUESTION_REVIEWS_TABLE,
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
