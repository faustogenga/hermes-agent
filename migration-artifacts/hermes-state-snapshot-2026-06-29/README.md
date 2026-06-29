# Hermes state snapshot for migration

This directory captures non-secret Hermes state that lives outside the git checkout but matters for rebuilding this server closely on another host.

Included:
- `cron/jobs.json` — scheduler registry snapshot from `~/.hermes/cron/jobs.json`
- `scripts/enrich_padel_contacts.py` — current padel contact enrichment helper
- `scripts/upsert_padel_jobs_airtable.py` — Airtable upsert helper for padel jobs
- `scripts/lead_enrichment_context.py` — Brussels lead-enrichment cron context script

Notes:
- These files are snapshots copied from `~/.hermes`, not the canonical upstream repo layout.
- No secrets were intentionally included.
- For a fully identical rebuild, still restore the real `~/.hermes` backup/archive as described in `docs/migration.md`.
