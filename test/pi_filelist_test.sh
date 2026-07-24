#!/bin/bash
# pi-filelist.sh — TDD test harness.
# Self-contained: creates a temp git repo with fixtures, runs scripts/pi-filelist.sh,
# and asserts on the output. Exits non-zero on any failed assertion (CI gate).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/pi-filelist.sh"

PASS=0
FAIL=0
FAILMSGS=()

assert_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -F -- "$needle" >/dev/null; then
    printf 'PASS: %s\n' "$desc"
    PASS=$((PASS + 1))
  else
    printf 'FAIL: %s (missing: %q)\n' "$desc" "$needle"
    FAIL=$((FAIL + 1))
    FAILMSGS+=("$desc: missing $needle")
  fi
}

assert_not_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -F -- "$needle" >/dev/null; then
    printf 'FAIL: %s (unexpectedly present: %q)\n' "$desc" "$needle"
    FAIL=$((FAIL + 1))
    FAILMSGS+=("$desc: unexpectedly present $needle")
  else
    printf 'PASS: %s\n' "$desc"
    PASS=$((PASS + 1))
  fi
}

assert_regex() {
  local desc="$1" haystack="$2" pattern="$3"
  if printf '%s' "$haystack" | grep -E -- "$pattern" >/dev/null; then
    printf 'PASS: %s\n' "$desc"
    PASS=$((PASS + 1))
  else
    printf 'FAIL: %s (no match for: %s)\n' "$desc" "$pattern"
    FAIL=$((FAIL + 1))
    FAILMSGS+=("$desc: no match /$pattern/")
  fi
}

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    printf 'PASS: %s\n' "$desc"
    PASS=$((PASS + 1))
  else
    printf 'FAIL: %s (expected=%q actual=%q)\n' "$desc" "$expected" "$actual"
    FAIL=$((FAIL + 1))
    FAILMSGS+=("$desc: expected $expected got $actual")
  fi
}

# shellcheck disable=SC2329  # cleanup is invoked via the EXIT trap below
cleanup() {
  [ -n "${TMPDIR_FIXTURE:-}" ] && rm -rf "$TMPDIR_FIXTURE"
}
trap cleanup EXIT

TMPDIR_FIXTURE="$(mktemp -d)"
git -C "$TMPDIR_FIXTURE" init -q
git -C "$TMPDIR_FIXTURE" config commit.gpgsign false
git -C "$TMPDIR_FIXTURE" config user.email "test@pi.local"
git -C "$TMPDIR_FIXTURE" config user.name "PI Test"
git -C "$TMPDIR_FIXTURE" config core.quotepath false

mkdir -p "$TMPDIR_FIXTURE/src" "$TMPDIR_FIXTURE/node_modules" \
  "$TMPDIR_FIXTURE/vendor" "$TMPDIR_FIXTURE/dist" \
  "$TMPDIR_FIXTURE/nested" "$TMPDIR_FIXTURE/dir.key" \
  "$TMPDIR_FIXTURE/docs"

# Normal source files that should survive filtering.
printf 'print("a")\n' > "$TMPDIR_FIXTURE/src/a.py"
printf 'print("b")\n' > "$TMPDIR_FIXTURE/src/b.py"
printf 'print("c")\n' > "$TMPDIR_FIXTURE/src/c.py"

# Denylist fixtures — these ARE tracked (force-added) so git ls-files emits them
# and the denylist filter must remove them. Proves the filter does the work.
printf 'SECRET=1\n' > "$TMPDIR_FIXTURE/.env"
printf 'KEY\n' > "$TMPDIR_FIXTURE/deploy.key"
printf 'module.exports = 1\n' > "$TMPDIR_FIXTURE/node_modules/x.js"

# A genuinely gitignored file — added to .gitignore, left UNtracked. Exercises the
# distinct "ls-files already excludes gitignored files" path.
printf 'ignored\n' > "$TMPDIR_FIXTURE/ignored.log"
printf 'ignored.log\n' > "$TMPDIR_FIXTURE/.gitignore"

