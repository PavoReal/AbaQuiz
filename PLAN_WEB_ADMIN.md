# Admin Web Rewrite - Implementation Plan

Complete rewrite of the admin web interface using a modern Bun/Hono stack with Telegram authentication.

---

## Current Implementation Status

**Last Updated:** 2025-01-22

### Phase 1: Foundation - COMPLETE

All foundation work is complete. The new web admin is located at `/web` and can be started with:

```bash
cd web
bun install
bun run build:css
bun run dev  # Starts on port 8070
```

**Implemented Files:**

| Category | Files | Status |
|----------|-------|--------|
| **Project Setup** | `package.json`, `tsconfig.json`, `bunfig.toml`, `tailwind.config.ts` | Done |
| **Entry Point** | `src/index.ts` | Done |
| **Database** | `src/db/connection.ts` (WAL mode), `src/db/queries/*.ts` | Done |
| **Auth** | `src/auth/telegram.ts`, `src/auth/session.ts`, `src/middleware/auth.ts` | Done |
| **Routes** | All page routes (`dashboard`, `questions`, `review`, `users`, `analytics`, `broadcast`, `generation`, `admin-mgmt`) | Done |
| **API** | `src/api/index.ts` (HTMX endpoints) | Done |
| **WebSocket** | `src/ws/index.ts` (stub implementation) | Done |
| **Styles** | `static/css/input.css`, `static/css/main.css` | Done |
| **Python Migration** | `src/database/migrations.py` v5 (queue tables) | Done |

### What Works Now

- Server starts and connects to existing SQLite database
- WAL mode enabled for concurrent access
- Queue tables created automatically on first run
- All page routes render (dashboard, questions, review, users, analytics, broadcast, generation, admin-mgmt)
- Telegram Login Widget auth flow (untested with real Telegram)
- JWT session management
- HTMX-powered interactions for review flow
- Chart.js visualizations on dashboard/analytics

### What Needs Work (Phase 2+)

- [ ] Real-time WebSocket updates (currently stub)
- [ ] Question editor form (create/edit)
- [ ] Python bot queue processors (broadcast, generation)
- [ ] Docker/supervisord configuration
- [ ] End-to-end testing with real Telegram auth
- [ ] Remove old Python web admin

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Runtime** | Bun |
| **Framework** | Hono |
| **Frontend** | HTMX + Alpine.js + Tailwind CSS |
| **Charts** | Chart.js |
| **Real-time** | WebSocket (Hono built-in) |
| **Auth** | Telegram Login Widget |
| **Database** | Direct SQLite with WAL mode |
| **Deployment** | Same container, supervisord |
| **Location** | `/web` at project root |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Container                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      supervisord                             ││
│  │  ┌─────────────────────┐    ┌─────────────────────────────┐ ││
│  │  │   Python Bot        │    │     Bun Web Admin           │ ││
│  │  │   (telegram-bot)    │    │     (hono server)           │ ││
│  │  │   - Bot handlers    │    │     - Admin UI              │ ││
│  │  │   - Scheduler       │    │     - REST API              │ ││
│  │  │   - Pool manager    │    │     - WebSocket             │ ││
│  │  │   - Broadcast proc  │    │     - Telegram auth         │ ││
│  │  └─────────┬───────────┘    └──────────┬──────────────────┘ ││
│  │            │                           │                     ││
│  │            └─────────┬─────────────────┘                     ││
│  │                      ▼                                       ││
│  │            ┌─────────────────┐                               ││
│  │            │    SQLite DB    │                               ││
│  │            │   (WAL mode)    │                               ││
│  │            │  /data/abaquiz  │                               ││
│  │            └─────────────────┘                               ││
│  └─────────────────────────────────────────────────────────────┘│
│  Ports: 8070 (web admin)                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Sharing Strategy

### WAL Mode Configuration

SQLite WAL (Write-Ahead Logging) mode enables concurrent read access from multiple processes:

