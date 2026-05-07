# Cron + Agent Wiring — Feature Spec

Companion to [`AGENTS_FEATURE.md`](./AGENTS_FEATURE.md). This doc
specifies the customizations on top of the upstream cron page that:

1. Let each cron job pick which **agent preset** to run as
   (`job.agent_name = <slug>`).
2. Add a **Daily Schedule Map** ("Today's Run Rhythm") visualization.
3. Add a **schedule-builder** UI for once / twice / three-times-per-day
   patterns.
4. Add **timezone persistence** for the cron scheduler.

The upstream `CronPage.tsx` ships a basic list. The fork-local version
is ~1100 lines longer and gains all of the above.

---

## 1. Data model: cron jobs

### `cron/jobs.py` — fields added by the fork

`create_cron_job(...)` accepts an additional keyword:

```python
def create_cron_job(
    prompt: str,
    schedule: str,
    name: Optional[str] = None,
    repeat: Optional[int] = None,
    deliver: Optional[str] = None,
    origin: Optional[Dict] = None,
    skill: Optional[str] = None,
    skills: Optional[List[str]] = None,
    agent_name: Optional[str] = None,    # ← FORK ADDITION (preset slug)
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    script: Optional[str] = None,
) -> Dict[str, Any]:
    ...
    normalized_agent_name = str(agent_name).strip() if isinstance(agent_name, str) else None
    ...
    job = {
        "id": ...,
        "name": ...,
        "prompt": ...,
        "agent_name": normalized_agent_name or None,    # ← persisted on disk
        ...
    }
```

`agent_name` is a free-form string but is interpreted as a **preset
slug** by everything downstream. `"default"` and `None` both mean
"use the active preset".

### `cron/scheduler.py`

When dispatching a job:
```python
from run_agent import AIAgent
agent = AIAgent(
    ...,
    agent_preset=job.get("agent_name"),    # ← preset wired in
    ...,
)
```

### `tools/cronjob_tools.py`

The MCP/skill-facing `cronjob` tool exposes `agent_name` on
**create**, **update**, and **list** so an agent (e.g. one running
inside a chat session) can schedule cron jobs with a chosen preset.

```python
def cronjob_tool(args):
    action = args.get("action")
    if action == "create":
        agent_name = _normalize_optional_job_value(args.get("agent_name"))
        return create_cron_job(..., agent_name=agent_name)
    elif action == "update":
        if args.get("agent_name") is not None:
            updates["agent_name"] = _normalize_optional_job_value(args["agent_name"])
        ...
    # On list responses:
    return {"agent_name": job.get("agent_name"), ...}
```

`_normalize_optional_job_value` trims, lowercases, and returns
`None` for empty strings — so an explicit empty unsets the field.

The tool's input JSON schema includes a new property:
```json
"agent_name": {
    "type": "string",
    "description": "Optional preset slug (e.g. 'lead-hunter'). When set, the cron job runs under that preset's identity."
}
```

---

## 2. Backend API additions

The upstream cron API (`/api/cron/jobs`) gains:

| Method | Path                          | Body changes                                       |
|--------|-------------------------------|----------------------------------------------------|
| POST   | `/api/cron/jobs`              | `agent_name?: string` accepted                     |
| PUT    | `/api/cron/jobs/{id}`         | `updates: { agent_name?: string }` accepted        |

The fork-local `web/src/lib/api.ts`:

```ts
createCronJob: (job: {
  prompt: string;
  schedule: string;
  name?: string;
  deliver?: string;
  agent_name?: string;          // ← FORK
}) => fetchJSON<CronJob>("/api/cron/jobs", { method: "POST", ... }),

updateCronJob: (id: string, updates: Record<string, unknown>) =>
  fetchJSON<CronJob>(`/api/cron/jobs/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  }),
