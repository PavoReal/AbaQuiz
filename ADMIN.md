# Admin & Utility Features Reference

A high-level overview of admin and utility features implemented in this Telegram bot. Use as a reference for implementing similar features in other projects.

---

## 1. Tiered Whitelist System

**Purpose:** Control who can access the bot with different permission levels.

### Configuration
```json
{
  "whitelist": {
    "admin_users": [123456789],
    "allowed_users": [987654321],
    "rejection_messages": [
      "Nice try, but you're not on the list. Your ID ({user_id}) has been noted."
    ]
  }
}
```

### Tiers
| Tier | Access |
|------|--------|
| `admin_users` | Full bot access + admin commands |
| `allowed_users` | Regular bot access only |
| Not listed | Rejected with random snarky message |

### Runtime Management Commands
| Command | Description |
|---------|-------------|
| `/whitelist list` | Show all whitelisted users |
| `/whitelist add <id>` | Add user to allowed list |
| `/whitelist remove <id>` | Remove from allowed list |
| `/whitelist promote <id>` | Move user to admin tier |
| `/whitelist demote <id>` | Move admin to allowed tier |

### Implementation Notes
- Changes persist to config file at runtime
- Prevents demoting yourself or last admin
- Logs all whitelist changes

---

## 2. Middleware Architecture

**Purpose:** Composable access control and request processing.

### Middleware Stack
```python
@dm_only_middleware           # 1. Only allow private chats
@whitelist_middleware(...)    # 2. Check authorization
@rate_limit_middleware(...)   # 3. Enforce rate limits (optional)
async def handler(update, context):
    ...
```

### Available Middleware

| Middleware | Purpose |
|------------|---------|
| `dm_only_middleware` | Silently ignore group chats |
| `whitelist_middleware` | Check user is admin or allowed |
| `admin_middleware` | Restrict to admin users only |
| `rate_limit_middleware` | Enforce per-user daily limits |

### Whitelist Middleware Features
- Random rejection messages with `{user_id}` placeholder
- Auto-creates user record in database
- Logs incoming messages: `[user_id] >> message`
- Triggers unauthorized access alerts

---

## 3. Admin Notification System

**Purpose:** Keep admins informed about bot activity and security events.

### Features

#### Real-time Unauthorized Access Alerts
```
*Unauthorized Access Attempt*

User ID: 123456789
Username: @suspicious_user
Name: John Doe

*Message:*
> Their attempted message here
```

#### Daily Usage Summaries
```
*Daily Summary - 01/13/2026*

*Overall Activity (Last 24h):*
Messages processed: 47
Input tokens: 23,456
Output tokens: 12,345
Estimated cost: $0.15

*Per-User Breakdown:*
- 123456789: 30 msgs | $0.10
- 987654321: 17 msgs | $0.05
```

### Per-Admin Preferences
| Command | Description |
|---------|-------------|
| `/notify status` | Show current settings |
| `/notify summary on\|off` | Toggle daily summaries |
| `/notify alerts on\|off` | Toggle access alerts |

### Configuration
```json
{
  "admin": {
    "summary_time": "09:00",
    "default_summary_enabled": true,
    "default_alerts_enabled": true
  }
}
```

### Database Schema
```sql
CREATE TABLE admin_settings (
    telegram_id INTEGER PRIMARY KEY,
    summary_enabled BOOLEAN DEFAULT TRUE,
    alerts_enabled BOOLEAN DEFAULT TRUE
)
```

---

## 4. Token Usage Tracking & Cost Monitoring

**Purpose:** Track API usage and estimate costs.

### Tracked Metrics (per note)
| Field | Description |
|-------|-------------|
| `input_tokens` | Tokens sent to LLM |
| `output_tokens` | Tokens received from LLM |
| `cache_creation_tokens` | Prompt cache write tokens |
| `cache_read_tokens` | Prompt cache hit tokens |
| `model` | Model used for processing |

### Cost Configuration
```json
{
  "pricing": {
    "anthropic": {
      "claude-sonnet-4-5": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "cache_write_per_million": 3.75,
        "cache_read_per_million": 0.30
      }
    }
  }
}
```

### Admin Usage Command
`/usage` - Shows rolling 24h stats:
- Total messages processed
- Token counts by type
- Estimated cost
- Per-user breakdown

---

## 5. Admin Access to User Data

**Purpose:** Allow admins to view/export other users' data for support.