```typescript
// web/src/db/connection.ts
import { Database } from "bun:sqlite";

const db = new Database("/app/data/abaquiz.db", {
  readonly: false,
  create: false,
});

// Enable WAL mode (if not already)
db.run("PRAGMA journal_mode=WAL");
db.run("PRAGMA busy_timeout=5000");  // Wait up to 5s for locks
db.run("PRAGMA synchronous=NORMAL"); // Balance durability/performance
```

### Concurrency Rules

1. **Reads**: Both processes can read simultaneously (unlimited readers)
2. **Writes**: One writer at a time, others wait up to `busy_timeout`
3. **Transactions**: Keep write transactions short to minimize lock contention
4. **Checkpoint**: WAL auto-checkpoints at 1000 pages; manual checkpoint on shutdown

### New Tables for Inter-Process Communication

```sql
-- Broadcast queue (web writes, bot reads/processes)
CREATE TABLE IF NOT EXISTS broadcast_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_text TEXT NOT NULL,
    message_format TEXT DEFAULT 'text', -- 'text', 'markdown', 'html'
    target_filter TEXT DEFAULT 'all',   -- 'all', 'active', 'custom'
    target_user_ids TEXT,               -- JSON array for custom filter
    created_by INTEGER NOT NULL,        -- Admin telegram_id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',      -- 'pending', 'processing', 'completed', 'failed'
    processed_at TIMESTAMP,
    sent_count INTEGER DEFAULT 0,
    error_message TEXT
);

-- Generation requests (web writes, bot reads/processes)
CREATE TABLE IF NOT EXISTS generation_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_count INTEGER NOT NULL,
    skip_dedup BOOLEAN DEFAULT FALSE,
    distribution TEXT,                  -- JSON object of content_area -> count
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',      -- 'pending', 'processing', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    generated_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_message TEXT
);

-- Generation progress (bot writes, web reads for real-time updates)
CREATE TABLE IF NOT EXISTS generation_progress (
    queue_id INTEGER PRIMARY KEY REFERENCES generation_queue(id),
    current_area TEXT,
    area_progress TEXT,                 -- JSON: { area: { generated, duplicates, status } }
    total_generated INTEGER DEFAULT 0,
    total_duplicates INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Authentication System

### Telegram Login Widget Flow

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│  Admin  │────▶│ Login Widget │────▶│  Telegram   │────▶│ Callback │
│ Browser │     │  (embedded)  │     │   Servers   │     │ Handler  │
└─────────┘     └──────────────┘     └─────────────┘     └────┬─────┘
                                                              │
                      ┌───────────────────────────────────────┘
                      ▼
              ┌───────────────┐     ┌────────────────┐
              │ Verify Hash   │────▶│ Check admins   │
              │ (HMAC-SHA256) │     │    table       │
              └───────────────┘     └───────┬────────┘
                                            │
                    ┌───────────────────────┴───────────────────┐
                    ▼                                           ▼
            ┌───────────────┐                           ┌───────────────┐
            │ Create JWT    │                           │ Access Denied │
            │ Set Cookie    │                           │    (403)      │
            └───────────────┘                           └───────────────┘
```

### Authentication Implementation

```typescript
// web/src/auth/telegram.ts
import { createHmac } from "crypto";

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export function verifyTelegramAuth(user: TelegramUser, botToken: string): boolean {
  const { hash, ...data } = user;

  // Create data check string (alphabetically sorted)
  const checkString = Object.keys(data)
    .sort()
    .map(k => `${k}=${data[k]}`)
    .join("\n");

  // Create secret key from bot token
  const secretKey = createHmac("sha256", "WebAppData")
    .update(botToken)
    .digest();

  // Calculate expected hash
  const expectedHash = createHmac("sha256", secretKey)
    .update(checkString)
    .digest("hex");

  // Verify hash matches
  if (hash !== expectedHash) return false;

  // Check auth_date is recent (within 24 hours)
  const now = Math.floor(Date.now() / 1000);
  if (now - user.auth_date > 86400) return false;

  return true;
}
```

### Session Management

