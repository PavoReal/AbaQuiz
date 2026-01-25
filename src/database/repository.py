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

    async def reset_daily_extra_counts_by_timezone(self, timezone: str) -> int:
        """
        Reset daily extra question counts for users in a specific timezone.

        Args:
            timezone: The timezone to reset limits for

        Returns:
            Number of users updated
        """
        async with self.db.execute(
            "UPDATE users SET daily_extra_count = 0 WHERE daily_extra_count > 0 AND timezone = ?",
            (timezone,),
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
        model: Optional[str] = None,
        source_citation: Optional[dict[str, Any]] = None,
        difficulty: Optional[int] = None,
    ) -> int:
        """Create a new question and return its ID."""
        citation_json = json.dumps(source_citation) if source_citation else None
        async with self.db.execute(
            """
            INSERT INTO questions
            (content, question_type, options, correct_answer, explanation, content_area, model, source_citation, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content,
                question_type,
                json.dumps(options),
                correct_answer,
                explanation,
                content_area,
                model,
                citation_json,
                difficulty,
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
                # Parse source_citation JSON if present
                if result.get("source_citation"):
                    try:
                        result["source_citation"] = json.loads(result["source_citation"])
                    except json.JSONDecodeError:
                        pass
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

    async def browse_questions(
        self,
        page: int = 1,
        per_page: int = 20,
        content_area: Optional[str] = None,
        difficulty_min: Optional[int] = None,
        difficulty_max: Optional[int] = None,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Browse questions with filters for the admin UI.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            content_area: Filter by content area
            difficulty_min: Minimum difficulty (1-5)
            difficulty_max: Maximum difficulty (1-5)
            search: Search term for question content

        Returns:
            Dict with rows, total, page, per_page, pages, and content_areas
        """
        # Build query with filters
        query = "SELECT * FROM questions WHERE 1=1"
        count_query = "SELECT COUNT(*) as count FROM questions WHERE 1=1"
        params: list[Any] = []

        if content_area:
            query += " AND content_area = ?"
            count_query += " AND content_area = ?"
            params.append(content_area)

        if difficulty_min is not None:
            query += " AND difficulty >= ?"
            count_query += " AND difficulty >= ?"
            params.append(difficulty_min)

        if difficulty_max is not None:
            query += " AND difficulty <= ?"
            count_query += " AND difficulty <= ?"
            params.append(difficulty_max)

        if search:
            query += " AND (content LIKE ? OR explanation LIKE ?)"
            count_query += " AND (content LIKE ? OR explanation LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        # Get total count
        async with self.db.execute(count_query, params) as cursor:
            count_row = await cursor.fetchone()
            total = count_row["count"] if count_row else 0

        # Add ordering and pagination
        query += " ORDER BY created_at DESC"
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"

        # Fetch rows
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            questions = []
            for row in rows:
                q = dict(row)
                q["options"] = json.loads(q["options"])
                questions.append(q)

        # Get distinct content areas for filter dropdown
        async with self.db.execute(
            "SELECT DISTINCT content_area FROM questions ORDER BY content_area"
        ) as cursor:
            area_rows = await cursor.fetchall()
            content_areas = [r["content_area"] for r in area_rows]

        return {
            "rows": questions,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total > 0 else 1,
            "content_areas": content_areas,
        }

    # =========================================================================
    # Sent Questions Tracking
    # =========================================================================

    async def record_sent_question(
        self,
        user_id: int,
        question_id: int,
        message_id: Optional[int] = None,
        is_scheduled: bool = False,
        is_bonus: bool = False,
    ) -> int:
        """Record that a question was sent to a user."""
        async with self.db.execute(
            """
            INSERT INTO sent_questions (user_id, question_id, message_id, is_scheduled, is_bonus)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, question_id, message_id, is_scheduled, is_bonus),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    async def was_bonus_sent_today(self) -> bool:
        """Check if a bonus question was already sent today."""
        async with self.db.execute(
            """
            SELECT 1 FROM sent_questions
            WHERE is_bonus = 1 AND DATE(sent_at) = DATE('now')
            LIMIT 1
            """
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_latest_daily_question_for_user(
        self, user_id: int
    ) -> Optional[dict[str, Any]]:
        """Get the most recent scheduled (daily) question sent to a user."""
        async with self.db.execute(
            """
            SELECT
                sq.question_id,
                sq.message_id,
                sq.sent_at,
                q.content,
                q.question_type,
                q.options,
                q.correct_answer,
                q.explanation,
                q.content_area,
                ua.user_answer,
                ua.is_correct,
                ua.answered_at
            FROM sent_questions sq
            JOIN questions q ON sq.question_id = q.id
            LEFT JOIN user_answers ua
                ON ua.question_id = sq.question_id AND ua.user_id = sq.user_id
            WHERE sq.user_id = ? AND sq.is_scheduled = 1
            ORDER BY sq.sent_at DESC
            LIMIT 1
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result["options"] = json.loads(result["options"])
                return result
            return None

    # =========================================================================
    # Answer Operations
    # =========================================================================

    async def record_answer(
        self,
        user_id: int,
        question_id: int,
        user_answer: str,
        is_correct: bool,
        response_time_ms: Optional[int] = None,
    ) -> int:
        """Record a user's answer."""
        async with self.db.execute(
            """
            INSERT INTO user_answers (user_id, question_id, user_answer, is_correct, response_time_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, question_id, user_answer, is_correct, response_time_ms),
        ) as cursor:
            await self.db.commit()
            answer_id = cursor.lastrowid

        # Update question stats
        await self.record_question_answer_stats(
            question_id=question_id,
            user_answer=user_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
        )

        return answer_id

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

    async def get_user_answer(
        self, user_id: int, question_id: int
    ) -> dict[str, Any] | None:
        """Get a specific user answer record."""
        async with self.db.execute(
            """
            SELECT * FROM user_answers
            WHERE user_id = ? AND question_id = ?
            """,
            (user_id, question_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

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
    # Admin Management Operations
    # =========================================================================

    async def add_admin(
        self,
        telegram_id: int,
        added_by: Optional[int] = None,
        is_super_admin: bool = False,
    ) -> bool:
        """
        Add an admin to the database.

        Args:
            telegram_id: Telegram user ID to add as admin
            added_by: Telegram ID of admin who added this user
            is_super_admin: Whether this admin can manage other admins

        Returns:
            True if newly added, False if already an admin
        """
        try:
            await self.db.execute(
                """
                INSERT INTO admins (telegram_id, added_by, is_super_admin)
                VALUES (?, ?, ?)
                """,
                (telegram_id, added_by, is_super_admin),
            )
            await self.db.commit()
            logger.info(
                f"Added admin {telegram_id} (super={is_super_admin}) by {added_by}"
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_admin(self, telegram_id: int) -> bool:
        """
        Remove an admin from the database.

        Args:
            telegram_id: Telegram user ID to remove

        Returns:
            True if removed, False if wasn't an admin
        """
        async with self.db.execute(
            "DELETE FROM admins WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            await self.db.commit()
            if cursor.rowcount > 0:
                logger.info(f"Removed admin {telegram_id}")
                return True
            return False

    async def is_admin(self, telegram_id: int) -> bool:
        """Check if user is an admin in the database."""
        async with self.db.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def is_super_admin(self, telegram_id: int) -> bool:
        """Check if user is a super admin (can manage other admins)."""
        async with self.db.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ? AND is_super_admin = 1",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_all_admins(self) -> list[dict[str, Any]]:
        """Get all admins from the database."""
        async with self.db.execute(
            "SELECT * FROM admins ORDER BY added_at"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_super_admin_count(self) -> int:
        """Get count of super admins."""
        async with self.db.execute(
            "SELECT COUNT(*) as count FROM admins WHERE is_super_admin = 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

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

    # =========================================================================
    # Pool Management Operations
    # =========================================================================

    async def get_active_user_count(self, days: int = 7) -> int:
        """Get count of users who answered a question in the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        async with self.db.execute(
            """
            SELECT COUNT(DISTINCT user_id) as count
            FROM user_answers
            WHERE answered_at > ?
            """,
            (cutoff,),
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_avg_unseen_questions_for_active_users(self, days: int = 7) -> float:
        """
        Get average number of unseen questions per active user.

        Active users = users who answered a question in the last N days.
        Returns 0.0 if there are no active users.
        """
        async with self.db.execute(
            """
            SELECT AVG(total_questions - seen_count) as avg_unseen
            FROM (
                SELECT
                    (SELECT COUNT(*) FROM questions) as total_questions,
                    COALESCE(
                        (SELECT COUNT(DISTINCT question_id)
                         FROM sent_questions
                         WHERE user_id = ua.user_id),
                        0
                    ) as seen_count
                FROM (
                    SELECT DISTINCT user_id
                    FROM user_answers
                    WHERE answered_at > datetime('now', ? || ' days')
                ) ua
            ) user_stats
            """,
            (f"-{days}",),
        ) as cursor:
            row = await cursor.fetchone()
            return float(row["avg_unseen"]) if row and row["avg_unseen"] else 0.0

    async def get_questions_by_content_area(
        self, content_area: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get most recent questions for a content area."""
        async with self.db.execute(
            """
            SELECT * FROM questions
            WHERE content_area = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (content_area, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                q = dict(row)
                q["options"] = json.loads(q["options"])
                result.append(q)
            return result

    async def get_total_question_count(self) -> int:
        """Get total count of questions in the pool."""
        async with self.db.execute(
            "SELECT COUNT(*) as count FROM questions"
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_questions_with_null_difficulty(
        self, limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Fetch questions where difficulty IS NULL.

        Args:
            limit: Maximum number of questions to return (None = all)

        Returns:
            List of question dicts with id, content, content_area, options, correct_answer
        """
        query = """
            SELECT id, content, content_area, options, correct_answer
            FROM questions
            WHERE difficulty IS NULL
            ORDER BY id
        """
        if limit is not None:
            query += f" LIMIT {limit}"

        async with self.db.execute(query) as cursor:
            rows = await cursor.fetchall()
            questions = []
            for row in rows:
                q = dict(row)
                q["options"] = json.loads(q["options"])
                questions.append(q)
            return questions

    async def bulk_update_difficulty(
        self, updates: list[tuple[int, int]]
    ) -> int:
        """
        Bulk update difficulty ratings for questions.

        Args:
            updates: List of (question_id, difficulty) tuples

        Returns:
            Number of questions updated
        """
        if not updates:
            return 0

        updated_count = 0
        for question_id, difficulty in updates:
            await self.db.execute(
                "UPDATE questions SET difficulty = ? WHERE id = ?",
                (difficulty, question_id),
            )
            updated_count += 1

        await self.db.commit()
        return updated_count

    # =========================================================================
    # Question Stats Operations
    # =========================================================================

    async def ensure_question_stats(self, question_id: int) -> None:
        """Ensure a question_stats record exists for the given question."""
        await self.db.execute(
            """
            INSERT OR IGNORE INTO question_stats (question_id)
            VALUES (?)
            """,
            (question_id,),
        )
        await self.db.commit()

    async def record_question_answer_stats(
        self,
        question_id: int,
        user_answer: str,
        is_correct: bool,
        response_time_ms: Optional[int] = None,
    ) -> None:
        """Update question_stats when an answer is recorded."""
        await self.ensure_question_stats(question_id)

        # Determine which option column to increment
        answer_upper = user_answer.upper()
        option_column = None
        if answer_upper == "A":
            option_column = "option_a_count"
        elif answer_upper == "B":
            option_column = "option_b_count"
        elif answer_upper == "C":
            option_column = "option_c_count"
        elif answer_upper == "D":
            option_column = "option_d_count"
        elif answer_upper == "TRUE":
            option_column = "option_true_count"
        elif answer_upper == "FALSE":
            option_column = "option_false_count"

        # Build update query
        updates = [
            "times_answered = times_answered + 1",
            f"correct_count = correct_count + {1 if is_correct else 0}",
            f"incorrect_count = incorrect_count + {0 if is_correct else 1}",
            "last_updated = CURRENT_TIMESTAMP",
        ]

        if option_column:
            updates.append(f"{option_column} = {option_column} + 1")

        if response_time_ms is not None:
            updates.append(f"total_response_time_ms = total_response_time_ms + {response_time_ms}")

        query = f"UPDATE question_stats SET {', '.join(updates)} WHERE question_id = ?"
        await self.db.execute(query, (question_id,))
        await self.db.commit()

    async def record_question_shown(self, question_id: int) -> None:
        """Increment times_shown for a question."""
        await self.ensure_question_stats(question_id)
        await self.db.execute(
            """
            UPDATE question_stats
            SET times_shown = times_shown + 1, last_updated = CURRENT_TIMESTAMP
            WHERE question_id = ?
            """,
            (question_id,),
        )
        await self.db.commit()

    async def get_question_stats(self, question_id: int) -> Optional[dict[str, Any]]:
        """Get stats for a specific question."""
        async with self.db.execute(
            "SELECT * FROM question_stats WHERE question_id = ?",
            (question_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # Question Reports Operations
    # =========================================================================

    async def create_question_report(
        self,
        question_id: int,
        user_id: int,
        report_type: str,
        details: Optional[str] = None,
    ) -> int:
        """Create a new question report."""
        async with self.db.execute(
            """
            INSERT INTO question_reports (question_id, user_id, report_type, details)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, user_id, report_type, details),
        ) as cursor:
            await self.db.commit()
            report_id = cursor.lastrowid

        # Update report count in question_stats
        await self.ensure_question_stats(question_id)
        await self.db.execute(
            """
            UPDATE question_stats
            SET report_count = report_count + 1, last_updated = CURRENT_TIMESTAMP
            WHERE question_id = ?
            """,
            (question_id,),
        )
        await self.db.commit()

        return report_id

    async def get_user_report_count_today(self, user_id: int) -> int:
        """Get number of reports a user has submitted today."""
        async with self.db.execute(
            """
            SELECT COUNT(*) as count FROM question_reports
            WHERE user_id = ? AND DATE(created_at) = DATE('now')
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_question_reports(
        self,
        question_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get question reports with optional filters."""
        query = "SELECT * FROM question_reports WHERE 1=1"
        params: list[Any] = []

        if question_id is not None:
            query += " AND question_id = ?"
            params.append(question_id)

        if status is not None:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_report_status(
        self,
        report_id: int,
        status: str,
        reviewed_by: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
    ) -> bool:
        """Update report status."""
        resolved_at = "CURRENT_TIMESTAMP" if status in ("resolved", "dismissed") else "NULL"
        await self.db.execute(
            f"""
            UPDATE question_reports
            SET status = ?, reviewed_by = ?, reviewer_notes = ?, resolved_at = {resolved_at}
            WHERE id = ?
            """,
            (status, reviewed_by, reviewer_notes, report_id),
        )
        await self.db.commit()
        return True

    # =========================================================================
    # Question Reviews Operations
    # =========================================================================

    async def create_question_review(
        self,
        question_id: int,
        reviewer_id: str,
        decision: str,
        notes: Optional[str] = None,
        review_data: Optional[dict[str, Any]] = None,
        difficulty: Optional[int] = None,
    ) -> int:
        """Create an expert review for a question."""
        review_data_json = json.dumps(review_data) if review_data else None

        async with self.db.execute(
            """
            INSERT INTO question_reviews (question_id, reviewer_id, decision, notes, review_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (question_id, reviewer_id, decision, notes, review_data_json),
        ) as cursor:
            await self.db.commit()
            review_id = cursor.lastrowid

        # Update question's review_status and difficulty
        updates = ["review_status = ?"]
        params: list[Any] = [decision]

        if difficulty is not None:
            updates.append("difficulty = ?")
            params.append(difficulty)

        params.append(question_id)
        await self.db.execute(
            f"UPDATE questions SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()

        return review_id

    async def get_question_reviews(
        self,
        question_id: int,
    ) -> list[dict[str, Any]]:
        """Get all reviews for a question."""
        async with self.db.execute(
            """
            SELECT * FROM question_reviews
            WHERE question_id = ?
            ORDER BY created_at DESC
            """,
            (question_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            reviews = []
            for row in rows:
                review = dict(row)
                if review.get("review_data"):
                    try:
                        review["review_data"] = json.loads(review["review_data"])
                    except json.JSONDecodeError:
                        pass
                reviews.append(review)
            return reviews

    async def get_question_with_review_data(
        self,
        question_id: int,
    ) -> Optional[dict[str, Any]]:
        """Get a question with its stats, reports, and reviews."""
        question = await self.get_question_by_id(question_id)
        if not question:
            return None

        question["stats"] = await self.get_question_stats(question_id)
        question["reports"] = await self.get_question_reports(question_id=question_id)
        question["reviews"] = await self.get_question_reviews(question_id)

        return question

    async def get_next_unreviewed_question(
        self,
        current_id: Optional[int] = None,
        content_area: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get the next unreviewed question for the review queue."""
        query = """
            SELECT * FROM questions
            WHERE (review_status IS NULL OR review_status = 'unreviewed')
        """
        params: list[Any] = []

        if current_id is not None:
            query += " AND id > ?"
            params.append(current_id)

        if content_area is not None:
            query += " AND content_area = ?"
            params.append(content_area)

        query += " ORDER BY id ASC LIMIT 1"

        async with self.db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result["options"] = json.loads(result["options"])
                if result.get("source_citation"):
                    try:
                        result["source_citation"] = json.loads(result["source_citation"])
                    except json.JSONDecodeError:
                        pass
                return result
            return None

    async def get_review_queue_count(
        self,
        content_area: Optional[str] = None,
    ) -> dict[str, int]:
        """Get counts of questions by review status."""
        query = """
            SELECT
                COALESCE(review_status, 'unreviewed') as status,
                COUNT(*) as count
            FROM questions
        """
        params: list[Any] = []

        if content_area is not None:
            query += " WHERE content_area = ?"
            params.append(content_area)

        query += " GROUP BY COALESCE(review_status, 'unreviewed')"

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return {row["status"]: row["count"] for row in rows}

    async def update_question_review_status(
        self,
        question_id: int,
        review_status: str,
        difficulty: Optional[int] = None,
    ) -> bool:
        """Update question's review_status and optionally difficulty."""
        updates = ["review_status = ?"]
        params: list[Any] = [review_status]

        if difficulty is not None:
            updates.append("difficulty = ?")
            params.append(difficulty)

        params.append(question_id)
        await self.db.execute(
            f"UPDATE questions SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()
        return True

    # =========================================================================
    # Admin Web GUI - Generic Table Operations
    # =========================================================================

    async def get_all_tables(self) -> list[dict[str, Any]]:
        """Get all table names with row counts."""
        async with self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ) as cursor:
            table_rows = await cursor.fetchall()

        tables = []
        for row in table_rows:
            name = row["name"]
            async with self.db.execute(f"SELECT COUNT(*) as count FROM [{name}]") as count_cursor:
                count_row = await count_cursor.fetchone()
                count = count_row["count"] if count_row else 0
            tables.append({"name": name, "count": count})

        return sorted(tables, key=lambda t: t["name"])

    async def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Get column info for a table."""
        # Validate table name first
        tables = await self.get_all_tables()
        if table_name not in [t["name"] for t in tables]:
            raise ValueError(f"Invalid table: {table_name}")

        async with self.db.execute(f"PRAGMA table_info([{table_name}])") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "name": row[1],
                    "type": row[2],
                    "nullable": not row[3],
                    "pk": bool(row[5]),
                }
                for row in rows
            ]

    async def browse_table(
        self,
        table_name: str,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        sort_col: Optional[str] = None,
        sort_dir: str = "asc",
    ) -> dict[str, Any]:
        """Browse table with pagination, search, sorting."""
        # Validate table
        tables = await self.get_all_tables()
        if table_name not in [t["name"] for t in tables]:
            raise ValueError(f"Invalid table: {table_name}")

        schema = await self.get_table_schema(table_name)
        columns = [c["name"] for c in schema]

        # Base query
        query = f"SELECT * FROM [{table_name}]"
        count_query = f"SELECT COUNT(*) as count FROM [{table_name}]"
        params: list[Any] = []

        # Search (across text columns)
        if search:
            text_cols = [c["name"] for c in schema if "TEXT" in (c["type"] or "").upper()]
            if text_cols:
                conditions = " OR ".join(f"[{col}] LIKE ?" for col in text_cols)
                query += f" WHERE ({conditions})"
                count_query += f" WHERE ({conditions})"
                params.extend([f"%{search}%"] * len(text_cols))

        # Count total
        async with self.db.execute(count_query, params) as cursor:
            count_row = await cursor.fetchone()
            total = count_row["count"] if count_row else 0

        # Sort
        if sort_col and sort_col in columns:
            direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
            query += f" ORDER BY [{sort_col}] {direction}"

        # Paginate
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            row_dicts = [dict(zip(columns, row)) for row in rows]

        return {
            "rows": row_dicts,
            "columns": columns,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total > 0 else 1,
        }

    async def get_record(self, table_name: str, record_id: int) -> Optional[dict[str, Any]]:
        """Get single record by id."""
        schema = await self.get_table_schema(table_name)
        columns = [c["name"] for c in schema]
        pk_col = next((c["name"] for c in schema if c["pk"]), "id")

        async with self.db.execute(
            f"SELECT * FROM [{table_name}] WHERE [{pk_col}] = ?",
            [record_id],
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None

    # =========================================================================
    # Admin Notification Settings Operations
    # =========================================================================

    async def get_admin_notification_setting(
        self,
        admin_id: int,
        event_type: str,
    ) -> Optional[dict[str, Any]]:
        """Get notification settings for a specific event type."""
        async with self.db.execute(
            """
            SELECT * FROM admin_notification_settings
            WHERE admin_telegram_id = ? AND event_type = ?
            """,
            (admin_id, event_type),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_admin_notification_settings(
        self,
        admin_id: int,
    ) -> list[dict[str, Any]]:
        """Get all notification settings for an admin."""
        async with self.db.execute(
            """
            SELECT * FROM admin_notification_settings
            WHERE admin_telegram_id = ?
            ORDER BY event_type
            """,
            (admin_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_admin_notification_setting(
        self,
        admin_id: int,
        event_type: str,
        realtime_enabled: Optional[bool] = None,
        summary_enabled: Optional[bool] = None,
    ) -> None:
        """Update or create notification setting for an event type."""
        existing = await self.get_admin_notification_setting(admin_id, event_type)

        if existing:
            # Update existing
            updates = []
            params: list[Any] = []

            if realtime_enabled is not None:
                updates.append("realtime_enabled = ?")
                params.append(realtime_enabled)
            if summary_enabled is not None:
                updates.append("summary_enabled = ?")
                params.append(summary_enabled)

            if updates:
                params.extend([admin_id, event_type])
                await self.db.execute(
                    f"""
                    UPDATE admin_notification_settings
                    SET {", ".join(updates)}
                    WHERE admin_telegram_id = ? AND event_type = ?
                    """,
                    params,
                )
        else:
            # Create new
            await self.db.execute(
                """
                INSERT INTO admin_notification_settings
                (admin_telegram_id, event_type, realtime_enabled, summary_enabled)
                VALUES (?, ?, ?, ?)
                """,
                (
                    admin_id,
                    event_type,
                    realtime_enabled if realtime_enabled is not None else True,
                    summary_enabled if summary_enabled is not None else True,
                ),
            )

        await self.db.commit()

    async def update_all_admin_notification_settings(
        self,
        admin_id: int,
        event_types: list[str],
        realtime_enabled: Optional[bool] = None,
        summary_enabled: Optional[bool] = None,
    ) -> None:
        """Update notification settings for all event types."""
        for event_type in event_types:
            await self.update_admin_notification_setting(
                admin_id, event_type, realtime_enabled, summary_enabled
            )

    # =========================================================================
    # Notification Log Operations
    # =========================================================================

    async def log_notification_event(
        self,
        event_type: str,
        priority: str,
        title: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Log a notification event for tracking and summaries."""
        metadata_json = json.dumps(metadata) if metadata else None

        async with self.db.execute(
            """
            INSERT INTO notification_log
            (event_type, priority, title, message, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, priority, title, message, metadata_json),
        ) as cursor:
            await self.db.commit()
            return cursor.lastrowid or 0

    async def mark_notification_sent(self, log_id: int) -> None:
        """Mark a notification as sent."""
        await self.db.execute(
            """
            UPDATE notification_log
            SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (log_id,),
        )
        await self.db.commit()

    async def get_unsummarized_events(
        self,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get events that haven't been included in a summary yet."""
        async with self.db.execute(
            """
            SELECT * FROM notification_log
            WHERE included_in_summary_at IS NULL
            AND created_at > datetime('now', ? || ' hours')
            ORDER BY created_at ASC
            """,
            (f"-{hours}",),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except json.JSONDecodeError:
                        pass
                result.append(d)
            return result

    async def mark_events_summarized(self, event_ids: list[int]) -> None:
        """Mark events as included in a summary."""
        if not event_ids:
            return

        placeholders = ",".join("?" * len(event_ids))
        await self.db.execute(
            f"""
            UPDATE notification_log
            SET included_in_summary_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            event_ids,
        )
        await self.db.commit()

    async def get_event_counts_by_type(
        self,
        hours: int = 24,
    ) -> dict[str, int]:
        """Get count of events by type for the last N hours."""
        async with self.db.execute(
            """
            SELECT event_type, COUNT(*) as count
            FROM notification_log
            WHERE created_at > datetime('now', ? || ' hours')
            GROUP BY event_type
            """,
            (f"-{hours}",),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row["event_type"]: row["count"] for row in rows}

    async def get_recent_notification_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent notification events with optional filtering."""
        query = "SELECT * FROM notification_log WHERE 1=1"
        params: list[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except json.JSONDecodeError:
                        pass
                result.append(d)
            return result


# Global repository instance
_repository: Optional[Repository] = None


async def get_repository(db_path: str) -> Repository:
    """Get or create the global repository instance."""
    global _repository
    if _repository is None:
        _repository = Repository(db_path)
        await _repository.connect()
    return _repository


async def close_repository() -> None:
    """Close the global repository instance."""
    global _repository
    if _repository is not None:
        await _repository.close()
        _repository = None
