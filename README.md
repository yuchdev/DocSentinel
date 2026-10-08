# DocSentinel

DocSentinel is a deterministic-first documentation QA project. **M0 is an inventory
scaffold only:** it discovers Markdown files but performs no detection. An empty
findings list does **not** mean documentation has been validated. The `standard`
and `deep` profiles are explicitly pending; no network services or models run.

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra test
uv run docsentinel init
uv run docsentinel scan . --format json
uv run docsentinel rules
uv run docsentinel doctor
```

`init` creates `docsentinel.toml` without overwriting an existing file. Scan
defaults to the current directory, accepts a directory or a single file path, reads its config if present, and accepts
`--config PATH`, `--profile fast|standard|deep`, and `--format text|json`.
Exit status 0 means inventory succeeded (not that detectors passed); 1 is
reserved for findings, and 2 means configuration or scan failed.

```toml
[docsentinel]
profile = "fast"
include = ["*.md", "**/*.md"]
exclude = [".git", ".venv", "node_modules"]
```

Patterns match relative paths; exclude patterns also match directory names.
Symlinked files are not included. Inventory paths and output order are stable.

The library and CLI share the same engine:

```python
from docsentinel import scan

result = scan(".")
print(result.documents, result.enabled_rules, result.pending)
```

For an opt-in pytest fixture, install the test extra and invoke
`uv run pytest -p docsentinel.pytest_plugin`. The `docsentinel_scan` fixture
returns a `ScanResult` for the working directory. It does not assert that
documentation is error-free.

See [architecture](docs/architecture/README.md) and
[contributing](CONTRIBUTING.md) for design boundaries and validation commands.
