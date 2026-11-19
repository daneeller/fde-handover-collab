"""权限分层：SaaS 管理员 + 分层用户（f22/f24/f41）。

令牌采用 HMAC 签名的无状态格式（`payload.signature`），
使云端多实例/多 worker 下任意请求都能独立验签，不依赖共享内存会话。
演示密钥固定；真实部署须替换为现有岗位账号体系与服务端密钥（f41：不借用他人账号）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set

# 权限点命名：<资源>:<动作>
PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {"*"},
    "inspector": {"defect:create", "defect:read", "locate:run", "knowledge:read"},
    "rectifier": {"defect:read", "locate:run", "review:write", "knowledge:read"},
    "auditor": {"defect:read", "audit:read", "knowledge:read", "harness:read"},
    "viewer": {"defect:read", "knowledge:read"},
}

ROLE_LABELS = {
    "admin": "租户管理员（SaaS）",
    "inspector": "现场验房员（林亦舟）",
    "rectifier": "整改项目专员（唐映秋）",
    "auditor": "工程质量经理（傅景）",
    "viewer": "客户 / 只读观察员",
}

_SECRET = b"handover-mvp-demo-secret"


def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


@dataclass(frozen=True)
class User:
    token: str
    name: str
    role: str
    label: str
    issued_at: float


class AuthStore:
    """无状态签名令牌；本地另存一份便于 Harness 自检。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, User] = {}

    def login(self, name: str, role: str) -> Optional[User]:
        if role not in PERMISSIONS:
            return None
        who = name.strip() or "未署名"
        issued = time.time()
        raw = json.dumps(
            {"n": who, "r": role, "t": issued},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        payload = base64.urlsafe_b64encode(raw).decode("ascii")
        token = payload + "." + _sign(payload)
        user = User(token=token, name=who, role=role,
                    label=ROLE_LABELS[role], issued_at=issued)
        self._sessions[token] = user
        return user

    def resolve(self, token: str) -> Optional[User]:
        try:
            payload, signature = token.split(".", 1)
            if not hmac.compare_digest(signature, _sign(payload)):
                return None
            data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
            role = data["r"]
            if role not in PERMISSIONS:
                return None
            return User(
                token=token,
                name=str(data.get("n", "未署名")),
                role=role,
                label=ROLE_LABELS[role],
                issued_at=float(data.get("t", 0)),
            )
        except Exception:
            return None

    @staticmethod
    def allows(user: User, permission: str) -> bool:
        granted = PERMISSIONS.get(user.role, set())
        return "*" in granted or permission in granted


auth_store = AuthStore()
