# agents.aldhaheri.co — Build Checklist

Personal AI agent office — a manager agent that dynamically spawns, manages, and learns from specialized sub-agents. 6th service in the aldhaheri.co monorepo.

**Status legend:** `[ ]` pending · `[~]` in progress · `[x]` complete · `[!]` blocked

---

## Phase 0 — Design approval (no code)
- [x] File structure proposal reviewed
- [x] DB schema (all tables + columns) drafted
- [x] API route surface drafted
- [x] All open design questions resolved → see "Locked Design Decisions"
- [x] Subdomain reserved: `agents.aldhaheri.co` → ports `3004` (frontend) / `8004` (backend)
- [x] Volume name reserved: `agents-data`
- [ ] **Final user green light to begin Phase 1**

## Phase 1 — DB schema + models
- [x] Create `agents/backend/db.py` (async engine, session, `get_db`)
- [x] Create `agents/backend/models.py` (SQLAlchemy `Base` + Pydantic schemas for all 9 tables — added `proposals` for the self-improving loop)
- [x] Create `agents/backend/migrations.py` with FTS5 CREATE statement + seed functions (called from lifespan in Phase 2)
- [x] Wire `Base.metadata.create_all` into FastAPI lifespan
- [x] Add FTS5 virtual table for `agent_sessions` (called from lifespan)
- [x] Seed `user_profile` (single row) on first startup
- [x] Seed manager agent (singleton; deletion guard pending in Phase 3 route layer) on first startup

## Phase 2 — Auth + scaffolding
- [x] `agents/backend/main.py` with CORS, lifespan, health, router includes
- [x] `agents/backend/routers/auth.py` — `get_current_user()` reusing JWT cookie pattern
- [x] `agents/backend/Dockerfile` (python:3.11-slim, port 8004, finance-style `COPY . ./backend/` layout)
- [x] `agents/backend/requirements.txt` (pinned to match finance versions where shared)
- [x] `agents/docker-compose.yml` — **backend service only for now**; frontend service added in Phase 8
- [x] Add `include:` entry in root `docker-compose.yml`
- [x] Add Agents section to `.env.example` (notes reused vars)
- [x] `docker compose config` passes

## Phase 3 — Agent CRUD + manager routing
- [x] `routers/agents.py` — list, create, get-detail, update, soft-delete (manager protected)
- [x] `routers/manager.py` — `/api/manager/route` Sonnet call returning route|spawn JSON
- [x] `services/prompt_assembly.py` — SOUL → USER → MEMORY → SKILL → TASK composer + history parser
- [x] `services/anthropic_client.py` — sync+async clients, MODEL_SONNET, MODEL_HAIKU constants
- [x] `services/skill_matcher.py` — Haiku picks the single best skill (or none) per turn
- [x] Wire `agents.router` and `manager.router` into `main.py`

## Phase 4 — Chat endpoint with full prompt assembly
- [x] `routers/chat.py` with SSE streaming via `async_client.messages.stream()`
- [x] `services/sessions.py` — create/append/close + FTS5 helper
- [x] Session creation if no session_id passed; continuation if provided
- [x] FTS5 mirror append per user + assistant turn
- [x] Action block parser (`<action>...</action>` JSON, mirrors finance pattern)
- [x] Agent status transitions: idle → thinking → working → done (or error)
- [x] Token totals accumulated on the session row
- [x] Reflection kicked off async via `asyncio.create_task` (stub in `services/reflection.py`)
- [~] Action executor: spawn_agent / create_task / schedule_cron — frontend-driven; execute endpoints land alongside crons (Phase 6) and via `POST /api/agents` (existing). Memory/skill proposals come from reflection (Phase 5).

## Phase 5 — Self-improving loop
- [x] `services/reflection.py` — Haiku call → task_type classification + optional memory + skill proposals; persists a Task row + Proposals
- [x] `routers/proposals.py` — list (filterable by status/agent/kind), accept, reject
- [x] Memory append-only versioning enforced via `MAX(version) + 1` on accept
- [x] Skill creation flow: accept → new agent_skills row with `source=proposal_accepted` + `source_proposal_id`
- [x] 2nd-occurrence gate on skill proposals (task_type must already be in recent history)
- [x] `routers/memory.py` — get latest, list versions, manual edit (creates new version)
- [x] `routers/skills.py` — CRUD with slug-collision protection
- [x] `routers/user_profile.py` — get + update singleton USER.md

## Phase 6 — Cron engine
- [x] `services/scheduler.py` — AsyncIOScheduler init, register/unregister, restore-from-DB on boot
- [x] `services/cron_executor.py` — fresh isolated session per fire, FTS5 ingest, optional Telegram delivery, updates CronRun + CronJob.last_run_at
- [x] `services/nl_schedule.py` — Haiku NL → cron string, validated by `CronTrigger.from_crontab`
- [x] `services/telegram.py` — minimal sendMessage wrapper (reuses TELEGRAM_BOT_TOKEN/CHAT_ID)
- [x] `routers/crons.py` — two-step create (parse + confirm), CRUD, enable/disable, run-now, run history
- [x] Wire `start_scheduler()` + `shutdown_scheduler()` into the lifespan

