import fs from 'node:fs'

// Behavioural guard on the pi.json overlay: `models` / `tiers` / `onDemand` / `allowOnDemand` /
// `extraModels` reach the engine as ARGS (the engine has no filesystem — /pi-review reads the file
// and relays it). A string-scan cannot prove which model each leaf actually runs, so this runs the
// engine for real with stubbed host globals and reads the alias out of every prompt it dispatches.
//
// The stakes: a config the engine silently ignores looks identical to a config that worked, and a
// silently-substituted model corrupts the panel with a duplicate opinion wearing another label.
const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const src = read('plugin/workflows/pi-council.js').replace(/^export const meta/m, 'const meta')

let ok = true
const check = (name, condition) => {
  console.log(`${condition ? 'PASS' : 'FAIL'} ${name}`)
  if (!condition) ok = false
}

async function runEngine(args) {
  const calls = []
  const logs = []
  const agent = async (prompt, opts = {}) => {
    calls.push({ label: opts.label, model: (String(prompt).match(/Use model (\S+) via opencode/) || [])[1] })
    return '[nit] a.js:1 — stub finding → none'
  }
  const parallel = async thunks => Promise.all(thunks.map(t => t()))
  const engine = new Function('args', 'agent', 'parallel', 'log', 'phase',
    `return (async () => {\n${src}\n})()`)
  const result = await engine(args, agent, parallel, m => logs.push(String(m)), () => {})
  const leaves = calls.filter(c => String(c.label || '').startsWith('oppy:')).map(c => c.model)
  return { calls, logs, leaves, result }
}
const throws = async args => { try { await runEngine(args); return null } catch (e) { return String(e && e.message) } }

const base = { target: 'x', workdir: '/tmp/x' }

// --- Defaults ------------------------------------------------------------------------------------
const def = await runEngine({ ...base, tier: 'med' })
// deepseek is OFF by default (region-locked on the Go plan), so it is stripped from every tier -
// these are the EFFECTIVE panels. Flipping DEEPSEEK_ENABLED restores it; BASE_TIERS still lists it.
check('med default panel is glm53 + qwen-flash + kimicode + hy3, deepseek stripped',
  def.leaves.join(',') === 'opencode-go/glm-5.3,opencode-go/qwen3.8-flash,opencode-go/kimi-k2.7-code,opencode-go/hy3')
check('low default panel is the cheap arms, deepseek stripped',
  (await runEngine({ ...base, tier: 'low' })).leaves.join(',') ===
  'opencode-go/mimo-v2.5-pro,opencode-go/longcat-2.0')
check('no tier ships a deepseek leaf while the kill switch is off',
  !['low','med','high'].some(t => def.leaves.concat([]).some(l => l.includes('deepseek'))))
// The expensive flagship earns its slot ONLY at pre-release stakes. If it ever leaks into low or med,
// the council quietly gets several times more expensive per run.
check('qwen3.7-max is high-only',
  !(await runEngine({ ...base, tier: 'low' })).leaves.includes('opencode-go/qwen3.7-max') &&
  !def.leaves.includes('opencode-go/qwen3.7-max') &&
  (await runEngine({ ...base, tier: 'high' })).leaves.includes('opencode-go/qwen3.7-max'))
// pro at high, flash at low/med — two families precisely because one family is one alias.
// The family stays REGISTERED even while stripped from tiers, so a host can still name it explicitly.
check('deepseek is still a known family, just not in any tier',
  (await runEngine({ ...base, tier: 'low', tiers: { low: ['deepseek','mimo'] } })).leaves.includes('opencode-go/deepseek-v4-pro'))
check('hy runs GA hy3 at med and the PREVIEW only at high',
  def.leaves.includes('opencode-go/hy3') &&
  (await runEngine({ ...base, tier: 'high' })).leaves.includes('opencode-go/hy4-preview'))
check('high default panel is every family except luna and deepseek',
  (await runEngine({ ...base, tier: 'high' })).leaves.length === 6)
// kimicode is an ORDINARY family now — it must fan out through oppy like any other leaf, NOT through
// the kimi-reviewer CLI agent. If this ever regresses, the panel silently loses its Go-plan Kimi.
check('the Go-plan kimi rides the oppy path, not the CLI agent',
  def.leaves.includes('opencode-go/kimi-k2.7-code'))
