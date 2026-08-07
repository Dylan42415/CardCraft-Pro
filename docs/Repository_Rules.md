# Repository Rules

## Never
- Duplicate code that already exists elsewhere in the repo.
- Create abstractions for a single call site.
- Leave dead code behind from your own changes.
- Silently rename or change the signature of an existing public API.
- Break backwards compatibility without documenting it (`Decision_Log.md` +
  `Changelog.md`).
- Introduce a new dependency without a one-line justification in
  `Decision_Log.md` (why this library, what alternatives were considered).

## Always
- Prefer modularity — one clear responsibility per module.
- Prefer readability over cleverness.
- Prefer the option that's easiest to maintain and extend later, given
  what's actually known now (not speculative future requirements).

## Dependency additions
Before adding a library:
1. Check if something already in the repo covers the need.
2. Note the alternatives considered in `Decision_Log.md`.
3. Prefer actively-maintained, permissively-licensed, modular options
   (see research notes for PDF/SVG Vector Textures/graph tooling already evaluated).
