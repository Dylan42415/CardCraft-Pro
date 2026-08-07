# Context Engineering

Documentation is part of the codebase, not an afterthought. It must never go
stale.

## What counts as "significant work" (triggers a doc update)
- A new module, pipeline stage, or PySide6 Desktop Application view is added.
- A dependency is added, removed, or swapped.
- An architectural decision is made or reversed.
- A design assumption changes (e.g. vault-only storage → hybrid DB).
- A known limitation or piece of technical debt is introduced or resolved.

## What to update, and where
| Change type                        | File(s) to update                     |
|------------------------------------|----------------------------------------|
| System/component structure         | `Architecture.md`                      |
| New/changed engineering decision   | `Decision_Log.md`                      |
| Shipped change (user-facing)       | `Changelog.md`                         |
| Known shortcut / deferred cleanup  | `Technical_Debt.md`                    |
| Vault note schema / graph rules    | `Knowledge_Graph_Architecture.md`      |
| PDF pipeline internals             | `PDF_Ingestion.md`                     |
| SVG Vector Textures pipeline internals         | `SVG Vector Textures_System.md`                    |
| Test coverage/strategy             | `Testing.md`                           |
| What worked / didn't                | `Lessons_Learned.md`                   |
| Future plans                       | `Roadmap.md`                           |

## Rule
Each fact lives in exactly one file. If two docs would say the same thing,
one of them should link to the other instead of repeating it.
