import { Hono } from "hono";
import {
  getQuestions,
  getQuestionById,
  countQuestions,
  updateQuestion,
  updateReviewStatus,
  deleteQuestion,
  getContentAreaDistribution,
} from "../db/queries/questions";
import { getAdmin } from "../middleware/auth";
import { paginate, getContentAreaLabel } from "../lib/utils";
import { isHtmxRequest, setHtmxHeaders, showToast } from "../lib/htmx";

export const questionRoutes = new Hono();

/**
 * Questions list page.
 */
questionRoutes.get("/", async (c) => {
  const admin = getAdmin(c);
  const page = parseInt(c.req.query("page") || "1");
  const search = c.req.query("search") || "";
  const contentArea = c.req.query("content_area") || "";
  const reviewStatus = c.req.query("review_status") || "";
  const pageSize = 20;

  const filters = {
    search: search || undefined,
    content_area: contentArea || undefined,
    review_status: reviewStatus || undefined,
  };

  const totalCount = countQuestions(filters);
  const pagination = paginate(totalCount, page, pageSize);
  const questions = getQuestions({
    ...filters,
    limit: pageSize,
    offset: pagination.offset,
  });

  const contentAreas = getContentAreaDistribution();
  const contentAreaOptions = Object.keys(contentAreas).map((area) => ({
    value: area,
    label: getContentAreaLabel(area),
    count: contentAreas[area],
  }));

  // If HTMX request, return just the table
  if (isHtmxRequest(c)) {
    return c.html(renderQuestionsTable(questions, pagination, { search, contentArea, reviewStatus }));
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Questions - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50" x-data="{ sidebarOpen: true, viewMode: 'list' }">
  <div class="flex">
    <!-- Sidebar (same as dashboard) -->
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
          <a href="/questions" class="sidebar-link active">
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
            <h1 class="text-xl font-display font-bold text-slate-900">Questions</h1>
          </div>
        </div>
      </header>

      <div class="p-6">
        <!-- Filters -->
        <div class="card p-4 mb-6">
          <form hx-get="/questions" hx-target="#questions-table" hx-push-url="true" class="flex flex-wrap gap-4 items-end">
            <div class="flex-1 min-w-[200px]">
              <label class="label">Search</label>
              <input type="text" name="search" value="${search}" placeholder="Search questions..." class="input">
            </div>
            <div class="w-48">
              <label class="label">Content Area</label>
              <select name="content_area" class="input">
                <option value="">All Areas</option>
                ${contentAreaOptions.map((opt) => `<option value="${opt.value}" ${contentArea === opt.value ? "selected" : ""}>${opt.label} (${opt.count})</option>`).join("")}
              </select>
            </div>
            <div class="w-40">
              <label class="label">Status</label>
              <select name="review_status" class="input">
                <option value="">All</option>
                <option value="unreviewed" ${reviewStatus === "unreviewed" ? "selected" : ""}>Unreviewed</option>
                <option value="approved" ${reviewStatus === "approved" ? "selected" : ""}>Approved</option>
                <option value="rejected" ${reviewStatus === "rejected" ? "selected" : ""}>Rejected</option>
              </select>
            </div>
            <div class="flex gap-2">
              <button type="submit" class="btn btn-primary">Filter</button>
              <a href="/questions" class="btn btn-secondary">Clear</a>
            </div>
          </form>
        </div>

        <!-- Questions table -->
        <div id="questions-table">
          ${renderQuestionsTable(questions, pagination, { search, contentArea, reviewStatus })}
        </div>
      </div>
    </main>
  </div>
</body>
</html>`;

  return c.html(html);
});

/**
 * View/edit single question.
 */
questionRoutes.get("/:id", async (c) => {
  const id = parseInt(c.req.param("id"));
  const question = getQuestionById(id);

  if (!question) {
    return c.notFound();
  }

  const admin = getAdmin(c);

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Question #${question.id} - AbaQuiz Admin</title>
  <link rel="stylesheet" href="/static/css/main.css">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="min-h-screen bg-slate-50">
  <div class="max-w-4xl mx-auto p-6">
    <div class="mb-6">
      <a href="/questions" class="text-blue-600 hover:underline">&larr; Back to Questions</a>
    </div>

    <div class="card p-6">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-xl font-display font-bold text-slate-900">Question #${question.id}</h1>
          <p class="text-sm text-slate-500 mt-1">${getContentAreaLabel(question.content_area)} &bull; ${question.category}</p>
        </div>
        <span class="badge ${question.review_status === "approved" ? "badge-green" : question.review_status === "rejected" ? "badge-red" : "badge-yellow"}">${question.review_status}</span>
      </div>

      <div class="prose max-w-none mb-6">
        <p class="text-lg text-slate-900">${question.question_text}</p>
      </div>

      <div class="grid grid-cols-2 gap-4 mb-6">
        <div class="p-3 rounded-lg ${question.correct_answer === "A" ? "bg-emerald-50 border border-emerald-200" : "bg-slate-50 border border-slate-200"}">
          <span class="font-medium ${question.correct_answer === "A" ? "text-emerald-700" : "text-slate-700"}">A:</span> ${question.option_a}
        </div>
        <div class="p-3 rounded-lg ${question.correct_answer === "B" ? "bg-emerald-50 border border-emerald-200" : "bg-slate-50 border border-slate-200"}">
          <span class="font-medium ${question.correct_answer === "B" ? "text-emerald-700" : "text-slate-700"}">B:</span> ${question.option_b}
        </div>
        <div class="p-3 rounded-lg ${question.correct_answer === "C" ? "bg-emerald-50 border border-emerald-200" : "bg-slate-50 border border-slate-200"}">
          <span class="font-medium ${question.correct_answer === "C" ? "text-emerald-700" : "text-slate-700"}">C:</span> ${question.option_c}
        </div>
        <div class="p-3 rounded-lg ${question.correct_answer === "D" ? "bg-emerald-50 border border-emerald-200" : "bg-slate-50 border border-slate-200"}">
          <span class="font-medium ${question.correct_answer === "D" ? "text-emerald-700" : "text-slate-700"}">D:</span> ${question.option_d}
        </div>
      </div>

      ${question.explanation ? `
      <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 class="font-medium text-blue-900 mb-2">Explanation</h3>
        <p class="text-blue-800">${question.explanation}</p>
      </div>
      ` : ""}

      <div class="flex gap-4 pt-4 border-t border-slate-200">
        <form hx-post="/api/questions/${question.id}/approve" hx-swap="none">
          <button type="submit" class="btn btn-success">Approve</button>
        </form>
        <form hx-post="/api/questions/${question.id}/reject" hx-swap="none">
          <button type="submit" class="btn btn-danger">Reject</button>
        </form>
        <a href="/questions/${question.id}/edit" class="btn btn-secondary">Edit</a>
      </div>
    </div>
  </div>
</body>
</html>`;

  return c.html(html);
});

/**
 * Render questions table HTML.
 */
function renderQuestionsTable(
  questions: any[],
  pagination: ReturnType<typeof paginate>,
  filters: { search: string; contentArea: string; reviewStatus: string }
): string {
  const queryParams = new URLSearchParams();
  if (filters.search) queryParams.set("search", filters.search);
  if (filters.contentArea) queryParams.set("content_area", filters.contentArea);
  if (filters.reviewStatus) queryParams.set("review_status", filters.reviewStatus);
  const baseUrl = `/questions?${queryParams.toString()}`;

  return `
    <div class="card">
      <div class="px-4 py-3 border-b border-slate-200 flex justify-between items-center">
        <p class="text-sm text-slate-500">${pagination.totalItems.toLocaleString()} questions found</p>
      </div>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Question</th>
              <th>Content Area</th>
              <th>Status</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${questions.map((q) => `
              <tr>
                <td class="font-mono-data">${q.id}</td>
                <td class="max-w-md">
                  <p class="truncate">${q.question_text.substring(0, 100)}${q.question_text.length > 100 ? "..." : ""}</p>
                </td>
                <td>
                  <span class="badge badge-blue">${getContentAreaLabel(q.content_area).split(" ").slice(0, 2).join(" ")}</span>
                </td>
                <td>
                  <span class="badge ${q.review_status === "approved" ? "badge-green" : q.review_status === "rejected" ? "badge-red" : "badge-yellow"}">${q.review_status}</span>
                </td>
                <td class="text-slate-500">${new Date(q.created_at).toLocaleDateString()}</td>
                <td>
                  <a href="/questions/${q.id}" class="text-blue-600 hover:underline text-sm">View</a>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      ${pagination.totalPages > 1 ? `
        <div class="px-4 py-3 border-t border-slate-200 flex justify-between items-center">
          <div class="flex gap-2">
            ${pagination.hasPrev ? `<a href="${baseUrl}&page=${pagination.page - 1}" hx-get="${baseUrl}&page=${pagination.page - 1}" hx-target="#questions-table" class="btn btn-secondary text-sm">Previous</a>` : ""}
            ${pagination.hasNext ? `<a href="${baseUrl}&page=${pagination.page + 1}" hx-get="${baseUrl}&page=${pagination.page + 1}" hx-target="#questions-table" class="btn btn-secondary text-sm">Next</a>` : ""}
          </div>
          <p class="text-sm text-slate-500">Page ${pagination.page} of ${pagination.totalPages}</p>
        </div>
      ` : ""}
    </div>
  `;
}
