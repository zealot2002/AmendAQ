#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${MYCS_API_PORT:-8765}"
WEB_PORT="${MYCS_WEB_PORT:-5180}"
LOG_DIR="${MYCS_DEV_LOG_DIR:-$ROOT/data/dev-logs}"

kill_pid_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local pid
  pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.3
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$f"
}

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.3
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

printf '[joyjoy] 停止开发服务...\n'
kill_pid_file "$LOG_DIR/api.pid"
kill_pid_file "$LOG_DIR/frontend.pid"
kill_port "$API_PORT"
kill_port "$WEB_PORT"
printf '[joyjoy] 已停止 (端口 %s, %s)\n' "$API_PORT" "$WEB_PORT"
