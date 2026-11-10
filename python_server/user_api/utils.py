"""Password utilities and explicit, fail-closed role checks."""

import hashlib
import hmac
import secrets

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Create a versioned PBKDF2-SHA256 hash with a random 16-byte salt."""
    if (
        not isinstance(password, str)
        or not 8 <= len(password.encode()) <= 1024
    ):
        raise ValueError("password must contain 8 to 1024 UTF-8 bytes")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify the supported format with constant-time digest comparison."""
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != ITERATIONS:
            return False
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        if len(salt) != 16 or len(expected) != 32:
            return False
        if not 8 <= len(password.encode()) <= 1024:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, ITERATIONS
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def is_admin(user: object) -> bool:
    """Check a trusted role object; this helper does not authenticate users."""
    return isinstance(user, dict) and user.get("role") == "admin"
