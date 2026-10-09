# Story 05.0 - Standard-Profile CI & Baseline Wiring

**Optional / deferrable.** This story ships no new detector. It decides *where* the `standard`
profile runs - CI, pre-commit, or on-demand only - and records the baseline guidance for a corpus
that will surface pre-existing findings the moment `standard` goes live. The four detectors are
already usable via `docsentinel scan --profile standard` after Stories 01.0-04.0; this story only
automates them.

It exists as its own story precisely because the CI/hook decision for `standard` is *different* from
`fast`'s, and conflating them would be wrong: `fast` is single-document, stdlib-only, and
milliseconds-fast, so Milestone 0001 put it in an `always_run: true` pre-commit hook. `standard`
is corpus-wide (an O(n²) TF-IDF pass), depends on a heavy optional extra, and runs `docsig` over
source - too slow and too dependency-heavy to block every commit by default.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Standard CI lane & optional pre-commit hook](01-ci-lane-and-optional-hook.md) | CI `standard`-extra lane; a separate, non-default `docsentinel-standard` pre-commit hook id; `standard` baseline guidance |

Single task - the decision and its wiring are small and belong together.
</content>
