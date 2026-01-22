import { Hono } from "hono";
import { getPoolStats, getDailyEngagement, getTotalApiCosts } from "../db/queries/analytics";
import { countQuestions, getReviewStatusDistribution, getContentAreaDistribution } from "../db/queries/questions";
import { countUsers, getActiveUserCount } from "../db/queries/users";
import { getAdmin } from "../middleware/auth";

export const dashboardRoutes = new Hono();

/**
 * Dashboard page.
 */
dashboardRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const poolStats = getPoolStats();
  const totalQuestions = countQuestions();
  const totalUsers = countUsers();
  const activeUsers = getActiveUserCount(7);
  const dailyEngagement = getDailyEngagement(7);
  const apiCosts = getTotalApiCosts(30);
  const reviewStatus = getReviewStatusDistribution();
  const contentAreas = getContentAreaDistribution();

  // Calculate pool health status
  let poolHealth = "health-healthy";
  if (poolStats.avg_unseen_per_user < 10) {
    poolHealth = "health-critical";
  } else if (poolStats.avg_unseen_per_user < 20) {
    poolHealth = "health-warning";
  }

  // Format content area data for chart
  const contentAreaLabels = Object.keys(contentAreas).map(area =>
    area.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")
  );
  const contentAreaData = Object.values(contentAreas);

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true }">
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
          <a href="/dashboard" class="sidebar-link active">
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
          <a href="/users" class="sidebar-link">
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
          ${admin.isSuper ? `
          <a href="/admin-mgmt" class="sidebar-link">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
            <span x-show="sidebarOpen">Admin Mgmt</span>
          </a>
          ` : ''}
        </div>
      </nav>

      <div class="p-4 border-t border-slate-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center text-slate-600 text-sm font-medium">
            ${admin.firstName.charAt(0)}
          </div>
          <div x-show="sidebarOpen" class="flex-1 min-w-0">
            <p class="text-sm font-medium text-slate-900 truncate">${admin.firstName}</p>
            <p class="text-xs text-slate-500 truncate">@${admin.username || 'admin'}</p>
          </div>
          <a x-show="sidebarOpen" href="/auth/logout" class="text-slate-400 hover:text-slate-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </a>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 min-h-screen">
      <header class="bg-white border-b border-slate-200 px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <button @click="sidebarOpen = !sidebarOpen" class="text-slate-500 hover:text-slate-700">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <h1 class="text-xl font-display font-bold text-slate-900">Dashboard</h1>
          </div>
          <div class="flex items-center gap-2" id="pool-health">
            <div class="health-indicator ${poolHealth}"></div>
            <span class="text-sm text-slate-500">Pool Health</span>
          </div>
        </div>
      </header>

      <div class="p-6">
        <!-- Stats cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div class="stat-card">
            <p class="stat-card-label">Total Questions</p>
            <p class="stat-card-value">${totalQuestions.toLocaleString()}</p>
            <div class="flex gap-2 mt-2">
              <span class="badge badge-green">${reviewStatus['approved'] || 0} approved</span>
              <span class="badge badge-yellow">${reviewStatus['unreviewed'] || 0} pending</span>
            </div>
          </div>

          <div class="stat-card">
            <p class="stat-card-label">Total Users</p>
            <p class="stat-card-value">${totalUsers.toLocaleString()}</p>
            <p class="text-sm text-slate-500 mt-2">${activeUsers} active (7d)</p>
          </div>

          <div class="stat-card">
            <p class="stat-card-label">Avg Unseen / User</p>
            <p class="stat-card-value">${poolStats.avg_unseen_per_user.toFixed(1)}</p>
            <p class="text-sm ${poolStats.avg_unseen_per_user < 20 ? 'text-amber-600' : 'text-slate-500'} mt-2">
              ${poolStats.avg_unseen_per_user < 20 ? 'Below threshold (20)' : 'Above threshold'}
            </p>
          </div>

          <div class="stat-card">
            <p class="stat-card-label">API Costs (30d)</p>
            <p class="stat-card-value">$${apiCosts.toFixed(2)}</p>
            <p class="text-sm text-slate-500 mt-2">GPT-5.2 + embeddings</p>
          </div>
        </div>

        <!-- Charts row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <!-- Content area distribution -->
          <div class="card p-6">
            <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Content Area Distribution</h3>
            <div class="h-64">
              <canvas id="contentAreaChart"></canvas>
            </div>
          </div>

          <!-- Daily engagement -->
          <div class="card p-6">
            <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Daily Engagement (7d)</h3>
            <div class="h-64">
              <canvas id="engagementChart"></canvas>
            </div>
          </div>
        </div>

        <!-- Quick actions -->
        <div class="card p-6">
          <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Quick Actions</h3>
          <div class="flex flex-wrap gap-4">
            <a href="/review" class="btn btn-primary">
              Review Questions (${reviewStatus['unreviewed'] || 0})
            </a>
            <a href="/generation" class="btn btn-secondary">
              Generate Questions
            </a>
            <a href="/broadcast" class="btn btn-secondary">
              Send Broadcast
            </a>
            <a href="/questions?action=new" class="btn btn-secondary">
              Create Question
            </a>
          </div>
        </div>
      </div>
    </main>
  </div>

  <script>
    // Content area chart
    new Chart(document.getElementById('contentAreaChart'), {
      type: 'doughnut',
      data: {
        labels: ${JSON.stringify(contentAreaLabels)},
        datasets: [{
          data: ${JSON.stringify(contentAreaData)},
          backgroundColor: [
            '#3B82F6', '#06B6D4', '#8B5CF6', '#EC4899', '#F97316',
            '#10B981', '#6366F1', '#F59E0B', '#EF4444'
          ]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              boxWidth: 12,
              font: { size: 11 }
            }
          }
        }
      }
    });

    // Engagement chart
    const engagementData = ${JSON.stringify(dailyEngagement.reverse())};
    new Chart(document.getElementById('engagementChart'), {
      type: 'line',
      data: {
        labels: engagementData.map(d => d.date),
        datasets: [{
          label: 'Questions Answered',
          data: engagementData.map(d => d.questions_answered),
          borderColor: '#3B82F6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.3
        }, {
          label: 'Active Users',
          data: engagementData.map(d => d.active_users),
          borderColor: '#10B981',
          backgroundColor: 'transparent',
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true
          }
        },
        plugins: {
          legend: {
            position: 'bottom'
          }
        }
      }
    });
  </script>
</body>
</html>`;

  return c.html(html);
});
