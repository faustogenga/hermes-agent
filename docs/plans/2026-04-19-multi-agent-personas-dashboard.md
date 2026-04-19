# Multi-Agent Personas + Dashboard Management Implementation Plan

> For Hermes: use subagent-driven-development skill to implement this plan task-by-task.

Goal: let one Hermes installation host multiple named agent personas (lead hunter, flight tracker, etc.) with separate identity/goals while sharing the same keys, tools, memory store, and runtime.

Architecture: add a first-class "agent presets" layer on top of the existing single-agent SOUL/personality model. Each preset stores its own soul/role/goal/personality/instructions/default skills, and the active preset can be selected by chat sessions, cron jobs, and the dashboard. Keep this lighter-weight than full Hermes profiles: profiles remain full isolation; agent presets are same-install, shared-keys, shared-runtime overlays.

Tech Stack: Python/FastAPI backend in hermes_cli/web_server.py, React dashboard in web/src/pages/AgentPage.tsx + web/src/lib/api.ts, config/state in hermes_cli/config.py plus files under ~/.hermes/agents/, cron integration in tools/cronjob_tools.py and cron/scheduler.py, prompt selection in run_agent.py / cli.py / gateway/run.py.

---

## Product decisions to lock before coding

1. Terminology
- Use "Agent Presets" or "Agents" in the dashboard.
- Profiles stay as they are today: fully isolated installs.
- Agent presets are lightweight overlays inside one profile/install.

2. Data model
- Store each custom agent under ~/.hermes/agents/<slug>/
  - AGENT.json        metadata + structured settings
  - SOUL.md           primary identity text
  - AGENTS.md         optional project-style instruction layer for that agent
  - README.md         optional notes for humans
- Keep one built-in default preset that maps to the current behavior.

3. Shared vs isolated boundaries
Shared across all agent presets:
- .env keys
- tool availability
- sessions DB implementation
- memories store
- cron engine
- installed skills
- dashboard

Per-agent preset state:
- soul / identity
- role / goal / description
- default personality key
- extra prompt instructions
- default skills list
- allowed or preferred toolsets (optional, phase 2)
- default cron skill bundle / behavior hints (optional, phase 2)

4. Session binding
- every new conversation can optionally bind to an agent preset
- cron jobs can explicitly name which preset to run as
- dashboard exposes active preset and editing UI

5. Non-goal
- do not build full multi-tenant isolation
- do not duplicate keys or create separate env files per preset
- do not replace Hermes profiles; complement them

---

## Proposed user-facing behavior

### CLI
- hermes --agent lead-hunter
- hermes --agent flight-tracker
- /agent use flight-tracker
- /agent list
- /agent show

### Cron
- cron jobs accept agent_name
- scheduler loads that preset's soul + instructions + default skills before prompt
- if omitted, use the default preset

### Dashboard /agent tab
Sections:
1. Active agent summary
2. Agent switcher
3. Agent library list
4. Create/edit agent form
5. Identity editor
   - SOUL.md
   - role/goal/description
   - optional AGENTS.md snippet
6. Runtime defaults
   - default personality
   - default skills
   - optional default toolset policy
7. Cron usage snippet
   - shows how this preset is referenced in cron jobs

### Example presets
- lead-hunter
- flight-tracker
- market-watcher
- coding-assistant
- research-analyst

---

## Codebase strategy

Reuse what already exists instead of inventing parallel systems:
- current SOUL.md handling in run_agent.py / hermes_cli.config
- current personality support in config.yaml (agent.personalities)
- current Agent dashboard page + /api/agent/profile endpoint
- current cron skill attachment model in tools/cronjob_tools.py + cron/scheduler.py
- existing profile concept remains untouched

Add a new layer:
- agent preset registry + active preset resolution
- preset-aware prompt/source loading
- preset-aware cron execution
- preset-aware dashboard management APIs

---

## Task 1: Add an agent preset domain model

Objective: define the structured representation for multi-agent presets and where they live on disk.

