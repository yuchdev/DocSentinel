# Task 02 — CI, backward compatibility, security and performance

- Run comprehensive old and new fast unit/mock/integration/E2E suites, `uv run pytest -p docsentinel.pytest_plugin`; run standard/deep regression suites under installed extras, respecting existing M3 model skip policy.
- Confirm exact fast/standard/deep profile independence; DS1xx select/ignore prefix; `scan` library/CLI/pytest/plugin; deterministic finding path/line/severity; baseline and GitHub annotations.
- Use adversarial fixtures and runtime path cases: Unicode, 2,000 unmatched delimiters, long lines, symlink escapes, `../` traversal, Windows drives and UNC, CRLF, invalid UTF-8, wrong config table keys, missing navigation index/mapping.
- Compare fast startup/runtime before and after on reproducible corpus; document machine, Python version, corpus size, wall-clock (no universal sub-second guarantee); ensure optional standard/deep imports never appear during fast run.
- Validate `docsentinel.toml` and `[tool.doc_sentinel]` load; `uv build` succeeds; CI never scans intentionally broken test assets.
- Report duplicated diagnostics across DS101/DS113/DS116 transparently; do not silently rewrite old baseline or delete old findings to get green CI.
