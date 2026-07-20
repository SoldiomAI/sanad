#!/usr/bin/env bash
# CI gate for SANAD editorial invariants. Exit non-zero on any violation.
# Usage: bash checks/copy-guard.sh [path]   (default: current directory)
# Runs on app source. prompts/ is excluded — it quotes the forbidden
# phrases on purpose. To exempt a single line, append: guard-allow
set -uo pipefail
ROOT="${1:-.}"
FAIL=0

hit () {  # hit <label> <extended-regex>
  local label="$1" pat="$2" out
  out=$(grep -rInE \
        --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next \
        --exclude-dir=checks --exclude-dir=dist --exclude-dir=build \
        --exclude-dir=prompts \
        --include='*.js'  --include='*.jsx' --include='*.ts' --include='*.tsx' \
        --include='*.html' --include='*.md' --include='*.json' --include='*.py' \
        -e "$pat" "$ROOT" 2>/dev/null | grep -v "guard-allow")
  if [ -n "$out" ]; then
    printf '\n❌ %s\n%s\n' "$label" "$out"
    FAIL=1
  fi
}

hit "forbidden term «الأركان الخمسة» — use «خمسة معايير من علم الحديث»" \
    'الأركان الخمسة'

hit "comparison language — SANAD speaks only about itself" \
    'غيرنا|على عكس|أفضل من|بخلاف المواقع|بخلاف المنصات|unlike others|better than other'

hit "hardcoded isnad score in copy — read it from the live item" \
    '"[1-7]/7"|٢ من ٧|٦ من ٧'

echo
if [ "$FAIL" -eq 0 ]; then echo "✅ copy-guard clean"; else echo "⛔ copy-guard failed"; fi
exit "$FAIL"