// qwen3.7-plus is barred by NAME, while its siblings stay reachable — the bar must not overreach.
check('qwen3.7-plus never runs, at any tier, however it is reached',
  !(await runEngine({ ...base, tier: 'med', models: { qwenflash: 'qwen3.7-plus' } })).leaves.includes('opencode-go/qwen3.7-plus'))
check('consent does NOT unlock qwen3.7-plus',
  !(await runEngine({ ...base, tier: 'med', models: { qwenflash: 'qwen3.7-plus' }, allowOnDemand: ['qwen3.7-plus'] })).leaves.includes('opencode-go/qwen3.7-plus'))
check('barring qwen3.7-plus does not bar its siblings',
  def.leaves.includes('opencode-go/qwen3.8-flash') &&
  (await runEngine({ ...base, tier: 'high' })).leaves.includes('opencode-go/qwen3.7-max'))
check('a clean run reports no downgrades in the footer',
  !def.result.coverage.includes('DOWNGRADED') && def.result.downgraded.length === 0)

// --- models overlay ------------------------------------------------------------------------------
// Repoint `glm53`, not `glm`: glm is the CHAIRMAN family and sits in no tier, so overlaying it would
// prove nothing about leaves. glm-5.1 is an ordinary ungated alias, which is what this case needs.
const bumped = await runEngine({ ...base, tier: 'med', models: { glm53: 'glm-5.1' } })
check('models overlay repoints one family and leaves the rest alone',
  bumped.leaves.includes('opencode-go/glm-5.1') && bumped.leaves.includes('opencode-go/kimi-k2.7-code') &&
  !bumped.leaves.includes('opencode-go/glm-5.3'))
check('models overlay accepts a fully-qualified alias too',
  (await runEngine({ ...base, tier: 'med', models: { glm53: 'opencode-go/glm-5.1' } })).leaves.includes('opencode-go/glm-5.1'))
check('models overlay can introduce a NEW family usable in a tier',
  (await runEngine({ ...base, tier: 'low', models: { hy3: 'hy3' }, tiers: { low: ['hy3'] } })).leaves.join(',') === 'opencode-go/hy3')
check('two families on one alias throws (panel would run the same model twice)',
  /duplicate alias/.test(await throws({ ...base, models: { qwen: 'glm-5.2' } })))
check('a malformed alias throws instead of reaching a leaf',
  /invalid model alias/.test(await throws({ ...base, models: { glm: 'glm 5.3!' } })))
check('models given as a list, not an object, throws',
  /invalid 'models' config/.test(await throws({ ...base, models: ['glm-5.3'] })))

// --- tiers overlay -------------------------------------------------------------------------------
check('tiers overlay replaces a tier roster',
  (await runEngine({ ...base, tier: 'low', tiers: { low: ['glm', 'mimo'] } })).leaves.join(',') ===
  'opencode-go/glm-5.2,opencode-go/mimo-v2.5-pro')
// The CLI leaf is a kimi-reviewer agent, not an oppy leaf, so it never shows up in `leaves` — count
// the labelled call instead. That separation IS the feature: two Kimis, two routes, two labels.
const withCli = await runEngine({ ...base, tier: 'low', tiers: { low: { families: ['glm'], kimiCli: true } } })
check('kimiCli adds the CLI leaf without touching the oppy panel',
  withCli.leaves.join(',') === 'opencode-go/glm-5.2' &&
  withCli.calls.some(c => String(c.label || '').startsWith('kimi-cli:')))
check('the CLI leaf label names the model, so the chairman cannot confuse the two Kimis',
  withCli.calls.some(c => String(c.label || '') === 'kimi-cli:k3-256k'))
check('kimiCli is off in every shipped tier (it spends the operator personal quota)',
  !def.calls.some(c => String(c.label || '').startsWith('kimi-cli:')))
check('the retired per-tier kimi switch throws rather than moving the wrong leaf',
  /retired 'kimi' switch/.test(await throws({ ...base, tiers: { low: { families: ['glm'], kimi: true } } })))
