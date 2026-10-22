# Frozen reference implementations

This directory holds verbatim copies of detector source files as they were **before** a
deliberate behaviour-preserving security change. Tests load them as an oracle and compare
their output with the live detectors, so that a change which is supposed to alter only
specific categories cannot silently alter anything else.

## Files

| File | Frozen from | Used by |
|------|-------------|---------|
| `ds101_links_pre_story_11.py.txt` | the DS101 link detector before the Story 11.0 existence-oracle fix | `tests/integration/test_oracle_parity_ds101_ds103.py` |
| `ds103_paths_pre_story_11.py.txt` | the DS103 path detector before the Story 11.0 existence-oracle fix | `tests/integration/test_oracle_parity_ds101_ds103.py` |

## Rules for maintainers

Do not edit these files and do not refresh them from the current detectors: a refreshed copy
would make the parity test compare the code with itself and pass without checking anything.
They carry the `.py.txt` suffix so formatters and linters leave them byte-for-byte as they
were. If a later story intentionally changes DS101 or DS103 behaviour, update the expected
difference set in the parity test instead of the reference files.
