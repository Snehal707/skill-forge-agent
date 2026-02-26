# Skill Forge — AGENTS.md
> Drop this file in the root of your project. Cursor will read it automatically.

## What We're Building
**Skill Forge** is an autonomous agent built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
that teaches itself new skills by researching a domain, writing a SKILL.md document, validating it
by actually executing the procedure in a sandbox, and saving it to the Hermes skills library.
Every key event is pushed to the user's Telegram AND to a live Vercel dashboard.

---

## Project Structure
```
skill-forge/
├── AGENTS.md                  ← this file (Cursor reads it)
├── skill_forge.py             ← main entry point / CLI
├── forge/
│   ├── __init__.py
│   ├── researcher.py          ← web research + doc scraping via Firecrawl
│   ├── writer.py              ← LLM skill writer (produces SKILL.md)
│   ├── validator.py           ← runs the skill procedure in a sandbox terminal
│   ├── notifier.py            ← Telegram notifications
│   ├── skill_manager.py       ← reads/writes to ~/.hermes/skills/
│   ├── summarizer.py          ← daily summary report builder
│   ├── llm.py                 ← single LLM call helper
│   └── db.py                  ← Supabase client (all DB calls go here)
├── dashboard/                 ← Next.js app → deployed to Vercel
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           ← main dashboard page
│   │   └── globals.css
│   ├── components/
│   │   ├── SkillCard.tsx
│   │   ├── StatsBar.tsx
│   │   ├── LiveFeed.tsx       ← real-time event stream
│   │   └── SkillModal.tsx     ← click skill → see full SKILL.md
│   ├── lib/
│   │   └── supabase.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.ts
├── config/
│   └── forge_config.yaml
├── prompts/
│   ├── researcher_prompt.txt
│   ├── writer_prompt.txt
│   └── validator_prompt.txt
├── tests/
├── requirements.txt
└── README.md
```

---

## Tech Stack

### Python Agent
- **Python 3.11+**
- **python-telegram-bot** — Telegram notifications
- **Firecrawl Python SDK** — web scraping
- **OpenRouter API** — LLM calls via openai SDK
- **supabase-py** — writing events + skills to Supabase
- **PyYAML**, **rich**, **schedule**, **loguru**

### Dashboard (Vercel)
- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS**
- **Supabase JS client** — real-time subscriptions
- **shadcn/ui** — components
- **react-markdown** + **rehype-highlight** — render SKILL.md beautifully

---

## Key Dependencies (requirements.txt)
```
openai>=1.0.0
firecrawl-py
python-telegram-bot>=20.0
pyyaml
rich
requests
supabase
schedule
loguru
```

---

## Environment Variables

### Python agent (.env)
```
OPENROUTER_API_KEY=sk-or-...
FIRECRAWL_API_KEY=fc-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=your_numeric_id
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key   # never expose in frontend
SKILLS_DIR=~/.hermes/skills
DASHBOARD_URL=https://your-app.vercel.app
```

### Vercel dashboard (set in Vercel project env settings)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

---

## Supabase Setup
Go to supabase.com → new project → SQL editor → run this:

```sql
-- Skills table
create table skills (
  id uuid default gen_random_uuid() primary key,
  name text not null,
  domain text not null,
  category text not null,
  description text,
  content text,             -- full SKILL.md markdown
  validation_passed boolean default false,
  sources_count integer default 0,
  attempts integer default 1,
  created_at timestamptz default now()
);

-- Events table (live feed)
create table events (
  id uuid default gen_random_uuid() primary key,
  event_type text not null,
  -- event_type values: research_start | research_done | writing |
  --                    validating | validated_ok | validated_fail | saved | error
  domain text,
  skill_name text,
  message text not null,
  metadata jsonb,
  created_at timestamptz default now()
);

-- Enable realtime on both tables
alter publication supabase_realtime add table skills;
alter publication supabase_realtime add table events;
```

After creating tables:
- Go to Settings → API → copy `URL`, `anon key` (for frontend), `service_role key` (for Python)

---

## Core Data Flow

```
User: "Learn Docker"
        ↓
[researcher.py] → db.insert_event("research_start") → Telegram notify
        ↓
[writer.py]     → db.insert_event("writing")         → Telegram notify
        ↓
[validator.py]  → db.insert_event("validating")      → Telegram notify
                → db.insert_event("validated_ok" or "validated_fail")
        ↓
[skill_manager] → db.insert_skill(...)               → Telegram notify
                → db.insert_event("saved")
        ↓
[Supabase realtime pushes to Vercel dashboard] ✨
```

---

## Dashboard Design (dashboard/)

### Layout
- Dark background `#0a0a0a`, terminal/hacker aesthetic
- JetBrains Mono for code elements, Inter for body text