check('the retired kimiMode arg throws rather than being silently ignored',
  /kimiMode' is retired/.test(await throws({ ...base, kimiMode: 'cli' })))
check('an unknown family in a tier throws (a leaf with no model)',
  /unknown model family/.test(await throws({ ...base, tiers: { low: ['nosuch'] } })))
check('an empty tier throws (a tier with no reviewers is not a review)',
  /NON-EMPTY/.test(await throws({ ...base, tiers: { low: [] } })))
check('inventing a fourth tier throws (low|med|high is the input contract)',
  /unknown tier/.test(await throws({ ...base, tiers: { paranoid: ['glm'] } })))
check('an invalid synthesis effort throws',
  /invalid effort/.test(await throws({ ...base, tiers: { low: { effort: 'ludicrous' } } })))

// --- on-demand gate ------------------------------------------------------------------------------
// The whole point: an on-demand model must NEVER run just because it is configured. Without per-run
// consent the council runs the stand-in AND says so — soft-degrade, never silent.
const ungated = await runEngine({ ...base, tier: 'med', models: { qwenflash: 'qwen3.8-max' } })
check('an unconfirmed on-demand model is downgraded, not run',
  ungated.leaves.includes('opencode-go/qwen3.7-max') && !ungated.leaves.includes('opencode-go/qwen3.8-max'))
check('the downgrade is visible in the coverage footer, not just the log',
  ungated.result.coverage.includes('DOWNGRADED') && ungated.result.coverage.includes('qwen3.8-max→qwen3.7-max'))
check('the downgrade is also a structured field on the result',
  ungated.result.downgraded.join(',') === 'qwen3.8-max→qwen3.7-max')

const consented = await runEngine({ ...base, tier: 'med', models: { qwenflash: 'qwen3.8-max' }, allowOnDemand: ['qwen3.8-max'] })
check('explicit per-run consent runs the real on-demand model',
  consented.leaves.includes('opencode-go/qwen3.8-max') && consented.result.downgraded.length === 0)
check('consent does not leak into the footer as a downgrade',
  !consented.result.coverage.includes('DOWNGRADED'))

// --- never on the Go plan (stronger than on-demand: consent cannot unlock it) ---------------------
check('kimi-k3 is substituted by the code-specialised K2.7 leaf',
  (await runEngine({ ...base, tier: 'med', models: { kimicode: 'kimi-k3' } })).leaves.includes('opencode-go/kimi-k2.7-code'))
check('the bar is by VENDOR, not by version — an unheard-of kimi is substituted too',
  (await runEngine({ ...base, tier: 'med', models: { kimicode: 'kimi-k9-turbo' } })).leaves.includes('opencode-go/kimi-k2.7-code'))
check('consent does NOT unlock a barred kimi',
  !(await runEngine({ ...base, tier: 'med', models: { kimicode: 'kimi-k3' }, allowOnDemand: ['kimi-k3'] }))
    .leaves.includes('opencode-go/kimi-k3'))
// The permitted member must stay runnable — otherwise the vendor rule would eat its own stand-in.
check('the permitted kimi is exempt from its own vendor rule',
  def.result.downgraded.length === 0)

const grok = await runEngine({ ...base, tier: 'low', extraModels: ['grok-4.6'] })
check('a barred grok leaf runs its stand-in (grok → luna)',
  grok.leaves.includes('opencode-go/gpt-5.6-luna') && !grok.leaves.includes('opencode-go/grok-4.6'))
check('extraModels adds a leaf ON TOP of the tier',
  grok.leaves.length === 3)
// The point of the whole table: --with is not a key to grok. A version bump must not become one either.
check('consent does NOT unlock grok — it is priced out of the Go plan, period',
  !(await runEngine({ ...base, tier: 'low', extraModels: ['grok-4.6'], allowOnDemand: ['grok-4.6'] }))
    .leaves.includes('opencode-go/grok-4.6'))
check('a NEWER grok is barred too — the rule names the vendor, not the version',
  !(await runEngine({ ...base, tier: 'low', extraModels: ['grok-5'], allowOnDemand: ['grok-5'] }))
    .leaves.includes('opencode-go/grok-5'))
check('a refused consent is reported, so --with never looks like it worked',
  (await runEngine({ ...base, tier: 'low', extraModels: ['grok-4.6'], allowOnDemand: ['grok-4.6'] }))
    .logs.some(l => /REFUSED/.test(String(l))))
check('a lookalike vendor is NOT caught by the bar (segment boundary, not prefix)',
  (await runEngine({ ...base, tier: 'low', models: { grokkish: 'grokkish-1' }, tiers: { low: ['grokkish'] } }))
    .leaves.join(',') === 'opencode-go/grokkish-1')
check('an unknown extraModel throws rather than hanging a leaf on an off-plan alias',
  /unknown model/.test(await throws({ ...base, extraModels: ['gpt-9'] })))

// The chair reconciles the whole panel — an unconfirmed on-demand chairman must stand down too.
const chair = await runEngine({ ...base, tier: 'low', chairmanModel: 'qwen3.8-max' })
check('an unconfirmed on-demand chairman is downgraded to its stand-in',
  chair.result.chairman === 'opencode-go/qwen3.7-max')
check('a confirmed on-demand chairman is seated',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'qwen3.8-max', allowOnDemand: ['qwen3.8-max'] })).result.chairman ===
  'opencode-go/qwen3.8-max')
