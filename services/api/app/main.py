from __future__ import annotations

import base64
import hashlib
import hmac
import json
import posixpath
import re
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from io import BytesIO
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi import Response
from pydantic import BaseModel, Field


app = FastAPI(title="AI WorkDock API", version="0.1.0")


@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    role: str
    status: str = "active"


@dataclass
class Prompt:
    id: str
    title: str
    content: str
    created_by: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    visibility: str = "team"
    status: str = "draft"
    usage_count: int = 0


@dataclass
class KnowledgeCard:
    id: str
    title: str
    card_type: str
    content: str
    created_by: str
    summary: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    related_prompt_ids: list[str] = field(default_factory=list)
    related_skill_ids: list[str] = field(default_factory=list)
    visibility: str = "team"
    status: str = "draft"
    version: int = 1
    favorite_count: int = 0


@dataclass
class Skill:
    id: str
    skill_id: str
    name: str
    description: str
    version: str
    risk_level: str
    status: str
    manifest: dict
    created_by: str
    rating: float | None = None


@dataclass
class AuditLog:
    id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SkillInstall:
    id: str
    skill_ref_id: str
    user_id: str
    version: str
    target_tool: str
    install_path: str
    status: str = "installed"


USERS: dict[str, User] = {
    "admin@workdock.local": User(
        id="u-admin",
        name="Admin",
        email="admin@workdock.local",
        password_hash="240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
        role="admin",
    ),
    "member@workdock.local": User(
        id="u-member",
        name="Member",
        email="member@workdock.local",
        password_hash="5600376e863d2f57a053518f324ad3840b0bc2348b573af281a7b7cbe7a228c6",
        role="member",
    ),
    "disabled@workdock.local": User(
        id="u-disabled",
        name="Disabled",
        email="disabled@workdock.local",
        password_hash="dde79399fb85ad1dfbaec103d360520c2590f9106832d830dff673eae18c39d9",
        role="member",
        status="disabled",
    ),
}
PROMPTS: dict[str, Prompt] = {}
KNOWLEDGE_CARDS: dict[str, KnowledgeCard] = {}
CARD_FAVORITES: set[tuple[str, str]] = set()
SKILLS: dict[str, Skill] = {}
AUDIT_LOGS: list[AuditLog] = []
SKILL_INSTALLS: dict[str, SkillInstall] = {}
SKILL_RATINGS: dict[tuple[str, str], int] = {}
REVOKED_TOKEN_IDS: set[str] = set()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PromptCreate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    visibility: str = "team"


class PromptUpdate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    visibility: str = "team"


class PromptReviewRequest(BaseModel):
    status: str


class KnowledgeCardCreate(BaseModel):
    title: str = Field(min_length=1)
    card_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    summary: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_prompt_ids: list[str] = Field(default_factory=list)
    related_skill_ids: list[str] = Field(default_factory=list)
    visibility: str = "team"


class SkillReviewRequest(BaseModel):
    status: str


class SkillInstallRequest(BaseModel):
    target_tool: str
    install_path: str
    confirm_high_risk: bool = False


class SkillRateRequest(BaseModel):
    score: int = Field(ge=1, le=5)