# Additional denylist, boundary, encoding, and duplicate-basename fixtures.
printf 'local=1\n' > "$TMPDIR_FIXTURE/.env.local"
printf 'ssh pub\n' > "$TMPDIR_FIXTURE/id_rsa.pub"
printf 'minified\n' > "$TMPDIR_FIXTURE/src/app.min.js"
printf '{}\n'      > "$TMPDIR_FIXTURE/package-lock.json"
printf 'pkg\n'     > "$TMPDIR_FIXTURE/vendor/pkg.js"
printf 'bundle\n'  > "$TMPDIR_FIXTURE/dist/out.js"
printf 'yaml\n'    > "$TMPDIR_FIXTURE/nested/secret.yaml"
printf 'creds\n'   > "$TMPDIR_FIXTURE/credentials.yml"
printf 'nested\n'  > "$TMPDIR_FIXTURE/dir.key/allowed.txt"
printf 'unicode\n' > "$TMPDIR_FIXTURE/src/文件.txt"
printf 'spaces\n'  > "$TMPDIR_FIXTURE/src/file with spaces.txt"
printf 'UPPER\n'   > "$TMPDIR_FIXTURE/src/DEPLOY.KEY"
printf 'foo src\n' > "$TMPDIR_FIXTURE/src/foo.txt"
printf 'foo docs\n' > "$TMPDIR_FIXTURE/docs/foo.txt"

# Nested / modern denylist fixtures (K3 dogfood: basename match + dir-depth + tfstate + modern keys).
mkdir -p "$TMPDIR_FIXTURE/backend" "$TMPDIR_FIXTURE/packages/foo/node_modules" "$TMPDIR_FIXTURE/infra"
printf 'SECRET=deep\n' > "$TMPDIR_FIXTURE/backend/.env"
printf 'machine h login u password p\n' > "$TMPDIR_FIXTURE/.netrc"
printf 'state\n' > "$TMPDIR_FIXTURE/infra/main.tfstate"
printf 'ed\n' > "$TMPDIR_FIXTURE/id_ed25519"
printf 'nested vendor\n' > "$TMPDIR_FIXTURE/packages/foo/node_modules/index.js"

git -C "$TMPDIR_FIXTURE" add -A
git -C "$TMPDIR_FIXTURE" add -f "$TMPDIR_FIXTURE/.env" "$TMPDIR_FIXTURE/deploy.key" "$TMPDIR_FIXTURE/node_modules/x.js" 2>/dev/null || true
git -C "$TMPDIR_FIXTURE" commit -q -m "fixtures"
# Confirm the gitignored file is NOT tracked (sanity for the test author).
if git -C "$TMPDIR_FIXTURE" ls-files -- ignored.log | grep -q .; then
  printf 'FAIL: ignored.log was tracked — fixture is wrong, fix the test\n' >&2
  exit 1
fi

printf '\n=== Run 1: full repo, default cap ===\n'
OUT1="$(bash "$SCRIPT" "$TMPDIR_FIXTURE")"
printf '%s\n' "$OUT1"

assert_not_contains "excludes .env"          "$OUT1" ".env"
assert_not_contains "excludes *.key"         "$OUT1" "deploy.key"
assert_not_contains "excludes node_modules/" "$OUT1" "node_modules/x.js"
assert_not_contains "excludes gitignored"   "$OUT1" "ignored.log"
assert_contains     "includes src/a.py"      "$OUT1" "src/a.py"
assert_contains     "includes src/b.py"      "$OUT1" "src/b.py"
assert_contains     "includes src/c.py"      "$OUT1" "src/c.py"
assert_regex        "has file-count summary" "$OUT1" "^# [0-9]+ files$"
assert_not_contains "denies nested backend/.env (basename match)"  "$OUT1" "backend/.env"
assert_not_contains "denies .netrc credential file"                "$OUT1" ".netrc"
assert_not_contains "denies *.tfstate (plaintext secrets)"         "$OUT1" "main.tfstate"
assert_not_contains "denies modern id_ed25519 private key"         "$OUT1" "id_ed25519"
assert_not_contains "denies nested node_modules (depth form)"      "$OUT1" "packages/foo/node_modules/index.js"

printf '\n=== Run 2: cap=PI_MAXFILES=2 ===\n'
OUT2="$(PI_MAXFILES=2 bash "$SCRIPT" "$TMPDIR_FIXTURE")"
printf '%s\n' "$OUT2"

# Path lines = non-#-prefixed lines.
PATHS2="$(printf '%s\n' "$OUT2" | grep -v -E '^#')"
PATH_COUNT2="$(printf '%s\n' "$PATHS2" | grep -c . || true)"
assert_eq "caps to exactly 2 paths" "2" "$PATH_COUNT2"
assert_regex "has dropped footer mentioning cap" "$OUT2" "^# dropped: .*cap 2"

printf '\n=== Run 3: non-git repo fails closed ===\n'
TMPDIR_NONGIT="$(mktemp -d)"
NON_RC=0
# shellcheck disable=SC2086  # capture stderr into the log line below
NON_OUT="$(bash "$SCRIPT" "$TMPDIR_NONGIT" 2>&1)" || NON_RC=$?
printf '%s\n' "$NON_OUT" | head -1 >&2
rm -rf "$TMPDIR_NONGIT"
if [ "$NON_RC" -ne 0 ]; then
  printf 'PASS: non-git repo exits non-zero (rc=%s)\n' "$NON_RC"
  PASS=$((PASS + 1))
