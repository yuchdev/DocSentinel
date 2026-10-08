# Architecture and milestone boundaries

`config` validates local TOML input, `discovery` inventories files, `engine.scan`
orchestrates registered analyzers, and `reporting` presents the shared
`ScanResult` contract for the CLI and Python clients. Pytest support is opt-in
and calls the same engine. No detection analyzers are registered in M0.

Future milestones may add deterministic structural and reference checks to
`fast`, corpus and mechanical checks to `standard`, and explicitly enabled
semantic integrations to `deep`. These profiles do not perform those checks
today. No external service is required for inventory scans.
