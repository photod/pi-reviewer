import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const workflow = read('plugin/workflows/pi-council.js')
const review = read('plugin/commands/pi-review.md')
const build = read('plugin/commands/pi-build.md')
const worker = read('plugin/agents/glm-worker.md')

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
process.exit(ok ? 0 : 1)
