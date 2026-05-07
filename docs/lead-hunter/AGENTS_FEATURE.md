# Agent Presets — Feature Spec

Goal: build a **`lead_hunter` plugin** under `plugins/` that adds
agent presets (Lead Hunter, Flight Finder, Brussels Housing Hunter,
…). Each preset is a self-contained identity (name, emoji, role,
goal, `SOUL.md`, `AGENTS.md`, default skills, optional personality).

The dashboard gets an **Agents** tab where the user creates, edits,
activates, and deletes presets. Cron jobs (see
[`CRON_FEATURE.md`](./CRON_FEATURE.md)) can pick which preset to run
as via the `agent_name` field.

The whole thing lives inside `plugins/lead_hunter/` so future
`git pull upstream main` cannot overwrite it. A handful of one-line
touches in upstream files act as dispatcher hooks; those are listed
in §11.

This is **not** the same as upstream's "Profiles : Multi Agents"
(which appeared later in main and overlaps conceptually). When
shipping, hide the upstream `/profiles` tab.

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

### Built-in templates (shipped with the plugin, version-controlled)

```
plugins/lead_hunter/agent/preset_templates/
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

(The `default` preset is synthesized in code; it has no template
directory — its `SOUL.md` is the legacy `~/.hermes/SOUL.md`.)

### User overrides + custom presets (per-host, not in repo)

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
2. Built-in templates from
   `plugins/lead_hunter/agent/preset_templates/*/AGENT.json` that
   aren't already overridden.
3. User-created presets in `$HERMES_HOME/agents/*/` that have both
   `AGENT.json` AND `SOUL.md` AND `enabled: true`.

User overrides at the same slug as a built-in template **win**.

---

## 3. Core Python module — `plugins/lead_hunter/agent/presets.py`

~310 lines. Public API:

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
- `_BUILTIN_TEMPLATE_DIR = Path(__file__).resolve().parent /
  "preset_templates"` — keep the templates directory next to this
  module so the path resolves automatically.

### Convenience re-export (optional)

To keep import sites short, add a tiny shim at
`plugins/lead_hunter/agent/__init__.py`:

```python
from .presets import (
    AgentPreset, slugify_agent_name, get_agent_presets_dir,
    get_default_agent_preset, list_agent_presets, load_agent_preset,
    get_active_agent_slug, resolve_agent_preset,
    save_agent_preset, delete_agent_preset, read_agent_preset_source,
)
```

Then upstream files (the touch-points in §11) can do
`from plugins.lead_hunter.agent import resolve_agent_preset, ...`.

---

## 4. Wiring into the agent runtime (shared-file touch-points)

### `agent/prompt_builder.py` (PATCH — pinned `merge=ours`)

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

### `run_agent.py` — `AIAgent.__init__` (PATCH — pinned `merge=ours`)

```python
from plugins.lead_hunter.agent import resolve_agent_preset

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

### `cli.py` — interactive REPL (PATCH — pinned `merge=ours`)

