# lead_hunter — feature specs (plugin-based)

Three documents that together describe the **`lead_hunter` plugin** —
a self-contained directory under `plugins/` that adds:

- Custom **agent presets** (Lead Hunter, Flight Finder, Brussels
  Housing Hunter, etc.) with a dashboard `Agents` tab to create / edit
  / delete / activate them.
- **Cron jobs that pick which agent preset to run as** (so each
  scheduled job has its own identity), plus a richer cron dashboard
  page.

## Why a plugin

Hermes upstream ships with a `plugins/` mechanism:
- Backend Python lives at `plugins/<name>/dashboard/plugin_api.py`
  and is auto-mounted at `/api/plugins/<name>/`.
- Frontend code lives under the plugin and is wired in via the
  dashboard's plugin SDK (or via Vite aliases for full TSX pages).
- `plugins/<name>/` is **never touched by upstream merges**.

By building these features as a plugin instead of patching upstream
files, every future `git pull upstream main` is safe — our agent
preset engine, our `AgentPage`, our `CronPage` customizations, and
our new API routes all live inside one directory upstream doesn't
own.

The only shared-file edits we accept are:
- a Vite alias (so the canonical `@/pages/AgentPage` import resolves
  into our plugin),
- a tiny `.gitattributes merge=ours` pin for the handful of upstream
  files that need a one-line tweak (registering the active-preset
  config key, hooking `agent_preset` into `prompt_builder.py`).

## The three docs

| Doc | What's in it |
|---|---|
| [`AGENTS_FEATURE.md`](./AGENTS_FEATURE.md) | Agent-preset engine, dashboard `Agents` page, create/edit/activate/delete flow, source cards, plugin slots, CLI integration. |
| [`CRON_FEATURE.md`](./CRON_FEATURE.md)     | The `agent_name` field on cron jobs (which preset runs the job), Daily Schedule Map, schedule builder, timezone handling, dashboard CronPage. |
| [`DATA_LOCATIONS.md`](./DATA_LOCATIONS.md) | Where every preset, cron job, identity file, and memory lives on disk. The user data contract. |

## Build order on a clean main checkout

```bash
git checkout main && git pull upstream main
git checkout -b your-feature-branch

# Step 1 — create the plugin scaffold
mkdir -p plugins/lead_hunter/{agent/preset_templates,dashboard,web,cli,cron,hooks,tests}

# Step 2 — implement per AGENTS_FEATURE.md (engine, API, page)
# Step 3 — implement per CRON_FEATURE.md   (cron wiring, page)
# Step 4 — verify against DATA_LOCATIONS.md (paths, file shapes)
# Step 5 — npm run build, hermes dashboard, smoke
```

Each spec doc ends with a numbered re-implementation checklist —
follow that order inside its scope.

## What lives outside the plugin (and why)

A handful of touch-points have to live in upstream files because
Python imports / runtime hooks aren't fully pluggable:

- `agent/prompt_builder.py` — accept an optional `agent_preset` kwarg
  on `load_soul_md()` and `build_context_files_prompt()`. Tiny patch.
- `run_agent.py` — read `agent_preset` from constructor + apply
  during prompt assembly. Tiny patch.
- `cli.py` — accept `--agent <slug>` flag + register `/agent` slash
  command. Tiny patch.
- `cron/scheduler.py` — pass `job.get("agent_name")` as
  `agent_preset` when spawning `AIAgent`. One-line patch.
- `hermes_cli/config.py` — add `"active_preset": "default"` under
  `DEFAULT_CONFIG["agent"]`. One-line patch.

These are listed in each spec under **"Shared-file touch-points"**
and should each be marked `merge=ours` in `.gitattributes` so future
upstream merges keep our version. The actual *implementation* of all
the logic lives inside `plugins/lead_hunter/` — these touch-points
are just dispatcher hooks.

## What's NOT in these specs

- The `connections` plugin (under `plugins/example-dashboard/`) —
  separate concern; copy that directory in once, then leave alone.
- Hunter / Apollo / Airtable env-var entries in `OPTIONAL_ENV_VARS` —
  pure-add additions; copy into a `plugins/lead_hunter/env_keys.py`
  module that registers them at import time.
- Personality definitions (`config.agent.personalities`) — these are
  user-editable values in `~/.hermes/config.yaml`, not code.
