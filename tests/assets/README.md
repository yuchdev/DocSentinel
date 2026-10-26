# Test text assets

Input text for detector tests lives here, grouped by the rule a case exercises, so the material for a
given error type can be found from its code alone.

```
tests/assets/
  ds101/                    # one directory per rule code (lowercase)
    dangling_file_link/     # one directory per case: a miniature documentation tree
      README.md
    missing_anchor_other_file/
      README.md
      other.md
  ds204/
    param_does_not_exist/
      src/calc.py           # Python sources for DS204 are assets too
```

## Conventions

- **Directory = rule, case = scenario.** `tests/assets/dsNNN/<case_name>/` holds the files of one scenario,
  laid out exactly as the detector should see them (`scan-root/`, `docs/`, `src/`, ...).
- **Byte-exact.** Cases are copied verbatim into `tmp_path`. Findings assert line numbers and offsets, so do
  not reformat assets. Some cases intentionally have no trailing newline.
- **Deliberately broken.** Assets contain dangling links, stray comments and wrong docstrings on purpose. They
  are excluded from the repository self-scan (`docsentinel.toml`), ruff (`ruff.toml`) and flakeforge
  (`pyproject.toml`). Do not "fix" them.
- **Compose, don't copy.** A scenario that spans rules (a fast-profile tree, a standard-profile corpus) loads
  several single-rule cases into one `tmp_path`. Give files distinct names so cases do not overwrite each other.
- **Shared substrate.** The corpus-model cases (`ds202/corpus_*`) back both DS202 and DS203, which share one
  fitted TF-IDF model.
- **Byte-level Unicode cases.** `ds114/unicode_normalized_ids/` deliberately stores two NFC-equivalent ids as
  genuinely different code point sequences: `a.md` uses the precomposed `U+00E9` (`café-guide`) and `b.md` uses
  the decomposed `e` + combining `U+0301` (`cafe<U+0301>-guide`). They differ byte-for-byte but normalize to the
  same NFC string, so DS114 reports the collision. Keep both encodings exactly as committed.
- **Generated-at-runtime input stays in the test.** Pathological inputs such as 2,000 unclosed `<!--`
  openers, invalid UTF-8 bytes, symlinks, and TOML configuration are built in the test body, not stored here.

## Loading a case

```python
from collections.abc import Callable

from tests.asset_helpers import AssetCase


def test_dangling_link(asset_case: Callable[[str, str], AssetCase]):
    case = asset_case("ds101", "dangling_file_link")          # copies into tmp_path
    findings = links.detect(case.root, case.documents("README.md"))
```

`AssetCase` offers `root`, `path(rel)`, `document(rel)`, `documents(*rels)`, `read_text(rel)` and `child(dir)`
for cases that nest their own scan root.

## Test taxonomy

| Type | Location | Loads assets? | Scope |
|---|---|---|---|
| Unit | `tests/unit/` | No | One function or method, with tiny inline strings |
| Mock | `tests/mock/` | No | A unit with an external resource (imports, vectorizer, file reads) replaced |
| Integration | `tests/integration/` | **Yes** | A detector, scan, or CLI run over asset documents |

Any test file that loads assets from `dsNNN` carries those IDs as a suffix, for example
`test_detectors_links_ds101.py` or `test_fast_profile_end_to_end_ds101_ds102_ds103.py`.