```typescript
// web/src/auth/session.ts
import { sign, verify } from "hono/jwt";

interface AdminSession {
  telegramId: number;
  username: string;
  isSuper: boolean;
  exp: number;
}

const JWT_SECRET = process.env.JWT_SECRET!;
const SESSION_DURATION = 7 * 24 * 60 * 60; // 7 days

export async function createSession(admin: Admin): Promise<string> {
  const payload: AdminSession = {
    telegramId: admin.telegram_id,
    username: admin.username,
    isSuper: admin.is_super,
    exp: Math.floor(Date.now() / 1000) + SESSION_DURATION,
  };
  return await sign(payload, JWT_SECRET);
}

export async function verifySession(token: string): Promise<AdminSession | null> {
  try {
    return await verify(token, JWT_SECRET) as AdminSession;
  } catch {
    return null;
  }
}
```

### Admin Permission Levels

| Feature | Regular Admin | Super Admin |
|---------|--------------|-------------|
| View dashboard | ✓ | ✓ |
| Browse questions | ✓ | ✓ |
| Review questions | ✓ | ✓ |
| Edit questions | ✓ | ✓ |
| Create questions | ✓ | ✓ |
| View users | ✓ | ✓ |
| Ban/unban users | ✓ | ✓ |
| Send broadcasts | ✓ | ✓ |
| Trigger generation | ✓ | ✓ |
| View analytics | ✓ | ✓ |
| Manage admins | ✗ | ✓ |
| View system config | ✗ | ✓ |

---

## Project Structure

```
web/
├── package.json
├── tsconfig.json
├── bunfig.toml
├── tailwind.config.ts
├── postcss.config.js
│
├── src/
│   ├── index.ts              # Entry point, Hono app setup
│   │
│   ├── routes/
│   │   ├── index.ts          # Route aggregator
│   │   ├── auth.ts           # Login/logout, Telegram callback
│   │   ├── dashboard.ts      # Main dashboard
│   │   ├── questions.ts      # Question browser + editor
│   │   ├── review.ts         # Review interface
│   │   ├── users.ts          # User management
│   │   ├── analytics.ts      # Analytics dashboard
│   │   ├── broadcast.ts      # Broadcast composer
│   │   ├── generation.ts     # Generation control
│   │   └── admin-mgmt.ts     # Admin management (super only)
│   │
│   ├── api/
│   │   ├── index.ts          # API route aggregator
│   │   ├── questions.ts      # CRUD operations
│   │   ├── users.ts          # User operations
│   │   ├── analytics.ts      # Stats endpoints
│   │   ├── broadcast.ts      # Queue management
│   │   └── generation.ts     # Generation control
│   │
│   ├── ws/
│   │   └── index.ts          # WebSocket handlers for real-time updates
│   │
│   ├── db/
│   │   ├── connection.ts     # SQLite connection with WAL
│   │   ├── queries/          # Prepared statements
│   │   │   ├── questions.ts
│   │   │   ├── users.ts
│   │   │   ├── analytics.ts
│   │   │   └── admin.ts
│   │   └── migrations.ts     # Schema updates
│   │
│   ├── auth/
│   │   ├── telegram.ts       # Telegram verification
│   │   ├── session.ts        # JWT session management
│   │   └── middleware.ts     # Auth middleware
│   │
│   ├── middleware/
│   │   ├── auth.ts           # Require authentication
│   │   ├── superAdmin.ts     # Require super admin
│   │   └── logger.ts         # Request logging
│   │
│   └── lib/
│       ├── render.ts         # Template rendering helpers
│       ├── htmx.ts           # HTMX response helpers
│       └── utils.ts          # General utilities
│
├── views/
│   ├── layouts/
│   │   └── base.html         # Base layout with sidebar
│   │
│   ├── pages/
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── questions.html
│   │   ├── question-editor.html
│   │   ├── review.html
│   │   ├── users.html
│   │   ├── analytics.html
│   │   ├── broadcast.html
│   │   ├── generation.html
│   │   └── admin-management.html
│   │
│   └── partials/
│       ├── question-card.html
│       ├── question-form.html
│       ├── review-panel.html
│       ├── user-row.html
│       ├── user-detail.html
│       ├── broadcast-form.html
│       ├── broadcast-queue.html
│       ├── generation-progress.html
│       ├── chart-container.html
│       └── pagination.html
│
├── static/
│   ├── css/
│   │   ├── input.css         # Tailwind input
│   │   └── main.css          # Compiled output
│   │
│   └── js/
│       ├── alpine-stores.ts  # Alpine.js global stores
│       ├── charts.ts         # Chart.js configurations
│       └── websocket.ts      # WebSocket client
│
└── scripts/
    └── build-css.ts          # Tailwind build script
```

