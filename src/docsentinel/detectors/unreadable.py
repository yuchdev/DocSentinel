"""DS100: a discovered document the engine could not read or decode.

``DS100`` has no analyzer. The engine checks every discovered document once
before any analyzer runs (``engine._partition_readable``): a document that cannot
be opened, is not a regular file or is not valid UTF-8 is withheld from every
analyzer, because none of them could check it, and is reported here instead.
The document stays in the inventory and the finding is an ``error``, so one bad
byte can never turn the gate green (security review H1).

The rule is registered in the ``fast`` profile so ``docsentinel rules`` and the
rule table list it, but it is an engine rule (:data:`docsentinel.rules.ENGINE_RULES`):
the engine emits it in every profile, honouring ``select``/``ignore``, and never
counts it among the evaluated rules of ``ScanResult.notice``.
"""

from typing import Final

from docsentinel import models, rules
from docsentinel.log import safe

DS100 = rules.register_rule(
    rules.Rule(
        code="DS100",
        profile="fast",
        title="Unreadable document",
        description="A discovered document cannot be read or is not valid UTF-8, so no other rule checked it.",
        severity="error",
    )
)

#: ``Finding.type`` of every DS100 finding.
FINDING_TYPE: Final[str] = "unreadable document"
#: Reason for a document that is not valid UTF-8.
NOT_UTF8: Final[str] = "not valid UTF-8"
#: Reason for a discovered path that is no longer a regular file when it is read.
NOT_REGULAR: Final[str] = "not a regular file"
#: Character cap on the reason echoed in a finding.
REASON_LIMIT: Final[int] = 120


def cannot_read(strerror: str) -> str:
    """Return the reason for a document whose open or read failed.

    :param strerror: The OS error text, or the exception type name when it has none.
    :returns: ``cannot read it (<strerror>)``.
    """
    return f"cannot read it ({strerror})"


def unreadable_finding(path: str, reason: str) -> models.Finding:
    """Return the DS100 finding for one unreadable document.

    The message is deterministic (``unreadable document: <reason>``) because it is
    part of the baseline fingerprint. It names only the reason, never content.

    :param path: The document path relative to the scan root.
    :param reason: :data:`NOT_UTF8`, :data:`NOT_REGULAR` or a :func:`cannot_read` text.
    :returns: An ``error`` finding with no line or column.
    """
    shown = safe(reason, REASON_LIMIT)
    return models.Finding(
        rule=DS100.code,
        path=path,
        message=f"unreadable document: {shown}",
        severity=DS100.severity,
        value=shown,
        type=FINDING_TYPE,
    )
