---
name: secret-scan
description: Scan requested or changed text files for likely hard-coded credentials and provide safe remediation without exposing secret values.
---

# Secret scan

Use supplied paths; otherwise inspect staged, unstaged, and untracked changed text files. Skip binary
and large artifact formats such as locks, images, PDFs, dumps, and databases, while warning that
skipped dumps may still contain sensitive data.

Search for high-signal credential shapes: AWS access and secret keys, Anthropic/OpenAI/Google keys,
GitHub and Slack tokens, private-key headers, credential-bearing Postgres URLs, and quoted assignments
to password/secret/token/API-key names. Treat obvious examples, `${VAR}` references, redacted values,
and explicit test placeholders as non-secrets. A generic assigned value that is exactly a 32/64-bit
hex address (at most 16 hex digits, optional integer suffix) is not a credential; longer hex values
remain findings.

Report only `file:line` and credential type with a safely redacted excerpt—never the full value. For
each real hit: remove it, rotate it if it reached any remote, replace it with an environment variable
or secrets manager, and recommend history rewriting if committed. End with `CLEAN` or the finding
count. Do not weaken detection merely to accommodate a fixture; make fixtures unmistakably fake.