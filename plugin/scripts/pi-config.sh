#!/bin/bash
# pi-config.sh — the one door for configuring the PI review council.
#
# Everything the council can be told lives in ONE file (~/.claude/pi.json), and this script is the
# only thing that needs to know its shape. `/pi-review` reads that file and relays it into the
# workflow engine, which has no filesystem access of its own.
#
# WHY THIS EXISTS: the engine (plugin/workflows/pi-council.js) is force-copied over the installed
# copy whenever the plugin's version differs — so editing the engine to change a model is not just
# awkward, it is WIPED on the next run. Config, not sed.
#
# WHY VALIDATION LIVES HERE: an off-plan model alias does not error at the backend, it HANGS until
# the leaf watchdog kills it (~10 min, per leaf). The engine cannot check — it has no fs and cannot
# run `opencode models`. So every alias is verified against the LIVE plan at write time, and
# `doctor` re-verifies the whole file on demand. This is the typo guard.
#
# The DEFAULTS below MIRROR the engine's BASE_MODELS / BASE_TIERS / BASE_ON_DEMAND so this script
# stands alone (it must work before the plugin is installed). test/pi_config_test.sh asserts the two
# never drift — the same pattern as test/scaffold_sync_test.mjs.
set -euo pipefail

CFG="${PI_CONFIG:-${HOME}/.claude/pi.json}"
VERIFY=1

# --- Defaults (MIRROR of the engine registry — kept in sync by test/pi_config_test.sh) -----------
DEFAULT_FAMILIES="glm qwen minimax deepseek mimo kimicode hy luna"
default_alias() {
  case "$1" in
    glm)      echo 'glm-5.2' ;;
    qwen)     echo 'qwen3.7-max' ;;
    minimax)  echo 'minimax-m3' ;;
    deepseek) echo 'deepseek-v4-flash' ;;
    mimo)     echo 'mimo-v2.5-pro' ;;
    kimicode) echo 'kimi-k2.7-code' ;;
    hy)       echo 'hy4-preview' ;;
    luna)     echo 'gpt-5.6-luna' ;;
    *)        echo '' ;;
  esac
}
default_tier() {
  case "$1" in
    low)  echo 'deepseek mimo qwen' ;;
    med)  echo 'glm qwen deepseek kimicode' ;;
    high) echo 'glm qwen minimax deepseek mimo kimicode hy' ;;
    *)    echo '' ;;
  esac
}
# on-demand alias : auto stand-in. NEVER used without per-run confirmation; the auto path downgrades.
DEFAULT_ONDEMAND='qwen3.8-max:qwen3.7-max glm-5.3:glm-5.2'
# NEVER on the Go plan: ANY alias under this vendor (except the listed one) is substituted for it,
# always, and no per-run consent unlocks it. Grok is priced out of a Poor-Intelligence council; any
# non-k2.7-code kimi belongs to the kimi-reviewer CLI leaf instead.
DEFAULT_NEVER_ON_GO='grok:gpt-5.6-luna kimi:kimi-k2.7-code'
TIER_NAMES="low med high"
EFFORTS="low medium high xhigh max"

