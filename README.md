# User API: Python и Go

## Быстрый запуск на Windows 11

Нужны запущенный Docker Desktop в режиме **Linux containers / WSL 2** и Python 3.12+ для проверочного скрипта.
Откройте PowerShell в каталоге проекта:

```powershell
cd "C:\Users\tsara\OneDrive\Desktop\ДЗ\Рефакторинг\refactored_project"
docker version
docker compose up --build -d --wait
docker compose ps
py scripts/test_endpoints.py
```

Ожидаемый результат: контейнер `healthy`, скрипт заканчивается сообщением `All endpoint checks passed` и кодом выхода 0.
Первый запуск требует интернета: скачиваются образ компилятора и Go-модули.
При сборке автоматически выполняются `gofmt`, `go vet`, тесты и детектор гонок Go.

- Проверка доступности: <http://localhost:8080/health> → `{"status":"ok"}`.
- Документация: <http://localhost:8080/docs>.
- OpenAPI: <http://localhost:8080/openapi.yaml> и <http://localhost:8080/openapi.json>.
- `/wrong` специально отвечает **500**: это учебная демонстрация, и тест считает её успешной проверкой.

```powershell
docker compose logs -f api
# Ctrl+C прекращает просмотр логов, контейнер продолжает работать.
docker compose down
```

`down` сохраняет именованный том с пользователями. Следующий `up -d --wait` использует те же данные.
`docker compose down -v` **удаляет данные**; используйте только для осознанного сброса учебной базы.
Тестовый HTTP-скрипт создаёт двух пользователей, не очищает чужие данные и допускает повторный запуск.

Если 8080 занят:

```powershell
$env:PORT = "18080"
docker compose up --build -d --wait
py scripts/test_endpoints.py --base-url http://localhost:18080
```

Можно скопировать `.env.example` в `.env` и изменить `PORT` там. Переменная PowerShell имеет приоритет над `.env`.

## Вариант без Compose

Из корня проекта:

```powershell
docker build -t refactoring-user-api:local ./go_server
docker volume create refactoring_users
docker run -d --name refactoring-api --restart unless-stopped -p 127.0.0.1:8080:8080 --mount type=volume,source=refactoring_users,target=/data refactoring-user-api:local
docker exec refactoring-api /server -healthcheck
py scripts/test_endpoints.py
docker logs refactoring-api
docker stop refactoring-api
docker rm refactoring-api
```

Образ запускается от UID/GID 65532, не содержит shell или компилятора. Healthcheck встроен в бинарный файл.
Том `/data` обязателен для сохранения SQLite при замене контейнера. Для bind mount на Linux заранее предоставьте UID 65532 право записи в каталог данных.

## Работа с API

| Метод | Путь | Результат |
|---|---|---|
| GET | `/health` | 200, проверка HTTP и соединения SQLite |
| POST | `/adduser` | 201, создать пользователя |
| POST | `/adducer` | 201, совместимый путь с опечаткой из исходника |
| GET | `/user/{id}` | 200 или 404 |
| POST, GET | `/activate/{id}` | 200, активировать существующего пользователя |
| GET | `/slow` | 202, задача принята; 503 + `Retry-After: 1` при занятости |
| GET | `/wrong` | 500, ожидаемая учебная ошибка |
| GET | `/docs`, `/openapi.yaml`, `/openapi.json` | 200, документация |

Создание, получение и активация в PowerShell:

```powershell
$body = @{ name = "Anna"; tags = @("student") } | ConvertTo-Json
$user = Invoke-RestMethod -Method Post -Uri http://localhost:8080/adduser -ContentType application/json -Body $body
Invoke-RestMethod "http://localhost:8080/user/$($user.id)"
Invoke-RestMethod -Method Post "http://localhost:8080/activate/$($user.id)"
```

Пример ответа создания:

```json
{"status":"ok","id":1,"name":"Anna","tags":["student","new"]}
```

`name`: строка 1–100 символов до удаления крайних пробелов, не пустая после удаления пробелов, без управляющих символов U+0000–U+001F.
`tags`: необязательный массив до 20 строк по 1–30 символов, с теми же ограничениями пробелов и управляющих символов.
Теги копируются, крайние пробелы и дубликаты удаляются, `new` добавляется один раз. В ответе возможно 21 значение.
Неизвестные поля, `null`, неправильный JSON и некорректные типы дают 400; неправильный Content-Type — 415; тело более 16 KiB — 413.
ID — положительное десятичное число до 9223372036854775807; некорректный ID — 400, отсутствующий пользователь — 404.
Числовые ID с ведущими нулями допускаются. Одинаковые имена разрешены; поиск утилитой по имени возвращает самую старую запись.
Ошибки возвращаются как `{"error":"..."}`, иногда с полем `detail`; `/wrong` сохраняет формат из урока: `{"msg":"error","detail":"division by zero"}`.
Неподдерживаемый метод: 405 с `Allow`. Для GET доступен HEAD без тела. Неизвестные пути: 404.

GET-активация сохранена для совместимости с уроком и меняет состояние; в новом коде используйте POST.
Список активности: последние 50 уникальных ID в памяти **одного процесса**, сбрасывается при перезапуске.
`/slow` запускает вычисление суммы квадратов 0…99999, максимум две задачи одновременно. Результат не сохраняется и не доступен через API; 202 означает принятие, а не завершение.
В Go задачи отменяются при штатной остановке; в Python это короткие daemon-потоки. Для долговечных заданий нужна отдельная очередь.

