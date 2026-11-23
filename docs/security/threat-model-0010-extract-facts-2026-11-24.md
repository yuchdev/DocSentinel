# Threat Model - Milestone 0010 Story 05.0 `extract-facts` (offline fact extraction) - 2026-11-24

Pre-code review of [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)
and its Tasks 01 to 04, against plan contracts C1, C5, C9 and C11, the ADR 0007 amendment of
2026-11-23, and owner rulings O1 to O4 (status.md, 2026-11-23). This document does not repeat the
consent-gate analysis. It relies on
[threat-model-0010-fact-check-gating-2026-11-23](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
(cited below as "gating M1-M12") and on
[threat-model-0007-template-engine-2026-10-31](/docs/security/threat-model-0007-template-engine-2026-10-31.md)
(cited as "0007 M1-M17", T2-R1, R4, R5). No product code or roadmap file was changed.

## Scope

- **In scope.**
  - `engine.extract_facts()` and the shared `_inventory()` step.
  - `detectors/fact_check.trace_candidates()`, `collect_candidates()` and `SelectionPolicy`.
  - `mining/salience.trace_salience()`.
  - `telemetry/facts_model.py`, the loader's new `context` key, and the `facts-text`/`facts-json`
    templates.
  - `reporting.render_facts()`, and the `cli.py` `extract-facts` handler, `doctor` lines and
    `-o` writer.
- **Trust boundaries.**
  1. The scanned tree: Markdown prose, which becomes claim text, paths, numbers and entities.
     It is untrusted.
  2. The project config, `--config FILE.json` and the user settings file. The project config is
     untrusted. The user file is trusted under its permission gate.
  3. `report_templates_dir` templates. They are untrusted and named by config.
  4. CLI arguments, `--template PATH` and `-o PATH`. These are trusted invoker input.
  5. Output to stdout or a file, and from there to terminals, CI logs and GitHub Actions log
     parsers.
  6. The process environment, which this command must not read for consent or keys.
- **Out of scope.** The DS302 egress path, the backend and the Lenz client. These are covered by
  the gating model and Story 03.0.

## Assets

- **The offline guarantee.** The command must never cause egress and never read a key. This
  is the property that makes it a safe consent preview.
- **Preview integrity.** What the user reviews must equal what DS302 would send (C11).
- **DS302 selection policy integrity.** An exploration policy must never reach DS302 (C5, X5, O1).
- **Document-derived text.** This means claims, paths and entities. It may be private, and it
  must not be logged.
- **API keys** (`DOCSENTINEL_FACTCHECK_*`). This command must never touch them. The real
  key-like value embedded in an example document is not reproduced here.
- **Terminal and CI-log integrity**, meaning no control-sequence or workflow-command injection.
- **Availability** of CI jobs that run the command.

## Threat actors

- **A1.** A contributor or repository author. They control the documents, `docsentinel.toml`,
  `report_templates_dir` and its templates.
- **A2.** A local process that races file swaps during a run. This needs local access.
- **A3.** A future maintainer who unknowingly widens the command, for example by adding a config
  key or a backend import.

## STRIDE analysis

- **Spoofing.** There is no authentication surface. The preview can be spoofed in two ways: a
  repository facts template can omit claims, and invisible code points can hide text (F5). The
  packaged names cannot be shadowed (0007 M9). Docs must direct consent review to the packaged
  templates.
- **Tampering and injection.** There is no shell, SQL or `eval`. Claim text reaches the text and
  JSON sinks (F3, F4, F5). The template loader takes a new key (F2, F4). Config can still set
  the three caps, which is intended.
- **Repudiation.** Not applicable. The command sends nothing. Past sends remain out of scope
  (O3; gating FC-10/M10).
- **Information disclosure.** Claim text could reach logs or error lines (F6). The `-o` file
  holds document text (F9). Keys and env are covered by F1 and gating M8/M12.
- **DoS.** Hostile template directories (F2), `--all` on large corpora, unbounded per-fact
  lists (F7), and late validation that wastes the extraction run (F6).
- **Elevation.** The command has no `--extension`, so `python:` code cannot run through it.
  A `facts` template cannot use `requires_extensions` or `ext.*` filters (F4). The CLI-only
  `--weights`/`--dedup-threshold` could leak into DS302 or a config file if implemented
  carelessly (F8).

## Findings

### [HIGH] F1 The specified proof of the offline guarantee cannot pass: spaCy itself imports `httpx`

- **Vector / evidence.**
  - Story README X10 and acceptance criterion 7 require `httpx` to be absent from
    `sys.modules` after `extract-facts`. So do Task 01 step 4.8 ("never imports `httpx`") and
    Task 04 step 8 (fresh-interpreter assertion).
  - The command necessarily calls `mining.nlp.load_pipeline()` and imports
    `docsentinel.mining.claims`. Verified locally, offline, with `python -I`: after those two
    calls, `"httpx" in sys.modules` is `True` and `"docsentinel.fact_check.lenz" in sys.modules`
    is `False`.
  - status.md (Story 01.0 Task 03 disposition) already records that "spaCy itself imports
    `httpx`".
- **Impact.**
  - The test that is meant to pin the command's central security property can never pass.
  - The likely outcomes are bad ones: the test is deleted, it is weakened to nothing, or someone
    "fixes" it with `sys.modules` manipulation. In each case the offline guarantee goes
    unverified. A later change that does construct an HTTP client, or imports a backend, would
    then go unnoticed.
  - CWE-1068 (inconsistent reference implementation and specification). It undermines CWE-359
    controls.
- **Mitigation.** E1: restate the invariant as follows.
  - No backend module is imported: `docsentinel.fact_check.lenz` and every value of
    `FACT_CHECK_BACKEND_MODULES`.
  - The `extract-facts` call graph contains no reference to `httpx` (AST).
  - No outbound socket is opened. Prove this in a fresh interpreter with
    `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` patched to
    record and raise before `cli.main` runs. Then assert that nothing was recorded.

### [MEDIUM] F2 Context-filtered listing would open and validate every hostile `report_templates_dir` file on every invocation

- **Vector / evidence.**
  - Task 02 step 4 says `packaged_template_names(context=)` should "do the same for the
    `report_templates_dir` discovery". Task 03 step 5 says the `doctor` `report_templates_dir`
    listing "splits the same way".
  - Today `available_templates` (`telemetry/loader.py:1930-1982`) explicitly does not open or
    validate files: "Files are not opened or validated here; a selected template is validated
    when loaded".
  - Splitting by context means reading the `context` key, which means opening and parsing each
    file.
  - Repository-controlled bounds: up to `MAX_DIRECTORY_TEMPLATES` (1024) files of up to
    `MAX_TEMPLATE_BYTES` (256 KiB) each. That is about 256 MiB of parsing and validation per
    `scan`, `extract-facts`, `--format` validation and `doctor`.
- **Impact.**
  - CWE-400/CWE-770 amplification by A1.
  - The parse attack surface widens from the one selected template to every file.
  - One malformed file breaks every invocation's template listing.
- **Mitigation.** E2.
  - The packaged context partition comes from the trusted packaged set. Either validate and cache
    it, or use a static name-to-context table pinned by a test.
  - The directory listing stays name-only.
  - A context mismatch on a directory template is detected only when the selected template is
    loaded, using the Task 02 errors (`… is a report template; use it with docsentinel scan` and
    its mirror).
  - `doctor` lists directory names under one line (`templates (report_templates_dir): …`,
    context checked at load). It does not split them.

### [MEDIUM] F3 `##[` in claim text reaches JSON output unescaped (GitHub legacy command marker)

- **Vector / evidence.**
  - JSON templates are not under the text sink-filter rule (`loader.py:1251`, an early `return`
    for non-text). `ensure_ascii` escapes neither `#` nor `[`.
  - The runner's legacy parser honours `##[` anywhere in a line (0007 T2-R1;
    `telemetry/filters.py:101-103` exists only for the text and GitHub sinks).
  - CR and LF cannot be injected, because JSON escapes them. A `##[error]…`/`##[group]` sequence
    in a document sentence, however, is emitted verbatim by `facts-json` to stdout.
  - The same latent issue exists for schema-2 `p.message`/`p.value`, but those are short and
    mostly path-shaped. Here the payload is free author prose of up to `MAX_CANDIDATE_CHARS`
    (1000) per fact, and the command is explicitly the thing to run "before consent", which
    makes running it in CI likely.