Files:
- Create: agent/agent_presets.py
- Test: tests/agent/test_agent_presets.py

Step 1: Write failing tests for preset discovery and built-in default behavior

Test cases:
- loading with no ~/.hermes/agents directory returns one built-in default preset
- valid preset directory with AGENT.json + SOUL.md is discovered
- invalid preset is skipped safely
- active preset falls back to default when unset

Step 2: Implement minimal preset model

In agent/agent_presets.py create:
- AgentPreset dataclass
  - name
  - slug
  - role
  - goal
  - description
  - personality
  - default_skills
  - soul_path
  - agents_path
  - metadata_path
  - built_in
- helpers:
  - get_agent_presets_dir()
  - list_agent_presets()
  - load_agent_preset(slug)
  - get_default_agent_preset()
  - get_active_agent_slug(config=None)

Step 3: Define on-disk schema

AGENT.json shape:
```json
{
  "name": "Lead Hunter",
  "slug": "lead-hunter",
  "role": "Evidence-first local SMB opportunity finder",
  "goal": "Find outreach-ready local businesses with weak digital demand capture",
  "description": "Commercial lead-finding preset for agency prospecting",
  "personality": "concise",
  "default_skills": ["local-business-opportunity-finder"],
  "enabled": true
}
```

Step 4: Verification
- Run: `source venv/bin/activate && python -m pytest tests/agent/test_agent_presets.py -q`
- Expected: pass

Step 5: Commit
- `git add agent/agent_presets.py tests/agent/test_agent_presets.py`
- `git commit -m "feat: add agent preset registry"`

---

## Task 2: Add config support for active preset + preset defaults

Objective: add minimal config keys so Hermes can remember which preset is active.

Files:
- Modify: hermes_cli/config.py
- Test: tests/hermes_cli/test_config.py or new tests/hermes_cli/test_agent_preset_config.py

Step 1: Add config keys to DEFAULT_CONFIG

Add under agent:
```python
"active_preset": "default",
```

Optional phase-1 key only if useful:
```python
"preset_overrides": {}
```

Step 2: Expose any needed env/config schema metadata if dashboard should render it cleanly

Step 3: Add tests
- default config includes agent.active_preset == "default"
- config round-trip preserves it

Step 4: Verification
- targeted pytest command

Step 5: Commit
- `git commit -m "feat: add active agent preset config"`

---

## Task 3: Make prompt building preset-aware

Objective: let Hermes use a preset-specific SOUL/AGENTS overlay instead of only the root SOUL.md.

Files:
- Modify: run_agent.py
- Possibly modify: agent/prompt_builder.py
- Test: tests/run_agent/test_agent_preset_identity.py

Step 1: Write failing tests

Test cases:
- when no preset specified, behavior matches today
- when preset slug is provided, prompt identity uses ~/.hermes/agents/<slug>/SOUL.md
- if preset AGENTS.md exists, include it where AGENTS.md is currently used as context instructions
- if preset specifies default skills, they are loaded/injected the same way user-loaded skills are layered

Step 2: Implement preset resolution path

Add a simple resolution order:
1. explicit session/cron/CLI agent preset
2. config.agent.active_preset
3. default

Then use preset files instead of root SOUL.md / cwd AGENTS.md where appropriate.

Important constraint:
- preserve prompt-caching principles
- resolve preset before building the system prompt for the conversation
- do not mutate identity mid-conversation

Step 3: Verification
- targeted pytest

Step 4: Commit
- `git commit -m "feat: use agent presets in prompt building"`

---

## Task 4: Add CLI support for agent presets

Objective: allow direct selection and inspection of presets from CLI sessions.

Files:
- Modify: hermes_cli/main.py
- Modify: cli.py
- Modify: hermes_cli/commands.py
- Test: tests/cli/test_agent_preset_commands.py

Step 1: Add CLI flag
- `hermes --agent <slug>`
- `hermes chat --agent <slug>`

