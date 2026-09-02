---
name: pi-review
description: Poor Intelligence, not AI ;-) — a council of cheap opencode-go models fans out; a glm-5.2 chairman reconciles ONE verdict.
argument-hint: "[low|med(default)|high] [target] [chairman: glm-5.2(default)|opus|sonnet] [--with <on-demand alias>] [agentPrefix: pi(default)|bare]"
---

# /pi-review — Poor Intelligence code-review council

Run the tiered multi-model review council and hand back **one reconciled verdict** (severity-tagged
findings only). You orchestrate; you do NOT write the review yourself.

## Resolve config — standing host config FIRST, then per-call overrides

Reconfiguration lives in a config the command reads — NOT in per-call args (those are one-off overrides).
1. **Standing config:** if `~/.claude/pi.json` exists, read it for defaults — keys: `tier`, `chairman`,
   `kimiCliModel`, plus the registry overlays `models`, `tiers`, `onDemand`. This is where a host is set up
   ONCE (e.g. `{"tiers":{"high":{"kimiCli":true}}}` to add the Kimi CLI leaf, or
   `{"models":{"minimax":"minimax-m2.7"}}` to pin a model). **No file → built-in defaults** (the fridge still
   works): `tier=med`, `chairman=glm-5.2`, `kimiCliModel=kimi-code/k3-256k`, shipped registry and rosters.
   - Pass `models` / `tiers` / `onDemand` straight through in the Workflow args, unchanged — the engine
     validates them and fails LOUD on anything malformed. Do NOT silently drop a key you do not
     recognise and do NOT "fix" a value: a config the run ignored looks exactly like one that worked.
   - **If the file does not parse, ABORT** with the parse error and point at `/pi-config doctor`.
     Never fall back to defaults on a corrupt config — the operator would get a panel they did not ask
     for and no signal that their settings were skipped.
   - Editing that file by hand is supported but unnecessary: **`/pi-config`** (or
     `${CLAUDE_PLUGIN_ROOT}/scripts/pi-config.sh`) owns validation, including checking every alias
     against the live plan. Never edit the engine to change a model — step 3 overwrites it.
2. **Per-call overrides:** parse `$ARGUMENTS` and let them override the config for THIS run only — a tier
   keyword (`low`/`med`/`high`), a target (path/glob/`diff`/`branch`; default `git diff HEAD`), a chairman
   (`opus`/`sonnet`/an `opencode-go/<alias>`), an explicit
   `agentPrefix=<pi|bare>` (escape hatch for step 3's namespace resolution — see there), and any number of
   on-demand review **lenses** via `--lens <name>` or `lens=<name>` (repeatable, e.g. `--lens security
   --lens ux`). Collect them into a `lenses` array passed in the Workflow args (below); the engine adds
   them on top of the always-on default lenses and ignores unknown names with a note. Valid on-demand
   lenses: `ux`, `blastradius`, `security`, `simplicity`, `honesty` (see `lenses.md`).
2b. **On-demand models (`--with <alias>`, repeatable).** Some models are opt-in per run — never
   automatic — because of cost/quota/policy (`glm-5.3`, `qwen3.8-max`, `kimi-k3`, `grok-4.6` by default; the map
   lives in pi.json `onDemand`). `--with` is a REQUEST, not the consent. Before passing it on:
   - **Get the operator's explicit confirmation in THIS run** (AskUserQuestion, or an unambiguous
     yes already in their message). A standing config can NEVER grant this — that is precisely why
     no such key exists. If you cannot ask, do NOT consent: pass the model and let it downgrade.
   - On confirmation pass BOTH `extraModels: ["<alias>"]` (add the leaf) and
     `allowOnDemand: ["<alias>"]` (the consent). Without the second the engine runs the model's
     stand-in and reports the swap in the coverage footer — soft-degrade, never silent.
   - Same gate for a chairman or a configured family that resolves to an on-demand model:
     `allowOnDemand` is the only unlock, and only for that one run.

Tiers (DEFAULTS — reconfigurable per host in pi.json, see `/pi-config`): `low` = deepseek + mimo +
qwen · `med` (default) = glm + qwen + deepseek + kimicode · `high` = all six + high-effort synth.
(`max` / `ultra` are accepted as aliases for `high` — people forget which word is the top.)