else
  printf 'FAIL: non-git repo exited 0 (expected non-zero)\n'
  FAIL=$((FAIL + 1))
  FAILMSGS+=("non-git repo should fail closed")
fi

printf '\n=== Run 4: empty subpath matches nothing ===\n'
OUT4="$(bash "$SCRIPT" "$TMPDIR_FIXTURE" "nonexistent-subdir")"
printf '%s\n' "$OUT4"
assert_eq "empty subpath → 0 paths" "0" "$(printf '%s\n' "$OUT4" | grep -v -E '^#' | grep -c . || true)"
assert_contains "empty subpath → summary line" "$OUT4" "# 0 files"

printf '\n=== Run 5: denylist edge cases ===\n'
OUT5="$(bash "$SCRIPT" "$TMPDIR_FIXTURE")"
printf '%s\n' "$OUT5"
assert_not_contains "denies .env.local via .env*"        "$OUT5" ".env.local"
assert_not_contains "denies id_rsa.pub via id_rsa*"      "$OUT5" "id_rsa.pub"
assert_not_contains "denies *.min.js"                    "$OUT5" "src/app.min.js"
assert_not_contains "denies package-lock.json"           "$OUT5" "package-lock.json"
assert_not_contains "denies vendor/*"                    "$OUT5" "vendor/pkg.js"
assert_not_contains "denies dist/*"                      "$OUT5" "dist/out.js"
assert_not_contains "denies paths containing secret"     "$OUT5" "nested/secret.yaml"
assert_not_contains "denies credentials substring"       "$OUT5" "credentials.yml"
assert_contains     "dir.key/allowed.txt allowed (basename-only glob not applied)" "$OUT5" "dir.key/allowed.txt"
assert_contains     "includes unicode filename"          "$OUT5" "src/文件.txt"
assert_contains     "includes filename with spaces"      "$OUT5" "src/file with spaces.txt"
assert_not_contains "uppercase .KEY denied (case-insensitive denylist)" "$OUT5" "src/DEPLOY.KEY"

printf '\n=== Run 6: cap boundaries ===\n'
ALLOWED_COUNT="$(printf '%s\n' "$OUT5" | grep -v -E '^#' | grep -c . || true)"
OUT6_FULL="$(PI_MAXFILES="$ALLOWED_COUNT" bash "$SCRIPT" "$TMPDIR_FIXTURE")"
assert_eq "cap equal to count returns all paths" "$ALLOWED_COUNT" "$(printf '%s\n' "$OUT6_FULL" | grep -v -E '^#' | grep -c . || true)"
assert_not_contains "no dropped footer when cap == count" "$OUT6_FULL" "# dropped:"
OUT6_MINUS="$(PI_MAXFILES=$((ALLOWED_COUNT - 1)) bash "$SCRIPT" "$TMPDIR_FIXTURE")"
assert_eq "cap count-1 returns count-1 paths" "$((ALLOWED_COUNT - 1))" "$(printf '%s\n' "$OUT6_MINUS" | grep -v -E '^#' | grep -c . || true)"
assert_contains "dropped footer when cap < count" "$OUT6_MINUS" "# dropped:"
OUT6_ZERO="$(PI_MAXFILES=0 bash "$SCRIPT" "$TMPDIR_FIXTURE")"
assert_eq "cap 0 returns 0 paths" "0" "$(printf '%s\n' "$OUT6_ZERO" | grep -v -E '^#' | grep -c . || true)"
assert_contains "dropped footer when cap 0" "$OUT6_ZERO" "# dropped:"

printf '\n=== Run 7: empty tracked file set ===\n'
TMPDIR_EMPTY="$(mktemp -d)"
git -C "$TMPDIR_EMPTY" init -q
git -C "$TMPDIR_EMPTY" config commit.gpgsign false
git -C "$TMPDIR_EMPTY" config user.email "test@pi.local"
git -C "$TMPDIR_EMPTY" config user.name "PI Test"
git -C "$TMPDIR_EMPTY" commit -q --allow-empty -m "empty"
OUT7="$(bash "$SCRIPT" "$TMPDIR_EMPTY")"
printf '%s\n' "$OUT7"
assert_eq "empty repo emits 0 path lines" "0" "$(printf '%s\n' "$OUT7" | grep -v -E '^#' | grep -c . || true)"
assert_contains "empty repo summary is # 0 files" "$OUT7" "# 0 files"
rm -rf "$TMPDIR_EMPTY"

