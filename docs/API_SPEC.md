# API Spec

## Auth

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

The MVP issues signed HMAC access and refresh tokens and stores seeded passwords as SHA-256 hashes for local development.

## Prompt

- `GET /api/prompts?q=keyword&tag=tag`
- `POST /api/prompts`
- `GET /api/prompts/{id}`
- `PUT /api/prompts/{id}`
- `DELETE /api/prompts/{id}`
- `POST /api/prompts/{id}/copy`
- `POST /api/prompts/{id}/review`

## Knowledge Card

- `GET /api/cards`
- `POST /api/cards`
- `POST /api/cards/{id}/publish`
- `POST /api/cards/{id}/favorite`

## Skill

- `GET /api/skills`
- `GET /api/skills/installed`
- `POST /api/skills/upload`
- `GET /api/skills/{id}`
- `POST /api/skills/{id}/review`
- `POST /api/skills/{id}/install`
- `POST /api/skills/{id}/uninstall`
- `POST /api/skills/{id}/update`
- `POST /api/skills/{id}/rollback`
- `POST /api/skills/{id}/rate`

## Audit

- `GET /api/audit-logs`

The current MVP uses in-memory storage so the behavior can be developed and tested before wiring PostgreSQL persistence.
