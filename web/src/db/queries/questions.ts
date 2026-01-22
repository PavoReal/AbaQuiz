import { getDb } from "../connection";

export interface Question {
  id: number;
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  explanation: string;
  content_area: string;
  category: string;
  created_at: string;
  model: string | null;
  source_citation: string | null;
  review_status: string;
  difficulty: number | null;
}

export interface QuestionStats {
  question_id: number;
  times_shown: number;
  times_answered: number;
  correct_count: number;
  incorrect_count: number;
  option_a_count: number;
  option_b_count: number;
  option_c_count: number;
  option_d_count: number;
}

export interface QuestionFilters {
  content_area?: string;
  review_status?: string;
  difficulty?: number;
  model?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

/**
 * Get questions with optional filters.
 */
export function getQuestions(filters: QuestionFilters = {}): Question[] {
  const db = getDb();
  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (filters.content_area) {
    conditions.push("content_area = ?");
    params.push(filters.content_area);
  }

  if (filters.review_status) {
    conditions.push("review_status = ?");
    params.push(filters.review_status);
  }

  if (filters.difficulty) {
    conditions.push("difficulty = ?");
    params.push(filters.difficulty);
  }

  if (filters.model) {
    conditions.push("model = ?");
    params.push(filters.model);
  }

  if (filters.search) {
    conditions.push(
      "(question_text LIKE ? OR explanation LIKE ? OR option_a LIKE ? OR option_b LIKE ? OR option_c LIKE ? OR option_d LIKE ?)"
    );
    const searchPattern = `%${filters.search}%`;
    params.push(
      searchPattern,
      searchPattern,
      searchPattern,
      searchPattern,
      searchPattern,
      searchPattern
    );
  }

  let sql = "SELECT * FROM questions";
  if (conditions.length > 0) {
    sql += ` WHERE ${conditions.join(" AND ")}`;
  }
  sql += " ORDER BY created_at DESC";

  if (filters.limit) {
    sql += ` LIMIT ${filters.limit}`;
    if (filters.offset) {
      sql += ` OFFSET ${filters.offset}`;
    }
  }

  return db.prepare(sql).all(...params) as Question[];
}

/**
 * Get a single question by ID.
 */
export function getQuestionById(id: number): Question | null {
  const db = getDb();
  return (
    (db.prepare("SELECT * FROM questions WHERE id = ?").get(id) as Question) ||
    null
  );
}

/**
 * Get question statistics.
 */
export function getQuestionStats(questionId: number): QuestionStats | null {
  const db = getDb();
  return (
    (db
      .prepare("SELECT * FROM question_stats WHERE question_id = ?")
      .get(questionId) as QuestionStats) || null
  );
}

/**
 * Count total questions with optional filters.
 */
export function countQuestions(filters: Omit<QuestionFilters, "limit" | "offset"> = {}): number {
  const db = getDb();
  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (filters.content_area) {
    conditions.push("content_area = ?");
    params.push(filters.content_area);
  }

  if (filters.review_status) {
    conditions.push("review_status = ?");
    params.push(filters.review_status);
  }

  if (filters.difficulty) {
    conditions.push("difficulty = ?");
    params.push(filters.difficulty);
  }

  if (filters.search) {
    conditions.push(
      "(question_text LIKE ? OR explanation LIKE ?)"
    );
    const searchPattern = `%${filters.search}%`;
    params.push(searchPattern, searchPattern);
  }

  let sql = "SELECT COUNT(*) as count FROM questions";
  if (conditions.length > 0) {
    sql += ` WHERE ${conditions.join(" AND ")}`;
  }

  const result = db.prepare(sql).get(...params) as { count: number };
  return result.count;
}

/**
 * Update question review status.
 */
export function updateReviewStatus(
  questionId: number,
  status: string
): void {
  const db = getDb();
  db.prepare("UPDATE questions SET review_status = ? WHERE id = ?").run(
    status,
    questionId
  );
}

/**
 * Update question.
 */
export function updateQuestion(
  questionId: number,
  updates: Partial<Question>
): void {
  const db = getDb();
  const fields: string[] = [];
  const params: (string | number | null)[] = [];

  for (const [key, value] of Object.entries(updates)) {
    if (key !== "id" && key !== "created_at") {
      fields.push(`${key} = ?`);
      params.push(value as string | number | null);
    }
  }

  if (fields.length > 0) {
    params.push(questionId);
    db.prepare(`UPDATE questions SET ${fields.join(", ")} WHERE id = ?`).run(
      ...params
    );
  }
}

/**
 * Delete question.
 */
export function deleteQuestion(questionId: number): void {
  const db = getDb();
  db.prepare("DELETE FROM questions WHERE id = ?").run(questionId);
}

/**
 * Get content area distribution.
 */
export function getContentAreaDistribution(): Record<string, number> {
  const db = getDb();
  const rows = db
    .prepare(
      "SELECT content_area, COUNT(*) as count FROM questions GROUP BY content_area"
    )
    .all() as Array<{ content_area: string; count: number }>;

  const distribution: Record<string, number> = {};
  for (const row of rows) {
    distribution[row.content_area] = row.count;
  }
  return distribution;
}

/**
 * Get review status distribution.
 */
export function getReviewStatusDistribution(): Record<string, number> {
  const db = getDb();
  const rows = db
    .prepare(
      "SELECT review_status, COUNT(*) as count FROM questions GROUP BY review_status"
    )
    .all() as Array<{ review_status: string; count: number }>;

  const distribution: Record<string, number> = {};
  for (const row of rows) {
    distribution[row.review_status] = row.count;
  }
  return distribution;
}
