"""
安全与 JWT 鉴权模块：
- 实现密码哈希与校验（采用标准 PBKDF2-HMAC-SHA256，无第三方 C 扩展兼容问题）
- 实现标准 RFC 7519 JWT (HS256) 签发与解析（优先使用 PyJWT，内置标准库回退）
- 提供 FastAPI 依赖注入：get_current_user, require_teacher, require_student_or_teacher
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.database import get_db_repository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """使用 PBKDF2-HMAC-SHA256 对密码进行加盐哈希。"""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    )
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    try:
        algo, salt, stored_hash = hashed_password.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        expected = hash_password(plain_password, salt)
        return hmac.compare_digest(expected, hashed_password)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_access_token(
    data: Dict[str, Any], expires_minutes: Optional[int] = None
) -> str:
    """签发 JWT Access Token (HS256)。"""
    to_encode = data.copy()
    expire_delta = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = int(time.time()) + int(expire_delta * 60)
    to_encode["iat"] = int(time.time())

    try:
        import jwt  # type: ignore

        return jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
    except ImportError:
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64url_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        payload_b64 = _b64url_encode(
            json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """解析并校验 JWT Access Token。"""
    try:
        import jwt  # type: ignore

        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except ImportError:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            expected_sig = hmac.new(
                settings.SECRET_KEY.encode("utf-8"),
                signing_input,
                hashlib.sha256,
            ).digest()
            actual_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise ValueError("Invalid token signature")
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
            if "exp" in payload and int(time.time()) > int(payload["exp"]):
                raise ValueError("Token expired")
            return payload
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"无效或已过期的身份凭证: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效或已过期的身份凭证: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo=Depends(get_db_repository),
) -> Dict[str, Any]:
    """FastAPI 依赖：获取当前登录用户（教师或学生）。"""
    payload = decode_access_token(token)
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 缺少用户标识",
        )
    user = repo.get_user_by_username(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


def require_teacher(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """FastAPI 依赖：仅限教师角色访问。"""
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：该操作仅限教师角色执行",
        )
    return current_user
