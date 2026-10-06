#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Export a non-secret Hermes migration snapshot into the git checkout.

Usage:
  scripts/export_migration_state.sh [options]

Options:
  --target-dir PATH         Hermes repo checkout path (default: ~/.hermes/hermes-agent)
  --hermes-home PATH        Hermes home directory (default: ~/.hermes)
  --snapshot-name NAME      Snapshot directory name under migration-artifacts/
                            (default: hermes-state-snapshot-<UTC date>)
  -h, --help                Show this help
EOF
}

log() { printf '[export] %s\n' "$*"; }
fail() { printf '[export][error] %s\n' "$*" >&2; exit 1; }

TARGET_DIR="${HOME}/.hermes/hermes-agent"
HERMES_HOME="${HOME}/.hermes"
SNAPSHOT_NAME="hermes-state-snapshot-$(date -u +%F)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --hermes-home)
      HERMES_HOME="$2"
      shift 2
      ;;
    --snapshot-name)
      SNAPSHOT_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -d "$TARGET_DIR/.git" ]] || fail "Expected a git checkout at $TARGET_DIR"
[[ -d "$HERMES_HOME" ]] || fail "Expected Hermes home at $HERMES_HOME"

OUT_DIR="$TARGET_DIR/migration-artifacts/$SNAPSHOT_NAME"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/cron" "$OUT_DIR/scripts" "$OUT_DIR/gateway" "$OUT_DIR/profiles"

log "Writing snapshot to $OUT_DIR"

cp "$HERMES_HOME/cron/jobs.json" "$OUT_DIR/cron/jobs.json"
cp "$HERMES_HOME/config.yaml" "$OUT_DIR/config.yaml"
cp "$HERMES_HOME/channel_directory.json" "$OUT_DIR/gateway/channel_directory.json"
cp "$HERMES_HOME/gateway_state.json" "$OUT_DIR/gateway/gateway_state.json"

if [[ -f "$HERMES_HOME/profiles/lead-hunter-brussels/config.yaml" ]]; then
  cp "$HERMES_HOME/profiles/lead-hunter-brussels/config.yaml" "$OUT_DIR/profiles/lead-hunter-brussels.config.yaml"
fi

if [[ -d "$HERMES_HOME/scripts" ]]; then
  find "$HERMES_HOME/scripts" -maxdepth 1 -type f -name '*.py' -exec cp {} "$OUT_DIR/scripts/" \;
fi

python3 - <<'PY' "$HERMES_HOME" "$OUT_DIR"
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

hermes_home = pathlib.Path(sys.argv[1])
out_dir = pathlib.Path(sys.argv[2])

# env key names only
keys = []
env_path = hermes_home / '.env'
if env_path.exists():
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        keys.append(line.split('=', 1)[0])
(out_dir / 'env_keys.txt').write_text('\n'.join(keys) + ('\n' if keys else ''))

jobs = json.loads((hermes_home / 'cron' / 'jobs.json').read_text()).get('jobs', [])
active = [j for j in jobs if j.get('enabled')]
paused = [j for j in jobs if not j.get('enabled')]

channel = {}
cd_path = hermes_home / 'channel_directory.json'
if cd_path.exists():
    channel = json.loads(cd_path.read_text())
telegram_channels = channel.get('platforms', {}).get('telegram', [])

serve_json = None
try:
    res = subprocess.run(
        ['tailscale', 'serve', 'status', '--json'],
        text=True,
        capture_output=True,
        check=False,
    )
    if res.stdout.strip():
        serve_json = json.loads(res.stdout)
        (out_dir / 'gateway' / 'tailscale_serve_status.json').write_text(
            json.dumps(serve_json, indent=2) + '\n'
        )
    else:
        (out_dir / 'gateway' / 'tailscale_serve_status.error.txt').write_text(res.stderr)
except FileNotFoundError:
    (out_dir / 'gateway' / 'tailscale_serve_status.error.txt').write_text('tailscale not installed\n')

profiles = []
profiles_dir = hermes_home / 'profiles'
if profiles_dir.exists():
    for p in sorted(x.name for x in profiles_dir.iterdir() if x.is_dir()):
        profiles.append(p)

summary_lines = [
    '# Hermes migration state snapshot',
    '',
    f'Generated UTC: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}',
    f'Hermes home: {hermes_home}',
    '',
    '## Profiles',
    '- default',
]
for p in profiles:
    summary_lines.append(f'- {p}')
summary_lines += [
    '',
    '## Cron summary',
    f'- total jobs: {len(jobs)}',
    f'- active jobs: {len(active)}',
    f'- paused jobs: {len(paused)}',
    '',
    '### Jobs',
]
for job in jobs:
    status = 'active' if job.get('enabled') else 'paused'
    summary_lines.append(
        f"- {job.get('id')} | {job.get('name')} | {status} | {job.get('schedule_display')}"
    )
summary_lines += [
    '',
    '## Telegram channels captured in channel directory',
]
if telegram_channels:
    for item in telegram_channels:
        summary_lines.append(
            f"- {item.get('id')} | {item.get('name')} | {item.get('type')} | thread={item.get('thread_id')}"
        )
else:
    summary_lines.append('- none')
summary_lines += [
    '',
    '## Tailscale Serve',
]
if serve_json:
    summary_lines.append('- tailscale serve status captured in gateway/tailscale_serve_status.json')
else:
    summary_lines.append('- no tailscale serve JSON captured')
summary_lines += [
    '',
    '## Included files',
    '- cron/jobs.json',
    '- config.yaml',
    '- gateway/channel_directory.json',
    '- gateway/gateway_state.json',
    '- env_keys.txt',
    '- scripts/*.py copied from ~/.hermes/scripts',
]
if (out_dir / 'profiles' / 'lead-hunter-brussels.config.yaml').exists():
    summary_lines.append('- profiles/lead-hunter-brussels.config.yaml')
if (out_dir / 'gateway' / 'tailscale_serve_status.json').exists():
    summary_lines.append('- gateway/tailscale_serve_status.json')
(out_dir / 'README.md').write_text('\n'.join(summary_lines) + '\n')

manifest = {
    'snapshot': out_dir.name,
    'generated_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'source_hermes_home': str(hermes_home),
    'profiles': ['default', *profiles],
    'job_counts': {
        'total': len(jobs),
        'active': len(active),
        'paused': len(paused),
    },
    'env_keys': keys,
    'telegram_channels': telegram_channels,
    'files': sorted(
        str(path.relative_to(out_dir))
        for path in out_dir.rglob('*')
        if path.is_file()
    ),
}
(out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY

log "Snapshot export complete"
log "Next step: git add migration-artifacts/$SNAPSHOT_NAME"