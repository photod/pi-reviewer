#!/bin/bash
# pi-stage.sh <repo-dir> [subpath] — stage a MASKED copy of the pi-filelist.sh file list into a temp dir,
# so whole-repo reviewers read redacted files, never the raw source. Prints the temp-dir path on stdout.
#
# The source tree is NEVER modified — only the copy under the temp dir is masked. Fails CLOSED: if masking
# errors, the staging dir is removed and a non-zero exit tells the caller to ABORT (never forward raw code).
# Basic best-effort protection (common high-value keys), NOT a guarantee — see pi-mask.py / the README.
set -euo pipefail
umask 077  # snapshot dirs/files are owner-only (0700/0600) — they hold copies of your code

repo_dir="$1"
subpath="${2:-}"
here="$(cd "$(dirname "$0")" && pwd)"

# Snapshot root — where the MASKED copy is staged for reviewers to read. DEFAULT: an owner-only temp dir
# OUTSIDE the repo (${TMPDIR:-/tmp}/pireview), so the workdir path the models see carries NO username /
# home path — an in-repo "/Users/<you>/…/.pi-review/…" path would otherwise leak into every leaf prompt.
# Override with PI_SNAP_ROOT (e.g. PI_SNAP_ROOT="$repo/.pi-review" for the old in-repo, auditable-in-place
# behaviour). Namespaced by an OPAQUE sha256 of the absolute repo path: separates repos (so prune is
# per-repo) and keeps the visible path opaque. umask 077 above keeps every snapshot dir/file owner-only.
repo_abs="$(cd "$repo_dir" && pwd -P)"   # PHYSICAL path (symlinks resolved) — used for the under-repo check below
snap_base="${PI_SNAP_ROOT:-${TMPDIR:-/tmp}/pireview}"
repo_hash="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])' "$repo_abs")"
snaproot="$snap_base/$repo_hash"
mkdir -p "$snaproot"
# Self-ignore ONLY when the snapshot root lives inside the repo (opt-in in-repo mode) so it's never committed.
case "$snaproot/" in
  "$repo_abs"/*) printf '*\n' > "$snap_base/.gitignore" 2>/dev/null || true ;;
esac

# Keep snapshots bounded: discard anything outside the newest N, plus anything older than D days.
# Snapshot names carry the creation timestamp, so reverse lexical order is newest-first. `nullglob`
# makes an empty snapshot root a normal (and silent) case.
snap_keep="${PI_SNAP_KEEP:-10}"
snap_days="${PI_SNAP_DAYS:-7}"
case "$snap_keep" in
  ''|*[!0-9]*) printf 'pi-stage: PI_SNAP_KEEP must be a non-negative integer\n' >&2; exit 2 ;;
esac
case "$snap_days" in
  ''|*[!0-9]*) printf 'pi-stage: PI_SNAP_DAYS must be a non-negative integer\n' >&2; exit 2 ;;
esac
shopt -s nullglob
snapshots=( "$snaproot"/snap-* )
newest=()
newest_count=0
for snapshot in "${snapshots[@]:-}"; do
  [ -d "$snapshot" ] || continue
  inserted=0
  for ((index = 0; index < newest_count; index++)); do
    if [[ "$snapshot" > "${newest[index]}" ]]; then
      newest=( "${newest[@]:0:index}" "$snapshot" "${newest[@]:index}" )
      inserted=1
      newest_count=$((newest_count + 1))
      break
    fi
  done
  if [ "$inserted" -eq 0 ]; then
    newest+=( "$snapshot" )
    newest_count=$((newest_count + 1))
  fi
done
for ((index = snap_keep; index < newest_count; index++)); do
  rm -rf -- "${newest[index]}"
done
find "$snaproot" -mindepth 1 -maxdepth 1 -type d -name 'snap-*' -mtime +"$snap_days" -exec rm -rf -- {} +

ms="$(python3 -c 'import time; print(int(time.time()*1000))')"
stage="$snaproot/snap-${ms}-$$"
mkdir -p "$stage"
# Fail closed on INTERRUPT too: if we are killed between the raw copy and masking, the snapshot could hold
# raw (unmasked) files — remove it on any early exit/signal. Cleared only after masking succeeds.
trap 'rm -rf "$stage" 2>/dev/null' EXIT INT TERM

# Copy each listed (relative) file into the staging tree, preserving structure.
"$here/pi-filelist.sh" "$repo_dir" "$subpath" | grep -v '^#' > "$stage/.pi-filelist"

# Cheap, friendly disk precheck: sum the sizes of the files we're about to copy and compare to the free
# space at the snapshot root. Bail BEFORE copying anything if there isn't room — much friendlier than a
# half-written snapshot dying mid-copy on a cryptic ENOSPC.
need_kb=0
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  # Mirror the copy loop below: symlinks and non-regular files are NOT staged, so don't count them (and
  # skipping the symlink avoids a noisy redirection failure when it points at a nonexistent/outside target).
  [ -L "$repo_dir/$rel" ] && continue
  [ -f "$repo_dir/$rel" ] || continue
  sz="$(wc -c < "$repo_dir/$rel" 2>/dev/null || printf 0)"
  need_kb=$(( need_kb + (sz + 1023) / 1024 ))
done < "$stage/.pi-filelist"
avail_kb="$(df -Pk "$snap_base" 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt $(( need_kb + 4096 )) ]; then
  rm -rf "$stage"
  printf 'pi-stage: not enough free space to stage a masked copy — need ~%d KB under %s, only %d KB free.\n' "$need_kb" "$snap_base" "$avail_kb" >&2
  printf 'pi-stage: free some disk, or set PI_SNAP_ROOT to a roomier volume, then retry.\n' >&2
  exit 1
fi

while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  # Defence in depth: reject anything that isn't a clean relative path inside the repo. git ls-files
  # never emits these, but a hostile/edge fileList must not let a copy escape the tree.
  case "$rel" in
    /*|..|../*|*/..|*/../*) printf 'pi-stage: skipped unsafe path (not staged): %s\n' "$rel" >&2; continue ;;
  esac
  # SECURITY: never follow a symlink — it could resolve OUTSIDE the repo (e.g. a tracked link to
  # ~/.ssh/id_rsa) and exfiltrate its target into the snapshot. Skip it here, AND copy with -P so a
  # symlink swapped in AFTER this check (TOCTOU) is copied as a link, never dereferenced.
  if [ -L "$repo_dir/$rel" ]; then printf 'pi-stage: skipped symlink (not staged): %s\n' "$rel" >&2; continue; fi
  # Ancestor-symlink guard: resolve the FULL physical path and confirm it is still under the repo — catches
  # an ANCESTOR directory swapped to a symlink pointing outside (cp -P only protects the final component).
  # Both sides are physical/realpath'd, so a legitimately symlinked repo root (macOS /tmp -> /private/tmp)
  # does NOT false-positive. Narrows — does not fully close — the realpath->cp TOCTOU; unresolvable => skip.
  real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$repo_dir/$rel" 2>/dev/null || printf '')"
  case "${real}/" in
    "$repo_abs"/*) : ;;
    *) printf 'pi-stage: skipped path resolving OUTSIDE the repo (not staged): %s\n' "$rel" >&2; continue ;;
  esac
  dest="$stage/$rel"
  mkdir -p "$(dirname "$dest")"
  cp -P "$repo_dir/$rel" "$dest"
done < "$stage/.pi-filelist"
rm -f "$stage/.pi-filelist"
# TOCTOU backstop: drop any symlink that still reached the snapshot (swapped in between the -L check
# and cp -P) so no staged link can resolve to a raw file outside the masked tree.
find "$stage" -type l -delete

# Mask the COPIES in place; fail closed on any error.
if ! find "$stage" -type f -print0 | xargs -0 python3 "$here/pi-mask.py"; then
  rm -rf "$stage"
  printf 'pi-stage: masking failed — aborting (fail-closed), no raw code forwarded\n' >&2
  exit 1
fi

trap - EXIT INT TERM   # masking done — the snapshot is safe to keep and return
printf '%s\n' "$stage"
