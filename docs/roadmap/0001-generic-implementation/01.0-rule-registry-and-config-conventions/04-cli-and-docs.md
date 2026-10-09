# Task 04 - CLI Flags & Documentation Refresh

**Story:** [01.0 - Rule Registry & Config Conventions](README.md)
**Depends on:** [02 - Config conventions](02-config-conventions.md), [03 - Selection resolution](03-selection-resolution.md)

## Purpose

Exposes `select`/`ignore` on the command line, fixes the one call site `Config`'s new fields
break, replaces the `docsentinel.toml` scaffold emitted by `init`, and makes `rules`/`doctor`
report the real (still-empty-of-detectors) registry instead of a hardcoded string. Docs that
describe the old config shape are brought in line. **No new detector lands in this task** -
`rules`/`doctor` will honestly still show zero rules per profile until Story 02.0; this task
only makes that *infrastructure* real.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify - `TEMPLATE`, `init`, `scan` argparse, `rules`, `doctor` |
| `tests/test_pytest_plugin.py` | Check only - confirm it does not construct `Config(...)` positionally; fix if it does |
| `tests/test_scan.py` | Modify - CLI-level tests for `--select`/`--ignore`; `init` test now asserts `doc_sentinel.toml` is created, not `docsentinel.toml` |
| `docs/architecture/README.md` | Modify - document the config discovery order and rule-code namespace from Tasks 02-03 |
| `docs/README.md` | Modify - update the `docs/roadmap/0001-*` rows (see Links) |
| `examples/docs/guide.md` directory (`examples/`) | Modify - add an example `doc_sentinel.toml` next to the existing sample doc, showing `select`/`ignore` in use |

## Symbols / fields

`src/docsentinel/cli.py`:

| Symbol | Change |
|--------|--------|
| `TEMPLATE` | Rewrite to the new top-level-key shape: `profile = "fast"`, `include = [...]`, `exclude = [...]`, `select = []`, `ignore = []` (no `[docsentinel]` header). |
| `init` subcommand | Target file becomes `Path(args.root) / "doc_sentinel.toml"` (was `docsentinel.toml`). Still opens with mode `"x"` (unchanged - never overwrites). |
| `scan` subcommand | Add `scan_parser.add_argument("--select", type=str, default=None)` and the `--ignore` equivalent. Each is a comma-separated string, e.g. `--select DS1,DS203`; parse via `tuple(s.strip() for s in value.split(",") if s.strip())` when not `None`. |
| CLI → `Config` override | Replace the existing `if args.profile: settings = Config(settings.include, settings.exclude, args.profile)` positional construction (broken by Task 02's new fields) with a keyword-argument rebuild that applies `--profile`, `--select`, and `--ignore` **only when each is explicitly given on the CLI** (each replaces, not merges with, the loaded config's value for that field - consistent with how `--profile` already behaves today). |
| `rules` subcommand | Replace the hardcoded `print("Enabled rules: []\n...")` with: for each profile in `("fast", "standard", "deep")`, print the profile name and `rules_for_profile(profile)` (code + title), or `"(none registered)"` if empty. Import `rules_for_profile` from `docsentinel.rules`. |
| `doctor` subcommand | Replace the hardcoded two-line print with: inventory capability (unchanged, "available"), then one line per profile with its registered-rule count via `len(rules_for_profile(profile))`, so `doctor` output changes automatically as later stories register rules - no code change needed in `doctor` itself when Story 02.0 lands. |

## Tests

`tests/test_scan.py` additions/changes:
- `test_init_creates_doc_sentinel_toml` (replaces the old `docsentinel.toml`-named test) -
  asserts the created file's name and that its content round-trips through `load_config`.
- `test_cli_select_flag_parses_comma_separated` - `main(["scan", str(tmp_path), "--select",
  "DS1, DS2"])` (note the space after the comma) results in a `Config.select == ("DS1", "DS2")`
  being used - assert this indirectly via a monkeypatched `scan()` capturing the `config` kwarg,
  or via `rules`/`doctor` output if that is simpler; either is acceptable as long as whitespace
  around commas is proven to be stripped.
- `test_cli_ignore_flag_overrides_config_file` - a `doc_sentinel.toml` sets
  `ignore = ["DS101"]`; `--ignore DS2` on the CLI replaces it entirely (not additive) - assert
  the effective config's `ignore == ("DS2",)`, not `("DS101", "DS2")`.
- `test_rules_command_lists_real_registry` - with no detectors registered (this milestone's
  state at the point this task ships), `docsentinel rules` prints all three profile names each
  followed by "(none registered)" - replaces the old hardcoded-string assertion.
- `test_doctor_command_reports_counts` - `docsentinel doctor` output contains `0` for every
  profile's count.

## Success criteria

- [ ] No remaining reference to `docsentinel.toml` (the old filename) or `[docsentinel]` (the old
      table name) anywhere in `src/`, `tests/`, or `examples/` - grep clean.
- [ ] `docsentinel scan --select DS1 .` and `docsentinel scan --ignore DS1 .` both run without
      error against a tree with no `doc_sentinel.toml` at all (CLI flags work with pure defaults,
      not only on top of an existing config file).
- [ ] `docsentinel rules` and `docsentinel doctor` output is generated from `rules.rules_for_profile`
      calls, not a string literal - confirmed by code review, not just test behavior.

## Constraints

- Full type annotations; `argparse` usage stays consistent with the existing subcommand style
  (no switch to a different CLI framework).
- Keep `main`'s existing exit-code contract (`0`/`1`/`2`) unchanged - this task adds flags and
  changes *output text*, not control flow or exit semantics.
- `docs/architecture/README.md`'s update must **not** claim any `fast` (or other) profile rule
  is implemented yet - word it as "the config/selection machinery exists; Story 02.0 is the
  first rule" to stay honest with `CLAUDE.md`'s standing rule against implying checks exist that
  don't.

## Links

- `docs/roadmap/README.md`'s `## Milestones` table row for `0001` must point at
  `0001-generic-implementation/plan.md` / `status.md` (the folder rename from
  `0001-working-implementation` that motivated this whole milestone) - verify this is already
  correct by the time this task starts; if not, fix it as part of this task's docs pass.
