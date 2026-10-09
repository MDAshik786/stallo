#!/usr/bin/env bash
# Smoke-test a deployed Stallo stack from the outside.
#
#   ./scripts/smoke.sh                          # production (defaults below)
#   ./scripts/smoke.sh http://localhost:8000 http://localhost:3000 <seller-id>

set -uo pipefail

API=${1:-https://stallo-pnd4.onrender.com}
WEB=${2:-https://stallo-nu.vercel.app}
SELLER=${3:-01a06aa0-dae5-73f3-bf64-12b6ac57927e}

pass=0; fail=0
check() { # name expected actual
  if [ "$2" = "$3" ]; then printf '  \033[32m✓\033[0m %-42s %s\n' "$1" "$3"; pass=$((pass+1))
  else printf '  \033[31m✗\033[0m %-42s got %s, want %s\n' "$1" "$3" "$2"; fail=$((fail+1)); fi
}
code() { curl -s -o /dev/null -w "%{http_code}" --max-time 90 "$@"; }

echo "API $API"
echo "WEB $WEB"
echo
echo "── availability ─────────────────────────────────"
printf '  waking services (free tier may sleep)…\n'
curl -s -o /dev/null --max-time 90 "$API/health"
check "api /health"                 200 "$(code $API/health)"
check "web /products"               200 "$(code $WEB/products)"

echo
echo "── auth stub ────────────────────────────────────"
check "no header rejected"          401 "$(code $API/products)"
check "malformed uuid rejected"     400 "$(code -H 'X-Seller-Id: nope' $API/products)"
check "valid seller accepted"       200 "$(code -H "X-Seller-Id: $SELLER" $API/products)"

echo
echo "── tenant isolation ─────────────────────────────"
OTHER=00000000-0000-7000-8000-000000000000
n=$(curl -s --max-time 60 -H "X-Seller-Id: $OTHER" "$API/products" | tr -d '[:space:]')
check "unknown seller sees nothing" "[]" "$n"

echo
echo "── cors ─────────────────────────────────────────"
allowed=$(curl -s -o /dev/null -D - --max-time 60 -X OPTIONS "$API/products" \
  -H "Origin: $WEB" -H "Access-Control-Request-Method: GET" \
  | grep -i "^access-control-allow-origin:" | tr -d '\r' | awk '{print $2}')
check "web origin allowed"          "$WEB" "$allowed"
evil=$(curl -s -o /dev/null -D - --max-time 60 -X OPTIONS "$API/products" \
  -H "Origin: https://evil.example.com" -H "Access-Control-Request-Method: GET" \
  | grep -ci "^access-control-allow-origin:" | tr -d '\r')
check "evil origin blocked"         "0" "$evil"

echo
echo "── agent ────────────────────────────────────────"
check "audit log reachable"        200 "$(code -H "X-Seller-Id: $SELLER" $API/agent/actions)"
check "audit log needs auth"       401 "$(code $API/agent/actions)"
run=$(curl -s --max-time 150 -X POST "$API/agent/runs" \
  -H "X-Seller-Id: $SELLER" -H "Content-Type: application/json" \
  -d '{"utterance":"add a rose bouquet for 899"}')
printf '%s' "$run" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('  could not parse agent response'); raise SystemExit
print(f\"  status: {d.get('status')}\")
for key in ('reply', 'error'):
    if d.get(key):
        print(f'    {d[key][:88]}')
"

echo
echo "── production hardening ─────────────────────────"
check "/docs hidden"                404 "$(code $API/docs)"
check "/openapi.json hidden"        404 "$(code $API/openapi.json)"

echo
echo "── data ─────────────────────────────────────────"
curl -s --max-time 60 -H "X-Seller-Id: $SELLER" "$API/products" \
  | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('  could not parse response'); raise SystemExit
print(f'  {len(d)} product(s)')
for p in d:
    print(f\"    {p['name']:22} ₹{p['price_paise']/100:>8.2f}  {p['status']}\")
"

echo
echo "─────────────────────────────────────────────────"
printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
