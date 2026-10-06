# Hermes server migration guide

This document is the current migration plan for moving this Hermes setup to a new cloud server.

It is written for a reproducible rebuild, not a one-off copy.

## 4-layer restore model

A full migration has four separate layers:

1. Code layer
   - git repo: `https://github.com/faustogenga/hermes-agent.git`
   - branch: `main`
   - pinned source commit at time of this guide update: `1be89307ddbc00f9967c3ae336939e8fc8fe9e43`
   - migration docs/scripts inside this repo

2. Hermes state layer
   - `~/.hermes/config.yaml`
   - `~/.hermes/cron/jobs.json`
   - `~/.hermes/state.db`
   - `~/.hermes/auth.json`
   - `~/.hermes/skills/`
   - `~/.hermes/sessions/`
   - profile state under `~/.hermes/profiles/`
   - helper scripts under `~/.hermes/scripts/`

3. Secrets layer
   - `~/.hermes/.env`
   - profile-specific `.env` files
   - OAuth/device auth stored in Hermes auth state
   - third-party API keys for Airtable, Tavily, Firecrawl, Google Places, Telegram, etc.

4. Host/infra layer
   - systemd user service for gateway
   - Tailscale install/login
   - Tailscale Serve config
   - dashboard bind strategy
   - hostname/node identity differences on the new machine

Important behavior:
- `hermes backup` includes Hermes home state.
- `hermes backup` does not include the `~/.hermes/hermes-agent` git checkout.
- `hermes profile export` / `hermes profile import` are useful for profile-scoped restores.
- Telegram bot polling cannot be active from two servers at the same time with the same bot token.

## Current live setup snapshot

Live facts verified on this server during this migration update:

- Hermes config path: `/home/ubuntu/.hermes/config.yaml`
- Hermes env path: `/home/ubuntu/.hermes/.env`
- Active Hermes profile: `default`
- Additional profile present: `lead-hunter-brussels`
- Gateway service: `hermes-gateway.service` running under systemd user services
- Linger: enabled (`loginctl show-user ubuntu -p Linger` => `yes`)
- Timezone in config: `Europe/Brussels`
- Messaging platform connected right now: Telegram only
- Known Telegram DM/home chat in channel directory: `8667992401` (`Fausto Genga`)
- Current Tailscale Serve mapping:
  - `https://ip-172-26-13-157.tail82b1d0.ts.net/`
  - proxied privately to `http://127.0.0.1:9119`
- Historical pre-dashboard Funnel/Serve config snapshot exists at:
  - `~/.hermes/backups/tailscale-funnel-before-dashboard.json`

Current cron inventory on this machine at update time:
- 10 active jobs
- 4 paused jobs
- scheduler attached to the running gateway

Current job IDs and names:
- `548f02dad753` — `brussels-daily-leads` — active
- `628deedb3571` — `housing-brussels-2p` — paused
- `47a277b40fed` — `flights-madrid-costa-rica-daily` — paused
- `57680d9f82f8` — `brussels-lead-enrichment` — active
- `a75c797f9081` — `global-padel-coach-jobs-daily` — paused
- `91cdbbf5d133` — `global-padel-coach-jobs-spanish-daily` — paused
- `3245c1ec26f0` — `padel-jobs-spanish-argentina` — active
- `8bdf8990a3b6` — `padel-jobs-spanish-spain` — active
- `fdd2f7cab1a6` — `padel-jobs-spanish-other` — active
- `357f7bcd43b7` — `padel-jobs-english-us` — active
- `e447c7b7a62c` — `padel-jobs-english-europe` — active
- `f3ac339c9b90` — `padel-jobs-english-asia` — active
- `7906e84ff7f9` — `padel-jobs-english-rest` — active
- `c816556f3626` — `padel-jobs-contact-enrichment` — active

## Migration artifacts in this repo

This repo should contain the migration kit itself:
- `docs/migration.md`
- `scripts/bootstrap_server.sh`
- `scripts/verify_install.sh`
- `scripts/export_migration_state.sh`
- `.env.template`
- `migration-artifacts/hermes-state-snapshot-2026-07-07/`

The snapshot directory is intentionally non-secret and captures current runtime shape that normally lives outside git.

## Non-secret runtime snapshot contents

The exported state snapshot should include at least:
- current `cron/jobs.json`
- current `channel_directory.json`
- current `gateway_state.json`
- current `config.yaml` copies for default/profile scope
- helper scripts from `~/.hermes/scripts/`
- env variable names only, not values
- Tailscale Serve status JSON when available
- a small human-readable summary of jobs, profiles, Telegram, and Tailscale

