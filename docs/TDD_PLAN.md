# TDD Plan

## Backend

- `/health` returns 200.
- Correct credentials can login.
- Wrong password fails.
- Disabled account cannot login.
- Refresh token returns a new access token.
- Tampered token is rejected.
- Logout revokes access token.
- Protected endpoints require login.
- Member cannot access admin review endpoint.
- Admin-created Prompt is published.
- Member-created Prompt is pending.
- Published Prompt can be searched.
- Prompt tag filter returns matching results.
- Admin review publishes member Prompt and writes audit log.
- Member cannot review Prompt.
- Private Prompt is hidden from other users.
- Copying Prompt increments `usage_count`.
- Prompt detail respects visibility.
- Prompt owner can update Prompt and writes audit log.
- Member cannot update another user's private Prompt.
- User can create Knowledge Card.
- Admin can publish Knowledge Card.
- Member can favorite Knowledge Card.
- Skill zip requires `SKILL.md`.
- `SKILL.md` requires `name` and `description`.
- `skill.json` is parsed.
- Published Skill detail is visible to members.
- Pending Skill detail is hidden from other members.
- `scripts/` marks Skill as high risk.
- Zip path traversal is rejected.
- Admin review publishes Skill and writes audit log.
- Deleting Prompt writes audit log.
- Installing Skill writes audit log.
- Installed Skills list current user's installs.
- Uninstalling Skill marks install removed and writes audit log.
- Updating installed Skill moves install to new version and writes audit log.
- Rolling back installed Skill restores a previous version and writes audit log.
- Duplicate Skill install returns already installed.
- Skill rating calculates average score.
- Archived Skill cannot be installed.
- High risk Skill install requires confirmation.
- Skill upload blocks sensitive script commands.
- Skill upload rejects oversized zip packages.

## Frontend

- Login page renders.
- Login failure shows an error.
- Prompt list renders and filters.
- Copy action shows success.
- Skill list renders.
- Admin can see review action.
- Member cannot see review action.

## Desktop

- Floating ball is the first desktop entry.
- Main panel contains search and copy actions.
- Tauri tray configuration is present.
