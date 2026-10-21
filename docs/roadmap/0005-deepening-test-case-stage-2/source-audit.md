# Source audit, October 21, 2026

| Check | Observed from GitHub `master` |
|---|---|
| Tree SHA / tip | `48ddf303b6f9b87c901833b29e8d75ffa3543950` |
| Latest visible commit | `Milestone 0004 added`, committed 2026-10-14 16:49:53 UTC |
| Roadmap 0004 | `docs/roadmap/0004-deepening-test-cases/` contains `plan.md`, `status.md`, `fixture-matrix.md/.csv/.json`, `implementation-contracts.md`, 14 story directories and task specs |
| Detector source still present | `src/docsentinel/detectors/` has DS101, DS102, DS103, DS301 plus standard DS201–DS204 modules; no new M4 detector modules observed in tree |
| Fixture assets | `tests/assets/ds101`–`ds103`, `ds201`–`ds204`, `ds301`; no `ds107`/`ds111`/`ds119` or other M4 rule asset folders present |
| Test conventions | `tests/asset_helpers.py` and `tests/conftest.py` expose `asset_case` copying `tests/assets/dsNNN/<scenario>/`; unit/mock/integration tiered tests |
| Tooling | Python >=3.12, uv, `doc_sentinel.toml`, config namespace `[tool.doc_sentinel]`, exact profiles, `Rule` registry, baseline and scan formats |
| Existing roadmap index | `docs/roadmap/README.md` still lists only 0001–0003, so 0004+0005 must be indexed during implementation |

**Consequence:** this plan is intentionally independent of the assumption that 0004 implementation has already shipped. After implementation begins, recheck master and prefer M4 shared parser/context if present. No GitHub mutation was requested or performed.
