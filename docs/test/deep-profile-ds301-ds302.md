# Manual test checklist: deep-profile contradiction and fact-check rules (DS301, DS302)

This checklist exercises the deep profile by hand in three passes. `DS301` finds two documents
that disagree with each other. `docsentinel extract-facts` shows, offline, which claims `DS302`
considers worth checking. `DS302` then sends exactly those claims to the Lenz API. Milestone 0010
is complete, so all three are real. Both rules are advisory-only: they never fail a scan,
regardless of `--strict` (deep findings always exit `0`).

The deep profile no longer has a confirmation gate. `deep_confirm`, the
`--i-understand-deep-is-heuristic` flag and `DOCSENTINEL_DEEP_CONFIRM` were all removed in
Milestone 0010, so `--profile deep` is now enough and passing the old flag is an argparse error
(exit `2`). `DS302` keeps its own, separate consent gate, which is the subject of use case 3.

Every command below runs with `DOCSENTINEL_SETTINGS=off` so a real `~/.local/share/docsentinel/settings.json`
on the machine running the checklist cannot change rule selection or the active profile out from
under you. Never run these steps with your real settings file, and never set
`DOCSENTINEL_USE_EXTERNAL_API=1` or a `DOCSENTINEL_FACTCHECK_*` variable outside the scoped shell
session described below.

## Setup

```sh
uv sync --extra test --extra deep
uv run python -m spacy download en_core_web_sm
```

The deep profile needs `docsentinel[deep]` (spaCy + textacy) and the pinned `en_core_web_sm`
model; `uv run docsentinel doctor` reports `deep profile: not ready` with install guidance until
both are present, and `deep profile: ready` with two `✓` lines once they are. Note that `uv sync`
removes the spaCy model package, because it is not in the lock file, so re-run the `spacy
download` line after any sync.

## Use case 1 — DS301: fact-contradiction candidate (coverage discrepancy)

### Fixtures

[`examples/docs/ds301-demo-coverage-report-v1.md`](/examples/docs/ds301-demo-coverage-report-v1.md)
is a contributor guide to the test suite;
[`examples/docs/ds301-demo-coverage-report-v2.md`](/examples/docs/ds301-demo-coverage-report-v2.md)
is a quarterly report written for a review meeting. They are deliberately different kinds of
document in different voices, both about testing, and each states the quarter's coverage figure in
the middle of ordinary prose:

```md
Coverage is measured on demand rather than on every run, because the coverage plugin is not a
project dependency. DocSentinel scored 85 on the test coverage benchmark this quarter, which sits
above the configured floor but below where the deep-profile modules ought to be.
```

```md
The suite ended the quarter green on every supported interpreter, with two deliberate skips and no
flakes recorded in the nightly runs. This quarter DocSentinel scored 90 on the test coverage, and
the reviewers accepted that figure as the baseline for the next period.
```

`DS301` works by extracting a subject-verb-object (SVO) triple per paragraph (`mining/claims.py`,
via textacy over the pinned spaCy model) and normalizing the subject and predicate to a
`(subject_key, predicate_key)` grouping key — here `("docsentinel", "scored")` for both documents,
even though the sentences are worded differently and put "this quarter" in different places. Two
claims in the same group "disagree" when their extracted object numbers are both non-empty and
disjoint (`{85}` vs. `{90}`); the same rule applies to named entities when numbers are absent.

Because the claims sit inside real paragraphs, this fixture pair also shows the rule's
selectivity: the two documents yield **24** claims between them, and only the coverage pair is
reported. Everything else — release counts, interpreter names, skip counts — either fails to group
or has no competing number.

The wording of the claim itself still matters, though. A copula sentence like "DocSentinel's test
coverage is 85 percent" does **not** reliably produce a usable claim: textacy's SVO extractor only
populates `object_numbers` when the number is the head of the object span, not when it modifies a
following noun phrase (`"85 percent test coverage"` parses with the object span starting after the
`85`). Both fixtures were verified against the live extractor.

### Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | `DOCSENTINEL_SETTINGS=off uv run docsentinel scan examples/docs --include ds301-demo-coverage-report-v1.md --include ds301-demo-coverage-report-v2.md --profile deep` | Exit `0`; exactly one `DS301 fact-contradiction candidate` finding on `ds301-demo-coverage-report-v2.md`: `candidate contradiction: subject 'DocSentinel' claimed as '85' in ds301-demo-coverage-report-v1.md but '90' in ds301-demo-coverage-report-v2.md - review to confirm` |
| 2 | Same command, but scan only `--include ds301-demo-coverage-report-v1.md` | Exit `0`; `0 findings`: a lone claim has nothing to disagree with |
| 3 | Run step 1 with no confirmation flag and no confirmation environment variable | Exit `0`; `DS301` runs and reports. The deep-confirm gate (`deep_confirm` / `--i-understand-deep-is-heuristic` / `DOCSENTINEL_DEEP_CONFIRM`) was **removed** in Milestone 0010, so passing the old flag now fails with `unrecognized arguments` (exit `2`). The advisory notice `1 deep rule(s) evaluated (heuristic, advisory-only).` is still printed |
| 4 | Run step 1 with `-v` | stderr DEBUG lines `DS301: 24 claims compared, 1 candidates` (from `contradictions.py`) and `DS301: 1 findings in <n>s`. The claim count is the selectivity check: many claims, one candidate |
| 5 | Record a baseline: `DOCSENTINEL_SETTINGS=off uv run docsentinel baseline <scratch copy of the two files> --profile deep --output baseline.json`, then re-scan with `--baseline baseline.json` | The baseline file holds one `DS301:ds301-demo-coverage-report-v2.md:<hash>` fingerprint; the re-scan reports `0 findings` and logs `1 fingerprints, 1 findings suppressed` — the standard "reviewed, now a non-issue" workflow. The fingerprint is rule + path + message, so editing the surrounding prose does not invalidate it |
| 6 | Add `ignore = ["DS301"]` to a `[tool.doc_sentinel]` config at the scan root, re-run step 1 | `Enabled rules` drops `DS301`; `profile=deep: 1 rules selected, 0 evaluated`; `0 findings` |
| 7 | `uv run docsentinel scan --format json examples/docs --include ds301-demo-coverage-report-v1.md --include ds301-demo-coverage-report-v2.md --profile deep` | Schema-2 JSON (`"schema_version": 2`); the finding appears under the `ds301-demo-coverage-report-v2.md` document entry with `"severity": "warning"`, `"fault_class": "contradiction_candidate"`, `"tier": "heuristic"`, `"outcome": "advisory"`; the `v1.md` entry has an empty `problems` array |

### Adjusting DS301's weights and parameters

`DS301` is the odd one out in `docsentinel.toml`: unlike `DS201`–`DS204` and `DS302`, it exposes
**no** `Config` field at all — `detect(root, documents)` does not even take a `config` argument
(confirm with `grep -n "contradiction\|DS301" src/docsentinel/config.py`, which matches nothing,
and with the `—` in the options column of its row in `docs/user/reference/rules.md`). There is no
numeric "contradiction threshold" to raise or lower from the command line or `docsentinel.toml`.
The real levers are:

- **Rule selection**, not rule tuning: `select = ["DS3"]` to run only deep rules, or
  `ignore = ["DS301"]` to turn it off entirely (checklist step 6). This changes *whether* it runs,
  not *how sensitively* it matches.
- **Scope**: `--include`/`--exclude` (or the config equivalents) change which documents' claims
  are compared, which indirectly changes the candidate pairs DS301 can find — the only
  "sensitivity" knob that exists today without touching code.
- **The matching logic itself, in code, not config** (`detectors/contradictions.py::_disagree`):
  it is a binary, deterministic test — disjoint non-empty number sets, or disjoint non-empty
  entity sets — with no weight or score to tune. Loosening or tightening it (for example, treating
  `85%` and `85.0` as equal, or adding a numeric tolerance band for rounding) is a code change to
  `_disagree`, reviewed like any other detector change, not a configuration edit.
  `_CLOSED_ENTITY_TYPES` in `mining/claims.py` is the closest thing to a tunable "parameter" — it
  restricts which spaCy entity labels count as comparable objects (`ORG`, `PRODUCT`, `GPE`,
  `PERSON`, `CARDINAL`, `QUANTITY`, `PERCENT`, `DATE`) — again a code constant, not a config key.
- **The pinned model** (`mining/nlp.py::MODEL_NAME = "en_core_web_sm"`): upgrading it changes what
  gets extracted as a claim at all (the module docstring warns extraction is deterministic only
  for the pinned version), which is the single biggest behavioral lever over DS301's recall — and
  it is a dependency change, not a runtime setting.

The salience weights of use case 2 do **not** apply here: `DS301` compares every extracted claim
and never scores or ranks them.

## Use case 2 — extracting facts with `docsentinel extract-facts`

`docsentinel extract-facts` answers the question "what would `DS302` send?" **without sending
anything**. It runs the same extraction and the same selection `DS302` uses (plan contract C11:
one shared `collect_candidates`), then prints the result. It makes no network call, needs no API
key and has no consent gate — it is the rehearsal you run before you ever let a claim leave the
machine.

