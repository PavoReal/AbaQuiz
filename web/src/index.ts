import { Hono } from "hono";
import { serveStatic } from "hono/bun";
import { logger } from "hono/logger";
import { cors } from "hono/cors";
import { secureHeaders } from "hono/secure-headers";

import { authRoutes } from "./routes/auth";
import { dashboardRoutes } from "./routes/dashboard";
import { questionRoutes } from "./routes/questions";
import { reviewRoutes } from "./routes/review";
import { userRoutes } from "./routes/users";
import { analyticsRoutes } from "./routes/analytics";
import { broadcastRoutes } from "./routes/broadcast";
import { generationRoutes } from "./routes/generation";
import { adminMgmtRoutes } from "./routes/admin-mgmt";
import { apiRoutes } from "./api";
import { wsHandler } from "./ws";
import { authMiddleware } from "./middleware/auth";
import { db, initDb } from "./db/connection";

const app = new Hono();

// Global middleware
app.use("*", logger());
app.use("*", secureHeaders());
app.use("*", cors());

// Static files
app.use("/static/*", serveStatic({ root: "./" }));

// Public routes (no auth required)
app.route("/auth", authRoutes);

// Protected routes (auth required)
app.use("/dashboard/*", authMiddleware);
app.use("/questions/*", authMiddleware);
app.use("/review/*", authMiddleware);
app.use("/users/*", authMiddleware);
app.use("/analytics/*", authMiddleware);
app.use("/broadcast/*", authMiddleware);
app.use("/generation/*", authMiddleware);
app.use("/admin-mgmt/*", authMiddleware);
app.use("/api/*", authMiddleware);

// Mount routes
app.route("/dashboard", dashboardRoutes);
app.route("/questions", questionRoutes);
app.route("/review", reviewRoutes);
app.route("/users", userRoutes);
app.route("/analytics", analyticsRoutes);
app.route("/broadcast", broadcastRoutes);
app.route("/generation", generationRoutes);
app.route("/admin-mgmt", adminMgmtRoutes);
app.route("/api", apiRoutes);

// WebSocket endpoint
app.get("/ws", wsHandler);

// Root redirect to dashboard or login
app.get("/", async (c) => {
  return c.redirect("/dashboard");
});

// Health check
app.get("/health", (c) => {
  return c.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Initialize database and start server
const PORT = parseInt(process.env.WEB_PORT || "8070");
const HOST = process.env.WEB_HOST || "0.0.0.0";

console.log(`Initializing database...`);
await initDb();

console.log(`Starting web admin server on ${HOST}:${PORT}`);

export default {
  port: PORT,
  hostname: HOST,
  fetch: app.fetch,
};