## Phase 7 — Session search
- [x] `routers/sessions.py` — list (optional agent_id filter), get full transcript, FTS5 search
- [x] FTS5 `MATCH` query with `snippet()` returning highlighted excerpts ranked by relevance
- [x] Route order: `/search` registered before `/{session_id}` so it isn't swallowed

## Phase 8 — Frontend scaffolding
- [x] `agents/frontend/` Vite + React 19 + Tailwind 4 + react-router-dom (mirrors hub deps exactly)
- [x] `Dockerfile` (node:20-alpine → nginx:alpine, port 3004)
- [x] `nginx.conf` SPA fallback
- [x] `vite.config.js` — port 3004, `/api` proxy to `localhost:8004`
- [x] `src/services/api.js` — `credentials: 'include'`, 401 → redirect to aldhaheri.co
- [x] `src/services/{auth,agents,manager}.js` — typed API client wrappers
- [x] `src/config/theme.js` — color constants matching CLAUDE.md, plus STATUS_COLORS map
- [x] `src/components/ProtectedRoute.jsx` — verifies session before render
- [x] `src/components/Header.jsx` — project nav (Trade dropped, Agents active)
- [x] `eslint.config.js`, `.gitignore`, `index.html` matching hub

## Phase 9 — Office UI (isometric grid)
- [x] `pages/Office.jsx` — header, isometric grid centered, manager input pinned bottom. Polls `/api/agents` every 3s for status changes.
- [x] `components/IsoGrid.jsx` — 5x5 isometric grid via per-cell positioning (no CSS rotate; native iso math). Depth-sorted by `row + col` so back tiles render first.
- [x] `components/DeskCell.jsx` — SVG cell: floor rhombus + bevel highlight, three-polygon desk with side faces, a tiny laptop hint, and a status halo when active.
- [x] `components/AgentSprite.jsx` — procedural pixel-style SVG (rectangular body + head, eyes, shadow, optional manager crown). 4 status states (idle/thinking/working/done) + error fallback, with bob/pulse/typing-dot/spawn-in CSS animations.
- [x] Procedural SVG sprites — using simple geometric primitives so art can be swapped without layout changes (per locked design).
- [x] `components/ManagerInput.jsx` — bottom-pinned bar that POSTs `/api/manager/route`; shows route/spawn result inline (spawn approval card stub — full flow lands in Phase 10).
- [~] `components/ActivityFeed.jsx` — deferred to Phase 10 (chat panel will own the live SSE consumer).
- [~] `components/SpawnApprovalCard.jsx` — deferred to Phase 10 (chat stream needs to render it inline).
- [x] Cell spawn-in animation (fade + scale) via the `spawn-in` keyframe in `index.css`.
- [x] Status transition animations driven by polling for now; SSE in Phase 10.

## Phase 10 — Chat panel
- [x] `components/ChatPanel.jsx` — right-side slide-in with header, scrolling transcript, streaming bubble, input bar
- [x] SSE consumer via fetch + ReadableStream in `services/chat.js` (async generator yielding parsed events)
- [x] `components/SpawnApprovalCard.jsx` — inline editable card for manager-proposed agents (name / specialization / soul)
- [x] Spawn flow: manager returns `spawn` → panel opens in spawn mode → on Accept, `POST /api/agents` then immediately fires the original message
- [x] Action preview cards rendered inline under each assistant turn for any `<action>{...}</action>` blocks the model emits
- [x] Inline proposal cards: after each turn ends, polls `/api/proposals` and surfaces pending memory/skill proposals with Accept/Reject
- [x] `services/proposals.js` — list / accept / reject wrappers
- [x] `slide-in` keyframe animation on the panel
- [x] Office.jsx orchestrates: clicking a DeskCell opens chat for that agent; ManagerInput submission opens chat (route) or spawn approval (spawn)

## Phase 11 — Memory + Skills panels + global proposal queue
- [x] Refactor `ChatPanel.jsx` into a chat-tab body (no outer wrapper or header)
- [x] New `components/AgentPanel.jsx` — slide-in wrapper with header, sprite, tab strip (Chat | Memory | Skills); tabs hidden in spawn mode
- [x] `components/MemoryPanel.jsx` — raw markdown textarea, save-creates-new-version, expandable version-history list with source + timestamp
- [x] `components/SkillsPanel.jsx` — inline expanding form for add/edit, soft-delete with confirm, trigger keywords as chips, expandable instructions/frontmatter
- [x] `services/memory.js` + `services/skills.js` — typed API wrappers
- [x] `pages/Proposals.jsx` — global pending-proposal queue with per-row Accept/Reject; expandable proposed content + memory diff
- [x] `components/AppNav.jsx` — in-app sub-nav (Office | Proposals) sits below the project nav with a pending-count badge
- [x] Office.jsx polls `/api/proposals` so the badge stays current
- [x] After spawn-accept, Office transitions the active conversation from `spawn` to `chat` mode so AgentPanel re-renders with tabs
- [x] App.jsx registers the `/proposals` route behind `ProtectedRoute`

