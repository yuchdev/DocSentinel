# Task 03 — Register `lenz`; declare `httpx` as a direct dependency

**Parent story:** [Story 03.0](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 02](./02-lenz-client-implementation.md).

## Goal

Connect `LenzFactCheckClient` to the Story 01.0 registry so that `load_backend("lenz")` returns it.
Declare `httpx` as a direct dependency (owner ruling D6). `import docsentinel` and every fast and
standard scan must still never import `httpx`. A gate-closed deep scan must never import
`docsentinel.fact_check.lenz` (it may import `httpx` through spaCy; amended 2026-11-24, egress
threat model E13).

## Inputs

- Story README decisions [U4 and U8](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md#decisions);
  plan [exit gate 3](/docs/roadmap/0010-fact-check/plan.md#exit-gates); ruling D6 in
  [status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions).
- [Story 01.0 Task 04](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/04-factcheckclient-protocol-and-data-contracts.md)
  (`FACT_CHECK_BACKEND_MODULES`, `FACT_CHECK_BACKENDS`, `load_backend`).
- `/pyproject.toml` and `/uv.lock`. `httpx` 0.28.1 is already in the lock as a transitive dependency.

## Steps

1. At the end of `fact_check/lenz.py`, add `FACT_CHECK_BACKENDS[LenzFactCheckClient.name] = LenzFactCheckClient`.
   Check that `FACT_CHECK_BACKEND_MODULES["lenz"] == "docsentinel.fact_check.lenz"`.
   Do not import the module from `/src/docsentinel/fact_check/__init__.py` (which imports nothing,
   plan contract C9) or from `/src/docsentinel/detectors/__init__.py`. Only `load_backend` imports
   it, and only after the gate is open.
2. In `/pyproject.toml` `dependencies`, add `"httpx>=0.28,<1"` under a `# deep profile (DS302
   fact-check backend)` comment, next to `spacy` and `textacy`. Use the existing comment style. Do
   not add it to the `fast`, `standard` or `deep` extras. Those extras are aliases and stay empty.
3. Run `uv lock`. The lock should change only in the root package's dependency metadata. Check that
   `uv sync --locked --extra test --extra standard --extra deep` succeeds.
   *Amended 2026-11-24 (egress threat model, EG-10, E10):* the lock must keep `httpx>=0.28`,
   `h11>=0.16.0` (CVE-2025-43859) and `httpcore>=1.0.9`; no `h2`, `brotli`/`brotlicffi`,
   `zstandard` or `socksio` is added. The declared floor `httpx>=0.28,<1` is accepted as is.
4. Leave `mining.nlp.deep_ready()` unchanged. A missing `httpx` must not disable `DS301`. A missing
   `httpx` shows up only as the `backend lenz is unavailable` WARNING from Story 01.0 Task 05.
5. Report a `Docs impact:` line covering trigger D (dependency) and trigger A.

## Deliverables

- `/src/docsentinel/fact_check/lenz.py` (one registration line)
- `/pyproject.toml`
- `/uv.lock`

## Acceptance criteria

- [ ] `load_backend("lenz") is LenzFactCheckClient`. The C3 check in `load_backend` passes.
- [ ] After `import docsentinel`, neither `"httpx"` nor `"docsentinel.fact_check.lenz"` is in
      `sys.modules`, and the same holds after a fast scan, a standard scan, `docsentinel rules` and
      `docsentinel doctor` with `DOCSENTINEL_USE_EXTERNAL_API` unset. After a confirmed deep scan
      with gate 2 closed, `"docsentinel.fact_check.lenz"` is absent from `sys.modules` and no
      socket was opened. Check this in a fresh `python -I` interpreter with a socket guard.
      *Amended 2026-11-24 (egress threat model, EG-13, E13; extract-facts model E1):* the
      gate-closed deep scan asserts the **lenz module** is absent, not `httpx`, because
      `import spacy` imports `httpx` (`DS301` loads spaCy). With the consent variable and a sentinel
      key set, `doctor` may import the client (`_backend_loadable`) but opens no socket.
- [ ] *Amended 2026-11-24 (egress threat model, E10):* `uv.lock` pins `httpx>=0.28`,
      `h11>=0.16.0` and `httpcore>=1.0.9`, and contains no `h2`, `brotli`, `zstandard` or `socksio`
      added by this task.
- [ ] `uv build` succeeds. The wheel contains `docsentinel/fact_check/lenz.py`, and its
      metadata declares `httpx`.
- [ ] `uv sync --locked` passes in CI on Python 3.12 and 3.13.

## Test expectations

- [Task 04](./04-fixtures-and-tests.md) adds the registry and lazy-import assertions.
- `uv run pytest -p docsentinel.pytest_plugin` passes.
- `uv run docsentinel scan . --format json` exits `0` with zero `DS302` findings.

## Out of scope

- A second backend.
- Changing the profile extras.
- Changes to `deep_ready()`.
