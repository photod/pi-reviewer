import fs from 'node:fs'

// Behavioural guard on WHICH agentType the engine actually dispatches.
//
// The sibling string-scan in tier_contract_test.mjs proves the SOURCE contains no bare literal; it
// cannot prove the RUNTIME dispatch is namespaced. Its regex has real false-pass modes — a call site
// written `agentType : 'oppy-reviewer'` (space before the colon) evades it entirely while the four
// legitimate matches keep the count and the every() green, and a locally shadowed
// `const OPPY_AGENT = 'oppy-reviewer'` would pass every textual check ever written.
//
// So: run the engine for real with stubbed host globals and record every agentType it asks for. The
// engine cannot be imported (top-level await/return, host-provided globals), so it is wrapped exactly
// as the host wraps it — an async function receiving `args`/`agent`/`parallel`/`log`.
const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const src = read('plugin/workflows/pi-council.js').replace(/^export const meta/m, 'const meta')

let ok = true
const check = (name, condition) => {
  console.log(`${condition ? 'PASS' : 'FAIL'} ${name}`)
  if (!condition) ok = false
}

async function runEngine(args) {
  const dispatched = []
  const agent = async (_prompt, opts = {}) => {
    dispatched.push(opts.agentType)
    return '[nit] a.js:1 — stub finding → none'   // non-empty and not UNAVAILABLE, so synthesis proceeds
  }
  const parallel = async thunks => Promise.all(thunks.map(t => t()))
  const log = () => {}
  const phase = () => {}
  const engine = new Function('args', 'agent', 'parallel', 'log', 'phase', `return (async () => {\n${src}\n})()`)
  const result = await engine(args, agent, parallel, log, phase)
  return { dispatched, result }
}

// `high` + kimiCli exercises every dispatch path at once: the high-tier oppy leaves, the separate Kimi
// CLI leaf, and the cheap chairman's synthesis call (which routes through oppy too). Six, not seven:
// deepseek ships OFF (region-locked on the Go plan), so it is stripped from the default tiers.
const HIGH_OPPY_LEAVES = 6
const base = { tier: 'high', tiers: { high: { kimiCli: true } }, target: 'x', workdir: '/tmp/x' }

const plugin = await runEngine({ ...base })
check('default install dispatches ONLY namespaced agent types',
  plugin.dispatched.length > 0 && plugin.dispatched.every(t => t === 'pi:oppy-reviewer' || t === 'pi:kimi-reviewer'))
check('every leaf AND the chairman are dispatched (high + kimiCli = 7 + 1 + 1)',
  plugin.dispatched.length === HIGH_OPPY_LEAVES + 2)
check('the kimi CLI leaf is dispatched namespaced too',
  plugin.dispatched.includes('pi:kimi-reviewer'))
check('a full panel produces a synthesis (stubbed leaves are usable)',
  Boolean(plugin.result && plugin.result.synthesis) && plugin.result.unavailable.length === 0)

const bare = await runEngine({ ...base, agentPrefix: 'bare' })
check('agentPrefix=bare dispatches ONLY unprefixed agent types',
  bare.dispatched.length === HIGH_OPPY_LEAVES + 2 && bare.dispatched.every(t => t === 'oppy-reviewer' || t === 'kimi-reviewer'))

const quoted = await runEngine({ ...base, agentPrefix: '"pi"' })
check('a quote-wrapped prefix from $ARGUMENTS still dispatches namespaced',
  quoted.dispatched.every(t => t.startsWith('pi:')))

// A prefix that cannot be a plugin name must fail LOUDLY at parse time, not turn into a panel of
// UNAVAILABLE leaves the operator has to diagnose.
let threw = null
try { await runEngine({ ...base, agentPrefix: 'pi pro' }) } catch (e) { threw = e }
check('a malformed agentPrefix throws instead of silently dispatching nothing',
  Boolean(threw) && /invalid agentPrefix/.test(String(threw && threw.message)))

// The opencode chairman path is the one that reuses the oppy agent for synthesis; an Anthropic
// chairman must NOT be dispatched through an agentType at all (it uses the model option instead).
const opusChair = await runEngine({ ...base, chairmanModel: 'opus' })
check('an Anthropic chairman is not dispatched through a plugin agentType',
  opusChair.dispatched.filter(t => t === undefined).length === 1)

process.exit(ok ? 0 : 1)
