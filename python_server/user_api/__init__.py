"""Factory for the refactored Flask implementation."""

import os
import sqlite3

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .models import NotFoundError
from .repository import UserRepository
from .routes import create_routes
from .services import BackgroundTasks, UserService


def create_app(database_path: str | None = None) -> Flask:
    """Create independent application state without a global connection."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16_384
    app.config["PROVIDE_AUTOMATIC_OPTIONS"] = False
    repository = UserRepository(
        database_path or os.getenv("DB_PATH", "data/python-users.db")
    )
    service = UserService(repository)
    tasks = BackgroundTasks()
    app.extensions.update(service=service, tasks=tasks)
    app.register_blueprint(create_routes(service, tasks))

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error="invalid_input", detail=str(error)), 400

    @app.errorhandler(NotFoundError)
    def not_found(error):
        return jsonify(error="not_found"), 404

    @app.errorhandler(HTTPException)
    def http_error(error):
        codes = {
            404: "not_found",
            405: "method_not_allowed",
            413: "body_too_large",
            415: "unsupported_media_type",
        }
        response = error.get_response()
        response.data = app.json.dumps(
            {"error": codes.get(error.code, "invalid_request")}
        )
        response.content_type = "application/json"
        return response

    @app.errorhandler(sqlite3.Error)
    @app.errorhandler(Exception)
    def internal_error(error):
        app.logger.exception("request failed")
        return jsonify(error="internal_error"), 500

    return app
