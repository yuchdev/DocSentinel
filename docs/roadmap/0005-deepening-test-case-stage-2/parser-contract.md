# Stage 2 — proposed scanner and rule data contracts

These are **targets for implementation**, not claims about existing APIs. An agent must first reconcile with M4's actual committed APIs.

```python
@dataclass(frozen=True)
class MarkdownSpan:
    path: str
    start_line: int     # one-based
    end_line: int
    start_offset: int   # half-open source byte-or-character offset, choose and document
    end_offset: int

@dataclass(frozen=True)
class MarkdownBlockIndex:
    spans: tuple[MarkdownSpan, ...]
    headings: tuple[HeadingToken, ...]
    fences: tuple[FenceToken, ...]
    link_references: tuple[ReferenceToken, ...]
    local_targets: tuple[LocalTargetToken, ...]
```

- Indexing must be **per original source text**, never after deleting fences without preserving source offsets.
- A `FenceToken` includes opener line, closer line (optional), delimiter character/length, info string and body-is-nonempty predicate.
- A `HeadingToken` carries generated slug, explicit anchors, level and line, and the same duplicate-suffix semantics as DS101.
- `LocalTargetToken` holds raw target, link category (`nav`, `image`, `ordinary`, `code_span`), path component, URL fragment and decoded safe path (if valid).
- `ReferenceToken` preserves normalized label and usage/definition line. It is acceptable for specific detectors to build indexed views from these immutable source tokens.

## Path resolver (security-critical)

Use a small `resolve_local_reference(root, document_path, raw_target)` with a tagged result:

```text
RESOLVED: target exists inside root (or safe path inside root that may not exist)
EXTERNAL: URL scheme/data URI/template
OUTSIDE_ROOT: lexical or symlink escape detected
UNSUPPORTED: cannot safely interpret token in configured dialect
```

A resolver must not open a target until it is confirmed to remain inside root. A *missing* path is not automatically an escape and belongs to DS101/DS113. A **missing navigation requirement** belongs to DS112. A path escape always belongs to DS116, independently of whether the file exists outside the root.

## No invented universal parser

M5 does **not** authorize implementing all CommonMark, full HTML5 parsing or a broad plugin parser framework. The purpose is consistent shared tokens for 13 specific rules. For cases outside the supported syntax, avoid confident false diagnostics and add a precise limitation note. Compatible refactoring of the previous DS101/DS103 regex implementations is allowed only with a documented regression test and no new findings accidentally suppressed by baseline changes.