```python
from plugins.lead_hunter.agent import (
    get_active_agent_slug, list_agent_presets, resolve_agent_preset,
)

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

### `hermes_cli/config.py` (PATCH — pinned `merge=ours`)

Add to `DEFAULT_CONFIG["agent"]`:

```python
"agent": {
    "active_preset": "default",
    ...other agent settings already present...
},
```

That's the only fork-local mutation here.

`config.agent.personalities` is a dict of named personality overlays
the user can attach to a preset. Each entry is either:
- a string (raw system-prompt addition), or
- a dict `{"system_prompt": "...", "description": "..."}`.

The preset's `personality` field references one of these keys (or `""`
to skip). Personalities are user-editable values in `config.yaml`,
not code we ship.

---

## 5. Backend API — `plugins/lead_hunter/dashboard/plugin_api.py`

Auto-mounted by Hermes at `/api/plugins/lead-hunter/`.

| Method | Path                                  | Body                | Returns                                                                          |
|--------|---------------------------------------|---------------------|----------------------------------------------------------------------------------|
| GET    | `/agent/profile`                      | —                   | `AgentProfileResponse` (full preset list + active + sources)                     |
| GET    | `/agents`                             | —                   | `{active_preset, presets[], available_personalities[]}`                          |
| POST   | `/agents`                             | `AgentPresetPayload`| Created `AgentPresetDetail` (409 if slug exists)                                 |
| PUT    | `/agents/{slug}`                      | `AgentPresetPayload`| Updated `AgentPresetDetail` (404 if missing)                                     |
| DELETE | `/agents/{slug}`                      | —                   | `{ok: true}` (400 if slug == "default", 404 if missing)                          |
| POST   | `/agents/{slug}/activate`             | optional `{slug}`   | `{ok: true, active_preset}` — also clears active when preset is deleted          |

### Plugin manifest — `plugins/lead_hunter/dashboard/manifest.json`

```json
{
  "name": "lead-hunter",
  "label": "Lead Hunter",
  "description": "Custom agent presets and preset-aware cron scheduling.",
  "icon": "Bot",
  "version": "1.0.0",
  "tab": { "path": "/lead-hunter", "hidden": true, "position": "end" },
  "api": "plugin_api.py"
}
```

`tab.hidden = true` because the plugin doesn't render its own tab —
its UI lives at `/agent` (an alias-routed page; see §8).

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

### Helper functions to ship inside `plugin_api.py`

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

`_build_agent_profile_payload` does a lazy
`from hermes_cli.web_server import get_model_info` to avoid import
cycles when the web server loads the plugin.

---

## 6. Frontend client — extend `web/src/lib/api.ts`

These are short additions to the existing `api` object. Pin
`web/src/lib/api.ts` with `merge=ours` so future merges keep them.

```ts
export const api = {
  // ...existing upstream methods...

  // ── lead_hunter plugin: agent preset endpoints ─────────────────────
  // Mounted at /api/plugins/lead-hunter/ — see
  // plugins/lead_hunter/dashboard/plugin_api.py.
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

Putting these types into `plugins/lead_hunter/web/types.ts` and
re-importing from `web/src/lib/api.ts` works too — the file location
is style preference, not load-bearing.

---

## 7. AgentPage UI — `plugins/lead_hunter/web/AgentPage.tsx` (~854 lines)

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
Add `agentPage?: boolean` to `web/src/plugins/types.ts`'s
`PluginManifest` (touch-point pinned `merge=ours`).

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

## 8. Routing + sidebar — Vite alias trick

The plugin TSX file lives at
`plugins/lead_hunter/web/AgentPage.tsx`, **outside** `web/src/`.
Pull it into the main bundle by aliasing the canonical import path
in `web/vite.config.ts`:

```ts
resolve: {
  alias: [
    {
      find: /^@\/pages\/AgentPage$/,
      replacement: path.resolve(__dirname, "../plugins/lead_hunter/web/AgentPage.tsx"),
    },
    // (CronPage alias — see CRON_FEATURE.md)
    { find: "@", replacement: path.resolve(__dirname, "./src") },
  ],
  dedupe: ["react", "react-dom", "@react-three/fiber", "@observablehq/plot",
           "three", "leva", "gsap"],
},
server: {
  proxy: { "/api": { target: BACKEND, ws: true }, "/dashboard-plugins": BACKEND },
  fs: { allow: [path.resolve(__dirname, ".."), __dirname] },
},
```

Mirror in `web/tsconfig.app.json`:

```json
"paths": {
  "@/pages/AgentPage": ["../plugins/lead_hunter/web/AgentPage.tsx"],
  "@/pages/CronPage":  ["../plugins/lead_hunter/web/CronPage.tsx"],
  "@/*": ["./src/*"]
}
```

Plugin TSX files import bare specifiers (`react`, `react-router-dom`,
…) which Rollup/Vite resolve from `node_modules` walking up from the
importing file. Since `plugins/lead_hunter/web/` is outside `web/`,
add a postinstall hook to `web/package.json`:

```json
"postinstall": "node -e \"const fs=require('fs'),path=require('path');const link=path.resolve('..','plugins','lead_hunter','web','node_modules');try{fs.lstatSync(link)}catch{fs.symlinkSync(path.resolve('node_modules'),link,'dir');console.log('linked '+link+' -> ../node_modules')}\""
```

…and gitignore the symlink:

```gitignore
plugins/lead_hunter/web/node_modules
```

Then `web/src/App.tsx` (touch-point pinned `merge=ours`) keeps the
import + nav entry as if AgentPage lived in `src/pages/`:

```tsx
import AgentPage from "@/pages/AgentPage";   // resolves to plugin file via alias
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

## 9. Tests — `plugins/lead_hunter/tests/`

Mirror the upstream `tests/` tree. Add this to `pyproject.toml` so
pytest discovers them:

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "plugins/lead_hunter/tests"]
```

And a one-file `plugins/lead_hunter/tests/conftest.py` that bridges
the hermetic fixtures from the main `tests/conftest.py`:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.conftest import *  # noqa: F401,F403,E402
```

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
- The `/api/plugins/lead-hunter/agent/profile` endpoint returns the
  full payload shape.
- POST/PUT/DELETE/activate routes round-trip correctly.
- CLI `--agent <slug>` flag and `/agent use <slug>` slash command.

Adjust the count assertion in
`test_list_agent_presets_returns_default_when_none_exist` to match
the number of built-in templates (currently **4**: default,
brussels-housing-hunter, flight-finder, lead-hunter).

---

## 10. Final plugin layout

```
plugins/lead_hunter/
├── README.md
├── __init__.py
├── agent/
│   ├── __init__.py                     re-exports public API
│   ├── presets.py                      ~310 LOC engine
│   └── preset_templates/
│       ├── brussels-housing-hunter/{AGENT.json, AGENTS.md, SOUL.md}
│       ├── flight-finder/{AGENT.json, AGENTS.md, SOUL.md}
│       └── lead-hunter/{AGENT.json, AGENTS.md, SOUL.md}
├── dashboard/
│   ├── manifest.json                   plugin descriptor
│   └── plugin_api.py                   FastAPI router + 6 routes + helpers
├── web/
│   ├── AgentPage.tsx                   pulled into web build via Vite alias
│   ├── CronPage.tsx                    (see CRON_FEATURE.md)
│   └── styles.css                      custom CSS imported by index.css
├── env_keys.py                         optional: registers Hunter/Apollo/Airtable env vars
└── tests/
    ├── conftest.py                     bridges tests/conftest.py fixtures
    ├── agent/test_agent_presets.py
    ├── cli/test_agent_preset_commands.py
    ├── hermes_cli/test_agent_preset_cli_args.py
    ├── run_agent/test_agent_preset_identity.py
    └── hermes_cli/test_agent_preset_routes.py
```

---

## 11. Shared-file touch-points (`merge=ours` pinned)

Every file in this list keeps a tiny patch from this fork. Pin them
in `.gitattributes`:

```gitattributes
agent/prompt_builder.py       merge=ours
run_agent.py                  merge=ours
cli.py                        merge=ours
cron/scheduler.py             merge=ours
hermes_cli/config.py          merge=ours
web/src/App.tsx               merge=ours
web/src/lib/api.ts            merge=ours
web/src/plugins/types.ts      merge=ours
web/vite.config.ts            merge=ours
web/tsconfig.app.json         merge=ours
web/package.json              merge=ours
```

Run once per clone:
```bash
git config merge.ours.driver true
```

When upstream actually changes one of these in a way you want to
absorb, take the upstream version explicitly with
`git checkout main -- <file>` and re-apply your tiny patch on top.

---

## 12. Re-implementation order (from a fresh main checkout)

1. `mkdir -p plugins/lead_hunter/{agent/preset_templates,dashboard,web,tests}`.
2. Copy template directories from any existing source (the
   lead-hunter-custom-backup branch has them at
   `agent/preset_templates/`):
   ```bash
   git checkout lead-hunter-custom-backup-2026-05-05 -- agent/preset_templates/
   git mv agent/preset_templates plugins/lead_hunter/agent/preset_templates
   ```
3. Add `plugins/lead_hunter/agent/presets.py` (the engine) and
   `__init__.py` (re-exports).
4. Add the 5 shared-file patches from §4 + §11; pin them with
   `merge=ours`.
5. Add `plugins/lead_hunter/dashboard/{manifest.json, plugin_api.py}`
   with the 6 routes + helpers (§5).
6. Add `plugins/lead_hunter/web/AgentPage.tsx` (the UI from §7).
7. Update `web/vite.config.ts`, `web/tsconfig.app.json`,
   `web/package.json`, and `web/src/App.tsx` per §8.
8. Extend `web/src/lib/api.ts` with the 6 new methods + types (§6).
9. Hide upstream's `/profiles` tab (§8).
10. Port tests from §9; run `pytest plugins/lead_hunter/tests/`.
11. `npm run build`; smoke the dashboard.

The cron half lives in [`CRON_FEATURE.md`](./CRON_FEATURE.md).
Storage paths in [`DATA_LOCATIONS.md`](./DATA_LOCATIONS.md).
