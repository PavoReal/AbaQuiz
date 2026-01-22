import { getDb } from "../connection";

export interface DailyStats {
  date: string;
  active_users: number;
  questions_answered: number;
  correct_count: number;
  new_users: number;
}

export interface ApiUsageStats {
  date: string;
  model: string;
  total_tokens: number;
  total_cost: number;
}

export interface PoolStats {
  total_questions: number;
  unreviewed_count: number;
  approved_count: number;
  rejected_count: number;
  content_area_distribution: Record<string, number>;
  active_users: number;
  avg_unseen_per_user: number;
}

/**
 * Get daily engagement statistics.
 */
export function getDailyEngagement(days: number = 30): DailyStats[] {
  const db = getDb();
  return db
    .prepare(
      `
      SELECT
        DATE(answered_at) as date,
        COUNT(DISTINCT user_id) as active_users,
        COUNT(*) as questions_answered,
        SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
        (SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE(answered_at)) as new_users
      FROM user_answers
      WHERE answered_at > datetime('now', '-${days} days')
      GROUP BY DATE(answered_at)
      ORDER BY date DESC
    `
    )
    .all() as DailyStats[];
}

/**
 * Get question performance by content area.
 */
export function getContentAreaPerformance(): Array<{
  content_area: string;
  total_answered: number;
  correct_rate: number;
  avg_time_ms: number | null;
}> {
  const db = getDb();
  return db
    .prepare(
      `
      SELECT
        q.content_area,
        COUNT(*) as total_answered,
        ROUND(AVG(CASE WHEN ua.is_correct = 1 THEN 100.0 ELSE 0.0 END), 1) as correct_rate,
        AVG(ua.response_time_ms) as avg_time_ms
      FROM user_answers ua
      JOIN questions q ON ua.question_id = q.id
      GROUP BY q.content_area
      ORDER BY q.content_area
    `
    )
    .all() as Array<{
    content_area: string;
    total_answered: number;
    correct_rate: number;
    avg_time_ms: number | null;
  }>;
}

/**
 * Get API usage and costs.
 */
export function getApiUsage(days: number = 30): ApiUsageStats[] {
  const db = getDb();
  return db
    .prepare(
      `
      SELECT
        DATE(created_at) as date,
        model,
        SUM(total_tokens) as total_tokens,
        SUM(cost) as total_cost
      FROM api_usage
      WHERE created_at > datetime('now', '-${days} days')
      GROUP BY DATE(created_at), model
      ORDER BY date DESC
    `
    )
    .all() as ApiUsageStats[];
}

/**
 * Get pool health statistics.
 */
export function getPoolStats(): PoolStats {
  const db = getDb();

  // Total questions
  const totalResult = db
    .prepare("SELECT COUNT(*) as count FROM questions")
    .get() as { count: number };

  // Review status counts
  const reviewCounts = db
    .prepare(
      `
      SELECT
        review_status,
        COUNT(*) as count
      FROM questions
      GROUP BY review_status
    `
    )
    .all() as Array<{ review_status: string; count: number }>;

  // Content area distribution
  const areaCounts = db
    .prepare(
      `
      SELECT
        content_area,
        COUNT(*) as count
      FROM questions
      GROUP BY content_area
    `
    )
    .all() as Array<{ content_area: string; count: number }>;

  // Active users (answered in last 7 days)
  const activeResult = db
    .prepare(
      `
      SELECT COUNT(DISTINCT user_id) as count
      FROM user_answers
      WHERE answered_at > datetime('now', '-7 days')
    `
    )
    .get() as { count: number };

  // Average unseen questions per active user
  // This is a simplified calculation
  const unseenResult = db
    .prepare(
      `
      SELECT
        ROUND(AVG(unseen_count), 1) as avg_unseen
      FROM (
        SELECT
          u.id as user_id,
          (SELECT COUNT(*) FROM questions) -
          (SELECT COUNT(*) FROM user_answers WHERE user_id = u.id) as unseen_count
        FROM users u
        WHERE u.id IN (
          SELECT DISTINCT user_id FROM user_answers
          WHERE answered_at > datetime('now', '-7 days')
        )
      )
    `
    )
    .get() as { avg_unseen: number | null };

  const reviewStatusMap: Record<string, number> = {};
  for (const row of reviewCounts) {
    reviewStatusMap[row.review_status] = row.count;
  }

  const contentAreaMap: Record<string, number> = {};
  for (const row of areaCounts) {
    contentAreaMap[row.content_area] = row.count;
  }

  return {
    total_questions: totalResult.count,
    unreviewed_count: reviewStatusMap["unreviewed"] || 0,
    approved_count: reviewStatusMap["approved"] || 0,
    rejected_count: reviewStatusMap["rejected"] || 0,
    content_area_distribution: contentAreaMap,
    active_users: activeResult.count,
    avg_unseen_per_user: unseenResult.avg_unseen || 0,
  };
}

/**
 * Get generation history.
 */
export function getGenerationHistory(limit: number = 20): Array<{
  id: number;
  requested_count: number;
  generated_count: number;
  duplicate_count: number;
  error_count: number;
  status: string;
  created_at: string;
  completed_at: string | null;
}> {
  const db = getDb();
  return db
    .prepare(
      `
      SELECT id, requested_count, generated_count, duplicate_count, error_count, status, created_at, completed_at
      FROM generation_queue
      ORDER BY created_at DESC
      LIMIT ?
    `
    )
    .all(limit) as Array<{
    id: number;
    requested_count: number;
    generated_count: number;
    duplicate_count: number;
    error_count: number;
    status: string;
    created_at: string;
    completed_at: string | null;
  }>;
}

/**
 * Get total API costs.
 */
export function getTotalApiCosts(days: number = 30): number {
  const db = getDb();
  const result = db
    .prepare(
      `
      SELECT COALESCE(SUM(cost), 0) as total
      FROM api_usage
      WHERE created_at > datetime('now', '-${days} days')
    `
    )
    .get() as { total: number };
  return result.total;
}
