"""
Pytest fixtures for AbaQuiz tests.
"""

import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

# Set test environment variables before importing settings
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token_12345"
os.environ["ANTHROPIC_API_KEY"] = "test_api_key_12345"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest_asyncio.fixture
async def repository(temp_db_path: str) -> AsyncGenerator:
    """Create a test repository with initialized database."""
    from src.database.migrations import initialize_database, run_migrations
    from src.database.repository import Repository

    # Initialize the database schema
    await initialize_database(temp_db_path)

    # Run migrations to add any new columns (e.g., source_citation, review_status)
    await run_migrations(temp_db_path)

    # Create repository
    repo = Repository(temp_db_path)
    await repo.connect()

    yield repo

    # Cleanup
    await repo.close()


@pytest.fixture
def sample_question() -> dict:
    """Sample question data for testing."""
    return {
        "content": "A behavior analyst is designing an intervention. What is the first step?",
        "question_type": "multiple_choice",
        "options": {
            "A": "Implement the intervention immediately",
            "B": "Conduct a functional assessment",
            "C": "Consult with colleagues",
            "D": "Review the literature",
        },
        "correct_answer": "B",
        "explanation": "Conducting a functional assessment is the first step.",
        "content_area": "Behavior Assessment",
    }


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user data for testing."""
    return {
        "telegram_id": 123456789,
        "username": "testuser",
        "timezone": "America/New_York",
    }
