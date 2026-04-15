#!/usr/bin/env bash
# GARC daemon.sh — Background polling daemon
#
# Polls Gmail inbox for new messages and auto-enqueues them.
# This is the GWS equivalent of LARC's IM poller.
#
# Usage:
#   garc daemon start   — start Gmail poller + worker in background
#   garc daemon stop    — stop all daemon processes
#   garc daemon status  — show running daemon info
#   garc daemon poll-once  — single poll cycle (for testing)

DAEMON_PID_DIR="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/daemon"
DAEMON_LOG_DIR="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/logs"
DAEMON_SEEN_DIR="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/seen"

GMAIL_POLLER_PID="${DAEMON_PID_DIR}/gmail-poller.pid"
GMAIL_POLLER_LOG="${DAEMON_LOG_DIR}/gmail-poller.log"
WORKER_PID="${DAEMON_PID_DIR}/worker.pid"
WORKER_LOG="${DAEMON_LOG_DIR}/worker.log"

garc_daemon() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    start)     _daemon_start "$@" ;;
    stop)      _daemon_stop "$@" ;;
    status)    _daemon_status "$@" ;;
    restart)   _daemon_stop "$@"; sleep 1; _daemon_start "$@" ;;
    poll-once) _daemon_poll_once "$@" ;;
    logs)      _daemon_logs "$@" ;;
    install)   _daemon_install_launchd "$@" ;;
    *)
      cat <<EOF
Usage: garc daemon <subcommand>

Subcommands:
  start      Start Gmail poller and worker in background
  stop       Stop all daemon processes
  status     Show daemon status
  restart    Restart daemon
  poll-once  Run one Gmail poll cycle (foreground, for testing)
  logs       Tail daemon logs
  install    Install as macOS launchd service (auto-start on login)

Options:
  --agent <id>       Agent ID to use (default: GARC_DEFAULT_AGENT)
  --interval <sec>   Poll interval in seconds (default: 60)
  --label <filter>   Gmail label to watch (default: INBOX)
  --unread-only      Only enqueue unread messages (default: true)
  --max <N>          Max messages per poll cycle (default: 10)

Examples:
  garc daemon start
  garc daemon start --interval 30 --agent main
  garc daemon poll-once
  garc daemon status
  garc daemon stop
  garc daemon logs --follow
EOF
      return 1
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────────
# start
# ─────────────────────────────────────────────────────────────────

_daemon_start() {
  local agent="${GARC_DEFAULT_AGENT:-main}"
  local interval=60
  local label="INBOX"
  local max_msgs=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a)    agent="$2"; shift 2 ;;
      --interval|-i) interval="$2"; shift 2 ;;
      --label)       label="$2"; shift 2 ;;
      --max)         max_msgs="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  _daemon_ensure_dirs

  # Check if already running
  if _daemon_is_running "${GMAIL_POLLER_PID}"; then
    echo "⚠️  Gmail poller already running (PID $(cat "${GMAIL_POLLER_PID}"))"
  else
    _start_gmail_poller "${agent}" "${interval}" "${label}" "${max_msgs}"
  fi

  echo ""
  _daemon_status
}

_daemon_ensure_dirs() {
  mkdir -p "${DAEMON_PID_DIR}" "${DAEMON_LOG_DIR}" "${DAEMON_SEEN_DIR}"
}

_daemon_is_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid=$(cat "${pid_file}")
  kill -0 "${pid}" 2>/dev/null
}

