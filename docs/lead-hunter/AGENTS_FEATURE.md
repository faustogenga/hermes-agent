# Agent Presets — Feature Spec

Goal: re-implement on a fresh branch from `main` everything the
`lead-hunter-custom-backup-2026-05-05` branch built for **agent
presets** — the system that lets the user define multiple distinct
personas (Lead Hunter, Flight Finder, Brussels Housing Hunter, etc.),
edit them in the dashboard, and assign them to cron jobs so each
scheduled run loads its preset's identity.

This is **not** the same as upstream's "Profiles : Multi Agents" (which
appeared in main later and overlaps; the upstream feature should be
hidden or removed).

---

## 1. Concept

A **preset** is a self-contained agent identity made of:

| Field            | Purpose                                                                |
|------------------|-------------------------------------------------------------------------|
| `slug`           | Stable identifier, kebab-case (`lead-hunter`, `flight-finder`)         |
| `name`           | Display name (`"Lead Hunter"`)                                         |
| `emoji`          | Single-glyph avatar (`🎯`)                                             |
| `role`           | One-line role sentence (`"Evidence-first SMB opportunity finder"`)     |
| `goal`           | One-line goal sentence                                                  |
| `description`    | Multi-sentence summary used in cards / lists                            |
| `personality`    | Optional name of a personality from `config.agent.personalities`        |
| `default_skills` | List of skill slugs to auto-load on every run                           |
| `soul_content`   | The preset's `SOUL.md` body (identity slot in the system prompt)       |
| `agents_content` | Optional `AGENTS.md` body (project-context slot)                        |
| `enabled`        | Bool — when false, preset is hidden from listings                       |

The active preset is selected by `config.agent.active_preset` (string
slug). When unset, `"default"` is used.

---

## 2. Filesystem layout

### Built-in templates (shipped in repo)

```
agent/preset_templates/
├── default/                       (no built-in dir; created lazily — see below)
├── brussels-housing-hunter/
│   ├── AGENT.json                 metadata
│   ├── SOUL.md                    identity prompt
│   └── AGENTS.md                  project context
├── flight-finder/
│   ├── AGENT.json
│   ├── SOUL.md
│   └── AGENTS.md
└── lead-hunter/
    ├── AGENT.json
    ├── SOUL.md
    └── AGENTS.md
```

### User overrides + custom presets (per-host)

```
$HERMES_HOME/agents/
├── default/                       overrides for the built-in default
│   ├── AGENT.json                 (writable copy of the metadata)
│   └── AGENTS.md                  (the default's project context)
├── lead-hunter/                   user-modified copy of the built-in
│   ├── AGENT.json
│   ├── SOUL.md
│   └── AGENTS.md
└── <slug>/                        any number of user-created presets
    ├── AGENT.json
    ├── SOUL.md
    └── AGENTS.md
```

The default preset is special: its `SOUL.md` lives at
`$HERMES_HOME/SOUL.md` (the original Hermes location), not inside the
`agents/default/` dir. Override metadata sits in `agents/default/`.

### `AGENT.json` schema

```json
{
  "name": "Lead Hunter",
  "slug": "lead-hunter",
  "emoji": "🎯",
  "role": "Evidence-first local SMB opportunity finder",
  "goal": "Find outreach-ready local businesses with weak digital demand capture",
  "description": "Commercial lead-finding preset for a web and app development agency",
  "personality": "",
  "default_skills": ["local-business-opportunity-finder"],
  "enabled": true
}
```

### Discovery rules

`list_agent_presets()` returns:
1. Always: the **default** preset (synthesized from
   `$HERMES_HOME/agents/default/AGENT.json` if present, else hard-coded
   defaults).
2. Built-in templates from `agent/preset_templates/*/AGENT.json` that
   aren't already overridden.
3. User-created presets in `$HERMES_HOME/agents/*/` that have both
   `AGENT.json` AND `SOUL.md` AND `enabled: true`.

