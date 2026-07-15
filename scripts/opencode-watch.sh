#!/usr/bin/env bash

set -euo pipefail

usage() {
  printf 'usage: %s <idle_secs> <cap_secs> -- <command> [args...]\n' "${0##*/}" >&2
  exit 2
}

if (( $# < 4 )); then
  usage
fi

idle_secs="$1"
cap_secs="$2"
shift 2

if ! [[ "${idle_secs}" =~ ^[0-9]+$ && "${cap_secs}" =~ ^[0-9]+$ ]]; then
  usage
fi
if (( idle_secs == 0 || cap_secs == 0 )); then
  usage
fi
if [[ "$1" != "--" ]]; then
  usage
fi
shift
if (( $# == 0 )); then
  usage
fi

child_pid=''
capture_file=''

terminate_group() {
  local pid="$1"

  if ! kill -0 "${pid}" 2>/dev/null; then
    return
  fi

  # setsid and Bash monitor mode both make the child PID its process-group ID.
  kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
  kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null || true
}

# shellcheck disable=SC2329  # invoked indirectly by the EXIT trap
cleanup() {
  if [[ -n "${child_pid}" ]]; then
    terminate_group "${child_pid}"
    wait "${child_pid}" 2>/dev/null || true
  fi
  if [[ -n "${capture_file}" ]]; then
    rm -f "${capture_file}"
  fi
}

trap cleanup EXIT
trap 'exit 130' HUP INT TERM

ATTEMPT_RESULT=''

run_attempt() {
  local attempt="$1"
  shift
  local started_at
  local last_growth_at
  local now
  local size
  local last_size=0
  local stop_reason=''
  local status

  capture_file="$(mktemp "${TMPDIR:-/tmp}/opencode-watch.XXXXXX")"
  started_at="$(date +%s)"
  last_growth_at="${started_at}"

  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >"${capture_file}" &
    child_pid="$!"
  else
    # macOS has no setsid(1). Monitor mode gives each background job its own
    # process group, with the background PID as the group leader.
    set -m
    "$@" >"${capture_file}" &
    child_pid="$!"
    set +m
  fi

  while kill -0 "${child_pid}" 2>/dev/null; do
    now="$(date +%s)"
    size="$(wc -c <"${capture_file}")"

    if (( size > last_size )); then
      last_size="${size}"
      last_growth_at="${now}"
    fi

    if (( now - started_at >= cap_secs )); then
      stop_reason="hard cap of ${cap_secs}s reached"
      terminate_group "${child_pid}"
      break
    fi
    if (( now - last_growth_at >= idle_secs )); then
      stop_reason="no stdout growth for ${idle_secs}s"
      terminate_group "${child_pid}"
      break
    fi

    sleep 1
  done

  if wait "${child_pid}"; then
    status=0
  else
    status="$?"
  fi
  child_pid=''

  if [[ -z "${stop_reason}" && "${status}" -eq 0 && -s "${capture_file}" ]]; then
    cat "${capture_file}"
    rm -f "${capture_file}"
    capture_file=''
    return 0
  fi

  if [[ -n "${stop_reason}" ]]; then
    ATTEMPT_RESULT="attempt ${attempt}: ${stop_reason}"
  elif [[ "${status}" -eq 0 ]]; then
    ATTEMPT_RESULT="attempt ${attempt}: command exited successfully without stdout"
  else
    ATTEMPT_RESULT="attempt ${attempt}: command exited with status ${status}"
  fi

  rm -f "${capture_file}"
  capture_file=''
  return 1
}

diagnostics=''
for attempt in 1 2; do
  if run_attempt "${attempt}" "$@"; then
    exit 0
  fi
  if [[ -n "${diagnostics}" ]]; then
    diagnostics="${diagnostics}; ${ATTEMPT_RESULT}"
  else
    diagnostics="${ATTEMPT_RESULT}"
  fi
done

printf 'opencode-watch: command failed after two attempts (%s)\n' "${diagnostics}" >&2
exit 1