```

### Timezone update wiring

When `PUT /api/config` saves a config whose `timezone` field changed,
the fork triggers cron recompute:

```python
from cron.jobs import recompute_all_next_runs
import hermes_time
hermes_time.reset_cache()
recompute_all_next_runs()
```

This already lives in upstream's web_server.py post-merge but the
fork added it earlier (commit `7c72ca73d`). Make sure it's present:
on timezone change, every job's `next_run_at` is recomputed against
the new TZ.

`hermes_time.py` adds a `reset_cache()` helper plus respects
`config.timezone` for `_hermes_now()`.

---

## 3. CronJob TS interface

`web/src/lib/api.ts`:
```ts
export interface CronJob {
  id: string;
  name?: string;
  prompt: string;
  schedule: { kind: string; expr: string; display: string };
  schedule_display: string;
  enabled: boolean;
  state: string;
  deliver?: string;
  agent_name?: string | null;   // ← FORK ADDITION
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
}
```

---

## 4. CronPage UI (`web/src/pages/CronPage.tsx`, ~1100 fork lines)

### Layout

Top-down on the page:

1. Header: `"Scheduled Jobs (N)"` + a `"Loading…"` red badge while
   `loading` is true.
2. **Schedule timezone** combobox (Card).
3. **Daily Schedule Map / Today's Run Rhythm** (Card).
4. **Create-job** form (Card with the schedule builder).
5. **Job list** (one Card per job).

### Schedule timezone

```ts
const [configTimezone, setConfigTimezone] = useState<string>("");
const [browserTimezone, setBrowserTimezone] = useState<string>(getBrowserTimezone());
```

On mount, `api.getConfig()` is read and `config.timezone` is hoisted
into `configTimezone`. The combobox shows `getTimezoneOptions(...)`
— the browser's IANA TZ + `Europe/Brussels` + `UTC` + every value
returned by `Intl.supportedValuesOf("timeZone")`.

When the user picks a new TZ:
```ts
setTimezoneSaving(true);
const next = { ...currentConfig, timezone: chosen };
await api.saveConfig(next);
// Server-side: PUT /api/config recomputes next_run_at for all jobs.
await reloadJobs();
setConfigTimezone(chosen);
```

The combobox label: `"SCHEDULE TIMEZONE"`. Help text describes that
this is what the cron expressions are evaluated against; falls back
to "Server local fallback" when unset.

### Daily Schedule Map

Function: `getDailyRunSlots(job)` returns an array of minute-of-day
ints when the job will fire today. It parses the job's
`schedule.expr` cron expression and extracts hour/minute fields. Only
**recurring daily** patterns are mapped; "every X minutes" and
one-off schedules are excluded.

`describeDailyCadence(job)` produces `"Once at 09:00"`,
`"Twice — 09:00 + 18:00"`, etc.

`estimateDurationMinutes(job)` is a heuristic: defaults to 15 min,
bumps to 25 if the prompt mentions "research" / "long" / "deep".

The visualization is a horizontal bar from 00:00 → 24:00 with one
colored block per timeline entry. Each entry has:

```ts
{
  id: `${job.id}-${slotIndex}`,
  title: job.name || truncatePrompt(job.prompt, 48),
  startMinute, endMinute, durationMinutes,
  startLabel, endLabel,
  widthPercent: max(2.2, durationMinutes/14.4),
  leftPercent: startMinute/14.4,
  overlapRisk: boolean,                    // computed in a second pass
  cadence,                                  // describeDailyCadence
  theme: getJobTheme(job),                  // per-job color palette
}
```

Overlap detection: sort by `startMinute`, walk linearly; if an entry
starts before the previous `runningEnd`, mark `overlapRisk = true`.

Header chips show `"N RUN WINDOWS/DAY"`, `"LONGEST RUN ≈ M MIN"`,
and `"NO OVERLAP RISK"` / `"⚠ N OVERLAPS"`.

When zero recurring daily slots exist (e.g. only "every 5 min" jobs),
a fallback message renders: `"Daily timeline unavailable for these
cron expressions — this overview only maps recurring daily
hour/minute schedules."`

### `getJobTheme(job)` — color palette

Keyed off `job.agent_name + name + prompt` text, returns a
preset-tinted theme:
- "lead-hunter" / "sales" / "outreach" → green
- "flight" / "travel" → blue
- "housing" / "rental" → amber
- "research" / "deep" → purple
- default → neutral steel

Each theme exports CSS class strings for card / bubble / badge / pill
/ status / timeline-bar / action-button styling.

### Schedule builder

Three radio patterns:
- `"once"` — one HH:MM input → cron `M H * * *`
- `"twice"` — two pairs → cron `M1 H1,H2 * * *` (or two separate
  expressions if minutes differ; falls back to a comma-list)
- `"three"` — three pairs
- `"custom"` — raw cron-expression input

`scheduleBuilderToExpr(builder)` and
`parseScheduleBuilderState(schedule)` round-trip between the UI
state and the cron string.