User overrides at the same slug as a built-in template **win**.

---

## 3. Core Python module

`agent/agent_presets.py` (~310 lines) — the engine. Public API:

```python
@dataclass
class AgentPreset:
    name: str
    slug: str
    emoji: str = "🤖"
    role: str = ""
    goal: str = ""
    description: str = ""
    personality: str = ""
    default_skills: list[str] = field(default_factory=list)
    soul_path: Optional[Path] = None
    agents_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    built_in: bool = False
    def to_dict(self) -> dict[str, Any]: ...

def slugify_agent_name(value: str) -> str: ...
def get_agent_presets_dir() -> Path:                    # $HERMES_HOME/agents
def get_default_agent_preset() -> AgentPreset: ...
def list_agent_presets() -> list[AgentPreset]: ...
def load_agent_preset(slug: Optional[str]) -> AgentPreset:    # raises FileNotFoundError
def get_active_agent_slug(config: Optional[dict] = None) -> str:
def resolve_agent_preset(slug=None, config=None) -> AgentPreset:  # falls back to default
def save_agent_preset(slug, *, metadata, soul_content, agents_content=None) -> AgentPreset:
def delete_agent_preset(slug: str) -> None:               # raises ValueError if slug == "default"
def read_agent_preset_source(path: Optional[Path]) -> str:   # safe file read
```

Notes:
- `slugify_agent_name` lowercases, replaces non-alphanumerics with `-`,
  trims. Empty input → `"default"`.
- `_normalize_skill_list` accepts a string ("a, b") OR list, dedupes,
  preserves order.
- `save_agent_preset` writes `AGENT.json` + `SOUL.md` + optional
  `AGENTS.md` atomically; rejects empty content for SOUL/AGENTS by
  deleting the file.
- The `_BUILTIN_TEMPLATE_DIR` is computed as `Path(__file__).parent /
  "preset_templates"` — relocate together with the module.

---

## 4. Wiring into the agent runtime

### `agent/prompt_builder.py`

Two function signatures gain an `agent_preset=None` keyword:

```python
def load_soul_md(agent_preset=None) -> Optional[str]:
    soul_path = getattr(agent_preset, "soul_path", None) or (get_hermes_home() / "SOUL.md")
    ...
    filename = (
        f"{getattr(agent_preset, 'slug', 'default')}/SOUL.md"
        if agent_preset and getattr(agent_preset, 'slug', 'default') != 'default'
        else "SOUL.md"
    )
    content = _scan_context_content(content, filename)

def build_context_files_prompt(cwd=None, skip_soul=False, agent_preset=None) -> str:
    # Loads the preset's AGENTS.md as a "## Preset AGENTS.md" section
    # AHEAD of the cwd's .hermes.md / AGENTS.md / CLAUDE.md chain.
    preset_agents = ""
    preset_agents_path = getattr(agent_preset, "agents_path", None)
    if preset_agents_path and preset_agents_path.exists():
        content = preset_agents_path.read_text("utf-8").strip()
        if content:
            content = _scan_context_content(content, f"{getattr(agent_preset, 'slug', 'preset')}/AGENTS.md")
            preset_agents = _truncate_content(f"## Preset AGENTS.md\n\n{content}", "AGENTS.md")
    ...  # priority chain:
    #   1. preset AGENTS.md
    #   2. .hermes.md / HERMES.md (walk to git root)
    #   3. cwd AGENTS.md / agents.md
    #   4. CLAUDE.md / claude.md
    #   5. .cursorrules / .cursor/rules/*.mdc
    if not skip_soul:
        soul_content = load_soul_md(agent_preset=agent_preset)
        ...
```

### `run_agent.py` — `AIAgent.__init__`

```python
from agent.agent_presets import resolve_agent_preset

class AIAgent:
    def __init__(self, ..., agent_preset: str = None, ...):
        ...
        self.agent_preset = resolve_agent_preset(agent_preset)
        self.agent_preset_slug = self.agent_preset.slug
        self._preset_skills_prompt = ""
        self._preset_loaded_skills: list[str] = []
```

