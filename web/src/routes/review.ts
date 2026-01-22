import { Hono } from "hono";
import { getQuestions, getQuestionById, updateReviewStatus } from "../db/queries/questions";
import { getAdmin } from "../middleware/auth";
import { getContentAreaLabel } from "../lib/utils";

export const reviewRoutes = new Hono();

/**
 * Review interface page.
 */
reviewRoutes.get("/", async (c) => {
  const admin = getAdmin(c);

  // Get first unreviewed question
  const unreviewedQuestions = getQuestions({
    review_status: "unreviewed",
    limit: 1,
  });

  const currentQuestion = unreviewedQuestions[0] || null;
  const unreviewedCount = unreviewedQuestions.length > 0 ? getQuestions({ review_status: "unreviewed" }).length : 0;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Review - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
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
          <a href="/review" class="sidebar-link active">
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
            <h1 class="text-xl font-display font-bold text-slate-900">Review Questions</h1>
          </div>
          <div class="badge badge-yellow">${unreviewedCount} pending</div>
        </div>
      </header>

      <div class="p-6" id="review-content">
        ${currentQuestion ? renderReviewQuestion(currentQuestion) : `
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
        `}
      </div>
    </main>
  </div>

  <script>
    // Keyboard shortcuts for review
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      if (e.key === 'a' || e.key === 'A') {
        document.querySelector('[data-action="approve"]')?.click();
      } else if (e.key === 'r' || e.key === 'R') {
        document.querySelector('[data-action="reject"]')?.click();
      } else if (e.key === 'n' || e.key === 'N') {
        document.querySelector('[data-action="skip"]')?.click();
      }
    });
  </script>
</body>
</html>`;

  return c.html(html);
});

function renderReviewQuestion(question: any): string {
  return `
    <div class="card p-6 max-w-4xl">
      <div class="flex justify-between items-start mb-6">
        <div>
          <span class="font-mono-data text-slate-500">Question #${question.id}</span>
          <p class="text-sm text-slate-500 mt-1">${getContentAreaLabel(question.content_area)} &bull; ${question.category}</p>
        </div>
        ${question.difficulty ? `<span class="text-yellow-500">${'★'.repeat(question.difficulty)}${'☆'.repeat(5 - question.difficulty)}</span>` : ''}
      </div>

      <div class="prose max-w-none mb-6">
        <p class="text-lg text-slate-900 leading-relaxed">${question.question_text}</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="p-4 rounded-lg ${question.correct_answer === 'A' ? 'bg-emerald-50 border-2 border-emerald-300' : 'bg-slate-50 border border-slate-200'}">
          <span class="font-bold ${question.correct_answer === 'A' ? 'text-emerald-700' : 'text-slate-700'}">A.</span>
          <span class="${question.correct_answer === 'A' ? 'text-emerald-700' : 'text-slate-700'}">${question.option_a}</span>
        </div>
        <div class="p-4 rounded-lg ${question.correct_answer === 'B' ? 'bg-emerald-50 border-2 border-emerald-300' : 'bg-slate-50 border border-slate-200'}">
          <span class="font-bold ${question.correct_answer === 'B' ? 'text-emerald-700' : 'text-slate-700'}">B.</span>
          <span class="${question.correct_answer === 'B' ? 'text-emerald-700' : 'text-slate-700'}">${question.option_b}</span>
        </div>
        <div class="p-4 rounded-lg ${question.correct_answer === 'C' ? 'bg-emerald-50 border-2 border-emerald-300' : 'bg-slate-50 border border-slate-200'}">
          <span class="font-bold ${question.correct_answer === 'C' ? 'text-emerald-700' : 'text-slate-700'}">C.</span>
          <span class="${question.correct_answer === 'C' ? 'text-emerald-700' : 'text-slate-700'}">${question.option_c}</span>
        </div>
        <div class="p-4 rounded-lg ${question.correct_answer === 'D' ? 'bg-emerald-50 border-2 border-emerald-300' : 'bg-slate-50 border border-slate-200'}">
          <span class="font-bold ${question.correct_answer === 'D' ? 'text-emerald-700' : 'text-slate-700'}">D.</span>
          <span class="${question.correct_answer === 'D' ? 'text-emerald-700' : 'text-slate-700'}">${question.option_d}</span>
        </div>
      </div>

      ${question.explanation ? `
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <h3 class="font-medium text-blue-900 mb-2">Explanation</h3>
          <p class="text-blue-800">${question.explanation}</p>
        </div>
      ` : ''}

      <div class="flex justify-between items-center pt-4 border-t border-slate-200">
        <div class="text-sm text-slate-500">
          Shortcuts: <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">A</kbd> Approve &bull;
          <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">R</kbd> Reject &bull;
          <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-xs">N</kbd> Skip
        </div>
        <div class="flex gap-3">
          <button hx-post="/api/questions/${question.id}/skip" hx-target="#review-content" hx-swap="innerHTML" data-action="skip" class="btn btn-secondary">
            Skip
          </button>
          <button hx-post="/api/questions/${question.id}/reject" hx-target="#review-content" hx-swap="innerHTML" data-action="reject" class="btn btn-danger">
            Reject
          </button>
          <button hx-post="/api/questions/${question.id}/approve" hx-target="#review-content" hx-swap="innerHTML" data-action="approve" class="btn btn-success">
            Approve
          </button>
        </div>
      </div>
    </div>
  `;
}
