# Story 05.0 — `extract-facts`: offline preview of the DS302 fact set

**Profile:** none (profile-independent; needs the `deep` extras and the spaCy model) · **New CLI
command:** `docsentinel extract-facts` · **New public API:** `docsentinel.extract_facts()` ->
`FactExtractionResult` · **Touched/new sources (described, not yet written):**
`src/docsentinel/detectors/fact_check.py` (`trace_candidates()`, `collect_candidates()`,
`SelectionPolicy`, extended `CandidateClaim`), `src/docsentinel/mining/salience.py`
(`trace_salience()`, extended `ScoredClaim`), `src/docsentinel/engine.py` (shared inventory step,
`extract_facts()`), `src/docsentinel/models.py` (`ExtractedFact`, `FactSettings`,
`FactExtractionResult`), `src/docsentinel/__init__.py` (exports),
`src/docsentinel/telemetry/facts_model.py` (new, facts context), `src/docsentinel/telemetry/loader.py`
(template `context` key), `src/docsentinel/telemetry/templates/facts-text.json` and
`facts-json.json` (new), `src/docsentinel/reporting.py` (`render_facts()`), `src/docsentinel/cli.py`
(`extract-facts` subcommand).
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (contracts C7, C9, C11).
**Depends on:** Story 01.0 (config keys, `detectors/fact_check.py`, `CandidateClaim`) and Story 02.0
(the salience pipeline). **Not** on Story 03.0: this story never needs a backend.
**Security-sensitive:** low. There is no network path and no secret. It writes document-derived text
to stdout or a file, and it adds a template-loader key. The Security Auditor reviews the loader
change (Task 02, step 6) against
[the template-engine threat model](/docs/security/threat-model-0007-template-engine-2026-10-31.md).

> **Added 2026-11-23 (owner request).** "Add CLI command `extract-facts` that accept documents and
> settings for the algorithm. The goal is to reduce document to a group of verifiable facts using
> non-LLM data mining algorithms. The resulting set of facts should be the one that used in `DS302`
> for external fact-checking APIs."

## Goal

Give users a strictly offline command, and a library function, that turns a set of documents into
the bounded, ranked set of verifiable facts (claims) that `DS302` would send to an external
fact-checking backend. Both use the same non-LLM data-mining pipeline: spaCy/textacy SVO
extraction, then numeric density, entity density, TF-IDF distinctiveness and near-duplicate
clustering. The default output **is** the DS302 candidate set for the same root, configuration and
selection, and one function produces both (contract
[C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts)).
It serves as the dry-run preview a user reviews before giving consent to DS302 egress.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| `01-shared-candidate-collection-and-public-api.md` | `mining.salience.trace_salience()` (`select_salient()` becomes its projection); signal fields on `ScoredClaim`/`CandidateClaim`; `trace_candidates()`/`collect_candidates()` and `SelectionPolicy` in `detectors/fact_check.py`; `DS302` `detect()` calls `collect_candidates()`; the engine's shared inventory step; `engine.extract_facts()`; `FactExtractionResult` and its parts in `models.py`; exports | Python Expert | ✅ Complete |
| `02-facts-template-context-and-packaged-templates.md` | Template `context` key (`report` default, `facts`); `FACTS_CONTEXT_SCHEMA` and `FactsModel.build()` in `telemetry/facts_model.py`; packaged `facts-text`/`facts-json`; `reporting.render_facts()`; Security Auditor review of the loader delta | Python Expert (+ Security Auditor review) | ✅ Complete |
| `03-extract-facts-cli-command.md` | `docsentinel extract-facts` subcommand: options, overrides, exploration flags, `--all`, output, logging, exit codes; `doctor` template line | Python Expert | ✅ Complete |
| `04-fixtures-and-tests.md` | Unit, mock and integration tests for Tasks 01–03, including the single-source check at the `detect()` boundary and the no-egress import check. The end-to-end equality check against a recording fake backend lives in [Story 04.0 Task 02](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/02-integration-and-mock-tests.md) | Testing Expert | ✅ Complete |

User documentation, the release notes and the diagram follow-up are folded into Story 04.0 (Tasks
04 and 05), which now depends on this story.

## Scope

