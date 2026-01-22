import { Hono } from "hono";
import { getDb } from "../db/connection";
import { getAdmin } from "../middleware/auth";
import { countUsers, getActiveUserCount } from "../db/queries/users";

export const broadcastRoutes = new Hono();

broadcastRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const db = getDb();

  const totalUsers = countUsers();
  const activeUsers = getActiveUserCount(7);

  // Get broadcast queue
  const queue = db.prepare(`
    SELECT * FROM broadcast_queue
    ORDER BY created_at DESC
    LIMIT 20
  `).all() as any[];

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Broadcast - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true, targetFilter: 'all' }">
  <div class="flex">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ 'w-64': sidebarOpen, 'w-16': !sidebarOpen }">
      <div class="p-4 border-b border-slate-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-sm">AQ</span>
          </div>
          <span x-show="sidebarOpen" class="font-display font-bold text-slate-900">AbaQuiz</span>
        </div>
      </div>
      <nav class="flex-1 py-4 overflow-y-auto">
        <div class="space-y-1">
          <a href="/dashboard" class="sidebar-link">Dashboard</a>
          <a href="/questions" class="sidebar-link">Questions</a>
          <a href="/review" class="sidebar-link">Review</a>
          <a href="/users" class="sidebar-link">Users</a>
          <a href="/analytics" class="sidebar-link">Analytics</a>
          <a href="/broadcast" class="sidebar-link active">Broadcast</a>
          <a href="/generation" class="sidebar-link">Generation</a>
        </div>
      </nav>
      <div class="p-4 border-t border-slate-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center text-slate-600 text-sm font-medium">${admin.firstName.charAt(0)}</div>
          <div x-show="sidebarOpen" class="flex-1 min-w-0">
            <p class="text-sm font-medium text-slate-900 truncate">${admin.firstName}</p>
          </div>
        </div>
      </div>
    </aside>

    <main class="flex-1 min-h-screen">
      <header class="bg-white border-b border-slate-200 px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <button @click="sidebarOpen = !sidebarOpen" class="text-slate-500 hover:text-slate-700">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <h1 class="text-xl font-display font-bold text-slate-900">Broadcast</h1>
          </div>
        </div>
      </header>

      <div class="p-6">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Compose form -->
          <div class="lg:col-span-2">
            <div class="card p-6">
              <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Compose Message</h2>

              <form hx-post="/api/broadcasts" hx-swap="innerHTML" hx-target="#queue-list">
                <div class="mb-4">
                  <label class="label">Message</label>
                  <textarea name="message_text" rows="6" class="input" placeholder="Enter your broadcast message..." required></textarea>
                </div>

                <div class="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label class="label">Format</label>
                    <select name="message_format" class="input">
                      <option value="text">Plain Text</option>
                      <option value="markdown">Markdown</option>
                      <option value="html">HTML</option>
                    </select>
                  </div>
                  <div>
                    <label class="label">Target Audience</label>
                    <select name="target_filter" class="input" x-model="targetFilter">
                      <option value="all">All Users (${totalUsers})</option>
                      <option value="active">Active Users (${activeUsers})</option>
                    </select>
                  </div>
                </div>

                <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <p class="text-amber-800 text-sm">
                    <strong>Warning:</strong> This will send a message to
                    <span x-text="targetFilter === 'all' ? '${totalUsers}' : '${activeUsers}'"></span> users.
                  </p>
                </div>

                <button type="submit" class="btn btn-primary">Queue Broadcast</button>
              </form>
            </div>
          </div>

          <!-- Queue list -->
          <div>
            <div class="card p-6">
              <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Recent Broadcasts</h2>
              <div id="queue-list" class="space-y-3">
                ${queue.length > 0 ? queue.map((b) => `
                  <div class="p-3 bg-slate-50 rounded-lg">
                    <div class="flex justify-between items-start mb-2">
                      <span class="badge ${b.status === 'completed' ? 'badge-green' : b.status === 'failed' ? 'badge-red' : 'badge-yellow'}">${b.status}</span>
                      <span class="text-xs text-slate-500">${new Date(b.created_at).toLocaleString()}</span>
                    </div>
                    <p class="text-sm text-slate-700 line-clamp-2">${b.message_text.substring(0, 100)}${b.message_text.length > 100 ? '...' : ''}</p>
                    ${b.sent_count ? `<p class="text-xs text-slate-500 mt-2">Sent to ${b.sent_count} users</p>` : ''}
                  </div>
                `).join('') : '<p class="text-sm text-slate-500">No broadcasts yet</p>'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</body>
</html>`;

  return c.html(html);
});
