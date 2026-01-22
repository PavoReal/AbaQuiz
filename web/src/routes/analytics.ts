import { Hono } from "hono";
import { getDailyEngagement, getContentAreaPerformance, getApiUsage, getTotalApiCosts } from "../db/queries/analytics";
import { getAdmin } from "../middleware/auth";

export const analyticsRoutes = new Hono();

analyticsRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const days = parseInt(c.req.query("days") || "30");

  const dailyEngagement = getDailyEngagement(days);
  const contentAreaPerformance = getContentAreaPerformance();
  const apiUsage = getApiUsage(days);
  const totalCosts = getTotalApiCosts(days);

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Analytics - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
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
          <a href="/dashboard" class="sidebar-link">Dashboard</a>
          <a href="/questions" class="sidebar-link">Questions</a>
          <a href="/review" class="sidebar-link">Review</a>
          <a href="/users" class="sidebar-link">Users</a>
          <a href="/analytics" class="sidebar-link active">Analytics</a>
          <a href="/broadcast" class="sidebar-link">Broadcast</a>
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
            <h1 class="text-xl font-display font-bold text-slate-900">Analytics</h1>
          </div>
          <div class="flex gap-2">
            <a href="/analytics?days=7" class="btn ${days === 7 ? 'btn-primary' : 'btn-secondary'} text-sm">7 days</a>
            <a href="/analytics?days=30" class="btn ${days === 30 ? 'btn-primary' : 'btn-secondary'} text-sm">30 days</a>
            <a href="/analytics?days=90" class="btn ${days === 90 ? 'btn-primary' : 'btn-secondary'} text-sm">90 days</a>
          </div>
        </div>
      </header>

      <div class="p-6">
        <!-- Stats summary -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div class="stat-card">
            <p class="stat-card-label">Total Engagement</p>
            <p class="stat-card-value">${dailyEngagement.reduce((sum, d) => sum + d.questions_answered, 0).toLocaleString()}</p>
            <p class="text-sm text-slate-500">questions answered</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">Avg Daily Users</p>
            <p class="stat-card-value">${dailyEngagement.length > 0 ? Math.round(dailyEngagement.reduce((sum, d) => sum + d.active_users, 0) / dailyEngagement.length) : 0}</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">Correct Rate</p>
            <p class="stat-card-value">${dailyEngagement.length > 0 ? Math.round(dailyEngagement.reduce((sum, d) => sum + d.correct_count, 0) / dailyEngagement.reduce((sum, d) => sum + d.questions_answered, 0) * 100) : 0}%</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">API Costs</p>
            <p class="stat-card-value">$${totalCosts.toFixed(2)}</p>
          </div>
        </div>

        <!-- Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div class="card p-6">
            <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Daily Engagement</h3>
            <div class="h-64">
              <canvas id="engagementChart"></canvas>
            </div>
          </div>
          <div class="card p-6">
            <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Content Area Performance</h3>
            <div class="h-64">
              <canvas id="performanceChart"></canvas>
            </div>
          </div>
        </div>

        <!-- Content area breakdown -->
        <div class="card p-6">
          <h3 class="text-lg font-display font-bold text-slate-900 mb-4">Content Area Breakdown</h3>
          <div class="table-wrapper">
            <table class="table">
              <thead>
                <tr>
                  <th>Content Area</th>
                  <th>Questions Answered</th>
                  <th>Correct Rate</th>
                  <th>Avg Response Time</th>
                </tr>
              </thead>
              <tbody>
                ${contentAreaPerformance.map((area) => `
                  <tr>
                    <td class="font-medium">${area.content_area.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}</td>
                    <td>${area.total_answered.toLocaleString()}</td>
                    <td>
                      <span class="badge ${area.correct_rate >= 70 ? 'badge-green' : area.correct_rate >= 50 ? 'badge-yellow' : 'badge-red'}">${area.correct_rate.toFixed(1)}%</span>
                    </td>
                    <td>${area.avg_time_ms ? (area.avg_time_ms / 1000).toFixed(1) + 's' : 'N/A'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  </div>

  <script>
    const engagementData = ${JSON.stringify(dailyEngagement.reverse())};
    new Chart(document.getElementById('engagementChart'), {
      type: 'line',
      data: {
        labels: engagementData.map(d => d.date),
        datasets: [{
          label: 'Questions',
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
        scales: { y: { beginAtZero: true } }
      }
    });

    const perfData = ${JSON.stringify(contentAreaPerformance)};
    new Chart(document.getElementById('performanceChart'), {
      type: 'bar',
      data: {
        labels: perfData.map(d => d.content_area.split('_').slice(0, 2).join(' ')),
        datasets: [{
          label: 'Correct Rate %',
          data: perfData.map(d => d.correct_rate),
          backgroundColor: '#3B82F6'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true, max: 100 } }
      }
    });
  </script>
</body>
</html>`;

  return c.html(html);
});