- **Impact.** Forged error or warning annotations and hidden log sections in an Actions job log
  (CWE-117, CWE-150). `set-env`/`add-path` were removed by GitHub after CVE-2020-15228, so this
  is limited to log integrity.
- **Mitigation.** E3.
  - For `facts`-context JSON, the engine serialises the `[` of every `##[` as `[`. This is
    lossless: the parsed string is unchanged, so the C11 byte-equality of `text` holds at the
    value level.
  - Docs: write facts output with `-o` and never print it in full to a CI log (CLAUDE.md CI rule).
  - Extending the same escape to `report` JSON is an owner question. It changes bytes only for
    hostile input.

### [MEDIUM] F4 The context split must hold at every scope entry point, and two "trusted" tags rest on producer discipline

- **Vector / evidence.**
  - The loader hard-codes `CONTEXT_SCHEMA` at two root scopes (`loader.py:901` text and `:918`
    json). Aliases (`_alias`, `:1094`) and `ext` resolution (`:1019`) also key off it.
  - The runtime renderer does not know the context. Story X9 checks mismatches only in the two
    `reporting` shims, so a library caller of `telemetry.engine.render_template` bypasses them.
  - The story table tags `…disposition` (closed set) and `run.notice` as trusted, so they may be
    placed in a text sink without a filter. That is safe only if `FactsModel.build` refuses any
    value outside `DISPOSITIONS` and `notice` is built from fixed vocabulary.
