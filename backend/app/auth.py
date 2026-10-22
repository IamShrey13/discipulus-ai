
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from dotenv import load_dotenv

load_dotenv()

_secret_key = os.getenv("JWT_SECRET_KEY")

if _secret_key is None or not _secret_key.strip():
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Add it to backend/.env."
    )

SECRET_KEY: str = _secret_key

ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


def create_access_token(user_id: int) -> str:
    """Create a signed JWT for an authenticated student."""
    now = datetime.now(timezone.utc)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return token
