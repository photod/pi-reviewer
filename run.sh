#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_PLUGIN="${REPO_DIR}/plugins/pi"

log() { printf '==> %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }

frontmatter() {
  awk 'NR==1 && $0=="---"{f=1;next} f && $0=="---"{exit} f{print}' "$1"
}

check() {
  local rc=0 file fm temp_home

  for file in "${REPO_DIR}"/plugin/agents/*.md "${REPO_DIR}"/plugin/commands/*.md; do
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
      "${REPO_DIR}/.claude-plugin/marketplace.json" \
      "${CODEX_PLUGIN}/.codex-plugin/plugin.json" \
      "${REPO_DIR}/.agents/plugins/marketplace.json"; then
    log "plugin manifests ok"
  else
    warn "invalid plugin manifest"
    rc=1
  fi

  for file in "${CODEX_PLUGIN}"/agents/*.toml; do
    if python3 -c 'import sys,tomllib; tomllib.load(open(sys.argv[1], "rb"))' "${file}"; then
      log "Codex agent TOML ok: $(basename "${file}")"
    else
      warn "invalid Codex agent TOML: ${file}"
      rc=1
    fi
  done
  if python3 -c 'import sys,tomllib; tomllib.load(open(sys.argv[1], "rb"))' \
      "${CODEX_PLUGIN}/profiles/pi.config.toml"; then
    log "Codex PI profile TOML ok"
  else
    warn "invalid Codex PI profile TOML"
    rc=1
  fi

  for file in pi-filelist.sh pi-stage.sh pi-mask.py masker-rules.md pi-mask.config.example.json opencode-watch.sh; do
    if cmp -s -- "${REPO_DIR}/scripts/${file}" "${CODEX_PLUGIN}/scripts/${file}"; then
      log "bundled script in sync: ${file}"
    else
      warn "bundled script drift: ${file}"
      rc=1
    fi
  done
  for file in pi-council.js glm-worker.md oppy-reviewer.md kimi-reviewer.md; do
    case "${file}" in
      pi-council.js) local source="${REPO_DIR}/plugin/workflows/${file}" ;;
      *) local source="${REPO_DIR}/plugin/agents/${file}" ;;
    esac
    if cmp -s -- "${source}" "${CODEX_PLUGIN}/references/${file}"; then
      log "Codex reference in sync: ${file}"
    else
      warn "Codex reference drift: ${file}"
      rc=1
    fi
  done

  temp_home="$(mktemp -d)"
  if CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_agents.py" install >/dev/null &&
      CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_agents.py" check >/dev/null &&
      CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_agents.py" uninstall >/dev/null; then
    log "Codex agent manager lifecycle ok"
  else
    warn "Codex agent manager lifecycle failed"
    rc=1
  fi
  rm -rf -- "${temp_home}"

  temp_home="$(mktemp -d)"
  if CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_profile.py" install >/dev/null &&
      CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_profile.py" check >/dev/null &&
      CODEX_HOME="${temp_home}" python3 "${CODEX_PLUGIN}/scripts/manage_profile.py" uninstall >/dev/null; then
    log "Codex PI profile manager lifecycle ok"
  else
    warn "Codex PI profile manager lifecycle failed"
    rc=1
  fi
  rm -rf -- "${temp_home}"

  node "${REPO_DIR}/test/coverage_footer_test.mjs" || rc=1
  node "${REPO_DIR}/test/tier_contract_test.mjs" || rc=1
  PYTHONDONTWRITEBYTECODE=1 python3 "${REPO_DIR}/test/pi_mask_test.py" || rc=1
  bash "${REPO_DIR}/test/pi_filelist_test.sh" || rc=1
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "${REPO_DIR}/test" -p 'test_*.py' || rc=1

  return "${rc}"
}

case "${1:-check}" in
  check) check ;;
  help|-h|--help) printf 'Usage: ./run.sh check\n' ;;
  *) warn "unknown command: ${1}"; exit 2 ;;
esac
