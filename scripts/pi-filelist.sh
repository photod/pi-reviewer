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

# --- Denylist filter (case-INSENSITIVE glob match on the full path AND basename) ----------
# Each pattern is glob-matched against BOTH the whole path and the basename, so a nested
# secret file (backend/.env, config/id_rsa) is caught regardless of directory depth.
denylist_paths=(
  # === Secret / credential files ===
  # env & package-manager auth
  '.env*'
  '*.env'
  '*.env.*'
  '.netrc' '_netrc' '*.netrc'
  '.npmrc' '.pypirc' '.git-credentials'
  '.htpasswd' '*.htpasswd'
  '.dockercfg' '.docker/config.json' '*/.docker/config.json' '.docker/*' '*/.docker/*'
  '.pgpass' '.my.cnf' '.boto' '.s3cfg' '.terraformrc'
  # private keys & keystores
  '*.pem' '*.key' '*.p12' '*.pfx' '*.jks' '*.keystore' '*.keytab'
  '*.ppk' '*.p8' '*.kdbx'
  'id_rsa*' 'id_ed25519*' 'id_ecdsa*' 'id_dsa*'
  '*.gpg' '*.asc' '*.age'
  # cloud / CI / infra credentials (depth forms so nested dirs are caught too)
  '.ssh/' '.ssh/*' '*/.ssh/*'
  '.gnupg/' '.gnupg/*' '*/.gnupg/*'
  '.aws/' '.aws/*' '*/.aws/*'
  '.azure/' '.azure/*' '*/.azure/*'
  '.kube/' '.kube/*' '*/.kube/*'
  'kubeconfig' 'kubeconfig.*' '*.kubeconfig'
  '.config/gcloud/' '.config/gcloud/*' '*/.config/gcloud/*'
  '*service-account*.json' '*serviceaccount*.json'
  '.terraform/' '.terraform/*' '*/.terraform/*'
  '*.tfstate' '*.tfstate.backup' '*.tfplan'
  '*.ovpn' '*.mobileprovision'
  # shell/REPL history (untracked-not-ignored files leak typed secrets)
  '.bash_history' '.zsh_history' '.python_history'
  '.psql_history' '.mysql_history' '.irb_history' '.node_repl_history'
  # convention-based encrypted blobs
  '*.enc' '*.encrypted'
  # broad substring globs — KEPT deliberately (fail-closed); known casualties:
  # secret_manager.py, credentials.py, docs/credentials.md — privacy over completeness
  '*secret*'
  '*credentials*'

  # === Binary / non-text assets ===
  # images
  '*.png' '*.jpg' '*.jpeg' '*.gif' '*.ico' '*.webp' '*.bmp' '*.tiff'
  '*.heic' '*.heif' '*.avif' '*.psd' '*.ai' '*.icns' '*.cur'
  '*.tga' '*.dds' '*.exr' '*.ktx' '*.ktx2'
  # media
  '*.mp3' '*.mp4' '*.wav' '*.mov' '*.avi' '*.webm'
  '*.flac' '*.ogg' '*.opus' '*.m4a' '*.m4v' '*.mkv' '*.wmv' '*.aiff' '*.aac'
  # fonts
  '*.woff' '*.woff2' '*.ttf' '*.otf' '*.eot' '*.ttc'
  # archives & packages
  '*.zip' '*.gz' '*.tgz' '*.tar' '*.bz2' '*.xz' '*.7z' '*.rar'
  '*.zst' '*.lz4' '*.lzma' '*.cab' '*.cpio'
  '*.iso' '*.img' '*.dmg' '*.apk' '*.aab' '*.ipa'
  '*.deb' '*.rpm' '*.msi' '*.pkg' '*.appimage'
  '*.jar' '*.war' '*.whl' '*.egg' '*.gem' '*.nupkg' '*.vsix'
  # compiled / object files
  '*.so' '*.o' '*.a' '*.dylib' '*.dll' '*.exe' '*.bin'
  '*.class' '*.wasm' '*.pyc' '*.pyo' '*.pyd'
  '*.lib' '*.obj' '*.pdb' '*.ilk' '*.exp' '*.ko'
  '*.gch' '*.pch' '*.rlib' '*.beam' '*.elc' '*.luac' '*.dex' '*.mo'
  '*.gcda' '*.gcno' '*.profraw' '*.profdata'
  '*.nib' '*.car'
  # databases & sidecars
  '*.sqlite' '*.sqlite3' '*.db' '*.mdb' '*.accdb' '*.duckdb' '*.realm'
  '*.frm' '*.ibd' '*.mdf' '*.ldf' '*.rdb'
  '*-wal' '*-shm'
  # binary office documents
  '*.pdf' '*.doc' '*.docx' '*.xls' '*.xlsx' '*.ppt' '*.pptx'
  '*.odt' '*.ods' '*.odp' '*.pages' '*.numbers'
  # other non-text blobs
  '.DS_Store' '*.lnk' '*.der'

  # === Vendor / build / generated / lockfiles / minified ===
  # vendor & dependency dirs (depth forms: nested trees leak otherwise)
  'node_modules/' 'node_modules/*' '*/node_modules/*'
  'bower_components/' 'bower_components/*' '*/bower_components/*'
  'vendor/' 'vendor/*' '*/vendor/*'
  'Pods/' 'Pods/*' '*/Pods/*'
  # build output dirs
  'dist/' 'dist/*' '*/dist/*'
  'build/' 'build/*' '*/build/*'
  'target/' 'target/*' '*/target/*'
  'out/' 'out/*' '*/out/*'
  'obj/' 'obj/*' '*/obj/*'
  '.next/' '.next/*' '*/.next/*'
  '.nuxt/' '.nuxt/*' '*/.nuxt/*'
  '.gradle/' '.gradle/*' '*/.gradle/*'
  # language envs & caches
  '.venv/' '.venv/*' '*/.venv/*'
  'venv/' 'venv/*' '*/venv/*'
  '.tox/' '.tox/*' '*/.tox/*'
  '__pycache__/' '__pycache__/*' '*/__pycache__/*'
  '*.egg-info/' '*.egg-info/*'
  '.pytest_cache/' '.pytest_cache/*'
  '.mypy_cache/' '.mypy_cache/*'
  '.ruff_cache/' '.ruff_cache/*'
  '.cache/' '.cache/*' '*/.cache/*'
  '.parcel-cache/' '.parcel-cache/*'
  'coverage/' 'coverage/*' '*/coverage/*'
  # lockfiles
  '*.lock'
  '*-lock.json'          # package-lock.json, etc.
  '*.lock.json'          # packages.lock.json (NuGet)
  'npm-shrinkwrap.json'
  '*-lock.yaml' '*-lock.yml'   # pnpm-lock.yaml
  '*.lock.hcl'                 # .terraform.lock.hcl
  'go.sum' 'bun.lockb'
  # minified & bundled
  '*.min.js' '*.min.css' '*-min.js' '*-min.css'
  '*.map'
  '*.bundle.js' '*.bundle.css' '*.chunk.js' '*.chunk.css'
  # logs: text, but machine-noise + frequent secret spillage
  '*.log'
)

is_denied() {
  local p="$1"
  local base="${p##*/}"
  local pat
  for pat in "${denylist_paths[@]}"; do
    # shellcheck disable=SC2254  # intentional glob match
    case "$p" in
      $pat) return 0 ;;
    esac
    # shellcheck disable=SC2254  # intentional glob match
    case "$base" in
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