---

## Features Specification

### 1. Dashboard

**Purpose**: Overview of system health and key metrics at a glance.

**Components**:
- **Pool health indicator**: Visual gauge showing questions remaining vs threshold
- **Active users count**: Users who answered in last 7 days
- **Quick stats cards**: Total questions, users, broadcasts sent, API costs
- **Recent activity feed**: Last 10 user answers, reviews, broadcasts
- **Content area distribution**: Pie chart of question distribution

**Real-time updates**: WebSocket pushes new activity items.

---

### 2. Questions Browser

**Purpose**: Browse, search, filter, and manage the question pool.

**Features**:
- **Grid/list view toggle**
- **Filters**:
  - Content area (9 BCBA areas)
  - Difficulty (1-5 stars)
  - Review status (unreviewed, approved, rejected)
  - Model used
  - Date range
- **Search**: Full-text search across question text, options, explanations
- **Bulk actions**: Select multiple questions for bulk approve/reject/delete
- **Quick preview**: Hover card showing full question details
- **Pagination**: 20 questions per page with infinite scroll option

---

### 3. Question Editor

**Purpose**: Create new questions manually or edit existing ones.

**Form Fields**:
- Question text (rich text with markdown preview)
- Answer options (A-D) with correct answer toggle
- Explanation (markdown)
- Content area (dropdown)
- Difficulty (1-5 star selector)
- Source citation (optional, JSON)
- Review status
- Tags (optional, for organization)

**Validation**:
- Question must be non-empty
- Exactly 4 options required
- One correct answer must be selected
- Content area required
- Difficulty required

**Preview mode**: Side-by-side edit and preview.

---

### 4. Review Interface

**Purpose**: Quality control for generated questions.

**Layout**:
- **Left panel**: Question display with options (randomized order)
- **Right panel**:
  - Performance stats (if answered before)
  - User reports (if any)
  - Previous reviews
  - Review form

**Review form**:
- Quality rating (1-5 stars)
- Issues checklist:
  - [ ] Factually incorrect
  - [ ] Ambiguous wording
  - [ ] Multiple correct answers
  - [ ] Too easy/hard
  - [ ] Out of scope
- Notes (freeform text)
- Decision: Approve / Reject / Needs revision

**Navigation**:
- Next/Previous buttons
- Jump to specific ID
- Filter by status
- Keyboard shortcuts (A=approve, R=reject, N=next, P=prev)

---

### 5. User Management

**Purpose**: View and manage bot users.

**User list**:
- Sortable columns: Username, Join date, Last active, Questions answered, Accuracy, Status
- Search by username, telegram ID
- Filter: All / Active / Inactive / Banned
- Pagination: 50 users per page

**User detail view** (modal or slide-out):
- Profile info (telegram ID, username, timezone)
- Statistics:
  - Total questions answered
  - Correct/incorrect breakdown
  - Current streak
  - Points and achievements
  - Content area performance chart
- Activity timeline: Recent answers with timestamps
- Actions:
  - Ban / Unban
  - Reset stats (with confirmation)
  - Send direct message (via broadcast queue)

---

### 6. Analytics Dashboard

**Purpose**: Visualize system metrics and trends.

**Charts** (Chart.js):

1. **User engagement over time** (line chart)
   - Daily active users
   - Questions answered per day
   - New user signups