When building the system prompt:
```python
_soul_content = load_soul_md(agent_preset=self.agent_preset)
...
# After loading default skills, ALSO preload preset.default_skills:
if self.agent_preset.default_skills:
    preset_skills_prompt, loaded_skills, _missing = build_preloaded_skills_prompt(
        self.agent_preset.default_skills, ...
    )
    if preset_skills_prompt:
        self._preset_skills_prompt = preset_skills_prompt
        self._preset_loaded_skills = loaded_skills
        prompt_parts.append(preset_skills_prompt)
...
context_prompt = build_context_files_prompt(..., agent_preset=self.agent_preset)
```

### `cli.py` — interactive REPL

```python
from agent.agent_presets import get_active_agent_slug, list_agent_presets, resolve_agent_preset

class CLI:
    def __init__(self, ..., agent_preset: str = None, ...):
        self.agent_preset_slug = resolve_agent_preset(
            agent_preset or get_active_agent_slug(CLI_CONFIG)
        ).slug
        ...
    # When spawning AIAgent:
    AIAgent(..., agent_preset=self.agent_preset_slug, ...)
```

Slash commands:
- `/agent` or `/agent show` — print active preset details.
- `/agent list` — list all presets with active marker and built-in tag.
- `/agent use <slug>` — switch active preset, persist via
  `save_config_value("agent.active_preset", target_slug)`.

CLI flag: `--agent <slug>` on `hermes` and `hermes chat`.

### `cron/scheduler.py`

When dispatching a job:
```python
AIAgent(..., agent_preset=job.get("agent_name"), ...)
```
The `agent_name` key on a cron job IS the preset slug. (The name
predates the preset feature; it now overloads to mean preset.)

---

## 5. Default config additions

`hermes_cli/config.py` `DEFAULT_CONFIG`:

```python
"agent": {
    "active_preset": "default",
    ...other agent settings...
},
```

`config.agent.personalities` is a dict of named personality overlays
the user can attach to a preset. Each entry is either:
- a string (raw system-prompt addition), or
- a dict `{"system_prompt": "...", "description": "..."}`.

The preset's `personality` field references one of these keys (or `""`
to skip).

---

## 6. Backend API

All routes serve JSON; all require the dashboard session token header.
On the **fresh branch**, mount these under
`/api/plugins/lead-hunter/...` via `plugins/lead_hunter/dashboard/plugin_api.py`
so they don't clutter the main FastAPI app:

| Method | Path                                  | Body                | Returns                                                                          |
|--------|---------------------------------------|---------------------|----------------------------------------------------------------------------------|
| GET    | `/agent/profile`                      | —                   | `AgentProfileResponse` (full preset list + active + sources)                     |
| GET    | `/agents`                             | —                   | `{active_preset, presets[], available_personalities[]}`                          |
| POST   | `/agents`                             | `AgentPresetPayload`| Created `AgentPresetDetail` (409 if slug exists)                                 |
| PUT    | `/agents/{slug}`                      | `AgentPresetPayload`| Updated `AgentPresetDetail` (404 if missing)                                     |
| DELETE | `/agents/{slug}`                      | —                   | `{ok: true}` (400 if slug == "default", 404 if missing)                          |
| POST   | `/agents/{slug}/activate`             | optional `{slug}`   | `{ok: true, active_preset}` — also clears active when preset is deleted          |

### `AgentPresetPayload` (Pydantic)

```python
class AgentPresetPayload(BaseModel):
    name: str
    slug: Optional[str] = None
    emoji: str = "🤖"
    role: str = ""
    goal: str = ""
    description: str = ""
    personality: str = ""
    default_skills: List[str] = []
    soul_content: str = ""
    agents_content: str = ""
```

### `AgentProfileResponse` shape