_start_gmail_poller() {
  local agent_id="$1"
  local interval="$2"
  local label="$3"
  local max_msgs="$4"

  # Export needed env vars for subprocess
  export GARC_DIR GARC_LIB GARC_CONFIG GARC_CACHE_DIR GARC_DEFAULT_AGENT
  # Use set -a/+a instead of export $(xargs) to handle values with spaces
  if [[ -f "${GARC_CONFIG:-${HOME}/.garc}/config.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${GARC_CONFIG:-${HOME}/.garc}/config.env" 2>/dev/null || true
    set +a
  fi

  ( _gmail_poller_loop "${agent_id}" "${interval}" "${label}" "${max_msgs}" \
      >> "${GMAIL_POLLER_LOG}" 2>&1 ) &

  local poller_pid=$!
  echo "${poller_pid}" > "${GMAIL_POLLER_PID}"
  echo "✅ Gmail poller started (PID ${poller_pid}, interval ${interval}s)"
  echo "   Log: ${GMAIL_POLLER_LOG}"
}

# ─────────────────────────────────────────────────────────────────
# Gmail polling loop — the core ingress driver
# ─────────────────────────────────────────────────────────────────

# ── Single poll cycle (shared by loop and poll-once) ─────────────────────────
_gmail_poll_cycle() {
  local agent_id="${1:-main}"
  local max_msgs="${2:-10}"
  local seen_file="${DAEMON_SEEN_DIR}/seen-${agent_id}.txt"

  touch "${seen_file}"

  python3 - "${seen_file}" "${agent_id}" "${max_msgs}" <<'PY'
import json, sys, subprocess, os

seen_file = sys.argv[1]
agent_id  = sys.argv[2]
max_msgs  = sys.argv[3]
garc_dir  = os.environ.get("GARC_DIR", "")

# Read seen message IDs
try:
    with open(seen_file) as f:
        seen = set(line.strip() for line in f if line.strip())
except Exception:
    seen = set()

# Fetch inbox as JSON
result = subprocess.run(
    ["python3", os.path.join(garc_dir, "scripts", "garc-gmail-helper.py"),
     "inbox", "--max", max_msgs, "--unread", "--format", "json"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"[gmail-poller] inbox fetch error: {result.stderr.strip()}", flush=True)
    sys.exit(1)

try:
    messages = json.loads(result.stdout)
except Exception as e:
    print(f"[gmail-poller] JSON parse error: {e}", flush=True)
    sys.exit(1)

if not isinstance(messages, list):
    messages = []

new_seen = []
enqueued = 0
for msg in messages:
    msg_id  = msg.get("id", "")
    sender  = msg.get("from", "")
    subject = msg.get("subject", "(no subject)")
    snippet = msg.get("snippet", "")[:120]

    if not msg_id:
        continue
    if msg_id in seen:
        new_seen.append(msg_id)
        continue

    text = f"Email from {sender}: {subject}"
    if snippet:
        text += f" — {snippet}"

    garc_bin = os.path.join(garc_dir, "bin", "garc")
    cmd = [garc_bin, "ingress", "enqueue",
           "--text", text,
           "--source", "gmail",
           "--sender", sender,
           "--agent", agent_id]

    env = os.environ.copy()
    env["GARC_DIR"] = garc_dir

    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print(f"[gmail-poller] Enqueued: {msg_id[:16]} from {sender[:30]}", flush=True)
        enqueued += 1
    else:
        print(f"[gmail-poller] Enqueue failed: {r.stderr.strip()}", flush=True)

    new_seen.append(msg_id)

if new_seen:
    with open(seen_file, "a") as f:
        f.write("\n".join(new_seen) + "\n")

print(f"[gmail-poller] Cycle done — {enqueued} enqueued, {len(messages) - enqueued} skipped", flush=True)
PY
}

_gmail_poller_loop() {
  local agent_id="${1:-main}"
  local interval="${2:-60}"
  local label="${3:-INBOX}"
  local max_msgs="${4:-10}"

  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [gmail-poller] Starting (agent=${agent_id}, interval=${interval}s, label=${label})"

  # Reload config
  [[ -f "${GARC_CONFIG:-${HOME}/.garc}/config.env" ]] && \
    source "${GARC_CONFIG:-${HOME}/.garc}/config.env" 2>/dev/null || true

  while true; do
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [gmail-poller] Polling..."
    _gmail_poll_cycle "${agent_id}" "${max_msgs}" || \
      echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [gmail-poller] cycle error, will retry"
    sleep "${interval}"
  done
}

# ─────────────────────────────────────────────────────────────────
# stop
# ─────────────────────────────────────────────────────────────────

_daemon_stop() {
  local stopped=0

  for pid_file in "${GMAIL_POLLER_PID}" "${WORKER_PID}"; do
    if _daemon_is_running "${pid_file}"; then
      local pid
      pid=$(cat "${pid_file}")
      kill "${pid}" 2>/dev/null && {
        echo "✅ Stopped PID ${pid} ($(basename "${pid_file}" .pid))"
        ((stopped++)) || true
      }
    fi
    rm -f "${pid_file}"
  done

  if [[ ${stopped} -eq 0 ]]; then
    echo "No daemon processes running."
  fi
}

# ─────────────────────────────────────────────────────────────────
# status
# ─────────────────────────────────────────────────────────────────

_daemon_status() {
  echo "GARC Daemon Status"
  echo "──────────────────"

  local name pid_file
  for entry in "gmail-poller:${GMAIL_POLLER_PID}" "worker:${WORKER_PID}"; do
    name="${entry%%:*}"
    pid_file="${entry#*:}"
    if _daemon_is_running "${pid_file}"; then
      local pid
      pid=$(cat "${pid_file}")
      echo "  ✅ ${name} — running (PID ${pid})"
    else
      echo "  ⬜ ${name} — stopped"
    fi
  done

  echo ""

  # Queue stats
  local q_dir="${GARC_QUEUE_DIR:-${HOME}/.garc/cache/queue}"
  if [[ -d "${q_dir}" ]]; then
    local pending
    pending=$(find "${q_dir}" -name "*.jsonl" -exec python3 -c "
import json, sys
try:
    q = json.loads(open(sys.argv[1]).readline())
    print(q.get('status',''))
except Exception:
    pass
" {} \; 2>/dev/null | grep -c "^pending$" || echo 0)
    echo "  Queue: ${pending} pending item(s)"
  fi

  echo ""
  echo "Logs:"
  echo "  ${GMAIL_POLLER_LOG}"
  echo "  ${WORKER_LOG}"
}

# ─────────────────────────────────────────────────────────────────
# poll-once — single cycle, foreground (for testing / manual trigger)
# ─────────────────────────────────────────────────────────────────

_daemon_poll_once() {
  local agent="${GARC_DEFAULT_AGENT:-main}"
  local max_msgs=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent="$2"; shift 2 ;;
      --max)      max_msgs="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  _daemon_ensure_dirs

  # Reload config so GARC_DIR etc. are available in subprocesses
  if [[ -f "${GARC_CONFIG:-${HOME}/.garc}/config.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${GARC_CONFIG:-${HOME}/.garc}/config.env" 2>/dev/null || true
    set +a
  fi

  echo "🔍 Polling Gmail inbox (agent=${agent}, max=${max_msgs})..."
  # Run a single cycle synchronously — no background process, no timeout kill
  _gmail_poll_cycle "${agent}" "${max_msgs}"
  echo ""
  echo "Poll cycle complete. Check: garc ingress list"
}

# ─────────────────────────────────────────────────────────────────
# logs
# ─────────────────────────────────────────────────────────────────

_daemon_logs() {
  local follow=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --follow|-f) follow=true; shift ;;
      *) shift ;;
    esac
  done

  if [[ "${follow}" == "true" ]]; then
    tail -f "${GMAIL_POLLER_LOG}" "${WORKER_LOG}" 2>/dev/null
  else
    echo "=== Gmail Poller (last 30 lines) ==="
    tail -30 "${GMAIL_POLLER_LOG}" 2>/dev/null || echo "(no log yet)"
    echo ""
    echo "=== Worker (last 30 lines) ==="
    tail -30 "${WORKER_LOG}" 2>/dev/null || echo "(no log yet)"
  fi
}

# ─────────────────────────────────────────────────────────────────
# install — OS-aware service installation (macOS launchd or Linux systemd)
# ─────────────────────────────────────────────────────────────────

_daemon_install_launchd() {
  # Backward-compatible alias — delegates to _daemon_install_service
  _daemon_install_service "$@"
}

_daemon_install_service() {
  local agent="${GARC_DEFAULT_AGENT:-main}"
  local interval=60
  local system_wide=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a)    agent="$2"; shift 2 ;;
      --interval|-i) interval="$2"; shift 2 ;;
      --system)      system_wide=true; shift ;;
      *) shift ;;
    esac
  done

  _daemon_ensure_dirs

  local os_type
  os_type="$(uname -s)"

  case "${os_type}" in
    Darwin)
      _daemon_install_launchd_plist "${agent}" "${interval}"
      ;;
    Linux)
      _daemon_install_systemd_unit "${agent}" "${interval}" "${system_wide}"
      ;;
    *)
      echo "⚠️  Unsupported OS: ${os_type}"
      echo "   Manual setup: run 'garc daemon start' from your init system."
      return 1
      ;;
  esac
}

