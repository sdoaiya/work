import io
import json
import zipfile

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def login(email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_skill_zip(
    skill_md: str | None = "---\nname: demo\ndescription: Demo skill\n---\n# Demo\n",
    skill_json: dict | None = None,
    include_scripts: bool = False,
    script_content: str = "print('hello')\n",
    traversal_name: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if skill_md is not None:
            archive.writestr("../SKILL.md" if traversal_name else "demo/SKILL.md", skill_md)
        if skill_json is not None:
            archive.writestr("demo/skill.json", json.dumps(skill_json))
        if include_scripts:
            archive.writestr("demo/scripts/run.py", script_content)
    return buffer.getvalue()


def test_health_returns_200():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_correct_credentials_can_login():
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@workdock.local", "password": "admin123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]
    assert response.json()["access_token"].count(".") == 2


def test_wrong_password_fails_login():
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@workdock.local", "password": "wrong"},
    )

    assert response.status_code == 401


def test_disabled_account_cannot_login():
    response = client.post(
        "/api/auth/login",
        json={"email": "disabled@workdock.local", "password": "disabled123"},
    )

    assert response.status_code == 401


def test_refresh_token_returns_new_access_token():
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@workdock.local", "password": "admin123"},
    ).json()

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_response["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"].count(".") == 2
    assert response.json()["token_type"] == "bearer"


def test_tampered_token_is_rejected():
    token = login("admin@workdock.local", "admin123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    response = client.get("/api/auth/me", headers=auth_header(tampered))

    assert response.status_code == 401


def test_logout_revokes_access_token():
    token = login("admin@workdock.local", "admin123")

    logout = client.post("/api/auth/logout", headers=auth_header(token))
    response = client.get("/api/auth/me", headers=auth_header(token))

    assert logout.status_code == 204
    assert response.status_code == 401


def test_protected_endpoint_requires_login():
    response = client.post("/api/prompts", json={"title": "x", "content": "y"})

    assert response.status_code == 401


def test_member_cannot_access_admin_review():
    member_token = login("member@workdock.local", "member123")

    response = client.post(
        "/api/skills/unknown/review",
        headers=auth_header(member_token),
        json={"status": "published"},
    )

    assert response.status_code == 403


def test_admin_can_create_prompt_as_published():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={
            "title": "政府汇报材料",
            "content": "请把业务思路整理成政府汇报方案",
            "tags": ["政府汇报", "方案"],
            "visibility": "team",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "published"


def test_member_prompt_is_pending():
    member_token = login("member@workdock.local", "member123")

    response = client.post(
        "/api/prompts",
        headers=auth_header(member_token),
        json={"title": "外贸邮件", "content": "写一封外贸跟进邮件"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_published_prompt_can_be_searched_by_member():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "Codex 调试", "content": "定位测试失败", "tags": ["Codex"]},
    )

    response = client.get(
        "/api/prompts",
        headers=auth_header(member_token),
        params={"q": "Codex"},
    )

    assert response.status_code == 200
    assert any(item["title"] == "Codex 调试" for item in response.json())


def test_prompt_tag_filter_returns_matching_results():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "政府方案", "content": "方案正文", "tags": ["政府汇报"]},
    )
    client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "外贸邮件", "content": "邮件正文", "tags": ["外贸"]},
    )

    response = client.get(
        "/api/prompts",
        headers=auth_header(member_token),
        params={"tag": "外贸"},
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["外贸邮件"]


def test_admin_review_publishes_member_prompt_and_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(member_token),
        json={"title": "待审核 Prompt", "content": "审核通过后团队可见"},
    ).json()

    response = client.post(
        f"/api/prompts/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    search = client.get(
        "/api/prompts",
        headers=auth_header(member_token),
        params={"q": "待审核 Prompt"},
    )
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert any(item["id"] == created["id"] for item in search.json())
    assert any(log["action"] == "prompt.review" for log in logs)


def test_member_cannot_review_prompt():
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(member_token),
        json={"title": "成员不能审核", "content": "成员提交后待审核"},
    ).json()

    response = client.post(
        f"/api/prompts/{created['id']}/review",
        headers=auth_header(member_token),
        json={"status": "published"},
    )

    assert response.status_code == 403


