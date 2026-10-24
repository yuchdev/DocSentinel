# Multiple unterminated blocks

A long opener swallows later pseudo-openers as body, so only the original
opener is reported once:

`````
body line
```
pseudo opener above is swallowed
```
more swallowed body
