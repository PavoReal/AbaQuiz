import { Hono } from "hono";
import { getDb } from "../db/connection";
import { getAdmin } from "../middleware/auth";
import {
  getQuestions,
  getQuestionById,
  updateReviewStatus,
  updateQuestion,
  deleteQuestion,
} from "../db/queries/questions";
import {
  getAllAdmins,
  addAdmin,
  removeAdmin,
  updateAdminSuper,
  isAdmin,
} from "../db/queries/admin";
import { banUser, unbanUser, isUserBanned } from "../db/queries/users";
import { getPoolStats, getGenerationHistory } from "../db/queries/analytics";
import { getContentAreaLabel } from "../lib/utils";

export const apiRoutes = new Hono();

// ============ Questions API ============

apiRoutes.post("/questions/:id/approve", async (c) => {
  const id = parseInt(c.req.param("id"));
  updateReviewStatus(id, "approved");

  // Return next question for review flow
  const next = getQuestions({ review_status: "unreviewed", limit: 1 });
  if (next.length > 0) {
    return c.html(renderReviewQuestion(next[0]));
  }
  return c.html(renderNoMoreQuestions());
});

apiRoutes.post("/questions/:id/reject", async (c) => {
  const id = parseInt(c.req.param("id"));
  updateReviewStatus(id, "rejected");

  const next = getQuestions({ review_status: "unreviewed", limit: 1 });
  if (next.length > 0) {
    return c.html(renderReviewQuestion(next[0]));
  }
  return c.html(renderNoMoreQuestions());
});

apiRoutes.post("/questions/:id/skip", async (c) => {
  const id = parseInt(c.req.param("id"));

  // Get next question (skip current one)
  const questions = getQuestions({ review_status: "unreviewed", limit: 2 });
  const next = questions.find((q) => q.id !== id) || questions[0];

  if (next && next.id !== id) {
    return c.html(renderReviewQuestion(next));
  }
  return c.html(renderNoMoreQuestions());
});

apiRoutes.delete("/questions/:id", async (c) => {
  const id = parseInt(c.req.param("id"));
  deleteQuestion(id);
  return c.json({ success: true });
});

// ============ Users API ============

apiRoutes.post("/users/:id/ban", async (c) => {
  const telegramId = parseInt(c.req.param("id"));
  const admin = getAdmin(c);
  const body = await c.req.json().catch(() => ({}));

  banUser(telegramId, body.reason || null, admin.telegramId);
  return c.json({ success: true });
});

apiRoutes.post("/users/:id/unban", async (c) => {
  const telegramId = parseInt(c.req.param("id"));
  unbanUser(telegramId);
  return c.json({ success: true });
});

// ============ Broadcasts API ============

apiRoutes.post("/broadcasts", async (c) => {
  const admin = getAdmin(c);
  const formData = await c.req.formData();

  const messageText = formData.get("message_text") as string;
  const messageFormat = formData.get("message_format") as string || "text";
  const targetFilter = formData.get("target_filter") as string || "all";

  if (!messageText) {
    return c.json({ error: "Message text required" }, 400);
  }

  const db = getDb();
  db.prepare(`
    INSERT INTO broadcast_queue (message_text, message_format, target_filter, created_by)
    VALUES (?, ?, ?, ?)
  `).run(messageText, messageFormat, targetFilter, admin.telegramId);

  // Return updated queue list
  const queue = db.prepare(`
    SELECT * FROM broadcast_queue
    ORDER BY created_at DESC
    LIMIT 20
  `).all() as any[];

  return c.html(renderBroadcastQueue(queue));
});

apiRoutes.delete("/broadcasts/:id", async (c) => {
  const id = parseInt(c.req.param("id"));
  const db = getDb();

  db.prepare("DELETE FROM broadcast_queue WHERE id = ? AND status = 'pending'").run(id);
  return c.json({ success: true });
});

// ============ Generation API ============

apiRoutes.post("/generation/start", async (c) => {
  const admin = getAdmin(c);
  const formData = await c.req.formData();

  const count = parseInt(formData.get("count") as string) || 50;
  const skipDedup = formData.get("skip_dedup") === "on";

  const db = getDb();

  // Check for existing pending/processing generation
  const existing = db.prepare(`
    SELECT id FROM generation_queue WHERE status IN ('pending', 'processing')
  `).get();

  if (existing) {
    return c.json({ error: "Generation already in progress" }, 400);
  }

  // Insert generation request
  const result = db.prepare(`
    INSERT INTO generation_queue (requested_count, skip_dedup, created_by)
    VALUES (?, ?, ?)
  `).run(count, skipDedup ? 1 : 0, admin.telegramId);

  // Create progress entry
  db.prepare(`
    INSERT INTO generation_progress (queue_id) VALUES (?)
  `).run(result.lastInsertRowid);

  return c.redirect("/generation");
});

