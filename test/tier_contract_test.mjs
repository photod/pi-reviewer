import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const workflow = read('plugin/workflows/pi-council.js')
const review = read('plugin/commands/pi-review.md')
const build = read('plugin/commands/pi-build.md')
const worker = read('plugin/agents/glm-worker.md')
const manifest = JSON.parse(read('plugin/.claude-plugin/plugin.json'))
const agentName = file => (read(`plugin/agents/${file}`).match(/^name:\s*(\S+)/m) || [])[1]

let ok = true
const check = (name, condition) => {
  console.log(`${condition ? 'PASS' : 'FAIL'} ${name}`)
  if (!condition) ok = false
}

check('review command exposes exact tiers', review.includes('[low|med(default)|high]'))
check('engine self-install refreshes on upgrade (not copy-if-absent)', review.includes('cmp -s') && review.includes('refresh it whenever'))
check('build command exposes exact tiers', build.includes('[low|med(default)|high]'))
check('workflow defaults to med', workflow.includes("A.tier || 'med'"))
check('workflow low panel preserved', workflow.includes("low:  { families: ['deepseek', 'mimo', 'qwen']"))
check('workflow med panel preserved', workflow.includes("med:  { families: ['glm', 'qwen', 'deepseek', 'kimicode'], kimiCli: false, effort: 'medium'"))
check('workflow high panel preserved', workflow.includes("high: { families: ['glm', 'qwen', 'minimax', 'deepseek', 'mimo', 'kimicode', 'hy']"))
check('workflow maps max/ultra aliases to high',
  workflow.includes("rawTier === 'max' || rawTier === 'ultra'") && workflow.includes('use low, med, or high'))
check('builder provider mapping is coherent',
  worker.includes('| **low** | `low` |') &&
  worker.includes('| **med** | `medium` |') &&
  worker.includes('| **high** | `high`'))
check('glm-worker model aliases stay in sync with the engine registry',
  worker.includes('opencode-go/glm-5.2') && worker.includes('opencode-go/qwen3.7-max') &&
  workflow.includes("glm:      'opencode-go/glm-5.2'") && workflow.includes("qwen:     'opencode-go/qwen3.7-max'"))

// --- pi-config.sh ↔ engine defaults ------------------------------------------
// pi-config.sh MIRRORS the engine's defaults because it must work standalone (before the plugin is
// installed, and offline). A mirror silently drifts — so compare them here, the same way
// scaffold_sync_test.mjs guards the embedded scaffolds. If this fails, the config tool is showing
// the operator a roster the council does not run.
const config = read('scripts/pi-config.sh')
const block = (src, re) => (src.match(re) || [])[1] || ''
const pairs = (src, re) => { const out = {}; for (const m of src.matchAll(re)) out[m[1]] = m[2]; return out }

const engineModels = pairs(block(workflow, /const BASE_MODELS = \{([\s\S]*?)\n\}/), /(\w+):\s*'opencode-go\/([^']+)'/g)
const configModels = pairs(block(config, /default_alias\(\) \{([\s\S]*?)\n\}/), /^\s+(\w+)\)\s+echo '([^']+)'/gm)
check('pi-config.sh model defaults match the engine registry',
  JSON.stringify(engineModels) === JSON.stringify(configModels))
check('pi-config.sh knows every engine family',
  Object.keys(engineModels).sort().join(' ') === block(config, /DEFAULT_FAMILIES="([^"]+)"/).split(/\s+/).sort().join(' '))

