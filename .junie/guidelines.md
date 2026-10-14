# DocSentinel Junie guidelines

## Project invariants

- DocSentinel is deterministic-first documentation QA. An empty findings list must never be described
  as proof that unimplemented detection ran.
- Preserve one orchestration path through `engine.scan`, deterministic sorted discovery, excluded
  directory pruning, symlink safety, frozen public result contracts, the analyzer registry, profile
  honesty, and CLI exit codes 0 (success), 1 (findings), and 2 (configuration/scan failure).
- Never send repository document content to a network or model unless a future deep integration is
  explicitly enabled. Do not log secrets, PII, raw document content, or sensitive payloads.
- Read `docs/dev/python_coding_standard.md`, then its referenced language/style rules, before Python
  changes. Project overrides win, including `Optional[T]` rather than `T | None` where mandated.
- Keep changes task-scoped. Never weaken tests or diagnostics to obtain a passing result, and never
  commit or push unless the user explicitly requests it.

## Specialist routing

Use the custom agent whose description owns the work. Non-trivial cross-specialist work goes through
`agent-orchestrator`; design through `app-architect`; implementation through `python-expert`; tests
through `testing-expert`; sensitive changes through `security-auditor`; and final correctness review
through `feature-reviewer`. Use `docs-writer` for new docs and `docs-updater` for existing docs.

## Lifecycle behavior retained from the Claude kit

Junie supports hooks only through user-level `~/.junie/config.json` or a file explicitly supplied via
`--config-location`; a repository `.junie/config.json` is not automatically loaded. Therefore this
repository does not fabricate executable hook wiring. Apply these rules during normal work:

### Session start (`session_start.py` intent)

When relevant to a multi-step task, inspect the current branch, recent commits, and urgent issue
context before planning. Treat remote issue lookup as best-effort and never imply unauthenticated
queries succeeded.

### Before tools and edits (`guard_bash.py`, `secret_scan.py` intent)

- Refuse recursive forced deletion, database drops/truncation, forced pushes, hard resets, raw-disk
  writes, filesystem formatting, and other destructive commands. Production-targeting actions require
  explicit human confirmation; an environment variable alone is not a substitute for current user
  authorization.
- Before writing requested or generated text, check it for likely credential shapes. Do not expose a
  detected value in output. Remove and rotate real credentials and use environment-variable or
  secret-manager references. Run the `secret-scan` skill for repository sweeps.

### After edits (`post_edit_format.py`, `style_fixes.py`, `dep_audit.py`,
`doc_link_check.py` intent)

- After Python edits, run scoped Ruff formatting/checks when configured and enforce repository typing
  conventions. Review automatic fixes; do not silently reformat unrelated files.
- After dependency-manifest edits, run the `dep-audit` skill or explicitly report why it could not run.
- After Markdown edits, check the edited file's relative links and anchors. Before completion, run the
  `link-check` skill over the affected documentation and `doc-xref` after moves or heading changes.

### External actions and completion (`github_audit.py`, `run_tests.py` intent)

- Summarize GitHub or other remote mutations by repository, issue/PR, branch/ref, and action without
  logging sensitive arguments. Do not claim a durable automatic audit log exists.
- Before ending code work, run meaningful targeted tests and then the repository's applicable Ruff and
  pytest gates. Analyze and fix failures; do not bypass them. Text-only configuration ports such as
  this kit do not require the application test suite.

The Claude `_common.py` helper only implemented Claude's JSON hook protocol, logging, path extraction,
and link helpers; it has no standalone Junie lifecycle role. Its safety, redaction, and link-resolution
semantics are incorporated above and in the corresponding skills.