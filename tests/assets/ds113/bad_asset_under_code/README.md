# Project

Documentation often shows broken markup as an example. A CommonMark renderer
hides these, so DocSentinel must not resolve them as live assets.

```markdown
![diagram](missing-in-fence.png)
```

Inline too: `![x](missing-in-span.png)` is just sample text.
