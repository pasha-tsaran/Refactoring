"""Generate the YAML and JSON contract from one source. Run from any folder."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "go_server" / "api"


def ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def response(description: str, schema: dict) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": schema}},
    }


def operation(title: str, operation_id: str, responses: dict) -> dict:
    result = {
        "summary": title,
        "operationId": operation_id,
        "responses": dict(responses),
    }
    for code in ("405", "500"):
        result["responses"].setdefault(
            code, response("Ошибка запроса или сервера", ref("Error"))
        )
    return result


def build_spec() -> dict:
    identifier = {
        "type": "integer",
        "format": "int64",
        "minimum": 1,
        "maximum": 9223372036854775807,
    }
    text = {
        "type": "string",
        "minLength": 1,
        "maxLength": 100,
        "pattern": r"^[^\u0000-\u001f]*\S[^\u0000-\u001f]*$",
    }
    tag = {**text, "maxLength": 30}
    tags = {"type": "array", "maxItems": 21, "items": tag}
    user = {
        "type": "object",
        "required": ["id", "name", "tags"],
        "additionalProperties": False,
        "properties": {"id": identifier, "name": text, "tags": tags},
    }
    create = operation(
        "Создать пользователя",
        "addUser",
        {
            "201": response("Пользователь создан", ref("AddUserResponse")),
            **{
                str(code): response("Некорректный запрос", ref("Error"))
                for code in (400, 413, 415)
            },
        },
    )
    create["requestBody"] = {
        "required": True,
        "content": {
            "application/json": {
                "schema": ref("AddUserRequest"),
                "example": {"name": "Анна", "tags": ["student"]},
            }
        },
    }
    alias = {
        **create,
        "operationId": "addUserLegacy",
        "deprecated": True,
        "summary": "Совместимость с опечаткой в исходном API",
    }
    path_parameter = {
        "name": "id",
        "in": "path",
        "required": True,
        "schema": identifier,
    }
    find = operation(
        "Получить пользователя",
        "getUser",
        {
            "200": response("Пользователь", ref("User")),
            "400": response("Некорректный ID", ref("Error")),
            "404": response("Пользователь отсутствует", ref("Error")),
        },
    )
    activate = operation(
        "Активировать пользователя",
        "activateUser",
        {
            "200": response("Активность обновлена", ref("ActivateResponse")),
            "400": response("Некорректный ID", ref("Error")),
            "404": response("Пользователь отсутствует", ref("Error")),
        },
    )
    slow = operation(
        "Запустить фоновую задачу",
        "runSlowTask",
        {
            "202": response(
                "Задача принята без гарантии завершения",
                ref("ScheduledResponse"),
            ),
            "503": {
                **response("Оба исполнителя заняты", ref("Error")),
                "headers": {
                    "Retry-After": {
                        "schema": {"type": "string", "const": "1"},
                        "description": "Повторите запрос через секунду",
                    }
                },
            },
        },
    )
    wrong = operation(
        "Учебный пример ответа 500",
        "wrongExample",
        {
            "500": response("Ожидаемая учебная ошибка", ref("DemoError")),
        },
    )
    spec = {
        "openapi": "3.1.0",
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {
            "title": "Refactoring User API",
            "version": "1.0.0",
            "description": (
                "Учебный API без авторизации. Активность хранится в памяти "
                "процесса, до 50 уникальных ID. Пользователи сохраняются "
                "в SQLite. GET /activate меняет состояние для совместимости; "
                "предпочитайте POST. Неизвестный путь: 404 JSON Error. "
                "Неподдерживаемый метод: 405 JSON Error и заголовок Allow. "
                "Для GET также доступен HEAD без тела ответа."
            ),
        },
        "servers": [{"url": "http://localhost:8080"}],
        "paths": {
            "/health": {
                "get": operation(
                    "Проверить HTTP и БД",
                    "health",
                    {
                        "200": response(
                            "Сервис доступен", ref("StatusResponse")
                        ),
                    },
                )
            },
            "/adduser": {"post": create},
            "/adducer": {"post": alias},
            "/user/{id}": {"parameters": [path_parameter], "get": find},
            "/activate/{id}": {
                "parameters": [path_parameter],
                "get": {
                    **activate,
                    "operationId": "activateUserLegacy",
                    "deprecated": True,
                },
                "post": activate,
            },
            "/slow": {"get": slow},
            "/wrong": {"get": wrong},
        },
        "components": {
            "schemas": {
                "User": user,
                "AddUserRequest": {
                    "type": "object",
                    "required": ["name"],
                    "additionalProperties": False,
                    "properties": {
                        "name": text,
                        "tags": {**tags, "maxItems": 20},
                    },
                },
                "AddUserResponse": {
                    **user,
                    "required": ["status", "id", "name", "tags"],
                    "properties": {
                        **user["properties"],
                        "status": {"type": "string", "const": "ok"},
                    },
                },
                "StatusResponse": {
                    "type": "object",
                    "required": ["status"],
                    "additionalProperties": False,
                    "properties": {
                        "status": {"type": "string", "const": "ok"}
                    },
                },
                "ScheduledResponse": {
                    "type": "object",
                    "required": ["status"],
                    "additionalProperties": False,
                    "properties": {
                        "status": {"type": "string", "const": "scheduled"}
                    },
                },
                "ActivateResponse": {
                    "type": "object",
                    "required": ["status", "active"],
                    "additionalProperties": False,
                    "properties": {
                        "status": {"type": "string", "const": "ok"},
                        "active": {
                            "type": "array",
                            "maxItems": 50,
                            "uniqueItems": True,
                            "items": identifier,
                        },
                    },
                },
                "Error": {
                    "type": "object",
                    "required": ["error"],
                    "additionalProperties": False,
                    "properties": {
                        "error": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                },
                "DemoError": {
                    "type": "object",
                    "required": ["msg", "detail"],
                    "additionalProperties": False,
                    "properties": {
                        "msg": {"type": "string", "const": "error"},
                        "detail": {
                            "type": "string",
                            "const": "division by zero",
                        },
                    },
                },
            }
        },
    }
    for path, mime_type in (
        ("/openapi.json", "application/json"),
        ("/openapi.yaml", "application/yaml"),
        ("/docs", "text/html"),
    ):
        spec["paths"][path] = {
            "get": operation(
                "Получить документацию",
                path[1:].replace(".", "_"),
                {
                    "200": {
                        "description": "Документация",
                        "content": {
                            mime_type: {
                                "schema": {
                                    "type": "object"
                                    if path.endswith("json")
                                    else "string",
                                }
                            }
                        },
                    },
                },
            )
        }
    return spec


if __name__ == "__main__":
    contract = build_spec()
    (API / "openapi.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (API / "openapi.yaml").write_text(
        yaml.safe_dump(contract, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print("Generated OpenAPI 3.1 YAML and JSON")
