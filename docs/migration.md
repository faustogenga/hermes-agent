# Hermes server migration guide

This document describes how to recreate this Hermes setup on a new server without losing the important parts of the current machine.

## What gets restored from where

There are **four layers** to a full rebuild:

1. **Git repo** — Hermes code, custom code changes, docs, helper scripts, and this migration kit.
2. **Hermes state backup** — `~/.hermes` user data such as config, skills, memories, sessions, cron state, and auth state.
3. **Secrets** — `.env` values and any OAuth/device logins that are not stored in git.
4. **Host-specific infra** — Tailscale, systemd user services, DNS/hostnames, firewall rules, dashboard exposure settings.

Important Hermes behavior:

- `hermes backup` **does include** your Hermes home state.
- `hermes backup` **does not include** the `~/.hermes/hermes-agent` git checkout.
- `hermes profile export` / `hermes profile import` are useful for per-profile moves.
- `hermes import` should be run with the gateway stopped.

## Current known setup

At the time this migration kit was created:

- Canonical repo: `https://github.com/faustogenga/hermes-agent.git`
- Current branch: `main`
- Current commit at creation time: `860cf5133a7961e71191de9cf0ac5ea130bfab61`
- Known profiles:
  - `default`
  - `lead-hunter-brussels`

When doing a production migration, prefer a **tag or pinned commit** over a floating branch.

## Files added for migration

This repo now includes:

- `docs/migration.md`
- `scripts/bootstrap_server.sh`
- `scripts/verify_install.sh`
- `.env.template`

## Recommended backup artifacts

Create these on the source server before migration:

### 1. Full Hermes backup

```bash
hermes backup -o ~/hermes-backup-full.zip
```

This is the main disaster-recovery artifact.

### 2. Optional per-profile archives

```bash
hermes profile export default -o ~/default-profile.tar.gz
hermes profile export lead-hunter-brussels -o ~/lead-hunter-brussels-profile.tar.gz
```

Use these when you want profile-level import/export instead of a whole-home restore.

### 3. Secrets bundle

Do **not** commit real secrets to git.

Keep a secure copy of:

- `~/.hermes/.env`
- any profile-specific `.env` files
- any extra credentials not covered by the Hermes backup strategy

Recommended storage:

- 1Password / Bitwarden
- encrypted archive
- cloud secret manager

## Source-server checklist

Run this on the current server before switching hosts:

### A. Make sure repo code is committed and pushed

```bash
cd ~/.hermes/hermes-agent
git status
git add docs/migration.md scripts/bootstrap_server.sh scripts/verify_install.sh .env.template
git commit -m "docs: add server migration kit"
git push origin main
```

If you have other uncommitted local code changes you want preserved, commit and push those too.

### B. Create a full backup

```bash
hermes backup -o ~/hermes-backup-full.zip
```

### C. Optionally export profiles

```bash
hermes profile export default -o ~/default-profile.tar.gz
hermes profile export lead-hunter-brussels -o ~/lead-hunter-brussels-profile.tar.gz
```

### D. Record the exact git ref

```bash
cd ~/.hermes/hermes-agent
git rev-parse HEAD
```

Use that ref during the rebuild if you want an exact match.

## Target-server rebuild flow

## 1. Prepare the new host

Install the basic host tools first:

- git
- curl
- uv
- node/npm
- python 3.11+
- Tailscale (if remote dashboard/gateway access depends on it)

Also enable the user session/service behavior you expect, especially if you want the gateway to survive logout.

## 2. Clone the repo

```bash
git clone https://github.com/faustogenga/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
```

For exact reproducibility, checkout a pinned ref:

```bash
git checkout 860cf5133a7961e71191de9cf0ac5ea130bfab61
```

Or use a migration tag if you created one.

## 3. Add secrets

Copy `.env.template` to the location you want to fill in later, or place a real env file on the new host before bootstrapping.

Example:

```bash
cp .env.template ~/.hermes/.env
```

Then fill in the real values securely.

## 4. Run the bootstrap script

Example with a full backup restore:

```bash
cd ~/.hermes/hermes-agent
./scripts/bootstrap_server.sh \
  --target-dir ~/.hermes/hermes-agent \
  --hermes-home ~/.hermes \
  --repo-ref 860cf5133a7961e71191de9cf0ac5ea130bfab61 \
  --backup-zip ~/hermes-backup-full.zip
```

Example with profile archives instead of a full backup:

```bash
cd ~/.hermes/hermes-agent
./scripts/bootstrap_server.sh \
  --target-dir ~/.hermes/hermes-agent \
  --hermes-home ~/.hermes \
  --repo-ref 860cf5133a7961e71191de9cf0ac5ea130bfab61 \
  --profile-archive ~/default-profile.tar.gz \
  --profile-archive ~/lead-hunter-brussels-profile.tar.gz
```

## 5. Verify the rebuild

```bash
cd ~/.hermes/hermes-agent
./scripts/verify_install.sh
```

Optional dashboard verification:

```bash
./scripts/verify_install.sh --dashboard-url http://127.0.0.1:9119/
```

Optional Firecrawl verification:

```bash
./scripts/verify_install.sh --check-firecrawl
```

## Host-specific tasks that still need manual attention

These are intentionally **not** fully automated because they depend on the destination machine:

### Tailscale

Reinstall/login and then reapply any serve/funnel settings, for example:

```bash
tailscale serve status
```

If you expose the dashboard over Tailscale and want MagicDNS access, make sure the dashboard binding matches your exposure strategy.

### Dashboard binding

Local-only dashboard:

```bash
hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
```

Tailscale-accessible dashboard:

```bash
hermes dashboard --host 0.0.0.0 --port 9119 --insecure --no-open --skip-build
```

### Gateway service

The bootstrap script attempts to install/restart the gateway service, but you should still verify:

```bash
hermes gateway status
```

### Systemd linger

If needed for services to survive logout:

```bash
sudo loginctl enable-linger "$USER"
```

## Recovery strategy

### Fastest full recovery

1. Clone repo.
2. Checkout pinned ref.
3. Restore secrets.
4. Run `bootstrap_server.sh` with `--backup-zip`.
5. Reapply host-specific infra.
6. Run `verify_install.sh`.

### Cleaner reproducible rebuild

1. Clone repo.
2. Checkout pinned ref.
3. Restore secrets from secure secret storage.
4. Run `bootstrap_server.sh` without a full backup, or with per-profile archives.
5. Reconfigure host-specific infra.
6. Run `verify_install.sh`.

## Summary

Reproducibility for this setup means:

- **git** restores the code
- **Hermes backup/profile archives** restore the Hermes state
- **secret storage** restores credentials
- **bootstrap + verify scripts** restore machine behavior

That combination is what makes a new server rebuildable instead of depending on one snowflake machine.
