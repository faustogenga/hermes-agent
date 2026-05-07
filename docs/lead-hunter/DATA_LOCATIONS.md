# Data Locations — where presets and cron jobs actually live

Companion to [`AGENTS_FEATURE.md`](./AGENTS_FEATURE.md) and
[`CRON_FEATURE.md`](./CRON_FEATURE.md). Knowing these paths matters
because:

- Re-implementing the feature on a fresh branch from main does **not**
  need to migrate this data — it's already on disk and the new code
  reads from the same paths.
- If you nuke `$HERMES_HOME/agents/` you lose all your custom presets.
- If you nuke `$HERMES_HOME/cron/jobs.json` you lose every scheduled
  job.

---

## `$HERMES_HOME` resolution

Defined in `hermes_constants.py`:

```python
def get_hermes_home() -> Path:
    val = os.environ.get("HERMES_HOME", "").strip()
    return Path(val) if val else Path.home() / ".hermes"
```

On this machine: `$HOME = /Users/faust1`, so `HERMES_HOME =
/Users/faust1/.hermes` unless the env var is set.

A profile-mode install (where `hermes profiles use <name>` was run)
puts `HERMES_HOME` at `~/.hermes/profiles/<name>`. The path lookups
below stay relative to whatever `get_hermes_home()` returns.

---

## Agent preset storage

### Built-in templates (in repo, version-controlled)

Source of truth shipped with the code:

```
agent/preset_templates/
├── brussels-housing-hunter/AGENT.json
├── brussels-housing-hunter/AGENTS.md
├── brussels-housing-hunter/SOUL.md
├── flight-finder/AGENT.json
├── flight-finder/AGENTS.md
├── flight-finder/SOUL.md
└── lead-hunter/AGENT.json
    lead-hunter/AGENTS.md
    lead-hunter/SOUL.md
```

When re-implementing, copy these directories from
`lead-hunter-custom-backup-2026-05-05:agent/preset_templates/` onto
the new branch.

```bash
git checkout lead-hunter-custom-backup-2026-05-05 -- agent/preset_templates/
```

(That command works as long as the destination directory doesn't
exist on the new branch — same trick we used during Stage 1 of the
plugin extraction.)

### User-created and user-overridden presets

Per-host, **not in git** — lives under `$HERMES_HOME/agents/`:

```
~/.hermes/agents/
├── default/                       (override of the built-in default)
│   ├── AGENT.json
│   └── AGENTS.md                  (the SOUL.md is at ~/.hermes/SOUL.md)
├── lead-hunter/                   (user's edited copy of the template)
│   ├── AGENT.json
│   ├── SOUL.md
│   └── AGENTS.md
└── <user-created-slug>/
    ├── AGENT.json
    ├── SOUL.md
    └── AGENTS.md
```

> On this host, `~/.hermes/agents/` does not exist yet — the user has
> only the built-in templates active. The dir is created lazily the
> first time `save_agent_preset()` runs (on `POST /agents` or `PUT
> /agents/{slug}`).

The default preset's `SOUL.md` is the legacy file at
`~/.hermes/SOUL.md`, NOT `~/.hermes/agents/default/SOUL.md`. The
override directory only carries `AGENT.json` (metadata) and optional
`AGENTS.md` (project context).

### Active preset

Stored in YAML config at `$HERMES_HOME/config.yaml`:

```yaml
agent:
  active_preset: lead-hunter
```

Default value: `"default"`. Set via:
- the dashboard `Activate` button (`POST /agents/{slug}/activate`)
- the CLI `/agent use <slug>` slash command
- the CLI flag `--agent <slug>` (sets it for one session, doesn't
  persist unless the slash command is also run)

---

## Cron job storage

### Jobs file

```
~/.hermes/cron/jobs.json
```

A JSON list of job dicts. Each entry's relevant fields:

```json
{
  "id": "abc123def456",
  "name": "Daily lead briefing",
  "prompt": "Find new leads in Brussels...",
  "skills": ["local-business-opportunity-finder"],
  "agent_name": "lead-hunter",
  "schedule": { "kind": "cron", "expr": "0 9 * * *", "display": "Daily at 09:00" },
  "schedule_display": "Daily at 09:00",
  "enabled": true,
  "state": "scheduled",
  "deliver": "telegram",
  "model": null,
  "provider": null,
  "base_url": null,
  "script": null,
  "last_run_at": "2026-05-04T09:00:00+00:00",
  "next_run_at": "2026-05-05T09:00:00+00:00",
  "last_error": null,
  "created_at": "2026-04-15T...",
  "repeat": null
}
```

> On this host, `~/.hermes/cron/` exists but `jobs.json` doesn't —
> the user has no scheduled jobs at the moment, so re-implementing
> the feature creates fresh state.

### Run logs

`~/.hermes/cron/output/` — per-run output capture. Created by the
scheduler each time a job fires. Filenames are
`<job_id>-<timestamp>.txt`.

### Schedule timezone

Stored in YAML config at `$HERMES_HOME/config.yaml`:

```yaml
timezone: Europe/Brussels
```

Default: empty (server-local fallback). Cron expressions are
interpreted against this TZ. Saving via `PUT /api/config` triggers
`hermes_time.reset_cache()` + `cron.jobs.recompute_all_next_runs()`.

---

## Memory + identity sources used by AgentPage's source cards

The `/agent/profile` endpoint surfaces four "source" files in addition
to the preset's own `SOUL.md` / `AGENTS.md`:

| Card key | File path                              | Purpose                                       |
|----------|----------------------------------------|-----------------------------------------------|
| `soul`   | `<preset>/SOUL.md` (or `~/.hermes/SOUL.md` for default) | Identity prompt slot                          |
| `agents` | `<preset>/AGENTS.md`                   | Project-context slot                          |
| `user`   | `~/.hermes/memories/USER.md`           | User profile auto-built from prior chats      |
| `memory` | `~/.hermes/memories/MEMORY.md`         | Long-term agent memory file                   |

USER.md and MEMORY.md are upstream Hermes features; the AgentPage
just renders them alongside the preset content for context.

---

## Backing up and restoring

### Backup

```bash
tar -czf hermes-presets-$(date +%F).tar.gz \
    ~/.hermes/SOUL.md \
    ~/.hermes/agents/ \
    ~/.hermes/cron/jobs.json \
    ~/.hermes/config.yaml \
    ~/.hermes/memories/USER.md \
    ~/.hermes/memories/MEMORY.md
```

(Skips `~/.hermes/sessions/` and `~/.hermes/logs/` which are large
and cheap to lose.)

### Restore on a fresh machine

```bash
tar -xzf hermes-presets-YYYY-MM-DD.tar.gz -C /
```

### Reset to defaults (nuclear)

```bash
rm -rf ~/.hermes/agents/ ~/.hermes/cron/jobs.json
# config.yaml: remove or zero the 'agent.active_preset' and 'timezone' lines
```

After reset, the next `hermes` startup re-creates the directories
empty; built-in preset templates still load from
`agent/preset_templates/`.

---

## Re-implementation reminder

When you start the fresh main-based branch:

1. Copy the source-of-truth template files in:
   ```bash
   git checkout lead-hunter-custom-backup-2026-05-05 -- agent/preset_templates/
   ```
2. **Don't touch** `~/.hermes/`. The user's existing data (or future
   data they create) will work with the new code as long as you read
   from / write to the paths documented here.
3. Implement code per [`AGENTS_FEATURE.md`](./AGENTS_FEATURE.md) and
   [`CRON_FEATURE.md`](./CRON_FEATURE.md).
4. Smoke-test by creating a preset in the dashboard, refreshing, and
   confirming `~/.hermes/agents/<new-slug>/` appears with the right
   files.

The key invariant: the **filesystem layout above is the user-data
contract**. As long as the new code reads and writes those exact
paths with the same JSON / Markdown shapes, the user's existing
work transfers across rewrites.
