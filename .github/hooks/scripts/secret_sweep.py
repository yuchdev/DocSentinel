#!/usr/bin/env python3
"""Stop hook: sweep the files this session can ship for credentials and warn loudly.

``secret_scan.py`` only sees the content of an agent's own Write/Edit calls. A key that
arrives any other way -- a manual commit, a copied file, an IDE save, a Bash redirect --
is invisible to it. This hook closes that gap at the end of every turn by scanning, in
full, every file that is modified, untracked, or committed but not yet pushed.

On a hit it does two things so the warning cannot be skimmed past:

* ``systemMessage`` shows the user a boxed banner directly (not routed through the model);
* ``decision: block`` makes the agent continue and open its reply with the same banner.

A repeat Stop (``stop_hook_active``) only re-shows the banner and never blocks again, so the
session cannot loop. The secret itself is never printed or logged: only file, line, rule
name and the first four characters of the match.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _common import REPO_ROOT, allow, append_log, read_event
from secret_scan import PATTERNS, SKIP_SUFFIXES, scan_text

MAX_FILE_BYTES = 1_000_000
MAX_FINDINGS_SHOWN = 10
BAR = "!" * 72


def _git(*args: str) -> list[str]:
    """Return NUL- or newline-separated git output as a list; empty on any failure."""
    try:
        proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [part for part in proc.stdout.replace("\0", "\n").splitlines() if part]


def candidate_files() -> list[Path]:
    """Modified, untracked and unpushed files (deduplicated, existing regular files only)."""
    names: set[str] = set()
    for line in _git("status", "--porcelain", "-z", "--untracked-files=all"):
        # "XY path"; a rename entry is followed by a bare path token, handled by the fallback.
        names.add(line[3:] if len(line) > 3 and line[2] == " " else line)
    names.update(_git("diff", "--name-only", "--diff-filter=ACMR", "@{u}..HEAD"))
    files: list[Path] = []
    for name in sorted(names):
        path = REPO_ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _mask(text: str, name: str, lineno: int) -> str:
    """First four characters of the offending match, never more."""
    line = text.splitlines()[lineno - 1]
    match = PATTERNS[name].search(line)
    return f"{match.group(0)[:4]}***" if match else "***"


def sweep(paths: list[Path]) -> list[tuple[str, int, str, str]]:
    """Return (relative_path, line, rule, masked_prefix) for every hit."""
    hits: list[tuple[str, int, str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for name, lineno, _excerpt in scan_text(text):
            hits.append((rel, lineno, name, _mask(text, name, lineno)))
    return hits


def banner(hits: list[tuple[str, int, str, str]]) -> str:
    """The boxed, all-caps warning shown to the user."""
    shown = hits[:MAX_FINDINGS_SHOWN]
    rows = [f"  >> {rel}:{lineno}  [{name}]  {masked}" for rel, lineno, name, masked in shown]
    if len(hits) > len(shown):
        rows.append(f"  >> ... and {len(hits) - len(shown)} more (see .copilot/logs/secret-sweep.log)")
    return "\n".join(
        [
            "",
            BAR,
            BAR,
            "!!  SECURITY WARNING: POSSIBLE LIVE SECRET IN FILES YOU MAY COMMIT OR PUSH  !!",
            BAR,
            *rows,
            BAR,
            "  1. DO NOT commit or push these files.",
            "  2. If it is a real key, ROTATE IT NOW - treat it as already exposed.",
            "  3. If it was already pushed, history must be rewritten (git filter-repo).",
            BAR,
            BAR,
            "",
        ]
    )


def main() -> None:
    event = read_event()
    hits = sweep(candidate_files())
    if not hits:
        append_log("secret-sweep.log", "CLEAN")
        allow()
    for rel, lineno, name, _masked in hits:
        append_log("secret-sweep.log", f"FOUND {rel}:{lineno} [{name}]")
    text = banner(hits)
    payload: dict[str, object] = {"systemMessage": text}
    if not event.get("stop_hook_active"):
        payload["decision"] = "block"
        payload["reason"] = (
            "The Stop-time secret sweep found a possible credential. Begin your final reply "
            "with the banner below, verbatim, in a code block, before anything else, and do "
            "not commit or push the listed files. Tell the user to rotate the key. Never print "
            "the secret itself.\n" + text
        )
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
