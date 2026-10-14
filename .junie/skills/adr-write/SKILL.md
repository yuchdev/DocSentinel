---
name: adr-write
description: Scaffold a proposed MADR architecture decision in docs/adr/ when a design decision must be recorded before implementation.
---

# Write an ADR

Use the requested title as the decision title.

1. Inspect `docs/adr/` and choose one above the highest zero-padded `NNNN-` prefix, starting at
   `0001`. Create `docs/adr/NNNN-<kebab-title>.md`.
2. Read `docs/adr/template.md` and the newest accepted ADR, if present. The repository template is
   authoritative; do not substitute a generic template.
3. Use the recent ten git commits and, when available, relevant open issues only to seed the problem
   context. Never invent a decision from this metadata.
4. Keep status `Proposed`. Fill context, one clear decision, at least one serious alternative and its
   rejection reason, positive and negative consequences, validation/rollout, and links to the driving
   task or issue. A human or architect must approve acceptance.
5. Add the ADR to `docs/README.md` and run the `link-check` skill on the new file.

Return the created path and one-line summary. The `app-architect` owns decision content; this skill
owns consistent scaffolding and indexing.