_daemon_install_launchd_plist() {
  local agent="$1"
  local interval="$2"
  local label="com.garc.gmail-poller"
  local plist_path="${HOME}/Library/LaunchAgents/${label}.plist"
  local garc_bin="${GARC_DIR}/bin/garc"

  mkdir -p "$(dirname "${plist_path}")"

  cat > "${plist_path}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${garc_bin}</string>
        <string>daemon</string>
        <string>poll-once</string>
        <string>--agent</string>
        <string>${agent}</string>
    </array>
    <key>StartInterval</key>
    <integer>${interval}</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GARC_DIR</key>
        <string>${GARC_DIR}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${GMAIL_POLLER_LOG}</string>
    <key>StandardErrorPath</key>
    <string>${GMAIL_POLLER_LOG}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

  echo "✅ Installed launchd plist: ${plist_path}"
  echo ""
  echo "To activate:"
  echo "  launchctl load ${plist_path}"
  echo ""
  echo "To unload:"
  echo "  launchctl unload ${plist_path}"
}

_daemon_install_systemd_unit() {
  local agent="$1"
  local interval="$2"
  local system_wide="$3"
  local garc_bin="${GARC_DIR}/bin/garc"
  local unit_name="garc-gmail-poller"

  local unit_dir
  if [[ "${system_wide}" == "true" ]]; then
    unit_dir="/etc/systemd/system"
  else
    unit_dir="${HOME}/.config/systemd/user"
  fi

  mkdir -p "${unit_dir}"
  local unit_path="${unit_dir}/${unit_name}.service"
  local timer_path="${unit_dir}/${unit_name}.timer"

  # Service unit — runs one poll cycle
  cat > "${unit_path}" <<EOF
[Unit]
Description=GARC Gmail Poller (single cycle)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${garc_bin} daemon poll-once --agent ${agent}
Environment=GARC_DIR=${GARC_DIR}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
StandardOutput=append:${GMAIL_POLLER_LOG}
StandardError=append:${GMAIL_POLLER_LOG}

[Install]
WantedBy=default.target
EOF

  # Timer unit — triggers service every N seconds
  cat > "${timer_path}" <<EOF
[Unit]
Description=GARC Gmail Poller Timer

[Timer]
OnBootSec=30
OnUnitActiveSec=${interval}
Unit=${unit_name}.service

[Install]
WantedBy=timers.target
EOF

  echo "✅ Installed systemd units:"
  echo "   ${unit_path}"
  echo "   ${timer_path}"
  echo ""

  if [[ "${system_wide}" == "true" ]]; then
    echo "To activate (system-wide, requires sudo):"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now ${unit_name}.timer"
    echo ""
    echo "To disable:"
    echo "  sudo systemctl disable --now ${unit_name}.timer"
  else
    echo "To activate (user-level):"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable --now ${unit_name}.timer"
    echo "  systemctl --user status ${unit_name}.timer"
    echo ""
    echo "To disable:"
    echo "  systemctl --user disable --now ${unit_name}.timer"
    echo ""
    echo "To view logs:"
    echo "  journalctl --user -u ${unit_name}.service -f"
  fi
}
