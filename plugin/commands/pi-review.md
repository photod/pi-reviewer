---
name: pi-review
description: Poor Intelligence — that's PI, not AI ;-). A code-review council of cheap opencode-go models instead of one pricey genius: they fan out in parallel, a glm-5.2 chairman reconciles ONE verdict. Run /pi-review [low|med|high] [target] [chairman] [kimiMode].
argument-hint: "[low|med(default)|high] [target] [chairman: glm-5.2(default)|opus|sonnet] [kimiMode: opencode(default)|cli|off]"
---

# /pi-review — Poor Intelligence code-review council

Run the tiered multi-model review council and hand back **one reconciled verdict** (severity-tagged
findings only). You orchestrate; you do NOT write the review yourself.

## Resolve config — standing host config FIRST, then per-call overrides

Reconfiguration lives in a config the command reads — NOT in per-call args (those are one-off overrides).
1. **Standing config:** if `~/.claude/pi.json` exists, read it for defaults — keys: `tier`, `chairman`,
   `kimiMode`, `edition`. This is where a host is set up ONCE (e.g. `{"kimiMode":"cli"}` to use the native
   Kimi CLI instead of opencode-go kimi). **No file → built-in defaults** (the fridge still works):
   `tier=med`, `chairman=glm-5.2`, `kimiMode=opencode`.
2. **Per-call overrides:** parse `$ARGUMENTS` and let them override the config for THIS run only — a tier
   keyword (`low`/`med`/`high`), a target (path/glob/`diff`/`branch`; default `git diff HEAD`), a chairman
   (`opus`/`sonnet`/an `opencode-go/<alias>`), a `kimiMode` (`opencode`/`cli`/`off`).

Tiers: `low` = 3 cheap models · `med` = glm + qwen + kimi (default) · `high` = all 6 + high-effort synth.
Kimi is a leaf at med/high only; `kimiMode` picks its backend (opencode-go by default, native CLI, or off).

## Execute — self-bootstrapping, single engine

0. **Preflight — `opencode` is REQUIRED.** Run `command -v opencode`. If it's missing, STOP (do not
   run the council) and show the operator this — opencode + an opencode-go plan is the engine PI runs on:
   > **PI needs the `opencode` CLI + an opencode-go plan** to run the council (it's a required prerequisite).
   > - https://opencode.ai/go?ref=RWGQD6Q9RA — **referral link: you get $5 credit and PI's author gets $5** (disclosed openly; use it if you're happy to).
   > - https://opencode.ai/go — plain link, no referral.
   >
   > Install opencode, then re-run `/pi-review`.
   (If opencode IS present but a leaf later errors on auth/plan, that surfaces as an `UNAVAILABLE` leaf
   with the real error — a different problem, not this preflight.)

1. **Ensure the engine is installed.** If `~/.claude/workflows/pi-council.js` does NOT exist but
   `${CLAUDE_PLUGIN_ROOT}/workflows/pi-council.js` does (fresh plugin install), copy the latter to the
   former (`mkdir -p ~/.claude/workflows` first). This self-installs the workflow — there is NO manual step.
2. **Whole-repo access — pick a MODE, then build the input.** ONLY for a whole-repo / bare-directory
   target; a diff / branch / named-file target skips this entirely and is UNCHANGED. An explicit
   `mode=yolo|curated|list|pack` in `$ARGUMENTS` overrides; otherwise **auto-triage**:
   - Task names specific files or an area → **`curated`**: YOU pick the relevant files as `fileList`, and
     tell reviewers *"if you hit a reference to a file NOT in this list that you need, NAME it in your
     findings"* (miss-recovery — recovers exactly the file the orchestrator failed to include).
   - Else run `fileList=$("${CLAUDE_PLUGIN_ROOT}/scripts/pi-filelist.sh" <workdir> [subpath])` and read its
     `# N files` count: **≤50 → `list`** (pass that fileList) · **>50 → `pack`**.
   - **`pack` = offer-first repomix:** if `command -v repomix` OR `command -v npx` succeeds, **ASK the
     operator before running** (`repomix` or `npx repomix` — respects `.gitignore`, runs `secretlint`),
     then review the pack. On decline, OR if neither is available → **degrade to `list`** (capped) and say
     so in one line. NEVER run repomix silently.
   - **`yolo`** (explicit-only, never auto): pass NO `fileList` — the leaf reviews the whole `--dir`
     unbounded. Riskiest (cost/leakage); only when the operator asks for it.
   `pi-filelist.sh` prints one path per line + `#`-comment footers (pi-council.js ignores `#` lines);
   capture the dropped-count from its `# dropped:` footer if present. Track the chosen `mode` for step 3.
   - **Mask before sending (`list` / `curated`).** Stage a REDACTED copy so reviewers never see raw
     secrets: `staged=$("${CLAUDE_PLUGIN_ROOT}/scripts/pi-stage.sh" <workdir> [subpath])`, then pass
     `workdir=$staged` to the workflow (the staged tree holds masked copies; the same relative `fileList`
     resolves inside it). `pi-stage.sh` fails CLOSED — a non-zero exit means masking failed, so ABORT the
     run rather than send raw code. This is **best-effort** masking of common high-value keys, NOT a
     guarantee. `pack` relies on repomix's own `secretlint`; **`yolo` sends raw** (no masking — that's the
     trade the operator opted into).
     **Once per repo, after masking succeeds:** if `"<workdir>/.pi-review/.pi-hinted"` is absent, tell the
     operator: **PI staged a redacted copy in `.pi-review/snap-.../` before sending code; nothing raw left
     the repo for this whole-repo review. Preview any file with `pi-mask.py --preview <path>`; toggle masked
     secret domains/countries in `pi-mask.config.json`.** Then create that marker file. If it exists, stay
     silent.
3. **Run it** by scriptPath (never by name — name-invocation can hit a stale registration):
   ```
   Workflow({
     scriptPath: "~/.claude/workflows/pi-council.js",
     args: { tier, target, workdir: <cwd or the target's dir>, chairmanModel, kimiMode, mode, ...(fileList ? {fileList} : {}), ...(dropped ? {dropped} : {}) }
   })
   ```
   Pass `mode` (diff/feature/list/pack/curated/yolo — default `diff` for non-whole-repo) so the coverage
   footer is accurate. Each model runs as its own single-model leaf, coached with the embedded reviewer
   scaffold + lenses; a dead leaf becomes a visible `UNAVAILABLE` record; the chairman reconciles at the tier's effort.
4. **Relay the reconciled verdict — and ALWAYS show its final `coverage:` line** (the workflow appends it
   even on a clean run: e.g. `coverage: list · 3/3 leaves OK · reviewed 16 files`). Surface any
   `UNAVAILABLE`/`PARTIAL` leaves and any degrade note honestly so coverage stays truthful — soft-degrade
   is fine, silent is not.
5. **If the engine file is genuinely absent** (not a plugin install, copy failed): run the tier inline as a
   fallback — parallel `oppy-reviewer` agents (one `-m opencode-go/<alias>` each; + a `kimi-reviewer` at
   med/high when `kimiMode:cli`), then an Opus synthesis. Tell the operator once that it ran in fallback mode.
