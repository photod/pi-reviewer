import fs from 'node:fs'

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const workflow = read('plugin/workflows/pi-council.js')
const review = read('plugin/commands/pi-review.md')
const build = read('plugin/commands/pi-build.md')
const worker = read('plugin/agents/glm-worker.md')
const codexReview = read('plugins/pi/skills/pi-review/SKILL.md')
const codexBuild = read('plugins/pi/skills/pi-build/SKILL.md')
const codexSetup = read('plugins/pi/skills/pi-setup/SKILL.md')
const piProfile = read('plugins/pi/profiles/pi.config.toml')
const codexRouter = read('plugins/pi/skills/pi/SKILL.md')
const codexLeaf = read('plugins/pi/agents/pi_oppy_reviewer.toml')

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
check('workflow maps max/ultra aliases to high',
  workflow.includes("rawTier === 'max' || rawTier === 'ultra'") && workflow.includes('use low, med, or high'))
check('builder provider mapping is coherent',
  worker.includes('| **low** | `low` |') &&
  worker.includes('| **med** | `medium` |') &&
  worker.includes('| **high** | `high`'))
check('Codex review forbids nested Codex',
  codexReview.includes('Never invoke `codex`, `codex exec`') && codexReview.includes('native subagent'))
check('Codex build forbids nested Codex',
  codexBuild.includes('Never invoke `codex`, `codex exec`') && codexBuild.includes('native Codex subagent'))
check('Codex external disclosure is gated',
  codexReview.includes('scope-specific consent') && codexBuild.includes('explicit current-request consent'))
check('Auto-review policy block is distinct',
  codexReview.includes('POLICY_BLOCKED') && !codexReview.includes('policy block as ordinary backend downtime'))
check('PI setup installs dedicated profile',
  codexSetup.includes('manage_profile.py install') && codexSetup.includes('codex -p pi --sandbox workspace-write'))
check('PI profile uses human approvals and scoped network',
  piProfile.includes('approvals_reviewer = "user"') &&
  piProfile.includes('sandbox_mode = "workspace-write"') &&
  piProfile.includes('network_access = true'))
check('Codex PI says the required consent aloud',
  codexRouter.includes('I consent to sharing the masked N-file snapshot') &&
  codexReview.includes('say the required sentence aloud') &&
  codexLeaf.includes('status: NEEDS_CONSENT'))
process.exit(ok ? 0 : 1)
