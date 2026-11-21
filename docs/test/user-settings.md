# Manual test checklist: user settings and JSON configuration

This checklist exercises the layered configuration of Milestone 0009 Story 03.0 by hand, on a
POSIX machine, without touching your real settings file. The automated tests cover the same rules;
run this list after a change to `config.py`, the `init --user` command or the CI workflow, and
before a release.

Every step points `DOCSENTINEL_SETTINGS` at a scratch directory, so the default file under your
home is never read, created or changed. Run the commands from a checkout with `uv sync` done.

## Setup

```sh
export SCRATCH="$(mktemp -d)"
export DOCSENTINEL_SETTINGS="$SCRATCH/settings.json"
mkdir "$SCRATCH/proj" && printf '# Title\n\nText.\n' > "$SCRATCH/proj/a.md"
```

## Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | `uv run docsentinel scan "$SCRATCH/proj"` before the file exists | Exit `2`: a file named by `DOCSENTINEL_SETTINGS` must exist (only a missing file at the default location is skipped) |
| 2 | `uv run docsentinel init --user --yes` | Prints `Created ...` with the path in tilde form when under your home; the file has mode `0600` (`ls -l`) |
| 3 | Run step 2 again | Exit `2`, `already exists; not overwriting it`, file unchanged |
| 4 | `printf '{"ignore": ["DS1"]}' > "$SCRATCH/settings.json"; chmod 600 "$SCRATCH/settings.json"` then `uv run docsentinel doctor` | `user settings: ... (loaded, 1 option)`; no value is printed |
| 5 | `printf '{"baseline": "x.json"}' > "$SCRATCH/settings.json"` then run a scan | Exit `2`; the message lists the refused key `baseline` |
| 6 | Put `{"link_root": ".", "include": []}` in the file | Exit `2`; both keys listed |
| 7 | `chmod 666 "$SCRATCH/settings.json"` with valid content, then scan | Exit `2`; message contains `writable by group or others (run chmod go-w on it)`; `chmod go-w` fixes it |
| 8 | `chmod 777 "$SCRATCH"` with a valid file | Exit `2`; message contains `its directory is owned by another user or writable by others`; `chmod 700` fixes it (a sticky `1777` directory is accepted) |
| 9 | Replace the file with a symlink to a valid file in a directory only you can write | Scan succeeds; a link planted in a shared directory by another user is refused |
| 10 | Write invalid JSON: a duplicate key, `{"profile": null}`, `NaN`, a file with a byte-order mark, a file over 1 MiB | Each exits `2` with a message prefixed `user settings` and in tilde form; the content is never echoed |
| 11 | `uv run docsentinel scan "$SCRATCH/proj" --no-user-settings` with a refused or unreadable file | Exit `0`; the file is not read |
| 12 | `DOCSENTINEL_SETTINGS=off uv run docsentinel doctor` | `user settings: off (DOCSENTINEL_SETTINGS=off)`; `init --user` exits `2` |
| 13 | `DOCSENTINEL_SETTINGS=relative.json uv run docsentinel scan "$SCRATCH/proj"` | Exit `2`; the value is not echoed |
| 14 | Restore a valid user file first (for example step 4's content, mode `600`). Then `printf '{"reference_scope": "strict"}' > "$SCRATCH/proj/c.json"; uv run docsentinel scan "$SCRATCH/proj" --config "$SCRATCH/proj/c.json" -v` | Exit `0`; the stderr `config:` line shows `project c.json`; a `docsentinel.json` in the scan root is not picked up without `--config` |
| 15 | Set `profile` in the user file and a different `profile` in the project config | The project value wins; a command-line `--profile` wins over both |
| 16 | `uv run docsentinel scan "$SCRATCH/proj"` and read the stderr INFO lines | `config: user settings loaded (<names>), project <file or none>`; names only, at most 20, then `and N more` |
| 17 | `.github/workflows/ci.yml` | Every job that runs `docsentinel` sets `DOCSENTINEL_SETTINGS: "off"` at job level |
| 18 | On WSL, a settings file under the Windows mount | Refused (mode `0777`); the same file in the Linux home loads |

## Cleanup

```sh
rm -rf "$SCRATCH"; unset SCRATCH DOCSENTINEL_SETTINGS
```

Never run these steps against the real `~/.local/share/docsentinel/settings.json`.

## See also

- [Configuration reference: how to set options](../user/reference/configuration.md#how-to-set-options)
- [Threat model for user settings](../security/threat-model-0009-user-settings-2026-11-17.md)
- [The test suite guide](README.md)
