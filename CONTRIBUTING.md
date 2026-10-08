# Contributing

Install Python 3.11+ and uv, then run:

```sh
uv sync --extra test
uv run pytest -p docsentinel.pytest_plugin
uv build
```

M0 only inventories Markdown; do not describe the absence of findings as a
successful content audit. Keep new detectors explicit and deterministic, and
add tests for their results before enabling them in the registry.