log()  { printf '%s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
die()  { printf '[error] %s\n' "$*" >&2; exit 1; }

# --- JSON primitives (python3 is already a dependency via pi-mask.py) ----------------------------
# Atomic write: a half-written pi.json would make every later run fail to parse its own config.
json_py() { PI_CFG="${CFG}" python3 - "$@" <<'PY'
import json, os, sys, tempfile

path = os.environ["PI_CFG"]
op, rest = sys.argv[1], sys.argv[2:]

def load():
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.exit(f"[error] {path} is not readable JSON: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"[error] {path} must contain a JSON object, found {type(data).__name__}")
    return data

def save(data):
    for key in [k for k, v in data.items() if isinstance(v, dict) and not v]:
        del data[key]          # never leave an empty {} behind after an --unset
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".pi.json.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)

if op == "dump":
    json.dump(load(), sys.stdout, indent=2, sort_keys=True)
    print()
elif op == "get":                      # get <key>            → scalar or ''
    val = load().get(rest[0], "")
    print(val if not isinstance(val, (dict, list)) else json.dumps(val))
elif op == "sub":                      # sub <top> <key>      → nested scalar or ''
    print(load().get(rest[0], {}).get(rest[1], ""))
elif op == "keys":                     # keys <top>           → nested keys, one per line
    for key in sorted(load().get(rest[0], {})):
        print(key)
elif op == "list":                     # list <top> <key>     → nested list, space-joined
    val = load().get(rest[0], {}).get(rest[1])
    print(" ".join(val) if isinstance(val, list) else "")
elif op == "subfield":                 # subfield <top> <key> <field> → 2-deep scalar or ''
    # A tier may be stored as a bare family LIST (no fields at all) or as an object — only the object
    # form can carry a field. Booleans print as JSON (true/false), never Python's True/False, so the
    # shell can compare them literally.
    entry = load().get(rest[0], {}).get(rest[1])
    val = entry.get(rest[2], "") if isinstance(entry, dict) else ""
    print(json.dumps(val) if isinstance(val, bool) else val)
elif op == "set":                      # set <key> <value>
    data = load(); data[rest[0]] = rest[1]; save(data)
elif op == "setsub":                   # setsub <top> <key> <value>
    data = load(); data.setdefault(rest[0], {})[rest[1]] = rest[2]; save(data)
elif op == "setlist":                  # setlist <top> <key> <v>...
    data = load(); data.setdefault(rest[0], {})[rest[1]] = rest[2:]; save(data)
elif op == "setbool":                  # setbool <top> <key> <field> true|false
    data = load()
    tier = data.setdefault(rest[0], {}).get(rest[1])
    tier = {"families": tier} if isinstance(tier, list) else (tier if isinstance(tier, dict) else {})
    tier[rest[2]] = rest[3] == "true"
    data[rest[0]][rest[1]] = tier
    save(data)
elif op == "setfield":                 # setfield <top> <key> <field> <value>
    data = load()
    tier = data.setdefault(rest[0], {}).get(rest[1])
    tier = {"families": tier} if isinstance(tier, list) else (tier if isinstance(tier, dict) else {})
    tier[rest[2]] = rest[3]
    data[rest[0]][rest[1]] = tier
    save(data)
elif op == "del":                      # del <key> [nested-key]
    data = load()
    if len(rest) == 1:
        data.pop(rest[0], None)
    elif isinstance(data.get(rest[0]), dict):
        data[rest[0]].pop(rest[1], None)
    save(data)
elif op == "check":                    # check → parse only (exit 1 on bad JSON)
    load()
else:
    sys.exit(f"[error] unknown json op {op}")
PY
}

# --- The live plan — the ONLY source of truth for "does this alias exist" ------------------------
# `< /dev/null` per our own opencode rule: never let a CLI call block on a TTY stdin.
PLAN_CACHE=""
plan_aliases() {
  if [[ -z "${PLAN_CACHE}" ]]; then
    command -v opencode >/dev/null 2>&1 || die "opencode CLI not found on PATH — install it, or re-run with --no-verify to skip plan checks"
    PLAN_CACHE="$(opencode models < /dev/null 2>/dev/null | grep '^opencode-go/' | sed 's|^opencode-go/||' || true)"
    [[ -n "${PLAN_CACHE}" ]] || die "\`opencode models\` returned no opencode-go aliases — are you signed in? (--no-verify skips this)"
  fi
  printf '%s\n' "${PLAN_CACHE}"
}
# Here-string, NOT a pipe: `set -o pipefail` + `grep -q` is a trap — grep exits on the first match
# and SIGPIPEs the producer (141), which pipefail then reports as the pipeline's status, so every
# alias would read as "not on plan". Same reason in_list/is_family below avoid pipes.
alias_on_plan() { grep -qxF -- "$1" <<< "$(plan_aliases)"; }
verify_alias() {
  local alias="$1"
  [[ "${VERIFY}" -eq 1 ]] || return 0
  if ! alias_on_plan "${alias}"; then
    warn "'${alias}' is NOT on your opencode-go plan. Available:"
    plan_aliases | sed 's/^/    /' >&2
    die "refusing to write an off-plan alias — an off-plan model does not error, it hangs the leaf until the watchdog kills it (--no-verify overrides)"
  fi
}

# effective value of a family: configured override, else built-in default
effective_alias() {
  local fam="$1" set_to
  set_to="$(json_py sub models "${fam}")"
  [[ -n "${set_to}" ]] && { printf '%s' "${set_to}"; return; }
  printf '%s' "$(default_alias "${fam}")"
}
effective_families() {
  { printf '%s\n' ${DEFAULT_FAMILIES}; json_py keys models; } | sort -u
}
effective_tier() {
  local name="$1" set_to
  set_to="$(json_py list tiers "${name}")"
  [[ -n "${set_to}" ]] && { printf '%s' "${set_to}"; return; }
  printf '%s' "$(default_tier "${name}")"
}
# The stand-in an alias downgrades to, or empty if the alias is an ordinary auto model. Config wins
# over the shipped map, and a config entry pointing somewhere else RETIRES the shipped one.
ondemand_target() {
  local set_to pair
  set_to="$(json_py sub onDemand "$1")"
  [[ -n "${set_to}" ]] && { printf '%s' "${set_to}"; return; }
  for pair in ${DEFAULT_ONDEMAND}; do
    [[ "${pair%%:*}" == "$1" ]] && { printf '%s' "${pair##*:}"; return; }
  done
  printf ''
}
is_family() { grep -qxF -- "$1" <<< "$(effective_families)"; }
# shellcheck disable=SC2086  # $2 is a space-separated word list on purpose
in_list()   { grep -qxF -- "$1" <<< "$(printf '%s\n' $2)"; }

# --- Commands ------------------------------------------------------------------------------------
cmd_show() {
  log "config file: ${CFG}$([[ -f "${CFG}" ]] || printf ' (absent — all defaults)')"
  log ""
  log "settings"
  local key val
  for key in tier chairman kimiCliModel; do
    val="$(json_py get "${key}")"
    if [[ -n "${val}" ]]; then printf '  %-10s %s\n' "${key}" "${val}"
    else
      case "${key}" in
        tier)     printf '  %-10s %s\n' "${key}" 'med (default)' ;;
        chairman) printf '  %-10s %s\n' "${key}" 'glm (default)' ;;
        kimiCliModel) printf '  %-10s %s\n' "${key}" 'kimi-code/k3-256k (default)' ;;
      esac
    fi
  done
  log ""
  log "models"
  local fam alias
  for fam in $(effective_families); do
    alias="$(effective_alias "${fam}")"
    if [[ -n "$(json_py sub models "${fam}")" ]]; then printf '  %-10s %-20s (configured)\n' "${fam}" "${alias}"
    else printf '  %-10s %-20s\n' "${fam}" "${alias}"; fi
  done
  log ""
  log "tiers"
  local t fams
  for t in ${TIER_NAMES}; do
    fams="$(effective_tier "${t}")"
    if [[ -n "$(json_py list tiers "${t}")" ]]; then printf '  %-6s %s (configured)\n' "${t}" "${fams}"
    else printf '  %-6s %s\n' "${t}" "${fams}"; fi
  done
  log ""
  log "on-demand (never automatic — confirm per run with: /pi-review ... --with <alias>)"
  local pair a b
  for pair in ${DEFAULT_ONDEMAND}; do
    a="${pair%%:*}"; b="${pair##*:}"
    printf '  %-14s auto downgrades to → %s\n' "${a}" "$( [[ -n "$(json_py sub onDemand "${a}")" ]] && json_py sub onDemand "${a}" || printf '%s' "${b}" )"
  done
  for a in $(json_py keys onDemand); do
    in_list "${a}" "$(printf '%s\n' ${DEFAULT_ONDEMAND} | cut -d: -f1)" && continue
    printf '  %-14s auto downgrades to → %s (configured)\n' "${a}" "$(json_py sub onDemand "${a}")"
  done
  log ""
  log "never on the Go plan (substituted ALWAYS — --with cannot unlock these)"
  for pair in ${DEFAULT_NEVER_ON_GO}; do
    a="${pair%%:*}"; b="${pair##*:}"
    printf '  %-14s any %-12s → %s\n' "${a}*" "${a} but ${b}" "$( [[ -n "$(json_py sub neverOnGo "${a}")" ]] && json_py sub neverOnGo "${a}" || printf '%s' "${b}" )"
  done
  for a in $(json_py keys neverOnGo); do
    in_list "${a}" "$(printf '%s\n' ${DEFAULT_NEVER_ON_GO} | cut -d: -f1)" && continue
    printf '  %-14s any %-12s → %s (configured)\n' "${a}*" "${a}" "$(json_py sub neverOnGo "${a}")"
  done
}

