# FG Hermes Plugin Recovery + Reimplementation Plan

> For Hermes: use the existing fg-hermes docs as the source of truth, but reuse the recovered server-side implementation in `/home/ubuntu/.hermes/hermes-agent-lead-hunter-v2/plugins/fg_hermes/` wherever it matches the spec.

Goal: restore the fg-hermes agent-preset and preset-aware cron feature set into the current `FG-Hermes` checkout, with the heavy custom logic living under `plugins/fg_hermes/` so future upstream updates do not overwrite it.

Architecture: recover the plugin-first implementation from the older server checkout, then wire only the minimum required shared-file touch-points into the current Hermes codebase. Keep user data in `~/.hermes/agents/`, `~/.hermes/SOUL.md`, `~/.hermes/cron/jobs.json`, and `~/.hermes/config.yaml` exactly as described by `docs/fg-hermes/DATA_LOCATIONS.md`.

Tech Stack: Hermes Python backend, FastAPI dashboard routes, React/Vite dashboard, plugin manifests, cron scheduler, config YAML.

---

## Current factual inventory

1. Specs exist in the current repo:
   - `docs/fg-hermes/README.md`
   - `docs/fg-hermes/AGENTS_FEATURE.md`
   - `docs/fg-hermes/CRON_FEATURE.md`
   - `docs/fg-hermes/DATA_LOCATIONS.md`
   - `docs/fg-hermes/IMPLEMENTATION_PROMPT.md`

2. A prior implementation exists on the server and is recoverable:
   - `/home/ubuntu/.hermes/hermes-agent-lead-hunter-v2/plugins/fg_hermes/`
   - It already contains:
     - `agent/presets.py`
     - `dashboard/plugin_api.py`
     - `dashboard/manifest.json`
     - `web/AgentPage.tsx`
     - `web/CronPage.tsx`
     - `web/styles.css`
     - built-in preset templates for:
       - `lead-hunter`
       - `flight-finder`
       - `brussels-housing-hunter`

3. User data already exists on this server:
   - `~/.hermes/agents/default/AGENT.json`
   - `~/.hermes/agents/flight-finder/*`
   - `~/.hermes/agents/brussels-housing-hunter/*`
   - `~/.hermes/config.yaml` already contains `agent.active_preset: default`
   - `~/.hermes/cron/jobs.json` already contains cron jobs with `agent_name` values such as:
     - `lead-hunter`
     - `flight-finder`
     - `brussels-housing-hunter`

4. The current repo does not yet contain the fg-hermes implementation:
   - no `plugins/fg_hermes/` directory
   - no current source matches for `agent_preset`, `agent_name`, `active_preset`, or dashboard `getAgentProfile` client methods in the repo source

5. Current dashboard plugin system already supports the needed base shape:
   - plugin backend API via `plugins/<name>/dashboard/plugin_api.py`
   - plugin manifest-based tabs/routes
   - existing examples: `plugins/example-dashboard`, `plugins/kanban`, `plugins/hermes-achievements`

---

## Implementation strategy

### Task 1: Recover the plugin directory into the current repo
Objective: bring the recovered fg-hermes plugin code into the active checkout without touching user data.

Files:
- Create: `plugins/fg_hermes/**`
- Source of copy: `/home/ubuntu/.hermes/hermes-agent-lead-hunter-v2/plugins/fg_hermes/**`

Steps:
1. Copy the recovered plugin tree into the current repo.
2. Verify the copied files exist in the active checkout.
3. Do not write anything into `~/.hermes/agents/` or `~/.hermes/cron/`.

Verification:
- `find plugins/fg_hermes -maxdepth 4 -type f | sort`

### Task 2: Diff recovered plugin against the current specs
Objective: identify where the recovered implementation matches or drifts from the docs.

Files:
- Compare: `docs/fg-hermes/*.md`
- Compare: `plugins/fg_hermes/**/*`

Steps:
1. Audit `presets.py` against `AGENTS_FEATURE.md` public API.
2. Audit `dashboard/plugin_api.py` routes against the documented route set.
3. Audit `AgentPage.tsx` and `CronPage.tsx` against the current desired UX and dashboard plugin workflow.
4. Record any spec deviations before wiring shared files.

Verification:
- written gap list in this plan or a follow-up implementation note

### Task 3: Add missing plugin tests from the spec or recovered branch
Objective: give the recovered plugin a repeatable regression harness before deep wiring.

Files:
- Create or restore under `plugins/fg_hermes/tests/`
- Update: `pyproject.toml` if needed

Steps:
1. Check whether tests exist in the recovered source.
2. Restore them if present; otherwise author minimal route/engine tests.
3. Ensure pytest can discover them.

Verification:
- `pytest plugins/fg_hermes/tests -q`

### Task 4: Wire agent preset support into shared Python touch-points
Objective: make runtime prompt assembly and CLI understand presets while keeping most code in the plugin.

Files to patch minimally:
- `agent/prompt_builder.py`
- `run_agent.py`
- `cli.py`
- `hermes_cli/config.py`

Verification:
- repo search finds `agent_preset` and `active_preset`
- targeted tests for prompt loading and CLI flag behavior

### Task 5: Wire preset-aware cron support into shared cron touch-points
Objective: make cron jobs persist and pass `agent_name` into `AIAgent`.

Files to patch minimally:
- `cron/jobs.py`
- `cron/scheduler.py`
- `tools/cronjob_tools.py`
- `hermes_time.py`
- `hermes_cli/web_server.py`

Verification:
- repo search finds `agent_name`
- create/list/update cron APIs include `agent_name`

### Task 6: Wire dashboard frontend imports/routes to plugin pages
Objective: let the dashboard use plugin-owned Agent/Cron pages rather than fragile in-place edits.

Files to patch minimally:
- `web/src/App.tsx`
- `web/src/lib/api.ts`
- `web/vite.config.ts`
- `web/tsconfig.app.json`
- `web/src/index.css`
- possibly `web/package.json`

Verification:
- `npm --prefix web run build`
- built assets update cleanly

### Task 7: Verify against real server data
Objective: prove the plugin reads the already-existing server state correctly.

Checks:
1. presets discovered include `default`, `flight-finder`, `brussels-housing-hunter`, and built-in `lead-hunter`
2. cron jobs show existing `agent_name` assignments from `~/.hermes/cron/jobs.json`
3. default save path still maps to `~/.hermes/SOUL.md`
4. dashboard plugin routes mount under `/api/plugins/fg-hermes/`

---

## Non-goals for the first pass

- rewriting user data
- deleting or migrating existing `~/.hermes/agents/*`
- force-pushing or changing branch tracking strategy
- inventing a new architecture when a recoverable implementation already exists on the server

---

## Immediate next action

Recover `plugins/fg_hermes/` from `/home/ubuntu/.hermes/hermes-agent-lead-hunter-v2/plugins/fg_hermes/` into the active `FG-Hermes` checkout, then inspect the copied code before patching shared files.
