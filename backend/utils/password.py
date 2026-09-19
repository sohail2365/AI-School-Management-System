import re
from passlib.context import CryptContext

# Bcrypt has a HARD 72-byte limit on passwords. Newer passlib/backend versions
# RAISE an error instead of silently truncating (old behavior) — this was
# breaking login for users whose browser/password-manager sent a long string.
# We truncate defensively in both hash and verify paths so a single overly-long
# input can never 500 the login endpoint.
_BCRYPT_MAX_BYTES = 72

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _safe_password(password: str) -> str:
    """
    Truncate a password to bcrypt's 72-byte limit without splitting a
    multi-byte UTF-8 character in half (which would corrupt the string).
    """
    encoded = password.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return password
    # Slice on bytes, then decode ignoring any partial multi-byte character.
    return encoded[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_safe_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(_safe_password(password), password_hash)
    except Exception:
        # Corrupt / unrecognized hash in the DB — treat as a failed login,
        # never a 500. Old records could be in a format this passlib version
        # doesn't recognize, and one bad row must not crash the endpoint.
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")