### Extended Commands
| Command | Description |
|---------|-------------|
| `/history [@user\|id]` | View user's recent notes |
| `/history all [@user\|id]` | View user's full history |
| `/stats [@user\|id]` | View user's statistics |
| `/export [@user\|id]` | Export user's notes as file |

### User Resolution
- By Telegram ID: `/history 123456789`
- By username: `/history @john`
- Case-insensitive username lookup

### Implementation
```python
async def resolve_user_identifier(identifier: str, repository) -> tuple[int | None, str | None]:
    # Strip @ if present
    # Try parsing as numeric ID first
    # Fall back to username lookup in database
    # Return (user_id, None) or (None, error_message)
```

---

## 6. Rate Limiting

**Purpose:** Prevent abuse and control API costs.

### Configuration
```json
{
  "rate_limit": {
    "notes_per_day": 100
  }
}
```

### Implementation
- Database-backed counter (notes per user per day)
- Resets at midnight
- Shows friendly message when exceeded
- Applied via middleware, not in handler

### Database Query
```sql
SELECT COUNT(*) FROM notes
WHERE telegram_id = ? AND date(created_at) = date('now')
```

---

## 7. Telegram Command Menus

**Purpose:** Show different command autocomplete menus for different users.

### Implementation
```python
from telegram._botcommandscope import BotCommandScopeDefault, BotCommandScopeChat

# Default commands for all users
await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())

# Extended commands for each admin (scoped to their DM)
for admin_id in admin_users:
    scope = BotCommandScopeChat(chat_id=admin_id)
    await bot.set_my_commands(ADMIN_COMMANDS, scope=scope)
```

### Notes
- Use `BotCommandScopeChat` for private chats (not `BotCommandScopeChatMember`)
- Wrap in try/except - fails if admin hasn't `/start`ed the bot
- Call in `post_init` after application is built

---

## 8. Database Schema Migrations

**Purpose:** Add new columns without breaking existing databases.

### Pattern
```python
async def _migrate_schema(self, db: aiosqlite.Connection) -> None:
    # Get existing columns
    async with db.execute("PRAGMA table_info(notes)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}

    # Add missing columns
    if "new_column" not in columns:
        await db.execute(
            "ALTER TABLE notes ADD COLUMN new_column INTEGER DEFAULT 0"
        )
```

### Best Practices
- Always use `DEFAULT` values for new columns
- Run migrations in `initialize()` before any queries
- Check column existence before ALTER

---

## 9. Scheduled Jobs

**Purpose:** Run periodic tasks like auto-flush and daily summaries.

### Setup
```python
from datetime import time as dt_time
from telegram.ext import Application

job_queue = application.job_queue
if job_queue:
    hour, minute = 9, 0
    job_queue.run_daily(
        daily_summary_job,
        time=dt_time(hour=hour, minute=minute),
        name="daily_summary",
    )
```

### Error Handling
```python
if job_queue is None:
    logger.warning(
        "Feature requires JobQueue. "
        "Install with: pip install 'python-telegram-bot[job-queue]'"
    )
```

---

## 10. Logging Best Practices

### Message Format
```
[user_id] >> incoming message
[user_id] << outgoing response
```

### Suppress Noisy Logs
```python
# Filter httpx polling logs
logging.getLogger("httpx").setLevel(logging.WARNING)
```

### Log Admin Actions
```python
logger.info(f"Admin {user.id} added user {target_id} to whitelist")
logger.warning(f"Unauthorized access attempt from user {user.id}")
```

---

## 11. Configuration System

### Environment Variable Substitution
```json
{
  "api_key": "${MY_API_KEY}"
}
```

```python
def substitute_env_vars(obj):
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        return os.environ.get(var_name, "")
    # Recurse for dicts/lists...
```

### Config Structure
```
config/
├── config.json      # Main config (loads env vars)
└── task_list.json   # Domain-specific data
```

---

## Quick Reference: Admin Commands

| Command | Description |
|---------|-------------|
| `/whitelist` | Manage user access |
| `/notify` | Notification preferences |
| `/usage` | 24h usage stats and costs |
| `/history [@user]` | View user's notes |
| `/stats [@user]` | View user's statistics |
| `/export [@user]` | Export user's notes |

---

## Files Involved

| File | Purpose |
|------|---------|
| `src/bot/middleware.py` | Whitelist, admin, rate limit middleware |
| `src/bot/notifications.py` | NotificationService class |
| `src/bot/commands.py` | Telegram command menu registration |
| `src/bot/handlers.py` | Admin command handlers |
| `src/db/repository.py` | Admin settings, usage queries |
| `config/config.json` | Whitelist, pricing, admin settings |