- One candidate-collection function shared by `DS302` and `extract-facts` (C11).
- A public library entry point that mirrors `scan()`: discovery, include/exclude, single-file
  targets, unreadable-document handling and the empty-invoker-selection error, all through one
  engine step.
- CLI overrides for the three config-backed selection settings, plus CLI/library-only exploration
  settings (weights, dedup threshold) that never reach `DS302` (decision X5; owner question O1).
- An `--all` listing of every extracted claim with its disposition, for tuning.
- Template-rendered output (`facts-text`, `facts-json`, user templates), with no hardcoded format.

## Non-goals

- Any network call, backend import, API-key read, consent-gate resolution or `deep_confirm` check.
- New configuration keys. The weights and the dedup threshold stay non-configurable (Story 02.0
  Security notes). They are never `Config` fields and never in user settings.
- Changing `DS301`, `mining/claims.py`, `Claim`, or the extraction itself (plan Out of scope).
  So there are no line numbers in this story (decision X8; owner question O2).
- A pytest-plugin fixture, a pre-commit hook or a baseline for facts. The command is a report, not a
  gate.
- Report extensions (`--extension`) on fact output.
- A record of what DS302 actually sent in a past run. That stays out of scope; see owner question O3.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| X1 | **One source of truth (C11).** `trace_candidates(root, documents, config, *, policy=DS302_POLICY)` in `detectors/fact_check.py` is the only function that turns documents into scored, dispositioned claims. `collect_candidates(root, documents, config)` returns `trace_candidates(...).selected` with the DS302 policy. `DS302` `detect()` calls `collect_candidates()` after the gate. `engine.extract_facts()` calls `trace_candidates()` with no gate | The owner's core requirement. A second extraction loop, even one copied line for line, would drift. The `.md` filter, strict UTF-8 read, pipeline load, pooling and `select_candidates` adaptation then exist once |
| X2 | `mining.salience.trace_salience(...)` is the pure core. It returns **every** canonical claim as a `ScoredClaim` with signals, cluster size and a `disposition`. `select_salient(...)` is defined as the `selected` subsequence of the trace, so ordering, tie-breaks and caps live once | `--all` needs the rejected claims and why they were rejected. Building a second "explain" path beside `select_salient` would duplicate the cap logic. Story 02.0's T5/T8 contracts are unchanged for the selected subset |
| X3 | `extract_facts()` lives in `engine.py` and shares a new private inventory step, `_inventory(root, config, include, exclude) -> _Inventory`, with `scan()`. The refactor is behaviour-preserving: every `scan()` result and log line is byte-identical to master | Discovery, single-file handling, invoker selection, the `EMPTY_SELECTION_MESSAGE` error and `_partition_readable` then behave identically for both, which is what makes "same set as DS302" hold for the same invocation |
| X4 | A single-file target is accepted exactly as `scan()` accepts it: include/exclude ignored with one WARNING, a symlinked file refused with `ValueError` | Same invocation shape as `scan`, and DS302 on a single-file scan sees the same one-document corpus, so the equality still holds |
| X5 | **Exploration settings (provisional; owner question O1).** `--weights N,E,D` and `--dedup-threshold F` (library: `weights=`, `dedup_threshold=`) change only this command's output. They build a non-default `SelectionPolicy` and are never `Config` fields, never in any file and never passed by `DS302`. When any of them differs from the DS302 constants, `matches_ds302` is `false` and the notice says so | The exposure argument behind "not configurable" (Story 02.0 Security notes) concerns what a project file could make DS302 send. This command sends nothing, and the DS302 path cannot receive a policy (`collect_candidates` has no `policy` parameter). Tuning without a code edit is the main reason to have the command |
| X6 | `--min-salience`, `--max-per-document` and `--max-total` override the three config keys for this run with `dataclasses.replace(config, ...)`. They default to the effective layered config. `select_candidates`' existing re-validation rejects an out-of-range value with `ConfigError`, so the bounds are the config bounds with no second validator | Default output equals the DS302 set for the same config. Overriding through `Config` (like `--reference-scope`) needs no new validation code. `matches_ds302` is `false` when an override differs from the effective config value |
| X7 | `--all` (library `include_rejected=True`) lists every extracted claim with a non-empty sentence, each with its disposition (`selected`, `duplicate`, `below_floor`, `document_cap`, `total_cap`). The selected subset and `matches_ds302` do not change | Explains why a claim did or did not make it, which tuning needs. The output is local only; template output caps bound its size |
| X8 | A fact carries `path` and `paragraph_index`, not a line number | `Claim` has no line, and changing `Claim`/`extract_claims` is out of this milestone's scope. Recomputing lines by re-splitting the text in the detector would be a second copy of the paragraph splitter (owner question O2) |
| X9 | **Output through templates.** A template gains an optional top-level key `"context"`: `"report"` (default, today's schema) or `"facts"` (new `FACTS_CONTEXT_SCHEMA`). New packaged templates `facts-text` (default) and `facts-json`. `--template PATH` and `report_templates_dir` work as for `scan`. A `facts` template given to `scan`, or a `report` template given to `extract-facts`, is a `TemplateError` (exit `2`) | Keeps the "no hardcoded output format" convention and reuses the loader's sink-order and neutralisation rules for untrusted claim text. Rejected: hand-written `json.dumps`/print code (breaks the convention), and mapping facts into `ReportModel` as findings (a fact is not a problem; the classification, outcome and `Blocking findings` recap would be wrong). Additive: every existing template is a `report` template with no edit |
| X10 | Strictly offline. The command does not resolve `use_external_api`, read `DOCSENTINEL_USE_EXTERNAL_API` or any `DOCSENTINEL_FACTCHECK_*` variable, or call `load_backend`/`resolve_external_api_gate`/`external_api_requested`. **Amended 2026-11-24 (threat model, E1):** the offline invariant has three parts: (a) no backend module is imported (`docsentinel.fact_check.lenz` and every value of `FACT_CHECK_BACKEND_MODULES`); (b) the `extract-facts` call graph in DocSentinel code contains no reference to `httpx` (AST), so it constructs no HTTP client; (c) no outbound socket is opened (`socket.socket.connect`, `socket.create_connection`, `socket.getaddrinfo`). It is **not** "`httpx` absent from `sys.modules`": spaCy itself imports `httpx` when `mining.nlp.load_pipeline()` runs. `extract-facts` has no `--use-external-api` option, so argparse rejects it (exit `2`) | This is the property that makes the command a safe preview. `docsentinel.fact_check.protocol` (stdlib-only data contracts) is already imported by `import docsentinel` through `detectors/__init__.py`. Refinement of the brief: the invariant is "no backend module, no `httpx` reference on the path, no socket", not "no `docsentinel.fact_check` at all" and not "no `httpx` in the process" (threat model F1, [threat-model-0010-extract-facts-2026-11-24](/docs/security/threat-model-0010-extract-facts-2026-11-24.md)) |
| X11 | Profile-independent, and no `deep_confirm`. `profile`, `select`, `ignore`, `baseline` and `deep_confirm` are not read. The deep extras and the spaCy model are required: if `deep_ready()` is false, the command stops before reading a document with exit `2` and the `DEEP_EXTRA_HINT` message | The command reports and does not gate. `deep_confirm` means "I accept heuristic noise in findings", and here there are no findings. The output carries a fixed heuristic notice instead |
| X12 | Exit codes: `0` on success, including zero facts and unreadable documents (skipped, logged once each by the shared step and counted in the output). `2` for `ConfigError`, `ValueError`, `OSError`, `TemplateError`, deep extras missing, or an invoker selection that admits no document. Never `1` | There is nothing to block on. An unreadable document is a `DS100` problem for `scan` to report; here it is a counted skip |

### Data contracts

```python
# src/docsentinel/mining/salience.py (Story 02.0 module; this story amends)

DISPOSITIONS: Final[tuple[str, ...]] = (
    "selected", "duplicate", "below_floor", "document_cap", "total_cap",
)


@dataclass(frozen=True)
class ScoredClaim:
    claim: Claim
    score: float            # combined, rounded to SCORE_DECIMALS
    numeric: float          # numeric density in [0, 1]
    entity: float           # entity density in [0, 1]
    distinctiveness: float  # from clustering, in [0, 1]
    cluster_id: int
    cluster_size: int       # canonical claims sharing cluster_id, >= 1
    disposition: str        # one of DISPOSITIONS


def trace_salience(
    claims: tuple[Claim, ...],
    *,
    weights: SalienceWeights,
    dedup_threshold: float,
    min_salience: float,
    max_per_document: int,
    max_total: int,
) -> tuple[ScoredClaim, ...]:
    """Score and disposition every canonical claim (pure, no Config).

    Order: (-score, path, paragraph_index, raw_sentence, raw_subject, raw_object).
    The "selected" subsequence equals select_salient(...) with the same arguments.
    :raises ValueError: For any numeric parameter out of range.
    """


def select_salient(claims, *, weights, dedup_threshold, min_salience,
                   max_per_document, max_total) -> tuple[ScoredClaim, ...]:
    """The "selected" subsequence of trace_salience(...), order preserved."""
```

```python
# src/docsentinel/detectors/fact_check.py (Story 01.0/02.0 module; this story adds)

@dataclass(frozen=True)
class SelectionPolicy:
    """The non-configurable DS302 selection policy, or an extract-facts exploration of it."""

    weights: tuple[float, float, float]  # numeric, entity, distinctiveness
    dedup_threshold: float


DS302_POLICY: Final[SelectionPolicy] = SelectionPolicy(
    (_W_NUMERIC, _W_ENTITY, _W_DISTINCT), _DEDUP_THRESHOLD
)


@dataclass(frozen=True)
class CandidateClaim:        # Story 02.0 fields plus the signal breakdown
    claim: Claim
    text: str                # stripped, at most MAX_CANDIDATE_CHARS code points: the text DS302 sends
    score: float
    numeric: float
    entity: float
    distinctiveness: float
    cluster_id: int
    cluster_size: int


@dataclass(frozen=True)
class CandidateTrace:
    entries: tuple[tuple[CandidateClaim, str], ...]  # (candidate, disposition), trace order
    documents_read: int
    claims_extracted: int

    @property
    def selected(self) -> tuple[CandidateClaim, ...]: ...


def trace_candidates(
    root: Path,
    documents: tuple[Document, ...],
    config: Config,
    *,
    policy: SelectionPolicy = DS302_POLICY,
) -> CandidateTrace:
    """Extract claims from the readable .md documents, pool them and trace the selection (C11)."""


def collect_candidates(
    root: Path, documents: tuple[Document, ...], config: Config
) -> tuple[CandidateClaim, ...]:
    """The DS302 candidate tuple: trace_candidates(root, documents, config).selected."""
```

`select_candidates(claims, config)` (Story 02.0) gains a keyword-only `policy: SelectionPolicy =
DS302_POLICY` and keeps its contract. `collect_candidates` has **no** `policy` parameter, so
`DS302` cannot receive an exploration policy.

```python
# src/docsentinel/models.py (new public contracts; stdlib only)

@dataclass(frozen=True)
class ExtractedFact:
    rank: int                       # 1-based position in the listed order
    path: str
    paragraph_index: int            # Claim.paragraph_index (0-based split index)
    text: str                       # == CandidateClaim.text (the DS302 send text)
    score: float
    numeric: float
    entity: float
    distinctiveness: float
    cluster_id: int
    cluster_size: int
    numbers: tuple[str, ...]        # Claim.object_numbers, first 32, each <= 200 code points (E8)
    entities: tuple[str, ...]       # Claim.object_entities ("LABEL:text"), same caps (E8)
    disposition: str                # "selected" unless include_rejected


@dataclass(frozen=True)
class FactSettings:
    min_salience: float
    max_per_document: int
    max_total: int
    weights: tuple[float, float, float]
    dedup_threshold: float


@dataclass(frozen=True)
class FactExtractionResult:
    documents: tuple[Document, ...]   # the discovered inventory, as in ScanResult
    documents_unreadable: int
    claims_extracted: int
    facts: tuple[ExtractedFact, ...]  # selected only, or every claim with include_rejected
    settings: FactSettings
    matches_ds302: bool               # selected subset == DS302's set for this config
    include_rejected: bool
    notice: str                       # fixed heuristic/offline text, see Task 01

    @property
    def selected(self) -> tuple[ExtractedFact, ...]: ...
```

```python
# src/docsentinel/engine.py (new public function; exported from docsentinel)

def extract_facts(
    root: Union[Path, str] = ".",
    *,
    config: Optional[Config] = None,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    min_salience: Optional[float] = None,
    max_per_document: Optional[int] = None,
    max_total: Optional[int] = None,
    weights: Optional[tuple[float, float, float]] = None,
    dedup_threshold: Optional[float] = None,
    include_rejected: bool = False,
) -> FactExtractionResult:
    """Offline preview of the DS302 fact set (C11); no gate, no network, no backend.

    :raises ConfigError: Invalid config/override, or an invoker selection admitting no document.
    :raises ValueError: Invalid weights/threshold, or a symlinked single-file target.
    :raises RuntimeError: The deep extras or the spaCy model are unavailable, or claim
        extraction failed (type name only, no chain; E7, amended 2026-11-24).
    """
```

### Facts template context (`FACTS_CONTEXT_SCHEMA`, Task 02)

| Path | Type | Trust |
|---|---|---|
| `run.notice` | str | trusted (engine constant) |
| `run.matches_ds302`, `run.include_rejected` | bool | trusted |
| `run.settings.{min_salience, max_per_document, max_total, dedup_threshold}` | number | trusted |
| `run.settings.weights.{numeric, entity, distinctiveness}` | number | trusted |
| `run.summary.{documents, unreadable, claims_extracted, facts_selected, facts_listed}` | int | trusted |
| `facts[]` (listed order) and `documents[].facts[]` (path order, each in rank order) | list | per field |
| `…rank`, `…paragraph_index`, `…score`, `…signals.{numeric, entity, distinctiveness}`, `…cluster.{id, size}` | number | trusted |
| `…disposition` | str (closed set, validated by `FactsModel.build`) | trusted |
| `…hidden_characters` | bool | trusted (computed by `FactsModel.build`; **Amended 2026-11-24 (threat model, E5)**) |
| `…path`, `documents[].path`, `…text`, `…numbers[]`, `…entities[]` | str | **untrusted** |

**Amended 2026-11-24 (threat model, E4/E5).** `…hidden_characters` is true when the fact's `text`
holds any code point of Unicode category Cf, Co or Cn, or of the 0007 R4 list (U+00AD, U+180E,
U+2060-U+2064, the Hangul fillers, variation selectors, U+E0000-U+E007F), that `neutralize` keeps.
The facts schema has no `ext` entry.

`facts-json` emits `{"schema": "docsentinel-facts", "schema_version": 1, "notice", "matches_ds302",
"include_rejected", "settings", "summary", "facts": [...]}` with `ensure_ascii` forced, and every
`##[` serialised as `##[` (E3).
`facts-text` prints each document path once, then one line per fact (rank, score, the three
signals, cluster id/size, paragraph, disposition when `--all`, a fixed hidden-characters marker when
`hidden_characters` is true (E5), then the text through `neutralize`), and ends with a summary line,
the `matches_ds302` line and the notice.

### Pipeline

```text
cli extract-facts / docsentinel.extract_facts()
  └─ engine._inventory()  (shared with scan(): discovery, selection, single-file, _partition_readable)
  └─ deep_ready()?  no -> RuntimeError / exit 2
  └─ settings = replace(config, <three overrides>); policy = DS302_POLICY or exploration policy
  └─ detectors.fact_check.trace_candidates(directory, readable, settings, policy=policy)   <- C11
        ├─ mining.claims.extract_claims (per readable .md, strict UTF-8), mining.nlp.load_pipeline
        └─ select_candidates(..., policy=) -> mining.salience.trace_salience(...)
  └─ map to ExtractedFact (selected only, or all with include_rejected) -> FactExtractionResult
  └─ reporting.render_facts(result, "facts-text"|"facts-json"|template) -> stdout or -o file

scan --profile deep … DS302 detect(): gate open? -> collect_candidates(root, readable, config)
                                                    == trace_candidates(..., DS302_POLICY).selected
```

## Security notes

- **A preview, not a send.** The command is how a user can see, before giving consent, exactly
  which bounded texts `DS302` would send under the same root, configuration and selection. The
  default output's `text` values are byte-equal to the strings `check_claim()` would receive (C11).
  This holds only for the same spaCy model version, configuration layers and selection. The notice
  says so.
- **No egress path exists in this command (X10).** **Amended 2026-11-24 (threat model, E1).** No
  backend module, no `httpx` reference in DocSentinel code on the path, no outbound socket, no gate
  resolution, and no read of `DOCSENTINEL_USE_EXTERNAL_API` or `DOCSENTINEL_FACTCHECK_*`. spaCy
  imports `httpx` itself, so its presence in `sys.modules` is not evidence either way. A
  fresh-interpreter test patches `socket.socket.connect`, `socket.create_connection` and
  `socket.getaddrinfo` to record and raise before `cli.main` runs, then asserts nothing was
  recorded and that neither `docsentinel.fact_check.lenz` nor any `FACT_CHECK_BACKEND_MODULES` value
  is in `sys.modules`. An AST test proves the `extract_facts`/`trace_candidates` call graph names
  none of the gate or backend functions and no `httpx`.
- **Exploration settings cannot reach DS302.** `collect_candidates()` has no `policy` parameter;
  `SelectionPolicy` values come only from the CLI or a library keyword, never from any
  configuration layer or the environment. Tests pin that `Config` has no weight or threshold field.
  **Amended 2026-11-24 (threat model, E9):** in every tier (TOML, pyproject, `--config` JSON, user
  settings) `weights`, `dedup_threshold`, `fact_check_weights`, `fact_check_dedup_threshold`,
  `include_rejected` and `selection_policy` each give the unknown-option `ConfigError`; the
  signatures of `scan`, `detect` and `collect_candidates` have no `policy`, `weights` or `dedup`
  parameter; and an in-process `extract_facts(weights=..., dedup_threshold=...)` leaves
  `DS302_POLICY`, the `_W_*` constants and the `collect_candidates` result unchanged.
- **`##[` in JSON output.** **Amended 2026-11-24 (threat model, E3).** `ensure_ascii` escapes
  neither `#` nor `[`, and the GitHub runner honours `##[` anywhere in a line. For `facts`-context
  JSON the template engine serialises the `[` of every `##[` as `[`. This is lossless: the
  parsed string is unchanged, so C11 byte-equality holds at the value level. Write facts output
  with `-o` and never print it in full to a CI log. Extending the escape to `report` JSON is an
  owner question.
- **Hidden characters in the preview.** **Amended 2026-11-24 (threat model, E5).** Code points
  `neutralize` keeps but a terminal renders invisibly (0007 R4) would be sent by DS302 yet unseen
  in `facts-text`. `FactsModel` sets the trusted `hidden_characters` flag and `facts-text` prints a
  fixed marker on such lines. `facts-json` (ASCII-escaped) is the authoritative review form, and
  consent should be reviewed with the packaged templates (residual RR1).
- **Document text leaves the process only to stdout or the `-o` file the invoker named.** Claim text
  is never logged at any level; log lines carry counts and, at DEBUG, paths through `safe()`. A
  report file holds document-derived text and should be treated like the documents themselves.
- **Untrusted text in sinks.** Paths, claim text, numbers and entities are untrusted in
  `FACTS_CONTEXT_SCHEMA`. The loader's existing rule (an untrusted variable in a `text` template
  must end in a sink filter) applies unchanged. JSON output forces `ensure_ascii`.
