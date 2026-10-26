# Example guide

This sample document is available for a simple inventory demonstration. It also walks through five small
examples of what DocSentinel reports. The settings they rely on are explained line by line in
[the example configuration](../docsentinel.toml).

Run every command from the repository root. If `docsentinel` is not on your path, put `uv run` in front of it.
To reproduce examples 2 to 4, save each snippet in the docs directory under the file name shown in the output
line below it, and delete the file again afterward.

## Example 1: inventory a directory

The example configuration only looks at Markdown files directly inside the docs directory, and it runs the
fast rules DS101 and DS102. Scanning the examples directory lists this guide and finds nothing wrong.

```sh
docsentinel scan examples
```

```text
Schema version: 1
Profile: fast
Documents: 1
Enabled rules: ["DS101", "DS102"]
2 fast rule(s) evaluated.
  docs/guide.md (N bytes)
```

The exit code is 0. An empty findings list is a successful scan, and the rule line shows what was actually
checked.

## Example 2: a dangling link (DS101)

DS101 reports a link whose target file does not exist, or whose `#anchor` is not a heading in the target.
Take a document with this content:

```markdown
# Setup notes

Follow the [install steps](install.md) first.
```

When the target file is missing, the scan prints one error per bad link:

```text
error: docs/setup-notes.md: dangling link -> install.md
```

Errors fail the scan, so the exit code is 1. Fix it by creating the target or correcting the link. Links
that start with a scheme, such as a web address, are never resolved. Links inside fenced code blocks and
inline code are ignored.

## Example 3: a stray HTML comment (DS102)

DS102 reports HTML comments left in a Markdown file, because they were probably meant as a note to the author
and would be easy to publish by mistake.

```markdown
# Release notes

<!-- TODO: add the 2.0 changes before publishing -->

Version 2.0 is out.
```

```text
warning: docs/release-notes.md: stray HTML comment: '<!-- TODO: add the 2.0 changes before publishing -->'
```

This is a warning, so the exit code stays 0. Add `--strict` and warnings fail the scan too, with exit code 1.
A comment that spans several lines is reported once, at the line where it starts.

## Example 4: select and ignore rules (DS103)

DS103 reports an inline code span that looks like a file path but does not resolve.

```markdown
# Layout

The entry point is `src/app/main.py`.
```

The example configuration lists DS103 under ignore, so a plain scan stays silent about it. Passing
`--ignore DS102` on the command line replaces that list, which turns DS103 back on and switches DS102 off:

```sh
docsentinel scan examples --ignore DS102
```

```text
warning: docs/layout.md: unresolvable path -> src/app/main.py
```

Ignore always wins over select. Running with only `--select DS103` while the file still ignores DS103
evaluates nothing, and the scan says so: `All fast rules were excluded by select/ignore.`

## Example 5: adopt DocSentinel on an existing project

A project with many old findings can record them once and only fail on new ones. The baseline command
writes the current findings to a file:

```sh
docsentinel baseline examples
```

```text
Saved baseline: /path/to/examples/.docsentinel-baseline.json
```

Point the configuration at that file by adding one line:

```toml
baseline = ".docsentinel-baseline.json"
```

From then on a scan hides the recorded findings and reports only new ones. With every error baselined the
exit code is 0, even under `--strict`. A finding is matched by its rule, file, and message, not by line
number, so adding text above an old finding does not bring it back.