It deliberately rejects the scan-only options: `--profile`, `--select`, `--ignore`, `--baseline`,
`--strict`, `--use-external-api`, `--link-root`, `--reference-scope`, `--extension` and
`--allow-python-extensions` are all argparse errors (exit `2`).

### Fixture

[`examples/docs/New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md`](/examples/docs/New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md),
a press-style article about an MRI antenna, is the document whose facts we extract here and
fact-check in use case 3.

### How a claim becomes a fact

Each extracted claim is scored on three signals, each in `[0, 1]`, combined with weights that sum
to `1.0`:

| Signal | Meaning | Source |
|---|---|---|
| `numeric` | numeric density of the object: `min(1, len(object_numbers) / object_token_count)` | `mining/salience.py::numeric_density` |
| `entity` | named-entity density of the object, same shape | `mining/salience.py::entity_density` |
| `distinctiveness` | how unusual the claim's wording is across the scanned corpus | `mining/clustering.py`, via the shared TF-IDF vectorizer |

`DS302`'s weights are **fixed in code** and not configurable: `0.3` numeric, `0.3` entity, `0.4`
distinctiveness, with a near-duplicate clustering threshold of `0.92`
(`detectors/fact_check.py::DS302_POLICY`). Scored claims are ranked and filtered by the three
`fact_check_*` selection options, and every claim ends with exactly one disposition from
`mining/salience.py::DISPOSITIONS`:

| Disposition | Meaning |
|---|---|
| `selected` | it would be sent |
| `duplicate` | another member of its near-duplicate cluster was taken instead |
| `below_floor` | its score is under `fact_check_min_salience` |
| `document_cap` | its document already contributed `fact_check_max_claims_per_document` facts |
| `total_cap` | the scan already contributed `fact_check_max_claims_total` facts |

### Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | `DOCSENTINEL_SETTINGS=off uv run docsentinel extract-facts examples/docs --include New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md` | Exit `0`, no network. INFO `extract-facts: 1 documents read, 22 claims, 3 selected, 3 listed (policy ds302)`; three facts are printed, the first being `#1 score 0.711374 (numeric 0.5, entity 1.0, distinct 0.653436) cluster 18/1 paragraph 14: The team led by Nandita Saha tested the new MRI antenna by imaging the eye and orbit in volunteers using a 7.0 Tesla MRI scanner.` (a claim is one self-contained, single-sentence *statement* with its pronouns and bare definite noun phrases resolved: the source sentence says "The researchers tested the design ..."; headings, quotations and hedged sentences are not listed, and every fact is one sentence); the footer reads `Matches the DS302 selection for this configuration: yes` |
| 2 | Read the trailing notice | `Heuristic, offline claim extraction; no network call was made and nothing was verified.` followed by the statement that the selected facts are what `DS302` would send *if* it ran with both gates open on the same configuration, and that `fact_check_time_budget_seconds` can stop it earlier |
| 3 | Re-run with `--all` | All `22` claims are listed, each with its disposition appended: `3 selected`, `5 document_cap`, no `duplicate`, the rest `below_floor`. Footer: `Facts: 3 selected, 22 listed, from 22 claims` |
| 4 | Find the `7.0 Tesla` claim in the `--all` output (`#1`) | `score 0.711374 (numeric 0.5, entity 1.0, distinct 0.653436) ... selected`. A statement's numbers and entities cover the whole statement (subject included), so the `7.0` counts (`numbers` `7.0`, entity `CARDINAL:7.0`), and the resolved subject's name (`PERSON:nandita saha`) raises the entity signal |
| 5 | Note how newlines are rendered | None appear: statement extraction joins hard-wrapped source lines with a space, so no fact contains a newline. The facts template still routes the untrusted document text through the neutralizing filter (a control character would print as `\xNN`), so one fact is always one line |
| 6 | `--format facts-json` | `{"schema": "docsentinel-facts", "schema_version": 1, ...}` with `matches_ds302`, `include_rejected`, a `settings` block echoing `min_salience`/`max_per_document`/`max_total`/`weights`/`dedup_threshold`, a `summary` block, and a `facts` array whose entries carry `rank`, `path`, `paragraph_index`, `text`, `score`, `signals`, `cluster`, `numbers` and `entities` (here, for `#1`: `numbers` `["7.0"]` and `entities` `["CARDINAL:7.0", "PERSON:nandita saha"]`, which earned the `numeric 0.5` and `entity 1.0`) |
| 7 | `-o facts.json` with any format | The report is written to the file instead of stdout. **It contains document text**: keep it out of the scan root and out of version control, as the option's own help text says |
| 8 | Pass a scan-only option, e.g. `--profile deep` or `--use-external-api` | argparse error, exit `2`: `extract-facts` has no such option by design |
| 9 | Read the INFO start line with `-v` | `extract-facts started: root=..., format=facts-text, output=stdout, include 1, exclude 0, options <names>` — overrides are logged **by name only**, never by value, and `extract-facts` never logs claim text at any level (the `scan` DS302 trace lines do quote the first ten words of a claim, owner ruling 2026-11-27); each line has the form `[YYYY-mm-dd HH:MM:SS][INFO]: ...` |