Step 2: Add slash command family
- `/agent`
- `/agent list`
- `/agent use <slug>`
- `/agent show`

Step 3: Implement behavior
- selecting a preset affects new session identity, not already-built prompt context
- `/agent use` should recommend /reset or create a new session if required by caching rules

Step 4: Verification
- targeted CLI tests for parsing + state selection

Step 5: Commit
- `git commit -m "feat: add CLI agent preset selection"`

---

## Task 5: Add cron support for choosing an agent preset

Objective: allow cron jobs to choose which agent persona runs the scheduled task.

Files:
- Modify: tools/cronjob_tools.py
- Modify: cron/jobs.py
- Modify: cron/scheduler.py
- Test: tests/tools/test_cron_agent_preset.py

Step 1: Extend cronjob tool schema
- add optional `agent_name` field on create/update

Step 2: Persist field in jobs
- include agent_name in stored job object

Step 3: Make scheduler pass that preset into the agent runtime
- scheduler builds the effective prompt under that preset
- preset default skills should load before explicit prompt body
- explicit cron skills should win or be appended deterministically

Recommended rule:
- effective skills = preset.default_skills + cron_job.skills
- dedupe while preserving order

Step 4: Add tests
- creating job with agent_name persists it
- scheduler uses the selected preset
- omitted agent_name uses default

Step 5: Verification
- targeted pytest

Step 6: Commit
- `git commit -m "feat: add cron agent preset selection"`

---

## Task 6: Expand /api/agent/profile into full agent preset management API

Objective: turn the Agent page backend into a preset management backend.

Files:
- Modify: hermes_cli/web_server.py
- Test: tests/hermes_cli/test_web_server.py

Step 1: Keep existing endpoint but expand response

New GET `/api/agent/profile` should return:
- active preset
- list of presets
- current preset full metadata
- current preset source files
- available personalities from config.agent.personalities
- recommended cron usage examples

Step 2: Add CRUD endpoints
- `GET /api/agents`
- `POST /api/agents`
- `PUT /api/agents/{slug}`
- `DELETE /api/agents/{slug}`
- `POST /api/agents/{slug}/activate`

Step 3: Add source editing endpoints or fold into PUT
- save AGENT.json
- save SOUL.md
- save optional AGENTS.md

Step 4: Add tests first
- create preset
- list preset
- activate preset
- update preset soul/personality/skills
- reject duplicate slug
- reject deleting built-in default

Step 5: Verification
- run targeted web server tests

Step 6: Commit
- `git commit -m "feat: add agent preset management API"`

---

## Task 7: Redesign the /agent dashboard page for multi-agent management

Objective: convert the current read-only Agent page into an agent preset manager.

