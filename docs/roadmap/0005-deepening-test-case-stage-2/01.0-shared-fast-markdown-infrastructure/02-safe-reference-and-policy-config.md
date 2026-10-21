# Task 02 — safe local references, config plumbing and optional policy gates

1. Reuse M4's Analyzer context if implemented. Otherwise choose the M4-compatible third optional Config parameter while maintaining `detect(root, documents)` direct calls for shipped detectors. Avoid reflection-based dispatch.
2. Build or reuse safe resolver for root-contained `../`, percent-encoded local paths, rooted `/docs` paths, Windows/UNC, symlinks, URL schemes, templates; return tagged results and **never** dereference unsafe paths.
3. Add all Story 02–14 named config fields into typed `Config`, strict known-options validation, TOML standalone and pyproject loaders, CLI `rules`/`doctor`, sample config. Handle inactive policy-dependent rules transparently, not by silently reporting zero findings.
4. Validate input (positive ints, enums, arrays of nonempty path strings, maps under scan root), enforce no network, and ensure `Config` object passed by library wins over file defaults.
5. Prove shared resolver compatibility with DS101, DS103, M4 DS107/DS113 if already implemented; add explicit non-overlap regression tests.
6. Set owners of scanner/resolver/config commits to avoid concurrent story patch conflicts.

**Acceptance:** no default behavior regression, no arbitrary file reads, optional rules state accurately reflected in scan output, strict unknown-config errors still work.
