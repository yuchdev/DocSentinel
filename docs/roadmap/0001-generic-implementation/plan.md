# Milestone 0001 - Generic Implementation

**Package:** `docsentinel` | **Module root:** `src/docsentinel/` | **Config namespace:** `doc_sentinel`

> Naming note: the distributed package, CLI, and import path are all `docsentinel` (one word,
> no underscore) - that is what `pyproject.toml`, `src/`, and every test already use, and
> changing it is out of scope here. The **configuration namespace** - the `pyproject.toml`
> table and the standalone config filename - is deliberately `doc_sentinel` (underscored) per
> `CLAUDE.md`'s explicit convention. These are two different names for two different things;
> do not "fix" one to match the other.

## Goal

Take DocSentinel from **M0 (inventory scaffold, zero detectors)** to a **first limited but real
run**: a working rule-selection convention every Pythonic static analyzer has (`include`/
`exclude` for files, `select`/`ignore` for rule codes), and the first batch of genuinely
deterministic detectors wired into `ANALYZERS` so `docsentinel scan` can actually fail a build
for a real reason, not just list files.

Scope is deliberately narrow - this milestone only promotes the **`fast` profile** (structural /
reference checks, per `docs/architecture/README.md`) from aspirational prose to working code.
`standard` (corpus/statistical: duplication, low-information content, complexity) and `deep`
(explicitly-enabled semantic integrations: fact contradictions, doc-vs-code drift, the periodic
background reviewer) are real, already-scoped future milestones - see
[Beyond this milestone](#beyond-this-milestone) - not attempted here. Shipping a small, honest
`fast` profile beats a half-working everything.

## Stories

| Story | Name                                     | Category | Output                                                                         |
|-------|-------------------------------------------|----------|---------------------------------------------------------------------------------|
| 01.0  | Rule Registry & Config Conventions        | feature  | `select`/`ignore`/`include`/`exclude`, `doc_sentinel` config namespace, rule codes |
| 02.0  | Fast-Profile Structural Detectors         | feature  | First real `ANALYZERS` entries: dangling links/anchors, stray HTML comments, uncovered entity mentions |
| 03.0  | CLI & Reporting Completion                | feature  | `scan --select/--ignore`, real `rules`/`doctor` output, versioned JSON report schema |
| 04.0  | Pre-commit, CI & Self-Scan Baseline       | chore    | `.pre-commit-hooks.yaml` fast hook enforces real findings; CI self-scan baseline captured |

## Cross-cutting guidelines (every story)

- **Determinism first.** Every detector added in this milestone must be explainable from its
  inputs alone - no network, no model calls, no wall-clock/locale-dependent output. This is the
  whole premise of `CLAUDE.md`'s "deterministic-first" framing; `standard`/`deep` get their own
  milestones precisely because they relax this one dimension at a time.
- **Tests before registration.** Per `CLAUDE.md` Conventions: a new detector's result tests land
  *before* it is added to `engine.ANALYZERS` - never the other way around.
- **No silent behavior change to the M0 contract.** `ScanResult.notice` must stop claiming
  "Detection rules are not implemented in M0" once real rules exist for the active profile; a
  `standard`/`deep` run with nothing implemented yet must keep saying so via `pending`, per
  `CLAUDE.md`'s "must not describe an empty findings list as a validated audit."
- **Full type annotations, `Optional[T]` style, no bare `except:`** - see
  [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md).

## Rule code namespace

Mirrors `flakeforge`'s own code-per-rule convention (see the Canonix Engine precedent this
project's scaffold is drawing on) and maps 1:1 onto the three profiles already named in
`docs/architecture/README.md`:

| Prefix  | Profile    | Category                                             | First codes this milestone               |
|---------|------------|-------------------------------------------------------|--------------------------------------------|
| `DS1xx` | `fast`     | Structural / reference (file- and link-level)         | `DS101` dangling link/anchor, `DS102` stray HTML comment, `DS103` uncovered entity mention |
| `DS2xx` | `standard` | Corpus / mechanical (statistics over the whole corpus) | _(reserved - milestone 0002)_             |
| `DS3xx` | `deep`     | Semantic (explicitly enabled, may call out to an agent) | _(reserved - milestone 0003)_             |

A rule's code is permanent once shipped (renumbering breaks someone's `ignore = ["DS101"]`); an
unused gap is cheaper than a reused number.

## Beyond this milestone

Not scoped here, listed so `select`/`ignore` and the `DS2xx`/`DS3xx` ranges have somewhere to
grow into without a later renumbering:

- **Milestone 0002 (`standard` profile)** - corpus-wide statistical detectors: duplicated
  text/facts (TF-IDF cosine), low-information content, text-complexity scoring (readability
  grade level). Non-LLM, but corpus-wide and slower than a single-file check, hence a separate
  profile and a separate milestone.
- **Milestone 0003 (`deep` profile + periodic review)** - explicitly-opt-in semantic checks (fact
  contradictions, doc-vs-code behavioral drift) and a periodic background-reviewer agent/loop,
  the two requirements that cannot be done deterministically - see
  `docs/security/README.md`'s own M0 threat model for why `deep` must stay opt-in (it is the
  point at which document contents could leave the local process).

## Links

- **Architecture boundaries:** [`docs/architecture/README.md`](/docs/architecture/README.md)
- **Config ADR (illustrative only, not followed):** [`docs/adr/0001-config-loading-via-layered-settings.md`](/docs/adr/0001-config-loading-via-layered-settings.md)
- **Coding standard:** [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md)
