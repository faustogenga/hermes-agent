# lead-hunter feature specs

Three documents that together describe everything the
`lead-hunter-custom-backup-2026-05-05` branch added on top of
upstream Hermes. Use them to re-implement the feature on a fresh
branch from `main` without rerunning the painful upstream merge.

| Doc | What's in it |
|---|---|
| [`AGENTS_FEATURE.md`](./AGENTS_FEATURE.md) | Agent presets engine, the `Agents` dashboard page, the create/edit/activate/delete flow, source cards, plugin slots, CLI integration. |
| [`CRON_FEATURE.md`](./CRON_FEATURE.md)     | The `agent_name` field on cron jobs, the Daily Schedule Map, the schedule builder UI, timezone handling, dashboard CronPage. |
| [`DATA_LOCATIONS.md`](./DATA_LOCATIONS.md) | Where every preset, cron job, identity file, and memory lives on disk. Commands to copy templates back from the backup branch. |

## How to use these docs

When you create the fresh branch, work in this order:

```bash
git checkout main
git pull
git checkout -b lead-hunter-clean

# 1. Pull the source-of-truth files that don't depend on patches:
git checkout lead-hunter-custom-backup-2026-05-05 -- \
    agent/preset_templates/ \
    docs/lead-hunter/

# 2. Read AGENTS_FEATURE.md → implement Stage A (engine + API + page)
# 3. Read CRON_FEATURE.md   → implement Stage B (cron wiring + UI)
# 4. Read DATA_LOCATIONS.md → confirm paths line up before you ship
# 5. npm run build, hermes dashboard, smoke
```

Each spec doc ends with a numbered re-implementation order; follow
that sequence inside its scope.

## What's NOT in these specs

- The `connections` plugin (under `plugins/example-dashboard/`) —
  separate concern, port directly from the backup branch as a
  filesystem copy.
- The Hunter / Apollo / Airtable env-var entries in
  `hermes_cli/config.py` `OPTIONAL_ENV_VARS` — copy those over with
  a careful diff after the merge from main lands; they're pure-add.
- Personality definitions (`config.agent.personalities`) — the
  presets reference these by name. Add or migrate from the user's
  existing `config.yaml`.
