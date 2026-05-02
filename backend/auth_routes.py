"""
auth_routes.py — Minimal JWT-based authentication for the Interview Authenticity Portal.

Endpoints mounted at /auth:
  POST /auth/login          — validate credentials, return JWT
  GET  /auth/me             — return current user info from token
  GET  /auth/employees      — (admin only) list all HR employees
  POST /auth/employees      — (admin only) add a new HR employee
  DELETE /auth/employees/{username}  — (admin only) remove an HR employee

Passwords are stored as SHA-256 hashes in backend/users.json.
JWT secret is read from the JWT_SECRET env var (falls back to a dev default).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

USERS_FILE = Path(__file__).parent / "users.json"
JWT_SECRET  = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production")
JWT_ALGO    = "HS256"
TOKEN_TTL_H = 12   # hours

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: list[dict]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def _make_token(username: str, role: str, display_name: str) -> str:
    payload = {
        "sub":          username,
        "role":         role,
        "display_name": display_name,
        "exp":          datetime.now(tz=timezone.utc) + timedelta(hours=TOKEN_TTL_H),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    payload = _decode_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


def _require_admin(user: dict = Depends(_get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class AddEmployeeRequest(BaseModel):
    username:     str
    password:     str
    display_name: str = ""


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", summary="Authenticate and receive a JWT")
def login(req: LoginRequest):
    users = _load_users()
    user  = next((u for u in users if u["username"] == req.username), None)

    if user is None or user["password_hash"] != _hash(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = _make_token(
        username=user["username"],
        role=user["role"],
        display_name=user.get("display_name", user["username"]),
    )
    logger.info("[auth] login OK: %s (%s)", user["username"], user["role"])
    return {
        "token":        token,
        "username":     user["username"],
        "role":         user["role"],
        "display_name": user.get("display_name", user["username"]),
    }


@router.get("/me", summary="Return current user info from JWT")
def me(user: dict = Depends(_get_current_user)):
    return {
        "username":     user["sub"],
        "role":         user["role"],
        "display_name": user.get("display_name", user["sub"]),
    }


@router.get("/employees", summary="[Admin] List all HR employees")
def list_employees(admin: dict = Depends(_require_admin)):
    users = _load_users()
    return [
        {
            "username":     u["username"],
            "role":         u["role"],
            "display_name": u.get("display_name", u["username"]),
        }
        for u in users
        if u["role"] != "admin"
    ]


@router.post("/employees", summary="[Admin] Add a new HR employee", status_code=201)
def add_employee(req: AddEmployeeRequest, admin: dict = Depends(_require_admin)):
    users = _load_users()
    if any(u["username"] == req.username for u in users):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' already exists",
        )
    new_user = {
        "username":     req.username,
        "password_hash": _hash(req.password),
        "role":         "hr",
        "display_name": req.display_name or req.username,
    }
    users.append(new_user)
    _save_users(users)
    logger.info("[auth] admin added employee: %s", req.username)
    return {"created": True, "username": req.username}


@router.delete("/employees/{username}", summary="[Admin] Remove an HR employee")
def remove_employee(username: str, admin: dict = Depends(_require_admin)):
    users = _load_users()
    target = next((u for u in users if u["username"] == username), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )
    if target["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin account",
        )
    updated = [u for u in users if u["username"] != username]
    _save_users(updated)
    logger.info("[auth] admin removed employee: %s", username)
    return {"deleted": True, "username": username}