- **Template-loader change.** The new `context` key is additive and closed (`report`/`facts`). A
  `facts` template can name only facts variables, a `report` template only report variables.
  `requires_extensions` must be empty for `facts`. Config-named templates keep the DS115 file gate.
  The Security Auditor reviews this delta (Task 02, step 6).
- **Output size.** `--all` can list every claim in a large corpus. `MAX_OUTPUT_CHARS` and
  `MAX_ITERATIONS` stop the render with `TemplateError` (exit `2`) and never truncate silently.
- **An untrusted project config still sets the three caps** shown in the preview. That is the
  intended behaviour, because the preview must show what DS302 would do under that same config.

## Acceptance criteria

- [ ] There is exactly one extraction loop for `DS302` and `extract-facts`: `trace_candidates()`.
      `DS302` `detect()` calls `collect_candidates()` and contains no `extract_claims` call of its
      own (AST test).
- [ ] With default settings, `[f.text for f in extract_facts(root).facts]` equals, in order, the
      texts a recording fake backend receives from a gate-open DS302 scan of the same root and
      config ([Story 04.0 Task 02](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/02-integration-and-mock-tests.md)).
      `matches_ds302` is `true`.
- [ ] Any override that differs from the effective config, or any exploration setting that differs
      from `DS302_POLICY`, gives `matches_ds302 == false`, and the notice names the setting.
