import re
import bcrypt

# Bcrypt has a HARD 72-byte limit. We truncate defensively (never splitting
# a multi-byte UTF-8 char) so a long input can never crash the endpoint.
#
# NOTE: we use bcrypt DIRECTLY here instead of passlib. Passlib 1.7.4 (its
# latest release, unmaintained since 2020) is incompatible with bcrypt 4.x:
# passlib's internal backend-initialization probe hashes a >72-byte test
# string, and bcrypt 4.x now raises on that instead of silently truncating —
# so the FIRST call to hash_password() crashes for ANY input, even a short
# password. Using bcrypt directly sidesteps this entirely.
_BCRYPT_MAX_BYTES = 72


def _safe_password(password: str) -> bytes:
    """Encode to bytes, truncating to 72 bytes without splitting a UTF-8 char."""
    encoded = password.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return encoded
    # Slice on bytes, then re-encode ignoring any partial multi-byte character.
    return encoded[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore").encode("utf-8")


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_safe_password(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_safe_password(password), password_hash.encode("utf-8"))
    except Exception:
        # Corrupt/unrecognized hash in the DB → treat as failed login, not a 500.
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")