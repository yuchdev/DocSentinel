# DocSentinel — Milestone 0004 archival specification

This archive contains **the specification only** for Milestone `0004-deepening-test-cases`, organized in the same on-repository hierarchy as current Milestones 0001–0003:

```text
docs/roadmap/0004-deepening-test-cases/
  plan.md
  status.md
  README.md
  implementation-contracts.md
  fixture-matrix.md
  01.0-shared-foundations-and-fixtures/
    README.md
    01-*.md, 02-*.md, 03-*.md
  02.0-... through 13.0-...   # 12 rules, one story each
    README.md
    01-implement-detector.md
    02-markdown-asset-cases.md
    03-integration-and-verification.md
  14.0-cross-profile-validation-and-release/
    README.md
    01-*.md, 02-*.md, 03-*.md
```

The companion `fixture-matrix.csv` next to `fixture-matrix.md` is a machine-readable manifest for generating/validating the future repository assets. The `.md` specifications are intended to be copied verbatim under `docs/roadmap/0004-deepening-test-cases/`.

## Verified repository starting point

- GitHub `master` commit: `04a3eb337f7b75d1783cd4a7f45da2c68528113b` (October 14, 2026).
- Python 3.12+, config file `docsentinel.toml`, exact three profiles, and `asset_case` from `tests/conftest.py` are actual checked contracts.

## Scope and completeness

- 12 rules, 14 stories, 42 story-level task specs.
- 163 named fixture directories specified (all containing Markdown files), of which 86 expected clean, 63 expected findings, and 14 expected pending/unverifiable.
- No current repository tests or code are changed by creating this archive.

Read **`docs/roadmap/0004-deepening-test-cases/plan.md`** first, then Story 01.0, then individual rule stories. When copy/pasting this specification into GitHub, add a link to the new milestone in the existing `docs/roadmap/README.md` index.
