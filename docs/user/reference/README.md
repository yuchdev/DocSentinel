# User Reference

This section contains reference documentation for DocSentinel's configurable
features. Each page covers a specific subsystem, its configuration keys, valid
ranges, defaults, and concrete examples.

## Pages

| Page | Purpose |
|------|---------|
| [Statistical Checks](statistical-checks.md) | DS201 text complexity, DS202 duplicate text, and DS203 low-information content: all six configurable keys, valid ranges, defaults, finding formats, and worked examples. |

## Full Configuration Reference

The remaining configuration options — policy options for headings, anchors,
fences, tables, navigation, assets, and naming introduced in Milestone 0005 —
will be documented here when Milestone 0005 completes. Until then, each option
is described in the docstring for the `Config` dataclass in the
`docsentinel` package, and the architecture guide at
[docs/architecture/README.md](../../architecture/README.md) lists which rules
consume each option.
