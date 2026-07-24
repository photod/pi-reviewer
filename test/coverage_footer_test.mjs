// Unit test of coverageLine() — EXTRACTED from pi-council.js at runtime so this test can never DRIFT
// from the real function (K3 dogfood: a hand-copied duplicate silently diverges). The footer must be
// NON-EMPTY in every case (soft-degrade, never silent).
import fs from 'node:fs'
const _src = fs.readFileSync(new URL('../plugin/workflows/pi-council.js', import.meta.url), 'utf8')
const _m = _src.match(/function coverageLine\([\s\S]*?\n\}/)
if (!_m) { console.log('FAIL could not extract coverageLine from pi-council.js'); process.exit(1) }
const coverageLine = new Function('return (' + _m[0] + ')')()

let ok = true
const check = (name, cond) => { if (!cond) { ok = false; console.log(`FAIL ${name}`) } else console.log(`PASS ${name}`) }

// (a) clean full panel
const a = coverageLine({ mode: 'med', ok: 3, total: 3, unavailable: [], files: 0, dropped: 0 })
check('clean: non-empty', a.length > 0)
check('clean: 3/3 leaves OK', a.includes('3/3 leaves OK'))
check('clean: no UNAVAILABLE noise', !a.includes('UNAVAILABLE'))

// (b) one UNAVAILABLE
const b = coverageLine({ mode: 'med', ok: 2, total: 3, unavailable: ['deepseek'], files: 0, dropped: 0 })
check('degraded: names the leaf', b.includes('deepseek') && b.includes('UNAVAILABLE'))
check('degraded: 2/3', b.includes('2/3 leaves OK'))

// (c) whole-repo with dropped files
const c = coverageLine({ mode: 'list', ok: 3, total: 3, unavailable: [], files: 150, dropped: 230 })
check('whole-repo: reviewed count', c.includes('reviewed 150 file'))
check('whole-repo: dropped count', c.includes('dropped 230'))

// footer is never empty regardless of input
check('never empty', coverageLine({ mode: 'yolo', ok: 1, total: 1, unavailable: [], files: 0, dropped: 0 }).length > 0)

console.log(ok ? '\nALL PASS' : '\nSOME FAILED')
process.exit(ok ? 0 : 1)
