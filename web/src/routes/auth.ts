import { Hono } from "hono";
import { setCookie, deleteCookie, getCookie } from "hono/cookie";
import {
  verifyTelegramAuth,
  verifyTelegramAuthAlt,
  parseTelegramCallback,
} from "../auth/telegram";
import { createSession, verifySession, SESSION_COOKIE } from "../auth/session";
import { isAdmin, getAdminByTelegramId } from "../db/queries/admin";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const BOT_USERNAME = process.env.TELEGRAM_BOT_USERNAME || "AbaQuizBot";

export const authRoutes = new Hono();

/**
 * Login page with Telegram Login Widget.
 */
authRoutes.get("/login", async (c) => {
  // Check if already logged in
  const token = getCookie(c, SESSION_COOKIE);
  if (token) {
    const session = await verifySession(token);
    if (session) {
      return c.redirect("/dashboard");
    }
  }

  const error = c.req.query("error");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center">
  <div class="w-full max-w-md p-8">
    <div class="card p-8 text-center">
      <div class="mb-6">
        <h1 class="text-2xl font-display font-bold text-slate-900 mb-2">AbaQuiz Admin</h1>
        <p class="text-slate-500">Sign in with your Telegram account</p>
      </div>

      ${
        error
          ? `<div class="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        ${error === "not_admin" ? "You are not authorized to access the admin panel." : "Authentication failed. Please try again."}
      </div>`
          : ""
      }

      <div class="flex justify-center mb-6">
        <script async src="https://telegram.org/js/telegram-widget.js?22"
          data-telegram-login="${BOT_USERNAME}"
          data-size="large"
          data-radius="8"
          data-auth-url="${c.req.url.replace("/login", "/callback")}"
          data-request-access="write">
        </script>
      </div>

      <p class="text-xs text-slate-400">
        Only authorized administrators can access this panel.
      </p>
    </div>
  </div>
</body>
</html>`;

  return c.html(html);
});

/**
 * Telegram OAuth callback handler.
 */
authRoutes.get("/callback", async (c) => {
  const url = new URL(c.req.url);
  const telegramUser = parseTelegramCallback(url.searchParams);

  if (!telegramUser) {
    return c.redirect("/auth/login?error=invalid_data");
  }

  // Verify the hash from Telegram
  // Try both verification methods
  const isValid =
    verifyTelegramAuth(telegramUser, BOT_TOKEN) ||
    verifyTelegramAuthAlt(telegramUser, BOT_TOKEN);

  if (!isValid) {
    console.error("Telegram auth verification failed for user:", telegramUser.id);
    return c.redirect("/auth/login?error=invalid_hash");
  }

  // Check if user is an admin
  if (!isAdmin(telegramUser.id)) {
    console.warn("Non-admin user attempted login:", telegramUser.id, telegramUser.username);
    return c.redirect("/auth/login?error=not_admin");
  }

  // Get admin details from database
  const admin = getAdminByTelegramId(telegramUser.id);
  if (!admin) {
    return c.redirect("/auth/login?error=not_admin");
  }

  // Create session
  const sessionToken = await createSession({
    telegram_id: telegramUser.id,
    username: telegramUser.username || null,
    first_name: telegramUser.first_name,
    is_super: admin.is_super,
    photo_url: telegramUser.photo_url,
  });

  // Set session cookie
  setCookie(c, SESSION_COOKIE, sessionToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "Lax",
    maxAge: 7 * 24 * 60 * 60, // 7 days
    path: "/",
  });

  console.log("Admin logged in:", telegramUser.id, telegramUser.username);

  return c.redirect("/dashboard");
});

/**
 * Logout handler.
 */
authRoutes.post("/logout", async (c) => {
  deleteCookie(c, SESSION_COOKIE, {
    path: "/",
  });
  return c.redirect("/auth/login");
});

authRoutes.get("/logout", async (c) => {
  deleteCookie(c, SESSION_COOKIE, {
    path: "/",
  });
  return c.redirect("/auth/login");
});

/**
 * Get current user info (API).
 */
authRoutes.get("/me", async (c) => {
  const token = getCookie(c, SESSION_COOKIE);
  if (!token) {
    return c.json({ error: "Not authenticated" }, 401);
  }

  const session = await verifySession(token);
  if (!session) {
    return c.json({ error: "Session expired" }, 401);
  }

  return c.json({
    telegramId: session.telegramId,
    username: session.username,
    firstName: session.firstName,
    isSuper: session.isSuper,
    photoUrl: session.photoUrl,
  });
});
