import fs from 'node:fs'

// Guards the "Fable" review scaffold against drift. The canonical copy lives in
// recipes/reviewer.md between the PI-LEAF-SCAFFOLD markers; plugin/agents/kimi-reviewer.md
// embeds a verbatim copy so a STANDALONE kimi-reviewer run (outside /pi-review) applies the
// same discipline. If either is edited without the other, this fails — turning a hand-synced
// duplicate into a guarded one.
const read = p => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')
const START = '<!-- PI-LEAF-SCAFFOLD:START -->'
const END = '<!-- PI-LEAF-SCAFFOLD:END -->'

let ok = true
const check = (name, cond) => {
  console.log(`${cond ? 'PASS' : 'FAIL'} ${name}`)
  if (!cond) ok = false
}

const between = (text, label) => {
  const i = text.indexOf(START)
  const j = text.indexOf(END)
  check(`scaffold markers present in ${label}`, i !== -1 && j !== -1 && j > i)
  return i !== -1 && j !== -1 && j > i ? text.slice(i + START.length, j) : null
}

const recipe = between(read('recipes/reviewer.md'), 'recipes/reviewer.md')
const agent = between(read('plugin/agents/kimi-reviewer.md'), 'plugin/agents/kimi-reviewer.md')

check('recipe scaffold is non-trivial', (recipe?.length ?? 0) > 200)
check('agent scaffold matches recipes/reviewer.md (no drift)', recipe !== null && agent === recipe)

process.exit(ok ? 0 : 1)
