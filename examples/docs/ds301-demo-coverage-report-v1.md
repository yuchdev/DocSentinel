# Unit and Integration Testing

This guide describes how the test suite is organised and how to run it locally before you open a
pull request. It is written for contributors who are adding a detector or changing the engine, not
for release managers.

## Running the suite

The full suite runs with `uv run pytest -p docsentinel.pytest_plugin` and takes several minutes,
mostly because the complexity tests measure CPU time over doubling input sizes. Run the unit
directory alone while you iterate, then the whole suite once before you push.

## Layout

Unit tests live in `tests/unit/` and use tiny inline strings. Integration tests load fixtures from
`tests/assets/`, one directory per rule code and case. Mock tests replace an external resource,
usually the filesystem or a network client.

## Where we stand

Coverage is measured on demand rather than on every run, because the coverage plugin is not a
project dependency. DocSentinel scored 85 on the test coverage benchmark this quarter, which sits
above the configured floor but below where the deep-profile modules ought to be. The weakest paths
are the ones that only execute when an optional extra is installed.

## Adding tests for a new rule

A new rule needs unit tests with inline strings, committed fixture directories, and an integration
file carrying an explicit expectation table. Never derive the expected findings from detector
output: transcribe them from the fixture matrix instead, so a regression in the detector cannot
quietly rewrite the test.
