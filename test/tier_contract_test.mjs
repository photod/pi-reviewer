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
check('workflow low panel preserved', workflow.includes("low:  { families: ['minimax', 'deepseek', 'mimo']"))
check('workflow med panel preserved', workflow.includes("med:  { families: ['glm', 'qwen'], kimi: true, effort: 'medium'"))
check('workflow high panel preserved', workflow.includes("high: { families: ['glm', 'qwen', 'minimax', 'deepseek', 'mimo']"))
check('workflow maps max/ultra aliases to high',
  workflow.includes("rawTier === 'max' || rawTier === 'ultra'") && workflow.includes('use low, med, or high'))
check('builder provider mapping is coherent',
  worker.includes('| **low** | `low` |') &&
  worker.includes('| **med** | `medium` |') &&
  worker.includes('| **high** | `high`'))
check('glm-worker model aliases stay in sync with the engine registry',
  worker.includes('opencode-go/glm-5.2') && worker.includes('opencode-go/qwen3.7-max') &&
  workflow.includes("glm:      'opencode-go/glm-5.2'") && workflow.includes("qwen:     'opencode-go/qwen3.7-max'"))

// --- Agent-type namespace contract -------------------------------------------
// A plugin's agents register as `<plugin.json name>:<agent frontmatter name>`; a bare `agentType`
// in the engine resolves to NOTHING under a plugin install, so every leaf returns UNAVAILABLE
// before a backend is contacted. Guard the whole chain: no bare literals, constants built from the
// caller-supplied prefix, agent names matching the shipped .md files, and the default prefix equal
// to this plugin's own name.
const agentTypes = [...workflow.matchAll(/agentType:\s*([^,}]+)/g)].map(m => m[1].trim())
check('engine spawns at least one agent by agentType', agentTypes.length >= 4)
check('no engine agentType is a bare quoted literal (must go through AGENT_PREFIX)',
  agentTypes.every(t => t === 'OPPY_AGENT' || t === 'KIMI_AGENT'))
check('agent-type constants are built from the caller-supplied prefix',
  workflow.includes('const AGENT_PREFIX = normPrefix(A.agentPrefix)') &&
  workflow.includes('const OPPY_AGENT = `${AGENT_PREFIX}oppy-reviewer`') &&
  workflow.includes('const KIMI_AGENT = `${AGENT_PREFIX}kimi-reviewer`'))
check('engine agent names match the shipped agent files',
  agentName('oppy-reviewer.md') === 'oppy-reviewer' && agentName('kimi-reviewer.md') === 'kimi-reviewer')

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
