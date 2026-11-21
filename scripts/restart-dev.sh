#!/usr/bin/env bash
# 一键停止并重启 mycs 开发环境（后端 API + 前端 Vite）
# 默认监听 0.0.0.0，同一局域网同事可通过本机 IP 访问；仅本机请设 MYCS_BIND_HOST=127.0.0.1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${MYCS_API_PORT:-8765}"
WEB_PORT="${MYCS_WEB_PORT:-5180}"
LOG_DIR="${MYCS_DEV_LOG_DIR:-$ROOT/data/dev-logs}"
PID_API="$LOG_DIR/api.pid"
PID_WEB="$LOG_DIR/frontend.pid"
MODE="${1:-dev}"

export NO_PROXY="127.0.0.1,localhost,::1,${NO_PROXY:-}"
export no_proxy="127.0.0.1,localhost,::1,${no_proxy:-}"

log() {
  printf '[joyjoy] %s\n' "$*"
}

lan_ipv4() {
  local iface ip
  for iface in en0 en1 bridge0; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [[ -n "$ip" ]]; then
      printf '%s' "$ip"
      return 0
    fi
  done
  return 1
}

resolve_bind_host() {
  printf '%s' "${MYCS_BIND_HOST:-${MYCS_API_HOST:-0.0.0.0}}"
}

print_access_urls() {
  local port="$1"
  local label="${2:-页面}"
  log "本机 ${label}: http://127.0.0.1:${port}/"
  if [[ "$BIND_HOST" == "127.0.0.1" ]]; then
    log "当前仅本机可访问（MYCS_BIND_HOST=127.0.0.1）"
    return 0
  fi
  local ip
  if ip="$(lan_ipv4)"; then
    log "同事 ${label}（同一 WiFi/局域网）: http://${ip}:${port}/"
  else
    log "未检测到局域网 IPv4；请在本机运行: ipconfig getifaddr en0"
    log "同事访问: http://<你的局域网IP>:${port}/"
  fi
  log "若连不上：macOS 防火墙需放行 Python/终端入站；问答走 LLM 需本机 .env 已配置 Key"
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

# 项目 .env 优先于 ~/.zshrc 里的旧 OPENAI_MODEL=Qwen 等
load_project_env() {
  if [[ -f "$ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
    log "已加载 $ROOT/.env（覆盖 shell 中的 MYCS_LLM / GLM_*）"
  else
    if [[ -n "${GLM_API_KEY:-}${ZHIPUAI_API_KEY:-}" ]]; then
      export MYCS_LLM=glm
      export GLM_MODEL="${GLM_MODEL:-glm-4-flash-250414}"
      log "未发现 .env，但 shell 中有智谱 Key → 强制 MYCS_LLM=glm GLM_MODEL=$GLM_MODEL"
    else
      log "未发现 $ROOT/.env，可 cp .env.example .env 并填写 GLM_API_KEY"
    fi
  fi
}

start_api() {
  log "同步 Python 依赖 (web)..."
  uv sync --extra web --extra dev -q
  mkdir -p "$LOG_DIR"
  load_user_llm_env
  load_project_env
  BIND_HOST="$(resolve_bind_host)"
  log "启动 API ${BIND_HOST}:${API_PORT} → $LOG_DIR/api.log (MYCS_LLM=${MYCS_LLM:-unset} GLM_MODEL=${GLM_MODEL:-unset} OLLAMA_MODEL=${OLLAMA_MODEL:-unset})"
  (
    cd "$ROOT"
    load_user_llm_env
    load_project_env
    export MYCS_API_HOST="${MYCS_API_HOST:-$BIND_HOST}"
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
  BIND_HOST="$(resolve_bind_host)"
  log "启动 Vite ${BIND_HOST}:${WEB_PORT} → $LOG_DIR/frontend.log"
  (
    cd "$ROOT/frontend"
    export MYCS_WEB_PORT="$WEB_PORT"
    export MYCS_API_PORT="$API_PORT"
    exec npm run dev -- --host "$BIND_HOST" --port "$WEB_PORT"
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
load_user_llm_env
load_project_env
BIND_HOST="$(resolve_bind_host)"

case "$MODE" in
  dev)
    start_api
    start_web_dev
    wait_http "http://127.0.0.1:${API_PORT}/api/health" "API" || true
    wait_http "http://127.0.0.1:${WEB_PORT}/" "前端" || true
    echo
    print_access_urls "$WEB_PORT" "前端（请把该地址发给同事）"
    log "API 健康检查: http://127.0.0.1:${API_PORT}/api/health"
    log "日志: tail -f $LOG_DIR/api.log $LOG_DIR/frontend.log"
    log "停止: scripts/stop-dev.sh"
    ;;
  prod)
    start_web_prod
    start_api
    wait_http "http://127.0.0.1:${API_PORT}/api/health" "API" || true
    echo
    print_access_urls "$API_PORT" "入口（单端口，请把该地址发给同事）"
    log "日志: tail -f $LOG_DIR/api.log"
    ;;
  *)
    echo "用法: $0 [dev|prod]" >&2
    echo "  dev  — API + Vite（默认，同事访问 Vite 端口）" >&2
    echo "  prod — npm build 后仅 API 托管 dist（同事访问 API 端口）" >&2
    echo "  仅本机在 .env 设 MYCS_BIND_HOST=127.0.0.1" >&2
    exit 1
    ;;
esac

log "=== 完成 ==="