- **Impact.** If any one entry point uses the wrong schema, a `facts` template could place
  untrusted claim text without a sink filter. It could also reach `ext`. A forged disposition or
  notice would bypass `neutralize` (CWE-116).
- **Mitigation.** E4.
  - One `schema_for(context)` is used for both root scopes and for alias checks.
  - `FACTS_CONTEXT_SCHEMA` has no `ext` entry. `requires_extensions` and every `ext.*` filter
    are refused in `facts`.
  - `render_template` raises `TemplateError` when `template.context` and the supplied model kind
    disagree. This is defence in depth, in addition to the shims.
  - `FactsModel.build` raises `ValueError` for a disposition outside `DISPOSITIONS`. The notice
    comes only from engine constants.
  - Every untrusted list element is tagged (0007 M1/M2). A `facts` template with `output.sink:
    github` obeys the T2-R1 rules unchanged.

### [LOW] F5 Invisible code points let the text preview show less than DS302 would send

- **Vector / evidence.** 0007 R4 is still open: `filters.py` does not neutralise U+00AD,
  U+180E, U+2060-U+2064, the Hangul fillers, variation selectors or the tag characters
  U+E0000-U+E007F. In `facts-text` these render invisibly, while the same code points are part of
  `CandidateClaim.text` and would be sent.
- **Impact.** The consent preview is less than what is sent: hidden ("ASCII-smuggled") text
  goes to a third party under the user's key (CWE-451).
- **Mitigation.** E5.
  - `FactsModel` adds a trusted per-fact boolean, `hidden_characters`, true when the text holds
    any code point of category Cf, Co or Cn, or of the R4 list, that `neutralize` keeps.
  - `facts-text` prints a fixed marker on such lines.
  - Docs name `facts-json` (ASCII-escaped) as the authoritative review form.
  - Closing R4 globally remains the preferred long-term fix.

### [LOW] F6 Error paths: document tokens in exception text, and validation after the expensive stage

- **Vector / evidence.**
  - Task 03 step 3 prints any `ValueError` as `Extraction failed: <neutralize_text(message)>` and
    logs it once. `neutralize_text` does not bound length.
  - Exceptions raised inside spaCy, textacy or scikit-learn, under `trace_candidates`, are not
    controlled by DocSentinel and can carry tokens. Separately, X6 relies on the re-validation in
    `select_candidates`, which runs after every document has been parsed. Weights and threshold
    are validated in `trace_salience`, which is also after extraction.
