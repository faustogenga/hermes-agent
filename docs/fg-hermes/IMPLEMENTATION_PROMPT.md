# Implementation Prompt — paste this to a Hermes server session

This is a self-contained briefing for a Hermes agent running on the
server. Copy the fenced block below and paste it as a single message
to that agent. It carries enough context to take over the fork
without any prior conversation.

```
You are taking over a fork of hermes-agent. Read this prompt fully, then
execute. The repo is at the standard hermes-agent checkout — wherever you
run `hermes` from. Work in stages and stop after each one to confirm.

═══════════════════════════════════════════════════════════════════════
GOAL
═══════════════════════════════════════════════════════════════════════

Switch the local checkout to the `FG-Hermes` branch and stand up the
`fg-hermes` plugin per the specs at `docs/fg-hermes/`. Once green, run
the dashboard from this branch from now on (default base for both
backend functionality and the web UI).

═══════════════════════════════════════════════════════════════════════
CONTEXT — what FG-Hermes is
═══════════════════════════════════════════════════════════════════════

`FG-Hermes` is a fork-local branch whose only commits today are docs
under `docs/fg-hermes/`. Those docs spec out a plugin at
`plugins/fg_hermes/` that adds:

  • Custom agent presets (Lead Hunter, Flight Finder, Brussels Housing
    Hunter, …) with a dashboard "Agents" tab to create / edit /
    activate them.
  • Cron jobs that pick which preset to run as (the `agent_name` field
    on each job), plus a richer CronPage with a Daily Schedule Map,
    schedule builder, and timezone control.

The plugin extracts the heavy custom code (1000+ LOC of TSX, the
preset engine, the FastAPI routes) into `plugins/fg_hermes/` so that
`git pull` from upstream main never overwrites it. A handful of
small touch-points in upstream files (~10 files, listed in
`docs/fg-hermes/AGENTS_FEATURE.md §11` and `CRON_FEATURE.md §7`) are
pinned with `merge=ours` in `.gitattributes`.

The branch tracking rule (set already, do not change): FG-Hermes does
NOT track upstream. Local `main` tracks `origin/main` and is the
conduit for pulling upstream improvements (`git pull upstream main`).
You merge `main → FG-Hermes` only when you decide to.

═══════════════════════════════════════════════════════════════════════
STAGE 1 — switch to the branch and read the specs
═══════════════════════════════════════════════════════════════════════

1.  `git fetch origin && git fetch upstream`
2.  `git checkout FG-Hermes`
3.  `git pull --ff-only origin FG-Hermes`  (no-op if you're up to date)
4.  Read in this order:
      - `docs/fg-hermes/README.md`           (~95 lines; the rationale)
      - `docs/fg-hermes/AGENTS_FEATURE.md`   (~800 lines; agents half)
      - `docs/fg-hermes/CRON_FEATURE.md`     (~440 lines; cron half)
      - `docs/fg-hermes/DATA_LOCATIONS.md`   (~225 lines; user-data contract)

Confirm before proceeding: "I have FG-Hermes checked out and have read
the four specs."

═══════════════════════════════════════════════════════════════════════
STAGE 2 — build the plugin (start of `plugins/fg_hermes/`)
═══════════════════════════════════════════════════════════════════════

Follow `AGENTS_FEATURE.md §12` (the numbered re-implementation order)
end-to-end, then `CRON_FEATURE.md §8` for the cron half. In short:

A.  Scaffold the directory:
    ```
    plugins/fg_hermes/
    ├── __init__.py
    ├── agent/
    │   ├── __init__.py            (re-exports the engine API)
    │   ├── presets.py             (~310 LOC engine, see §3)
    │   └── preset_templates/      (copy from the backup branch)
    ├── dashboard/
    │   ├── manifest.json
    │   └── plugin_api.py          (FastAPI router + 6 routes + helpers)
    ├── web/
    │   ├── AgentPage.tsx          (~854 LOC — see §7)
    │   ├── CronPage.tsx           (~1100 LOC — see CRON_FEATURE.md §4)
    │   └── styles.css             (~200 LOC custom CSS)
    └── tests/
        ├── conftest.py            (bridges tests/conftest.py fixtures)
        ├── agent/test_agent_presets.py
        ├── cli/test_agent_preset_commands.py
        ├── hermes_cli/test_agent_preset_cli_args.py
        ├── hermes_cli/test_agent_preset_routes.py
        └── run_agent/test_agent_preset_identity.py
    ```

B.  Pull the built-in template files in:
    ```
    git checkout lead-hunter-custom-backup-2026-05-05 \
        -- agent/preset_templates/
    git mv agent/preset_templates plugins/fg_hermes/agent/preset_templates
    ```
    (The backup branch holds the master copies of brussels-housing-hunter,
    flight-finder, and lead-hunter templates. Don't worry about the
    branch name — that's just where they live.)

C.  Implement the engine, plugin_api, and TSX pages by following the
    spec sections directly. The spec gives you exact function
    signatures, route shapes, and the UI structure.

D.  Apply the shared-file touch-points listed in
    `AGENTS_FEATURE.md §11`:
        agent/prompt_builder.py    `agent_preset` kwarg
        run_agent.py               `AIAgent.__init__` reads it
        cli.py                     `--agent` flag + `/agent` slash command
        cron/scheduler.py          forwards `job.agent_name`
        cron/jobs.py               persists `agent_name`
        tools/cronjob_tools.py     exposes `agent_name`
        hermes_cli/config.py       `agent.active_preset = "default"`
        hermes_cli/web_server.py   timezone-recompute on PUT /api/config
        web/src/App.tsx            sidebar + route entries
        web/src/lib/api.ts         8 new methods + types
        web/vite.config.ts         alias for AgentPage + CronPage
        web/tsconfig.app.json      matching paths entry
        web/package.json           postinstall symlink hook
        web/src/index.css          @import the plugin styles.css

E.  Pin every shared-file touch-point in `.gitattributes`:
    ```
    agent/prompt_builder.py       merge=ours
    run_agent.py                  merge=ours
    cli.py                        merge=ours
    cron/scheduler.py             merge=ours
    cron/jobs.py                  merge=ours
    tools/cronjob_tools.py        merge=ours
    hermes_time.py                merge=ours
    hermes_cli/config.py          merge=ours
    hermes_cli/web_server.py      merge=ours
    web/src/App.tsx               merge=ours
    web/src/lib/api.ts            merge=ours
    web/src/plugins/types.ts      merge=ours
    web/src/index.css             merge=ours
    web/vite.config.ts            merge=ours
    web/tsconfig.app.json         merge=ours
    web/package.json              merge=ours
    ```
    Then run once: `git config merge.ours.driver true`

F.  Add `plugins/fg_hermes/tests` to `pyproject.toml`:
    ```
    [tool.pytest.ini_options]
    testpaths = ["tests", "plugins/fg_hermes/tests"]
    ```

G.  Hide upstream's `/profiles` ("Profiles : Multi Agents") tab in
    `web/src/App.tsx` — it duplicates our Agents tab.

Commit each logical step (engine, API, UI, touch-points). Do NOT
amend or force-push.

═══════════════════════════════════════════════════════════════════════
STAGE 3 — verify and start using
═══════════════════════════════════════════════════════════════════════

1.  Install + build:
        cd web && npm install && cd ..
        npm --prefix web run build
    The build must finish "✓ built in N s" with `hermes_cli/web_dist/`
    populated. If TS errors block the build, run `vite build` directly
    (the package.json `build` script is `vite build` only — `tsc -b` is
    available as a separate `npm run typecheck`).

2.  Python imports + plugin discovery:
        python3 -c "
        import hermes_cli.web_server as ws
        plugins = ws._get_dashboard_plugins()
        names = [p['name'] for p in plugins]
        print('plugins:', names)
        assert 'fg-hermes' in names, 'fg-hermes plugin not discovered'

        routes = sorted({r.path for r in ws.app.routes
                         if hasattr(r,'path') and 'fg-hermes' in r.path})
        print('fg-hermes routes:')
        for r in routes: print(' ', r)
        assert any('agent/profile' in r for r in routes)
        "

3.  Run tests:
        pytest plugins/fg_hermes/tests/ -q

4.  Start the dashboard:
        hermes dashboard --no-open --port 9119
    Then in a browser visit http://127.0.0.1:9119/, sign in (the token
    is auto-injected on the same machine), and click into the Agents
    tab. You should see the four built-in presets (default, lead-hunter,
    flight-finder, brussels-housing-hunter), be able to create a new
    one, activate it, and see it appear in the agent_name dropdown on
    the Cron page.

5.  Smoke a cron job:
        - Create a one-off cron with `agent_name = lead-hunter`.
        - Trigger it (the ⚡ button) and confirm the run output shows
          the Lead Hunter SOUL.md content in the system prompt.

═══════════════════════════════════════════════════════════════════════
STAGE 4 — make this branch the new default
═══════════════════════════════════════════════════════════════════════

Once Stages 1–3 are green:

  • Don't merge FG-Hermes back into main on the server. main stays as
    the upstream-tracking conduit.
  • From now on, run `hermes` and `hermes dashboard` while checked out
    on FG-Hermes. If you have a systemd / launchd / PM2 service that
    starts the dashboard, leave it pinned to FG-Hermes too.
  • To pick up upstream improvements:
        git checkout main
        git pull upstream main
        git push origin main
        git checkout FG-Hermes
        git merge main
        # resolve any conflicts on merge=ours-pinned files (these are
        #  one-line touch-points that pin auto-resolves to "ours")
        npm --prefix web run build
        pytest plugins/fg_hermes/tests/

═══════════════════════════════════════════════════════════════════════
RULES OF THE ROAD
═══════════════════════════════════════════════════════════════════════

  - Don't push to `upstream/*`. Only push to `origin`.
  - Don't force-push.
  - If something doesn't match the spec, the spec wins — don't drift.
  - User data at `~/.hermes/agents/` and `~/.hermes/cron/jobs.json` is
    sacred. Never edit / delete it without explicit confirmation.
  - Stop and ask if a stage fails in a way the spec doesn't predict
    (especially in Stage 2D — the prompt_builder / run_agent /
    cli / cron patches need surgical care).

When you're done, post a summary of:
  • the commit hashes you pushed,
  • the count of presets discovered,
  • the routes mounted under /api/plugins/fg-hermes/,
  • whether `hermes dashboard` boots clean,
  • any spec deviations you had to make and why.
```
