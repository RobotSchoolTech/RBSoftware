#!/usr/bin/env bash
# smoke.sh — smoke test post-deploy del LMS
#
# Uso:
#   LMS_EMAIL=admin@example.com LMS_PASSWORD=secret ./scripts/smoke.sh [BASE_URL]
#
# Si BASE_URL no se pasa, usa https://lms.miel-robotschool.com
# Las credenciales se leen de variables de entorno (nunca hardcoded).
# Requiere: curl, jq

set -euo pipefail

BASE="${1:-https://lms.miel-robotschool.com}"
EMAIL="${LMS_EMAIL:?Variable LMS_EMAIL no definida}"
PASSWORD="${LMS_PASSWORD:?Variable LMS_PASSWORD no definida}"

COOKIE_JAR=$(mktemp)
BODY_TMP=$(mktemp)
PASS=0
FAIL=0

cleanup() { rm -f "$COOKIE_JAR" "$BODY_TMP"; }
trap cleanup EXIT

ok() {
    echo "  ✓ $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  ✗ $1  — HTTP $2"
    FAIL=$((FAIL + 1))
}

# http_check <label> <expected_code> <method> <url> [curl_args...]
http_check() {
    local label="$1" expected="$2" method="$3" url="$4"
    shift 4
    local status
    status=$(curl -sS -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
        -o /dev/null -w '%{http_code}' \
        -X "$method" "$@" "$url")
    if [[ "$status" == "$expected" ]]; then ok "$label"; else fail "$label" "$status"; fi
}

# http_fetch <label> <expected_code> <method> <url> [curl_args...]
# Igual que http_check pero guarda el body en $BODY_TMP para lectura posterior.
http_fetch() {
    local label="$1" expected="$2" method="$3" url="$4"
    shift 4
    local status
    status=$(curl -sS -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
        -o "$BODY_TMP" -w '%{http_code}' \
        -X "$method" "$@" "$url")
    if [[ "$status" == "$expected" ]]; then ok "$label"; else fail "$label" "$status"; fi
}

echo "=== LMS Smoke Test — $BASE ==="
echo ""

# ── 1. Health ────────────────────────────────────────────────────────────────
echo "[ Infraestructura ]"
http_check "GET /health" "200" "GET" "$BASE/api/health"

# ── 2. Autenticación ─────────────────────────────────────────────────────────
echo ""
echo "[ Autenticación ]"
http_check "POST /auth/login" "200" "POST" "$BASE/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
http_check "GET /auth/me" "200" "GET" "$BASE/api/auth/me"

# ── 3. Datos académicos ───────────────────────────────────────────────────────
echo ""
echo "[ Datos académicos ]"
http_check "GET /academic/schools"  "200" "GET" "$BASE/api/academic/schools"
http_check "GET /academic/courses"  "200" "GET" "$BASE/api/academic/courses"

# ── 4. Usuarios ───────────────────────────────────────────────────────────────
echo ""
echo "[ Usuarios ]"
http_check "GET /auth/users" "200" "GET" "$BASE/api/auth/users"

# ── 5. Training ───────────────────────────────────────────────────────────────
echo ""
echo "[ Training ]"
http_check "GET /training/programs" "200" "GET" "$BASE/api/training/programs"

# ── 6. Repositorio ────────────────────────────────────────────────────────────
echo ""
echo "[ Repositorio ]"
http_fetch "GET /repository/folders" "200" "GET" "$BASE/api/repository/folders"
FOLDERS_BODY=$(cat "$BODY_TMP")
http_check "GET /repository/share-options" "200" "GET" "$BASE/api/repository/share-options"

# ── 7. Crear y borrar share (regresión del bug original) ─────────────────────
echo ""
echo "[ Share create/delete — bug regression ]"
FOLDER_ID=$(echo "$FOLDERS_BODY" | jq -r 'first | .public_id // empty' 2>/dev/null || true)

http_fetch "" "200" "GET" "$BASE/api/academic/schools" 2>/dev/null || true
SCHOOL_ID=$(cat "$BODY_TMP" | jq -r 'first | .public_id // empty' 2>/dev/null || true)

if [[ -z "$FOLDER_ID" || -z "$SCHOOL_ID" ]]; then
    echo "  ! share create/delete omitido — sin carpetas o colegios en la BD"
else
    http_fetch "POST /repository/folders/{id}/shares" "201" "POST" \
        "$BASE/api/repository/folders/$FOLDER_ID/shares" \
        -H "Content-Type: application/json" \
        -d "{\"scope_type\":\"school\",\"scope_id\":\"$SCHOOL_ID\"}"
    SHARE_ID=$(cat "$BODY_TMP" | jq -r '.id // empty' 2>/dev/null || true)
    if [[ -n "$SHARE_ID" ]]; then
        http_check "DELETE /repository/folders/{id}/shares/{id}" "204" "DELETE" \
            "$BASE/api/repository/folders/$FOLDER_ID/shares/$SHARE_ID"
    else
        echo "  ! delete share omitido — no se obtuvo ID del share creado"
    fi
fi

# ── 8. Logout ─────────────────────────────────────────────────────────────────
echo ""
echo "[ Cierre ]"
http_check "POST /auth/logout" "204" "POST" "$BASE/api/auth/logout"

# ── Resultado ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Resultado: $PASS ok  •  $FAIL fallaron ==="

if [[ "$FAIL" -gt 0 ]]; then
    echo "SMOKE TEST FALLÓ — revisar logs antes de dar el deploy por bueno."
    exit 1
else
    echo "Todo verde."
fi
