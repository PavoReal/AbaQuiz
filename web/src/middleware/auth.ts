import { Context, Next } from "hono";
import { getCookie } from "hono/cookie";
import { verifySession, SESSION_COOKIE, AdminSession } from "../auth/session";

// Extend Hono's context to include admin session
declare module "hono" {
  interface ContextVariableMap {
    admin: AdminSession;
  }
}

/**
 * Authentication middleware.
 * Redirects to login page if not authenticated.
 */
export async function authMiddleware(c: Context, next: Next) {
  const token = getCookie(c, SESSION_COOKIE);

  if (!token) {
    // Check if this is an API request
    if (c.req.path.startsWith("/api/")) {
      return c.json({ error: "Unauthorized" }, 401);
    }
    return c.redirect("/auth/login");
  }

  const session = await verifySession(token);

  if (!session) {
    // Invalid or expired token
    if (c.req.path.startsWith("/api/")) {
      return c.json({ error: "Session expired" }, 401);
    }
    return c.redirect("/auth/login");
  }

  // Store session in context for use in handlers
  c.set("admin", session);

  await next();
}

/**
 * Super admin middleware.
 * Requires user to be a super admin.
 */
export async function superAdminMiddleware(c: Context, next: Next) {
  const admin = c.get("admin");

  if (!admin || !admin.isSuper) {
    if (c.req.path.startsWith("/api/")) {
      return c.json({ error: "Forbidden: Super admin required" }, 403);
    }
    return c.redirect("/dashboard?error=forbidden");
  }

  await next();
}

/**
 * Get current admin from context.
 */
export function getAdmin(c: Context): AdminSession {
  return c.get("admin");
}
