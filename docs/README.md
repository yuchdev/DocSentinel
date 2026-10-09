# Documentation Registry

| Path | Purpose |
|------|---------|
| `docs/README.md` | This registry of documents under `docs/`. |
| `docs/architecture/README.md` | DocSentinel's own design boundaries: the config → discovery → `engine.scan` → reporting flow, and which checks the `fast`/`standard`/`deep` profiles may add in later milestones (none exist in M0). |
| `docs/adr/README.md` | ADR conventions: MADR template, `000N-slug.md` naming, Mermaid assets. |
| `docs/adr/template.md` | MADR skeleton used by `app-architect` and `/adr-write`. |
| `docs/adr/0001-config-loading-via-layered-settings.md` | Illustrative example ADR (layered pydantic-settings). Not a real DocSentinel decision; DocSentinel loads config with `tomllib` in `config.py`. |
| `docs/adr/assets/0001-config-source-precedence.mmd` | Mermaid diagram referenced by the example ADR 0001. |
| `docs/agent/agents.md` | Reference table of the kit's Claude Code agents, their models and roles. |
| `docs/agent/skills.md` | Reference table of the kit's skills and how to invoke them. |
| `docs/agent/hooks.md` | Reference table of the kit's hooks and their triggers. |
| `docs/agent/tutorial.md` | Tutorial for working with the agentic kit. |
| `docs/dev/python_coding_standard.md` | Entry point to the Python coding standard, with project-specific overrides that win on conflict. |
| `docs/dev/python_language_rules.md` | Base Python language dos and don'ts. |
| `docs/dev/python_style_rules.md` | Base Python style rules (formatting, comments, TODO format, typing). |
| `docs/roadmap/README.md` | Roadmap conventions and the milestone index: the Milestone → Story → Task hierarchy. Start here to navigate into any milestone's `plan.md`, then its story `README.md`s, then task specs - this registry does not re-list every roadmap leaf file. |
| `docs/roadmap/0001-generic-implementation/plan.md` | Milestone 0001: rule registry, `pyproject.toml`/`doc_sentinel.toml` config conventions with `select`/`ignore`, and the first `fast`-profile detectors (`DS101`-`DS103`) - the "first limited run." 4 stories, fully task-specced. |
| `docs/roadmap/0002-standard-profile-detectors/plan.md` | Milestone 0002: `standard`-profile detectors - corpus duplication, low-information content, text complexity, and a `docsig`-based doc-vs-code signature check (`DS201`-`DS204`). 5 stories, fully task-specced. |
| `docs/roadmap/0003-deep-profile-and-periodic-review/plan.md` | Milestone 0003: the `deep`-profile fact-contradiction candidate detector (`DS301`), its opt-in gating, and the periodic `docs-reviewer` agent/loop. 4 stories, fully task-specced. |
| `docs/reviews/README.md` | Where `background-reviewer` writes dependency, secret, performance and license reports. |
| `docs/reviews/example-report.md` | Example review report showing the expected format. |
| `docs/security/README.md` | Threat models and security reviews owned by `security-auditor`, including the initial DocSentinel threat-model draft. |
| `docs/test/code_test_coverage.md` | Coverage requirements checklist and workflow. |