cmd_set() {
  local key="${1:-}" val="${2:-}"
  [[ -n "${key}" && -n "${val}" ]] || die "usage: pi-config.sh set <tier|chairman|kimiCliModel> <value>"
  case "${key}" in
    tier)
      case "${val}" in max|ultra) val=high ;; esac
      in_list "${val}" "${TIER_NAMES}" || die "invalid tier '${val}' — use one of: ${TIER_NAMES}"
      ;;
    kimiCliModel)
      # The kimi CLI's OWN alias namespace (kimi -m), not an opencode one — 'kimi-for-coding/k3-256k'
      # is the same model in opencode and is WRONG here. Only shape is checked; 'kimi doctor' lists
      # what this host actually defines.
      [[ "${val}" == */* ]] || die "invalid kimiCliModel '${val}' — use a kimi-code CLI alias like 'kimi-code/k3-256k' (see: kimi doctor)"
      case "${val}" in
        kimi-for-coding/*) die "'${val}' is the OPENCODE spelling — the kimi CLI wants 'kimi-code/${val#*/}'" ;;
      esac
      command -v kimi >/dev/null 2>&1 || warn "the 'kimi' CLI is not on PATH — any tier with kimiCli=true will come back UNAVAILABLE"
      ;;
    chairman)
      if [[ "${val}" != "opus" && "${val}" != "sonnet" ]] && ! is_family "${val}"; then
        verify_alias "${val}"
      fi
      ;;
    kimiMode) die "'kimiMode' is retired — the Go-plan Kimi is the ordinary family 'kimicode' (put it in a tier), and the Kimi CLI leaf is per-tier: pi-config.sh tier <name> --kimi-cli on|off" ;;
    *) die "unknown key '${key}' — settable keys are: tier, chairman, kimiCliModel (models → 'model', tiers → 'tier')" ;;
  esac
  json_py set "${key}" "${val}"
  log "set ${key} = ${val}"
}

