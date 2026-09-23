#!/usr/bin/env bash
# apply_schema.sh — supabase/schema.sql 을 적용한다 (DATA_CONTRACT §13).
# 승인 gate: 이 스크립트는 사람이 승인한 뒤에만 실행한다. 멱등이므로 재실행해도 안전하다.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi
: "${SUPABASE_DB_URL:?SUPABASE_DB_URL 이 비어 있다 — .env.local 을 채운 뒤 다시 실행하라}"

SCHEMA="$ROOT/supabase/schema.sql"
[ -f "$SCHEMA" ] || { echo "schema.sql 없음: $SCHEMA" >&2; exit 1; }

if command -v psql >/dev/null 2>&1; then
  echo "[apply_schema] psql 로 적용"
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA"
elif command -v supabase >/dev/null 2>&1; then
  echo "[apply_schema] supabase CLI 로 적용"
  mkdir -p "$ROOT/supabase/migrations"
  cp "$SCHEMA" "$ROOT/supabase/migrations/00000000000000_zerohr_schema.sql"
  supabase db push --db-url "$SUPABASE_DB_URL"
else
  cat >&2 <<'MSG'
psql 도 supabase CLI 도 없다. 수동 적용:
  1) https://supabase.com/dashboard → 프로젝트 → SQL Editor
  2) supabase/schema.sql 전체를 붙여넣고 Run
  3) 완료 후 `python3 supabase/seed.py --root . && python3 supabase/verify.py --root .`
MSG
  exit 2
fi
echo "[apply_schema] 완료"
