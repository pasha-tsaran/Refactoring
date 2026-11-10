"""Domain objects and validation independent of HTTP and storage."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    """Public user data; password hashes never belong in this model."""

    id: int
    name: str
    tags: list[str]


class NotFoundError(Exception):
    """The requested user does not exist."""


def validate_user(payload: object) -> tuple[str, list[str]]:
    """Validate input and return a fresh list containing the new-user tag."""
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")
    if set(payload) - {"name", "tags"}:
        raise ValueError("unknown fields")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("name must contain 1 to 100 characters")
    if any(ord(char) < 32 for char in name):
        raise ValueError("name must not contain control characters")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or len(tags) > 20:
        raise ValueError("tags must be an array of at most 20 strings")
    if any(
        not isinstance(tag, str)
        or not tag.strip()
        or len(tag) > 30
        or any(ord(char) < 32 for char in tag)
        for tag in tags
    ):
        raise ValueError("each tag must contain 1 to 30 characters")
    result = list(dict.fromkeys(tag.strip() for tag in tags))
    if "new" not in result:
        result.append("new")
    return name.strip(), result


def parse_id(value: str) -> int:
    """Accept only positive decimal signed-64-bit identifiers."""
    if not value.isascii() or not value.isdecimal():
        raise ValueError("id must be a positive integer")
    number = int(value)
    if not 1 <= number <= 2**63 - 1:
        raise ValueError("id must be a positive 64-bit integer")
    return number
