import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const workflow = read('plugin/workflows/pi-council.js')
const review = read('plugin/commands/pi-review.md')
const build = read('plugin/commands/pi-build.md')
const worker = read('plugin/agents/glm-worker.md')
const codexReview = read('plugins/pi/skills/pi-review/SKILL.md')
const codexBuild = read('plugins/pi/skills/pi-build/SKILL.md')

let ok = true
const check = (name, condition) => {
  console.log(`${condition ? 'PASS' : 'FAIL'} ${name}`)
  if (!condition) ok = false
}

check('review command exposes exact tiers', review.includes('[low|med(default)|high]'))
check('build command exposes exact tiers', build.includes('[low|med(default)|high]'))
check('workflow defaults to med', workflow.includes("A.tier || 'med'"))
check('workflow low panel preserved', workflow.includes("low:  { families: ['minimax', 'deepseek', 'mimo']"))
check('workflow med panel preserved', workflow.includes("med:  { families: ['glm', 'qwen'], kimi: true, effort: 'medium'"))
check('workflow high panel preserved', workflow.includes("high: { families: ['glm', 'qwen', 'minimax', 'deepseek', 'mimo']"))
check('workflow rejects aliases', !workflow.includes("rawTier === 'max'") && workflow.includes('use low, med, or high'))
check('builder provider mapping is coherent',
  worker.includes('| **low** | `low` |') &&
  worker.includes('| **med** | `medium` |') &&
  worker.includes('| **high** | `high`'))
check('Codex review forbids nested Codex',
  codexReview.includes('Never invoke `codex`, `codex exec`') && codexReview.includes('native subagent'))
check('Codex build forbids nested Codex',
  codexBuild.includes('Never invoke `codex`, `codex exec`') && codexBuild.includes('native Codex subagent'))
check('Codex external disclosure is gated',
  codexReview.includes('explicit consent') && codexBuild.includes('explicit current-request consent'))

process.exit(ok ? 0 : 1)