2. **Question performance** (bar chart)
   - Correct answer rate by content area
   - Average difficulty vs actual difficulty

3. **Content area distribution** (doughnut chart)
   - Current pool distribution
   - Target vs actual

4. **API costs** (stacked area chart)
   - Daily costs: GPT-5.2, embeddings
   - Cumulative monthly cost

5. **Generation metrics** (bar chart)
   - Questions generated per batch
   - Duplicate rate
   - Error rate

**Date range selector**: Last 7 days, 30 days, 90 days, all time, custom range.

**Export**: Download chart data as CSV.

---

### 7. Broadcast Composer

**Purpose**: Send messages to users through the bot.

**Compose form**:
- Message text (rich editor with markdown preview)
- Format: Plain text / Markdown / HTML
- Target audience:
  - All users
  - Active users (last 7 days)
  - Inactive users
  - Custom selection (multi-select from user list)
- Schedule:
  - Send immediately
  - Schedule for later (datetime picker)

**Preview**: Shows rendered message as users will see it.

**Queue view**:
- List of pending/completed broadcasts
- Status: Pending / Processing / Completed / Failed
- Sent count / Total count
- Cancel button for pending
- Retry button for failed

**Confirmation**: Require typing "SEND" to confirm broadcast to all users.

---

### 8. Generation Control

**Purpose**: Manage question generation batches.

**Pool status dashboard**:
- Current pool size per content area
- Average unseen per active user
- Health indicator (healthy/warning/critical/empty)
- BCBA weight targets vs actual

**Generation form**:
- Count slider (1-500)
- Skip deduplication checkbox
- Distribution preview (auto-calculated from BCBA weights)
- Estimated cost display
- Start generation button

**Progress view** (WebSocket-powered):
- Overall progress bar
- Per-content-area progress bars
- Live counters: Generated / Duplicates / Errors
- Running cost
- Cancel button
- ETA display

**History**:
- Table of past generation batches
- Date, count, cost, error rate
- Click to see details

---

### 9. Admin Management (Super Admin Only)

**Purpose**: Manage who has admin access.

**Admin list**:
- Username, Telegram ID, Added date, Added by, Is Super
- Actions: Promote to super / Demote / Remove

**Add admin form**:
- Telegram ID (numeric)
- Super admin checkbox

**Audit log**:
- Who added/removed/promoted whom and when

---

## Design System

### Color Palette (Cool Blues/Slates)

```css
:root {
  /* Base colors (Slate) */
  --background: #F8FAFC;      /* slate-50 */
  --sidebar-bg: #F1F5F9;      /* slate-100 */
  --surface: #FFFFFF;
  --border: #E2E8F0;          /* slate-200 */
  --border-muted: #CBD5E1;    /* slate-300 */

  /* Text colors */
  --text-primary: #0F172A;    /* slate-900 */
  --text-secondary: #475569;  /* slate-600 */
  --text-tertiary: #334155;   /* slate-700 */
  --text-muted: #94A3B8;      /* slate-400 */

  /* Accent colors */
  --accent-primary: #2563EB;  /* blue-600 */
  --accent-primary-hover: #1D4ED8; /* blue-700 */
  --accent-secondary: #0EA5E9; /* sky-500 */
  --accent-success: #10B981;  /* emerald-500 */
  --accent-warning: #F59E0B;  /* amber-500 */
  --accent-danger: #EF4444;   /* red-500 */

  /* Data visualization */
  --chart-1: #3B82F6;         /* blue-500 */
  --chart-2: #06B6D4;         /* cyan-500 */
  --chart-3: #8B5CF6;         /* violet-500 */
  --chart-4: #EC4899;         /* pink-500 */
  --chart-5: #F97316;         /* orange-500 */
}
```

### Typography

```css
--font-display: "IBM Plex Mono", monospace;
--font-body: Inter, system-ui, sans-serif;
```

- **Headlines**: IBM Plex Mono, bold
- **Body**: Inter, various weights
- **Monospace data**: IBM Plex Mono for IDs, codes

