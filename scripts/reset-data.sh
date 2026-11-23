#!/usr/bin/env bash
# 清空运行时 mock / 测试数据（空库 + 无 demo 自动灌入）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec uv run amendaq reset-data "$@"