```ts
{
  // Active preset summary fields
  name: string,
  role: string,
  description: string,
  active_personality: string,
  personality_prompt: string,
  active_preset: string,                       // slug
  // Lists
  presets: AgentPresetDetail[],                // serialized via _serialize_agent_preset
  current_preset: AgentPresetDetail,
  available_personalities: string[],           // sorted keys of config.agent.personalities
  cron_examples: [{ name, payload }],          // ready-to-paste cron job templates
  model: ModelInfoResponse,                    // result of get_model_info()
  // Source cards (file content used by the agent)
  sources: AgentProfileSource[],               // [soul, agents, user, memory]
  source_map: Record<string, AgentProfileSource>,
}
```

### `AgentProfileSource` (per-card)

```ts
{
  key: "soul" | "agents" | "user" | "memory",
  title: "SOUL.md" | "AGENTS.md" | "USER.md" | "MEMORY.md",
  path: string,                                // absolute path or "" if missing
  present: boolean,
  summary: string,                             // 240-char single-line preview
  content: string,                             // up to 4000 chars, head+tail truncated
}
```

`USER.md` lives at `$HERMES_HOME/memories/USER.md`,
`MEMORY.md` at `$HERMES_HOME/memories/MEMORY.md`.

### Helper functions to port

From `hermes_cli/web_server.py` (or relocate to `plugin_api.py`):

```python
def _read_dashboard_text(path) -> str
def _truncate_dashboard_text(text, max_chars=4000) -> str   # 75/25 head/tail split
def _compact_dashboard_text(text, max_chars=240) -> str     # collapse whitespace, ellipsis
def _strip_dashboard_comments(text) -> str                   # remove <!-- ... -->
def _derive_agent_identity(soul_content) -> tuple[str, str] # (role, description) from SOUL paragraphs
def _resolve_personality_prompt(config, personality_name) -> str
def _agent_source_card(key, title, path, content, missing_summary) -> dict
def _serialize_agent_preset(preset, config, *, active_slug) -> dict
def _build_agent_profile_payload(config) -> dict
```

`_derive_agent_identity` extracts role + description from the first
two non-heading paragraphs of `SOUL.md`, used as fallback when the
preset's metadata fields are empty.

`_serialize_agent_preset` adds `active`, `personality_prompt`, and
both file contents (soul + agents) to the preset dict.

---

## 7. Frontend client (`web/src/lib/api.ts`)

```ts
export const api = {
  // ...
  getAgentProfile: () =>
    fetchJSON<AgentProfileResponse>("/api/plugins/lead-hunter/agent/profile"),
  getAgents: () =>
    fetchJSON<{ active_preset: string; presets: AgentPresetSummary[]; available_personalities: string[] }>(
      "/api/plugins/lead-hunter/agents"
    ),
  createAgent: (agent: AgentPresetUpsertPayload) =>
    fetchJSON<AgentPresetDetail>("/api/plugins/lead-hunter/agents",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(agent) }),
  updateAgent: (slug: string, agent: AgentPresetUpsertPayload) =>
    fetchJSON<AgentPresetDetail>(`/api/plugins/lead-hunter/agents/${encodeURIComponent(slug)}`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(agent) }),
  activateAgent: (slug: string) =>
    fetchJSON<{ ok: boolean; active_preset: string }>(
      `/api/plugins/lead-hunter/agents/${encodeURIComponent(slug)}/activate`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slug }) }),
  deleteAgent: (slug: string) =>
    fetchJSON<{ ok: boolean }>(`/api/plugins/lead-hunter/agents/${encodeURIComponent(slug)}`,
      { method: "DELETE" }),
};
```

Required type exports (TS):