## Phase 12 — Cron manager UI
- [ ] `pages/Crons.jsx` — list, create (natural language input), edit, enable/disable
- [ ] `components/CronRunHistory.jsx` — per-job run log with output

## Phase 13 — Docker, deploy, hub card
- [x] Add `nginx/agents.aldhaheri.co` site config (SSE-friendly: `proxy_buffering off`, `proxy_http_version 1.1`, 600s timeouts)
- [x] Add DNS A record `agents → 165.232.162.72` (GoDaddy, propagated 2026-05-15)
- [x] On VPS: nginx site installed + reloaded, certbot issued cert (expires 2026-08-13)
- [x] Backend live: `docker compose up -d --build agents-backend`, `/health` returns 200
- [x] Verified seeds: USER profile (id=1, version=1), manager agent (id=1, role=manager), initial memory (version=1)
- [x] Verified FTS5: MATCH + snippet() work end-to-end against `agent_sessions_fts`
- [x] Auth gates: unauthenticated `/api/auth/verify` and `/api/agents` return 401
- [x] Build + deploy `agents-frontend` container — live at https://agents.aldhaheri.co
- [x] nginx site updated to dual-target: `/` → frontend (3004), `/api/` + `/health` → backend (8004). SSL re-attached via `certbot --reinstall`.
- [ ] Add `agents.aldhaheri.co` to hub's `projects.js` (waiting on Phase 10 to round out the UX before advertising)
- [ ] Update root `CLAUDE.md` (service table, scheduled jobs, env vars) — after Phase 10
- [ ] Update root `README.md` (project description, services, endpoints) — after Phase 10

## Phase 14 — Verification
- [ ] Create manager + first sub-agent end-to-end
- [ ] Memory proposal → accept → version row appears in DB
- [ ] Skill creation → next chat turn injects the skill
- [ ] Cron created via NL → fires on schedule → Telegram delivered
- [ ] FTS5 search returns expected results across sessions

---

## Locked Design Decisions (resolved 2026-05-15)

1. **Manager scope** — Auto-spawn. Manager decides when to spawn a new agent; no explicit user syntax required. User always gets an inline approval card before the spawn persists.
2. **Spawn UX** — Inline approval card rendered in the chat stream. Card shows proposed `name`, `specialization`, `soul`, with edit-before-accept fields.
3. **Reflection frequency** — Every assistant turn. Fires *after* the SSE stream completes, runs async (does not block the user), proposals queue up in `proposals` table and surface in the ProposalQueue UI.
4. **Skill auto-propose trigger** — On the 2nd occurrence of the same task type for a given agent. Reflection model classifies each turn into a task-type label and compares against the agent's recent task-type history. 2nd match → emit `new_skill` proposal.
5. **Cron NL parsing** — Haiku translates NL ("every Monday 9am") into a cron string. Backend returns the parsed expression to the UI for user confirmation before persistence.
6. **Memory edit mode** — Raw markdown textarea. No structured field UI.
7. **Office UI** — Animated scene, **top-down isometric grid**. Manager always center cell, sub-agents in surrounding cells. Pixel-art sprite avatars with four states: idle / thinking / working / done. Click a cell → chat panel slides in. Habbo / Stardew vibe on dark theme (#0F0F1A floor, #1A1A2E tiles, #7C3AED accents on active states).
8. **Storage** — DB-only. No markdown files on disk. The DB is the single source of truth for USER.md, AGENT_MEMORY, and skills.
9. **Streaming** — SSE via FastAPI `StreamingResponse` + Anthropic `client.messages.stream()`.
10. **Model split** — Sonnet (`claude-sonnet-4-6`) for: chat replies, manager routing. Haiku (`claude-haiku-4-5-20251001`) for: skill matching per turn, reflection/proposals, NL→cron parsing, task-type classification.

### Implications of the locked decisions

- **Reflection-every-turn cost mitigation**: streaming response returns immediately; reflection fires as `asyncio.create_task(...)` and writes to `proposals` without blocking. UI polls/streams the queue separately.
- **Task-type classification**: each turn's reflection call must produce a normalized task-type label (e.g. `summarize_pr`, `draft_email_followup`). Stored on the `tasks` row created for that turn. Skill proposal triggers on `COUNT(*) WHERE agent_id=? AND task_type=? >= 2`.
- **Spawn approval flow**: manager's `/api/manager/route` SSE stream can emit an `<action type="spawn">{...}</action>` block. Frontend renders an inline card; on accept, frontend POSTs `/api/agents` and re-routes the original message to the new agent.
- **Animated scene impact**: bumps the frontend dep list (likely `framer-motion`), gets its own subsection in Phase 9, and the aesthetic answer below locks the visual style.
