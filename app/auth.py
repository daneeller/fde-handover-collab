"""权限分层：SaaS 管理员 + 分层用户（f22/f24/f41）。

演示用内存令牌；真实部署须替换为现有岗位账号体系（f41：不借用他人账号）。
"""
from __future__ import annotations

import time
import uuid
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


@dataclass(frozen=True)
class User:
    token: str
    name: str
    role: str
    label: str
    issued_at: float


class AuthStore:
    """内存会话表。重启即失效，符合"演示环境"定位。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, User] = {}

    def login(self, name: str, role: str) -> Optional[User]:
        if role not in PERMISSIONS:
            return None
        user = User(
            token=uuid.uuid4().hex,
            name=name.strip() or "未署名",
            role=role,
            label=ROLE_LABELS[role],
            issued_at=time.time(),
        )
        self._sessions[user.token] = user
        return user

    def resolve(self, token: str) -> Optional[User]:
        return self._sessions.get(token)

    @staticmethod
    def allows(user: User, permission: str) -> bool:
        granted = PERMISSIONS.get(user.role, set())
        return "*" in granted or permission in granted


auth_store = AuthStore()
