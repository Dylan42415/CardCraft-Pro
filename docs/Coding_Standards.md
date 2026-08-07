# Coding Standards

These apply to all code (agent-written or human-written) in this repo.
Adapted from the Karpathy-inspired guidelines the project follows.

## 1. Think before coding
- State assumptions explicitly instead of silently picking one interpretation.
- If genuinely ambiguous, ask rather than guess.
- Surface tradeoffs and simpler alternatives before implementing the complex path.

## 2. Simplicity first
- Write the minimum code that solves the stated problem — nothing speculative.
- No config/flexibility that wasn't asked for.
- No error handling for scenarios that can't occur here.
- If it could be 1/4 the length, rewrite it shorter.

## 3. Surgical changes
- Touch only what the task requires. Don't reformat or "improve" adjacent code.
- Match existing style even if you'd personally do it differently.
- Remove imports/variables your own change orphaned; leave pre-existing dead
  code alone (flag it in `Technical_Debt.md` instead of deleting it).

## 4. Goal-driven execution
- Turn vague tasks into verifiable ones: "add validation" → "write tests for
  invalid inputs, then make them pass."
- For multi-step work, state a short plan as `Step → verify: check` before
  implementing.

## Python conventions
- Python 3.11+, type hints on all public functions.
- `black` + `ruff` for formatting/linting.
- One module = one responsibility (e.g. `ingestion/pdf/docling_parser.py`,
  not a catch-all `utils.py`).
- Docstrings on public functions/classes: purpose, args, returns.

## Naming
- No renaming public APIs silently — see `Repository_Rules.md`.
- Vault note filenames: `snake_case`, derived from source document title/ID.
