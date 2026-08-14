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
check('med default panel is glm + qwen + deepseek + kimi',
  def.leaves.join(',') === 'opencode-go/glm-5.2,opencode-go/qwen3.7-max,opencode-go/deepseek-v4-pro,opencode-go/kimi-k2.7-code')
check('low default panel drops minimax and keeps deepseek',
  (await runEngine({ ...base, tier: 'low' })).leaves.join(',') ===
  'opencode-go/deepseek-v4-pro,opencode-go/mimo-v2.5-pro,opencode-go/qwen3.7-max')
check('high default panel is all six + kimi',
  (await runEngine({ ...base, tier: 'high' })).leaves.length === 6)
check('a clean run reports no downgrades in the footer',
  !def.result.coverage.includes('DOWNGRADED') && def.result.downgraded.length === 0)

// --- models overlay ------------------------------------------------------------------------------
// glm-5.1 rather than glm-5.3 on purpose: 5.3 is ON-DEMAND (it would be downgraded here, which is
// tested further down) — this case is about the plain overlay, so it needs an ordinary auto alias.
const bumped = await runEngine({ ...base, tier: 'med', models: { glm: 'glm-5.1' } })
check('models overlay repoints one family and leaves the rest alone',
  bumped.leaves.includes('opencode-go/glm-5.1') && bumped.leaves.includes('opencode-go/qwen3.7-max') &&
  !bumped.leaves.includes('opencode-go/glm-5.2'))
check('models overlay accepts a fully-qualified alias too',
  (await runEngine({ ...base, tier: 'med', models: { glm: 'opencode-go/glm-5.1' } })).leaves.includes('opencode-go/glm-5.1'))
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
check('tiers overlay can move the kimi leaf onto low',
  (await runEngine({ ...base, tier: 'low', tiers: { low: { families: ['glm'], kimi: true } } })).leaves.length === 2)
check('tiers overlay can turn the kimi leaf off at med',
  (await runEngine({ ...base, tier: 'med', tiers: { med: { families: ['glm'], kimi: false } } })).leaves.length === 1)
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
const ungated = await runEngine({ ...base, tier: 'med', models: { qwen: 'qwen3.8-max' } })
check('an unconfirmed on-demand model is downgraded, not run',
  ungated.leaves.includes('opencode-go/qwen3.7-max') && !ungated.leaves.includes('opencode-go/qwen3.8-max'))
check('the downgrade is visible in the coverage footer, not just the log',
  ungated.result.coverage.includes('DOWNGRADED') && ungated.result.coverage.includes('qwen3.8-max→qwen3.7-max'))
check('the downgrade is also a structured field on the result',
  ungated.result.downgraded.join(',') === 'qwen3.8-max→qwen3.7-max')

const consented = await runEngine({ ...base, tier: 'med', models: { qwen: 'qwen3.8-max' }, allowOnDemand: ['qwen3.8-max'] })
check('explicit per-run consent runs the real on-demand model',
  consented.leaves.includes('opencode-go/qwen3.8-max') && consented.result.downgraded.length === 0)
check('consent does not leak into the footer as a downgrade',
  !consented.result.coverage.includes('DOWNGRADED'))

check('kimi-k3 downgrades to the code-specialised K2.7 leaf',
  (await runEngine({ ...base, tier: 'med', models: { kimi: 'kimi-k3' } })).leaves.includes('opencode-go/kimi-k2.7-code'))

const grok = await runEngine({ ...base, tier: 'low', extraModels: ['grok-4.5'] })
check('an extra on-demand leaf without consent runs its stand-in (grok → luna)',
  grok.leaves.includes('opencode-go/gpt-5.6-luna') && !grok.leaves.includes('opencode-go/grok-4.5'))
check('extraModels adds a leaf ON TOP of the tier',
  grok.leaves.length === 4)
check('a confirmed extra leaf runs the real model',
  (await runEngine({ ...base, tier: 'low', extraModels: ['grok-4.5'], allowOnDemand: ['grok-4.5'] }))
    .leaves.includes('opencode-go/grok-4.5'))
check('an unknown extraModel throws rather than hanging a leaf on an off-plan alias',
  /unknown model/.test(await throws({ ...base, extraModels: ['gpt-9'] })))

// The chair reconciles the whole panel — an unconfirmed on-demand chairman must stand down too.
const chair = await runEngine({ ...base, tier: 'low', chairmanModel: 'grok-4.5' })
check('an unconfirmed on-demand chairman is downgraded to its stand-in',
  chair.result.chairman === 'opencode-go/gpt-5.6-luna')
check('a confirmed on-demand chairman is seated',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'grok-4.5', allowOnDemand: ['grok-4.5'] })).result.chairman ===
  'opencode-go/grok-4.5')
check('an Anthropic chairman is untouched by the gate',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'opus' })).result.chairman === 'opus')

check('a downgrade CHAIN in onDemand config throws (a stand-in must be an auto model)',
  /chain/.test(await throws({ ...base, onDemand: { 'glm-5.1': 'kimi-k3' } })))
check('an on-demand model standing in for itself throws',
  /itself|stand-in/.test(await throws({ ...base, onDemand: { 'glm-5.1': 'glm-5.1' } })))

// The flagship must not silently get more expensive: glm-5.3 is priced out of the flat plan, so it
// is on-demand and the chair/leaf fall back to 5.2 unless the operator confirms it for that run.
const glm53 = await runEngine({ ...base, tier: 'med', models: { glm: 'glm-5.3' } })
check('glm-5.3 is on-demand — a pinned glm-5.3 runs glm-5.2 instead',
  glm53.leaves.includes('opencode-go/glm-5.2') && !glm53.leaves.includes('opencode-go/glm-5.3'))
check('the glm downgrade is reported, not silent',
  glm53.result.coverage.includes('glm-5.3→glm-5.2'))
check('a confirmed glm-5.3 runs for real',
  (await runEngine({ ...base, tier: 'med', models: { glm: 'glm-5.3' }, allowOnDemand: ['glm-5.3'] }))
    .leaves.includes('opencode-go/glm-5.3'))
check('an unconfirmed glm-5.3 chairman stands down to glm-5.2',
  (await runEngine({ ...base, tier: 'low', chairmanModel: 'glm-5.3' })).result.chairman === 'opencode-go/glm-5.2')
check('pi.json can retire an on-demand entry by pointing a new one at an auto model',
  (await runEngine({ ...base, tier: 'low', models: { deepseek: 'deepseek-v4-flash' }, onDemand: { 'deepseek-v4-flash': 'deepseek-v4-pro' } }))
    .result.downgraded.join(',') === 'deepseek-v4-flash→deepseek-v4-pro')

// Consent for something that is not on-demand is harmless — it must NOT abort a review (config
// errors above DO throw; a stale per-run flag does not).
const stray = await runEngine({ ...base, tier: 'low', allowOnDemand: ['glm-5.2'] })
check('stray consent is noted and ignored, never fatal',
  stray.leaves.length === 3 && stray.logs.some(l => /allowOnDemand names non-on-demand/.test(l)))

// The panel roster must be legible without reading prompts — operators diagnose from this line.
check('the engine logs the resolved panel',
  def.logs.some(l => /^panel: /.test(l)) && def.result.panel.join(',') === 'glm-5.2,qwen3.7-max,deepseek-v4-pro')

process.exit(ok ? 0 : 1)
