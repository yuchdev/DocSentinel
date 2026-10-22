"""Oracle-parity regression: the Story 11.0 fix changes DS101/DS103 only for security categories.

Contract E and Story 11.0 require that removing the DS101/DS103 outside-root existence
oracle does **not** otherwise change their public behavior. These tests load the frozen
pre-Story-11.0 copies of ``links.py`` and ``paths.py`` kept in ``tests/reference`` as reference
modules, run the old and the
new detectors over a seeded corpus and over this repository's own documentation, and assert
that the only differences are findings that disappear because their target is a security
category DS116 now owns (a root escape, an unsafe ``drive``/``unc``/``backslash``/``control``
target, or an in-root symlink pointing outside) -- and that no new finding ever appears.

The frozen modules are exec'd under private names while DS101/DS103 are temporarily removed from
the shared registry, which is restored immediately afterward so the live rules are untouched.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import load_config
from docsentinel.detectors import links as new_links
from docsentinel.detectors import paths as new_paths
from docsentinel.detectors.path_boundaries import escapes_via_symlink, is_ds116_owned
from docsentinel.discovery import discover

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = REPO_ROOT / "tests" / "reference"


def _load_frozen_module(filename: str, module_name: str) -> types.ModuleType:
    """Exec a frozen pre-Story-11.0 detector reference under a private name.

    The reference files in ``tests/reference`` are verbatim copies of ``links.py`` and
    ``paths.py`` as they were BEFORE the Story 11.0 existence-oracle fix. They are frozen
    in the repository (not read from ``git``) so this guard keeps comparing against the
    original behaviour after the change is committed. DS101/DS103 are popped from the
    shared registry so the old module can register them during exec without a
    duplicate-code error, then the registry (rules and analyzers) is restored verbatim so
    the live detectors are unaffected.

    :param filename: Name of the frozen reference file inside ``tests/reference``.
    :param module_name: Private name to register the loaded module under.
    :returns: The executed reference module.
    """
    source = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
    saved_rules = dict(rules.RULES)
    saved_analyzers = dict(rules.ANALYZERS)
    for code in ("DS101", "DS103"):
        rules.RULES.pop(code, None)
    module = types.ModuleType(module_name)
    module.__file__ = str(REFERENCE_DIR / filename)
    sys.modules[module_name] = module
    try:
        # The executed source is this repository's own frozen reference copy (trusted).
        exec(compile(source, filename, "exec"), module.__dict__)
    finally:
        rules.RULES.clear()
        rules.RULES.update(saved_rules)
        rules.ANALYZERS.clear()
        rules.ANALYZERS.update(saved_analyzers)
    return module


def _target_is_security_owned(root: Path, document_path: str, target: str) -> bool:
    """Return whether a disappeared finding's target is a DS116-owned security category.

    :param root: The scan root.
    :param document_path: POSIX path of the document the finding came from.
    :param target: The raw target echoed in the finding message.
    :returns: ``True`` when the target escapes the root, is an unsafe category, or
        reaches outside through an in-root symlink.
    """
    if is_ds116_owned(root, document_path, target):
        return True
    file_part = target.partition("#")[0]
    if not file_part:
        return False
    base = root if file_part.startswith("/") else (root / document_path).parent
    joined = base / file_part.lstrip("/") if file_part.startswith("/") else base / file_part
    return escapes_via_symlink(root, joined)


def _finding_targets(findings: tuple[models.Finding, ...]) -> set[tuple[str, int, str]]:
    """Return a hashable ``(path, line, target)`` key set for a finding tuple."""
    keys: set[tuple[str, int, str]] = set()
    for finding in findings:
        target = finding.message.split("-> ", 1)[-1]
        keys.add((finding.path, finding.line or 0, target))
    return keys


@pytest.fixture(scope="module")
def frozen_modules() -> tuple[types.ModuleType, types.ModuleType]:
    """Load the frozen pre-Story-11.0 ``links`` and ``paths`` references once per test module."""
    old_links = _load_frozen_module("ds101_links_pre_story_11.py.txt", "_frozen_links_ds101")
    old_paths = _load_frozen_module("ds103_paths_pre_story_11.py.txt", "_frozen_paths_ds103")
    return old_links, old_paths


def _seeded_document(root: Path) -> models.Document:
    """Write a comprehensive seeded corpus document under ``docs`` and return its model."""
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "exists.md").write_text("# exists\n", encoding="utf-8")
    (root / "top.md").write_text("# top\n", encoding="utf-8")
    (docs / "sub").mkdir()

    db_url_env = "postgres://user:${PGPASSWORD}@host/db"  # env-var reference, not a literal credential
    spans = [
        "*.md",
        "docs/**",
        ".claude/**",
        "{NN}-{slug}.md",
        "a{b}c.md",
        "docs/?.md",
        "http://example.com/x",
        "https://example.com/y",
        "ftp://host/z",
        "mailto:a@b.c",
        "postgres://host/db",
        db_url_env,
        "exists.md",
        "missing.py",
        "sub/other.py",
        "/usr/bin/python3",
        "#!/usr/bin/python3",
        "./exists.md",
        "a/../missing.md",
        "sub/",
        "caf\u00e9.md",
        "../../escape.py",
        "%2e%2e/%2e%2e/enc.py",
        r"C:\Windows\win.ini",
        r"\\server\share\x.py",
        r"\rooted\win.py",
        "%252e%252e/double.py",
    ]
    code_block = "".join(f"- `{span}`\n" for span in spans)
    link_block = "".join(f"[t{i}]({span})\n" for i, span in enumerate(spans))
    image_block = "![i](../../escape.png)\n![j](exists.md)\n"
    ref_block = "[r1]: ../../escape.md\n[r2]: missing.md\n"
    fenced = "```\n`../../fenced.py`\n[f](../../fenced.md)\n```\n"
    commented = "<!-- `../../commented.py` [c](../../commented.md) -->\n"
    body = code_block + link_block + image_block + ref_block + fenced + commented
    (docs / "README.md").write_text(body, encoding="utf-8")
    return models.Document("docs/README.md", 0)


def test_ds101_and_ds103_seeded_corpus_differ_only_by_security_categories(
    tmp_path: Path, frozen_modules: tuple[types.ModuleType, types.ModuleType]
):
    """
    [Integration] oracle parity: verifies DS101/DS103 differ from the frozen pre-Story-11.0 reference only on DS116-owned targets.

    Scenario:
        Given a seeded document exercising globs, templates, URL schemes, anchors, existing and
            missing in-root paths, a directory, an absolute POSIX path, oscillation, a shebang span,
            images, reference definitions, and fenced/commented examples, plus explicit escapes and
            Windows/UNC/backslash/encoded targets
        When the frozen reference and current DS101 and DS103 detectors both scan it
        Then no new finding appears in either rule, and every finding that disappears has a target
            that is a DS116-owned security category (escape, drive/unc/backslash/control, or symlink-out).

    Boundaries:
        - Focus: parity of DS101/DS103 public behavior outside the security categories
        - Fixtures/params: tmp_path, frozen_modules

    On failure, first check:
        - The reported appeared set (must be empty) and the disappeared targets that are not security-owned
        - Whether a glob/template/external/in-root target was wrongly skipped by the new detector
    """
    old_links, old_paths = frozen_modules
    documents = (_seeded_document(tmp_path),)

    for old_module, new_module in ((old_links, new_links), (old_paths, new_paths)):
        old_keys = _finding_targets(old_module.detect(tmp_path, documents))
        new_keys = _finding_targets(new_module.detect(tmp_path, documents))
        appeared = new_keys - old_keys
        disappeared = old_keys - new_keys

        assert appeared == set(), f"{new_module.__name__}: unexpected new findings {appeared}"
        not_owned = {key for key in disappeared if not _target_is_security_owned(tmp_path, key[0], key[2])}
        assert not_owned == set(), f"{new_module.__name__}: findings disappeared that are not DS116-owned: {not_owned}"
        assert disappeared, f"{new_module.__name__}: seeded corpus produced no security-owned difference"


def test_repo_docs_diff_matches_security_categories_only(
    frozen_modules: tuple[types.ModuleType, types.ModuleType],
):
    """
    [Integration] oracle parity: verifies the repo-docs DS101/DS103 diff is security-owned only.

    Scenario:
        Given this repository's own documentation discovered with the project configuration
        When the frozen reference and current DS101 and DS103 detectors both scan every document
        Then under the Story 11.0 code-span ruling nothing appears AND nothing disappears for either
            rule over this repo's docs: DS101 links have no escaping targets here, and DS103 again
            reports the drive/UNC/backslash code-span examples it momentarily skipped, so new == frozen.

    Boundaries:
        - Focus: reproduces the reviewer's diff method on the real corpus; the allowed difference for
          DS103 code spans has shrunk to root-escape + symlink-out (none of which occur in repo docs)
        - Fixtures/params: frozen_modules

    On failure, first check:
        - The printed appeared/disappeared lists; any non-empty set means the code-span split drifted
        - Whether a drive/UNC/backslash code span is still wrongly skipped by new DS103
    """
    old_links, old_paths = frozen_modules
    config = load_config(REPO_ROOT)
    documents = discover(REPO_ROOT, config)

    for old_module, new_module in ((old_links, new_links), (old_paths, new_paths)):
        old_keys = _finding_targets(old_module.detect(REPO_ROOT, documents))
        new_keys = _finding_targets(new_module.detect(REPO_ROOT, documents))
        appeared = new_keys - old_keys
        disappeared = old_keys - new_keys

        assert appeared == set(), f"{new_module.__name__}: unexpected new findings over repo docs: {appeared}"
        assert disappeared == set(), (
            f"{new_module.__name__}: findings changed over repo docs; the code-span scope expects an "
            f"identical diff (0 disappeared) here: {disappeared}"
        )
