import { sign, verify } from "hono/jwt";

export interface AdminSession {
  telegramId: number;
  username: string | null;
  firstName: string;
  isSuper: boolean;
  photoUrl?: string;
  exp: number;
}

const JWT_SECRET = process.env.JWT_SECRET || "change-me-in-production";
const SESSION_DURATION = 7 * 24 * 60 * 60; // 7 days in seconds

/**
 * Create a new session token for an admin.
 */
export async function createSession(admin: {
  telegram_id: number;
  username: string | null;
  first_name: string;
  is_super: boolean;
  photo_url?: string;
}): Promise<string> {
  const payload: AdminSession = {
    telegramId: admin.telegram_id,
    username: admin.username,
    firstName: admin.first_name,
    isSuper: admin.is_super,
    photoUrl: admin.photo_url,
    exp: Math.floor(Date.now() / 1000) + SESSION_DURATION,
  };
  return await sign(payload, JWT_SECRET);
}

/**
 * Verify and decode a session token.
 */
export async function verifySession(
  token: string
): Promise<AdminSession | null> {
  try {
    const payload = await verify(token, JWT_SECRET);
    return payload as AdminSession;
  } catch {
    return null;
  }
}

/**
 * Get the session cookie name.
 */
export const SESSION_COOKIE = "abaquiz_session";