def test_private_prompt_is_hidden_from_other_users():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "私有模板", "content": "仅自己可见", "visibility": "private"},
    )

    response = client.get(
        "/api/prompts",
        headers=auth_header(member_token),
        params={"q": "私有模板"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_copy_prompt_increments_usage_count():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "复制测试", "content": "复制正文"},
    ).json()

    response = client.post(
        f"/api/prompts/{created['id']}/copy",
        headers=auth_header(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["usage_count"] == 1
    assert response.json()["content"] == "复制正文"


def test_get_prompt_detail_respects_visibility():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "详情测试", "content": "团队可见详情"},
    ).json()

    response = client.get(f"/api/prompts/{created['id']}", headers=auth_header(member_token))

    assert response.status_code == 200
    assert response.json()["title"] == "详情测试"


def test_update_prompt_by_owner_writes_audit_log():
    member_token = login("member@workdock.local", "member123")
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(member_token),
        json={"title": "原始标题", "content": "原始正文"},
    ).json()

    response = client.put(
        f"/api/prompts/{created['id']}",
        headers=auth_header(member_token),
        json={"title": "更新标题", "content": "更新正文", "tags": ["更新"]},
    )
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["title"] == "更新标题"
    assert response.json()["content"] == "更新正文"
    assert response.json()["tags"] == ["更新"]
    assert any(log["action"] == "prompt.update" for log in logs)


def test_member_cannot_update_other_private_prompt():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "私有不可改", "content": "私有正文", "visibility": "private"},
    ).json()

    response = client.put(
        f"/api/prompts/{created['id']}",
        headers=auth_header(member_token),
        json={"title": "恶意更新", "content": "不应成功"},
    )

    assert response.status_code == 404


def test_user_can_create_knowledge_card():
    member_token = login("member@workdock.local", "member123")

    response = client.post(
        "/api/cards",
        headers=auth_header(member_token),
        json={
            "title": "AI 使用经验",
            "card_type": "experience",
            "content": "把常用 Prompt 沉淀成卡片",
            "tags": ["经验"],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["version"] == 1


def test_admin_can_publish_knowledge_card():
    member_token = login("member@workdock.local", "member123")
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/cards",
        headers=auth_header(member_token),
        json={"title": "待发布卡片", "card_type": "workflow", "content": "标准流程"},
    ).json()

    response = client.post(f"/api/cards/{created['id']}/publish", headers=auth_header(admin_token))
    list_response = client.get("/api/cards", headers=auth_header(member_token))

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert any(item["id"] == created["id"] for item in list_response.json())


def test_member_can_favorite_knowledge_card():
    member_token = login("member@workdock.local", "member123")
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/cards",
        headers=auth_header(admin_token),
        json={"title": "可收藏卡片", "card_type": "faq", "content": "FAQ 内容"},
    ).json()
    client.post(f"/api/cards/{created['id']}/publish", headers=auth_header(admin_token))

    response = client.post(f"/api/cards/{created['id']}/favorite", headers=auth_header(member_token))

    assert response.status_code == 200
    assert response.json()["favorite_count"] == 1


def test_skill_upload_requires_skill_md():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_md=None), "application/zip")},
    )

    assert response.status_code == 400
    assert "SKILL.md" in response.json()["detail"]


def test_skill_upload_requires_name():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(skill_md="---\ndescription: Demo skill\n---\n# Demo\n"),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert "name" in response.json()["detail"]


def test_skill_upload_requires_description():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(skill_md="---\nname: demo\n---\n# Demo\n"),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert "description" in response.json()["detail"]


def test_skill_json_is_parsed():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(skill_json={"skill_id": "demo", "version": "1.2.0"}),
                "application/zip",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["skill_id"] == "demo"
    assert response.json()["version"] == "1.2.0"


def test_published_skill_detail_visible_to_member():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "1.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )

    response = client.get(f"/api/skills/{created['id']}", headers=auth_header(member_token))

    assert response.status_code == 200
    assert response.json()["skill_id"] == "demo"


def test_pending_skill_detail_hidden_from_other_member():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()

    response = client.get(f"/api/skills/{created['id']}", headers=auth_header(member_token))

    assert response.status_code == 404


def test_skill_with_scripts_is_high_risk():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(include_scripts=True),
                "application/zip",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["risk_level"] == "high"


def test_skill_upload_blocks_sensitive_script_commands():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(include_scripts=True, script_content="rm -rf ~/.ssh\n"),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert "sensitive command" in response.json()["detail"]


