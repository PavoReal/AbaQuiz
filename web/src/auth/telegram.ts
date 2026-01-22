import { createHmac } from "crypto";

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

/**
 * Verify Telegram Login Widget authentication data.
 *
 * The hash is calculated as:
 * 1. Create data-check-string from all fields except hash, sorted alphabetically
 * 2. Create secret key: HMAC-SHA256 of bot token using "WebAppData" as key
 * 3. Calculate hash: HMAC-SHA256 of data-check-string using secret key
 */
export function verifyTelegramAuth(
  user: TelegramUser,
  botToken: string
): boolean {
  const { hash, ...data } = user;

  // Create data check string (alphabetically sorted key=value pairs)
  const checkString = Object.keys(data)
    .sort()
    .map((k) => `${k}=${data[k as keyof typeof data]}`)
    .join("\n");

  // Create secret key from bot token
  // For Telegram Login Widget, use SHA256 of bot token directly
  const secretKey = createHmac("sha256", "WebAppData").update(botToken).digest();

  // Calculate expected hash
  const expectedHash = createHmac("sha256", secretKey)
    .update(checkString)
    .digest("hex");

  // Verify hash matches
  if (hash !== expectedHash) {
    return false;
  }

  // Check auth_date is recent (within 24 hours)
  const now = Math.floor(Date.now() / 1000);
  if (now - user.auth_date > 86400) {
    return false;
  }

  return true;
}

/**
 * Alternative verification method using direct SHA256 of bot token.
 * Some Telegram widgets use this method instead.
 */
export function verifyTelegramAuthAlt(
  user: TelegramUser,
  botToken: string
): boolean {
  const { hash, ...data } = user;

  // Create data check string (alphabetically sorted key=value pairs)
  const checkString = Object.keys(data)
    .sort()
    .map((k) => `${k}=${data[k as keyof typeof data]}`)
    .join("\n");

  // Create secret key: SHA256 hash of bot token
  const crypto = require("crypto");
  const secretKey = crypto.createHash("sha256").update(botToken).digest();

  // Calculate expected hash
  const expectedHash = createHmac("sha256", secretKey)
    .update(checkString)
    .digest("hex");

  // Verify hash matches
  if (hash !== expectedHash) {
    return false;
  }

  // Check auth_date is recent (within 24 hours)
  const now = Math.floor(Date.now() / 1000);
  if (now - user.auth_date > 86400) {
    return false;
  }

  return true;
}

/**
 * Parse Telegram auth callback data from URL parameters.
 */
export function parseTelegramCallback(params: URLSearchParams): TelegramUser | null {
  const id = params.get("id");
  const first_name = params.get("first_name");
  const auth_date = params.get("auth_date");
  const hash = params.get("hash");

  if (!id || !first_name || !auth_date || !hash) {
    return null;
  }

  return {
    id: parseInt(id, 10),
    first_name,
    last_name: params.get("last_name") || undefined,
    username: params.get("username") || undefined,
    photo_url: params.get("photo_url") || undefined,
    auth_date: parseInt(auth_date, 10),
    hash,
  };
}
