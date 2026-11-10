# Результаты проверки

Дата: 10 ноября 2026 (Europe/Moscow). Проверка выполнена локально на Windows, Linux-контейнерах Docker Desktop.

## Подтверждённые результаты

| Проверка | Результат |
|---|---|
| Python `pytest -q` | 29 passed |
| Python Ruff lint и format check | Passed, длина строки 79, PEP 8 |
| OpenAPI 3.1 validator | Passed; JSON/YAML одинаковы и совпадают с генератором |
| Python-ответы против JSON Schema из OpenAPI | Passed |
| Go `go test ./...` | Passed |
| Go `go vet ./...`, `gofmt` | Passed |
| Go `go test -race` | Passed, гонок не обнаружено в выполненных сценариях |
| Покрытие Go `internal/...` с учётом интеграционных тестов | 90.3% statements |
| Docker многоэтапная сборка, CGO_ENABLED=0 | Passed |
| Docker Compose, read-only root, non-root UID | Passed; healthy |
| HTTP smoke по работающему Go-контейнеру | Все 18 проверок passed |
| HTTP smoke по работающему Python/Waitress | Все 18 проверок passed |
| Live JSON Schema для обеих реализаций | По 8 реальных ответов соответствуют контракту |
| Live параллельные HTTP-запросы | По 24 создания + активации, все ID уникальны |
| Перезапуск Go-контейнера | Пользователь, имя и теги сохранились в томе |
| GitHub workflow, actionlint + ShellCheck | Passed локально |
| Python `pip check` | Конфликтов зависимостей нет |

Машиночитаемые результаты дополнительных HTTP-проверок: `live-verification.json`.
`/wrong` с 500 — ожидаемый учебный ответ, включённый в успешные проверки.

## Регрессионные сценарии

- Создание, чтение, обе формы активации, legacy `/adducer`, health, документация.
- SQL-инъекции в имени, поиске и ID; имя с апострофом сохраняется буквально.
- Некорректный JSON, null, массив вместо объекта, неизвестные поля, типы имени/тегов.
- Пустое имя, управляющие символы, превышение длины, больше 20 тегов, тело больше 16 KiB.
- Коды 200/201/202/400/404/405/413/415/500/503, Allow и Retry-After.
- Независимость списка тегов от аргумента вызывающего, int ID, декодирование тегов.
- 60 конкурентных пользователей и активаций в каждой реализации, лимит/уникальность и независимые snapshots.
- Хеширование с разными солями, проверка верного/неверного пароля, повреждённый хеш, fail-closed роли.
- Ограничение фоновых задач; Go cancellation и запрет запуска после shutdown.
- Данные после повторного открытия SQLite и после реального Docker restart.

## Окружение

Python 3.12.9; Flask 3.1.3; Waitress 3.0.2; pytest 9.2.0; Ruff 0.17.4;
openapi-spec-validator 0.9.0; PyYAML 6.0.3.
Go 1.26.10 linux/amd64 в `golang:1.26-bookworm`, образ компилятора зафиксирован digest в Dockerfile.
SQLite Go-драйвер modernc.org/sqlite v1.45.0, контрольные суммы зависимостей проверены `go mod verify`.
Docker Engine 29.8.2, Linux amd64.

## Практические пределы проверки

Это локальные функциональные и регрессионные тесты. Они не доказывают отсутствие всех возможных ошибок.
Проверка производительности, полный penetration test и нагрузочный профиль реального production не проводились.
Удалённый сервер, GitHub Actions в облаке, push на GitHub и Docker Hub не запускались; для них подготовлены конфигурации и инструкции.
Проверочные контейнеры остановлены после тестирования; исходники и пользовательские Docker-проекты не изменялись.

## Повторение

Из корня проекта, после установки requirements-dev.txt:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest -q
docker build -t refactoring-user-api:local ./go_server
docker compose up -d --wait
py scripts/test_endpoints.py
docker compose down
```

Каждая полная Docker-сборка проходит этап тестирования Go с `-race` до создания финального образа.
