#!/bin/bash
# pi-filelist.sh — enumerate a capped, denylist-filtered list of TRACKED files for a repo/subpath.
#
# Usage: pi-filelist.sh <repo-dir> [subpath]
#
# Output (stdout): one file path per line, then a final summary comment line "# <n> files".
# If the list exceeds ${PI_MAXFILES:-150}, only the FIRST N surviving paths are kept and a
# "# dropped: <K> files (cap <N>)" footer line is ALSO printed (after the file list, before
# the summary). Any line beginning with "#" is a comment/footer — callers may strip those
# to obtain a clean path list.
#
# Fails CLOSED: a non-git <repo-dir> prints to stderr and exits non-zero. Enumerates TRACKED plus
# UNTRACKED-not-ignored files (git ls-files --cached --others --exclude-standard), so new/uncommitted
# work is reviewed while .gitignore is still respected. A denylist (case-INSENSITIVE glob match) then
# strips secret-pattern, vendor, build, lockfile, minified, and binary paths.
set -euo pipefail
shopt -s nocasematch  # denylist matches regardless of case (deploy.KEY, secret.PEM, …)

if [ $# -lt 1 ]; then
  printf 'usage: pi-filelist.sh <repo-dir> [subpath]\n' >&2
  exit 2
fi

repo_dir="$1"
subpath="${2:-}"

if ! git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'error: %s is not a git repo\n' "$repo_dir" >&2
  exit 1
fi

# --- Enumerate tracked + untracked-not-ignored files -------------------------
# --cached --others --exclude-standard = committed AND new files, minus .gitignored (so fresh
# work is reviewed too). core.quotePath=false keeps non-ASCII paths literal (no octal escaping).
if [ -n "$subpath" ]; then
  candidates="$(git -c core.quotePath=false -C "$repo_dir" ls-files --cached --others --exclude-standard -- "$subpath")"
else
  candidates="$(git -c core.quotePath=false -C "$repo_dir" ls-files --cached --others --exclude-standard)"
fi

# --- Denylist filter (case-INSENSITIVE glob match on the full path) ----------
# Patterns are matched as glob against the whole path (case_fold_/_down); basename-only
# patterns are appended both as bare-name globs to catch the file regardless of dir.
denylist_paths=(
  '.env*'
  '*.pem'
  '*.key'
  '*.p12'
  'id_rsa*'
  '*credentials*'
  '*secret*'
  'node_modules/'
  'node_modules/*'
  '.venv/'
  '.venv/*'
  'vendor/'
  'vendor/*'
  'dist/'
  'dist/*'
  'build/'
  'build/*'
  '*.min.js'
  '*-lock.json'
  'package-lock.json'
  '*.lock'
  '*.png'
  '*.jpg'
  '*.pdf'
  '*.zip'
  '*.so'
  '*.bin'
)

is_denied() {
  local p="$1"
  local pat
  for pat in "${denylist_paths[@]}"; do
    # shellcheck disable=SC2254  # intentional glob match
    case "$p" in
      $pat) return 0 ;;
    esac
  done
  return 1
}

kept=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  if ! is_denied "$line"; then
    kept+=("$line")
  fi
done <<<"$candidates"

# --- Cap (env-overridable, default 150) --------------------------------------
max="${PI_MAXFILES:-150}"
total="${#kept[@]}"
dropped=0
out=()
if [ "$max" -ge 0 ] && [ "$total" -gt "$max" ]; then
  for ((i = 0; i < max; i++)); do
    out+=("${kept[$i]}")
  done
  dropped=$((total - max))
else
  if [ "$total" -gt 0 ]; then
    out=("${kept[@]}")
  fi
fi

# --- Emit --------------------------------------------------------------------
if [ "${#out[@]}" -gt 0 ]; then
  for p in "${out[@]}"; do
    printf '%s\n' "$p"
  done
fi
if [ "$dropped" -gt 0 ]; then
  printf '# dropped: %d files (cap %d)\n' "$dropped" "$max"
fi
printf '# %d files\n' "${#out[@]}"