```ts
export interface AgentProfileSource { key, title, path, present, summary, content }
export interface AgentPresetSummary {
  name, slug, emoji, role, goal, description, personality, personality_prompt,
  default_skills: string[], built_in: boolean, active: boolean,
}
export interface AgentPresetDetail extends AgentPresetSummary {
  soul_content: string, agents_content: string,
  soul_path: string|null, agents_path: string|null, metadata_path: string|null,
}
export interface AgentPresetUpsertPayload {
  name, slug?: string, emoji, role, goal, description, personality,
  default_skills: string[], soul_content, agents_content,
}
export interface AgentProfileResponse {
  name, role, description, active_personality, personality_prompt,
  active_preset: string,
  current_preset: AgentPresetDetail,
  presets: AgentPresetDetail[],
  available_personalities: string[],
  cron_examples: { name: string; payload: { action; name; schedule; agent_name; prompt } }[],
  model: ModelInfoResponse,
  sources: AgentProfileSource[],
  source_map: Record<string, AgentProfileSource>,
}
```

---

## 8. AgentPage UI (`web/src/pages/AgentPage.tsx`, ~854 lines)

A two-pane layout: a **grid of preset cards** on the left, a
**preset editor** on the right.

### Header
- Title `"Agents"` (`font-expanded text-3xl`).
- "New agent" button → opens editor with the `"blank"` template.
- Three quick-template buttons: `"Default"`, `"Lead Hunter"`,
  `"Flight Finder"` (re-fills the editor with `buildTemplate(...)`).

### Preset card grid (left)

For each preset:
- **Avatar** — emoji if present, otherwise `getPresetIcon(preset)` (a
  Lucide icon picked by name keywords: Plane, Compass, Target, Rocket,
  Sparkles, etc.).
- Name + slug.
- Truncated description (`summarizePreset`, 90 chars).
- Active badge if `preset.active`.
- Built-in badge if `preset.built_in`.
- Click selects, second click activates (calls `api.activateAgent`).
- Right-click / trash icon → confirm + `api.deleteAgent`.

A **mascot** floats inside the grid with absolute positioning;
position is computed once per layout via a `useLayoutEffect`. It uses
the active preset's emoji.

`getPresetTheme(preset)` returns a per-preset color palette
(`stageClass`, `avatarClass`, `glowClass`, `cardClass`, etc.) keyed
off slug + name + description text matching keywords.

### Editor (right)

Fields, in order:
1. **Emoji + emoji picker** — clicking the avatar opens a popover
   with `EMOJI_GROUPS` (4 named groups: Modern, Mission, Travel,
   Style) plus a search input that filters `ALL_PICKER_EMOJIS`.
2. **Name** + auto-generated **slug** (slugified from name unless
   user types one; locked once the preset exists).
3. **Role** (one line).
4. **Goal** (one line).
5. **Description** (multi-line).
6. **Personality** (`Select` populated from
   `profile.available_personalities`, with `""` for none).
7. **Default skills** (comma-separated input).
8. **`SOUL.md` body** — large textarea, `font-mono`, ~20 rows.
9. **`AGENTS.md` body** — large textarea, optional.

Bottom of editor:
- **Status** message ("Saved", "Activated", error text).
- **Save** button → `api.updateAgent(slug, payload)` if existing,
  `api.createAgent(payload)` if new. Reloads via
  `api.getAgentProfile()` and re-selects the saved slug.
- **Activate** button → `api.activateAgent(slug)`.
- **Delete** button (only for non-built-in, non-active presets).

### Source cards (below the editor)

Four "source" mini-cards rendered from `profile.sources`:
`SOUL.md`, `AGENTS.md`, `USER.md`, `MEMORY.md`. Each shows:
- Title + path (small).
- "PRESENT" / "MISSING" badge.
- Summary (one line, dimmed).
- Toggle to expand the full `content` (truncated to 4000 chars).

### Cron-link panel

If `cronJobs` (loaded via `api.getCronJobs()`) contains jobs whose
`agent_name === selectedSlug`, a panel lists them with
`<Link to="/cron">` so the user can jump to edit the schedule.

If the user is viewing the active preset, also show
`profile.cron_examples` as **template cron jobs** the user can paste
into the cron page to quickly schedule a run with this preset.

### Plugin slot integration