### Fact consolidation

Before any score is computed, the document's sentences are turned into **statements**:
single-sentence, self-contained, checkable units. That step decides how many facts there are and
how they read. Scoring and selection (next section) only decide which of them are sent.

**These parameters are module constants and rules in `src/docsentinel/mining/claims.py`, not
configuration options.** No `docsentinel.toml` key or CLI flag changes them. Tuning means editing
the code. A change applies to `DS302` and `extract-facts` together, so `matches_ds302` stays `true`.
`DS301` still uses `extract_claims` and is not affected.

A statement is **never a join of sentences**. A sentence that refers back is *resolved*: the
pronoun or noun phrase that points outside the sentence is replaced by the earlier mention it
stands for. The resolution is classic rule-based anaphora resolution (number and animacy agreement,
nearest sentence first, subject before object), deterministic for the pinned spaCy model. It uses
no learned coreference model and no LLM, and it can pick the wrong antecedent: a statement is an
advisory candidate, never a verified fact. The pipeline runs in four stages.

**Stage 1 — Markdown to prose** (`_prose_blocks`, `_strip_inline_markdown`, `_parse`).

- Headings, whole-line bold pseudo-headings (`**Next Steps**`), thematic breaks, fenced code,
  front matter, table rows and HTML-only lines are removed. Each one is a *section boundary* that
  no later sentence may take an antecedent across.
- List and blockquote markers, a leading `Label:` (`_LABEL`: `Summary:`, `Date:`, `Note:`) and
  inline syntax (emphasis, link targets, images, code ticks) are stripped. Hard-wrapped lines are
  joined with a space.
- No sentence may start inside, or right after, an inline code span. This uses preset
  `is_sent_start`, with the same spaCy pipeline. So `` `Config(...)` `` or `` `scan(root=".")` ``
  no longer cut a sentence in two.

**Stage 2 — drop sentences a fact-check cannot confirm.**

| Parameter | Default | What it drops |
|---|---|---|
| `_is_declarative` (rule) | finite verb root with a subject | fragments, labels, imperatives, questions, a lead-in ending in `:`, a bare subordinate clause ("When you need those."), unbalanced brackets |
| `_is_headline` (rule) | 4+ words, every content word capitalized | titles and citation fragments |
| `_is_quotation` (rule) | opens with a quotation mark, or quoted text is at least half of it | direct quotes: opinions |
| `_HEDGE_MODALS` | `could may might would should will shall 'll` | predictions and possibilities. The modal is checked on the claim verb; for "X says ..." it is checked on the reported clause. `can` is kept on purpose: it states a capability |
| `_REPORTING_LEMMAS` | `say add note explain tell state claim suggest believe think argue` | none itself: it tells `_is_hedged` to look inside "X says ..." |
| `_RESULT_CONNECTIVES` | `as a result`, `therefore`, `thus`, `hence`, `consequently`, `so,` ... | a sentence opening with one states a consequence of the previous sentence and is dropped |

**Stage 3 — resolve and trim** (`_rewrite_sentence`).

