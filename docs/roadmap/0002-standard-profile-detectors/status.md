# Milestone 0002 - Standard-Profile Detectors - Status

Tracks progress against [plan.md](plan.md). Updated as each story lands.

## Current status

| Story | Name                                                 | Status      | Progress | Rules            | Tests    |
|-------|------------------------------------------------------|-------------|----------|------------------|----------|
| 01.0  | Optional-Dependency Plumbing & Lazy Standard Loading | ✅ Complete | 3/3      | -                | 22 full  |
| 02.0  | Text Complexity Detector                             | ✅ Complete | 2/2      | `DS201`          | 26 full  |
| 03.0  | Corpus Statistics: Duplicate & Low-Information Detectors | ✅ Complete | 4/4  | `DS202`, `DS203` | 61 full  |
| 04.0  | Doc-vs-Code Signature Mismatch Detector              | ✅ Complete | 3/3      | `DS204`          | 42 full  |
| 05.0  | Standard-Profile CI & Baseline Wiring                | ✅ Complete | 1/1      | -                | 5 full   |

## Task status

| Task | Deliverable | Status | Evidence / disposition |
|------|-------------|--------|------------------------|
| 01.0-01 | Optional dependency group & error type | ✅ Complete | Added `standard` extra in `pyproject.toml` and `ExtraNotInstalledError` in `errors.py`; 3 focused tests passed |
| 01.0-02 | Lazy standard loader & engine wiring | ✅ Complete | Implemented `loader.py` and lazy `standard` subpackage loading; 12 focused tests passed |
| 01.0-03 | CLI & docs awareness | ✅ Complete | Graceful CLI `rules`/`doctor` degradation, standard error messaging, and architecture documentation; 6 focused tests passed |
| 02.0-01 | Complexity detector (`DS201`) | ✅ Complete | Readability grade detector via `textstat`, markdown stripping, word count guard, and `Config.max_grade_level`; 14 focused tests passed |
| 02.0-02 | DS201 wiring & E2E | ✅ Complete | Standard subpackage export, exit code 0 default warning behavior, `--strict` exit 1, and architecture sync; 6 focused tests passed |
| 03.0-01 | Shared corpus module | ✅ Complete | `CorpusModel`, paragraph chunking with 1-based lines, and deterministic TF-IDF vectorization; 13 focused tests passed |
| 03.0-02 | Duplicate-text detector (`DS202`) | ✅ Complete | Pairwise cosine similarity with `Config.duplicate_similarity` (default 0.85); 21 focused tests passed |
| 03.0-03 | Low-information detector (`DS203`) | ✅ Complete | Geometric-mean combining TTR and max TF-IDF with `Config.min_information_score` (default 0.15); 21 focused tests passed |
| 03.0-04 | Corpus caching & E2E | ✅ Complete | `lru_cache(maxsize=1)` single TF-IDF fit per scan, end-to-end multi-rule validation, and architecture sync; 6 focused tests passed |
| 04.0-01 | Python source discovery | ✅ Complete | Stdlib-only `code_discovery.py` supporting `Config.docsig_paths` (default `src`) with directory pruning and symlink safety; 27 focused tests passed |
| 04.0-02 | Signature mismatch detector (`DS204`) | ✅ Complete | In-process `docsig` runner with ANSI suppression, pure stdout report parser, and `error` severity findings; 10 focused tests passed |
| 04.0-03 | DS204 wiring & E2E | ✅ Complete | Standard subpackage export, exit code 1 default failure on signature error, source-code threat modeling note, and architecture sync; 5 focused tests passed |
| 05.0-01 | Standard CI lane & opt-in hook | ✅ Complete | Added opt-in `docsentinel-standard` pre-commit hook, CI standard scan step, `--baseline` CLI override, and separate `.docsentinel-standard-baseline.json`; 5 focused tests passed |

## Decisions and gap dispositions

- **Lazy loading isolation:** `standard` optional dependencies (`scikit-learn`, `textstat`, `docsig`) are loaded exclusively when `profile="standard"` is evaluated, maintaining fast zero-dependency behavior for default runs.
- **Corpus vectorizer sharing:** `DS202` and `DS203` share `build_corpus_model` with `lru_cache(maxsize=1)` memoization to guarantee a single TF-IDF fit per scan without modifying the frozen `Analyzer` contract.
- **Code discovery separation:** `code_discovery.py` discovers `.py` files independently from Markdown `Document` discovery, allowing `DS204` to scan Python source trees without forcing code through the Markdown model.
- **Severity semantics:** `DS201`, `DS202`, and `DS203` are heuristic `warning` severity (exit 0 by default, exit 1 under `--strict`), while `DS204` is deterministic `error` severity (exit 1 by default).
- **Separate baseline files:** `.docsentinel-standard-baseline.json` stores standard profile fingerprints independently from `.docsentinel-baseline.json`.

## Story close evidence

- **01.0 Optional-Dependency Plumbing & Lazy Standard Loading:** Delivered `pyproject.toml` standard extra, `ExtraNotInstalledError`, lazy loader module, engine conditional loading, CLI diagnostic awareness, and architecture docs.
- **02.0 Text Complexity Detector:** Delivered `DS201` readability grade detector, Markdown text stripper, short document bypass, `Config.max_grade_level` configuration, and end-to-end test suite.
- **03.0 Corpus Statistics (Duplicate & Low-Information Detectors):** Delivered `CorpusModel`, `DS202` pairwise cosine duplicate detector, `DS203` filler text detector combining lexical diversity with TF-IDF distinctiveness, and `lru_cache` per-scan model caching.
- **04.0 Doc-vs-Code Signature Mismatch Detector:** Delivered `code_discovery.py` Python source scanner, in-process `docsig` integration, `DS204` error-level detector, and security documentation covering expanded source-code read surface.
- **05.0 Standard-Profile CI & Baseline Wiring:** Delivered opt-in `docsentinel-standard` pre-commit hook, CLI `--baseline` argument support, CI workflow standard scan step, and committed `.docsentinel-standard-baseline.json`.

## Milestone exit-gate evidence

- **Locked environment:** `uv sync --locked --all-extras` completed cleanly.
- **Tests:** 364 tests passed with the DocSentinel pytest plugin loaded.
- **Self-scan and honesty:** Fast scan evaluated 3 fast rules on 113 documents (exit 0). Standard scan evaluated 4 standard rules (DS201-DS204) on 113 documents gated by `.docsentinel-standard-baseline.json` (exit 0).
- **Build:** Source distribution `docsentinel-0.1.0.tar.gz` and wheel `docsentinel-0.1.0-py3-none-any.whl` built successfully.
- **Quality and review:** Ruff check and format passed across all 43 source and test files.
- **Documentation:** `python scripts/check_doc_links.py docs/` scanned 75 files with 0 broken links or anchor failures. Milestone 0002 is complete.

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started
</content>
