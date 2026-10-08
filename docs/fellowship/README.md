# docs/fellowship/

Project-side state for the Fellowship plugin. The tree is closed — do not add directories or files beyond those listed here.

```
docs/fellowship/
├── README.md              this guide
├── product.md             what we are building, and for whom
├── quest-log.md           open decisions and commitments, one dated line each
├── quest-log-archive.md   older quest-log entries (SessionEnd sweep)
├── specs/                 active specs
├── plans/                 active implementation plans
├── handoffs/              active session handoffs
├── design/                active design contracts
└── archive/
    ├── specs/
    ├── plans/
    ├── handoffs/
    └── design/
```

- Archives are flat, one directory per artifact type — no quarterly subdivision.
- Ethos and artifact templates are plugin-owned; there is no `templates/` here.
- `session-log.md` is retired; use `quest-log.md` and `handoffs/`.