| Parameter | Default | Effect |
|---|---|---|
| `_PRONOUN_CLASS` | `it they them he she him` and the possessives `its their his her` | a third-person pronoun subject or object is replaced by its antecedent from the previous `_PRONOUN_WINDOW` (`2`) sentences of the same section, nearest first, subject before object, inanimate first for "it", animate or collective first for "they". A pronoun already resolved inside its own sentence ("Because the antenna is light, it ...") stays |
| possessives | -- | "its/their/his/her N" becomes "the N of <antecedent>": "Their findings were published in Advanced Materials" becomes "The findings of the team led by Nandita Saha were published in Advanced Materials". For "their findings/results/paper" the possessor must be a person or a group |
| bare definite noun phrase | -- | "the antenna" or "those signals" is replaced by the earlier same-head mention that is more informative: an indefinite introduction ("a new MRI antenna") wins over a later definite one |
| `_AGENT_NOUNS` | `researchers team scientists engineers ...` | a bare definite agent ("the researchers") names the document's primary agent (the first anchored people-noun subject, here "a team led by Nandita Saha"), unless a same-head anchored mention is in the same paragraph. An organisation never replaces its people |
| `_SHELL_NOUNS`, `_CREATION_VERBS` | `design technology innovation device ...`, `develop build create ...` | a bare definite shell noun ("the design") names the primary artifact: the indefinite object the primary agent introduced with a creation verb ("has developed a new MRI antenna") |
| `_MAX_GROUNDING_TOKENS` | `12` | the replacement text is the antecedent's *grounding text*: its noun phrase plus post-modifiers holding a proper name or a number, appositions removed, article normalised to "the". Only a well-formed noun phrase (noun head, no verb, subordinator or wh-word) can be an antecedent |
| `_GLUE_CONNECTIVES` | `in addition`, `however`, `yet`, `but`, `also`, and with a comma only: `still`, `next`, `first`, ... | a leading connective is removed and the statement kept. `_GLUE_ADVERBS` (`also`) is removed wherever it stands |
| `_LABEL`, `_LEADING_FILLER` | `Summary:`, `now and today` | removed from the start of a statement; the next word is capitalized only then (so `scan()` keeps its case) |
| fronted demonstrative | -- | a fronted clause built on a demonstrative with no antecedent ("To overcome this limitation, ...") is removed |
| `_MAX_CLAUSES` | `4` | a sentence coordinating several predicates under one subject with "and" becomes one statement per predicate, the subject repeated and each resolved. A conjunct without auxiliaries inherits the root's, so "could X and Y" stays hedged in both. The split is skipped when a conjunct carries a time adverbial ("every week", "in 2025") that reads as shared |

**Stage 4 — re-check each rewritten statement.** The statement text is parsed again as one
sentence and must still be declarative, unhedged and independent (`_is_dependent`). It is dropped
when a pronoun or demonstrative still has no antecedent, so an orphan is never kept.

A statement's `numbers` and `entities` (`_statement_numbers`, `_object_entities`) cover **the
whole statement, subject included**, and the subject is the *resolved* one. The idiom "one of" is
not counted as a number. That is why the selection went from 1 to 3 without touching any salience
weight: the `7.0 Tesla` statement gets `numeric 0.5` from the number and `entity 1.0` from the
name its subject was resolved to.

How to verify a change to one of these parameters:

1. Re-run steps 1 and 3 of the checklist above and compare the `claims` count and the `--all` list.
2. Read every statement aloud. Each must be one sentence, make sense on its own, and name the
   same person, group or thing as the source sentence it came from. Compare a few against the
   article: a resolution can be wrong, and a wrong one reads fluently.
3. Run the extraction tests:
   `uv run pytest -p docsentinel.pytest_plugin tests/integration/test_mining_statements_ds302.py tests/unit/test_mining_claims.py`.
   The assets `tests/assets/ds302/statements_self_contained/doc.md` and
   `tests/assets/ds302/statements_resolved/doc.md` have one paragraph per rule.
4. Check a technical page too, for example `docs/user/tutorial/library.md`. Code spans, colon
   lead-ins and identifiers at the start of a sentence only show up in technical docs.

### Fine-tuning: weights and the other options

These options act **after** consolidation: they choose which statements are sent and cannot merge
or split one. The options fall into two groups, and the difference between them matters more than any single
value.

**Group A — the three config-backed selection options.** Real `Config` fields that `DS302` itself
reads, so a value set in `docsentinel.toml` changes both commands identically:

| Option | CLI override | Default | Effect |
|---|---|---|---|
| `fact_check_min_salience` | `--min-salience FLOAT` | `0.5` | Score floor; anything lower is `below_floor` |
| `fact_check_max_claims_per_document` | `--max-per-document INT` | `3` | Per-document cap; the rest is `document_cap` |
| `fact_check_max_claims_total` | `--max-total INT` | `25` | Per-scan cap; the rest is `total_cap` |

**Group B — the two exploration-only flags.** `--weights N,E,D` and `--dedup-threshold FLOAT` have
**no** configuration key and are never read by `DS302` (story decision X5). They exist to show how
the ranking responds, and nothing else.

The honesty marker ties the groups together. Any override — from either group, the Group A flags
included — makes the run diverge from what `DS302` would do with the project's own configuration,
so the output is stamped `matches_ds302: false` (`Matches the DS302 selection for this
configuration: no`). Setting the *same* value in the config file instead keeps it `true`. That is
the first thing to check when deciding whether a preview is trustworthy as a prediction:

| # | Experiment | Verified result |
|---|---|---|
| 10 | `--min-salience 0.32` on the article | `3 selected` (the document cap binds), and `matches_ds302 false` — the preview no longer predicts `DS302` |
| 11 | The same floor as `fact_check_min_salience = 0.32` in a `[tool.doc_sentinel]` config, with no CLI flag | The **same** `3 selected`, but `matches_ds302 true`. Identical selection, different trustworthiness: configure the floor rather than flagging it when you want the preview to mean something |
| 12 | `--weights 0,0,1` (pure distinctiveness) | A different ranking: `#1` becomes the `0.893289`-distinctiveness sentence about metamaterials, and the number- and entity-rich sentence the defaults put first drops away. `3 selected` — here the **document cap** binds, not the floor |
| 13 | `--weights 1,0,0 --min-salience 0.0` (pure numeric) | Only the `7.0 Tesla` statement scores (`0.5`, its `numeric` signal); every other score is `0.0`. Tied scores fall back to the deterministic `(path, paragraph_index, raw_sentence)` tie-break, giving paragraphs `14`, then `4` and `6` — document order, capped at `3` |
| 14 | `--dedup-threshold` at `0.1` / `0.3` / `0.92` / `1.0`, each with `--all` | `21` / `3` / `0` / `0` duplicates. `0.1` treats almost the whole article as one cluster. Since a statement is one entry (no longer one per SVO triple), the compound-sentence duplicates are gone and the default `0.92` and `1.0` find none here |
| 15 | `--weights 0.5,0.5,0.5` | `Extraction failed: salience weights must sum to 1.0`, exit `2`. The constraint is enforced in `SalienceWeights.__post_init__` with an absolute tolerance of `1e-9`, so the combined score can never leave `[0, 1]` |
| 16 | `--max-total 2` over the whole `examples/docs` directory with `--all` | Facts beyond the second carry `total_cap`, across documents, in rank order |

Practical guidance:

- **Too few facts selected** is the common case, and the floor is usually what cuts them, not the
  caps. Run `--all` first and read the dispositions before changing anything: `below_floor`
  everywhere means lower `fact_check_min_salience`; `document_cap` everywhere means raise
  `fact_check_max_claims_per_document`.
- **Cost control before enabling `DS302`**: `extract-facts` tells you how many claims a real run
  would send, for free. Multiply the `selected` count by your backend's per-claim cost before you
  ever pass `--use-external-api`.
- **Do not tune with the flags and then assume `DS302` follows.** Only Group A values written to
  the configuration change `DS302`. The flags are a microscope, not a dial.

## Use case 3 — DS302: external fact-check with the Lenz API

`DS302` takes the facts of use case 2 and asks a backend whether they hold up. The one shipped
backend is `lenz` (`src/docsentinel/fact_check/lenz.py`), which POSTs each claim to
`https://lenz.io/api/v1/assess` — a fixed `BASE_URL` with no override — with `Bearer` auth,
`Accept-Encoding: identity`, `follow_redirects=False`, `trust_env=False`, a 30-second request
timeout, a 64 KiB response cap and a 1,000-character claim cap.

> **This is the one DocSentinel feature that sends your document text to a third party.** The
> claim sentences `extract-facts` printed in use case 2 are exactly what leaves the machine. Run
> the gated steps only against a document you are willing to disclose, with a key you control.