### Tailwind Config

```typescript
// web/tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,html}", "./views/**/*.html"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
        },
      },
      fontFamily: {
        display: ['"IBM Plex Mono"', "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
} satisfies Config;
```

---

## Docker Configuration

### Updated Dockerfile

```dockerfile
# docker/Dockerfile
FROM oven/bun:1.1-alpine AS web-builder

WORKDIR /web
COPY web/package.json web/bun.lockb ./
RUN bun install --frozen-lockfile

COPY web/ .
RUN bun run build:css

# Python builder stage (existing)
FROM python:3.11-slim AS python-builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install bun
RUN apt-get update && apt-get install -y curl unzip && \
    curl -fsSL https://bun.sh/install | bash && \
    ln -s /root/.bun/bin/bun /usr/local/bin/bun && \
    apt-get remove -y curl unzip && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install supervisord
RUN apt-get update && apt-get install -y supervisor && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 abaquiz
WORKDIR /app

# Copy Python dependencies
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy web admin
COPY --from=web-builder /web /app/web

# Copy application code
COPY src/ /app/src/
COPY config/ /app/config/

# Copy supervisord config
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set permissions
RUN chown -R abaquiz:abaquiz /app

USER abaquiz

EXPOSE 8070

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep -f "python.*main" && pgrep -f "bun.*index" || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

### Supervisord Configuration

```ini
# docker/supervisord.conf
[supervisord]
nodaemon=true
user=root
logfile=/dev/stdout
logfile_maxbytes=0
pidfile=/tmp/supervisord.pid

[program:telegram-bot]
command=python -m src.main --no-web
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
user=abaquiz

[program:web-admin]
command=bun run /app/web/src/index.ts
directory=/app/web
environment=NODE_ENV=production,DATABASE_PATH=/app/data/abaquiz.db
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
user=abaquiz
```

### Updated docker-compose.yml

```yaml
# docker-compose.yml
version: "3.8"

services:
  abaquiz:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: abaquiz
    restart: unless-stopped
    ports:
      - "8070:8070"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_PATH=/app/data/abaquiz.db
      - LOG_LEVEL=INFO
      - WEB_PORT=8070
      - WEB_HOST=0.0.0.0
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ./data:/app/data
      - ./config:/app/config:ro
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 768M
```

---

## WebSocket Protocol

### Connection

```typescript
// Client connects to ws://host:8070/ws
// Must include auth token in query string or cookie
const ws = new WebSocket(`ws://${host}/ws?token=${authToken}`);
```

### Message Types

```typescript
// Server -> Client
interface WSMessage {
  type: "generation_progress" | "new_activity" | "pool_update" | "broadcast_status";
  payload: any;
}

// generation_progress payload
interface GenerationProgress {
  queueId: number;
  status: "processing" | "completed" | "failed";
  currentArea: string;
  areaProgress: Record<string, { generated: number; duplicates: number; status: string }>;
  totalGenerated: number;
  totalDuplicates: number;
  totalErrors: number;
  estimatedCost: number;
}

// new_activity payload
interface Activity {
  type: "answer" | "review" | "broadcast" | "generation";
  timestamp: string;
  details: any;
}

// Client -> Server
interface WSCommand {
  type: "subscribe" | "unsubscribe";
  channel: "generation" | "activity" | "pool";
}
```

---

## API Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Login page with Telegram widget |
| GET | `/auth/callback` | Telegram OAuth callback |
| POST | `/auth/logout` | Clear session |
| GET | `/auth/me` | Get current admin info |

### Questions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/questions` | List questions (paginated, filtered) |
| GET | `/api/questions/:id` | Get single question |
| POST | `/api/questions` | Create new question |
| PUT | `/api/questions/:id` | Update question |
| DELETE | `/api/questions/:id` | Delete question |
| POST | `/api/questions/bulk-action` | Bulk approve/reject/delete |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/users` | List users (paginated, filtered) |
| GET | `/api/users/:id` | Get user details + stats |
| POST | `/api/users/:id/ban` | Ban user |
| POST | `/api/users/:id/unban` | Unban user |
| DELETE | `/api/users/:id/stats` | Reset user stats |

### Reviews

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/reviews/next` | Get next unreviewed question |
| POST | `/api/reviews` | Submit review |
| GET | `/api/reviews/stats` | Review queue statistics |

