"""Regression tests: the shared resolver stays compatible with DS101/DS103.

These guard the intentional overlap documented in the Milestone 0005 contracts:
the shared :func:`resolve_local_reference` classifies targets the same way the
existing fast detectors treat them, so a future shared adapter cannot silently
change DS101/DS103 behavior.
"""

from pathlib import Path

from docsentinel.detectors import paths
from docsentinel.detectors.links import _is_skippable
from docsentinel.markdown_blocks import ReferenceStatus, resolve_local_reference


def test_external_and_template_targets_are_not_resolved_like_ds101():
    """
    [Unit] markdown_blocks: verifies external and template targets are not resolved like ds101.

    Scenario:
        Given link targets DS101 treats as skippable (URLs, templates, globs)
        When resolve_local_reference classifies each target
        Then every target resolves to an EXTERNAL or UNSUPPORTED status.

    Boundaries:
        - Focus: resolver agreement with DS101 skippable targets
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the resolver status
        - DS101 _is_skippable and resolve_local_reference branches
        - Recent changes to scheme/template handling
    """
    root = Path("/repo")
    skippable = ["https://example.com", "//cdn.example/x.png", "{placeholder}", "glob*.md"]
    for target in skippable:
        assert _is_skippable(target) is True
        status = resolve_local_reference(root, "README.md", target).status
        assert status in (ReferenceStatus.EXTERNAL, ReferenceStatus.UNSUPPORTED)


def test_ordinary_local_targets_resolve_inside_root():
    """
    [Unit] markdown_blocks: verifies ordinary local targets resolve inside root.

    Scenario:
        Given ordinary local link targets DS101 resolves
        When resolve_local_reference classifies each target
        Then each is RESOLVED with a candidate path inside the scan root.

    Boundaries:
        - Focus: resolver agreement with DS101 resolvable targets
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the resolver status and path
        - DS101 _is_skippable and resolve_local_reference branches
        - Recent changes to rooted/relative path handling
    """
    root = Path("/repo")
    for target in ["guide.md", "./guide.md", "/docs/guide.md", "nested/page.md#anchor"]:
        assert _is_skippable(target) is False
        resolved = resolve_local_reference(root, "docs/index.md", target)
        assert resolved.status is ReferenceStatus.RESOLVED
        assert resolved.path is not None
        assert root in resolved.path.parents or resolved.path == root


def test_root_escape_is_flagged_outside_root():
    """
    [Unit] markdown_blocks: verifies root escape is flagged outside root.

    Scenario:
        Given a link target that lexically escapes the scan root via ``..``
        When resolve_local_reference classifies the target
        Then the status is OUTSIDE_ROOT and no candidate path is returned.

    Boundaries:
        - Focus: DS116-style root-escape detection
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the resolver status
        - The _normalize_relative escape branch
        - Recent changes to containment handling
    """
    root = Path("/repo")
    resolved = resolve_local_reference(root, "docs/index.md", "../../etc/passwd")
    assert resolved.status is ReferenceStatus.OUTSIDE_ROOT
    assert resolved.path is None


def test_local_paths_resolve_to_the_same_target_as_ds103():
    """
    [Unit] markdown_blocks: verifies local paths resolve to the same target as ds103.

    Scenario:
        Given relative and rooted path spans DS103 resolves via ``_resolve``
        When resolve_local_reference classifies the same raw target
        Then it is RESOLVED to the identical filesystem path DS103 computes.

    Boundaries:
        - Focus: resolver agreement with DS103 path resolution
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the resolved path equality
        - paths._resolve rooted vs source-relative branches
        - Recent changes to resolver combine/normalize handling
    """
    root = Path("/repo")
    source = root / "README.md"
    for target in ["docs/guide.md", "/docs/guide.md"]:
        resolved = resolve_local_reference(root, "README.md", target)
        assert resolved.status is ReferenceStatus.RESOLVED
        assert resolved.path == paths._resolve(target, source, root)


def test_ds103_exclusions_are_a_non_overlapping_domain():
    """
    [Unit] markdown_blocks: verifies DS103 exclusions are a non-overlapping domain.

    Scenario:
        Given spans DS103 deliberately excludes from path detection
            (version strings and bare extensions)
        When resolve_local_reference classifies the same raw targets
        Then DS103 rejects them as non-path-like while the resolver still
            RESOLVES them, proving the two domains do not overlap and the
            resolver is not a silent substitute for DS103's code-span rules.

    Boundaries:
        - Focus: non-overlap between DS103 code-span exclusions and the resolver
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to _looks_path_like vs resolver status
        - paths._is_excluded version and bare-extension branches
        - Recent changes to resolver scheme/glob handling
    """
    root = Path("/repo")
    for target in ["1.2.3", ".md"]:
        assert paths._looks_path_like(target) is False
        assert resolve_local_reference(root, "README.md", target).status is ReferenceStatus.RESOLVED