- **Impact.**
  - A claim fragment can reach stderr and the log file, which breaks the "never log claim text"
    rule (CWE-209/CWE-532).
  - Minutes of CPU are wasted before an invalid `--max-total 0` is rejected (CWE-400, minor).
- **Mitigation.**
  - **E6.** Validate the three overrides, `weights`, `dedup_threshold` and `include_rejected`
    before `deep_ready()` or `load_pipeline()`, using the same validators: the config numeric
    validator, `SalienceWeights`, and the `dedup_threshold` unit check. NaN and infinity are
    refused.
  - **E7.** Inside `extract_facts`, any exception from `trace_candidates` other than
    `ConfigError`, `OSError` or `UnicodeDecodeError` is replaced by
    `RuntimeError("extract-facts: claim extraction failed (<TypeName>)")`. It is raised outside
    the `except` block, so it has no `__cause__` or `__context__`, and it is logged without
    `exc_info`. This mirrors gating M5. `scan()` is unchanged.

### [LOW] F7 Output and memory volume (`--all`, large corpora, per-fact lists)

- **Vector / evidence.**
  - The text is bounded: `CandidateClaim.text` is at most 1000 code points (`fact_check.py:76`).
  - `numbers` and `entities` come from object spans of the uncapped `raw_sentence`, so a single
    long, unpunctuated paragraph can carry thousands of them.
  - `--all` lists every claim. Rendering stops at `MAX_OUTPUT_CHARS` (64 MiB) or
    `MAX_ITERATIONS` (5M) with `TemplateError`, and never truncates (0007 M13/R5).
  - Extraction cost equals a DS301 run over the whole corpus, every time.
- **Impact.** Exit `2` with no output on very large `--all` runs, and CI time spent (CWE-770).
  There is no unbounded growth beyond the caps.
- **Mitigation.** E8.
  - Cap `ExtractedFact.numbers` and `entities` at 32 items of at most 200 code points each.
    These are preview-only fields that DS302 never sends, so C11 is unaffected.
  - Document that `--all` on a large corpus can hit the render cap.
  - A render failure with `-o` leaves no file. The existing `_write_report` renders first and
    then writes.

### [LOW] F8 Exploration settings must stay out of DS302, every config tier and shared state

- **Vector / evidence.** The design is sound: `collect_candidates` has no `policy` parameter, and
  the flags are CLI or library only (C11, X5, O1; gating "extract-facts" section). There are three
  residual vectors:
  - a handler that copies `vars(args)` into `dataclasses.replace(config, …)`;
  - a config key added later for convenience (A3);
  - module-global mutation, or a cache keyed without the policy (today only `mining/corpus.py`
    has an `lru_cache`, and it does not serve clustering).
- **Impact.** A repository or a library caller could silently change what DS302 sends (C5
  spirit, CWE-15).
- **Mitigation.** E9. Tests:
  - In every tier (TOML, pyproject, `--config` JSON, user settings), `weights`,
    `dedup_threshold`, `fact_check_weights`, `fact_check_dedup_threshold`, `include_rejected` and
    `selection_policy` each give the unknown-option `ConfigError`.
  - `inspect.signature` of `scan`, `detect` and `collect_candidates` has no `policy`, `weights`
    or `dedup` parameter.
  - After an in-process `extract_facts(weights=(0.2, 0.2, 0.6), dedup_threshold=0.5)`,
    `DS302_POLICY` and `_W_*` are unchanged, and `collect_candidates` equals its pre-call result.

### [LOW] F9 `-o/--output`, include/exclude and `--config` reuse

- **Vector / evidence.**
  - `_write_report` (`cli.py:1268-1284`) creates parents, overwrites and follows a symlink at
    the destination with umask permissions. That is acceptable for a trusted invoker path, and
    it is the same as `scan`.
  - The new risk is feedback. A facts file written under the scan root as `.md` is discovered by
    the next scan, so DS302 would extract the preview and send it again (the 0007 closure C2
    analogue).
  - Include/exclude go through `normalize_invoker_selectors` and `check_invoker_selector_shape`,
    and `--config` through the strict JSON reader with the refused-key set. Neither changes
    (ADR 0005/0006 threat models).
