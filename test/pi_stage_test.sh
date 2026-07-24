#!/bin/bash
# pi-stage.sh — TDD harness. Builds a temp git repo, stages a MASKED snapshot, and asserts the
# security invariants: symlinks never staged, no symlink reaches the snapshot (TOCTOU backstop),
# maskable secrets redacted in the copy, binary/NUL content omitted, source tree left untouched.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="${REPO_ROOT}/scripts/pi-stage.sh"

PASS=0
FAIL=0
pass() { printf 'PASS: %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf 'FAIL: %s\n' "$1"; FAIL=$((FAIL + 1)); }

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP" "${SNAP_CREATED:-}"; }
trap cleanup EXIT

git -C "$TMP" init -q
git -C "$TMP" config commit.gpgsign false

# A normal source file with a maskable (synthetic) AWS key.
printf 'aws_key = "AKIAIOSFODNN7EXAMPLE"\n' > "$TMP/app.py"
# A symlink whose target is OUTSIDE the repo — must never be staged/dereferenced.
ln -s /etc/hostname "$TMP/link_out"
# A ".txt" (reviewable extension) that is actually binary (NUL bytes) with an unmatched secret.
printf 'HEAD\x00\x00 UNMATCHED_TOKEN_zzz999 \x00 tail' > "$TMP/notes.txt"
git -C "$TMP" add -A
git -C "$TMP" -c user.email=t@t.test -c user.name=tester commit -qm init

stage="$("$STAGE" "$TMP")"
SNAP_CREATED="$(dirname "$stage")"   # per-repo snapshot dir to clean up (default lives OUTSIDE the repo)

[ -d "$stage" ] && pass "staging created a snapshot dir" || fail "no snapshot dir"
case "$stage" in */pireview/*) pass "default snapshot is OUT of the repo (…/pireview/…)" ;; *) fail "default snapshot not under pireview: $stage" ;; esac
case "$stage" in "$TMP"/*) fail "snapshot leaked INTO the repo tree" ;; *) pass "snapshot path is outside the repo (no home/username leak)" ;; esac

# PI_SNAP_ROOT relocates the snapshot root (opt-in in-repo / audit mode).
stage2="$(PI_SNAP_ROOT="$TMP/relocated" "$STAGE" "$TMP")"
case "$stage2" in "$TMP/relocated/"*) pass "PI_SNAP_ROOT override honored" ;; *) fail "PI_SNAP_ROOT ignored: $stage2" ;; esac
[ ! -e "$stage/link_out" ] && pass "outside-pointing symlink not staged" || fail "symlink was staged"
[ -z "$(find "$stage" -type l)" ] && pass "snapshot contains no symlinks (TOCTOU backstop)" || fail "snapshot has a symlink"

if [ -f "$stage/app.py" ] && ! grep -q 'AKIAIOSFODNN7EXAMPLE' "$stage/app.py"; then
  pass "maskable AWS key redacted in staged copy"
else
  fail "AWS key leaked raw in staged copy"
fi

if [ -f "$stage/notes.txt" ] && grep -q 'omitted from review' "$stage/notes.txt" && ! grep -q 'UNMATCHED_TOKEN' "$stage/notes.txt"; then
  pass "binary/NUL content omitted from staged copy"
else
  fail "binary/NUL content not omitted from staged copy"
fi

if grep -q 'AKIAIOSFODNN7EXAMPLE' "$TMP/app.py"; then
  pass "source tree left unmodified (raw key still in original)"
else
  fail "source tree was modified"
fi

printf '\npi-stage: PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