const engineTiers = pairs(block(workflow, /const BASE_TIERS = \{([\s\S]*?)\n\}/), /(\w+):\s*\{ families: \[([^\]]*)\]/g)
const configTiers = pairs(block(config, /default_tier\(\) \{([\s\S]*?)\n\}/), /^\s+(\w+)\)\s+echo '([^']+)'/gm)
check('pi-config.sh tier defaults match the engine tiers',
  Object.keys(engineTiers).length === 3 &&
  Object.keys(engineTiers).every(t =>
    engineTiers[t].replace(/['\s]/g, '').split(',').join(' ') === configTiers[t]))

const engineOnDemand = pairs(block(workflow, /const BASE_ON_DEMAND = \{([\s\S]*?)\n\}/), /'([^']+)':\s*'([^']+)'/g)
const configOnDemand = Object.fromEntries(block(config, /DEFAULT_ONDEMAND='([^']+)'/).split(/\s+/).map(p => p.split(':')))
check('pi-config.sh on-demand map matches the engine',
  JSON.stringify(engineOnDemand) === JSON.stringify(configOnDemand))
check('every on-demand stand-in is itself an auto model in the registry',
  Object.values(engineOnDemand).every(to => Object.values(engineModels).includes(to) && !engineOnDemand[to]))
check('no default tier seats an on-demand model',
  Object.values(engineTiers).every(fams => fams.replace(/['\s]/g, '').split(',')
    .every(f => !engineOnDemand[engineModels[f]])))

// The engine cannot check an alias against the live plan (no fs, no subprocess) — pi-config.sh is
// the ONLY validator, which is why the hard 6-model allowlist could be retired. Guard that story.
check('pi-config.sh verifies aliases against the live plan',
  config.includes('opencode models') && config.includes('< /dev/null') && config.includes('alias_on_plan'))
check('the oppy relay never substitutes a model it was not asked for',
  read('plugin/agents/oppy-reviewer.md').includes('NEVER substitute'))
check('config is documented as the way to change models (not editing the engine)',
  workflow.includes('Config, not sed.') && read('README.md').includes('pi-config'))

// --- Agent-type namespace contract -------------------------------------------
// A plugin's agents register as `<plugin.json name>:<agent frontmatter name>`; a bare `agentType`
// in the engine resolves to NOTHING under a plugin install, so every leaf returns UNAVAILABLE
// before a backend is contacted. Guard the whole chain: no bare literals, constants built from the
// caller-supplied prefix, agent names matching the shipped .md files, and the default prefix equal
// to this plugin's own name.
const agentTypes = [...workflow.matchAll(/agentType:\s*([^,}]+)/g)].map(m => m[1].trim())
// Three dispatch sites exactly: the oppy leaf fan-out, the Kimi CLI leaf, and the cheap chairman's
// synthesis. (It was four until the Go-plan Kimi stopped being a special-cased leaf and became the
// ordinary `kimicode` family, which rides the oppy fan-out.) A count of zero would mean the engine
// stopped dispatching by agentType at all — the regression this whole block exists to catch.
check('engine spawns every agent through an agentType constant', agentTypes.length === 3)
check('no engine agentType is a bare quoted literal (must go through AGENT_PREFIX)',
  agentTypes.every(t => t === 'OPPY_AGENT' || t === 'KIMI_AGENT'))
check('agent-type constants are built from the caller-supplied prefix',
  workflow.includes('const AGENT_PREFIX = normPrefix(A.agentPrefix)') &&
  workflow.includes('const OPPY_AGENT = `${AGENT_PREFIX}oppy-reviewer`') &&
  workflow.includes('const KIMI_AGENT = `${AGENT_PREFIX}kimi-reviewer`'))
check('engine agent names match the shipped agent files',
  agentName('oppy-reviewer.md') === 'oppy-reviewer' && agentName('kimi-reviewer.md') === 'kimi-reviewer')
// The regex above only sees `agentType:` spelled its way — `agentType : 'oppy-reviewer'` slips it.
// Backstop it from the other side: the engine must contain NO quoted agent-name literal at all (the
// two constants build their names with backticks off AGENT_PREFIX). test/agent_dispatch_test.mjs is
// the real guard — it runs the engine and inspects what it actually dispatches.
check('engine contains no quoted agent-name literal in any form',
  !/['"](oppy|kimi)-reviewer['"]/.test(workflow))
// The `agents=` log line is the diagnostic README.md and pi-review.md tell operators to check FIRST
// when a whole panel comes back UNAVAILABLE — a refactor must not silently drop or rename it.
check('engine logs the resolved namespace for diagnosis',
  workflow.includes('agents=${AGENT_PREFIX') && review.includes('agents=pi:') && read('README.md').includes('agents=pi:'))

// normPrefix is the one place a slip turns every leaf UNAVAILABLE again — test the real function,
// lifted out of the engine (the engine itself cannot be imported: top-level await + host globals).
const src = (workflow.match(/function normPrefix\(p\) \{[\s\S]*?\n\}/) || [])[0]
check('normPrefix is present in the engine', Boolean(src))
if (src) {
  const normPrefix = new Function(`${src}\nreturn normPrefix`)()
  check(`normPrefix defaults to the plugin's own namespace ('${manifest.name}:')`,
    normPrefix(undefined) === `${manifest.name}:` && normPrefix(null) === `${manifest.name}:`)
  check('normPrefix accepts a name with or without a trailing colon (never doubles it)',
    normPrefix('pi') === 'pi:' && normPrefix('pi:') === 'pi:' && normPrefix(' pi ') === 'pi:')
  check('normPrefix maps the bare sentinels to BARE agent names (manual install)',
    normPrefix('bare') === '' && normPrefix('none') === '' && normPrefix('BARE') === '' &&
    normPrefix('') === '' && normPrefix('  ') === '' && normPrefix(':') === '')
  // `agentPrefix=""` in $ARGUMENTS reaches the engine as the two-char string `""` — it must NOT
  // become the prefix `"":` (that is the very bug agentPrefix exists to fix, re-entering via the
  // escape hatch). Same for a quoted name.
  check('normPrefix survives quotes carried in from $ARGUMENTS',
    normPrefix('""') === '' && normPrefix("''") === '' && normPrefix('"pi"') === 'pi:')
}
check('review command tells the host to resolve the agent namespace',
  review.includes('agentPrefix') && review.includes('pi:oppy-reviewer'))
check('inline fallback path uses the resolved namespace, not bare agent names',
  review.includes('parallel `pi:oppy-reviewer` agents'))

process.exit(ok ? 0 : 1)