Files:
- Modify: web/src/lib/api.ts
- Modify: web/src/pages/AgentPage.tsx
- Possibly create: web/src/components/agent/*
- Test: frontend unit tests if available; otherwise rely on build + backend tests

Step 1: Extend API client/types
Add types for:
- AgentPresetSummary
- AgentPresetDetail
- AgentProfileResponse v2

Add methods:
- getAgents()
- createAgent()
- updateAgent()
- activateAgent()
- deleteAgent()

Step 2: Replace page layout

New /agent page sections:
1. Active Agent card
2. Agent list sidebar
3. Agent editor form
4. Soul editor text area
5. Optional AGENTS.md editor
6. Default skills multiselect / comma editor
7. Personality picker
8. Activate / Save / Duplicate / Delete actions
9. Cron usage panel showing example payload

Step 3: Preserve existing visibility
Still show:
- model/provider/capabilities
- source files used by active preset

Step 4: Add create-from-template flow
Templates:
- default
- lead-hunter
- blank

Step 5: Verification
- `cd web && npm run build`
- manual dashboard check

Step 6: Commit
- `git commit -m "feat: add multi-agent management dashboard"`

---

## Task 8: Seed initial presets and migration logic

Objective: ensure existing users aren’t broken and lead-hunter remains available.

Files:
- Modify: hermes_cli/config.py or new migration helper
- Modify: agent/agent_presets.py
- Test: migration tests

Step 1: Built-in default preset
- maps to current root SOUL.md + current config behavior

Step 2: Seed optional built-in lead-hunter preset
- can point to files shipped in repo or generated under ~/.hermes/agents/lead-hunter/
- do not hard-delete existing root SOUL.md behavior

Step 3: Migration behavior
- if no presets exist, auto-create the default preset view without forcing file writes unless needed
- if user later creates named presets, root SOUL.md becomes the default preset source unless explicitly migrated

Step 4: Verification
- no-presets install still works
- current user setup still works unchanged

Step 5: Commit
- `git commit -m "feat: add default agent preset migration path"`

---

## Task 9: Optional phase-2 subagent policy support

Objective: allow presets to define subagent behavior hints without creating separate installs.

Files:
- Modify: agent/agent_presets.py
- Modify: tools/delegate_tool.py or prompt wiring only if needed
- Test: tests/tools/test_agent_preset_subagent_defaults.py

Phase-2 fields:
- delegation_model
- default_subagent_style
- default_child_skills
- default_reasoning_effort

Important rule:
- do not actually create daemonized preset-specific child agents yet
- only provide default policies applied when delegate_task is used from that preset

---

## Task 10: Documentation and examples

Objective: make the feature understandable and operational.

Files:
- Create: docs/plans/ or website docs page for agent presets
- Modify: README or website/docs/user-guide/features/

Document:
- difference between profiles vs agent presets
- difference between personalities vs presets
- cron example using agent_name
- examples for lead-hunter and flight-tracker

Example cron tool payload:
```json
{
  "action": "create",
  "name": "Morning flight check",
  "schedule": "0 8 * * *",
  "agent_name": "flight-tracker",
  "prompt": "Check tracked flights and report delays.",
  "skills": ["find-nearby"]
}
```

Step 2: Commit
- `git commit -m "docs: add agent preset documentation"`

---

## Suggested implementation order

Phase 1 (usable core)
1. Task 1 — preset registry
2. Task 2 — active config key
3. Task 3 — preset-aware prompt identity
4. Task 5 — cron agent_name support
5. Task 6 — backend management API
6. Task 7 — dashboard manager UI

Phase 2 (power features)
7. Task 4 — richer CLI commands
8. Task 8 — migration + seed templates
9. Task 9 — subagent defaults
10. Task 10 — docs

---

## Design recommendation

Preferred implementation model:
- Keep Profiles = hard isolation
- Add Agent Presets = soft identity overlays

Why this is the right fit:
- matches your requirement that all agents share keys and everything else
- avoids operational overhead of many full profiles
- still supports distinct souls/goals/functions
- fits cron selection cleanly
- fits the existing /agent dashboard page well

---

## Acceptance criteria

This feature is complete when:
- user can create multiple named agents in the dashboard
- each agent has its own soul/role/goal/personality/default skills
- one agent can be activated as current
- cron jobs can target a specific agent preset
- sessions started with a preset use that preset identity
- all presets share the same keys and install
- lead-hunter remains available as one preset among many
- dashboard build passes
- targeted tests pass

---

## Verification commands

```bash
source venv/bin/activate
python -m pytest tests/agent/test_agent_presets.py -q
python -m pytest tests/hermes_cli/test_web_server.py -q
python -m pytest tests/tools/test_cron_agent_preset.py -q
cd web && npm run build
```

---

## Rollback strategy

If prompt integration becomes too invasive:
- ship dashboard CRUD + cron agent_name first
- resolve preset to an augmented prompt prefix rather than full SOUL override
- keep root SOUL.md as global fallback

If cron integration becomes risky:
- land preset management UI/API first
- defer scheduler execution changes behind an `agent_name` feature flag

---

Plan complete. Ready to execute in phases. Recommended first implementation slice: preset registry + active preset config + read-only dashboard list + cron `agent_name` persistence, before full editing UI.
