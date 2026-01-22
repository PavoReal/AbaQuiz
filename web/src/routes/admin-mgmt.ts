import { Hono } from "hono";
import { getAllAdmins, addAdmin, removeAdmin, updateAdminSuper } from "../db/queries/admin";
import { getAdmin } from "../middleware/auth";
import { superAdminMiddleware } from "../middleware/auth";

export const adminMgmtRoutes = new Hono();

// All routes require super admin
adminMgmtRoutes.use("*", superAdminMiddleware);

adminMgmtRoutes.get("/", async (c) => {
  const currentAdmin = getAdmin(c);
  const admins = getAllAdmins();

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Management - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true, showAddForm: false }">
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
          <a href="/broadcast" class="sidebar-link">Broadcast</a>
          <a href="/generation" class="sidebar-link">Generation</a>
          <a href="/admin-mgmt" class="sidebar-link active">Admin Mgmt</a>
        </div>
      </nav>
      <div class="p-4 border-t border-slate-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center text-slate-600 text-sm font-medium">${currentAdmin.firstName.charAt(0)}</div>
          <div x-show="sidebarOpen" class="flex-1 min-w-0">
            <p class="text-sm font-medium text-slate-900 truncate">${currentAdmin.firstName}</p>
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
            <h1 class="text-xl font-display font-bold text-slate-900">Admin Management</h1>
          </div>
          <button @click="showAddForm = !showAddForm" class="btn btn-primary">Add Admin</button>
        </div>
      </header>

      <div class="p-6">
        <!-- Add admin form -->
        <div x-show="showAddForm" x-transition class="card p-6 mb-6">
          <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Add New Admin</h2>
          <form hx-post="/api/admins" hx-target="#admin-list" hx-swap="innerHTML" @htmx:after-swap="showAddForm = false">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="label">Telegram ID</label>
                <input type="number" name="telegram_id" required class="input" placeholder="123456789">
              </div>
              <div>
                <label class="label">Username (optional)</label>
                <input type="text" name="username" class="input" placeholder="@username">
              </div>
              <div>
                <label class="label">Role</label>
                <select name="is_super" class="input">
                  <option value="false">Admin</option>
                  <option value="true">Super Admin</option>
                </select>
              </div>
            </div>
            <div class="flex gap-2 mt-4">
              <button type="submit" class="btn btn-primary">Add Admin</button>
              <button type="button" @click="showAddForm = false" class="btn btn-secondary">Cancel</button>
            </div>
          </form>
        </div>

        <!-- Admin list -->
        <div class="card" id="admin-list">
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
                      <p class="font-medium text-slate-900">${admin.username ? '@' + admin.username : 'Unknown'}</p>
                    </td>
                    <td class="font-mono-data">${admin.telegram_id}</td>
                    <td>
                      <span class="badge ${admin.is_super ? 'badge-blue' : 'badge-gray'}">${admin.is_super ? 'Super Admin' : 'Admin'}</span>
                    </td>
                    <td class="text-slate-500">${new Date(admin.created_at).toLocaleDateString()}</td>
                    <td>
                      ${admin.telegram_id !== currentAdmin.telegramId ? `
                        <div class="flex gap-2">
                          <button hx-post="/api/admins/${admin.telegram_id}/toggle-super" hx-target="#admin-list" hx-swap="innerHTML" class="text-sm text-blue-600 hover:underline">
                            ${admin.is_super ? 'Demote' : 'Promote'}
                          </button>
                          <button hx-delete="/api/admins/${admin.telegram_id}" hx-target="#admin-list" hx-swap="innerHTML" hx-confirm="Are you sure you want to remove this admin?" class="text-sm text-red-600 hover:underline">
                            Remove
                          </button>
                        </div>
                      ` : '<span class="text-xs text-slate-400">You</span>'}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  </div>
</body>
</html>`;

  return c.html(html);
});
