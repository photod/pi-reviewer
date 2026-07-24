# PI review lenses — the canned set

Ten baked review angles. The point: a careless or non-expert user runs `/pi-review` and gets expert-grade
lenses applied *for* them — the lens does the thinking. **P.I. for non-I.**

> **Source of truth:** these lenses are EMBEDDED as the `LENSES` map in
> `plugin/workflows/pi-council.js` (a Workflow has no filesystem access, so it can't read this file at
> runtime). The 5 **default** lenses are always injected into every leaf; the 5 **on-demand** ones are
> added when the `/pi-review` command passes `args.lenses = ['security', …]` (via `--lens <name>`). This
> file is the human-readable copy — to change behavior, edit the `LENSES` map in
> `plugin/workflows/pi-council.js` and copy it to the installed `~/.claude/workflows/pi-council.js`.

- **Default set** (always applied, no thought required): Contradiction, Feasibility, Human,
  Negative-Space, Failure-Modes. These are the five that catch the bugs that actually hurt.
- **On-demand** (aim one by name, e.g. `/pi-review --lens security`): UX, Blast-Radius, Security,
  Simplicity, Honesty.

Each lens is a self-contained instruction handed to a reviewer. Tone is fixed: sharp, specific,
brutal, laconic — cite the exact spot, give a one-line fix, no praise.

---

## DEFAULT — always on

### 1. Contradiction
> Find where two parts of this can't both be true: a rule that contradicts an example, a tool list
> that doesn't match the described workflow, a guarantee undercut three sections later, a default
> that violates a stated constraint. For each, quote **both** sides and name which one is wrong.

### 2. Feasibility
> Trace every mechanism end to end as if you have to implement it tomorrow. Where does a step
> silently fail, race, hang, or assume something unproven? Name the exact step that breaks and what
> it assumed. "It should work" is not an answer — show the path or show the hole.

### 3. Human
> There is a human at the end of this chain who asked for it. Does this actually serve *them*? Flag
> every place it optimizes for cleverness, completeness, or the machine's convenience over the
> person's real need — and every place a normal person would look at it and just say "…why?" Missing
> common sense counts as a defect. If the human was forgotten, that's the most important finding here.

### 4. Negative Space
> Review what ISN'T here. The unhandled error branch, the missing test, the absent edge case, the
> requirement stated but never satisfied, the failure mode never mentioned, the empty/first-run/
> nothing-configured state nobody designed. List what *should* exist and doesn't.

### 5. Failure Modes
> Assume this WILL fail — enumerate how: empty input, huge input, concurrent runs, network dies
> mid-call, dependency missing, quota exhausted, malformed/encoded data, clock skew. For each, does
> it fail **loud and safe** or **silent and dangerous**? The silent-dangerous ones are critical.

---

## ON-DEMAND — aim by name

### 6. UX
> Walk through this as the actual user, click by click / step by step. Where's the friction, the
> state where they don't know what just happened or what to do next, the silent failure, the knob
> they should never have had to touch, the error message that explains nothing? Rank by how often a
> real user hits it.

### 7. Blast Radius
> What downstream breaks if this ships? Enumerate dependents — callers, consumers, serialized
> formats, queue messages, other services, existing user workflows, scheduled jobs. Which change
> that looks like a local edit is secretly a **migration** because meaning crosses a boundary?

### 8. Security
> What crosses a trust boundary — secrets, PII, untrusted input, third-party transmission, elevated
> permission? Find every **overclaim** ("safe", "guaranteed", "can't happen") that reality doesn't
> back. State the concrete worst case if an attacker or an accidental leak hits this exact spot.

### 9. Simplicity
> What can be deleted with no loss? Over-engineering, speculative generality, a knob nobody asked
> for, a layer that adds no value, scope that betrays the core purpose. For each, argue the simpler
> version — and if you can't, say the complexity is earned.

### 10. Honesty
> Extract every claim this makes and check it against reality. Mark each: **true** / **best-effort
> sold as guarantee** / **unverified** / **false**. Pay special attention to confident language with
> nothing behind it — fluency is not evidence. The dangerous claim is the one a user will *trust*.
