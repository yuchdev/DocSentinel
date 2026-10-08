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
| `docs/roadmap/README.md` | Roadmap conventions: the Milestone → Story → Task hierarchy. |
| `docs/roadmap/0001-working-implementation/plan.md` | Example milestone plan from the kit scaffolding (targets a `doc_sentinel` package with a hello-world endpoint, which does not match DocSentinel's CLI). |
| `docs/roadmap/0001-working-implementation/status.md` | Progress tracker for that example milestone. |
| `docs/roadmap/0001-working-implementation/01.0-hello-world-endpoint/README.md` | Example story README. |
| `docs/roadmap/0001-working-implementation/01.0-hello-world-endpoint/01-config-model.md` | Example task spec: config model. |
| `docs/roadmap/0001-working-implementation/01.0-hello-world-endpoint/02-health-endpoint.md` | Example task spec: health endpoint. |
| `docs/roadmap/0001-working-implementation/01.0-hello-world-endpoint/03-tests.md` | Example task spec: tests. |
| `docs/reviews/README.md` | Where `background-reviewer` writes dependency, secret, performance and license reports. |
| `docs/reviews/example-report.md` | Example review report showing the expected format. |
| `docs/security/README.md` | Threat models and security reviews owned by `security-auditor`, including the initial DocSentinel threat-model draft. |
| `docs/test/code_test_coverage.md` | Coverage requirements checklist and workflow. |