TOKEN_SECRET = b"ai-workdock-local-dev-secret"
MAX_SKILL_UPLOAD_BYTES = 5 * 1024 * 1024


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_token(user: User, token_type: str = "access", ttl_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.email,
        "role": user.role,
        "type": token_type,
        "exp": int(time.time()) + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }
    signing_input = ".".join(
        [
            b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(TOKEN_SECRET, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def decode_token(token: str, expected_type: str = "access") -> dict | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    signing_input = ".".join(parts[:2])
    expected_signature = b64url(hmac.new(TOKEN_SECRET, signing_input.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(parts[2], expected_signature):
        return None
    try:
        payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None
    if payload.get("type") != expected_type or int(payload.get("exp", 0)) < int(time.time()):
        return None
    if payload.get("jti") in REVOKED_TOKEN_IDS:
        return None
    return payload


def user_from_token(token: str, expected_type: str = "access") -> User | None:
    payload = decode_token(token, expected_type)
    if payload is None:
        return None
    return USERS.get(payload.get("sub", ""))


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    user = user_from_token(authorization.removeprefix("Bearer ").strip())
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def current_token_payload(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(authorization.removeprefix("Bearer ").strip(), expected_type="access")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def add_audit(actor: User, action: str, target_type: str, target_id: str, metadata: dict | None = None) -> None:
    AUDIT_LOGS.append(
        AuditLog(
            id=str(uuid.uuid4()),
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )
    )


def public_prompt(prompt: Prompt, user: User) -> bool:
    if prompt.visibility == "private":
        return prompt.created_by == user.id
    return prompt.status == "published" or prompt.created_by == user.id or user.role == "admin"


def public_skill(skill: Skill, user: User) -> bool:
    return skill.status == "published" or skill.created_by == user.id or user.role == "admin"


def public_card(card: KnowledgeCard, user: User) -> bool:
    if card.visibility == "private":
        return card.created_by == user.id
    return card.status == "published" or card.created_by == user.id or user.role == "admin"


def prompt_matches(prompt: Prompt, query: str | None) -> bool:
    if not query:
        return True
    haystack = " ".join([prompt.title, prompt.content, *(prompt.tags or [])]).lower()
    return query.lower() in haystack


def prompt_has_tag(prompt: Prompt, tag: str | None) -> bool:
    if not tag:
        return True
    return tag.lower() in [item.lower() for item in prompt.tags]


def assert_safe_zip_names(names: list[str]) -> None:
    for name in names:
        normalized = posixpath.normpath(name.replace("\\", "/"))
        if normalized.startswith("../") or normalized == ".." or posixpath.isabs(normalized):
            raise HTTPException(status_code=400, detail="Zip package contains unsafe path")


def parse_skill_frontmatter(skill_md: str) -> dict[str, str]:
    if not skill_md.startswith("---"):
        return {}
    match = re.match(r"---\s*\n(.*?)\n---", skill_md, re.DOTALL)
    if not match:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata


SENSITIVE_SCRIPT_PATTERNS = [
    r"rm\s+-rf",
    r"curl\b.*\|\s*bash",
    r"wget\b.*\|\s*sh",
    r"\.ssh",
    r"cookie",
    r"token",
    r"browser user",
    r"upload\b.*\bfile",
]


def assert_scripts_are_safe(archive: zipfile.ZipFile, names: list[str]) -> None:
    script_names = [
        name
        for name in names
        if "/scripts/" in name.replace("\\", "/") or name.replace("\\", "/").startswith("scripts/")
    ]
    for name in script_names:
        try:
            content = archive.read(name).decode("utf-8", errors="ignore").lower()
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Skill script could not be read") from exc
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in SENSITIVE_SCRIPT_PATTERNS):
            raise HTTPException(status_code=400, detail="Skill script contains sensitive command")


def parse_skill_package(data: bytes) -> dict:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip package") from exc

    names = archive.namelist()
    assert_safe_zip_names(names)
    assert_scripts_are_safe(archive, names)

    skill_md_names = [name for name in names if name.replace("\\", "/").endswith("/SKILL.md") or name == "SKILL.md"]
    if not skill_md_names:
        raise HTTPException(status_code=400, detail="Skill package must contain SKILL.md")

    skill_md = archive.read(skill_md_names[0]).decode("utf-8")
    metadata = parse_skill_frontmatter(skill_md)
    if not metadata.get("name"):
        raise HTTPException(status_code=400, detail="SKILL.md must contain name")
    if not metadata.get("description"):
        raise HTTPException(status_code=400, detail="SKILL.md must contain description")

    manifest: dict = {}
    skill_json_names = [name for name in names if name.replace("\\", "/").endswith("/skill.json") or name == "skill.json"]
    if skill_json_names:
        try:
            manifest = json.loads(archive.read(skill_json_names[0]).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="skill.json is not valid JSON") from exc

    normalized_names = [name.replace("\\", "/") for name in names]
    has_scripts = any("/scripts/" in name or name.startswith("scripts/") for name in normalized_names)
    return {
        "skill_id": manifest.get("skill_id") or metadata["name"],
        "name": manifest.get("name") or metadata["name"],
        "description": manifest.get("description") or metadata["description"],
        "version": manifest.get("version") or "0.1.0",
        "risk_level": "high" if has_scripts else "low",
        "manifest": manifest,
    }


def parse_single_multipart_file(body: bytes, content_type: str | None) -> bytes:
    if not content_type or "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Expected multipart upload")

    boundary_marker = "boundary="
    if boundary_marker not in content_type:
        raise HTTPException(status_code=400, detail="Multipart boundary missing")
    boundary = content_type.split(boundary_marker, 1)[1].split(";", 1)[0].strip().strip('"')
    delimiter = f"--{boundary}".encode()

    for part in body.split(delimiter):
        if b'Content-Disposition:' not in part or b'name="file"' not in part:
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            raise HTTPException(status_code=400, detail="Malformed multipart upload")
        file_data = part[header_end + 4 :]
        return file_data.rstrip(b"\r\n-")

    raise HTTPException(status_code=400, detail="Upload must include file")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = USERS.get(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash) or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_token(user, token_type="access", ttl_seconds=3600),
        refresh_token=create_token(user, token_type="refresh", ttl_seconds=86400),
    )


@app.post("/api/auth/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest) -> TokenResponse:
    user = user_from_token(payload.refresh_token, expected_type="refresh")
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return TokenResponse(access_token=create_token(user, token_type="access", ttl_seconds=3600))


@app.post("/api/auth/logout", status_code=204)
def logout(payload: Annotated[dict, Depends(current_token_payload)]) -> Response:
    REVOKED_TOKEN_IDS.add(payload["jti"])
    return Response(status_code=204)


@app.get("/api/auth/me")
def me(user: Annotated[User, Depends(current_user)]) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@app.post("/api/prompts", status_code=201)
def create_prompt(payload: PromptCreate, user: Annotated[User, Depends(current_user)]) -> dict:
    prompt = Prompt(
        id=str(uuid.uuid4()),
        title=payload.title,
        description=payload.description,
        content=payload.content,
        category=payload.category,
        tags=payload.tags,
        visibility=payload.visibility,
        created_by=user.id,
        status="published" if user.role == "admin" else "pending",
    )
    PROMPTS[prompt.id] = prompt
    return asdict(prompt)


@app.get("/api/prompts")
def list_prompts(
    user: Annotated[User, Depends(current_user)],
    q: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    return [
        asdict(prompt)
        for prompt in PROMPTS.values()
        if public_prompt(prompt, user) and prompt_matches(prompt, q) and prompt_has_tag(prompt, tag)
    ]


@app.get("/api/prompts/{prompt_id}")
def get_prompt(prompt_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    prompt = PROMPTS.get(prompt_id)
    if prompt is None or not public_prompt(prompt, user):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return asdict(prompt)


@app.put("/api/prompts/{prompt_id}")
def update_prompt(prompt_id: str, payload: PromptUpdate, user: Annotated[User, Depends(current_user)]) -> dict:
    prompt = PROMPTS.get(prompt_id)
    if prompt is None or not public_prompt(prompt, user):
        raise HTTPException(status_code=404, detail="Prompt not found")
    if user.role != "admin" and prompt.created_by != user.id:
        raise HTTPException(status_code=403, detail="Cannot update this prompt")
    prompt.title = payload.title
    prompt.description = payload.description
    prompt.content = payload.content
    prompt.category = payload.category
    prompt.tags = payload.tags
    prompt.visibility = payload.visibility
    add_audit(user, "prompt.update", "prompt", prompt.id)
    return asdict(prompt)


@app.post("/api/prompts/{prompt_id}/copy")
def copy_prompt(prompt_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    prompt = PROMPTS.get(prompt_id)
    if prompt is None or not public_prompt(prompt, user):
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.usage_count += 1
    return {"content": prompt.content, "usage_count": prompt.usage_count}


@app.post("/api/prompts/{prompt_id}/review")
def review_prompt(
    prompt_id: str,
    payload: PromptReviewRequest,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    prompt = PROMPTS.get(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if payload.status not in {"published", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="Unsupported status")
    prompt.status = payload.status
    add_audit(admin, "prompt.review", "prompt", prompt.id, {"status": payload.status})
    return asdict(prompt)


@app.delete("/api/prompts/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: str, user: Annotated[User, Depends(current_user)]) -> Response:
    prompt = PROMPTS.get(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if user.role != "admin" and prompt.created_by != user.id:
        raise HTTPException(status_code=403, detail="Cannot delete this prompt")
    del PROMPTS[prompt_id]
    add_audit(user, "prompt.delete", "prompt", prompt_id)
    return Response(status_code=204)


@app.post("/api/cards", status_code=201)
def create_knowledge_card(
    payload: KnowledgeCardCreate,
    user: Annotated[User, Depends(current_user)],
) -> dict:
    card = KnowledgeCard(
        id=str(uuid.uuid4()),
        title=payload.title,
        card_type=payload.card_type,
        summary=payload.summary,
        content=payload.content,
        category=payload.category,
        tags=payload.tags,
        related_prompt_ids=payload.related_prompt_ids,
        related_skill_ids=payload.related_skill_ids,
        visibility=payload.visibility,
        created_by=user.id,
    )
    KNOWLEDGE_CARDS[card.id] = card
    return asdict(card)


@app.get("/api/cards")
def list_knowledge_cards(user: Annotated[User, Depends(current_user)]) -> list[dict]:
    return [asdict(card) for card in KNOWLEDGE_CARDS.values() if public_card(card, user)]


@app.post("/api/cards/{card_id}/publish")
def publish_knowledge_card(card_id: str, admin: Annotated[User, Depends(require_admin)]) -> dict:
    card = KNOWLEDGE_CARDS.get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Knowledge card not found")
    card.status = "published"
    add_audit(admin, "card.publish", "knowledge_card", card.id)
    return asdict(card)


@app.post("/api/cards/{card_id}/favorite")
def favorite_knowledge_card(card_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    card = KNOWLEDGE_CARDS.get(card_id)
    if card is None or not public_card(card, user):
        raise HTTPException(status_code=404, detail="Knowledge card not found")
    favorite_key = (card.id, user.id)
    if favorite_key not in CARD_FAVORITES:
        CARD_FAVORITES.add(favorite_key)
        card.favorite_count += 1
    return asdict(card)


@app.post("/api/skills/upload", status_code=201)
async def upload_skill(
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> dict:
    body = await request.body()
    if len(body) > MAX_SKILL_UPLOAD_BYTES + 4096:
        raise HTTPException(status_code=413, detail="Skill package is too large")
    uploaded = parse_single_multipart_file(body, request.headers.get("content-type"))
    if len(uploaded) > MAX_SKILL_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Skill package is too large")
    parsed = parse_skill_package(uploaded)
    skill = Skill(
        id=str(uuid.uuid4()),
        skill_id=parsed["skill_id"],
        name=parsed["name"],
        description=parsed["description"],
        version=parsed["version"],
        risk_level=parsed["risk_level"],
        status="pending",
        manifest=parsed["manifest"],
        created_by=user.id,
    )
    SKILLS[skill.id] = skill
    add_audit(user, "skill.upload", "skill", skill.id, {"risk_level": skill.risk_level})
    return asdict(skill)


@app.get("/api/skills")
def list_skills(user: Annotated[User, Depends(current_user)]) -> list[dict]:
    return [asdict(skill) for skill in SKILLS.values() if public_skill(skill, user)]


@app.get("/api/skills/installed")
def list_installed_skills(user: Annotated[User, Depends(current_user)]) -> list[dict]:
    return [
        asdict(install)
        for install in SKILL_INSTALLS.values()
        if install.user_id == user.id and install.status == "installed"
    ]


@app.get("/api/skills/{skill_id}")
def get_skill(skill_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    skill = SKILLS.get(skill_id)
    if skill is None or not public_skill(skill, user):
        raise HTTPException(status_code=404, detail="Skill not found")
    return asdict(skill)


@app.post("/api/skills/{skill_id}/review")
def review_skill(
    skill_id: str,
    payload: SkillReviewRequest,
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    skill = SKILLS.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if payload.status not in {"published", "archived", "pending"}:
        raise HTTPException(status_code=400, detail="Unsupported status")
    skill.status = payload.status
    add_audit(admin, "skill.review", "skill", skill.id, {"status": payload.status})
    return asdict(skill)


@app.post("/api/skills/{skill_id}/install", status_code=201)
def install_skill(
    skill_id: str,
    payload: SkillInstallRequest,
    user: Annotated[User, Depends(current_user)],
) -> dict:
    skill = SKILLS.get(skill_id)
    if skill is None or skill.status != "published":
        raise HTTPException(status_code=404, detail="Published Skill not found")
    if skill.risk_level == "high" and not payload.confirm_high_risk:
        raise HTTPException(status_code=409, detail="High risk Skill requires installation confirmation")
    for existing in SKILL_INSTALLS.values():
        if existing.user_id == user.id and existing.skill_ref_id == skill.id and existing.version == skill.version:
            raise HTTPException(status_code=409, detail="Skill version already installed")
    install = SkillInstall(
        id=str(uuid.uuid4()),
        skill_ref_id=skill.id,
        user_id=user.id,
        version=skill.version,
        target_tool=payload.target_tool,
        install_path=payload.install_path,
    )
    SKILL_INSTALLS[install.id] = install
    add_audit(user, "skill.install", "skill", skill.id, {"install_id": install.id})
    return asdict(install)


@app.post("/api/skills/{skill_id}/uninstall")
def uninstall_skill(skill_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    skill = SKILLS.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    for install in SKILL_INSTALLS.values():
        if install.user_id == user.id and install.skill_ref_id == skill.id and install.status == "installed":
            install.status = "removed"
            add_audit(user, "skill.uninstall", "skill", skill.id, {"install_id": install.id})
            return asdict(install)
    raise HTTPException(status_code=404, detail="Installed Skill not found")


@app.post("/api/skills/{skill_id}/update")
def update_installed_skill(skill_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    target_skill = SKILLS.get(skill_id)
    if target_skill is None or target_skill.status != "published":
        raise HTTPException(status_code=404, detail="Published Skill not found")
    for install in SKILL_INSTALLS.values():
        installed_skill = SKILLS.get(install.skill_ref_id)
        if (
            install.user_id == user.id
            and install.status == "installed"
            and installed_skill is not None
            and installed_skill.skill_id == target_skill.skill_id
        ):
            if install.version == target_skill.version:
                raise HTTPException(status_code=409, detail="Skill version already installed")
            install.skill_ref_id = target_skill.id
            install.version = target_skill.version
            add_audit(user, "skill.update", "skill", target_skill.id, {"install_id": install.id})
            return asdict(install)
    raise HTTPException(status_code=404, detail="Installed Skill not found")


@app.post("/api/skills/{skill_id}/rollback")
def rollback_installed_skill(skill_id: str, user: Annotated[User, Depends(current_user)]) -> dict:
    target_skill = SKILLS.get(skill_id)
    if target_skill is None or target_skill.status != "published":
        raise HTTPException(status_code=404, detail="Published Skill not found")
    for install in SKILL_INSTALLS.values():
        installed_skill = SKILLS.get(install.skill_ref_id)
        if (
            install.user_id == user.id
            and install.status == "installed"
            and installed_skill is not None
            and installed_skill.skill_id == target_skill.skill_id
        ):
            if install.version == target_skill.version:
                raise HTTPException(status_code=409, detail="Skill version already installed")
            install.skill_ref_id = target_skill.id
            install.version = target_skill.version
            add_audit(user, "skill.rollback", "skill", target_skill.id, {"install_id": install.id})
            return asdict(install)
    raise HTTPException(status_code=404, detail="Installed Skill not found")


@app.post("/api/skills/{skill_id}/rate")
def rate_skill(
    skill_id: str,
    payload: SkillRateRequest,
    user: Annotated[User, Depends(current_user)],
) -> dict:
    skill = SKILLS.get(skill_id)
    if skill is None or skill.status != "published":
        raise HTTPException(status_code=404, detail="Published Skill not found")
    SKILL_RATINGS[(skill.id, user.id)] = payload.score
    scores = [score for (rated_skill_id, _), score in SKILL_RATINGS.items() if rated_skill_id == skill.id]
    skill.rating = round(sum(scores) / len(scores), 1)
    return asdict(skill)


@app.get("/api/audit-logs")
def list_audit_logs(admin: Annotated[User, Depends(require_admin)]) -> list[dict]:
    return [asdict(log) for log in AUDIT_LOGS]
