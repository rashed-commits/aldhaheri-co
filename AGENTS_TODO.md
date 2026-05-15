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
- [ ] `routers/agents.py` — list, create, get, update soul, soft-delete
- [ ] `routers/manager.py` — `/api/manager/route` (manager picks agent or proposes spawn)
- [ ] `services/prompt_assembly.py` — builds SOUL → USER → MEMORY → SKILL → TASK → HISTORY
- [ ] `services/anthropic_client.py` — shared Anthropic client + model constants
- [ ] `services/skill_matcher.py` — Haiku-based skill picker per turn

## Phase 4 — Chat endpoint with full prompt assembly
- [ ] `routers/chat.py` with SSE streaming via `client.messages.stream()`
- [ ] Session creation + transcript append per turn
- [ ] FTS5 index update on each turn
- [ ] Action block parser (reusable from finance pattern: `<action>{...}</action>`)
- [ ] Action executor: spawn_agent, update_memory, propose_skill, create_task, schedule_cron

## Phase 5 — Self-improving loop
- [ ] `services/reflection.py` — post-response Haiku call → memory & skill proposals
- [ ] `routers/proposals.py` — list pending, accept, reject
- [ ] Memory append-only versioning (each accept creates new `agent_memory` row)
- [ ] Skill creation flow (accept proposal → write `agent_skills` row)

## Phase 6 — Cron engine
- [ ] `services/scheduler.py` — APScheduler init in lifespan, restore jobs from DB on boot
- [ ] `services/cron_executor.py` — runs an agent in a fresh session, writes `cron_runs` row, optional Telegram delivery
- [ ] `routers/crons.py` — CRUD, enable/disable, manual trigger, list runs per job
- [ ] Natural-language schedule parser (Haiku → cron string, validated)
- [ ] Reuse `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` for delivery

## Phase 7 — Session search
- [ ] `routers/sessions.py` — list, get full transcript, search via FTS5
- [ ] FTS5 query: `MATCH` against indexed content, return ranked snippets

## Phase 8 — Frontend scaffolding
- [ ] `agents/frontend/` Vite + React 19 + Tailwind 4 init (mirror hub)
- [ ] `Dockerfile` (node:20-alpine → nginx:alpine, port 3004)
- [ ] `nginx.conf` SPA fallback
- [ ] `vite.config.js` with `/api` proxy to `localhost:8004`
- [ ] `src/services/api.js` fetch wrapper with `credentials: 'include'`, 401 → redirect
- [ ] Theme constants matching CLAUDE.md (#0F0F1A, #1A1A2E, #7C3AED, etc.)
- [ ] `ProtectedRoute` + `/api/auth/verify` flow

## Phase 9 — Office UI (isometric grid)
- [ ] `pages/Office.jsx` — isometric grid container, manager pinned to center cell, sub-agent cells laid out around it (expanding ring as more spawn)
- [ ] `components/IsoGrid.jsx` — CSS-grid + `transform: rotateX(60deg) rotateZ(-45deg)` board, depth-sorted cells
- [ ] `components/DeskCell.jsx` — a single tile: floor texture, desk graphic, agent sprite, name label, ambient state effect
- [ ] `components/AgentSprite.jsx` — sprite with 4 animation states (idle / thinking / working / done). Framer Motion variants for bobbing, typing puff, completion flash
- [ ] Source/commission pixel-art sprites (or generate via simple SVG primitives initially — can swap art later)
- [ ] `components/ManagerInput.jsx` — global input bar pinned bottom-center, calls `/api/manager/route`
- [ ] `components/ActivityFeed.jsx` — slide-out drawer with live SSE feed of sessions/crons/proposals
- [ ] `components/SpawnApprovalCard.jsx` — inline card rendered in the chat stream when manager emits `<action type="spawn">`; editable name/specialization/soul fields before accept
- [ ] Cell spawn-in animation (fade + scale from grid origin) when a new agent is created
- [ ] Status transition animations (idle → thinking → working → done) driven by SSE `agent_status` events

## Phase 10 — Chat panel
- [ ] `components/ChatPanel.jsx` — slides in from right when agent clicked
- [ ] SSE consumer (EventSource or fetch+ReadableStream)
- [ ] Action approval UI (mirrors finance chatbot pattern)
- [ ] Inline proposal cards (memory/skill) post-response

## Phase 11 — Memory + Skills panels
- [ ] `components/MemoryPanel.jsx` — markdown view + edit, version history
- [ ] `components/SkillsPanel.jsx` — list with frontmatter, edit, create, soft-delete
- [ ] `components/ProposalQueue.jsx` — global view of all pending proposals

## Phase 12 — Cron manager UI
- [ ] `pages/Crons.jsx` — list, create (natural language input), edit, enable/disable
- [ ] `components/CronRunHistory.jsx` — per-job run log with output

## Phase 13 — Docker, deploy, hub card
- [ ] Add `agents.aldhaheri.co` to hub's `projects.js`
- [ ] Add `nginx/agents.aldhaheri.co` site config (port 80 only — certbot adds SSL)
- [ ] Add DNS A record `agents → 165.232.162.72`
- [ ] On VPS: certbot, `docker compose up -d --build`, verify `/health`
- [ ] Update root `CLAUDE.md` (service table, scheduled jobs, env vars)
- [ ] Update root `README.md` (project description, services, endpoints)

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
