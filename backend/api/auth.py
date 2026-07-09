"""JWT tabanli kullanici dogrulama ve rol yonetimi."""

from __future__ import annotations

import os
import json
import hashlib
import hmac
import base64
import time
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def _auth_secret() -> str:
    return os.getenv('AUTH_SECRET', 'mcbu-dev-secret-degistirin')


def hash_password(password: str) -> str:
    secret = _auth_secret()
    return hashlib.sha256(f'{secret}:{password}'.encode()).hexdigest()


def verify_password(plain: str, stored: str) -> bool:
    if len(stored) == 64 and all(c in '0123456789abcdef' for c in stored.lower()):
        return hmac.compare_digest(hash_password(plain), stored)
    return hmac.compare_digest(plain, stored)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _jwt_encode(payload: dict) -> str:
    header = _b64url(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    body = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    msg = f'{header}.{body}'.encode()
    sig = hmac.new(_auth_secret().encode(), msg, hashlib.sha256).digest()
    return f'{header}.{body}.{_b64url(sig)}'


def _jwt_decode(token: str) -> dict:
    try:
        header, body, sig = token.split('.')
        msg = f'{header}.{body}'.encode()
        expected = _b64url(hmac.new(_auth_secret().encode(), msg, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError('bad signature')
        padded = body + '=' * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get('exp', 0) < time.time():
            raise ValueError('expired')
        return payload
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Gecersiz token') from e


def _load_users() -> dict[str, dict]:
    root = Path(__file__).resolve().parents[2]
    path = os.getenv('AUTH_USERS_FILE', str(root / 'config' / 'users.json'))
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return {u['username']: u for u in data.get('users', [])}
    return {
        'admin': {'username': 'admin', 'password': 'admin123', 'role': 'admin'},
        'viewer': {'username': 'viewer', 'password': 'viewer123', 'role': 'viewer'},
    }


def authenticate_user(username: str, password: str) -> dict | None:
    user = _load_users().get(username)
    if not user:
        return None
    stored = user.get('password_hash') or user.get('password', '')
    if not verify_password(password, stored):
        return None
    return {'username': username, 'role': user.get('role', 'viewer')}


def create_access_token(user: dict, hours: int | None = None) -> str:
    expire_hours = hours or int(os.getenv('AUTH_TOKEN_HOURS', 24))
    payload = {
        'sub': user['username'],
        'role': user['role'],
        'exp': int(time.time()) + expire_hours * 3600,
    }
    return _jwt_encode(payload)


def auth_enabled() -> bool:
    return os.getenv('AUTH_ENABLED', 'true').lower() == 'true'


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if not auth_enabled():
        return {'username': 'guest', 'role': 'admin'}
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Giris gerekli')
    data = _jwt_decode(credentials.credentials)
    return {'username': data['sub'], 'role': data.get('role', 'viewer')}


def require_role(*roles: str):
    async def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user['role'] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Yetki yok')
        return user
    return _checker
