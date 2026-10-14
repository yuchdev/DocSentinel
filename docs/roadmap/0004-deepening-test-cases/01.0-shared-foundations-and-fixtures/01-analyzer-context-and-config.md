# Task 01 — Analyzer context and configuration dispatch

## Current master behavior

`engine.scan` calls standard analyzers with `(root, documents, settings)` and fast/deep analyzers with `(root, documents)`. `Config` already has strict TOML unknown-key validation, and public `scan(root, *, config=...)` supports injected configs. Adding a config-sensitive fast or deep detector without reconciling this would produce silently inconsistent results.

## Implementation

1. Choose one stable internal `Analyzer` protocol and update engine invocation. Preferred: optional third `Config` arg on all legacy analyzers, defaulting to `None` for existing direct-call API; adapt DS101–DS301 accordingly. Alternatively use an immutable `ScanContext` with explicit legacy adapters. Avoid runtime signature reflection on every analyzer.
2. Add optional `changed_paths` context to `scan` without breaking caller signatures. The CLI will supply repeated `--changed-file PATH`, and pytest plugin/library callers may pass a tuple; default is *not supplied*, distinguishable from an explicitly supplied empty change set.
3. Define safe in-process cache scopes, one per scan and root, so graph/symbol indexes may be shared across DS107/DS216/DS316. Never use a cache key consisting only of document filenames.
4. Keep findings/report schema backward-compatible. For rule-specific unsupported/partial execution, prefer additive optional execution status metadata rather than overloading an empty findings tuple.
5. Add both standalone and `[tool.doc_sentinel]` TOML tests for every new option. Current config file is `doc_sentinel.toml` (underscore).

## Exact acceptance

- [ ] Existing direct `links.detect(root,docs)`, `contradictions.detect(root,docs)` and `signatures.detect(root,docs,config)` usages still work.
- [ ] Injected `Config` reaches new fast/deep analyzers without reading stale config on disk.
- [ ] Profile exactness, selector precedence, baseline, sorted outputs and public CLI remain unchanged.
- [ ] `scan(changed_paths=...)` preserves specified file paths safely without I/O to arbitrary outside targets.
- [ ] Incomplete analysis never masquerades as 'N rules evaluated successfully'.