apiRoutes.get("/generation/progress/:id", async (c) => {
  const id = parseInt(c.req.param("id"));
  const db = getDb();

  const progress = db.prepare(`
    SELECT gq.*, gp.*
    FROM generation_queue gq
    LEFT JOIN generation_progress gp ON gq.id = gp.queue_id
    WHERE gq.id = ?
  `).get(id) as any;

  if (!progress) {
    return c.json({ error: "Not found" }, 404);
  }

  return c.html(renderGenerationProgress(progress));
});

apiRoutes.get("/generation/pool-stats", async (c) => {
  const stats = getPoolStats();
  return c.json(stats);
});

// ============ Admins API ============

apiRoutes.get("/admins", async (c) => {
  const admins = getAllAdmins();
  return c.json(admins);
});

apiRoutes.post("/admins", async (c) => {
  const admin = getAdmin(c);
  const formData = await c.req.formData();

  const telegramId = parseInt(formData.get("telegram_id") as string);
  const username = formData.get("username") as string || null;
  const isSuper = formData.get("is_super") === "true";

  if (!telegramId) {
    return c.json({ error: "Telegram ID required" }, 400);
  }

  if (isAdmin(telegramId)) {
    return c.json({ error: "Already an admin" }, 400);
  }

  addAdmin(telegramId, username, isSuper, admin.telegramId);

  // Return updated list
  const admins = getAllAdmins();
  return c.html(renderAdminList(admins, admin.telegramId));
});

apiRoutes.post("/admins/:id/toggle-super", async (c) => {
  const telegramId = parseInt(c.req.param("id"));
  const admin = getAdmin(c);
  const db = getDb();

  const current = db.prepare("SELECT is_super FROM admins WHERE telegram_id = ?").get(telegramId) as { is_super: number } | undefined;
  if (current) {
    updateAdminSuper(telegramId, !current.is_super);
  }

  const admins = getAllAdmins();
  return c.html(renderAdminList(admins, admin.telegramId));
});

apiRoutes.delete("/admins/:id", async (c) => {
  const telegramId = parseInt(c.req.param("id"));
  const admin = getAdmin(c);

  if (telegramId === admin.telegramId) {
    return c.json({ error: "Cannot remove yourself" }, 400);
  }

  removeAdmin(telegramId);

  const admins = getAllAdmins();
  return c.html(renderAdminList(admins, admin.telegramId));
});

// ============ Helper renderers ============

function renderReviewQuestion(question: any): string {
  return `
    <div class="card p-6 max-w-4xl">
      <div class="flex justify-between items-start mb-6">
        <div>
          <span class="font-mono-data text-slate-500">Question #${question.id}</span>
          <p class="text-sm text-slate-500 mt-1">${getContentAreaLabel(question.content_area)} &bull; ${question.category}</p>
        </div>
      </div>

      <div class="prose max-w-none mb-6">
        <p class="text-lg text-slate-900 leading-relaxed">${question.question_text}</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        ${["A", "B", "C", "D"].map((opt) => `
          <div class="p-4 rounded-lg ${question.correct_answer === opt ? "bg-emerald-50 border-2 border-emerald-300" : "bg-slate-50 border border-slate-200"}">
            <span class="font-bold ${question.correct_answer === opt ? "text-emerald-700" : "text-slate-700"}">${opt}.</span>
            <span class="${question.correct_answer === opt ? "text-emerald-700" : "text-slate-700"}">${question[`option_${opt.toLowerCase()}`]}</span>
          </div>
        `).join("")}
      </div>

      ${question.explanation ? `
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <h3 class="font-medium text-blue-900 mb-2">Explanation</h3>
          <p class="text-blue-800">${question.explanation}</p>
        </div>
      ` : ""}

      <div class="flex justify-between items-center pt-4 border-t border-slate-200">
        <div class="text-sm text-slate-500">
          Shortcuts: <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">A</kbd> Approve &bull;
          <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">R</kbd> Reject &bull;
          <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">N</kbd> Skip
        </div>
        <div class="flex gap-3">
          <button hx-post="/api/questions/${question.id}/skip" hx-target="#review-content" hx-swap="innerHTML" data-action="skip" class="btn btn-secondary">Skip</button>
          <button hx-post="/api/questions/${question.id}/reject" hx-target="#review-content" hx-swap="innerHTML" data-action="reject" class="btn btn-danger">Reject</button>
          <button hx-post="/api/questions/${question.id}/approve" hx-target="#review-content" hx-swap="innerHTML" data-action="approve" class="btn btn-success">Approve</button>
        </div>
      </div>
    </div>
  `;
}