cmd_model() {
  local fam="${1:-}" alias="${2:-}"
  [[ -n "${fam}" ]] || die "usage: pi-config.sh model <family> <alias|--unset>"
  if [[ "${alias}" == "--unset" ]]; then
    local back
    back="$(default_alias "${fam}")"
    json_py del models "${fam}"
    log "model ${fam} → back to default (${back:-none: '${fam}' was a config-only family and is now gone})"
    return
  fi
  [[ -n "${alias}" ]] || die "usage: pi-config.sh model <family> <alias|--unset>"
  [[ "${fam}" =~ ^[a-z][a-z0-9-]*$ ]] || die "invalid family name '${fam}' — use a short lowercase name like 'glm'"
  alias="${alias#opencode-go/}"
  verify_alias "${alias}"
  # A second family already pointing here means the panel would silently run one model twice — the
  # correlated-blind-spot failure the council exists to avoid. The engine throws on this; catch it here.
  local other
  for other in $(effective_families); do
    [[ "${other}" == "${fam}" ]] && continue
    [[ "$(effective_alias "${other}")" == "${alias}" ]] && die "family '${other}' already uses '${alias}' — two families on one alias makes the panel run the same model twice"
  done
  json_py setsub models "${fam}" "${alias}"
  log "model ${fam} = ${alias}"
  # Pinning a family to an on-demand alias is allowed — but the auto path will stand in for it every
  # run, so say that HERE rather than letting the operator discover it in a coverage footer later.
  local stand_in
  stand_in="$(ondemand_target "${alias}")"
  if [[ -n "${stand_in}" ]]; then
    warn "'${alias}' is ON-DEMAND: normal runs will use '${stand_in}' instead. To really run it: /pi-review ... --with ${alias} (and confirm)."
    warn "if it should be an ordinary auto model, run: pi-config.sh ondemand ${alias} --unset"
  fi
}

