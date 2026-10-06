#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Verify a Hermes server rebuild.

Usage:
  scripts/verify_install.sh [options]

Options:
  --target-dir PATH         Hermes repo checkout path (default: ~/.hermes/hermes-agent)
  --hermes-home PATH        Hermes home directory (default: ~/.hermes)
  --dashboard-url URL       Optional dashboard URL to probe
  --check-firecrawl         If FIRECRAWL_API_KEY is present, run a live scrape test
  -h, --help                Show this help
EOF
}

log() { printf '[verify] %s\n' "$*"; }
warn() { printf '[verify][warn] %s\n' "$*" >&2; }
fail() { printf '[verify][error] %s\n' "$*" >&2; exit 1; }

TARGET_DIR="${HOME}/.hermes/hermes-agent"
HERMES_HOME="${HOME}/.hermes"
DASHBOARD_URL=""
CHECK_FIRECRAWL=0

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
    --dashboard-url)
      DASHBOARD_URL="$2"
      shift 2
      ;;
    --check-firecrawl)
      CHECK_FIRECRAWL=1
      shift
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

[[ -d "$TARGET_DIR" ]] || fail "Missing target dir: $TARGET_DIR"
[[ -x "$TARGET_DIR/venv/bin/hermes" ]] || fail "Missing Hermes binary: $TARGET_DIR/venv/bin/hermes"
[[ -f "$TARGET_DIR/pyproject.toml" ]] || fail "Missing pyproject.toml in $TARGET_DIR"

export HERMES_HOME
HERMES_BIN="$TARGET_DIR/venv/bin/hermes"

log "Hermes binary"
"$HERMES_BIN" --version

log "Git status"
git -C "$TARGET_DIR" status --short --branch

log "Profiles"
"$HERMES_BIN" profile list

log "Config paths"
"$HERMES_BIN" config path
"$HERMES_BIN" config env-path

log "Gateway status"
"$HERMES_BIN" gateway status || warn "Gateway status check reported a problem"

log "Cron scheduler status"
"$HERMES_BIN" cron status || warn "Cron status reported a problem"

log "Cron registry"
"$HERMES_BIN" cron list --all || warn "Cron list reported a problem"

if [[ -f "$HERMES_HOME/channel_directory.json" ]]; then
  log "Known Telegram/home channels from channel directory"
  python3 - <<'PY' "$HERMES_HOME/channel_directory.json"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text())
items = obj.get('platforms', {}).get('telegram', [])
if not items:
    print('  none')
for item in items:
    print(f"  {item.get('id')} | {item.get('name')} | {item.get('type')} | thread={item.get('thread_id')}")
PY
fi

if command -v tailscale >/dev/null 2>&1; then
  log "Tailscale Serve status"
  tailscale serve status || warn "tailscale serve status reported a problem"
fi

if [[ -n "$DASHBOARD_URL" ]]; then
  log "Probing dashboard URL: $DASHBOARD_URL"
  code=$(curl -sS -o /tmp/hermes-verify-dashboard.out -w '%{http_code}' "$DASHBOARD_URL")
  [[ "$code" == "200" ]] || fail "Dashboard probe failed with HTTP $code"
  head -n 5 /tmp/hermes-verify-dashboard.out || true
fi

if [[ $CHECK_FIRECRAWL -eq 1 ]]; then
  log "Checking Firecrawl via live scrape"
  python3 - <<'PY'
from pathlib import Path
from dotenv import dotenv_values
import requests
import os

home = Path(os.environ['HERMES_HOME'])
env = {}
for p in [home / '.env', home / 'hermes-agent' / '.env']:
    if p.exists():
        env.update({k: v for k, v in dotenv_values(p).items() if v is not None})
key = env.get('FIRECRAWL_API_KEY')
if not key:
    raise SystemExit('FIRECRAWL_API_KEY not present; cannot run --check-firecrawl')
headers = {
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json',
}
resp = requests.post(
    'https://api.firecrawl.dev/v1/scrape',
    headers=headers,
    json={'url': 'https://example.com', 'formats': ['markdown'], 'onlyMainContent': True},
    timeout=60,
)
print('firecrawl_status', resp.status_code)
text = resp.text[:300].replace('\n', ' ')
print('firecrawl_preview', text)
if resp.status_code != 200:
    raise SystemExit(f'Firecrawl scrape failed: HTTP {resp.status_code}')
PY
fi

log "Verification complete"