## Структура и архитектура

```text
originals/                    исходники как получены, неисполняемые
python_server/user_api/
  models.py                   модель и валидация
  repository.py               SQLite, транзакции, закрытие соединений
  services.py                 правила пользователей, активность, фоновые задачи
  utils.py                    PBKDF2, проверка паролей и роли
  routes.py                   HTTP-маршруты
  __init__.py                 фабрика Flask
  __main__.py                 запуск через Waitress
python_server/tests/          Python-регрессионные тесты
go_server/
  cmd/server/main.go          запуск, graceful shutdown, healthcheck
  internal/config/            настройки окружения
  internal/model/             модели и валидация
  internal/store/             SQLite-репозиторий
  internal/service/           бизнес-логика и блокировка активности
  internal/handler/           HTTP и обработка ошибок
  internal/tasks/             ограничение и отмена фоновых задач
  internal/utils/             хеширование и проверка паролей
  api/                        встроенные OpenAPI JSON/YAML и HTML
  Dockerfile                  многоэтапная сборка, тесты, минимальный образ
scripts/test_endpoints.py     проверки всех HTTP endpoint'ов без pip-зависимостей
scripts/generate_openapi.py   единый источник генерации OpenAPI
tests/test_openapi.py         валидатор OpenAPI и проверка JSON-ответов
docs/                        аудит, архитектура, отчёт о тестах, развёртывание
.github/workflows/ci.yml      Python, OpenAPI, Go race, Docker, HTTP smoke
```

Python оформлен по PEP 8 с аннотациями типов; Go — по `gofmt` и принятым Go-соглашениям.
Контроллеры не исполняют SQL. Инициализация БД выполняется до приёма запросов; ошибки старта не скрываются.
Go использует один SQLite connection в пуле; Python — отдельное соединение на операцию, с commit/rollback и обязательным close.
SQLite использует WAL и ожидание блокировки до 5 секунд. Это учебный однопроцессный сервис, не распределённая система.

## Запуск Python без Docker

Из корня проекта, PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\python_server"
.\.venv\Scripts\python.exe -m user_api
```

Откройте другой терминал в корне проекта:

```powershell
py scripts/test_endpoints.py --base-url http://localhost:8081
```

По умолчанию Waitress слушает `127.0.0.1:8081`, БД — `data/python-users.db`.
Настройки: `HOST`, `PORT`, `DB_PATH`. На Linux: `PYTHONPATH=python_server python -m user_api` после установки зависимостей.
Python читает документацию из `go_server/api/`, поэтому переносите целый проект.
Flask debug и автоперезапуск выключены.

## Запуск Go без Docker

Нужен Go 1.26+; SQLite-драйвер pure Go, C-компилятор для обычной сборки не нужен.

```powershell
cd go_server
go mod download
go run ./cmd/server
# либо:
go build -trimpath -o bin/server.exe ./cmd/server
.\bin\server.exe
```

Настройки: `HTTP_ADDR` (по умолчанию `:8080`), `DB_PATH` (по умолчанию `data/users.db`).
Не запускайте обе реализации на одной и той же БД одновременно; у них отдельное состояние активности и рекомендуются отдельные файлы.
Схема нового проекта едина для Python и Go, но автоматическая миграция неизвестных старых `test.db`/`users.db` не реализована.

## Тесты и качество

Из корня проекта:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest -q
docker build --target test -t refactoring-user-api:test ./go_server
docker compose up --build -d --wait
py scripts/test_endpoints.py
```

Для Go с установленным компилятором: `go vet ./...`, `go test ./...`, `go test -race -cover ./...` из `go_server`.
Детектор гонок требует CGO/C-компилятор; Docker test-stage уже содержит всё необходимое.
Для повторной генерации OpenAPI: `.\.venv\Scripts\python.exe scripts/generate_openapi.py`, затем тесты и пересборка Go-образа.
Контракт соответствует [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0.html); YAML и JSON генерируются вместе, тест проверяет их равенство.
HTTP-скрипт проверяет статусы и содержимое, завершает процесс с кодом 1 при провале.

Подробности: [аудит](docs/AUDIT.md), [архитектура](docs/ARCHITECTURE.md), [результаты тестирования](docs/TEST_REPORT.md), [инструкция для сервера и GitHub](docs/DEPLOYMENT.md).

## Границы учебного проекта

Авторизации, регистрации с паролем и управления ролями через HTTP нет: исходный API их не содержал.
Парольные утилиты доступны только из кода и сохраняют PBKDF2-SHA256 (600000 итераций, соль 16 байт) в SQLite; хеши никогда не включаются в публичный объект User.
`is_admin`/`IsAdmin` принимают доверенные данные, а не пользовательский JSON, и сами по себе не являются механизмом авторизации.
Порт Compose по умолчанию опубликован только на localhost. Для внешнего сервера настройте TLS и контроль доступа на reverse proxy; пример развёртывания — в `docs/DEPLOYMENT.md`.
Публикация на GitHub и Docker Hub пользователем выполняется отдельно по готовым командам. Удалённый сервер в рамках сдачи не использовался.
