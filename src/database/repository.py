"""
Database repository for AbaQuiz.

All database operations are centralized here.
"""

import json
from datetime import date, datetime, timedelta
from typing import Any, Optional

import aiosqlite

from src.config.constants import AchievementType, ContentArea
from src.config.logging import get_logger

logger = get_logger(__name__)


class Repository:
    """Async database repository for all data operations."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Get active connection."""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # =========================================================================
    # User Operations
    # =========================================================================

    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        timezone: str = "America/Los_Angeles",
    ) -> int:
        """Create a new user and return their ID."""
        async with self.db.execute(
            """
            INSERT INTO users (telegram_id, username, timezone)
            VALUES (?, ?, ?)
            """,
            (telegram_id, username, timezone),
        ) as cursor:
            await self.db.commit()
            user_id = cursor.lastrowid

        # Create initial stats record
        await self.db.execute(
            "INSERT INTO user_stats (user_id) VALUES (?)",
            (user_id,),
        )
        await self.db.commit()

        logger.info(f"Created user {telegram_id} with ID {user_id}")
        return user_id

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[dict[str, Any]]:
        """Get user by Telegram ID."""
        async with self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        """Get user by internal ID."""
        async with self.db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_user(
        self,
        telegram_id: int,
        **kwargs: Any,
    ) -> None:
        """Update user fields."""
        if not kwargs:
            return

        # Handle JSON fields
        if "focus_preferences" in kwargs and isinstance(
            kwargs["focus_preferences"], list
        ):
            kwargs["focus_preferences"] = json.dumps(kwargs["focus_preferences"])

        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [telegram_id]

        await self.db.execute(
            f"UPDATE users SET {fields}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE telegram_id = ?",
            values,
        )
        await self.db.commit()

    async def get_subscribed_users(self) -> list[dict[str, Any]]:
        """Get all subscribed users."""
        async with self.db.execute(
            "SELECT * FROM users WHERE is_subscribed = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_users(self) -> list[dict[str, Any]]:
        """Get all users."""
        async with self.db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_subscribed_users_by_timezone(
        self, timezone: str
    ) -> list[dict[str, Any]]:
        """Get all subscribed users in a specific timezone."""
        async with self.db.execute(
            "SELECT * FROM users WHERE is_subscribed = 1 AND timezone = ?",
            (timezone,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_user_count(self) -> int:
        """Get total user count."""
        async with self.db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_subscribed_user_count(self) -> int:
        """Get count of subscribed users."""
        async with self.db.execute(
            "SELECT COUNT(*) as count FROM users WHERE is_subscribed = 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_recent_users(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most recently registered users."""
        async with self.db.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_banned_users(self) -> list[dict[str, Any]]:
        """Get all banned users."""
        async with self.db.execute("SELECT * FROM banned_users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_active_users(self, days: int = 7) -> list[dict[str, Any]]:
        """Get users active in the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        async with self.db.execute(
            """
            SELECT DISTINCT u.* FROM users u
            JOIN user_answers ua ON u.id = ua.user_id
            WHERE ua.answered_at > ?
            """,
            (cutoff,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_user(self, telegram_id: int) -> bool:
        """Delete user and all their data."""
        user = await self.get_user_by_telegram_id(telegram_id)
        if not user:
            return False

        await self.db.execute(
            "DELETE FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        await self.db.commit()
        logger.info(f"Deleted user {telegram_id}")
        return True

    async def reset_daily_extra_counts(self) -> int:
        """Reset daily extra question counts for all users. Returns count updated."""
        async with self.db.execute(
            "UPDATE users SET daily_extra_count = 0 WHERE daily_extra_count > 0"
        ) as cursor:
            await self.db.commit()
            return cursor.rowcount

    # =========================================================================
    # Question Operations
    # =========================================================================

    async def create_question(
        self,
        content: str,
        question_type: str,
        options: dict[str, str],
        correct_answer: str,
        explanation: str,
        content_area: str,
    ) -> int:
        """Create a new question and return its ID."""
        async with self.db.execute(
            """
            INSERT INTO questions
            (content, question_type, options, correct_answer, explanation, content_area)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                content,
                question_type,
                json.dumps(options),
                correct_answer,
                explanation,
                content_area,
            ),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    async def get_question_by_id(
        self, question_id: int
    ) -> Optional[dict[str, Any]]:
        """Get question by ID."""
        async with self.db.execute(
            "SELECT * FROM questions WHERE id = ?",
            (question_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result["options"] = json.loads(result["options"])
                return result
            return None

    async def get_unseen_question_for_user(
        self,
        user_id: int,
        content_area: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get a random question the user hasn't seen yet."""
        if content_area:
            query = """
                SELECT q.* FROM questions q
                WHERE q.content_area = ?
                AND q.id NOT IN (
                    SELECT question_id FROM sent_questions WHERE user_id = ?
                )
                ORDER BY RANDOM()
                LIMIT 1
            """
            params = (content_area, user_id)
        else:
            query = """
                SELECT q.* FROM questions q
                WHERE q.id NOT IN (
                    SELECT question_id FROM sent_questions WHERE user_id = ?
                )
                ORDER BY RANDOM()
                LIMIT 1
            """
            params = (user_id,)

        async with self.db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result["options"] = json.loads(result["options"])
                return result
            return None

    async def get_question_pool_counts(self) -> dict[str, int]:
        """Get count of questions per content area."""
        async with self.db.execute(
            """
            SELECT content_area, COUNT(*) as count
            FROM questions
            GROUP BY content_area
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return {row["content_area"]: row["count"] for row in rows}

    async def get_available_questions_for_user(
        self,
        user_id: int,
        content_area: str,
    ) -> int:
        """Count unseen questions for a user in a content area."""
        async with self.db.execute(
            """
            SELECT COUNT(*) as count FROM questions q
            WHERE q.content_area = ?
            AND q.id NOT IN (
                SELECT question_id FROM sent_questions WHERE user_id = ?
            )
            """,
            (content_area, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    # =========================================================================
    # Sent Questions Tracking
    # =========================================================================

    async def record_sent_question(
        self,
        user_id: int,
        question_id: int,
        message_id: Optional[int] = None,
        is_scheduled: bool = False,
    ) -> int:
        """Record that a question was sent to a user."""
        async with self.db.execute(
            """
            INSERT INTO sent_questions (user_id, question_id, message_id, is_scheduled)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, question_id, message_id, is_scheduled),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    # =========================================================================
    # Answer Operations
    # =========================================================================

    async def record_answer(
        self,
        user_id: int,
        question_id: int,
        user_answer: str,
        is_correct: bool,
    ) -> int:
        """Record a user's answer."""
        async with self.db.execute(
            """
            INSERT INTO user_answers (user_id, question_id, user_answer, is_correct)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, question_id, user_answer, is_correct),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    async def has_user_answered_question(
        self, user_id: int, question_id: int
    ) -> bool:
        """Check if user has already answered a question."""
        async with self.db.execute(
            """
            SELECT 1 FROM user_answers
            WHERE user_id = ? AND question_id = ?
            """,
            (user_id, question_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_user_answers(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get user's answer history."""
        async with self.db.execute(
            """
            SELECT ua.*, q.content_area, q.content
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            WHERE ua.user_id = ?
            ORDER BY ua.answered_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_user_accuracy_by_area(
        self, user_id: int
    ) -> dict[str, dict[str, Any]]:
        """Get user's accuracy breakdown by content area."""
        async with self.db.execute(
            """
            SELECT
                q.content_area,
                COUNT(*) as total,
                SUM(CASE WHEN ua.is_correct THEN 1 ELSE 0 END) as correct
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            WHERE ua.user_id = ?
            GROUP BY q.content_area
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {
                row["content_area"]: {
                    "total": row["total"],
                    "correct": row["correct"],
                    "accuracy": row["correct"] / row["total"] if row["total"] > 0 else 0,
                }
                for row in rows
            }

    async def get_user_weakest_area(
        self, user_id: int, min_answers: int = 5
    ) -> Optional[str]:
        """Get user's weakest content area (lowest accuracy with min answers)."""
        async with self.db.execute(
            """
            SELECT
                q.content_area,
                COUNT(*) as total,
                SUM(CASE WHEN ua.is_correct THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as accuracy
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            WHERE ua.user_id = ?
            GROUP BY q.content_area
            HAVING total >= ?
            ORDER BY accuracy ASC
            LIMIT 1
            """,
            (user_id, min_answers),
        ) as cursor:
            row = await cursor.fetchone()
            return row["content_area"] if row else None

    # =========================================================================
    # Stats Operations
    # =========================================================================

    async def get_user_stats(self, user_id: int) -> Optional[dict[str, Any]]:
        """Get user stats."""
        async with self.db.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_user_stats(
        self,
        user_id: int,
        **kwargs: Any,
    ) -> None:
        """Update user stats."""
        if not kwargs:
            return

        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]

        await self.db.execute(
            f"UPDATE user_stats SET {fields} WHERE user_id = ?",
            values,
        )
        await self.db.commit()

    async def add_points(self, user_id: int, points: int) -> int:
        """Add points to user and return new total."""
        await self.db.execute(
            """
            UPDATE user_stats
            SET total_points = total_points + ?
            WHERE user_id = ?
            """,
            (points, user_id),
        )
        await self.db.commit()

        stats = await self.get_user_stats(user_id)
        return stats["total_points"] if stats else points

    async def update_streak(
        self,
        user_id: int,
        answer_date: date,
    ) -> tuple[int, bool]:
        """
        Update user streak based on answer date.

        Returns:
            Tuple of (new_streak, streak_increased)
        """
        stats = await self.get_user_stats(user_id)
        if not stats:
            return (0, False)

        last_answer = stats["last_answer_date"]
        current_streak = stats["current_streak"]
        longest_streak = stats["longest_streak"]

        if last_answer is None:
            new_streak = 1
            streak_increased = True
        else:
            # Parse last_answer if it's a string
            if isinstance(last_answer, str):
                last_answer = date.fromisoformat(last_answer)

            days_diff = (answer_date - last_answer).days

            if days_diff == 0:
                # Same day, no change
                new_streak = current_streak
                streak_increased = False
            elif days_diff == 1:
                # Consecutive day
                new_streak = current_streak + 1
                streak_increased = True
            else:
                # Streak broken
                new_streak = 1
                streak_increased = False

        # Update longest if needed
        new_longest = max(longest_streak, new_streak)

        await self.update_user_stats(
            user_id,
            current_streak=new_streak,
            longest_streak=new_longest,
            last_answer_date=answer_date.isoformat(),
        )

        return (new_streak, streak_increased)

    async def get_total_questions_answered(self, user_id: int) -> int:
        """Get total questions answered by user."""
        async with self.db.execute(
            "SELECT COUNT(*) as count FROM user_answers WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_overall_accuracy(self, user_id: int) -> float:
        """Get user's overall accuracy."""
        async with self.db.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
            FROM user_answers WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row["total"] > 0:
                return row["correct"] / row["total"]
            return 0.0

    # =========================================================================
    # Achievement Operations
    # =========================================================================

    async def grant_achievement(
        self,
        user_id: int,
        achievement_type: AchievementType,
    ) -> bool:
        """Grant achievement to user. Returns True if newly granted."""
        try:
            await self.db.execute(
                """
                INSERT INTO achievements (user_id, achievement_type)
                VALUES (?, ?)
                """,
                (user_id, achievement_type.value),
            )
            await self.db.commit()
            logger.info(f"Granted {achievement_type.value} to user {user_id}")
            return True
        except aiosqlite.IntegrityError:
            # Already has this achievement
            return False

    async def has_achievement(
        self,
        user_id: int,
        achievement_type: AchievementType,
    ) -> bool:
        """Check if user has an achievement."""
        async with self.db.execute(
            """
            SELECT 1 FROM achievements
            WHERE user_id = ? AND achievement_type = ?
            """,
            (user_id, achievement_type.value),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_user_achievements(
        self, user_id: int
    ) -> list[dict[str, Any]]:
        """Get all achievements for a user."""
        async with self.db.execute(
            """
            SELECT * FROM achievements
            WHERE user_id = ?
            ORDER BY unlocked_at DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # Ban Operations
    # =========================================================================

    async def ban_user(
        self,
        telegram_id: int,
        banned_by: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Ban a user. Returns True if newly banned."""
        try:
            await self.db.execute(
                """
                INSERT INTO banned_users (telegram_id, banned_by, reason)
                VALUES (?, ?, ?)
                """,
                (telegram_id, banned_by, reason),
            )
            await self.db.commit()
            logger.info(f"Banned user {telegram_id}")
            return True
        except aiosqlite.IntegrityError:
            return False

    async def unban_user(self, telegram_id: int) -> bool:
        """Unban a user. Returns True if was banned."""
        async with self.db.execute(
            "DELETE FROM banned_users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            await self.db.commit()
            if cursor.rowcount > 0:
                logger.info(f"Unbanned user {telegram_id}")
                return True
            return False

    async def is_banned(self, telegram_id: int) -> bool:
        """Check if user is banned."""
        async with self.db.execute(
            "SELECT 1 FROM banned_users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchone() is not None

    # =========================================================================
    # Admin Settings Operations
    # =========================================================================

    async def get_admin_settings(
        self, telegram_id: int
    ) -> Optional[dict[str, Any]]:
        """Get admin notification settings."""
        async with self.db.execute(
            "SELECT * FROM admin_settings WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_admin_settings(
        self,
        telegram_id: int,
        summary_enabled: Optional[bool] = None,
        alerts_enabled: Optional[bool] = None,
    ) -> None:
        """Update or create admin settings."""
        existing = await self.get_admin_settings(telegram_id)

        if existing:
            updates = {}
            if summary_enabled is not None:
                updates["summary_enabled"] = summary_enabled
            if alerts_enabled is not None:
                updates["alerts_enabled"] = alerts_enabled

            if updates:
                fields = ", ".join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [telegram_id]
                await self.db.execute(
                    f"UPDATE admin_settings SET {fields} WHERE telegram_id = ?",
                    values,
                )
        else:
            await self.db.execute(
                """
                INSERT INTO admin_settings (telegram_id, summary_enabled, alerts_enabled)
                VALUES (?, ?, ?)
                """,
                (
                    telegram_id,
                    summary_enabled if summary_enabled is not None else True,
                    alerts_enabled if alerts_enabled is not None else True,
                ),
            )

        await self.db.commit()

    # =========================================================================
    # API Usage Operations
    # =========================================================================

    async def record_api_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        estimated_cost: float,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        content_area: Optional[str] = None,
    ) -> int:
        """Record API usage."""
        async with self.db.execute(
            """
            INSERT INTO api_usage
            (input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
             model, content_area, estimated_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                input_tokens,
                output_tokens,
                cache_write_tokens,
                cache_read_tokens,
                model,
                content_area,
                estimated_cost,
            ),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    async def get_api_usage_stats(
        self, hours: int = 24
    ) -> dict[str, Any]:
        """Get API usage stats for the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)

        async with self.db.execute(
            """
            SELECT
                COUNT(*) as total_calls,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cache_write_tokens) as total_cache_write_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                SUM(estimated_cost) as total_cost
            FROM api_usage
            WHERE timestamp > ?
            """,
            (cutoff,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

    # =========================================================================
    # Analytics Operations
    # =========================================================================

    async def get_daily_stats(self, date_obj: date) -> dict[str, Any]:
        """Get stats for a specific date."""
        date_str = date_obj.isoformat()

        async with self.db.execute(
            """
            SELECT
                COUNT(DISTINCT ua.user_id) as active_users,
                COUNT(*) as answers_count,
                SUM(CASE WHEN ua.is_correct THEN 1 ELSE 0 END) as correct_count
            FROM user_answers ua
            WHERE DATE(ua.answered_at) = ?
            """,
            (date_str,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_new_users_count(self, hours: int = 24) -> int:
        """Get count of new users in last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        async with self.db.execute(
            "SELECT COUNT(*) as count FROM users WHERE created_at > ?",
            (cutoff,),
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0


# Global repository instance
_repository: Optional[Repository] = None


async def get_repository(db_path: str) -> Repository:
    """Get or create the global repository instance."""
    global _repository
    if _repository is None:
        _repository = Repository(db_path)
        await _repository.connect()
    return _repository
