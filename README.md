# AI WorkDock

AI WorkDock is a desktop dock and team AI knowledge platform for prompts, internal AI experience cards, workflows, forum knowledge, and installable Codex Skills.

## Current MVP

- FastAPI backend with auth, RBAC, Prompt search/copy, Skill zip parsing, admin review, and audit logs.
- Signed local access/refresh tokens and hashed seed passwords.
- React admin web shell for login, Prompt list, and Skill list.
- Tauri desktop shell with floating entry and tray configuration.
- Docker Compose and CI skeleton.

## Verify

```bash
cd services/api
python tests/run_mvp.py
```

Pytest test files are present, but this Windows environment currently hangs inside the pytest runner. The direct runner reuses the same test functions and avoids the plugin layer.
