from __future__ import annotations
from typing import Optional
import os
from datetime import timedelta, datetime as dt

import jwt
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer


User = get_user_model()


JWT_SECRET = os.getenv("ASTROAI_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = os.getenv("ASTROAI_JWT_ALG", "HS256")
JWT_EXP_MIN = int(os.getenv("ASTROAI_JWT_EXP_MIN", "60"))


def issue_jwt(user: object) -> str:
    payload = {
        "sub": str(user.id),
        "email": getattr(user, "email", ""),
        "exp": dt.utcnow() + timedelta(minutes=JWT_EXP_MIN),
        "iat": dt.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_jwt(token: str) -> Optional[object]:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        uid = int(data.get("sub"))
        return User.objects.get(id=uid)
    except Exception:
        return None


class JWTBearer(HttpBearer):
    def authenticate(self, request, token: str) -> Optional[object]:
        return verify_jwt(token)


# Export a default auth instance for convenience
auth = JWTBearer()
