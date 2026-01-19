"""
Database migrations for AbaQuiz.

Handles schema creation and updates.
"""

import aiosqlite

from src.config.logging import get_logger
from src.database.models import ALL_TABLES, CREATE_INDEXES

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

        await db.commit()


async def migrate_to_v1(db: aiosqlite.Connection) -> None:
    """
    Migration to schema version 1.

    Adds 'model' column to questions table to track which Claude model
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