printf '\n=== Run 8: absent vs empty subpath ===\n'
OUT8_NOARG="$(bash "$SCRIPT" "$TMPDIR_FIXTURE")"
OUT8_EMPTY="$(bash "$SCRIPT" "$TMPDIR_FIXTURE" "")"
assert_eq "empty subpath string matches no subpath arg" "$OUT8_NOARG" "$OUT8_EMPTY"

printf '\n=== Run 9: subpath filtering variants ===\n'
OUT9_SRC="$(bash "$SCRIPT" "$TMPDIR_FIXTURE" "src")"
printf '%s\n' "$OUT9_SRC"
assert_contains "subpath src includes src/a.py" "$OUT9_SRC" "src/a.py"
assert_not_contains "subpath src excludes repo root file" "$OUT9_SRC" ".gitignore"
OUT9_SRCSLASH="$(bash "$SCRIPT" "$TMPDIR_FIXTURE" "src/")"
assert_eq "subpath src/ equals src" "$OUT9_SRC" "$OUT9_SRCSLASH"
OUT9_FILE="$(bash "$SCRIPT" "$TMPDIR_FIXTURE" "src/a.py")"
printf '%s\n' "$OUT9_FILE"
assert_eq "subpath file returns exactly one path" "1" "$(printf '%s\n' "$OUT9_FILE" | grep -v -E '^#' | grep -c . || true)"
assert_contains "subpath file returns the file" "$OUT9_FILE" "src/a.py"

printf '\n=== Run 10: duplicate basenames in different dirs ===\n'
OUT10="$(bash "$SCRIPT" "$TMPDIR_FIXTURE")"
printf '%s\n' "$OUT10"
assert_contains "includes src/foo.txt"  "$OUT10" "src/foo.txt"
assert_contains "includes docs/foo.txt" "$OUT10" "docs/foo.txt"

printf '\n=== Run 11: malformed inputs fail cleanly ===\n'
RC_USAGE=0
# shellcheck disable=SC2086
OUT_USAGE="$(bash "$SCRIPT" 2>&1)" || RC_USAGE=$?
assert_eq "missing repo arg exits 2" "2" "$RC_USAGE"
TMPDIR_NOENT="/does/not/exist/pi-reviewer-$$"
RC_NOENT=0
OUT_NOENT="$(bash "$SCRIPT" "$TMPDIR_NOENT" 2>&1)" || RC_NOENT=$?
if [ "$RC_NOENT" -ne 0 ]; then
  printf 'PASS: non-existent repo exits non-zero (rc=%s)\n' "$RC_NOENT"
  PASS=$((PASS + 1))
else
  printf 'FAIL: non-existent repo exited 0\n'
  FAIL=$((FAIL + 1))
  FAILMSGS+=("non-existent repo should fail closed")
fi
TMPDIR_FILE="$(mktemp)"
printf 'not a dir\n' > "$TMPDIR_FILE"
RC_FILE=0
OUT_FILE="$(bash "$SCRIPT" "$TMPDIR_FILE" 2>&1)" || RC_FILE=$?
if [ "$RC_FILE" -ne 0 ]; then
  printf 'PASS: file as repo exits non-zero (rc=%s)\n' "$RC_FILE"
  PASS=$((PASS + 1))
else
  printf 'FAIL: file as repo exited 0\n'
  FAIL=$((FAIL + 1))
  FAILMSGS+=("file as repo should fail closed")
fi
rm -f "$TMPDIR_FILE"

printf '\n=== Run 12: concurrent runs are consistent ===\n'
TMPDIR_CONC="$(mktemp -d)"
for _ in a b c d; do
  bash "$SCRIPT" "$TMPDIR_FIXTURE" > "$TMPDIR_CONC/$_" &
done
wait
assert_eq "concurrent run a matches b" "$(cat "$TMPDIR_CONC/a")" "$(cat "$TMPDIR_CONC/b")"
assert_eq "concurrent run a matches c" "$(cat "$TMPDIR_CONC/a")" "$(cat "$TMPDIR_CONC/c")"
assert_eq "concurrent run a matches d" "$(cat "$TMPDIR_CONC/a")" "$(cat "$TMPDIR_CONC/d")"
rm -rf "$TMPDIR_CONC"

printf '\n=========================================\n'
printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
if [ "$FAIL" -ne 0 ]; then
  printf 'Failed assertions:\n' >&2
  for m in "${FAILMSGS[@]}"; do printf '  - %s\n' "$m" >&2; done
  exit 1
fi
exit 0