### Broadcasts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/broadcasts` | List broadcast queue |
| POST | `/api/broadcasts` | Queue new broadcast |
| DELETE | `/api/broadcasts/:id` | Cancel pending broadcast |
| POST | `/api/broadcasts/:id/retry` | Retry failed broadcast |

### Generation

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/generation/pool-stats` | Current pool statistics |
| POST | `/api/generation/start` | Queue generation request |
| GET | `/api/generation/progress/:id` | Get generation progress |
| POST | `/api/generation/cancel/:id` | Cancel generation |
| GET | `/api/generation/history` | Past generation batches |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/engagement` | User engagement metrics |
| GET | `/api/analytics/performance` | Question performance |
| GET | `/api/analytics/costs` | API cost breakdown |
| GET | `/api/analytics/export` | Export data as CSV |

### Admin Management (Super Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admins` | List admins |
| POST | `/api/admins` | Add admin |
| PUT | `/api/admins/:id` | Update admin (promote/demote) |
| DELETE | `/api/admins/:id` | Remove admin |
| GET | `/api/admins/audit-log` | Admin action audit log |

---

## Implementation Phases

### Phase 1: Foundation (Week 1) - COMPLETE
- [x] Set up Bun project structure
- [x] Configure Hono with middleware
- [x] Implement SQLite connection with WAL
- [x] Create base layout and design system
- [x] Implement Telegram Login Widget auth
- [x] Session management with JWT
- [x] Basic dashboard page

### Phase 2: Core Features (Week 2) - MOSTLY COMPLETE
- [x] Questions browser with filters
- [ ] Question editor (create/edit) - **needs form implementation**
- [x] Review interface
- [x] User management
- [ ] WebSocket setup for real-time - **stub exists, needs full implementation**

### Phase 3: Advanced Features (Week 3) - PAGES DONE, NEEDS BACKEND
- [x] Analytics dashboard with Chart.js
- [x] Broadcast composer with queue - **UI done, needs bot processor**
- [x] Generation control with progress - **UI done, needs bot processor**
- [x] Admin management (super admin)

### Phase 4: Integration & Polish (Week 4) - NOT STARTED
- [ ] Update Docker configuration
- [x] Add new database tables for queues
- [ ] Python bot: Implement broadcast queue processor
- [ ] Python bot: Implement generation queue processor
- [ ] End-to-end testing
- [ ] Remove old Python web admin

### Phase 5: Documentation & Deployment - NOT STARTED
- [ ] Update CLAUDE.md with new web admin commands
- [ ] Update deployment documentation
- [ ] Create admin onboarding guide
- [ ] Production deployment

---

## Environment Variables

```bash
# Required for web admin
TELEGRAM_BOT_TOKEN=your_bot_token     # For auth verification
JWT_SECRET=random_32_char_string       # For session tokens
DATABASE_PATH=/app/data/abaquiz.db    # SQLite database path
WEB_PORT=8070                          # Web server port
WEB_HOST=0.0.0.0                       # Web server host

# Optional
LOG_LEVEL=INFO
NODE_ENV=production
```

---

## Migration Checklist

Before removing old Python web admin:

- [ ] All features ported to new admin
- [ ] All existing functionality tested
- [ ] Database migrations applied
- [ ] Docker builds and runs correctly
- [ ] Authentication works end-to-end
- [ ] WebSocket updates work
- [ ] Broadcast queue processing works
- [ ] Generation queue processing works
- [ ] Super admin can manage admins
- [ ] All API endpoints tested
- [ ] Production deployment verified

Files to remove after migration:
- `src/web/` (entire directory)
- `src/web/__init__.py`
- References in `src/main.py` to old web server
