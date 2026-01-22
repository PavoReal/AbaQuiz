import { getDb } from "../connection";

export interface Admin {
  id: number;
  telegram_id: number;
  username: string | null;
  is_super: boolean;
  added_by: number | null;
  created_at: string;
}

/**
 * Check if a Telegram user ID is an admin.
 */
export function isAdmin(telegramId: number): boolean {
  const db = getDb();
  const result = db
    .prepare("SELECT id FROM admins WHERE telegram_id = ?")
    .get(telegramId) as { id: number } | undefined;
  return !!result;
}

/**
 * Check if a Telegram user ID is a super admin.
 */
export function isSuperAdmin(telegramId: number): boolean {
  const db = getDb();
  const result = db
    .prepare("SELECT is_super FROM admins WHERE telegram_id = ?")
    .get(telegramId) as { is_super: number } | undefined;
  return result?.is_super === 1;
}

/**
 * Get admin by Telegram ID.
 */
export function getAdminByTelegramId(telegramId: number): Admin | null {
  const db = getDb();
  const result = db
    .prepare("SELECT * FROM admins WHERE telegram_id = ?")
    .get(telegramId) as Admin | undefined;
  return result || null;
}

/**
 * Get all admins.
 */
export function getAllAdmins(): Admin[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM admins ORDER BY created_at DESC")
    .all() as Admin[];
}

/**
 * Add a new admin.
 */
export function addAdmin(
  telegramId: number,
  username: string | null,
  isSuper: boolean,
  addedBy: number
): void {
  const db = getDb();
  db.prepare(
    "INSERT INTO admins (telegram_id, username, is_super, added_by) VALUES (?, ?, ?, ?)"
  ).run(telegramId, username, isSuper ? 1 : 0, addedBy);
}

/**
 * Remove an admin.
 */
export function removeAdmin(telegramId: number): void {
  const db = getDb();
  db.prepare("DELETE FROM admins WHERE telegram_id = ?").run(telegramId);
}

/**
 * Update admin's super status.
 */
export function updateAdminSuper(telegramId: number, isSuper: boolean): void {
  const db = getDb();
  db.prepare("UPDATE admins SET is_super = ? WHERE telegram_id = ?").run(
    isSuper ? 1 : 0,
    telegramId
  );
}