## Housekeeping asks (preview masking) — handle in chat, no council

If the request is about the MASKER rather than a review ("preview what you'd mask in X", "what would
you redact"), handle it right here — do NOT run a review: run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pi-mask.py" --preview <paths>` on the paths the operator
named and relay the output (what would be redacted, line by line). This is local-only — nothing is
staged or sent anywhere. (If an operator explicitly asks to change WHICH domains get masked, a
repo-root `pi-mask.config.json` — created from the bundled `scripts/pi-mask.config.example.json` —
toggles `groups.<name>` / `national_ids.<CC>` booleans; nobody should have to touch it otherwise.)
TWO different Kimis, deliberately kept apart. `kimicode` is the Go-plan `kimi-k2.7-code` — an ORDINARY
family, in med/high like any other, running through `oppy-reviewer`. The `kimi-reviewer` agent is a
SEPARATE leaf running K3 (`kimi-code/k3-256k`) on the operator's own Kimi subscription; it is off in
every shipped tier and switched on per tier with `kimiCli`. Both may run at once — that buys
availability (two quota pools), not vendor diversity: they are both Moonshot, so weigh them as one
vendor's voice. Panel labels keep them apart: `kimi-k2.7-code` vs `kimi-cli:k3-256k`.

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

1. **Ensure the engine is installed AND up to date.** The engine runs from
   `~/.claude/workflows/pi-council.js`. Install it on first run and **refresh it whenever the plugin's
   bundled copy differs** — otherwise a `/plugin update` never takes effect and you stay pinned to the
   version you first installed (copy-if-absent was the old, un-upgradable behaviour). Run:
   `mkdir -p ~/.claude/workflows && (cmp -s "${CLAUDE_PLUGIN_ROOT}/workflows/pi-council.js" ~/.claude/workflows/pi-council.js || cp -f "${CLAUDE_PLUGIN_ROOT}/workflows/pi-council.js" ~/.claude/workflows/pi-council.js)`
   — `cmp` is silent when they already match (no copy); on any difference (an upgrade) or a missing file
   it copies the plugin's canonical copy over. There is NO manual step. Never hand-edit the installed
   copy — the plugin dir is the source of truth and the installed file is overwritten on any version change.
1b. **First run ever — advertise the extras ONCE.** If `~/.claude/.pi-welcomed` is absent, show the
   operator this one screen (then create that marker file and never repeat it):
   > **PI, first run — what's in the box:**
   > - Tiers `low|med|high` — and `max`/`ultra` if you forget which word is the top; optional
   >   `[target] [chairman]` per run.
   > - **`/pi-config`** — change anything for good: which models the panel runs, who reviews at each
   >   tier, whether the Kimi CLI leaf joins, who chairs. `/pi-config doctor` checks it all against your
   >   live plan.
   > - **Masking is ON at every scope** — diffs, named files, and whole repos all go through the
   >   secret masker before any model sees your code. Only an explicit `mode=yolo` sends raw.
   > - Ask in chat: *"what would PI mask in `<path>`?"* — instant preview, nothing is sent.
   > - `/pi-build` — the companion builder: small, test-driven changes from the same cheap panel.
2. **Masking is the DEFAULT at every scope.** The only unmasked mode is an explicit `mode=yolo` —
   the operator's opt-in trade. Build the (masked) input by target shape:
   - **Diff / branch target (the default).** Materialize the diff, mask the TEXT, and review the
     masked artifact — the leaves must never re-fetch the raw diff:
     ```
     snap="<workdir>/.pi-review/snap-$(date +%Y%m%d-%H%M%S)" && mkdir -p "$snap" &&
     git diff HEAD | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pi-mask.py" - > "$snap/diff.patch"
     ```
     (For a branch target, diff that branch range instead.) `pi-mask.py` fails CLOSED — a non-zero
     exit means masking failed, so ABORT the run rather than send the raw diff. Then run the workflow
     with `workdir=$snap`, `mode=diff`, and `target` set to: *"the masked diff at diff.patch — review
     ONLY that file; do NOT run git diff or read other repo files — this masked copy IS the whole
     input."* (Leaves lose surrounding-repo context on a masked diff — that is the price of masking;
     say so in one honest line if the operator asks.)
   - **Named-file target.** Treat it as `curated`: build fileList from exactly those files and stage
     them through `pi-stage.sh` as below.
   - **Whole-repo / bare-directory target — pick a MODE, then build the input.** An explicit
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
       unbounded. Riskiest (cost/leakage); the ONLY mode that sends raw source.
   `pi-filelist.sh` prints one path per line + `#`-comment footers (pi-council.js ignores `#` lines);
   capture the dropped-count from its `# dropped:` footer if present. Track the chosen `mode` for step 3.
   - **Stage before sending (`list` / `curated` / named files).** Stage a REDACTED copy so reviewers
     never see raw secrets: `staged=$("${CLAUDE_PLUGIN_ROOT}/scripts/pi-stage.sh" <workdir> [subpath])`,
     then pass `workdir=$staged` to the workflow (the staged tree holds masked copies; the same relative
     `fileList` resolves inside it). `pi-stage.sh` fails CLOSED — a non-zero exit means masking failed, so
     ABORT the run rather than send raw code. This is **best-effort** masking of common high-value keys,
     NOT a guarantee. `pack` relies on repomix's own `secretlint`.
     **Once per repo, after masking succeeds:** if `"<workdir>/.git/pi-review-hinted"` is absent (a marker
     inside `.git`, so it is never committed), tell the operator: **PI staged a redacted copy OUTSIDE your
     repo (default `${TMPDIR:-/tmp}/pireview/<hash>/`, owner-only — set `PI_SNAP_ROOT` to relocate, e.g. to
     `.pi-review/` in the repo for in-place auditing) before sending code; nothing raw was sent. Masking
     stays on at every scope (explicit `mode=yolo` sends raw); ask in chat "what would PI mask in
     `<path>`?" to preview any file.** Then create that marker file. If it exists, stay silent.
3. **Resolve the agent namespace, then run it** by scriptPath (never by name — name-invocation can hit
   a stale registration). Claude registers a plugin's agents **namespaced** (`pi:oppy-reviewer`), but a
   manual install (agent `.md` files in `~/.claude/agents/`) registers them **bare** — and the engine
   cannot see the agent registry, only you can. So look at YOUR available agent types and set
   `agentPrefix`: `"pi"` if `pi:oppy-reviewer` is listed (the normal plugin install — this is also the
   default if you omit the arg), `"bare"` if only an unprefixed `oppy-reviewer` is listed. Get this wrong and every
   leaf comes back `UNAVAILABLE` before a backend is ever contacted — the engine reports the namespace it
   used in its first log line (`agents=pi:`), so check that line first if the whole panel is UNAVAILABLE.
   An explicit `agentPrefix=…` in `$ARGUMENTS` overrides this detection (operator escape hatch). `bare`
   and `none` are RESERVED words meaning "no namespace"; anything that isn't a plausible plugin name is
   rejected with a loud error rather than becoming a prefix that matches no agent.
   ```
   Workflow({
     scriptPath: "~/.claude/workflows/pi-council.js",
     args: { tier, target, workdir: <cwd or the target's dir>, chairmanModel, mode, agentPrefix, ...(kimiCliModel ? {kimiCliModel} : {}), ...(models ? {models} : {}), ...(tiers ? {tiers} : {}), ...(onDemand ? {onDemand} : {}), ...(extraModels && extraModels.length ? {extraModels} : {}), ...(allowOnDemand && allowOnDemand.length ? {allowOnDemand} : {}), ...(fileList ? {fileList} : {}), ...(dropped ? {dropped} : {}), ...(lenses && lenses.length ? {lenses} : {}) }
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
   fallback — parallel `pi:oppy-reviewer` agents (one `-m opencode-go/<alias>` each; + a `pi:kimi-reviewer`
   running `kimi -m kimi-code/k3-256k` for any tier with `kimiCli:true`), then an Opus synthesis. Use the **same namespace you resolved in step
   3** — `pi:`-prefixed when installed as this plugin, bare (`oppy-reviewer` / `kimi-reviewer`) when the
   agents were installed standalone. Tell the operator once that it ran in fallback mode.
