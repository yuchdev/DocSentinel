# Milestone 0002 - Standard-Profile Detectors - Status

Tracks progress against [plan.md](plan.md). Updated as each story lands.

## Current status

| Story | Name                                                 | Status         | Rules        | Tests |
|-------|------------------------------------------------------|----------------|--------------|-------|
| 01.0  | Optional-Dependency Plumbing & Lazy Standard Loading | ⬜ Not started | -            | -     |
| 02.0  | Text Complexity Detector                             | ⬜ Not started | `DS201`      | -     |
| 03.0  | Corpus Statistics: Duplicate & Low-Information Detectors | ⬜ Not started | `DS202`, `DS203` | - |
| 04.0  | Doc-vs-Code Signature Mismatch Detector              | ⬜ Not started | `DS204`      | -     |
| 05.0  | Standard-Profile CI & Baseline Wiring                | ⬜ Not started | -            | -     |

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started

## Dependency order

```
01.0 (plumbing)  ──►  02.0 (DS201)
                 ├──►  03.0 (DS202, DS203)
                 └──►  04.0 (DS204)
                            └──►  05.0 (CI/baseline wiring, optional)
```

01.0 must land first - every detector registers into the lazily-loaded `standard` subpackage it
creates. 02.0 / 03.0 / 04.0 are independent of one another (different rule codes, no shared state
beyond the subpackage's import list) and can be implemented in any order. 05.0 wires whatever
detectors exist into CI/pre-commit and is best done last (or deferred).
</content>
