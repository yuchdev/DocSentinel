# Story 01.0 - Deep Profile Opt-In Gating & Dependency Plumbing

Before any `deep` detector exists to run, `deep` needs to be made *safe to merely select*.
Today `profile = "deep"` is a harmless no-op (M0 registers nothing). The moment Story 02.0 lands a
model-loading, content-reading detector, selecting `deep` must **not** be enough to trigger it -
`deep` is slow (model load), reads full document contents, and is heuristic (expected false
positives). This story builds the second, explicit opt-in gate `docs/architecture/README.md` and
`CLAUDE.md` already describe in prose ("explicitly enabled"), the optional-dependency group that
carries spaCy/textacy, and the lazy-import boundary that keeps `docsentinel.engine` cheap to
import whether or not that group is installed.

This story produces **no new findings** by itself (`DS301` is Story 02.0's job) - it is pure
gating and plumbing that Story 02.0 plugs into.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Deep opt-in confirmation gate](01-deep-opt-in-confirmation-gate.md) | `Config.deep_confirm`, `--i-understand-deep-is-heuristic`, `DOCSENTINEL_DEEP_CONFIRM`, engine refusal + distinct `pending` |
| 02 | [Optional `deep` dependency group & lazy-import boundary](02-optional-dependency-group-and-lazy-import.md) | `[project.optional-dependencies] deep`, `deep_support.py` readiness probe, no eager spaCy import |
| 03 | [`doctor` deep-readiness & model-setup docs](03-doctor-readiness-and-model-setup-docs.md) | `doctor` reports gate/deps/model state; one-time `spacy download` documented |

Sequential - 01 defines the confirmation state the engine checks; 02 defines the dependency
probe 03 reports on; 03 surfaces both to the user. Task 02 must land before Story 02.0's detector
can import anything heavy without breaking the cheap-import guarantee.