## Secrets and auth that must move separately

These do not belong in git:
- `~/.hermes/.env`
- `~/.hermes/profiles/*/.env`
- `~/.hermes/auth.json` if handled outside the full backup flow
- Telegram bot token
- Airtable, Tavily, Firecrawl, Hunter, Apollo, Google, Supabase, GitHub, and other API keys

Discovered environment-variable keys currently used on this server:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS`
- `TELEGRAM_HOME_CHANNEL`
- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `HUNTER_API_KEY`
- `APOLLO_API_KEY`
- `AIRTABLE_PAT`
- `AIRTABLE_WORKSPACE_ID`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_FLIGHTS_TABLE`
- `AIRTABLE_PADEL_BASE_ID`
- `AIRTABLE_PADEL_TABLE_ID`
- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_PLACES_API_KEY`
- `GITHUB_TOKEN`
- `FGBUDDY_PROFILE_ID`
- `FGBUDDY_UNKNOWN_WALLET_ID`
- `FGBUDDY_SUPABASE_URL`
- `FGBUDDY_SUPABASE_KEY`
- `FGBUDDY_TX_WEBHOOK_SECRET`

## Source-server checklist

Do this on the old server before cutover.

### 1. Commit and push the migration kit first

```bash
cd ~/.hermes/hermes-agent
git status
git add docs/migration.md scripts/bootstrap_server.sh scripts/verify_install.sh scripts/export_migration_state.sh .env.template migration-artifacts
git commit -m "docs: refresh Hermes server migration kit"
git push origin main
```

### 2. Export the current non-secret runtime snapshot

```bash
cd ~/.hermes/hermes-agent
./scripts/export_migration_state.sh --snapshot-name hermes-state-snapshot-2026-07-07
```

### 3. Create fresh backup artifacts

Use a new migration directory for this cutover:

```bash
export MIGRATION_DIR="$HOME/.hermes/backups/migration-20260707-050233"
mkdir -p "$MIGRATION_DIR"

hermes backup -o "$MIGRATION_DIR/hermes-backup-full.zip"
hermes profile export default -o "$MIGRATION_DIR/default-profile.tar.gz"
hermes profile export lead-hunter-brussels -o "$MIGRATION_DIR/lead-hunter-brussels-profile.tar.gz"

tar -czf "$MIGRATION_DIR/secrets-bundle.tar.gz" \
  -C "$HOME" \
  .hermes/.env \
  .hermes/auth.json \
  .hermes/profiles/lead-hunter-brussels/.env
```

Notes:
- the secrets bundle is sensitive; keep it encrypted/off-git
- full backup is the best disaster-recovery artifact
- profile archives are useful when you want more selective restore behavior

### 4. Record the exact git ref used for the migration

```bash
cd ~/.hermes/hermes-agent
git rev-parse HEAD
```

## Telegram takeover plan

The simplest and correct way to keep the existing Telegram setup is to reuse the same bot token and move the polling endpoint to the new server.

Important constraint:
- this setup uses Telegram polling
- only one running gateway may poll the same bot at a time
- if both servers run Hermes with the same `TELEGRAM_BOT_TOKEN`, Telegram will return a polling conflict and one instance will lose

Recommended cutover sequence:

1. Restore the new server fully, including `.env` and Hermes auth state.
2. Confirm `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, and `TELEGRAM_HOME_CHANNEL` are present on the new server.
3. Keep the old server running until the new one is ready.
4. At cutover time, stop the old gateway:

```bash
hermes gateway stop
# or
systemctl --user stop hermes-gateway
```

5. Start the gateway on the new server:

```bash
hermes gateway install
hermes gateway restart || hermes gateway start
```

6. Verify:

```bash
hermes gateway status
tail -n 80 ~/.hermes/logs/gateway.log
```

Expected success condition:
- Telegram shows connected on the new server
- no continuing `Conflict: terminated by other getUpdates request` loop after the old gateway is down

If you want to keep the same bot identity and same DM/home channel, do not create a new bot; just move the token and stop the old poller.

## Tailscale takeover plan

Current known private Serve config on the old server:

```text
https://ip-172-26-13-157.tail82b1d0.ts.net/
  -> proxy http://127.0.0.1:9119
```

This is tailnet-only Serve, not public Funnel.

On the new server:

1. Install and log into Tailscale.
2. Confirm the new node joins the same tailnet.
3. Start the Hermes dashboard locally.
4. Recreate Serve on the new node.

Suggested commands:

```bash
tailscale status
hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
tailscale serve http://127.0.0.1:9119
tailscale serve status
```

Notes:
- the new node name and `.ts.net` hostname will probably differ from the old server
- if you need MagicDNS/Tailscale access only, keep the dashboard bound to `127.0.0.1` and use Tailscale Serve as the proxy
- if you instead want direct network access to the dashboard over the tailnet without Serve, bind Hermes to `0.0.0.0` and follow the Host-header caveats
- the historical Funnel/Serve JSON saved in `~/.hermes/backups/tailscale-funnel-before-dashboard.json` is useful if you later want to restore the old `/webhook/tx` publishing behavior

## Target-server rebuild flow

### 1. Prepare host prerequisites

Install the baseline host tools:
- git
- curl
- uv
- node/npm
- python 3.11+
- tailscale

Also enable user linger if you want the gateway to survive logout:

```bash
sudo loginctl enable-linger "$USER"
```

### 2. Clone the repo

```bash
git clone https://github.com/faustogenga/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout 1be89307ddbc00f9967c3ae336939e8fc8fe9e43
```

### 3. Restore secrets

Preferred options:
- restore from secure secret storage
- unpack the encrypted `secrets-bundle.tar.gz`
- or restore from full Hermes backup if you trust that path for this migration

At minimum, make sure the new host gets:
- `~/.hermes/.env`
- `~/.hermes/auth.json` or equivalent Hermes auth state
- any profile-specific env files

### 4. Copy backup artifacts to the new server

Expected cutover artifact set from this migration:
- `hermes-backup-full.zip`
- `default-profile.tar.gz`
- `lead-hunter-brussels-profile.tar.gz`
- `secrets-bundle.tar.gz`

### 5. Run bootstrap

Full backup restore path:

```bash
cd ~/.hermes/hermes-agent
./scripts/bootstrap_server.sh \
  --target-dir ~/.hermes/hermes-agent \
  --hermes-home ~/.hermes \
  --repo-ref 1be89307ddbc00f9967c3ae336939e8fc8fe9e43 \
  --backup-zip ~/.hermes/backups/migration-20260707-050233/hermes-backup-full.zip
```

Profile-based restore path:

```bash
cd ~/.hermes/hermes-agent
./scripts/bootstrap_server.sh \
  --target-dir ~/.hermes/hermes-agent \
  --hermes-home ~/.hermes \
  --repo-ref 1be89307ddbc00f9967c3ae336939e8fc8fe9e43 \
  --profile-archive ~/.hermes/backups/migration-20260707-050233/default-profile.tar.gz \
  --profile-archive ~/.hermes/backups/migration-20260707-050233/lead-hunter-brussels-profile.tar.gz
```

Important restore-order note:
- if you are both importing a backup and copying a fresh env file, copy the env file after import so the backup does not overwrite your intended secrets file

### 6. Re-enable Telegram on the new server

Use the Telegram takeover sequence described above.

### 7. Re-enable Tailscale access on the new server

Use the Tailscale takeover sequence described above.

### 8. Verify the rebuilt machine

```bash
cd ~/.hermes/hermes-agent
./scripts/verify_install.sh --dashboard-url http://127.0.0.1:9119/
```

Optional live Firecrawl verification:

```bash
./scripts/verify_install.sh --check-firecrawl
```

## Recovery paths

### Fastest recovery
1. Clone repo
2. Checkout pinned commit
3. Restore `.env` and auth state
4. Import full Hermes backup
5. Start gateway
6. Recreate Tailscale Serve
7. Stop old Telegram poller and start new one
8. Verify

### Cleaner reproducible rebuild
1. Clone repo
2. Checkout pinned commit
3. Restore secrets
4. Import selected profile archives or minimal state
5. Recreate host-specific infra explicitly
6. Verify

## Success criteria for cutover

The migration is complete when all of these are true on the new server:
- `hermes gateway status` shows running
- `hermes cron status` shows the scheduler active
- `hermes cron list --all` matches the expected jobs and paused/active states
- `hermes profile list` shows `default` and `lead-hunter-brussels`
- Telegram is connected on the new server and disconnected on the old one
- Tailscale Serve points the new node hostname to `http://127.0.0.1:9119`
- dashboard probe returns HTTP 200 locally
- required env vars and auth state are present

That is the point where the new server truly “knows everything” operationally that this server knows.