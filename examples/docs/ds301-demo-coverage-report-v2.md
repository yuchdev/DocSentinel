# Test Coverage Report — Q1 2026

Prepared for the quarterly engineering review. This report summarises the health of the automated
checks over the quarter and records the follow-up items agreed with the maintainers.

## Summary

The suite ended the quarter green on every supported interpreter, with two deliberate skips and no
flakes recorded in the nightly runs. This quarter DocSentinel scored 90 on the test coverage, and
the reviewers accepted that figure as the baseline for the next period.

## Observations by area

The detector package stays the best covered, because every rule ships with committed fixtures
alongside it. Reporting templates and the telemetry context are exercised indirectly, through the
end-to-end runs rather than through tests of their own. The optional-dependency modules continue
to account for most of the uncovered lines, which matches what contributors report when they work
on the deep profile.

## Follow-up

1. Give the deep-profile modules fixtures of their own before raising the floor again.
2. Keep the lint gate free of a baseline, so a new violation surfaces on the first run.
3. Re-measure once the next milestone lands, and compare against this report rather than against
   the developer guide, which quotes an older figure.