def test_skill_upload_rejects_oversized_zip():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", b"x" * (5 * 1024 * 1024 + 1), "application/zip")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_skill_zip_rejects_path_traversal():
    admin_token = login("admin@workdock.local", "admin123")

    response = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={
            "file": (
                "skill.zip",
                make_skill_zip(traversal_name=True),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400


def test_admin_review_publishes_skill_and_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()

    response = client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert any(log["action"] == "skill.review" for log in logs)


def test_delete_prompt_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/prompts",
        headers=auth_header(admin_token),
        json={"title": "待删除 Prompt", "content": "删除需要审计"},
    ).json()

    response = client.delete(f"/api/prompts/{created['id']}", headers=auth_header(admin_token))
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 204
    assert any(log["action"] == "prompt.delete" for log in logs)


def test_skill_install_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )

    response = client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 201
    assert response.json()["status"] == "installed"
    assert any(log["action"] == "skill.install" for log in logs)


def test_installed_skills_lists_current_user_installs():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "1.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )

    response = client.get("/api/skills/installed", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()[0]["skill_ref_id"] == created["id"]
    assert response.json()[0]["version"] == "1.0.0"


def test_uninstall_skill_marks_install_removed_and_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )

    response = client.post(f"/api/skills/{created['id']}/uninstall", headers=auth_header(admin_token))
    installed = client.get("/api/skills/installed", headers=auth_header(admin_token)).json()
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["status"] == "removed"
    assert installed == []
    assert any(log["action"] == "skill.uninstall" for log in logs)


def test_update_installed_skill_to_new_version_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    version_one = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "1.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{version_one['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    client.post(
        f"/api/skills/{version_one['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )
    version_two = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "2.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{version_two['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )

    response = client.post(f"/api/skills/{version_two['id']}/update", headers=auth_header(admin_token))
    installed = client.get("/api/skills/installed", headers=auth_header(admin_token)).json()
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0"
    assert installed[0]["version"] == "2.0.0"
    assert any(log["action"] == "skill.update" for log in logs)


def test_rollback_installed_skill_to_previous_version_writes_audit_log():
    admin_token = login("admin@workdock.local", "admin123")
    version_one = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "1.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{version_one['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    version_two = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "2.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{version_two['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    client.post(
        f"/api/skills/{version_two['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )

    response = client.post(f"/api/skills/{version_one['id']}/rollback", headers=auth_header(admin_token))
    installed = client.get("/api/skills/installed", headers=auth_header(admin_token)).json()
    logs = client.get("/api/audit-logs", headers=auth_header(admin_token)).json()

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"
    assert installed[0]["version"] == "1.0.0"
    assert any(log["action"] == "skill.rollback" for log in logs)


def test_skill_rating_calculates_average():
    admin_token = login("admin@workdock.local", "admin123")
    member_token = login("member@workdock.local", "member123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )

    first = client.post(
        f"/api/skills/{created['id']}/rate",
        headers=auth_header(admin_token),
        json={"score": 5},
    )
    second = client.post(
        f"/api/skills/{created['id']}/rate",
        headers=auth_header(member_token),
        json={"score": 3},
    )

    assert first.status_code == 200
    assert first.json()["rating"] == 5.0
    assert second.status_code == 200
    assert second.json()["rating"] == 4.0


def test_duplicate_skill_install_returns_already_installed():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(skill_json={"skill_id": "demo", "version": "1.0.0"}), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    payload = {"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"}
    first = client.post(f"/api/skills/{created['id']}/install", headers=auth_header(admin_token), json=payload)
    second = client.post(f"/api/skills/{created['id']}/install", headers=auth_header(admin_token), json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Skill version already installed"


def test_archived_skill_cannot_be_installed():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "archived"},
    )

    response = client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )

    assert response.status_code == 404


def test_high_risk_skill_install_requires_confirmation():
    admin_token = login("admin@workdock.local", "admin123")
    created = client.post(
        "/api/skills/upload",
        headers=auth_header(admin_token),
        files={"file": ("skill.zip", make_skill_zip(include_scripts=True), "application/zip")},
    ).json()
    client.post(
        f"/api/skills/{created['id']}/review",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )

    response = client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={"target_tool": "Codex", "install_path": "C:/Users/example/.codex/skills/demo"},
    )
    confirmed = client.post(
        f"/api/skills/{created['id']}/install",
        headers=auth_header(admin_token),
        json={
            "target_tool": "Codex",
            "install_path": "C:/Users/example/.codex/skills/demo",
            "confirm_high_risk": True,
        },
    )

    assert response.status_code == 409
    assert "confirmation" in response.json()["detail"]
    assert confirmed.status_code == 201
