// Unit test of coverageLine() — mirrors the pure function in pi-council.js.
// The footer must be NON-EMPTY in every case (soft-degrade, never silent).
function coverageLine({ mode, ok, total, unavailable, files, dropped }) {
  let s = `coverage: ${mode} · ${ok}/${total} leaves OK`
  if (unavailable && unavailable.length) s += ` · ${unavailable.length} UNAVAILABLE (${unavailable.join(', ')})`
  if (files) s += ` · reviewed ${files} file(s)`
  if (dropped) s += `, dropped ${dropped}`
  return s
}

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
