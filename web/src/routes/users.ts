import { Hono } from "hono";
import { getUsers, countUsers, getUserByTelegramId, getUserStats, isUserBanned } from "../db/queries/users";
import { getAdmin } from "../middleware/auth";
import { paginate } from "../lib/utils";
import { isHtmxRequest } from "../lib/htmx";

export const userRoutes = new Hono();

/**
 * Users list page.
 */
userRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const page = parseInt(c.req.query("page") || "1");
  const search = c.req.query("search") || "";
  const filter = c.req.query("filter") || "";
  const pageSize = 50;

  const filters = {
    search: search || undefined,
    is_banned: filter === "banned" ? true : filter === "active" ? false : undefined,
  };

  const totalCount = countUsers(filters);
  const pagination = paginate(totalCount, page, pageSize);
  const users = getUsers({
    ...filters,
    limit: pageSize,
    offset: pagination.offset,
  });

  if (isHtmxRequest(c)) {
    return c.html(renderUsersTable(users, pagination, { search, filter }));
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Users - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true }">
  <div class="flex">
    <!-- Sidebar (same structure) -->
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
          <a href="/dashboard" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
            </svg>
            <span x-show="sidebarOpen">Dashboard</span>
          </a>
          <a href="/questions" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span x-show="sidebarOpen">Questions</span>
          </a>
          <a href="/review" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span x-show="sidebarOpen">Review</span>
          </a>
          <a href="/users" class="sidebar-link active">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <span x-show="sidebarOpen">Users</span>
          </a>
          <a href="/analytics" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
            </svg>
            <span x-show="sidebarOpen">Analytics</span>
          </a>
          <a href="/broadcast" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"/>
            </svg>
            <span x-show="sidebarOpen">Broadcast</span>
          </a>
          <a href="/generation" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
            </svg>
            <span x-show="sidebarOpen">Generation</span>
          </a>
        </div>
      </nav>
      <div class="p-4 border-t border-slate-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center text-slate-600 text-sm font-medium">
            ${admin.firstName.charAt(0)}
          </div>
          <div x-show="sidebarOpen" class="flex-1 min-w-0">
            <p class="text-sm font-medium text-slate-900 truncate">${admin.firstName}</p>
            <p class="text-xs text-slate-500 truncate">@${admin.username || "admin"}</p>
          </div>
          <a x-show="sidebarOpen" href="/auth/logout" class="text-slate-400 hover:text-slate-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </a>
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
            <h1 class="text-xl font-display font-bold text-slate-900">Users</h1>
          </div>
        </div>
      </header>

      <div class="p-6">
        <!-- Filters -->
        <div class="card p-4 mb-6">
          <form hx-get="/users" hx-target="#users-table" hx-push-url="true" class="flex flex-wrap gap-4 items-end">
            <div class="flex-1 min-w-[200px]">
              <label class="label">Search</label>
              <input type="text" name="search" value="${search}" placeholder="Username or Telegram ID..." class="input">
            </div>
            <div class="w-40">
              <label class="label">Status</label>
              <select name="filter" class="input">
                <option value="">All Users</option>
                <option value="active" ${filter === "active" ? "selected" : ""}>Active</option>
                <option value="banned" ${filter === "banned" ? "selected" : ""}>Banned</option>
              </select>
            </div>
            <div class="flex gap-2">
              <button type="submit" class="btn btn-primary">Filter</button>
              <a href="/users" class="btn btn-secondary">Clear</a>
            </div>
          </form>
        </div>

        <!-- Users table -->
        <div id="users-table">
          ${renderUsersTable(users, pagination, { search, filter })}
        </div>
      </div>
    </main>
  </div>
</body>
</html>`;

  return c.html(html);
});

function renderUsersTable(
  users: any[],
  pagination: ReturnType<typeof paginate>,
  filters: { search: string; filter: string }
): string {
  const queryParams = new URLSearchParams();
  if (filters.search) queryParams.set("search", filters.search);
  if (filters.filter) queryParams.set("filter", filters.filter);
  const baseUrl = `/users?${queryParams.toString()}`;

  return `
    <div class="card">
      <div class="px-4 py-3 border-b border-slate-200">
        <p class="text-sm text-slate-500">${pagination.totalItems.toLocaleString()} users found</p>
      </div>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr>
              <th>User</th>
              <th>Telegram ID</th>
              <th>Timezone</th>
              <th>Joined</th>
              <th>Last Active</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${users.map((u) => {
              const isBanned = isUserBanned(u.telegram_id);
              return `
                <tr>
                  <td>
                    <div>
                      <p class="font-medium text-slate-900">${u.first_name || 'Unknown'} ${u.last_name || ''}</p>
                      <p class="text-sm text-slate-500">${u.username ? '@' + u.username : ''}</p>
                    </div>
                  </td>
                  <td class="font-mono-data">${u.telegram_id}</td>
                  <td class="text-slate-500">${u.timezone || 'Not set'}</td>
                  <td class="text-slate-500">${new Date(u.created_at).toLocaleDateString()}</td>
                  <td class="text-slate-500">${u.last_active_at ? new Date(u.last_active_at).toLocaleDateString() : 'Never'}</td>
                  <td>
                    <span class="badge ${isBanned ? 'badge-red' : 'badge-green'}">${isBanned ? 'Banned' : 'Active'}</span>
                  </td>
                  <td>
                    <a href="/users/${u.telegram_id}" class="text-blue-600 hover:underline text-sm">View</a>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
      ${pagination.totalPages > 1 ? `
        <div class="px-4 py-3 border-t border-slate-200 flex justify-between items-center">
          <div class="flex gap-2">
            ${pagination.hasPrev ? `<a href="${baseUrl}&page=${pagination.page - 1}" hx-get="${baseUrl}&page=${pagination.page - 1}" hx-target="#users-table" class="btn btn-secondary text-sm">Previous</a>` : ""}
            ${pagination.hasNext ? `<a href="${baseUrl}&page=${pagination.page + 1}" hx-get="${baseUrl}&page=${pagination.page + 1}" hx-target="#users-table" class="btn btn-secondary text-sm">Next</a>` : ""}
          </div>
          <p class="text-sm text-slate-500">Page ${pagination.page} of ${pagination.totalPages}</p>
        </div>
      ` : ""}
    </div>
  `;
}
