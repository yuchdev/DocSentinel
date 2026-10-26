# Task 03 — Documentation, security and milestone closure

## Documentation

Update `README.md`, `docs/architecture/README.md`, `docs/roadmap/README.md`, `docs/user/tutorial/cli.md`, `docs/user/tutorial/library.md`, `tests/assets/README.md`, `examples/docsentinel.toml`, and rule catalog/help output as required. Explain each new rule's scope, supported constructs, limitations, severity, configuration, and the explicit/cumulative profile distinction (profiles are *exact*).

## Security audit

Use the existing repo `security-auditor` conventions to review Markdown and code snippet parsing, path traversal, symlinks, source execution/import avoidance, semantic candidate misrepresentation, redaction in findings, optional model gating, and CI PR supply-chain risks. No code examples are executed. No git invocation or remote fetch is hidden in DS316.

## Performance

Measure fast on small + typical repo, standard on representative 100/500-document corpora, deep DS302/DS316 on a moderate graph. Do not hard-code an unverified sub-second guarantee on arbitrarily large repos. Bound pairwise comparisons with documented safeguards and avoid quadratic memory explosions in DS207/208/302.

## Milestone handoff

1. Link story READMEs and task specs via repo-root-absolute links per roadmap convention (update `plan.md` links appropriately when installed in repo).
2. Fill `status.md` story-by-story with test counts, fixture counts, benchmark notes, known limitations and PR links.
3. Assert fixture matrix totals, verify each test file name carries DS ID, run links checker and full suite.
4. Do not regenerate baselines reflexively. Review each new finding on self-scan and either fix docs, explicitly document exemption or create a new baseline entry only under approved baseline policy.
5. Deliver readable PR summary describing which rules are verified versus heuristic and which document/source constructs remain unsupported.

## Release gate

- All 12 rules implemented with mandatory Markdown fixtures; zero unchecked scenarios.
- Three legacy milestones remain green; profiles and API contracts backward compatible.
- No optional heavy import on fast path; no user-code execution; no hidden background work.
- CI, build and documentation checks green; milestone index/status updated.
