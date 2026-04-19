# Agent Presets

Agent Presets let one Hermes installation host multiple named personas that share the same keys, tools, memory store, sessions database, skills installation, cron engine, and dashboard.

Use Agent Presets when you want soft identity overlays.
Use Profiles when you want full isolation.

## Profiles vs Agent Presets

Profiles
- separate Hermes homes
- separate config, keys, memories, sessions, and installs
- operationally heavier
- best for hard isolation

Agent Presets
- one shared Hermes install
- shared keys, tools, memory, sessions, skills, cron, and dashboard
- separate SOUL.md / role / goal / description / personality / default skills
- best for switching persona inside one install

## Personalities vs Presets

Personalities
- lightweight prompt overlays
- mainly style/tone shaping
- usually chosen from config.agent.personalities

Presets
- full named persona packages
- own SOUL.md, role, goal, description, optional AGENTS.md, default skills
- can be activated in the dashboard, CLI, and cron jobs

## Storage model

Custom presets live under:
- ~/.hermes/agents/<slug>/AGENT.json
- ~/.hermes/agents/<slug>/SOUL.md
- ~/.hermes/agents/<slug>/AGENTS.md

Built-ins
- default: maps to the root ~/.hermes/SOUL.md behavior
- lead-hunter: shipped as a built-in template and available even before the user creates custom presets

Custom presets override built-ins when they use the same slug.
If a custom override is deleted, the built-in preset becomes visible again.

## CLI usage

Start chat with a preset:

```bash
hermes --agent lead-hunter
hermes chat --agent lead-hunter
```

Inspect or switch in an active CLI session:

```text
/agent
/agent list
/agent show
/agent use lead-hunter
```

Important:
- `/agent use <slug>` changes the preset for new prompt builds
- it does not silently mutate an already-built active prompt
- after switching presets, use `/new` or `/clear` to start a fresh session with the new identity

## Cron usage

Cron jobs can target a preset with `agent_name`.

Example:

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

If `agent_name` is omitted, Hermes uses the active preset or falls back to `default`.

## Dashboard usage

The `/agent` dashboard page supports:
- active preset summary
- preset library list
- preset creation and editing
- SOUL.md editing
- optional AGENTS.md editing
- role / goal / description fields
- personality selection
- default skills editing
- activation
- cron usage snippet

## Example presets

Lead Hunter
- purpose: local SMB prospecting for websites, apps, automation, funnels, and local SEO
- built-in: yes
- default skills: `local-business-opportunity-finder`

Flight Tracker
- purpose: track flights, delays, or daily airline monitoring
- built-in: no, but can be created as a custom preset

Research Analyst
- purpose: recurring market scans, synthesis, and evidence-first research
- built-in: no, but can be created as a custom preset

## Migration behavior

- Existing installs continue to work with the built-in `default` preset mapped to root `SOUL.md`
- No preset files are required for the default experience
- Built-in presets can exist without writing anything into `~/.hermes/agents/`
- Custom presets are only written when the user creates or updates them
