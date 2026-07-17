# Repository rules

- Use Python 3.12 and the dependency versions declared in `pyproject.toml`.
- Treat `ok-kes` only as a behavioral reference; do not copy its handler chain into this repository.
- Keep `ok-script` calls inside `src/tasks/ChaosTask.py`. Code under `src/chaos/` must remain independently testable.
- One task tick means one OCR snapshot, one page decision, and at most one action.
- The card catalog supports character-owned cards only. Do not add neutral-card or monster-card definitions.
- Card samples remain pending until a human reviews them. Never auto-promote OCR output into `data/cards/`.
- Passive card collection is one captured frame, one OCR pass, and zero game actions.
- Automated card collection may navigate only a positively identified card list/detail loop. Take a fresh frame before
  every action, perform at most one action per transition, and stop immediately when post-action verification fails.
- Page handlers must have unique IDs, explicit priorities, positive tests, and confusing-page negative tests.
- Unknown or ambiguous pages must not click. Never add destructive actions without dedicated recognition and confirmation tests.
- Run `python -m ruff check .` and `python -m pytest` before handing off changes.
