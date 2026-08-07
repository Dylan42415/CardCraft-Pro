# Development Workflow

For every task, in order:

1. **Understand the problem** — restate it, note what's ambiguous.
2. **Inspect existing code** — read before writing; don't assume structure.
3. **Identify affected modules** — list files/components that will change.
4. **Plan changes** — short `step → verify` plan (see `Coding_Standards.md`).
5. **Explain the plan** — surface it before implementing anything non-trivial.
6. **Implement incrementally** — small verifiable steps, not one large diff.
7. **Validate** — run/describe the verification for each step in the plan.
8. **Update documentation** — architecture, decision log, changelog, technical
   debt, as relevant (see `Context_Engineering.md` for what counts as
   "significant work").
9. **Summarize completed work** — what changed, what was verified, what's left.

## When this can be skipped
Trivial, obviously-scoped changes (typo fixes, one-line config tweaks) can
skip straight to implementation — see the tradeoff note in
`Coding_Standards.md`.