### StatsBar (top of page)
Four stats with animated number counts:
- Total Skills Learned
- Skills Today
- Validation Success Rate (%)
- Domains Covered

### Two-column layout below StatsBar

**LiveFeed (left, 40%):**
- Real-time stream of `events` table via Supabase subscription
- Each event: timestamp + emoji icon + message
- Color coded: 🟢 green=success, 🟡 yellow=in-progress, 🔴 red=failed, 🔵 blue=info
- New events slide in from top, auto-scroll to latest
- Label at top: "LIVE" with a pulsing dot

**SkillGrid (right, 60%):**
- Cards from `skills` table, newest first
- Each card: skill name, domain tag, category tag, validation badge (✅ / ⚠️), time ago
- Filter bar: filter by domain or category
- Click → SkillModal

### SkillModal
- Slide-in panel from right
- Full SKILL.md rendered with react-markdown + syntax highlighting for code blocks
- Header: skill name, domain, validation badge
- Footer: sources count | attempts taken | saved timestamp
- "Copy SKILL.md" button

### Design tokens
```
--bg:          #0a0a0a
--surface:     #111111
--border:      #1f1f1f
--text:        #f0f0f0
--muted:       #555555
--green:       #00ff87
--yellow:      #ffd700
--red:         #ff4444
--blue:        #4488ff
```

---

## SKILL.md Format
```markdown
---
name: skill-name-kebab-case
description: One sentence about what this skill enables
version: 1.0.0
metadata:
  skill_forge:
    domain: "docker"
    generated_at: "2026-02-26T10:00:00Z"
    validation_passed: true
    sources_used: 3
  hermes:
    tags: [docker, containers, devops]
    category: devops
---

# Skill Title

## When to Use
Clear trigger conditions.

## Prerequisites
- What needs to be installed first

## Procedure
1. Step one: `command here`
2. Step two
3. Step three

## Verification
How to confirm it worked.

## Pitfalls
- Known failure modes

## Sources
- URL 1
```

---

## Telegram Notification Templates
```python
NOTIF_RESEARCH_START  = "🔍 *Skill Forge* — Researching: `{domain}`"
NOTIF_RESEARCH_DONE   = "📖 Research complete — {source_count} sources for `{domain}`"
NOTIF_WRITING         = "✍️ Writing skill: `{skill_name}`"
NOTIF_VALIDATING      = "🧪 Validating `{skill_name}` in sandbox..."
NOTIF_VALIDATED_OK    = "✅ *Skill learned!*\n`{skill_name}`\n_{description}_\n\n{steps_tested} steps validated"
NOTIF_VALIDATED_FAIL  = "⚠️ Validation failed for `{skill_name}`\nRetrying... (attempt {attempt}/3)"
NOTIF_SAVED           = "📚 Saved: `{skill_name}`\n🌐 [View on dashboard]({dashboard_url})"
NOTIF_DAILY_SUMMARY   = """
📊 *Skill Forge — Daily Report*
━━━━━━━━━━━━━━━━━━━
✅ Learned today: {learned}
{learned_list}
❌ Failed: {failed}
{failed_list}
📈 Total skills: {total}
🌐 {dashboard_url}
━━━━━━━━━━━━━━━━━━━
"""
```

---

## forge/db.py Convention
```python
"""All Supabase database operations. Never import supabase client outside this module."""
import os
from supabase import create_client, Client

def get_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

def insert_event(event_type: str, domain: str = "", skill_name: str = "",
                 message: str = "", metadata: dict = {}) -> None: ...

def insert_skill(name: str, domain: str, category: str, description: str,
                 content: str, validation_passed: bool,
                 sources_count: int, attempts: int) -> None: ...

def get_stats() -> dict: ...  # returns total, today_count, success_rate, domains
```

## forge/llm.py Convention
```python
"""Single LLM call helper. All LLM calls go through here."""
import os
from openai import OpenAI

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
DEFAULT_MODEL = "anthropic/claude-sonnet-4"

def llm_call(user_prompt: str, system_prompt: str, model: str = DEFAULT_MODEL) -> str: ...
```

---

## Coding Conventions
- Type hints on every function
- Module-level docstring on every module
- `rich.console.Console` for all terminal output — no bare `print()`
- `loguru` for file logging
- Every external API call wrapped in try/except
- Dataclasses for all DTOs: ResearchBundle, SkillDraft, ValidationResult
- All LLM calls → `forge/llm.py` only
- All DB calls → `forge/db.py` only

## What NOT to Do
- Never hardcode API keys
- Never skip YAML frontmatter validation before saving a skill
- Never run validation commands directly on host — Docker subprocess only
- Never use `SUPABASE_SERVICE_KEY` in the Next.js frontend
- Never use class components in React — functional + hooks only
- Never put dashboard code inside the Python package
