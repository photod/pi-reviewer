#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '==> %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }

frontmatter() {
  awk 'NR==1 && $0=="---"{f=1;next} f && $0=="---"{exit} f{print}' "$1"
}

check() {
  local rc=0 file fm

  for file in "${REPO_DIR}"/plugin/agents/*.md "${REPO_DIR}"/plugin/commands/*.md "${REPO_DIR}"/cody/agents/*.md; do
    fm="$(frontmatter "${file}")"
    if [[ -n "${fm}" ]] && printf '%s\n' "${fm}" | grep -q '^name:'; then
      log "Claude frontmatter ok: $(basename "${file}")"
    else
      warn "bad Claude frontmatter: ${file}"
      rc=1
    fi
  done

  for file in "${REPO_DIR}/plugin/commands/pi-review.md" "${REPO_DIR}/plugin/commands/pi-build.md"; do
    if frontmatter "${file}" | grep -qF 'argument-hint: "[low|med(default)|high]'; then
      log "tier input contract ok: $(basename "${file}")"
    else
      warn "tier input contract must be exactly low|med|high: ${file}"
      rc=1
    fi
  done

  if command -v opencode >/dev/null 2>&1; then
    log "required CLI present: opencode ($(command -v opencode))"
  else
    warn "required CLI missing: opencode"
    rc=1
  fi
  if command -v kimi >/dev/null 2>&1; then
    log "optional CLI present: kimi ($(command -v kimi))"
  else
    log "optional CLI absent: kimi"
  fi

  if python3 -c 'import json,sys; [json.load(open(p)) for p in sys.argv[1:]]' \
      "${REPO_DIR}/plugin/.claude-plugin/plugin.json" \
      "${REPO_DIR}/cody/.claude-plugin/plugin.json" \
      "${REPO_DIR}/.claude-plugin/marketplace.json"; then
    log "plugin manifests ok"
  else
    warn "invalid plugin manifest"
    rc=1
  fi

  if diff -rq "${REPO_DIR}/scripts" "${REPO_DIR}/plugin/scripts" >/dev/null 2>&1; then
    log "Claude plugin scripts in sync (scripts/ == plugin/scripts/)"
  else
    warn "Claude plugin script drift (scripts/ vs plugin/scripts/):"
    diff -rq "${REPO_DIR}/scripts" "${REPO_DIR}/plugin/scripts" >&2 || true
    rc=1
  fi

  if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck --severity=error "${REPO_DIR}"/scripts/*.sh "${REPO_DIR}"/test/*.sh "${REPO_DIR}/run.sh" >/dev/null 2>&1; then
      log "shellcheck clean (scripts, tests, run.sh)"
    else
      warn "shellcheck reported errors:"
      shellcheck --severity=error "${REPO_DIR}"/scripts/*.sh "${REPO_DIR}"/test/*.sh "${REPO_DIR}/run.sh" >&2 || true
      rc=1
    fi
  else
    log "shellcheck absent — skipped (optional)"
  fi

  node "${REPO_DIR}/test/coverage_footer_test.mjs" || rc=1
  node "${REPO_DIR}/test/tier_contract_test.mjs" || rc=1
  node "${REPO_DIR}/test/agent_dispatch_test.mjs" || rc=1
  node "${REPO_DIR}/test/scaffold_sync_test.mjs" || rc=1
  PYTHONDONTWRITEBYTECODE=1 python3 "${REPO_DIR}/test/pi_mask_test.py" || rc=1
  bash "${REPO_DIR}/test/pi_filelist_test.sh" || rc=1
  bash "${REPO_DIR}/test/pi_stage_test.sh" || rc=1
  bash "${REPO_DIR}/test/opencode_watch_test.sh" || rc=1

  return "${rc}"
}

case "${1:-check}" in
  check) check ;;
  help|-h|--help) printf 'Usage: ./run.sh check\n' ;;
  *) warn "unknown command: ${1}"; exit 2 ;;
esac
