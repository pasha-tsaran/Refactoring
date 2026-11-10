"""Regression tests for validation, SQL safety, contracts, and concurrency."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from user_api import create_app
from user_api.services import long_running_task
from user_api.utils import hash_password, is_admin, verify_password


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "users.db"))


@pytest.fixture
def client(app):
    return app.test_client()


def test_create_read_activate_and_alias(client):
    response = client.post("/adduser", json={"name": "  Анна  "})
    assert response.status_code == 201
    user = response.json
    assert user["name"] == "Анна" and user["tags"] == ["new"]
    uid = user["id"]
    assert client.get(f"/user/{uid}").json == {
        "id": uid,
        "name": "Анна",
        "tags": ["new"],
    }
    for method in (client.get, client.post):
        assert method(f"/activate/{uid}").json["active"] == [uid]
    assert client.post("/adducer", json={"name": "Legacy"}).status_code == 201
    assert client.get("/health").json == {"status": "ok"}


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"name": " "},
        {"name": 1},
        {"name": None},
        {"name": "x" * 101},
        {"name": "a\nb"},
        {"name": "ok", "tags": None},
        {"name": "ok", "tags": "bad"},
        {"name": "ok", "tags": [None]},
        {"name": "ok", "tags": [" "]},
        {"name": "ok", "tags": ["x" * 31]},
        {"name": "ok", "tags": ["a"] * 21},
        {"name": "ok", "role": "admin"},
    ],
)
def test_invalid_payload(client, payload):
    assert (
        client.post(
            "/adduser",
            data=json.dumps(payload),
            content_type="application/json",
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "uid", ["0", "-1", "abc", "1 OR 1=1", "9223372036854775808"]
)
def test_invalid_id(client, uid):
    assert client.get(f"/user/{uid}").status_code == 400


def test_http_errors_and_docs(client):
    assert client.post("/adduser", data="x").status_code == 415
    assert (
        client.post(
            "/adduser", data="{", content_type="application/json"
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/adduser", data="x" * 20_000, content_type="application/json"
        ).status_code
        == 413
    )
    for path in ("/user/999999", "/activate/999999", "/absent"):
        assert client.get(path).status_code == 404
    result = client.get("/adduser")
    assert result.status_code == 405 and "POST" in result.headers["Allow"]
    assert client.options("/adduser").status_code == 405
    assert client.get("/wrong").json == {
        "msg": "error",
        "detail": "division by zero",
    }
    assert client.get("/wrong").status_code == 500
    assert client.get("/slow").status_code == 202
    for path in ("/docs", "/openapi.json", "/openapi.yaml"):
        assert client.get(path).status_code == 200
    assert client.head("/health").data == b""


def test_sql_injection_tags_and_mutable_arguments(app, client):
    service = app.extensions["service"]
    tags = ["student"]
    name = "Robert'); DROP TABLE users; --"
    uid = service.add_user(name, tags)
    assert type(uid) is int and tags == ["student"]
    assert service.get_user_by_name(name).id == uid
    assert service.get_user_by_name("' OR 1=1 --") is None
    assert service.get_user_by_name("missing") is None
    assert client.get(f"/user/{uid}").json["tags"] == ["student", "new"]
    assert (
        client.post(
            "/adduser",
            json={
                "name": "20 tags",
                "tags": [str(i) for i in range(20)],
            },
        ).status_code
        == 201
    )


def test_concurrent_users_and_activity(app):
    service = app.extensions["service"]

    def add_and_activate(index):
        uid = service.add_user(f"User {index}")
        service.activate(uid)
        return uid

    with ThreadPoolExecutor(max_workers=10) as executor:
        ids = list(executor.map(add_and_activate, range(60)))
    assert len(set(ids)) == 60
    snapshot = service.activate(ids[0])
    assert len(snapshot) == 50 and len(set(snapshot)) == 50
    snapshot.clear()
    assert len(service.activate(ids[0])) == 50


def test_password_storage_and_fail_closed_roles(app):
    service = app.extensions["service"]
    uid = service.add_user("Password user")
    service.store_password(uid, "correct-password")
    with sqlite3.connect(service.repository.path) as connection:
        encoded = connection.execute(
            "SELECT password_hash FROM users WHERE id=?", (uid,)
        ).fetchone()[0]
    assert "correct-password" not in encoded
    assert verify_password("correct-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert hash_password("correct-password") != encoded
    for invalid in ("", "bad", "pbkdf2_sha256$999999999$x$x"):
        assert not verify_password("correct-password", invalid)
    assert is_admin({"role": "admin"})
    assert not any(is_admin(value) for value in (None, "admin", {}, 1))


def test_busy_scheduler(app, client):
    slots = app.extensions["tasks"]._slots
    slots.acquire()
    slots.acquire()
    try:
        response = client.get("/slow")
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
    finally:
        slots.release()
        slots.release()


def test_persistence(app):
    service = app.extensions["service"]
    uid = service.add_user("Persistent")
    reopened = create_app(service.repository.path)
    assert (
        reopened.test_client().get(f"/user/{uid}").json["name"] == "Persistent"
    )
    assert long_running_task(10) == 285
