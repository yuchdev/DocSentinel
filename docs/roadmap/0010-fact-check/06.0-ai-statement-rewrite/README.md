# Story 06.0 — Optional AI-assisted statement rewrite

**Profile:** none directly (a post-processing stage; it rides on whichever of `extract-facts` /
`DS302` open decision [O5](#decisions) attaches it to — `extract-facts` stays profile-independent,
`DS302` stays `deep`) · **New CLI flag (name open, decision Y4/O6):** `--ai-rewrite`
(`DOCSENTINEL_USE_AI_REWRITE=1`) · **New public API (shape open, decision Y2/O5):** extends
`ExtractedFact`/`FactExtractionResult` and/or `scan(ai_rewrite=)`, never a `Config` field.
**Touched/new sources (described, not yet written; nothing in this list exists in the tree
today):** new package `src/docsentinel/rewrite/` (`__init__.py`, `protocol.py`,
`anthropic_backend.py`), `src/docsentinel/mining/claims.py` (additive, pure signal only),
and — depending on O5 — `src/docsentinel/detectors/fact_check.py`, `src/docsentinel/engine.py`,
`src/docsentinel/models.py`, `src/docsentinel/cli.py`.
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (contracts C1, C5, C9,
C11, new C12). **Depends on:** Story 01.0 (the dual-gate precedent and its CLI/env/`Config`
conventions), Story 02.0 (the salience/candidate pipeline this stage attaches to), Story 05.0
(`extract-facts`, the natural first consumer per the owner's own framing). **Conditionally on
Story 03.0:** only if decision O5 attaches this stage to `DS302`; the `extract-facts`-only option
in O5 never needs it.
**Security-sensitive:** **high.** This is DocSentinel's first feature that sends document-derived
text to a *generative* model and feeds its *generated* text back into the pipeline — not a
closed-set verdict, as `DS302`/Lenz returns. It opens a brand-new third-party destination
(Anthropic) and a secret whose environment-variable name deliberately departs from this
project's own per-backend naming convention (contract C3). A dedicated pre-code threat model is
required before any Python Expert task starts (mirroring Stories 01.0 and 03.0) and is named, not
written, in this story (see [Security notes](#security-notes)).

> **Added 2026-11-25 (owner request).** "optional AI-assisted step after `docsentinel fact-check`.
> If the resulted set of facts may seem disconnected and either of them can't be checked
> independently, process the result with AI, on the first step using Anthropic API and
> `ANTHROPIC_API_KEY` with simplest model and clear instructions - rephrase statements borrowing
> content from previous statements, to make them processed as independent self-contained, atomic
> statements."

> **Note 2026-11-26 (owner decision needed on scope).** After this story was specified, a
> deterministic, rule-based anaphora resolution landed in `mining.claims.extract_statements`: a
> statement is now one sentence (or one clause), a third-person pronoun, a possessive or a bare
> definite noun phrase is replaced by its antecedent, and a statement with an unresolved pronoun is
> dropped. The "joining" and `MAX_STATEMENT_SENTENCES` this story's Goal refers to no longer exist,
> so an AI stage would start from already-resolved statements. The owner should re-evaluate this
> story's scope and need. The story text and its open decisions below are deliberately unchanged.

## Resolving "`docsentinel fact-check`"

There is no literal `fact-check` subcommand. The owner's description matches the two existing
pipelines that already produce a bounded candidate-statement set and already share one candidate
source (contract
[C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts)):

- `docsentinel extract-facts` / `engine.extract_facts()` — offline, no network, produces
  `ExtractedFact`/`FactExtractionResult` ([Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)).
- `DS302`'s `detect()` — sends `CandidateClaim`s to the Lenz backend
  ([Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md),
  [03.0](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md)).

Both are fed by `trace_candidates()`/`collect_candidates()` in `detectors/fact_check.py`. Where the
new rewrite stage attaches to this shared seam is **decision Y2 / open question O5** below: it is
not decided here.

## Goal

Give an invoker an optional, dual-gated way to turn a candidate statement that still reads as
disconnected from its source paragraph — a pronoun or connective the extraction's own joining
(`mining.claims.extract_statements`, up to `MAX_STATEMENT_SENTENCES` sentences) could not fully
resolve — into an independent, self-contained, atomic statement, by asking a fixed, pinned
Anthropic model to rephrase it using only the statement's own text and its immediate predecessor
context. The original statement is always kept alongside any rewritten text, so a reviewer can see
exactly what the model changed; a rewrite that fails or looks invented falls back to the original,
logged, never silently.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| 01 — ADR 0008 and gate contract | ADR 0008 (`Proposed`), realizing plan contract C12 and the ratified Y-decisions below | Architect | ⬜ Not started |
| 02 — Pre-code threat model | A new `threat-model-0010-ai-rewrite-*` document (number reserved by this task's naming, not written) covering prompt injection, hallucination/overclaim validation, and the Anthropic client's transport hardening, mirroring the Lenz egress review's E1–E13 shape | Security Auditor | ⬜ Not started |
| 03 — `docsentinel.rewrite` package | `protocol.py` (`StatementRewriter`, `RewriteResult`, `RewriteOutcome`), `anthropic_backend.py` (`AnthropicRewriteClient`), its own import tripwire test (mirrors `tests/unit/test_fact_check_layering.py`) | Python Expert | ⬜ Not started |
| 04 — Mining-layer rewrite-candidate signal | `mining/claims.py` additive `flag_rewrite_candidates()` (pure, `Config`-free, no network; reuses the existing anaphora/back-reference heuristic) | Python Expert | ⬜ Not started |
| 05 — Gate, wiring and fail-soft application | The new consent gate, the stage wired into the location decision O5 ratifies, the original/rewritten data contract, output validation and the fallback-to-original path | Python Expert | ⬜ Not started |
| 06 — CLI/library surface and honesty lines | `--ai-rewrite`/`ai_rewrite=`, `doctor`/`rules` lines, CLAUDE.md and `cli.md` updates stating the dual requirement and the "heuristic paraphrase, not verified fact" framing | Python Expert | ⬜ Not started |
| 07 — Fixtures and tests | Unit (mining signal, protocol/result validation), mock (Anthropic client transport against a fake, never real network), integration (fail-soft fallback, end-to-end against a fake `StatementRewriter`) | Testing Expert | ⬜ Not started |

Execution order mirrors Stories 01.0/03.0: Task 01 (ADR) only after the owner ratifies the open
decisions below; Task 02 (threat model) before Task 03 starts; Tasks 03–04 may run in parallel;
Task 05 depends on both; Task 06 and 07 come last. No task file beyond this README exists yet.

## Scope

- An optional, dual-gated post-processing stage that rewrites a flagged candidate statement into
  an independent, self-contained, atomic form using one fixed, pinned Anthropic model.
- A pure, mining-layer heuristic signal — reusing the anaphora/back-reference detection
  `mining/claims.py`'s `extract_statements` already computes internally — that flags which
  statements are even offered for rewrite, bounding cost and exposure exactly as the existing
  salience filter bounds `DS302`'s candidate set (plan principle 3, by analogy).
- A new structural `StatementRewriter` Protocol and exactly one backend
  (`AnthropicRewriteClient`), mirroring the `FactCheckClient`/`LenzFactCheckClient` precedent: a
  swappable backend boundary with fixed transport constants on the class, never sourced from
  config (plan principle 7, C4, by analogy).
- A transparency-preserving data contract: the original statement text is always retained
  alongside any rewritten text and its validation outcome; nothing is silently overwritten.
- A fail-soft contract: any per-statement failure (timeout, malformed/invalid model output, a
  response-shape mismatch, a failed hallucination check) falls back to the original text, logged,
  and never raises into `scan()` or `extract_facts()` (mirrors plan contract C8).
- A second, independent, explicit consent gate for this brand-new third-party destination (plan
  principle 4 / contract C1, extended as new contract C12), never inferred from the presence of
  `ANTHROPIC_API_KEY` alone.

## Non-goals

- Deciding, in this task, whether the stage feeds `extract-facts`, `DS302`, or both shared through
  one seam (decision Y2 / open question O5). A recommendation is given; it is not adopted here.
- Writing ADR 0008, the threat model, or any code. This story is specification only, exactly like
  the rest of this milestone's spec-authoring passes.
- A second Anthropic model tier, a multi-turn conversation with the model, batching several
  statements into one call, or rewriting anything beyond one bounded rephrase per flagged
  statement.
- Changing `DS301`, `extract_claims`, or the shape `extract_statements` returns. The mining-layer
  addition (Task 04) is purely additive.
- Any change to `DS302`'s rule code, severity, fault class or finding type. This is a text
  pre-processing stage, never a new rule; it changes *what text* a rule sees or shows, never
  *whether* a rule fires.
- A new baseline mechanism. If `DS302` ends up in scope (O5), its findings keep today's generic
  baseline unchanged (plan contract C6).
- A UI/CLI surface for inspecting a past rewrite beyond what the data contract already persists on
  that run's output (mirrors Story 05.0's non-goal on "what DS302 sent").
- Proxy support, retries, or a circuit-breaker on repeated Anthropic failures (mirrors the Lenz
  client's stated non-goals and open follow-ups OQ-E1/OQ-E2).

## Design

### Decisions

Every row is a recommendation so work could proceed if ratified; rows marked **OPEN** are
genuinely undecided judgment calls flagged for the owner, not silent choices, per this task's
instructions.

| # | Decision | Rationale |
|---|---|---|
| Y1 | No new rule code. This stage changes what text a rule sees or a report shows, never whether a rule fires or the deep profile's exit code | Confirm. A new `DSxxx` code would wrongly imply a new detector; this is a pipeline stage |
| Y2 | **OPEN.** Where the stage sits: (a) after candidate selection, before `extract-facts` renders output only; (b) after candidate selection, before `DS302` sends to Lenz only; (c) in one shared place feeding both, matching C11's "one candidate source" spirit. **Recommended: (c), shared**, applied as a thin optional pass over `CandidateClaim`/`ExtractedFact` text right after `collect_candidates()`/`trace_candidates()` and before either consumer uses it | (c) keeps one implementation instead of two, matching why C11 itself exists. But it is flagged OPEN because it changes two long-standing guarantees at once: `extract-facts`'s "offline, no network, no gate" invariant (C11/Story 05.0 decision X10) and `DS302`'s risk surface (a second third-party destination, Y13 below). A narrower (a)-only or (b)-only choice avoids one of those two changes; the owner should pick knowingly, not by default |
| Y3 | A new top-level package `docsentinel/rewrite/` (`protocol.py` + `anthropic_backend.py`), mirroring `fact_check/`'s split and its own import tripwire test | `mining/` cannot hold it (C9 forbids network I/O and `Config`); `fact_check/` has a different Protocol shape (verdict/confidence, not rewritten text) and a different third party. A sibling package keeps both auditable as small, single-purpose modules with no upward imports, exactly like `fact_check/` was placed beside `mining/` (ADR 0007 driver 9, E1 precedent) |
| Y4 | **OPEN** (exact names). Opt-in gate 2-shaped surface: CLI flag `--ai-rewrite` on `scan`/`baseline`/`extract-facts` (whichever Y2 selects), keyword `ai_rewrite=`/`weights=`-style library argument, and `DOCSENTINEL_USE_AI_REWRITE=1` (exact match), mirroring C1 gate 2's flag-or-env shape and its strict `"1"` comparison | Mirrors the one proven pattern this project already has for "a new, independent, explicit network-egress consent" (C1 gate 2). A different name is possible; flagged because naming is cheap to get wrong once documented |
| Y5 | **OPEN** (the divergence itself). The API-key environment variable is the plain `ANTHROPIC_API_KEY`, not `DOCSENTINEL_FACTCHECK_ANTHROPIC_API_KEY` or any `DOCSENTINEL_`-prefixed name — a deliberate departure from plan contract C3. **Recommended: accept the divergence**, because the owner specifically asked for the standard name every other Anthropic SDK/tool already reads, and the independent Y4 gate (not inferred from key presence) is exactly the safeguard C3's per-backend naming was never meant to provide here | A developer may already export `ANTHROPIC_API_KEY` in their shell for an unrelated tool (their own Claude Code session, for instance). Its mere presence must never silently enable new egress — that is why Y4's gate is mandatory and independent, exactly like C1 gate 2 does not infer consent from `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` being set either. This still departs from "one environment variable per backend" (C3); it is flagged, not silently extended |
| Y6 | Fixed transport constants on `AnthropicRewriteClient`, never sourced from config (extends C4): `BASE_URL = "https://api.anthropic.com"`, `MESSAGES_URL = BASE_URL + "/v1/messages"`, `MODEL_ID = "claude-haiku-4-5-20251001"` (pinned, dated, not an alias), `ANTHROPIC_VERSION` header pinned, `REQUEST_TIMEOUT_SECONDS`, `MAX_RESPONSE_BYTES`, `MAX_OUTPUT_TOKENS`, a fixed `SYSTEM_PROMPT`. No retries. `trust_env=False`, no redirects — mirroring the Lenz client's E1–E5/E10 shape exactly | "Simplest model" is made concrete: Claude Haiku 4.5 is the current cheapest/fastest Claude model suited to a narrow, bounded rewrite task. Pinning the exact dated model id (not an alias such as `claude-haiku-4-5`) matches this project's existing dependency-pinning discipline (`httpx>=0.28,<1` with an exact locked version in `uv.lock`) and avoids silent behaviour drift if Anthropic repoints an alias later |
| Y7 | **OPEN** (exact signal shape). A new pure, additive mining-layer function — tentatively `mining.claims.flag_rewrite_candidates(claims) -> frozenset[int]` or an additive `Claim` field — flags a statement that still carries an unresolved back-reference signal after `extract_statements`'s own joining: for example a dependent sentence dropped because its anchor already held `MAX_STATEMENT_SENTENCES` members, or a statement whose `_needs_context`-style heuristic still returns non-`None` on the final joined text. Only flagged statements are ever offered to the rewrite stage | This is the "pure algorithmic part" constraint 8 calls for: it reuses the anaphora/back-reference signal `extract_statements` already computes internally rather than inventing a second heuristic, stays `Config`-free and network-free (C9), and bounds which statements even become a rewrite candidate — the same shape of bound the existing salience/dedup filter gives `DS302`. The exact function shape (new field vs. side-channel function, exact unresolved-signal rule) is an implementation judgment call, flagged rather than fixed here |
| Y8 | Fail soft, never silent-replace (extends C8). A new data contract (below) keeps `original_text`, `rewritten_text` (equal to `original_text` unless accepted), and an `outcome` (`"accepted"`, `"rejected_shape"`, `"rejected_hallucination"`, `"skipped_error"`). A rejected or failed rewrite falls back to `original_text`, logged once, never raised into `scan()`/`extract_facts()` | Mirrors how `DS302`'s `Finding.value` keeps the exact sent text separate from the verdict, and how `extract-facts` already frames itself as a preview, not a send (Story 05.0's transparency ethos). A reviewer must always be able to see what the AI changed, or that it changed nothing |
| Y9 | A minimal structural validation gate before any rewrite is accepted: same statement count and order as the input (one rewrite per flagged statement, nothing added or dropped), and a provenance check that the rewritten text's content tokens (nouns, numbers, named entities) are a subset of the union of the original statement's own tokens and its immediate joined predecessor sentence(s). A rewrite failing either check is `"rejected_shape"`/`"rejected_hallucination"` and falls back per Y8 | The owner's ask ("rephrase ... borrowing content from previous statements") is also the exact shape of DocSentinel's first correctness-critical new-fact risk: the model could introduce a claim not present in the source text, which a human or Lenz would then treat as the document's own claim — worse than doing nothing. The exact token-provenance algorithm is deferred to implementation and the threat model (Task 02); this row fixes only the requirement, not the algorithm |
| Y10 | A structural prompt-injection defense is mandatory, not optional: the statement (and its borrowed context) is always wrapped in an explicit, clearly delimited data block, and the fixed `SYSTEM_PROMPT` explicitly instructs the model to rephrase only, never to follow any instruction that appears inside the delimited statement text | The document's own content — which the rewrite step necessarily includes in context — is the one thing in this whole milestone that is genuinely attacker-controlled free text handed to a model with instruction-following behaviour. This is new relative to `DS302`/Lenz, which only ever returns a closed-set verdict/confidence, never generated text |
| Y11 | **OPEN.** A new ADR 0008 (recommended) versus an amendment to ADR 0007. **Recommended: new ADR 0008**, reserved, not written here | The dual-gate *pattern* is the same shape as ADR 0007's (invoker-only flag/env plus a required key), but the consent surface's secret-naming convention (Y5), the backend Protocol's I/O shape (rewriting text, not returning a verdict — Y3), the third party (Anthropic, not Lenz) and the risk class (generated text re-entering the pipeline, not a closed-set verdict) are all materially different. An amendment would stretch ADR 0007's "Context and Problem Statement" past what it was written to cover |
| Y12 | If Y2 resolves to (a) or (c) (`extract-facts` is in scope), `extract-facts`'s existing "offline, no network, no gate, no backend" invariant (plan contract C11, Story 05.0 decision X10, and the fresh-interpreter socket-guard test) must be amended to "offline unless `--ai-rewrite` is also explicitly passed", a second explicit gate layered on one command. Every place that states the offline guarantee (`doctor`, CLI help, `docs/user/tutorial/cli.md`, the fresh-interpreter test) must say so plainly whenever `--ai-rewrite` is used, and `extract-facts`'s exit-code contract (never `1`, only `0`/`2`) is unaffected | This is a genuine amendment to a documented invariant other tests and docs currently assert byte-for-byte; it is called out so it is not discovered as a silent regression later |
| Y13 | If Y2 resolves to (b) or (c) (`DS302` is in scope), `DS302` gains a second third-party network destination (Anthropic, beside Lenz) and a second secret inside one rule's `detect()`. This touches ADR 0007 Contract 4 ("fixed transport") only by addition (the Lenz client is untouched) but does touch Decision Driver 9 ("import discipline... the mining layer stays pure") and needs its own egress threat-model pass, parallel to but separate from `threat-model-0010-fact-check-egress-2026-11-24.md` | A rule that already has a dual-gated egress path to one vendor silently growing a second, differently-shaped egress path to a second vendor is exactly the kind of change this project's threat-modelling discipline exists to catch before code lands, not after |
| Y14 | No `Config`/TOML/JSON/user-settings field ever carries `ai_rewrite`, a model id, or the key, extending contract C5 verbatim. A file naming `ai_rewrite` gets the existing generic unknown-option `ConfigError`, with no special casing needed | Matches constraint 3 and the precedent of `use_external_api` (R4 of ADR 0007): the untrusted config tier tunes *what* happens only after egress is already consented to elsewhere, never *whether* it happens |

### Data contracts

```python
# src/docsentinel/rewrite/protocol.py (new package; stdlib + typing only, mirrors fact_check/protocol.py; C9)

RewriteOutcome = Literal["accepted", "rejected_shape", "rejected_hallucination", "skipped_error"]

@dataclass(frozen=True)
class RewriteResult:
    """A backend's attempt to rewrite one statement; never discards the original (Y8)."""

    rewritten_text: str   # == the statement text given, when outcome != "accepted"
    outcome: RewriteOutcome
    backend: str           # the backend name, same shape as fact_check's backend-name grammar


@runtime_checkable
class StatementRewriter(Protocol):
    """Structural contract of a rewrite backend (PEP 544), distinct from FactCheckClient: this
    Protocol returns rewritten text, never a verdict/confidence pair (Y3).

    Construction convention (not expressible in the Protocol, mirrors FactCheckClient): the class
    is constructible as cls(api_key=<str>); the key lives only in a private attribute; __repr__
    never reveals it; the backend never reads os.environ itself.
    """

    name: str
    API_KEY_ENV_VAR: ClassVar[str]   # "ANTHROPIC_API_KEY" for the one backend (Y5)

    def rewrite(self, statement: str, *, context: tuple[str, ...]) -> RewriteResult:
        """Attempt to rephrase ``statement`` as an independent, self-contained statement.

        :param statement: The flagged statement's own text.
        :param context: The immediate predecessor statement(s) it borrows content from, oldest
            first; bounded, never the whole document.
        :raises: nothing but a backend-specific error type the caller contains (mirrors
            FactCheckError's one-exception contract); never raises into the pipeline uncaught.
        """
```

```python
# src/docsentinel/rewrite/anthropic_backend.py (new; stdlib + httpx + rewrite.protocol only; C9)

class AnthropicRewriteClient:
    name: ClassVar[str] = "anthropic"
    API_KEY_ENV_VAR: ClassVar[str] = "ANTHROPIC_API_KEY"            # Y5, deliberate C3 divergence
    BASE_URL: ClassVar[str] = "https://api.anthropic.com"
    MESSAGES_URL: ClassVar[str] = BASE_URL + "/v1/messages"
    MODEL_ID: ClassVar[str] = "claude-haiku-4-5-20251001"            # pinned, dated, not an alias
    ANTHROPIC_VERSION: ClassVar[str] = "2023-06-01"                  # fixed header, pinned
    REQUEST_TIMEOUT_SECONDS: ClassVar[float] = 30.0                  # mirrors Lenz E4 shape
    MAX_RESPONSE_BYTES: ClassVar[int] = 65_536                       # mirrors Lenz E5 shape
    MAX_OUTPUT_TOKENS: ClassVar[int] = 256
    SYSTEM_PROMPT: ClassVar[str] = "..."  # fixed; delimits untrusted data; forbids following
                                            # instructions found inside it (Y10)

    def __init__(self, api_key: str, *, transport: Optional[httpx.BaseTransport] = None): ...
    def rewrite(self, statement: str, *, context: tuple[str, ...]) -> RewriteResult: ...
    def close(self) -> "None": ...
```

```python
# location open per decision Y2/O5: a new rewrite_stage.py, or alongside the gate helper in
# detectors/fact_check.py (if DS302 is in scope), or in engine.py (if extract-facts only)

AI_REWRITE_ENV: Final[str] = "DOCSENTINEL_USE_AI_REWRITE"


def ai_rewrite_requested(ai_rewrite: bool) -> bool:
    """Mirrors external_api_requested(): a real bool, or DOCSENTINEL_USE_AI_REWRITE == "1"."""


@dataclass(frozen=True)
class AiRewriteGate:
    """Mirrors ExternalApiGate's shape exactly (new contract C12)."""

    requested: bool
    key_present: bool
    backend_available: bool = True

    @property
    def open(self) -> bool: ...          # requested and key_present and backend_available
    def reasons(self) -> tuple[str, ...]: ...
    def skip_message(self) -> str: ...


def resolve_ai_rewrite_gate(*, ai_rewrite: bool) -> AiRewriteGate: ...


@dataclass(frozen=True)
class RewrittenStatement:
    """The transparency-preserving record of one rewrite attempt (Y8)."""

    original_text: str
    rewritten_text: str       # == original_text unless outcome == "accepted"
    outcome: RewriteOutcome
    was_flagged: bool         # the Y7 mining-layer signal, kept even when the gate is closed


def apply_ai_rewrite(
    texts: tuple[str, ...],
    flagged: frozenset[int],
    *,
    gate: AiRewriteGate,
    client: Optional[StatementRewriter] = None,
) -> tuple[RewrittenStatement, ...]:
    """Fail-soft pass over selected candidate texts (Y8).

    A closed gate, an unflagged statement, or any per-statement failure or validation rejection
    (Y9) keeps rewritten_text == original_text. Never raises into scan()/extract_facts().
    """
```

### Pipeline

```text
collect_candidates() / trace_candidates()        (C11, unchanged by this story)
  └─ mining.claims.flag_rewrite_candidates()       (Y7; pure, Config-free, no network)
  └─ gate = resolve_ai_rewrite_gate(ai_rewrite=...)  (Y4; ANTHROPIC_API_KEY presence checked here)
       closed -> every candidate keeps original_text; one WARNING (+ pending/doctor line, mirrors C1/C8)
       open   -> load the "anthropic" backend lazily (rewrite/ package; never imported on a closed gate)
                 for each flagged candidate, in order:
                   client.rewrite(statement, context=<its immediate predecessor text(s)>)
                     -> validated (Y9: count/order + token-provenance check)
                        accepted             -> RewrittenStatement(outcome="accepted", rewritten_text=...)
                        rejected / timed out / malformed -> falls back to original_text (Y8), logged
  └─ (Y2 OPEN) consumed at the location the owner ratifies:
       extract-facts  -> ExtractedFact gains original_text/rewritten_text/outcome; --ai-rewrite flag
       DS302 detect() -> the (possibly rewritten) text is what is sent to Lenz; Finding.value keeps
                          BOTH the original and the rewritten text (never only the rewritten one)
```

## Security notes

- **New risk class.** This is the first DocSentinel feature that sends free-form document-derived
  text to a generative model *and* feeds its generated text back into the pipeline, rather than
  receiving a closed-set verdict/confidence pair the way `DS302` receives from Lenz. The future
  threat model (named, not written, here: the next free `threat-model-0010-ai-rewrite-*` file,
  dated when a Security Auditor task actually authors it) must treat this as its own risk class,
  not a copy of the Lenz egress review.
- **Prompt injection (Y10).** The document's own content — necessarily included in the model's
  context — could contain text aimed at the model ("ignore prior instructions..."). The fixed
  `SYSTEM_PROMPT` must give an explicit, structural defense: the statement and its borrowed context
  are always wrapped in clearly delimited data, and the prompt explicitly instructs the model never
  to follow an instruction appearing inside that delimited block, only to rephrase it.
- **Hallucination / overclaim risk (Y9).** The model could introduce a fact not present in the
  original statement or its borrowed predecessor context, which would then be fact-checked by Lenz
  or shown to a human as if it were the document's own claim — a correctness-critical failure mode
  *worse than doing nothing*. Output is validated before acceptance: same count and order as the
  input, and at minimum a lexical/structural provenance check (every content token traceable to the
  source statement or its immediate predecessor(s)); anything failing validation falls back to the
  untouched original per Y8, never partially accepted.
- **Mandatory, deferred-to-implementation transport hardening** (requirements named here, not
  designed here; mirrors the Lenz client's E1–E13 precedent): one fixed URL and pinned model id
  (never derived from claim text, config or a response); no redirects followed; `trust_env=False`
  (no ambient proxy or CA variable); a hard per-request wall-clock deadline enforced from outside
  any blocking read (mirrors E4); a raw-byte response-size cap read with an identity-encoded,
  never-content-decoded stream (mirrors E5); strict UTF-8, no `NaN`/`Infinity` parsing of the
  model's JSON response; no retries; the key validated before any HTTP client object exists, never
  logged, echoed, chained into an exception, or exposed through `__repr__`.
- **Key never logged (constraint 9, blanket rule).** `ANTHROPIC_API_KEY`'s value, length and
  prefix never reach a log record, a `Finding`, a `ScanResult`, `repr()`, or `doctor`/`rules`
  output, exactly like every other secret in this project.
- **Presence of the key is never consent (Y5).** `ANTHROPIC_API_KEY` may already be set in an
  invoker's shell for an unrelated tool. The explicit `--ai-rewrite`/`DOCSENTINEL_USE_AI_REWRITE=1`
  gate (Y4) is mandatory and independent of key presence, exactly as C1 gate 2 does not infer
  consent from `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` being set.
- **No untrusted layer grants this consent or carries this secret (Y14, extends C5).** `ai_rewrite`
  and the model id are never `Config`/TOML/JSON/user-settings fields.
- **Exposure shape differs from Lenz.** Each call sends the full flagged statement *and* its
  predecessor context (more than Lenz's one bounded claim string) and receives back free-form
  generated text (not a closed four-value verdict). Both widen the exposure and trust surface per
  call relative to `DS302`/Lenz; the future threat model must size and bound both.
- **Honesty (constraint 9 / exit-gate-6 precedent).** Wherever this feature is described —
  `doctor`, `rules`, CLI help, `extract-facts --ai-rewrite` output, and every doc file that mentions
  it — it must say plainly: optional, off by default, needs **both** the opt-in and the key to do
  anything, and the rewritten text is an LLM's heuristic paraphrase, not verified fact, mirroring
  how `DS301`/`DS302` already carry "advisory, not ground truth" framing.

## Acceptance criteria

Forward-looking; nothing below is implemented. All depend on open decision O5/Y2 being ratified
first.

- [ ] No `Config`/TOML/JSON/user-settings field can enable this feature or carry the key (mirrors
      the existing `use_external_api` drift test, extended to `ai_rewrite`/`ANTHROPIC_API_KEY`).
- [ ] The opt-in gate (Y4) and the key presence (Y5) are both required and independently testable;
      a sentinel-key test proves the key never reaches any log, `Finding`, `repr`, or `doctor`
      output.
- [ ] `apply_ai_rewrite()` never raises into `scan()`/`extract_facts()`: every per-statement
      failure (timeout, malformed output, failed validation) falls back to the original text, with
      exactly one log line, and `RewrittenStatement.original_text` is retrievable even when
      `outcome != "accepted"`.
- [ ] A rewrite that fails the Y9 provenance check is never accepted, regardless of how fluent it
      reads (a planted test case with an invented number/entity not in the source).
- [ ] A fresh-interpreter test proves a closed gate never imports `docsentinel.rewrite.anthropic_backend`
      or `httpx` on its own account, mirroring the Lenz/`extract-facts` import-isolation tests.
- [ ] `mining.claims.flag_rewrite_candidates()` (or its ratified equivalent) is pure: no `Config`,
      no network, no import outside `mining.*` and the standard library (C9 tripwire extended).
- [ ] Whichever of `extract-facts`/`DS302` is in scope per O5, its existing byte-identical-output
      tests for a run that never passes `--ai-rewrite` still pass unchanged.
- [ ] `doctor`/`rules`/CLI help state the dual requirement and the "heuristic paraphrase, not
      verified fact" framing wherever this feature is named.

## Test plan

Planned, not yet written; file names are tentative.

| Layer | File (planned) | Covers |
|---|---|---|
| Unit | `tests/unit/test_mining_rewrite_signal.py` | `flag_rewrite_candidates()` purity and cases (anaphoric subject, connective, additive adverb, cap-exceeded dependent) |
| Unit | `tests/unit/test_rewrite_protocol.py` | `RewriteResult`/`StatementRewriter` validation, mirrors `test_fact_check_protocol.py` |
| Unit | `tests/unit/test_rewrite_layering.py` | Import tripwire for `docsentinel.rewrite` (mirrors `test_fact_check_layering.py`) |
| Unit | `tests/unit/test_ai_rewrite_gate.py` | `ai_rewrite_requested`/`AiRewriteGate` exact-`"1"` match, reasons order |
| Mock | `tests/mock/test_anthropic_client_transport.py` | Fixed URL/model id, timeout, size cap, no redirects, `trust_env=False` (mirrors Lenz's mock suite shape) |
| Mock | `tests/mock/test_anthropic_client_no_secret_leak.py` | Sentinel-key test across every sink, mirrors `test_lenz_client_no_secret_leak.py` |
| Mock | `tests/mock/test_ai_rewrite_fail_soft.py` | Per-statement timeout/malformed/hallucination-rejected cases each fall back to the original, one log line, no raise |
| Integration | end-to-end against a fake `StatementRewriter` (location depends on O5) | Gate-closed default path is byte-identical to today; gate-open path with a fake backend rewrites only flagged statements and preserves originals in the output |

## Docs to update

Deferred until the open decisions are ratified and code lands (mirrors how Story 05.0's docs were
folded into Story 04.0 Task 04); not edited by this task:

- `/CLAUDE.md` (Project status entry for this story once named/numbered; Commands;
  Architecture; environment variables list — `ANTHROPIC_API_KEY`, `DOCSENTINEL_USE_AI_REWRITE`).
- `/docs/user/tutorial/cli.md` (the `--ai-rewrite` section, wherever it lands).
- `/docs/architecture/README.md` (the new `rewrite/` package, if the diagrams get there).
- `/docs/adr/0008-...md` (Task 01, once ADR 0008 is actually written).
- The future threat model file (Task 02).
- `/docs/user/reference/rules.md`, `/docs/specs/fault-classes.md`, `/docs/specs/finding-types.md`:
  **no changes expected** (Y1/Y13 — no new rule code, `DS302`'s existing `unverified claim` type is
  unchanged even if its sent text can now be a rewrite of the original).

## Diagrams

No diagram changes land with this story: it is specification only, and nothing described above
exists in the codebase yet. Per the project's diagram rule, a diagram documenting a planned design
rather than shipped code is deferred, not drawn early. Once the open decisions are ratified and
code lands, the follow-up (recorded for whichever task implements Task 05/06 above) will likely
touch `component-detectors.puml` and/or `component-overview.puml` (a `rewrite/` package box and,
if O5 selects `DS302`, a second outbound network edge) and possibly a new
`sequence/ai-rewrite-gate` diagram, mirroring the Story 04.0 Task 05 pattern for Stories 01.0/03.0.

**Diagram impact: none (specification only; no code, module or contract has landed yet).**
