# Diagrams

Diagrams of the as-built DocSentinel package (`src/docsentinel/`), grouped by
diagram kind, one subdirectory per diagram. Each `.puml` source sits beside its
rendered `.svg` and `.png`. Re-render from the repository root with
`python .claude/skills/plantuml/scripts/convert_puml.py <path>.puml --format svg`
(repeat with `--format png`).

## Component diagrams (`component/`)

### Overview

![DocSentinel component overview: consumers, core, detectors, reporting, inputs and extras](component/overview/component-overview.svg)

### Detectors by profile

![Detectors grouped by profile with the shared Markdown scanner, lazy standard loader and deep gate](component/detectors/component-detectors.svg)

### Reporting and telemetry

![Reporting shim and the telemetry package: loader, model, engine, extensions and templates](component/reporting/component-reporting.svg)

## Sequence diagrams (`sequence/`)

### Layered configuration load

![Layered configuration load: user settings JSON gate, project layer, CLI flags, single validation and the injected Config bypass](sequence/config-layered-load/config-layered-load.svg)

### Invoker include and exclude selection

![Invoker include and exclude selection: CLI early validation, engine normalisation and merge, discovery, and the empty-selection ConfigError](sequence/scan-selection/scan-selection.svg)

### DS302 consent gate and fail-soft paths

![DS302 consent gate: engine gate resolution, closed-gate skip, backend load, per-claim failures and the time budget](sequence/ds302-fact-check-gate/ds302-fact-check-gate.svg)

### extract-facts offline preview

![extract-facts: CLI, shared inventory, the one candidate source and render_facts, with no network edge](sequence/extract-facts/extract-facts.svg)

## Layout

```text
docs/diagrams/
├── README.md
├── component/
│   ├── overview/    component-overview.{puml,svg,png}
│   ├── detectors/   component-detectors.{puml,svg,png}
│   └── reporting/   component-reporting.{puml,svg,png}
└── sequence/
    ├── config-layered-load/   config-layered-load.{puml,svg,png}
    ├── ds302-fact-check-gate/ ds302-fact-check-gate.{puml,svg,png}
    ├── extract-facts/         extract-facts.{puml,svg,png}
    └── scan-selection/        scan-selection.{puml,svg,png}
```

New diagram kinds (state, deployment, …) get a sibling directory
next to `component/`, with one subdirectory per diagram.
