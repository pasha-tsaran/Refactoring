"""User operations, synchronized activity, and bounded background work."""

import logging
from threading import BoundedSemaphore, Lock, Thread

from .models import User, validate_user
from .repository import UserRepository
from .utils import hash_password


class ActiveUsers:
    """Keep the last 50 unique activated IDs, most recent last."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._users: list[int] = []

    def set_active(self, user_id: int) -> list[int]:
        """Update and return an independent snapshot under the same lock."""
        with self._lock:
            if user_id in self._users:
                self._users.remove(user_id)
            self._users.append(user_id)
            self._users = self._users[-50:]
            return list(self._users)


def long_running_task(n: int = 100_000) -> int:
    """Calculate sum(i*i for i in range(n)) without sleeping."""
    if not 0 <= n <= 100_000:
        raise ValueError("n must be between 0 and 100000")
    return sum(i * i for i in range(n))


class BackgroundTasks:
    """Run at most two short demo jobs; refuse excess work immediately."""

    def __init__(self) -> None:
        self._slots = BoundedSemaphore(2)

    def schedule(self) -> bool:
        """Return False if both workers are busy."""
        if not self._slots.acquire(blocking=False):
            return False

        def worker() -> None:
            try:
                long_running_task()
            except Exception:
                logging.exception("background task failed")
            finally:
                self._slots.release()

        Thread(target=worker, daemon=True).start()
        return True


class UserService:
    """Share business rules between the API and direct utility callers."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository
        self.active = ActiveUsers()

    def add_user(self, name: str, tags: list[str] | None = None) -> int:
        """Add a user without modifying the caller's tags; return an int."""
        payload = {"name": name, "tags": tags if tags is not None else []}
        return self.create(payload).id

    def create(self, payload: object) -> User:
        """Validate and persist a user."""
        name, tags = validate_user(payload)
        return self.repository.add(name, tags)

    def activate(self, user_id: int) -> list[int]:
        """Activate only an existing user."""
        self.repository.get(user_id)
        return self.active.set_active(user_id)

    def get_user_by_name(self, name: str) -> User | None:
        """Find the oldest user with an exact name match."""
        return self.repository.by_name(name)

    def store_password(self, user_id: int, password: str) -> None:
        """Hash and store the password for an existing user."""
        self.repository.get(user_id)
        self.repository.store_password_hash(user_id, hash_password(password))
