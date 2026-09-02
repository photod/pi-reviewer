#!/bin/bash
# Tests for scripts/pi-config.sh — the config door.
#
# Hermetic: a STUB `opencode` on PATH provides the "live plan", so these tests never depend on a
# real subscription while still exercising the plan-verification path that replaced the old hard
# allowlist. That path is the typo guard — an off-plan alias does not error at the backend, it
# hangs the leaf until the watchdog kills it, so "rejected at write time" is the whole safety net.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${REPO_DIR}/scripts/pi-config.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

CFG="${TMP}/pi.json"
rc=0
pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; rc=1; }
check() { if [[ "$1" -eq 0 ]]; then pass "$2"; else fail "$2"; fi }

# --- stub plan -----------------------------------------------------------------------------------
mkdir -p "${TMP}/bin"
{
  printf '#!/bin/bash\n'
  printf 'printf "%%s\\n" opencode/big-pickle opencode-go/glm-5.1 opencode-go/glm-5.2 opencode-go/glm-5.3 \\\n'
  printf '  opencode-go/qwen3.7-max opencode-go/qwen3.8-max opencode-go/deepseek-v4-pro \\\n'
  printf '  opencode-go/mimo-v2.5-pro opencode-go/minimax-m3 opencode-go/kimi-k2.7-code \\\n'
  printf '  opencode-go/deepseek-v4-flash opencode-go/hy4-preview \\\n'
  printf '  opencode-go/kimi-k2.6 opencode-go/kimi-k3 opencode-go/gpt-5.6-luna opencode-go/grok-4.6 opencode-go/hy3\n'
} > "${TMP}/bin/opencode"
chmod +x "${TMP}/bin/opencode"
export PATH="${TMP}/bin:${PATH}"

pi() { "${SCRIPT}" --file "${CFG}" "$@"; }
json_ok() { python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${CFG}" >/dev/null 2>&1; }
field() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d.get(sys.argv[2],"")))' "${CFG}" "$1" 2>/dev/null; }

# --- defaults, no file ---------------------------------------------------------------------------
out="$(pi show 2>&1)"
grep -q 'absent — all defaults' <<< "${out}"; check $? 'show works with no config file at all'
grep -q 'glm-5.2' <<< "${out}";               check $? 'show lists the built-in model defaults'
grep -q 'low    deepseek mimo qwen' <<< "${out}"; check $? 'show lists the built-in tier rosters'
grep -q 'qwen3.8-max' <<< "${out}";           check $? 'show lists the on-demand models'
grep -q 'never on the Go plan' <<< "${out}"; check $? 'show lists the barred vendors separately from on-demand'
grep -q 'grok' <<< "${out}";                  check $? 'show names grok as barred'
[[ ! -f "${CFG}" ]];                          check $? 'show is read-only — it does not create the file'

# --- scalar settings -----------------------------------------------------------------------------
pi set kimiCliModel kimi-code/k3 >/dev/null 2>&1; check $? 'set kimiCliModel succeeds'
[[ "$(field kimiCliModel)" == '"kimi-code/k3"' ]]; check $? 'kimiCliModel is persisted'
json_ok;                                      check $? 'the written file is valid JSON'
pi set kimiCliModel bogus >/dev/null 2>&1;    [[ $? -ne 0 ]]; check $? 'a kimiCliModel with no provider is rejected'
# The opencode spelling of the SAME model is the likeliest typo here — it must be caught by name.
pi set kimiCliModel kimi-for-coding/k3-256k >/dev/null 2>&1; [[ $? -ne 0 ]]; check $? 'the opencode spelling is rejected for the CLI'
[[ "$(field kimiCliModel)" == '"kimi-code/k3"' ]]; check $? 'a rejected write leaves the previous value intact'
pi set kimiMode cli >/dev/null 2>&1;          [[ $? -ne 0 ]]; check $? 'the retired kimiMode key is rejected'
pi set tier ultra >/dev/null 2>&1
[[ "$(field tier)" == '"high"' ]];            check $? 'tier alias ultra is canonicalized to high'
pi set nosuchkey x >/dev/null 2>&1;           [[ $? -ne 0 ]]; check $? 'an unknown settings key is rejected'

# --- models ---------------------------------------------------------------------------------------
pi model glm glm-5.1 >/dev/null 2>&1;         check $? 'pinning a family to an on-plan alias succeeds'
grep -q 'glm-5.1' <<< "$(pi dump)";           check $? 'the model override is persisted'
pi model glm nope-9 >/dev/null 2>&1;          [[ $? -ne 0 ]]; check $? 'an OFF-PLAN alias is refused (the typo guard)'
grep -q 'glm-5.1' <<< "$(pi dump)";           check $? 'the refused write did not corrupt the existing value'
pi model qwen glm-5.1 >/dev/null 2>&1;        [[ $? -ne 0 ]]; check $? 'two families on one alias is refused'