Plugins can advertise `agentPage: true` in their manifest. Such
plugins get rendered in a strip above the editor (each as a `<Card>`
showing its `label` + `description`, link to `/<plugin.tab.path>`).
The dashboard plugin manifest type already exposes
`agentPage?: boolean`.

### Error UI

If the initial `api.getAgentProfile()` rejects:

```
┌─────────────────────────────────────────┐
│ ⚠  Agent page failed to load             │
│ <error message>                          │
│ If you just changed dashboard code,      │
│ rebuild the frontend and restart the     │
│ dashboard process.                       │
└─────────────────────────────────────────┘
```

---

## 9. Routing + sidebar

`web/src/App.tsx`:
```tsx
import AgentPage from "@/pages/AgentPage";
// ...
const BUILTIN_NAV: NavItem[] = [
  { path: "/", labelKey: "status", label: "Status", icon: Activity },
  { path: "/agent", label: "Agents", icon: Bot },           // ← inserted just after Status
  { path: "/cron", labelKey: "cron", label: "Cron", icon: Clock },
  ...
];
// In <Routes>:
<Route path="/agent" element={<AgentPage />} />
<Route path="/agents" element={<Navigate to="/agent" replace />} />
```

If running on top of upstream main, also **hide upstream's
`/profiles` ("Profiles : Multi Agents") tab** because it duplicates
this page conceptually. Either:
- Remove the `BUILTIN_NAV` entry + `<Route path="/profiles">`, or
- Set the manifest's `tab.hidden = true` if upstream registers it via
  the plugin system.

---

## 10. Tests to port

From `tests/agent/test_agent_presets.py` and the matching cli/web
test files. Adjust the `default` count in
`test_list_agent_presets_returns_default_when_none_exist` to match
the number of built-in templates (currently **4**: default,
brussels-housing-hunter, flight-finder, lead-hunter).

Required coverage:
- `slugify_agent_name` round-trips for hyphens, spaces, casing.
- `list_agent_presets` returns built-ins when `$HERMES_HOME/agents/`
  is empty.
- A user-created preset with valid `AGENT.json` + `SOUL.md` is
  discovered.
- Invalid presets (missing files, bad JSON, `enabled: false`) are
  skipped without raising.
- `get_active_agent_slug` falls back to "default" when the configured
  slug doesn't exist.
- `delete_agent_preset("default")` raises `ValueError`.
- The `/agent/profile` endpoint returns the full payload shape.
- POST/PUT/DELETE/activate routes round-trip correctly.
- CLI `--agent <slug>` flag and `/agent use <slug>` slash command.

---

## 11. Re-implementation order

On the fresh branch from main:

1. Add `agent/agent_presets.py` + `agent/preset_templates/*` (pure-add,
   no upstream conflicts).
2. Patch `agent/prompt_builder.py` to accept `agent_preset` keyword.
3. Patch `run_agent.py` (`AIAgent.__init__` + system-prompt assembly).
4. Add `agent.active_preset` to `DEFAULT_CONFIG` in `hermes_cli/config.py`.
5. Patch `cli.py` for the `--agent` flag + `/agent` slash commands.
6. Patch `cron/scheduler.py` to pass `job.agent_name` as `agent_preset`.
7. Add the dashboard plugin scaffold at
   `plugins/lead_hunter/dashboard/{manifest.json, plugin_api.py}` with
   the 6 routes + helpers.
8. Add `web/src/pages/AgentPage.tsx` + the api.ts methods + types.
9. Wire the route + sidebar in `web/src/App.tsx`.
10. Hide / remove upstream's `/profiles` tab if present.
11. Port tests; run `pytest agent/ tests/cli/ tests/hermes_cli/`.
12. `npm run build`, smoke the dashboard.

The Cron half of this lives in [`CRON_FEATURE.md`](./CRON_FEATURE.md);
storage paths in [`DATA_LOCATIONS.md`](./DATA_LOCATIONS.md).
