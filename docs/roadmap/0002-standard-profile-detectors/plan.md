# Milestone 0002 - Standard-Profile Detectors

**Package:** `docsentinel` | **Module root:** `src/docsentinel/` | **Config namespace:** `doc_sentinel`

> Naming note (unchanged from Milestone 0001): the distributed package, CLI, and import path are
> all `docsentinel` (one word). The **configuration namespace** - the `pyproject.toml` table and
> the standalone config filename - is deliberately `doc_sentinel` (underscored). Two names for two
> different things; do not "fix" one to match the other.

## Goal

Promote the **`standard` profile** from aspirational prose (`docs/architecture/README.md`) to
working code: the first corpus-wide, statistical/mechanical detectors that still require **no
network and no model calls**, but that are heavier than `fast` because they either (a) depend on a
non-stdlib library or (b) need the *whole* corpus loaded at once rather than one document at a
time.

This is the profile `CLAUDE.md` describes as "corpus and mechanical checks, such as duplicated
text and facts." It is deliberately a separate milestone from `fast` (Milestone 0001) because it
crosses two lines `fast` is defined to never cross:

- **Dependencies.** `fast` is stdlib-only and imports unconditionally in `detectors/__init__.py`.
  `standard` needs `scikit-learn`, `textstat`, and `docsig` - real, sometimes-heavy third-party
  packages that must **not** be required merely to run `docsentinel scan --profile fast`. Story
  01.0 builds the optional-dependency group and lazy-import plumbing that makes this safe *before*
  any detector is written.
- **Scope of input.** `fast` detectors are single-document (the `Analyzer` receives the full
  `documents` tuple but each fast rule iterates it one file at a time). The duplication and
  low-information detectors here are genuinely corpus-wide: they vectorize every paragraph of
  every document together. The `Analyzer` signature does not change - it already passes the whole
  tuple - these detectors simply use all of it.

It stays strictly inside the deterministic-first premise: the same corpus produces the same
findings every run. Semantic checks that need an agent or a model (fact contradictions, behavioral
doc-vs-code drift, the periodic background reviewer) remain reserved for **Milestone 0003 (`deep`
profile)**, which is being specced in parallel and owns the `DS3xx` range.

## Stories

| Story | Name                                             | Category | Rules        | Output                                                                                   |
|-------|--------------------------------------------------|----------|--------------|------------------------------------------------------------------------------------------|
| 01.0  | Optional-Dependency Plumbing & Lazy Standard Loading | chore | -            | `[project.optional-dependencies] standard`, `errors.ExtraNotInstalledError`, `detectors.loader`, lazy `standard` subpackage, engine/CLI wiring |
| 02.0  | Text Complexity Detector                         | feature  | `DS201`      | `detectors/standard/complexity.py` (textstat readability grade), `Config.max_grade_level` |
| 03.0  | Corpus Statistics: Duplicate & Low-Information Detectors | feature | `DS202`, `DS203` | Shared `detectors/standard/corpus.py` (TF-IDF vectorizer + chunking), duplicate-text and low-information detectors |
| 04.0  | Doc-vs-Code Signature Mismatch Detector          | feature  | `DS204`      | `detectors/standard/signatures.py` (docsig), a code-scanning discovery path, `Config.docsig_paths` |
| 05.0  | Standard-Profile CI & Baseline Wiring            | chore    | -            | CI-only `standard` lane + optional non-default `docsentinel-standard` pre-commit hook; baseline guidance |

Story 05.0 is **optional / deferrable** - it wires `standard` into CI and pre-commit but ships no
new detector; the four detectors are usable (`docsentinel scan --profile standard`) the moment
Stories 01.0-04.0 land.

## Cross-cutting guidelines (every story)

- **Determinism first, still.** Every detector here is explainable from its inputs alone - no
  network, no model download, no wall-clock/locale output. `textstat`, `scikit-learn`
  (`TfidfVectorizer` + `cosine_similarity`), and `docsig` are all pure functions of their text
  input; none fetch anything. A `standard` run that reached the network would be a bug.
- **Tests before registration.** Per `CLAUDE.md`: a new detector's result tests land *before* it
  is added to the `standard` subpackage's import list (which is what registers it into
  `engine.ANALYZERS`).
- **`fast` must stay stdlib-only and zero-cost to import.** Nothing in this milestone may add an
  import of `sklearn`/`textstat`/`docsig` to any module reachable from
  `import docsentinel.engine` on the `fast` path. Story 01.0's lazy loader is the only sanctioned
  entry to the heavy modules, and it is called *only* when `profile == "standard"`.
- **Honesty about `notice`/`pending` (unchanged rule).** A `standard` run that evaluated real
  rules must say so; a `standard` run that could not (extra not installed) must fail loudly with
  the actionable error from Story 01.0, never silently report "0 findings." An empty findings list
  is never a validated audit.
