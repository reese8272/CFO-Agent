#!/usr/bin/env bash
# Gate 2 in one command, no Docker required (WSL distros without Docker Desktop integration).
#
# Stands up a throwaway Postgres + Redis + uvicorn stack, runs the Playwright browser
# suite (tests/e2e/verify_ui.py), and tears everything down. State lives in a mktemp dir.
#
# Requires: postgresql@16 + redis on PATH (brew), repo venv at .venv with requirements
# installed plus `playwright` and `playwright install chromium`, and a .env in the repo
# root (ANTHROPIC_API_KEY is used for the chat round-trip step).
#
#   bash tests/e2e/run_e2e.sh                       # full suite incl. chat (spends tokens)
#   CFO_E2E_SKIP_CHAT=1 bash tests/e2e/run_e2e.sh   # skip the LLM chat step
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PG_PORT="${CFO_E2E_PG_PORT:-5434}"
REDIS_PORT="${CFO_E2E_REDIS_PORT:-6381}"
APP_PORT="${CFO_E2E_APP_PORT:-8101}"
WORK="$(mktemp -d /tmp/cfo-e2e.XXXXXX)"
UVICORN_PID=""

teardown() {
  [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true
  redis-cli -p "$REDIS_PORT" shutdown nosave 2>/dev/null || true
  pg_ctl -D "$WORK/pgdata" stop -m immediate -s 2>/dev/null || true
  rm -rf "$WORK"
}
trap teardown EXIT

echo "== throwaway stack in $WORK (pg:$PG_PORT redis:$REDIS_PORT app:$APP_PORT) =="
initdb -D "$WORK/pgdata" -U cfo --auth=trust -E UTF8 > /dev/null
pg_ctl -D "$WORK/pgdata" -o "-p $PG_PORT -k $WORK" -l "$WORK/pg.log" start -s
psql -h "$WORK" -p "$PG_PORT" -U cfo -d postgres -q -c "CREATE DATABASE personal_cfo;"
redis-server --port "$REDIS_PORT" --daemonize yes --dir "$WORK" > /dev/null

export DATABASE_URL="postgresql+psycopg://cfo:cfo@localhost:$PG_PORT/personal_cfo"
export REDIS_URL="redis://localhost:$REDIS_PORT/0"
export ENV=development
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
VAULT_ENCRYPTION_KEY="$("$ROOT/.venv/bin/python" -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export VAULT_ENCRYPTION_KEY

cd "$ROOT"
.venv/bin/alembic upgrade head > "$WORK/alembic.log" 2>&1

.venv/bin/uvicorn main:app --port "$APP_PORT" --log-level warning \
  > "$WORK/uvicorn.log" 2>&1 &
UVICORN_PID=$!

for _ in $(seq 1 30); do
  curl -sf "http://localhost:$APP_PORT/health" > /dev/null && break
  sleep 1
done
curl -sf "http://localhost:$APP_PORT/health" > /dev/null || {
  echo "app failed to start:"; tail -20 "$WORK/uvicorn.log"; exit 1;
}

CFO_E2E_BASE="http://localhost:$APP_PORT" .venv/bin/python tests/e2e/verify_ui.py