check('a BARRED chairman stands down even when confirmed',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'grok-4.6', allowOnDemand: ['grok-4.6'] })).result.chairman ===
  'opencode-go/gpt-5.6-luna')
check('an Anthropic chairman is untouched by the gate',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'opus' })).result.chairman === 'opus')

check('a downgrade CHAIN in onDemand config throws (a stand-in must be an auto model)',
  /chain/.test(await throws({ ...base, onDemand: { 'glm-5.1': 'qwen3.8-max' } })))
// glm-5.3 was gated until 2026-09-02 and is now an ordinary leaf — this guards the un-gating.
check('glm-5.3 is NOT gated any more — it runs as the med/high leaf it is',
  def.leaves.includes('opencode-go/glm-5.3') && def.result.downgraded.length === 0)
check('a neverOnGo fallback that is itself on-demand throws',
  /always runs|on-demand/.test(await throws({ ...base, neverOnGo: { acme: 'qwen3.8-max' } })))
check('a neverOnGo fallback barred by ANOTHER vendor rule throws',
  /barred/.test(await throws({ ...base, neverOnGo: { acme: 'grok-9' } })))
check('an on-demand model standing in for itself throws',
  /itself|stand-in/.test(await throws({ ...base, onDemand: { 'glm-5.1': 'glm-5.1' } })))

// glm-5.3 was gated until 2026-09-02. It is now an ordinary leaf, and the chair may be seated on it
// without consent — the two assertions below are the ones that would fail if the gate crept back.
check('a glm-5.3 chairman is seated, not stood down',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'glm-5.3' })).result.chairman === 'opencode-go/glm-5.3')
check('the default chairman is still 5.2 — un-gating 5.3 must not move the chair',
  (await runEngine({ ...base, tier: 'low' })).result.chairman === 'opencode-go/glm-5.2')
check('pi.json can put a model back under the gate',
  (await runEngine({ ...base, tier: 'med', onDemand: { 'glm-5.3': 'glm-5.2' } }))
    .result.downgraded.join(',') === 'glm-5.3→glm-5.2')
check('pi.json can retire an on-demand entry by pointing a new one at an auto model',
  (await runEngine({ ...base, tier: 'low', onDemand: { 'mimo-v2.5-pro': 'longcat-2.0' } }))
    .result.downgraded.join(',') === 'mimo-v2.5-pro→longcat-2.0')

// Consent for something that is not on-demand is harmless — it must NOT abort a review (config
// errors above DO throw; a stale per-run flag does not).
const stray = await runEngine({ ...base, tier: 'low', allowOnDemand: ['glm-5.2'] })
check('stray consent is noted and ignored, never fatal',
  stray.leaves.length === 2 && stray.logs.some(l => /allowOnDemand names non-on-demand/.test(l)))

// The panel roster must be legible without reading prompts — operators diagnose from this line.
check('the engine logs the resolved panel',
  def.logs.some(l => /^panel: /.test(l)) && def.result.panel.join(',') === 'glm-5.3,qwen3.8-flash,kimi-k2.7-code,hy3')

// --- other providers ------------------------------------------------------------------------------
// The Go plan can be dry or region-gated; the council must be able to run where there IS credit.
const other = await runEngine({ ...base, tier: 'low', models: { mimo: 'opencode/mimo-v2.5-free' } })
check('a provider-qualified alias is honoured verbatim, not forced onto the Go plan',
  other.leaves.includes('opencode/mimo-v2.5-free'))
// kimi-for-coding/k3 is K3 on the operator's OWN subscription - a different account, so the Go-plan
// vendor bar must NOT follow it there. If this regresses, a paid-for model silently becomes k2.7-code.
check('the Go-plan kimi bar does NOT apply to another provider',
  (await runEngine({ ...base, tier: 'low', models: { mimo: 'kimi-for-coding/k3' } })).leaves.includes('kimi-for-coding/k3'))
check('a bare alias still resolves against the default provider',
  (await runEngine({ ...base, tier: 'low', models: { mimo: 'glm-5.1' } })).leaves.includes('opencode-go/glm-5.1'))

process.exit(ok ? 0 : 1)
