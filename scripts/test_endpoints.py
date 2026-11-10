"""Smoke-test every endpoint using only the Python standard library."""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(
    base: str, method: str, path: str, expected: int, payload: object = None
) -> object:
    """Assert HTTP status and decode JSON when available."""
    body = None if payload is None else json.dumps(payload).encode()
    headers = {} if body is None else {"Content-Type": "application/json"}
    req = Request(base + path, data=body, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        status = response.status
        if status != expected:
            raise RuntimeError(
                f"{method} {path}: expected {expected}, got {status}: "
                f"{content[:200]!r}"
            )
        print(f"OK {method:4} {path:35} {status}")
        if "json" in response.headers.get("Content-Type", ""):
            return json.loads(content)
        return content.decode("utf-8")


def main() -> int:
    """Create two smoke users and check positive and negative responses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    try:
        request(base, "GET", "/health", 200)
        name = f"Smoke O'Brien {time.time_ns()}"
        user = request(
            base, "POST", "/adduser", 201, {"name": name, "tags": ["smoke"]}
        )
        assert isinstance(user["id"], int) and user["name"] == name
        assert user["tags"] == ["smoke", "new"]
        uid = user["id"]
        assert request(base, "GET", f"/user/{uid}", 200)["name"] == name
        for method in ("GET", "POST"):
            active = request(base, method, f"/activate/{uid}", 200)["active"]
            assert active.count(uid) == 1
        request(base, "POST", "/adducer", 201, {"name": "Legacy smoke"})
        request(base, "GET", "/slow", 202)
        request(base, "GET", "/wrong", 500)
        contract = request(base, "GET", "/openapi.json", 200)
        assert contract["openapi"] == "3.1.0"
        request(base, "GET", "/openapi.yaml", 200)
        request(base, "GET", "/docs", 200)
        request(base, "POST", "/adduser", 400, {"name": " "})
        request(base, "POST", "/adduser", 400, {"name": 123})
        request(base, "GET", "/user/9223372036854775807", 404)
        request(base, "POST", "/activate/9223372036854775807", 404)
        request(base, "GET", "/user/1%20OR%201=1", 400)
        request(base, "GET", "/adduser", 405)
        request(base, "GET", "/absent", 404)
        print("All endpoint checks passed. Two smoke users remain in the DB.")
        return 0
    except (RuntimeError, AssertionError, URLError, TimeoutError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