- **Impact.** Duplicate egress of document text on a later gate-open scan. The file holds
  document text (CWE-538 if committed).
- **Mitigation.** E10.
  - Docs: write facts output outside the scan root, or under an excluded path, and never commit
    it.
  - Tests: `-o` after a forced render failure leaves no file. `--include ../x`, a `##[` value
    and `exclude .` exit `2` exactly as for `scan`.

### [LOW] F10 Re-read after partition follows symlinks (pre-existing, now echoed to stdout)

- **Vector / evidence.** `fact_check.py:320-321` reopens `root / doc.path` with a plain `open`
  after `_partition_readable`. A2 can swap a document for a symlink between the two reads, and
  the target's sentences then appear in the output. This is shared by DS302 because C11 makes it
  one function.
- **Impact.** A local file read through the preview (CWE-367/CWE-59). It needs a concurrent local
  attacker.
- **Mitigation.** E11, a follow-up allowed to land after this story: open with `O_NOFOLLOW`,
  `fstat` with `S_ISREG`, or reuse the text already read by the partition step. One change
  covers both consumers.

### [INFO] F11 `matches_ds302: true` is conditional

- A `true` value holds only with both gates open and DS302 in the active rules. `select`,
  `ignore` and `profile` are read by `scan` but not by this command.
- It also needs the same user settings layer and the same spaCy model. `fact_check_time_budget_seconds`
  can stop DS302 before the end of the list.
- **Mitigation.** E12: the fixed notice says these are "the claims DS302 would send, at most and
  in this order, if it ran with both gates open on the same configuration and selection".

### Not applicable or no finding

- **Logging.** The design (counts and option names only, paths through `safe()`) is correct.
  E13 extends the sentinel test to `-v` (DEBUG, including the `trace_salience` stage counts), to
  the `config:` INFO line and to the E7 error path.
- **Environment.** The command reads only the variables that config loading and logging already
  read. It reads no consent or key variable (gating M8, extended by Task 03 step 4).
- **Elevation through extensions.** The command has no `--extension`, and `render_facts` takes
  no extensions. `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS` is not read.
- **Exit codes.** The command never exits `1`, so it cannot be mistaken for a gate.

## Mitigations

| ID | Mitigation (one line) | Implements | Test (Task 04) |
|---|---|---|---|
| E1 | Offline invariant is "no backend module, no `httpx` reference on the path, no socket", not "`httpx` absent" | README X10/AC, Task 01 step 4.8 | integration `test_extract_facts_cli_ds302.py`: fresh interpreter with a socket guard and backend-module absence; unit `test_extract_facts_offline.py`: AST, no `httpx` name |
| E2 | Directory template listing stays name-only; context is checked only when the selected template loads; packaged partition is static or validated | Task 02 step 4, Task 03 step 5 | unit `test_facts_template_context.py`: an open/parse spy shows listing opens no directory file; malformed directory file breaks only its own selection; integration `doctor` line |
| E3 | `facts` JSON serialises the `[` of `##[` as `[` (lossless) | Task 02 steps 2-3 | unit `test_facts_template_context.py`: `##[error]x` claim gives no `##[` in output and `json.loads` round-trips equal |
| E4 | One `schema_for(context)`; no `ext` in facts; engine-level context check; disposition validated; notice from constants | Task 02 steps 1, 2, 5 | unit `test_facts_template_context.py`: cross-context at text, json and alias scope; `ext.*` filter refused; `render_template` mismatch raises; bad disposition raises; `{facts|json}` without `neutralize` refused; github-sink facts template obeys T2-R1 |
| E5 | Trusted `hidden_characters` flag and a fixed marker in `facts-text` | Task 02 steps 2-3 | unit `test_facts_template_context.py`: U+E0041 and U+2060 claims are flagged and marked |
| E6 | Validate overrides and policy (finite numbers, ranges, `bool`) before deep readiness and extraction | Task 01 step 4.3 | mock `test_extract_facts_engine.py`: `nan`, `inf`, `--max-total 0` raise with a `load_pipeline` spy not called |
| E7 | Extraction-stage exceptions become a type-name-only `RuntimeError` with no chaining and no `exc_info` | Task 01 step 4, Task 03 step 3 | mock `test_extract_facts_engine.py` and integration: patched `extract_claims` raising `ValueError(<sentinel sentence>)`; sentinel absent from stderr, log file and records |
| E8 | Cap per-fact `numbers`/`entities` (32 items of 200 code points) | Task 01 step 4.4, models | mock `test_extract_facts_engine.py`: 10,000 entities capped; integration: `--all` over a generated corpus succeeds; forced cap overflow with `-o` leaves no file |
| E9 | Exploration names refused in every config tier; no policy parameter on DS302 surfaces; no shared-state leak | Task 01 step 2, Task 03 step 1 | unit `test_extract_facts_offline.py` (signatures, `Config` fields); unit config cases for four tiers; mock `test_fact_check_single_source.py` (in-process leak check) |
| E10 | `-o` keeps existing semantics; docs warn against writing under the scan root or committing | Task 03 step 2.6; Story 04.0 Task 04 docs | integration: render failure leaves no file; selector refusals match `scan` |
| E11 | Re-read without following symlinks (follow-up; covers DS302 too) | Task 01 step 2 (or follow-up) | mock: document swapped to symlink after partition is not read |
| E12 | Notice wording states the gate, rule-selection and budget conditions | Task 01 step 4.6 | mock `test_extract_facts_engine.py`: exact notice constants |
| E13 | Sentinel no-claim-text test also runs with `-v` and on the E7 path | Task 03 step 2 | integration `test_extract_facts_cli_ds302.py` |