- **Full type annotations, no bare `except:`** - see
  [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md).

## Builds on Milestone 0001

This milestone assumes the Milestone 0001 contracts are in place (they are specced, and must be
implemented first):

- `rules.Rule` / `rules.RULES` / `register_rule` / `rules_for_profile` / `effective_rules` /
  `matches_selector` ([Story 01.0](/docs/roadmap/0001-generic-implementation/01.0-rule-registry-and-config-conventions/README.md)).
- `ANALYZERS` keyed by rule code, with `engine.scan()` resolving `active_codes` per profile +
  `select`/`ignore`, and the three `notice`/`pending` branches
  ([Story 01.0 Task 03](/docs/roadmap/0001-generic-implementation/01.0-rule-registry-and-config-conventions/03-selection-resolution.md)).
- `Config.select` / `Config.ignore` and the `doc_sentinel.toml` / `[tool.doc_sentinel]`
  convention ([Story 01.0 Task 02](/docs/roadmap/0001-generic-implementation/01.0-rule-registry-and-config-conventions/02-config-conventions.md)).
- `Finding.severity` exit-code semantics (`error` fails the default build, `warning` does not;
  `--strict` makes warnings fail)
  ([Story 03.0 Task 01](/docs/roadmap/0001-generic-implementation/03.0-cli-and-reporting-completion/01-severity-aware-exit-codes.md)).
- The baseline suppression mechanism (`Config.baseline`, fingerprinting)
  ([Story 04.0 Task 02](/docs/roadmap/0001-generic-implementation/04.0-pre-commit-ci-and-baseline/02-baseline-file-mechanism.md)).
  Every `DS2xx` finding is a plain `Finding`, so it flows through baselining by construction - this
  milestone adds no new baseline machinery.

## Rule code namespace

Extends the table in
[Milestone 0001's plan](/docs/roadmap/0001-generic-implementation/plan.md#rule-code-namespace).
`DS2xx` is this milestone's range; `DS1xx` (fast) and `DS3xx` (deep, Milestone 0003) are untouched.

| Code    | Profile    | Rule                                   | Severity  | Library     | Story |
|---------|------------|----------------------------------------|-----------|-------------|-------|
| `DS201` | `standard` | Text complexity (readability grade)    | `warning` | `textstat`  | 02.0  |
| `DS202` | `standard` | Duplicated text / facts (TF-IDF cosine)| `warning` | `scikit-learn` | 03.0 |
| `DS203` | `standard` | Low-information content                 | `warning` | `scikit-learn` + `textstat` | 03.0 |
| `DS204` | `standard` | Docstring / signature mismatch          | `error`   | `docsig`    | 04.0  |

Severity rationale: `DS201`-`DS203` are statistical/heuristic - a false positive is plausible, so
they ship as `warning` (visible, non-build-breaking by default, strictifiable via `--strict`).
`DS204` is mechanical and unambiguous (a documented parameter that does not exist in the signature
is simply wrong), so it ships as `error`, matching `DS101`'s reasoning in Milestone 0001.

A rule's code is permanent once shipped (renumbering breaks someone's `ignore = ["DS201"]`); an
unused gap is cheaper than a reused number.

## Why these libraries (already researched)

- **`textstat>=0.7`** - pure-Python readability metrics (Flesch-Kincaid grade, Gunning Fog,
  type-token ratio). No model download, no network. Powers `DS201` and the lexical-diversity half
  of `DS203`.
- **`scikit-learn>=1.4`** - `TfidfVectorizer` + `cosine_similarity` for corpus-wide near-duplicate
  detection (`DS202`) and the TF-IDF distinctiveness half of `DS203`. Deterministic for a fixed
  corpus and fixed parameters.
- **`docsig>=0.96`** - deterministic docstring-vs-signature checker for Python source. Chosen over
  `darglint` (unmaintained since 2021) and `pydoclint`; its stable `SIGxxx` codes and documented
  output format compose into this project's `Finding` model (`DS204`). This is the one `standard`
  detector that reads **code**, not the Markdown corpus - see
  [Story 04.0](04.0-doc-vs-code-signature-mismatch/README.md) for the honest discovery-path design.

All three are added as an **optional** dependency group (`docsentinel[standard]`), never a hard
dependency - Story 01.0.

## Links

- **Architecture boundaries:** [`docs/architecture/README.md`](/docs/architecture/README.md)
- **Milestone 0001 (fast profile):** [`docs/roadmap/0001-generic-implementation/plan.md`](/docs/roadmap/0001-generic-implementation/plan.md)
- **Coding standard:** [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md)
- **Status tracker:** [status.md](status.md)
</content>
</invoke>
