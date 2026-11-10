"""HTTP routes; business logic and persistence live in separate modules."""

from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest

from .models import parse_id
from .services import BackgroundTasks, UserService


def create_routes(service: UserService, tasks: BackgroundTasks) -> Blueprint:
    """Build routes with dependencies supplied by the application factory."""
    routes = Blueprint("api", __name__)

    @routes.get("/health")
    def health():
        service.repository.ping()
        return jsonify(status="ok")

    @routes.post("/adduser")
    @routes.post("/adducer")
    def add_user():
        if request.mimetype != "application/json":
            return jsonify(error="unsupported_media_type"), 415
        try:
            payload = request.get_json()
        except BadRequest:
            return jsonify(error="invalid_json"), 400
        user = service.create(payload)
        return jsonify(status="ok", **asdict(user)), 201

    @routes.get("/user/<uid>")
    def get_user(uid: str):
        return jsonify(asdict(service.repository.get(parse_id(uid))))

    @routes.route("/activate/<uid>", methods=["GET", "POST"])
    def activate(uid: str):
        return jsonify(status="ok", active=service.activate(parse_id(uid)))

    @routes.get("/slow")
    def slow():
        if not tasks.schedule():
            response = jsonify(error="busy")
            response.headers["Retry-After"] = "1"
            return response, 503
        return jsonify(status="scheduled"), 202

    @routes.get("/wrong")
    def wrong():
        return jsonify(msg="error", detail="division by zero"), 500

    api_path = Path(__file__).resolve().parents[2] / "go_server" / "api"

    @routes.get("/openapi.json")
    def openapi_json():
        return Response(
            (api_path / "openapi.json").read_bytes(),
            content_type="application/json",
        )

    @routes.get("/openapi.yaml")
    def openapi_yaml():
        return Response(
            (api_path / "openapi.yaml").read_bytes(),
            content_type="application/yaml",
        )

    @routes.get("/docs")
    def docs():
        return Response(
            (api_path / "docs.html").read_bytes(), content_type="text/html"
        )

    return routes