# Pinning to an ON-DEMAND alias is allowed but must be called out at write time — otherwise the
# operator only discovers the substitution in a coverage footer, mid-review.
out="$(pi model glm glm-5.3 2>&1)"
grep -q 'ON-DEMAND' <<< "${out}";             check $? 'pinning an on-demand alias warns that runs will use the stand-in'
grep -q 'glm-5.2' <<< "${out}";               check $? 'the warning names the stand-in that will actually run'
grep -q 'ON-DEMAND' <<< "$(pi doctor 2>&1)";  check $? 'doctor flags a family pinned to an on-demand model'
pi doctor >/dev/null 2>&1;                    check $? 'an on-demand pin is a note, not a doctor failure'
pi model glm glm-5.1 >/dev/null 2>&1
pi --no-verify model glm nope-9 >/dev/null 2>&1; check $? '--no-verify allows an unverifiable alias (offline escape hatch)'
pi model glm --unset >/dev/null 2>&1;         check $? 'a model override can be removed'
grep -q 'nope-9' <<< "$(pi dump)";            [[ $? -ne 0 ]]; check $? 'the removed override is really gone'
pi model 'Bad Family' glm-5.1 >/dev/null 2>&1; [[ $? -ne 0 ]]; check $? 'a malformed family name is refused'

# --- tiers ------------------------------------------------------------------------------------------
pi tier low deepseek mimo >/dev/null 2>&1;    check $? 'a tier roster can be set'
[[ "$(field tiers)" == '{"low": ["deepseek", "mimo"]}' ]]; check $? 'the roster is stored as a plain list'
pi tier low nosuch >/dev/null 2>&1;           [[ $? -ne 0 ]]; check $? 'an unknown family in a tier is refused'
pi tier paranoid glm >/dev/null 2>&1;         [[ $? -ne 0 ]]; check $? 'a fourth tier name is refused (low|med|high is fixed)'
pi tier med --kimi-cli on >/dev/null 2>&1;    check $? 'the Kimi CLI leaf can be switched on per tier'
grep -q '"kimiCli": true' <<< "$(pi dump)";   check $? 'the kimiCli switch is stored as an object field'
pi tier med --kimi off >/dev/null 2>&1;       [[ $? -ne 0 ]]; check $? 'the retired --kimi switch is rejected'
pi tier high --effort max >/dev/null 2>&1;    check $? 'synthesis effort can be set per tier'
pi tier high --effort ludicrous >/dev/null 2>&1; [[ $? -ne 0 ]]; check $? 'an invalid effort is refused'
pi tier low --unset >/dev/null 2>&1;          check $? 'a tier can be reset to its default'

# a family added via config must become usable in a tier — the "add a model we do not ship" path
pi model hy3 hy3 >/dev/null 2>&1
pi tier low hy3 deepseek >/dev/null 2>&1;     check $? 'a config-only family can be put in a tier'

# --- on-demand ---------------------------------------------------------------------------------------
pi ondemand kimi-k3 kimi-k2.6 >/dev/null 2>&1;    check $? 'an on-demand mapping can be changed'
pi ondemand kimi-k3 kimi-k3 >/dev/null 2>&1;      [[ $? -ne 0 ]]; check $? 'a model cannot stand in for itself'
pi ondemand kimi-k3 not-on-plan >/dev/null 2>&1;  [[ $? -ne 0 ]]; check $? 'an off-plan stand-in is refused'
pi ondemand kimi-k3 --unset >/dev/null 2>&1;      check $? 'an on-demand entry can be removed'

# --- doctor ------------------------------------------------------------------------------------------
pi reset >/dev/null 2>&1
pi doctor >/dev/null 2>&1;                    check $? 'doctor passes on a default (absent) config'
pi --no-verify model glm ghost-1 >/dev/null 2>&1
pi doctor >/dev/null 2>&1;                    [[ $? -ne 0 ]]; check $? 'doctor FAILS an alias that is not on the plan'
grep -q 'HANG' <<< "$(pi doctor 2>&1)";       check $? 'doctor explains the consequence (a hung leaf), not just "invalid"'
pi model glm --unset >/dev/null 2>&1
pi doctor >/dev/null 2>&1;                    check $? 'doctor passes again once the bad alias is removed'

printf '{ this is not json' > "${CFG}"
pi doctor >/dev/null 2>&1;                    [[ $? -ne 0 ]]; check $? 'doctor fails loudly on an unparseable config'
pi show >/dev/null 2>&1;                      [[ $? -ne 0 ]]; check $? 'a corrupt config is an error, never silently ignored'

# --- reset -------------------------------------------------------------------------------------------
pi reset >/dev/null 2>&1
[[ ! -f "${CFG}" ]];                          check $? 'reset with no key removes the whole file'
pi set tier low >/dev/null 2>&1
pi reset tier >/dev/null 2>&1
[[ "$(field tier)" == '""' ]];                check $? 'reset <key> drops just that key'

exit "${rc}"