cmd_tier() {
  local name="${1:-}"; shift || true
  [[ -n "${name}" ]] || die "usage: pi-config.sh tier <low|med|high> <family...> | --kimi-cli on|off | --effort <e> | --unset"
  in_list "${name}" "${TIER_NAMES}" || die "unknown tier '${name}' — the low/med/high contract is fixed"
  case "${1:-}" in
    --unset)  json_py del tiers "${name}"; log "tier ${name} → back to default ($(default_tier "${name}"))"; return ;;
    --kimi)
      die "'--kimi' is retired — it used to move a single Kimi slot. The Go-plan Kimi is now the ordinary family 'kimicode' (pi-config.sh tier ${name} <family...>), and '--kimi-cli' toggles the separate Kimi CLI (K3) leaf" ;;
    --kimi-cli)
      in_list "${2:-}" "on off" || die "usage: pi-config.sh tier ${name} --kimi-cli on|off"
      json_py setbool tiers "${name}" kimiCli "$([[ "$2" == "on" ]] && echo true || echo false)"
      log "tier ${name} kimiCli = ${2}"; return ;;
    --effort)
      in_list "${2:-}" "${EFFORTS}" || die "usage: pi-config.sh tier ${name} --effort <${EFFORTS// /|}>"
      json_py setfield tiers "${name}" effort "$2"
      log "tier ${name} effort = ${2}"; return ;;
    "") die "usage: pi-config.sh tier ${name} <family...>  (current: $(effective_tier "${name}"))" ;;
  esac
  local fam
  for fam in "$@"; do
    is_family "${fam}" || die "unknown family '${fam}' — known: $(effective_families | tr '\n' ' ')— add one first: pi-config.sh model ${fam} <alias>"
  done
  json_py setlist tiers "${name}" "$@"
  log "tier ${name} = $*"
}

cmd_ondemand() {
  local alias="${1:-}" fallback="${2:-}"
  [[ -n "${alias}" ]] || die "usage: pi-config.sh ondemand <alias> <auto-stand-in|--unset>"
  alias="${alias#opencode-go/}"
  if [[ "${fallback}" == "--unset" ]]; then
    json_py del onDemand "${alias}"
    log "ondemand ${alias} removed (it becomes an ordinary auto model if a tier names it)"
    return
  fi
  [[ -n "${fallback}" ]] || die "an on-demand model needs an auto stand-in: pi-config.sh ondemand ${alias} <alias>"
  fallback="${fallback#opencode-go/}"
  [[ "${alias}" != "${fallback}" ]] || die "'${alias}' cannot stand in for itself"
  verify_alias "${alias}"
  verify_alias "${fallback}"
  json_py setsub onDemand "${alias}" "${fallback}"
  log "ondemand ${alias} → ${fallback} (never automatic; confirm per run)"
}

cmd_reset() {
  local key="${1:-}"
  if [[ -z "${key}" ]]; then
    [[ -f "${CFG}" ]] || { log "nothing to reset — ${CFG} does not exist"; return; }
    rm -f "${CFG}"
    log "removed ${CFG} — every setting back to the built-in defaults"
  else
    json_py del "${key}"
    log "reset ${key} → default"
  fi
}

cmd_doctor() {
  local rc=0 val fam alias t f kimi_cli_tiers
  log "config file: ${CFG}"
  if [[ -f "${CFG}" ]]; then
    if json_py check; then log "  ok   parses as JSON"; else log "  FAIL not valid JSON — fix or run: pi-config.sh reset"; return 1; fi
  else
    log "  ok   absent — running on built-in defaults"
  fi

  if command -v opencode >/dev/null 2>&1; then
    log "  ok   opencode CLI: $(command -v opencode)"
  else
    log "  FAIL opencode CLI not on PATH — every leaf will be UNAVAILABLE"; rc=1
  fi

  # The Kimi CLI leaf is per-tier now, so the CLI only has to exist if SOME tier switched it on.
  kimi_cli_tiers=""
  for t in ${TIER_NAMES}; do
    [[ "$(json_py subfield tiers "${t}" kimiCli)" == "true" ]] && kimi_cli_tiers="${kimi_cli_tiers}${t} "
  done
  if [[ -n "${kimi_cli_tiers}" ]]; then
    if command -v kimi >/dev/null 2>&1; then log "  ok   kimi CLI: $(command -v kimi) (kimiCli on: ${kimi_cli_tiers%% })"
    else log "  FAIL kimiCli is on for tier(s) ${kimi_cli_tiers%% }but no 'kimi' on PATH — that leaf will be UNAVAILABLE"; rc=1; fi
  fi

  if [[ -f "${HOME}/.claude/workflows/pi-council.js" ]]; then
    log "  ok   engine installed: ~/.claude/workflows/pi-council.js"
  else
    log "  note engine not installed yet — /pi-review installs it on first run"
  fi

  if [[ "${VERIFY}" -eq 1 ]] && command -v opencode >/dev/null 2>&1; then
    log "models (verified against your live opencode-go plan)"
    for fam in $(effective_families); do
      alias="$(effective_alias "${fam}")"
      local stand_in
      stand_in="$(ondemand_target "${alias}")"
      if [[ -z "${alias}" ]]; then log "  FAIL ${fam}: no alias — configured family with no model"; rc=1
      elif ! alias_on_plan "${alias}"; then log "  FAIL ${fam} → ${alias} is NOT on your plan — this leaf will HANG until the watchdog kills it"; rc=1
      elif [[ -n "${stand_in}" ]]; then log "  note ${fam} → ${alias} is ON-DEMAND — normal runs use ${stand_in}; confirm per run with --with ${alias}"
      else log "  ok   ${fam} → ${alias}"; fi
    done
  else
    log "models: plan verification skipped (--no-verify or no opencode CLI)"
  fi

  log "tiers"
  for t in ${TIER_NAMES}; do
    local bad=""
    for f in $(effective_tier "${t}"); do is_family "${f}" || bad="${bad} ${f}"; done
    if [[ -n "${bad}" ]]; then log "  FAIL ${t}: unknown family/families —${bad}"; rc=1
    else log "  ok   ${t}: $(effective_tier "${t}")"; fi
  done

  val="$(json_py get chairman)"
  if [[ -n "${val}" ]]; then
    if [[ "${val}" == "opus" || "${val}" == "sonnet" ]] || is_family "${val}"; then log "  ok   chairman: ${val}"
    elif [[ "${VERIFY}" -eq 1 ]] && command -v opencode >/dev/null 2>&1 && alias_on_plan "${val}"; then log "  ok   chairman: ${val}"
    else log "  FAIL chairman '${val}' is neither opus/sonnet, a known family, nor a plan alias"; rc=1; fi
  fi

  [[ "${rc}" -eq 0 ]] && log "" && log "all good." || { log ""; log "problems found — see FAIL lines above."; }
  return "${rc}"
}