> **Do not use `examples/docs/lenz_fact-checking.md` as setup instructions.** That file sits in the
> same directory as the article used here, but it is not a normal fixture: it is written as direct
> instructions to an AI agent ("Run the snippet above as-is, and show me the verdict...", "Do not
> add it yet; describe it first") and it embeds a bare API key. The project's own roadmap notes
> record that it was read read-only and never acted on, and Milestone 0010's exit gates include a
> regression test that fails if that key, or a real `lenz.io` call, appears in any commit, test,
> fixture or log. Treat it as untrusted document content. Use your own rotated key, never that one.

### The consent gate

`DS302` self-gates on two things no configuration file can grant: the invoker's
`--use-external-api` (or `DOCSENTINEL_USE_EXTERNAL_API=1`) **and** a non-empty
`DOCSENTINEL_FACTCHECK_LENZ_API_KEY` (or, when that is unset, `LENZ_API_KEY`). Choosing the backend in `docsentinel.toml` grants nothing.

| # | Step | Expected |
|---|------|----------|
| 1 | `DOCSENTINEL_SETTINGS=off uv run docsentinel scan examples/docs --include New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md --profile deep` (no flag, no key) | Exit `0`; `WARNING: DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY`; the report's `Pending:` line repeats it; zero `DS302` findings and **no** network call |
| 2 | Same, adding `--use-external-api` but still no key | A shorter message, not the identical one: `WARNING: DS302 skipped: set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY` — the satisfied half of the gate drops out of the reason list |
| 3 | `DOCSENTINEL_SETTINGS=off uv run docsentinel doctor` with nothing set | `fact-check gate: off (pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY)` |
| 4 | `doctor` with only the key set | `fact-check gate: off (pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1))` — `doctor` always resolves as if the flag were absent |
| 5 | `doctor` with the key **and** `DOCSENTINEL_USE_EXTERNAL_API=1` | `fact-check gate: on (backend: lenz)`. `doctor` still makes no request; it only resolves the gate and loads the backend class |
| 6 | A scan with `--use-external-api` and a malformed key, e.g. `DOCSENTINEL_FACTCHECK_LENZ_API_KEY=short` | `WARNING: DS302 skipped: backend lenz could not be initialised (FactCheckError)`, zero findings, and still **no** request: the key grammar (16–256 printable ASCII characters, no whitespace) is checked in the constructor before any `httpx` object exists, and the message never contains the key |

### Rehearsal with the real client and no network

Before spending a real key, exercise the actual Lenz request and response handling locally. The
client takes a `transport=` test seam, so you can drive the shipped code with `httpx.MockTransport`
in place of the network. Save this as a scratch script (do not commit it under `src/` or `tests/`)
and run it with `uv run python`:

```python
import json
import os

import httpx

from docsentinel import scan
from docsentinel.config import Config
from docsentinel.fact_check.lenz import LenzFactCheckClient
from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS

ARTICLE = "New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md"
KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"
sent = []


class _Stream(httpx.SyncByteStream):
    """A streamed body: the client refuses an already-read content= response."""

    def __init__(self, data):
        self._data = data

    def __iter__(self):
        yield self._data

    def close(self):
        pass


def handler(request):
    claim = json.loads(request.content)["claim"]
    sent.append(claim)
    print(f"  [mock] POST {request.url}  auth sent: {'authorization' in request.headers}")
    print(f"  [mock] claim ({len(claim)} chars): {claim[:70]!r}...")
    body = json.dumps({"claims": [{"claim": claim, "verdict": "false", "confidence": 0.78}]}).encode()
    return httpx.Response(200, headers={"content-type": "application/json"}, stream=_Stream(body))


class RehearsalLenz(LenzFactCheckClient):
    def __init__(self, api_key):
        super().__init__(api_key, transport=httpx.MockTransport(handler))


FACT_CHECK_BACKENDS["lenz"] = RehearsalLenz
os.environ[KEY_ENV] = "rehearsal-key-not-a-real-credential"
try:
    result = scan("examples/docs", config=Config(profile="deep"), use_external_api=True, include=[ARTICLE])
finally:
    del FACT_CHECK_BACKENDS["lenz"]
    os.environ.pop(KEY_ENV, None)

print(f"--- claims sent: {len(sent)} ---")
for finding in result.findings:
    print(f"  {finding.rule} | {finding.message}")
    print(f"       value: {finding.value}")
```

| # | Step | Expected |
|---|------|----------|
| 7 | Run the script as written | `claims sent: N`, where the claims are **the exact facts use case 2 selected** (up to the document cap of 3, in rank order; re-verify `N` for your script and document, the counts changed when DS302 moved to statement-level extraction). This is the contract between the two commands: `extract-facts` predicts the send list, `DS302` sends it |
| 8 | Read the finding | One `DS302` finding: `external fact-check: '<claim>' rated false by lenz - review to confirm`, with the confidence only in the report-only `value` field: `false (confidence 0.78): <claim>`. Keeping the confidence out of `message` is what makes baseline fingerprints stable when a verdict's confidence wobbles between runs |
| 9 | Change the scripted verdict to `"mixed"` and re-run | A `warning` finding of type `unverified claim` with `value` `mixed (confidence ...): <claim>` when the scripted confidence is at or above `fact_check_min_confidence`. Since the owner ruling R of 2026-11-27 every verdict is kept: `Mostly True` maps to `true`, `Half True` to `mixed`, any unknown label to `unverifiable` (printed in the INFO trace `DS302: fact i/n ... verdict unverifiable, ... not reported`, never a finding). Confidence may also be `high`, `medium` or `low` (0.9, 0.6, 0.3) |
| 10 | Script `{"error_code": "no_claim"}`, or `{"claims": []}` | `unverifiable` at confidence `0.0`, which is not reportable: zero findings, no warning. This is the "nothing checkable in that sentence" answer |
| 11 | Add `fact_check_min_confidence=0.79` to the `Config(...)` call, keeping the `false`/`0.78` verdict | Zero findings: the floor is an inclusive `>=`, so `0.78` no longer clears `0.79`. At exactly `0.78` the finding returns |
| 12 | Script a non-200 status, or a response larger than 64 KiB | A per-claim `FactCheckError` with a fixed message, logged as one WARNING naming the document only. Backend messages never carry request or response data — a header error can contain the `Bearer` value, which is why only the exception *type* name survives |

### The real run, with your own key

| # | Step | Expected |
|---|------|----------|
| 13 | Export a key **you** rotated (never the one in `lenz_fact-checking.md`), then run step 1's scan with `--use-external-api` | Up to `fact_check_max_claims_total` claims are POSTed to `lenz.io`; INFO logs `DS302: sent N claim(s) from M document(s) to backend lenz; <f> failed, <r> reported, <n> not sent (time budget)` — counts only; the per-claim trace lines before it quote the first ten words of each claim (owner ruling 2026-11-27) |
| 14 | Compare the sent count against the use case 2 preview | They match for the same configuration and selection, unless the time budget cut the run short |
| 15 | Set `fact_check_time_budget_seconds=1` against a slow or distant endpoint | Remaining claims are skipped with `DS302: time budget of 1 s exhausted; N of M claim(s) not checked`. This skip is logged **only**: it never reaches `ScanResult.pending` or the report's `Pending:` line, so a budget cutoff is invisible to anyone reading just the rendered report |
| 16 | Confirm nothing leaked | The key must not appear in stdout, stderr, the per-run log file, any finding field, any rendered report, or the client `repr` (the fixed `LenzFactCheckClient(base_url='https://lenz.io/api/v1')`). `tests/mock/test_fact_check_no_key_logged.py` asserts exactly this with a sentinel key |

### Adjusting DS302's weights and parameters

`DS302`'s own options are all validated `Config` fields (`config.py`,
`validate_fact_check_option`), re-validated at every layer that reads them, so even an injected
`Config` fails closed:

