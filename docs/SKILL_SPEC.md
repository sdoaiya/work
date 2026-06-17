# Skill Package Spec

Standard package:

```text
skill-name/
├── SKILL.md
├── skill.json
├── README.md
├── prompts/
├── references/
├── assets/
├── scripts/
└── examples/
```

Rules:

1. `SKILL.md` is required.
2. `SKILL.md` must include frontmatter `name`.
3. `SKILL.md` must include frontmatter `description`.
4. `skill.json` is parsed when present.
5. Any `scripts/` directory marks the package as `high` risk.
6. Zip path traversal is rejected.
7. Scripts are never executed in the MVP.
8. Publishing requires admin review.
9. High risk Skill installation requires explicit confirmation.
10. The same user cannot install the same Skill version twice.
11. Archived Skills cannot be newly installed.
12. Scripts containing sensitive commands or sensitive local paths are rejected at upload time.
13. Skill zip uploads are limited to 5 MB in the MVP.