function renderNoMoreQuestions(): string {
  return `
    <div class="card p-12 text-center">
      <div class="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
      </div>
      <h2 class="text-xl font-display font-bold text-slate-900 mb-2">All caught up!</h2>
      <p class="text-slate-500">No questions waiting for review.</p>
      <a href="/generation" class="btn btn-primary mt-4">Generate More Questions</a>
    </div>
  `;
}

function renderBroadcastQueue(queue: any[]): string {
  return queue.length > 0
    ? queue.map((b) => `
        <div class="p-3 bg-slate-50 rounded-lg">
          <div class="flex justify-between items-start mb-2">
            <span class="badge ${b.status === "completed" ? "badge-green" : b.status === "failed" ? "badge-red" : "badge-yellow"}">${b.status}</span>
            <span class="text-xs text-slate-500">${new Date(b.created_at).toLocaleString()}</span>
          </div>
          <p class="text-sm text-slate-700 line-clamp-2">${b.message_text.substring(0, 100)}${b.message_text.length > 100 ? "..." : ""}</p>
          ${b.sent_count ? `<p class="text-xs text-slate-500 mt-2">Sent to ${b.sent_count} users</p>` : ""}
        </div>
      `).join("")
    : '<p class="text-sm text-slate-500">No broadcasts yet</p>';
}

function renderGenerationProgress(progress: any): string {
  return `
    <div class="card p-6 mb-6" id="generation-progress" hx-get="/api/generation/progress/${progress.id}" hx-trigger="every 2s">
      <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Generation ${progress.status === "completed" ? "Complete" : "in Progress"}</h2>
      <div class="space-y-4">
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>Progress</span>
            <span>${progress.total_generated || 0} / ${progress.requested_count}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${((progress.total_generated || 0) / progress.requested_count * 100).toFixed(0)}%"></div>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-4 text-center">
          <div>
            <p class="text-2xl font-bold text-emerald-600">${progress.total_generated || 0}</p>
            <p class="text-sm text-slate-500">Generated</p>
          </div>
          <div>
            <p class="text-2xl font-bold text-amber-600">${progress.total_duplicates || 0}</p>
            <p class="text-sm text-slate-500">Duplicates</p>
          </div>
          <div>
            <p class="text-2xl font-bold text-red-600">${progress.total_errors || 0}</p>
            <p class="text-sm text-slate-500">Errors</p>
          </div>
        </div>
        ${progress.status !== "completed" ? `<p class="text-sm text-slate-500">Current area: ${progress.current_area || "Starting..."}</p>` : ""}
      </div>
    </div>
  `;
}

function renderAdminList(admins: any[], currentAdminId: number): string {
  return `
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th>Admin</th>
            <th>Telegram ID</th>
            <th>Role</th>
            <th>Added</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${admins.map((admin) => `
            <tr>
              <td>
                <p class="font-medium text-slate-900">${admin.username ? "@" + admin.username : "Unknown"}</p>
              </td>
              <td class="font-mono-data">${admin.telegram_id}</td>
              <td>
                <span class="badge ${admin.is_super ? "badge-blue" : "badge-gray"}">${admin.is_super ? "Super Admin" : "Admin"}</span>
              </td>
              <td class="text-slate-500">${new Date(admin.created_at).toLocaleDateString()}</td>
              <td>
                ${admin.telegram_id !== currentAdminId ? `
                  <div class="flex gap-2">
                    <button hx-post="/api/admins/${admin.telegram_id}/toggle-super" hx-target="#admin-list" hx-swap="innerHTML" class="text-sm text-blue-600 hover:underline">
                      ${admin.is_super ? "Demote" : "Promote"}
                    </button>
                    <button hx-delete="/api/admins/${admin.telegram_id}" hx-target="#admin-list" hx-swap="innerHTML" hx-confirm="Are you sure?" class="text-sm text-red-600 hover:underline">
                      Remove
                    </button>
                  </div>
                ` : '<span class="text-xs text-slate-400">You</span>'}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}
