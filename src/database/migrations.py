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

        # Add migrations here as the schema evolves
        # Example:
        # if current_version < 1:
        #     await migrate_to_v1(db)
        #     await set_schema_version(db, 1)
        #
        # if current_version < 2:
        #     await migrate_to_v2(db)
        #     await set_schema_version(db, 2)

        await db.commit()


# Future migration functions can be added here
# async def migrate_to_v1(db: aiosqlite.Connection) -> None:
#     """Migration to schema version 1."""
#     pass
