import { getDb } from "../connection";

export interface User {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  timezone: string;
  created_at: string;
  last_active_at: string | null;
  is_active: boolean;
  focus_preferences: string | null;
}

export interface UserStats {
  user_id: number;
  total_answered: number;
  correct_answers: number;
  incorrect_answers: number;
  current_streak: number;
  longest_streak: number;
  points: number;
  last_answer_date: string | null;
}

export interface UserFilters {
  search?: string;
  is_active?: boolean;
  is_banned?: boolean;
  limit?: number;
  offset?: number;
}

/**
 * Get users with optional filters.
 */
export function getUsers(filters: UserFilters = {}): User[] {
  const db = getDb();
  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (filters.search) {
    conditions.push(
      "(username LIKE ? OR first_name LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?)"
    );
    const searchPattern = `%${filters.search}%`;
    params.push(searchPattern, searchPattern, searchPattern);
  }

  if (filters.is_active !== undefined) {
    conditions.push("is_active = ?");
    params.push(filters.is_active ? 1 : 0);
  }

  if (filters.is_banned !== undefined) {
    if (filters.is_banned) {
      conditions.push(
        "telegram_id IN (SELECT telegram_id FROM banned_users)"
      );
    } else {
      conditions.push(
        "telegram_id NOT IN (SELECT telegram_id FROM banned_users)"
      );
    }
  }

  let sql = "SELECT * FROM users";
  if (conditions.length > 0) {
    sql += ` WHERE ${conditions.join(" AND ")}`;
  }
  sql += " ORDER BY last_active_at DESC NULLS LAST";

  if (filters.limit) {
    sql += ` LIMIT ${filters.limit}`;
    if (filters.offset) {
      sql += ` OFFSET ${filters.offset}`;
    }
  }

  return db.prepare(sql).all(...params) as User[];
}

/**
 * Get user by Telegram ID.
 */
export function getUserByTelegramId(telegramId: number): User | null {
  const db = getDb();
  return (
    (db
      .prepare("SELECT * FROM users WHERE telegram_id = ?")
      .get(telegramId) as User) || null
  );
}

/**
 * Get user statistics.
 */
export function getUserStats(userId: number): UserStats | null {
  const db = getDb();
  return (
    (db
      .prepare("SELECT * FROM user_stats WHERE user_id = ?")
      .get(userId) as UserStats) || null
  );
}

/**
 * Count total users with optional filters.
 */
export function countUsers(filters: Omit<UserFilters, "limit" | "offset"> = {}): number {
  const db = getDb();
  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (filters.search) {
    conditions.push(
      "(username LIKE ? OR first_name LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?)"
    );
    const searchPattern = `%${filters.search}%`;
    params.push(searchPattern, searchPattern, searchPattern);
  }

  if (filters.is_active !== undefined) {
    conditions.push("is_active = ?");
    params.push(filters.is_active ? 1 : 0);
  }

  let sql = "SELECT COUNT(*) as count FROM users";
  if (conditions.length > 0) {
    sql += ` WHERE ${conditions.join(" AND ")}`;
  }

  const result = db.prepare(sql).get(...params) as { count: number };
  return result.count;
}

/**
 * Check if user is banned.
 */
export function isUserBanned(telegramId: number): boolean {
  const db = getDb();
  const result = db
    .prepare("SELECT 1 FROM banned_users WHERE telegram_id = ?")
    .get(telegramId);
  return !!result;
}

/**
 * Ban a user.
 */
export function banUser(telegramId: number, reason: string | null, bannedBy: number): void {
  const db = getDb();
  db.prepare(
    "INSERT OR REPLACE INTO banned_users (telegram_id, reason, banned_by, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)"
  ).run(telegramId, reason, bannedBy);
}

/**
 * Unban a user.
 */
export function unbanUser(telegramId: number): void {
  const db = getDb();
  db.prepare("DELETE FROM banned_users WHERE telegram_id = ?").run(telegramId);
}

/**
 * Get count of active users (answered in last N days).
 */
export function getActiveUserCount(days: number = 7): number {
  const db = getDb();
  const result = db
    .prepare(
      `SELECT COUNT(DISTINCT user_id) as count FROM user_answers
       WHERE answered_at > datetime('now', '-${days} days')`
    )
    .get() as { count: number };
  return result.count;
}

/**
 * Get user's answer history.
 */
export function getUserAnswerHistory(
  userId: number,
  limit: number = 20
): Array<{
  question_id: number;
  user_answer: string;
  is_correct: boolean;
  answered_at: string;
}> {
  const db = getDb();
  return db
    .prepare(
      `SELECT question_id, user_answer, is_correct, answered_at
       FROM user_answers
       WHERE user_id = ?
       ORDER BY answered_at DESC
       LIMIT ?`
    )
    .all(userId, limit) as Array<{
    question_id: number;
    user_answer: string;
    is_correct: boolean;
    answered_at: string;
  }>;
}

/**
 * Get user's achievements.
 */
export function getUserAchievements(userId: number): Array<{
  achievement_type: string;
  earned_at: string;
}> {
  const db = getDb();
  return db
    .prepare(
      "SELECT achievement_type, earned_at FROM achievements WHERE user_id = ? ORDER BY earned_at DESC"
    )
    .all(userId) as Array<{ achievement_type: string; earned_at: string }>;
}
