"""SQLite persistence with parameterized queries and bounded connections."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import NotFoundError, User


class UserRepository:
    """Open a separate connection for each operation and close it reliably."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL, tags TEXT NOT NULL, "
                "password_hash TEXT)"
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Commit on success, roll back on failure, and always close."""
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def ping(self) -> None:
        """Check that the configured database is available."""
        with self.connection() as connection:
            connection.execute("SELECT 1").fetchone()

    def add(self, name: str, tags: list[str]) -> User:
        """Insert a user and return the generated integer identifier."""
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users(name, tags) VALUES (?, ?)",
                (name, json.dumps(tags, ensure_ascii=False)),
            )
            return User(int(cursor.lastrowid), name, list(tags))

    def get(self, user_id: int) -> User:
        """Return a user or raise NotFoundError."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, tags FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("user not found")
        return User(row["id"], row["name"], json.loads(row["tags"]))

    def by_name(self, name: str) -> User | None:
        """Return the oldest matching user, or None when absent."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, tags FROM users WHERE name = ? "
                "ORDER BY id LIMIT 1",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return User(row["id"], row["name"], json.loads(row["tags"]))

    def store_password_hash(self, user_id: int, encoded: str) -> None:
        """Store only a password hash in the database, never in a text file."""
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (encoded, user_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("user not found")
