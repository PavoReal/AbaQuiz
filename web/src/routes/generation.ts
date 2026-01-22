import { Hono } from "hono";
import { getDb } from "../db/connection";
import { getPoolStats, getGenerationHistory } from "../db/queries/analytics";
import { getAdmin } from "../middleware/auth";
import { getContentAreaLabel, CONTENT_AREA_LABELS } from "../lib/utils";

export const generationRoutes = new Hono();

generationRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const poolStats = getPoolStats();
  const history = getGenerationHistory(10);

  // Get any active generation
  const db = getDb();
  const activeGeneration = db.prepare(`
    SELECT gq.*, gp.*
    FROM generation_queue gq
    LEFT JOIN generation_progress gp ON gq.id = gp.queue_id
    WHERE gq.status IN ('pending', 'processing')
    ORDER BY gq.created_at DESC
    LIMIT 1
  `).get() as any;

  // BCBA weights (from config)
  const bcbaWeights: Record<string, number> = {
    measurement_and_experimentation: 0.12,
    experimental_design: 0.08,
    behavior_measurement: 0.10,
    displaying_and_interpreting_behavioral_data: 0.08,
    philosophical_underpinnings: 0.05,
    concepts_and_principles: 0.14,
    behavior_assessment: 0.12,
    behavior_change_procedures: 0.18,
    selecting_and_implementing_interventions: 0.08,
    personnel_supervision_and_management: 0.03,
    ethics: 0.02,
  };

  const contentAreas = Object.entries(CONTENT_AREA_LABELS).map(([key, label]) => ({
    key,
    label,
    current: poolStats.content_area_distribution[key] || 0,
    weight: bcbaWeights[key] || 0,
  }));

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Generation - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true, count: 50, skipDedup: false }">
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
          <a href="/generation" class="sidebar-link active">Generation</a>
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
            <h1 class="text-xl font-display font-bold text-slate-900">Question Generation</h1>
          </div>
        </div>
      </header>

      <div class="p-6">
        <!-- Pool status -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div class="stat-card">
            <p class="stat-card-label">Total Questions</p>
            <p class="stat-card-value">${poolStats.total_questions.toLocaleString()}</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">Active Users</p>
            <p class="stat-card-value">${poolStats.active_users}</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">Avg Unseen / User</p>
            <p class="stat-card-value ${poolStats.avg_unseen_per_user < 20 ? 'text-amber-600' : ''}">${poolStats.avg_unseen_per_user.toFixed(1)}</p>
          </div>
          <div class="stat-card">
            <p class="stat-card-label">Pool Health</p>
            <div class="flex items-center gap-2 mt-1">
              <div class="health-indicator ${poolStats.avg_unseen_per_user < 10 ? 'health-critical' : poolStats.avg_unseen_per_user < 20 ? 'health-warning' : 'health-healthy'}"></div>
              <span class="text-lg font-bold">${poolStats.avg_unseen_per_user < 10 ? 'Critical' : poolStats.avg_unseen_per_user < 20 ? 'Warning' : 'Healthy'}</span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Generation form -->
          <div class="lg:col-span-2">
            ${activeGeneration ? `
              <!-- Active generation -->
              <div class="card p-6 mb-6" id="generation-progress" hx-get="/api/generation/progress/${activeGeneration.id}" hx-trigger="every 2s">
                <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Generation in Progress</h2>
                <div class="space-y-4">
                  <div>
                    <div class="flex justify-between text-sm mb-1">
                      <span>Progress</span>
                      <span>${activeGeneration.total_generated || 0} / ${activeGeneration.requested_count}</span>
                    </div>
                    <div class="progress-track">
                      <div class="progress-fill" style="width: ${((activeGeneration.total_generated || 0) / activeGeneration.requested_count * 100).toFixed(0)}%"></div>
                    </div>
                  </div>
                  <div class="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p class="text-2xl font-bold text-emerald-600">${activeGeneration.total_generated || 0}</p>
                      <p class="text-sm text-slate-500">Generated</p>
                    </div>
                    <div>
                      <p class="text-2xl font-bold text-amber-600">${activeGeneration.total_duplicates || 0}</p>
                      <p class="text-sm text-slate-500">Duplicates</p>
                    </div>
                    <div>
                      <p class="text-2xl font-bold text-red-600">${activeGeneration.total_errors || 0}</p>
                      <p class="text-sm text-slate-500">Errors</p>
                    </div>
                  </div>
                  <p class="text-sm text-slate-500">Current area: ${activeGeneration.current_area || 'Starting...'}</p>
                </div>
              </div>
            ` : `
              <!-- Generation form -->
              <div class="card p-6">
                <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Generate Questions</h2>

                <form hx-post="/api/generation/start" hx-swap="outerHTML">
                  <div class="mb-4">
                    <label class="label">Number of Questions</label>
                    <input type="range" name="count" min="10" max="200" step="10" x-model="count" class="w-full">
                    <div class="flex justify-between text-sm text-slate-500 mt-1">
                      <span>10</span>
                      <span class="font-medium text-slate-900" x-text="count"></span>
                      <span>200</span>
                    </div>
                  </div>

                  <div class="mb-4">
                    <label class="flex items-center gap-2">
                      <input type="checkbox" name="skip_dedup" x-model="skipDedup" class="rounded text-blue-600">
                      <span class="text-sm text-slate-700">Skip deduplication check</span>
                    </label>
                    <p class="text-xs text-slate-500 mt-1">Only disable for testing. Duplicates waste API costs.</p>
                  </div>

                  <div class="bg-slate-50 rounded-lg p-4 mb-4">
                    <h3 class="text-sm font-medium text-slate-700 mb-2">Distribution Preview</h3>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                      ${contentAreas.slice(0, 6).map((area) => `
                        <div class="flex justify-between">
                          <span class="text-slate-600">${area.label.split(' ').slice(0, 2).join(' ')}</span>
                          <span class="font-mono" x-text="Math.round(count * ${area.weight})"></span>
                        </div>
                      `).join('')}
                    </div>
                  </div>

                  <button type="submit" class="btn btn-primary w-full">Start Generation</button>
                </form>
              </div>
            `}

            <!-- Content area distribution -->
            <div class="card p-6 mt-6">
              <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Current Distribution</h2>
              <div class="space-y-3">
                ${contentAreas.map((area) => {
                  const target = Math.round(poolStats.total_questions * area.weight);
                  const diff = area.current - target;
                  return `
                    <div>
                      <div class="flex justify-between text-sm mb-1">
                        <span class="text-slate-700">${area.label}</span>
                        <span class="text-slate-500">${area.current} / ${target} target</span>
                      </div>
                      <div class="progress-track">
                        <div class="progress-fill ${diff < -10 ? 'bg-amber-500' : ''}" style="width: ${Math.min(100, target > 0 ? (area.current / target * 100) : 0).toFixed(0)}%"></div>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            </div>
          </div>

          <!-- History -->
          <div>
            <div class="card p-6">
              <h2 class="text-lg font-display font-bold text-slate-900 mb-4">Generation History</h2>
              <div class="space-y-3">
                ${history.length > 0 ? history.map((h) => `
                  <div class="p-3 bg-slate-50 rounded-lg">
                    <div class="flex justify-between items-start mb-2">
                      <span class="badge ${h.status === 'completed' ? 'badge-green' : h.status === 'failed' ? 'badge-red' : 'badge-yellow'}">${h.status}</span>
                      <span class="text-xs text-slate-500">${new Date(h.created_at).toLocaleDateString()}</span>
                    </div>
                    <p class="text-sm text-slate-700">
                      <span class="font-medium">${h.generated_count}</span> generated
                      ${h.duplicate_count ? `, ${h.duplicate_count} duplicates` : ''}
                      ${h.error_count ? `, ${h.error_count} errors` : ''}
                    </p>
                  </div>
                `).join('') : '<p class="text-sm text-slate-500">No generation history</p>'}
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
