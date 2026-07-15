#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH="${ROOT_DIR}/scripts/opencode-watch.sh"
TEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/opencode-watch-test.XXXXXX")"

# shellcheck disable=SC2329  # invoked indirectly by the EXIT trap
cleanup() {
  rm -rf "${TEST_TMP}"
}
trap cleanup EXIT

fail() {
  printf 'not ok - %s\n' "$1" >&2
  exit 1
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local message="$3"

  if [[ "${actual}" != "${expected}" ]]; then
    printf 'expected: %q\nactual:   %q\n' "${expected}" "${actual}" >&2
    fail "${message}"
  fi
}

fast_output="$("${WATCH}" 2 6 -- bash -c 'printf "fast output\n"')" ||
  fail 'fast command should succeed'
assert_eq 'fast output' "${fast_output}" 'fast command output should pass through unchanged'
printf 'ok - fast command passes through output\n'

stall_stdout="${TEST_TMP}/stall.stdout"
stall_stderr="${TEST_TMP}/stall.stderr"
if "${WATCH}" 2 6 -- bash -c 'printf "partial output\n"; sleep 30' \
  >"${stall_stdout}" 2>"${stall_stderr}"; then
  fail 'twice-stalling command should fail'
fi
[[ ! -s "${stall_stdout}" ]] || fail 'failed attempts must not leak captured stdout'
[[ -s "${stall_stderr}" ]] || fail 'twice-stalling command should diagnose on stderr'
printf 'ok - stalled command is killed, retried once, then fails\n'

# shellcheck disable=SC2016  # expanded by the nested bash, not this test shell
stream_output="$("${WATCH}" 2 8 -- bash -c '
  for line in 1 2 3 4; do
    printf "stream %s\n" "${line}"
    sleep 1
  done
')" || fail 'streaming command should not be killed'
assert_eq $'stream 1\nstream 2\nstream 3\nstream 4' "${stream_output}" \
  'streaming output should pass through unchanged'
printf 'ok - output growth resets the idle timer\n'

marker="${TEST_TMP}/second-attempt.marker"
# shellcheck disable=SC2016  # expanded by the nested bash, not this test shell
retry_output="$("${WATCH}" 2 6 -- bash -c '
  marker="$1"
  if [[ ! -e "${marker}" ]]; then
    : >"${marker}"
    printf "discard this attempt\n"
    sleep 30
  fi
  printf "retry succeeded\n"
' _ "${marker}")" || fail 'second attempt should recover after first attempt stalls'
assert_eq 'retry succeeded' "${retry_output}" 'only successful retry output should be emitted'
printf 'ok - stalled first attempt can recover on retry\n'

printf 'all opencode-watch tests passed\n'
