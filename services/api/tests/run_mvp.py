from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_mvp
from app.main import (
    AUDIT_LOGS,
    CARD_FAVORITES,
    KNOWLEDGE_CARDS,
    PROMPTS,
    REVOKED_TOKEN_IDS,
    SKILL_INSTALLS,
    SKILL_RATINGS,
    SKILLS,
)


def reset_state() -> None:
    PROMPTS.clear()
    KNOWLEDGE_CARDS.clear()
    CARD_FAVORITES.clear()
    SKILLS.clear()
    SKILL_INSTALLS.clear()
    SKILL_RATINGS.clear()
    REVOKED_TOKEN_IDS.clear()
    AUDIT_LOGS.clear()


def main() -> None:
    tests = [
        item
        for _, item in sorted(vars(test_mvp).items())
        if inspect.isfunction(item) and item.__name__.startswith("test_")
    ]
    for test in tests:
        reset_state()
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main()