| Option | Default | Effect | Read by |
|---|---|---|---|
| `fact_check_backend` | `"lenz"` | Which registered backend receives claims | gate resolution, `_validated_backend` |
| `fact_check_min_salience` | `0.5` | Salience floor for selection (use case 2) | `select_candidates` |
| `fact_check_min_confidence` | `0.6` | Smallest backend confidence for a verdict to become a finding; inclusive `>=` | `_check_candidates` |
| `fact_check_max_claims_per_document` | `3` | Per-document send cap | `select_candidates` |
| `fact_check_max_claims_total` | `25` | Per-scan send cap | `select_candidates` |
| `fact_check_time_budget_seconds` | `300` | Wall-clock budget for the network stage; `1`–`3600` | `_check_candidates` |
| `fact_check_combination` | `"each"` | Groups selected claims into facts (`each`, `all`, or ranges like `1-6,7-8,9-16`); a combined fact over 1000 characters is not sent; `extract-facts` has no flag for it yet | `combine_candidates` in `_check_candidates` |

- **The salience weights and the dedup threshold are deliberately not on this list.** They are
  fixed in `DS302_POLICY` (`0.3`/`0.3`/`0.4`, `0.92`) and reachable only through the
  exploration-only `extract-facts` flags. There is no configuration key for them, so what `DS302`
  sends cannot be re-weighted from a config file — only the floor and the caps move.
- **To send less, tune selection, not confidence.** `fact_check_min_salience` and the two caps
  change what leaves the machine, so they are the privacy and cost levers.
  `fact_check_min_confidence` only filters verdicts after the round trip: it reduces report noise
  but never reduces egress.
- **An unrecognised backend name fails closed**: `fact_check_backend = "unknownbackend"` is a
  `ConfigError` (`must be one of: lenz`) before any candidate is touched, never a silent fallback.
- **No option opens the gate.** Configuration tunes an already-consented scan; it never grants
  network egress (ADR 0007 Contracts 3–4). A run that changes a `fact_check_*` value and sees no
  behaviour change should check `doctor`'s `fact-check gate:` line first.

## See also

- [Configuration reference: how to set options](../user/reference/configuration.md#how-to-set-options)
- [Rules reference: DS301, DS302](../user/reference/rules.md)
- [ADR 0007: fact-check backend protocol and dual consent gate](../adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md)
- [Threat model: 0010 fact-check gating](../security/threat-model-0010-fact-check-gating-2026-11-23.md)
- [Milestone 0010 plan and status](../roadmap/0010-fact-check/plan.md)
- [The test suite guide](README.md)
