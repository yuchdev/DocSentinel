# Contributing

Install Python 3.12+ and uv, then run:

```sh
uv sync --extra test
uv run pytest -p docsentinel.pytest_plugin
uv build
```

Direct runs such as `uv run pytest -q`, the Stop hook, and CI share the session
setup in `tests/conftest.py`. It downloads NLTK's `cmudict` corpus if missing:
the locked textstat English syllable counter needs this data, which `uv sync`
does not install. The first test run needs network access; later runs reuse
NLTK's data cache. For offline runs, provision it beforehand with
`uv run python -c 'import nltk; nltk.download("cmudict", raise_on_error=True)'`.
For a custom data directory, set `NLTK_DATA` and pass the same directory as
`download_dir` to `nltk.download`. Download or lookup failures fail test setup;
no tests are skipped.

M0 only inventories Markdown; do not describe the absence of findings as a
successful content audit. Keep new detectors explicit and deterministic, and
add tests for their results before enabling them in the registry.
