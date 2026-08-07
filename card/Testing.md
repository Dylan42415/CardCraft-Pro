# Testing

## Approach
Tests should exist where they catch real regressions cheaply — not for
coverage's own sake (see `Coding_Standards.md`: no error handling/tests for
impossible scenarios).

## Layers
- **Unit tests** — parsers (PDF extraction functions, SVG Vector Textures validators),
  vault note generation (frontmatter/schema correctness), chunking logic.
- **Integration tests** — a small fixture PDF and a small fixture SVG Vector Textures
  file run through the full pipeline; assert the expected notes/links appear
  in a scratch vault.
- **Manual QA** — periodic spot-check of the actual vault graph in Obsidian
  for correctness (broken links, duplicate notes, mis-linked concepts) —
  automating this fully isn't practical short-term.

## Fixtures
Keep a small `tests/fixtures/` set (1-2 representative PDFs with tables, 1-2
small SVG Vector Textures files) rather than testing against full NEA production data.

## Definition of done (per `Development_Workflow.md` step 7)
A change is validated when: unit tests pass, the integration fixture run
produces the expected vault diff, and no existing test regressed.