cmd_models() {
  log "opencode-go aliases available on your plan:"
  plan_aliases | sed 's/^/  /'
}

usage() {
  cat <<'USAGE'
pi-config.sh — configure the PI review council (~/.claude/pi.json)

  show                              print the effective config (defaults + your overrides)
  doctor                            verify everything against the live plan and CLIs
  models                            list the opencode-go aliases your plan actually offers

  set tier      <low|med|high>      default tier for /pi-review
  set chairman  <opus|sonnet|family|alias>
  set kimiCliModel <cli-alias>      model for the Kimi CLI leaf (default kimi-code/k3-256k)

  model <family> <alias>            pin a family to a model      (e.g. model glm glm-5.3)
  model <family> --unset            back to the built-in default

  tier  <name> <family...>          set a tier's reviewers       (e.g. tier low deepseek mimo qwen)
  tier  <name> --kimi-cli on|off    add/remove the Kimi CLI (K3) leaf for that tier
  tier  <name> --effort <level>     synthesis effort for that tier
  tier  <name> --unset              back to the built-in default

  ondemand <alias> <stand-in>       mark a model opt-in-only, with its auto downgrade target
  ondemand <alias> --unset          make it an ordinary auto model

  reset [key]                       drop one key, or the whole file

Options:
  --file <path>   use a different config file (default: ~/.claude/pi.json, or $PI_CONFIG)
  --no-verify     skip live-plan alias checks (offline; you own the typo risk)

On-demand models are NEVER used automatically. If a tier or the chairman resolves to one without
per-run confirmation, the council runs its stand-in instead and says so in the coverage footer.
USAGE
}

main() {
  local args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --file) CFG="${2:?--file needs a path}"; shift 2 ;;
      --no-verify) VERIFY=0; shift ;;
      -h|--help|help) usage; return 0 ;;
      *) args+=("$1"); shift ;;
    esac
  done
  set -- ${args[@]+"${args[@]}"}
  case "${1:-show}" in
    show)     cmd_show ;;
    path)     printf '%s\n' "${CFG}" ;;
    dump)     json_py dump ;;
    set)      shift; cmd_set "$@" ;;
    model)    shift; cmd_model "$@" ;;
    tier)     shift; cmd_tier "$@" ;;
    ondemand) shift; cmd_ondemand "$@" ;;
    reset)    shift; cmd_reset "$@" ;;
    doctor)   cmd_doctor ;;
    models)   cmd_models ;;
    *)        warn "unknown command: $1"; usage; return 2 ;;
  esac
}

main "$@"
