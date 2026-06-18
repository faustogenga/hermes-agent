#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap a Hermes server from an already-cloned repo checkout.

Usage:
  scripts/bootstrap_server.sh [options]

Options:
  --target-dir PATH         Hermes repo checkout path (default: ~/.hermes/hermes-agent)
  --hermes-home PATH        Hermes home directory (default: ~/.hermes)
  --repo-ref REF            Git ref to checkout after fetch (branch/tag/commit)
  --env-file PATH           Copy this env file to <hermes-home>/.env before service start
  --backup-zip PATH         Import a full Hermes backup zip after install
  --profile-archive PATH    Import a profile archive (.tar.gz). Can be repeated.
  --skip-gateway            Do not install/restart the Hermes gateway service
  --start-dashboard         Start the dashboard after install
  --dashboard-host HOST     Dashboard host when using --start-dashboard (default: 127.0.0.1)
  --dashboard-port PORT     Dashboard port when using --start-dashboard (default: 9119)
  --dashboard-insecure      Pass --insecure to dashboard start (required for non-localhost binds)
  -h, --help                Show this help

Examples:
  ./scripts/bootstrap_server.sh --repo-ref main
  ./scripts/bootstrap_server.sh --repo-ref <commit> --backup-zip ~/hermes-backup-full.zip
  ./scripts/bootstrap_server.sh --profile-archive ~/default-profile.tar.gz --profile-archive ~/lead-hunter-brussels-profile.tar.gz
EOF
}

log() { printf '[bootstrap] %s\n' "$*"; }
warn() { printf '[bootstrap][warn] %s\n' "$*" >&2; }
fail() { printf '[bootstrap][error] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

TARGET_DIR="${HOME}/.hermes/hermes-agent"
HERMES_HOME="${HOME}/.hermes"
REPO_REF=""
ENV_FILE=""
BACKUP_ZIP=""
SKIP_GATEWAY=0
START_DASHBOARD=0
DASHBOARD_HOST="127.0.0.1"
DASHBOARD_PORT="9119"
DASHBOARD_INSECURE=0
PROFILE_ARCHIVES=()

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
    --repo-ref)
      REPO_REF="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --backup-zip)
      BACKUP_ZIP="$2"
      shift 2
      ;;
    --profile-archive)
      PROFILE_ARCHIVES+=("$2")
      shift 2
      ;;
    --skip-gateway)
      SKIP_GATEWAY=1
      shift
      ;;
    --start-dashboard)
      START_DASHBOARD=1
      shift
      ;;
    --dashboard-host)
      DASHBOARD_HOST="$2"
      shift 2
      ;;
    --dashboard-port)
      DASHBOARD_PORT="$2"
      shift 2
      ;;
    --dashboard-insecure)
      DASHBOARD_INSECURE=1
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

require_cmd git
require_cmd uv
require_cmd npm
require_cmd python3

mkdir -p "$HERMES_HOME"
mkdir -p "${HOME}/.local/bin"

[[ -d "$TARGET_DIR/.git" ]] || fail "Expected a git checkout at $TARGET_DIR"
[[ -f "$TARGET_DIR/pyproject.toml" ]] || fail "Missing pyproject.toml in $TARGET_DIR"
[[ -f "$TARGET_DIR/package.json" ]] || fail "Missing package.json in $TARGET_DIR"

cd "$TARGET_DIR"

log "Repo root: $TARGET_DIR"
log "Hermes home: $HERMES_HOME"

if [[ -n "$REPO_REF" ]]; then
  log "Fetching git refs"
  git fetch --all --tags --prune
  log "Checking out $REPO_REF"
  git checkout "$REPO_REF"
fi

log "Creating/updating managed venv"
uv venv venv --python 3.11

log "Installing Hermes Python dependencies"
uv pip install --python venv/bin/python -e ".[all,dev]"

log "Installing Node/workspace dependencies"
npm install

log "Building dashboard web bundle"
( cd web && npm run build )

log "Installing ~/.local/bin/hermes wrapper"
cat > "${HOME}/.local/bin/hermes" <<EOF
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$TARGET_DIR/venv/bin/hermes" "\$@"
EOF
chmod +x "${HOME}/.local/bin/hermes"

export HERMES_HOME
HERMES_BIN="$TARGET_DIR/venv/bin/hermes"
[[ -x "$HERMES_BIN" ]] || fail "Hermes binary not found at $HERMES_BIN"

if [[ -n "$BACKUP_ZIP" || ${#PROFILE_ARCHIVES[@]} -gt 0 ]]; then
  log "Stopping gateway before import operations"
  "$HERMES_BIN" gateway stop || true
fi

if [[ -n "$BACKUP_ZIP" ]]; then
  [[ -f "$BACKUP_ZIP" ]] || fail "Backup zip not found: $BACKUP_ZIP"
  log "Importing Hermes backup: $BACKUP_ZIP"
  "$HERMES_BIN" import "$BACKUP_ZIP" --force
fi

if [[ ${#PROFILE_ARCHIVES[@]} -gt 0 ]]; then
  for archive in "${PROFILE_ARCHIVES[@]}"; do
    [[ -f "$archive" ]] || fail "Profile archive not found: $archive"
    log "Importing profile archive: $archive"
    "$HERMES_BIN" profile import "$archive"
  done
fi

if [[ -n "$ENV_FILE" ]]; then
  [[ -f "$ENV_FILE" ]] || fail "Env file not found: $ENV_FILE"
  log "Copying env file to $HERMES_HOME/.env"
  cp "$ENV_FILE" "$HERMES_HOME/.env"
fi

log "Running lightweight Hermes sanity checks"
"$HERMES_BIN" --version
"$HERMES_BIN" profile list || true
"$HERMES_BIN" config path || true

if [[ $SKIP_GATEWAY -eq 0 ]]; then
  log "Installing/restarting gateway service"
  "$HERMES_BIN" gateway install || true
  "$HERMES_BIN" gateway restart || "$HERMES_BIN" gateway start || true
fi

if [[ $START_DASHBOARD -eq 1 ]]; then
  if [[ "$DASHBOARD_HOST" != "127.0.0.1" && "$DASHBOARD_HOST" != "localhost" && $DASHBOARD_INSECURE -ne 1 ]]; then
    fail "Non-localhost dashboard binds require --dashboard-insecure"
  fi
  log "Starting dashboard"
  "$HERMES_BIN" dashboard --stop || true
  dashboard_args=(dashboard --host "$DASHBOARD_HOST" --port "$DASHBOARD_PORT" --no-open --skip-build)
  if [[ $DASHBOARD_INSECURE -eq 1 ]]; then
    dashboard_args+=(--insecure)
  fi
  nohup "$HERMES_BIN" "${dashboard_args[@]}" >/tmp/hermes-dashboard-bootstrap.log 2>&1 &
  sleep 3
fi

log "Bootstrap complete"
log "Next step: run scripts/verify_install.sh"