The hour `Select` lists `"00".."23"`; the minute `Select` lists
`["00","05","10","15","20","30","40","45","50","55"]` for the human
defaults (still allows custom mode for finer values).

### Job list — per-card UI

Each `<Card>` shows:
- **Header**: emoji + name (`job.theme.emoji`), with the
  schedule's `display` line ("Daily at 09:00 UTC").
- **Prompt preview** (truncated 200 chars).
- **Status badges**:
  - `enabled / paused / running / error`,
  - cadence chip (`"Once at 09:00"`),
  - duration chip (`"≈15 min"`),
  - "Last: …", "Next: …" timestamps formatted in `configTimezone`,
  - `"Starts <time>"` in primary run window,
  - `"⚠ Overlap risk"` if applicable.
- **Agent select** (`Select` populated from `presets` state):
  ```tsx
  <Select
    value={job.agent_name || "default"}
    onValueChange={(v) => handleReassignAgent(job, v)}
  >
    {presetOptions.map(p => (
      <SelectOption key={p.slug} value={p.slug}>
        {p.emoji || "🤖"} {p.name}
      </SelectOption>
    ))}
  </Select>
  ```
  `handleReassignAgent` calls `api.updateCronJob(job.id, {
  agent_name: nextAgentName || "default" })`.
- **Action buttons**: Edit (pencil), Pause/Resume (Play/Pause),
  Run-now (Zap), Delete (Trash2). Edit toggles an inline editor with
  three inputs (`name`, `prompt`, `schedule`) backed by
  `editDrafts[job.id]`.
- **Inline editor save** → `api.updateCronJob(id, { name, prompt,
  schedule })`. `Cancel` reverts the draft.
- **Last error** rendered in a destructive-tinted box if present.

### Presets state on the page

```ts
const [presets, setPresets] = useState<AgentPresetSummary[]>([]);
```
Loaded once on mount via `api.getAgents()`. If empty, fall back to
`[{ slug: "default", name: "Default" }]`.

---

## 5. Custom CSS

`web/src/index.css` gains ~198 fork-local lines (port to a separate
file like `plugins/lead_hunter/web/styles.css` and `@import` it from
`web/src/index.css`):

- `.cron-meta-chip` / `.cron-meta-chip-pastel` — small pill chips for
  status info
- `.cron-agent-select` / `.cron-preset-pill` — agent-selector styling
- Per-theme classes consumed by `getJobTheme(...)`:
  `cron-theme-leadhunter`, `cron-theme-flight`, `cron-theme-housing`,
  `cron-theme-research`, `cron-theme-default`.
- Timeline bar, overlap-warning, mascot-positioning rules.
- Agent-page-specific classes (`agent-card`, `agent-card-active`,
  `agent-mascot`, `agent-emoji-picker`, etc.).

---

## 6. Tests to port

From `tests/cron/test_jobs.py`, `tests/cron/test_scheduler.py`,
`tests/tools/test_cronjob_tools.py`:

- `create_cron_job(..., agent_name="lead-hunter")` persists the
  field.
- `cronjob` tool create + update flows for `agent_name`.
- Scheduler: when running a job with `agent_name="X"`, the spawned
  `AIAgent` has `agent_preset_slug == "X"`.
- `PUT /api/config` recomputes cron next_run_at when timezone
  changes (existing test —
  `test_put_config_recomputes_cron_runs_when_timezone_changes`).

---

## 7. Re-implementation order

1. Patch `cron/jobs.py` to accept and persist `agent_name`.
2. Patch `cron/scheduler.py` to forward it to `AIAgent`.
3. Patch `tools/cronjob_tools.py` to expose `agent_name` in
   create/update/list + JSON schema.
4. Patch `hermes_cli/web_server.py` (or your plugin's `plugin_api.py`)
   so PUT `/api/config` triggers `recompute_all_next_runs()` +
   `hermes_time.reset_cache()` on TZ change.
5. Patch `web/src/lib/api.ts`: `createCronJob` adds `agent_name`,
   `updateCronJob` is added, `CronJob` interface gains `agent_name`.
6. Replace `web/src/pages/CronPage.tsx` with the fork version (or
   alias it to `plugins/lead_hunter/web/CronPage.tsx`). Move the
   custom CSS chunk into a separate stylesheet imported from
   `index.css`.
7. Add the corresponding tests.
8. `npm run build`, smoke the dashboard.

Storage paths in [`DATA_LOCATIONS.md`](./DATA_LOCATIONS.md).