- [ ] `select_salient(...)` equals the `selected` subsequence of `trace_salience(...)` for the
      generated 200-claim corpus of Story 02.0 Task 04 and for every Story 02.0 unit case.
- [ ] `scan()` results and log output are byte-identical to master for every existing test after
      the `_inventory` refactor.
- [ ] `extract-facts` exits `0` with zero facts, `2` on every failure listed in X12, and never `1`.
      `extract-facts --use-external-api` is an argparse error (exit `2`).
- [ ] **Amended 2026-11-24 (threat model, E1).** In a fresh interpreter with
      `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` patched to
      record and raise before `cli.main` runs, `extract-facts` records no socket call, and neither
      `docsentinel.fact_check.lenz` nor any `FACT_CHECK_BACKEND_MODULES` value is in `sys.modules`
      afterwards. The `extract-facts` call graph names no `httpx` (AST). `"httpx" in sys.modules`
      is **not** asserted (spaCy imports it). No code on its path reads
      `DOCSENTINEL_USE_EXTERNAL_API` or a `DOCSENTINEL_FACTCHECK_*` variable.
- [ ] No log record from the command contains any claim text (sentinel-sentence test).
- [ ] Every existing template loads and renders byte-identically. `scan --format facts-json` and
      `extract-facts --format json` both exit `2` with a message naming the right command.
