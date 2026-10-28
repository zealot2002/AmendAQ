#!/usr/bin/env bash
# 一键停止并重启 mycs 开发环境（后端 API + 前端 Vite）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${MYCS_API_PORT:-8765}"
WEB_PORT="${MYCS_WEB_PORT:-5173}"
LOG_DIR="${MYCS_DEV_LOG_DIR:-$ROOT/data/dev-logs}"
PID_API="$LOG_DIR/api.pid"
PID_WEB="$LOG_DIR/frontend.pid"
MODE="${1:-dev}"

export NO_PROXY="127.0.0.1,localhost,::1,${NO_PROXY:-}"
export no_proxy="127.0.0.1,localhost,::1,${no_proxy:-}"

log() {
  printf '[joyjoy] %s\n' "$*"
}

kill_pid_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local pid
    pid="$(cat "$f")"
    if kill -0 "$pid" 2>/dev/null; then
      log "停止 PID $pid ($f)"
      kill "$pid" 2>/dev/null || true
      sleep 0.5
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
  fi
}

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log "释放端口 ${port} (PID: ${pids//$'\n'/ })"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.5
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

stop_all() {
  kill_pid_file "$PID_API"
  kill_pid_file "$PID_WEB"
  kill_port "$API_PORT"
  kill_port "$WEB_PORT"
}

load_user_llm_env() {
  if [[ -f "$HOME/.zshrc" ]]; then
    set +u
    # shellcheck disable=SC1090
    source "$HOME/.zshrc" 2>/dev/null || true
    set -u
  fi
}

start_api() {
  log "同步 Python 依赖 (web)..."
  uv sync --extra web --extra dev -q
  mkdir -p "$LOG_DIR"
  load_user_llm_env
  log "启动 API :${API_PORT} → $LOG_DIR/api.log (MYCS_LLM=${MYCS_LLM:-unset})"
  (
    cd "$ROOT"
    load_user_llm_env
    export MYCS_API_HOST="${MYCS_API_HOST:-127.0.0.1}"
    export MYCS_API_PORT="$API_PORT"
    exec uv run mycs-api
  ) >>"$LOG_DIR/api.log" 2>&1 &
  echo $! >"$PID_API"
}

start_web_dev() {
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    log "安装前端依赖..."
    (cd "$ROOT/frontend" && npm install)
  fi
  log "启动 Vite :${WEB_PORT} → $LOG_DIR/frontend.log"
  (
    cd "$ROOT/frontend"
    export MYCS_WEB_PORT="$WEB_PORT"
    exec npm run dev -- --host 127.0.0.1 --port "$WEB_PORT"
  ) >>"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$PID_WEB"
}

start_web_prod() {
  log "构建前端..."
  (cd "$ROOT/frontend" && npm run build)
  log "生产模式：仅 API，静态资源由 API 挂载 frontend/dist"
  log "访问 http://127.0.0.1:${API_PORT}/"
}

wait_http() {
  local url="$1"
  local name="$2"
  local i
  for i in $(seq 1 40); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "${name} 就绪: ${url}"
      return 0
    fi
    sleep 0.25
  done
  log "警告: ${name} 未在预期时间内响应 (${url})，请查看 ${LOG_DIR}"
  return 1
}

log "=== mycs 开发环境重启 (mode=${MODE}) ==="
stop_all

case "$MODE" in
  dev)
    start_api
    start_web_dev
    wait_http "http://127.0.0.1:${API_PORT}/api/health" "API" || true
    wait_http "http://127.0.0.1:${WEB_PORT}/" "前端" || true
    echo
    log "前端: http://127.0.0.1:${WEB_PORT}/"
    log "API:  http://127.0.0.1:${API_PORT}/api/health"
    log "日志: tail -f $LOG_DIR/api.log $LOG_DIR/frontend.log"
    log "停止: scripts/stop-dev.sh"
    ;;
  prod)
    start_web_prod
    start_api
    wait_http "http://127.0.0.1:${API_PORT}/api/health" "API" || true
    echo
    log "单端口: http://127.0.0.1:${API_PORT}/"
    log "日志: tail -f $LOG_DIR/api.log"
    ;;
  *)
    echo "用法: $0 [dev|prod]" >&2
    echo "  dev  — API + Vite（默认）" >&2
    echo "  prod — npm build 后仅 API 托管 dist" >&2
    exit 1
    ;;
esac

log "=== 完成 ==="