Existing controls relied on, not duplicated: 0007 M1-M17 (loader, sinks, caps), gating M8
(env reads), M9 (closed-gate laziness for `scan`) and M12 (test env isolation), and ADR 0005/0006
selectors and config.

## Required spec amendments

- **Story README.**
  - X10, Security notes item 2, and acceptance criterion 7: E1 wording.
  - Security notes: add E3, E5 and E9.
  - Facts context table: add `…hidden_characters` (bool, trusted).
- **Task 01.**
  - Step 4.8: "never imports a backend module, constructs no HTTP client, opens no socket" (E1).
  - Step 4.3: validate everything before step 4.2 (E6).
  - New step: the E7 exception wrapper.
  - Step 4.4: E8 caps.
  - Step 4.6: E12 notice text.
  - Step 2: the E11 note.
- **Task 02.**
  - Step 4: the directory listing stays name-only (E2).
  - Step 1: `schema_for` at both root scopes and alias checks, and no `ext` in facts (E4).
  - Step 5: an engine-level context check (E4).
  - Step 2: disposition validation, `hidden_characters` (E4, E5) and the `##[` JSON escape (E3).
  - Step 3: the `facts-text` marker (E5).
  - Acceptance: add E3, E4 and E5 cases.
- **Task 03.**
  - Step 5: one name-only `report_templates_dir` line (E2).
  - Step 3: the E7 path prints the fixed text.
  - Acceptance: add `-v` to the sentinel test (E13).
- **Task 04.**
  - Step 8: replace the `"httpx" in sys.modules` assertion with E1.
  - Add the E2 to E13 tests listed above.

## Residual risks

- **RR1.** A repository-supplied facts template, selected explicitly by name, can still omit
  claims from the preview. Docs must say to review consent with the packaged templates.
- **RR2.** An untrusted project config sets the three caps shown in the preview. This is intended,
  and it is bounded by the config limits (gating FC-13 and OQ1).
- **RR3.** 0007 R4 stays open globally. E5 covers only the facts preview.
- **RR4.** Equality with DS302 holds only for the same spaCy model version (Story README).

## Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL finding, so the merge is not blocked. F1 (HIGH) is a specification defect,
not an exploitable flaw: the command has no egress path by design. However, the amendment for E1
must be applied before Task 04 is written, so that the offline guarantee is actually verified.
E2, E3 and E4 (MEDIUM) must land in Task 02 before merge. E5 to E10, E12 and E13 land with their
tasks. E11 may follow in a later change.