- [ ] `tests/unit/test_mining_layering.py` and `tests/unit/test_fact_check_layering.py` stay green.
      `trace_salience` takes no `Config`.

## Test plan

| Layer | File (new unless noted) | Covers |
|---|---|---|
| Unit | `tests/unit/test_mining_salience.py` (extended) | `trace_salience` dispositions, signal fields, cluster size, order totality, `select_salient` == selected projection |
| Unit | `tests/unit/test_fact_check_candidates.py` (extended) | `SelectionPolicy`/`DS302_POLICY`, `select_candidates(policy=)`, `CandidateClaim` signal fields, `collect_candidates` has no `policy` parameter |
| Unit | `tests/unit/test_facts_template_context.py` | Loader `context` key: default, `facts`, unknown value, cross-context variable refused, untrusted-sink rule, `requires_extensions` refused for `facts` |
| Unit | `tests/unit/test_extract_facts_offline.py` | AST: no gate/backend/env reference on the `extract_facts`/`trace_candidates` path; `Config` has no weight/threshold field |
| Mock | `tests/mock/test_fact_check_single_source.py` | `detect()` with an open gate and a patched `_check_candidates` receives exactly `collect_candidates(...)`; `trace_candidates` patched -> both consumers see the patch |
| Mock | `tests/mock/test_extract_facts_engine.py` | `extract_facts()` with `trace_candidates` stubbed: overrides, `matches_ds302`, `include_rejected`, deep-not-ready `RuntimeError`, single-file target, empty invoker selection `ConfigError`, unreadable count |
| Integration | `tests/integration/test_extract_facts_cli_ds302.py` | CLI end to end over `tests/assets/ds302/` cases: `facts-text`/`facts-json`, `-o`, overrides, `--weights`, `--all`, exit codes, `--use-external-api` rejected, fresh-interpreter socket-guard and backend-absence check (E1, amended 2026-11-24), no claim text in logs (also with `-v`, E13) |
| Integration (Story 04.0) | `tests/integration/test_fact_check_extract_facts_equivalence_ds302.py` | The C11 end-to-end equality against the recording `FakeFactCheckClient` |

Deep cases skip with a reason when `deep_ready()` is false, as the `DS301` tests do.

## Docs to update

Deferred to Story 04.0 Task 04 (do not edit these in this story): `/docs/user/tutorial/cli.md`
(`extract-facts` section), `/docs/specs/report-template-format.md` (the `context` key and the facts
context), `/docs/user/tutorial/custom-reports.md` (one paragraph on `facts` templates),
`/docs/architecture/README.md`, `/CLAUDE.md` (Commands, Architecture), `/README.md`, and the
proposed `/RELEASE_NOTES.json` entry. Diagram follow-up: Story 04.0 Task 05.
