# Task 01 - Python Source Discovery Path (`code_discovery.py`)

**Story:** [04.0 - Doc-vs-Code Signature Mismatch Detector](README.md)
**Depends on:** Milestone 0001 Story 01.0 Task 02 (`Config`); Milestone 0002 Story 01.0 (this is a
`standard`-only concern, but `code_discovery.py` itself is stdlib-only and may live outside the lazy
subpackage - see Decision §3)

## Purpose

`DS204` needs a list of Python source files to hand to `docsig`. The existing `discovery.discover`
inventories Markdown into `Document(path, bytes)` and is driven by the Markdown `include`/`exclude`
config - the wrong model and the wrong config axis for Python source. This task adds a separate,
small discovery path for `*.py` files, scoped to configurable source roots, honestly acknowledging
that code discovery and doc discovery are different concerns rather than overloading one.

## Decision this task implements

1. **Separate function, not a reuse of `discover`.** `discover_python(root, config)` walks the
   configured source roots for `*.py` files and returns plain `tuple[Path, ...]` (absolute or
   root-relative `Path`s), **not** `Document` objects. `Document`'s `(path, bytes)` shape is a
   Markdown-inventory contract; `docsig` wants file paths, so returning `Path`s avoids a lossy,
   confusing round-trip through a model that does not fit. This is the "don't force code through the
   Markdown-shaped `Document`" decision stated plainly.
2. **Scoped by `Config.docsig_paths`, default `("src",)`.** `DS204` scans *source*, which lives under
   `src/` in this repo and most Python projects - not the whole tree, and emphatically not the docs
   corpus. `docsig_paths` is a tuple of root-relative directory (or file) paths; each is resolved
   against the scan `root`. A configured path that does not exist is skipped silently (a project
   without a `src/` simply yields no Python files, which is not an error).
3. **`code_discovery.py` is stdlib-only and may live at `src/docsentinel/code_discovery.py`** (next
   to `discovery.py`), not inside the lazy `standard` subpackage - it imports nothing heavy
   (`os`/`pathlib`/`fnmatch` only). Keeping it out of the lazy subpackage means the detector module
   (Task 02, which *does* import `docsig`) stays the only heavy module, and discovery can be tested
   without the `standard` extra at all.
4. **Reuse the directory-pruning discipline of `discovery.discover`.** Prune symlinked directories
   and any directory whose name matches `config.exclude` (so `.git`/`.venv`/`node_modules` and a
   project's own excludes are honored), and skip symlinked files - the same safety posture
   `discovery.py` already enforces for Markdown. Do not re-apply the Markdown `include` patterns
   (those are `*.md`-shaped); the file filter here is simply "name ends in `.py`."

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/code_discovery.py` | Create |
| `src/docsentinel/config.py` | Modify - add `Config.docsig_paths` + validation |
| `tests/test_code_discovery.py` | Create |
| `tests/test_config.py` | Modify - `docsig_paths` validation tests |

## Symbols / fields

`src/docsentinel/code_discovery.py`:

| Symbol | Kind | Signature | Notes |
|--------|------|-----------|-------|
| `discover_python(root: Path, config: Config) -> tuple[Path, ...]` | function | - | For each entry in `config.docsig_paths`, resolve `root / entry`; if it is a file ending `.py`, include it; if a directory, `os.walk` it (topdown), pruning symlinked and `exclude`-matching directories, collecting non-symlink `*.py` files. Returns paths sorted for determinism. Nonexistent entries skipped. |

`src/docsentinel/config.py`:

| Symbol | Change |
|--------|--------|
| `Config.docsig_paths: tuple[str, ...] = ("src",)` | New field. |
| validation | Must be a list of nonempty strings (same rule as `include`/`exclude`); else `ConfigError("docsig_paths must be a list of nonempty paths")`. Accepted in both config-file shapes. |

## Validators (raise `ConfigError`)

- `docsig_paths` present but not a list of nonempty strings → `ConfigError`.
- No existence check at config-parse time (a path that does not exist is a runtime skip, Decision §2,
  not a config error - mirrors how `include` patterns that match nothing are not errors).

## Tests (`tests/test_code_discovery.py`)

- `test_discovers_py_files_under_default_src` - a `tmp_path` with `src/pkg/a.py` and `src/pkg/b.py`
  and `Config()` (default `docsig_paths=("src",)`) returns both, sorted.
- `test_ignores_non_py_files` - a `src/notes.md` and `src/data.json` are not returned.
- `test_respects_exclude_dirs` - a `src/.venv/x.py` under an excluded dir name is not returned.
- `test_skips_symlinked_dirs_and_files` - a symlinked directory and a symlinked `.py` file are both
  skipped (mirror `discovery.discover`'s symlink posture; use `tmp_path` + `os.symlink`, guarded for
  platforms without symlink support).
- `test_nonexistent_configured_path_is_skipped` - `docsig_paths=("does-not-exist",)` returns `()`,
  no exception.
- `test_single_file_path_is_allowed` - `docsig_paths=("src/pkg/a.py",)` returns just that file.
- `test_multiple_roots` - `docsig_paths=("src", "scripts")` collects from both.
- `test_result_is_deterministically_sorted` - files come back in sorted order regardless of
  filesystem walk order.

`tests/test_config.py` additions:
- `test_docsig_paths_default_is_src` - `Config().docsig_paths == ("src",)`.
- `test_docsig_paths_non_list_raises` - `docsig_paths = "src"` (a bare string) → `ConfigError`.
- `test_docsig_paths_empty_string_entry_raises` - `docsig_paths = [""]` → `ConfigError`.

## Success criteria

- [ ] `discover_python` returns `Path`s (not `Document`s) and never routes Python source through the
      Markdown `Document` model - the honest-separation decision, verified by the return type in
      tests.
- [ ] Symlink and `exclude`-dir pruning match `discovery.discover`'s safety posture.
- [ ] `docsig_paths` round-trips through both config shapes and is validated like `include`/`exclude`.

## Constraints

- Full type annotations; no bare `except:`. Walk errors: follow `discovery.discover`'s `onerror`
  convention (propagate) so an unreadable source directory surfaces rather than silently yielding a
  partial file list.
- Stdlib-only - no `docsig` import here (that is Task 02). This keeps discovery testable without the
  `standard` extra.
- Do not merge this with `discovery.discover` into one "polymorphic" discoverer - the two have
  different file filters, different config axes, and different return models; one function each is
  clearer than a mode flag.
</content>
