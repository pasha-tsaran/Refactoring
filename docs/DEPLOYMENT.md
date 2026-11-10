# GitHub и удалённый запуск

## Подготовка GitHub

`.gitignore`, `.gitattributes`, workflow CI и инструкции уже подготовлены. Репозиторий локальный, remote и публикация не выполнялись.
Из каталога `refactored_project`, после проверки git status:

```powershell
git status
git add .
git commit -m "Refactor Python API and add modular Go server"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/refactoring-user-api.git
git push -u origin main
```

Сначала создайте пустой репозиторий на GitHub, замените YOUR_USERNAME своим именем.
Если Git ещё не настроен, укажите своё имя/почту через `git config user.name` и `git config user.email` в этом репозитории.
`.env`, БД, venv, кэш и бинарные файлы игнорируются. `originals/` намеренно сохранены как материалы аудита и не импортируются.
Не добавляйте в Git пользовательские БД и секреты. CI не публикует образ автоматически.

## Linux-сервер через Git

Нужны установленный Docker Engine и Compose plugin. После копирования проекта или клонирования:

```bash
cd refactoring-user-api
docker compose up --build -d --wait
docker compose ps
curl --fail http://127.0.0.1:8080/health
python3 scripts/test_endpoints.py --base-url http://127.0.0.1:8080
```

На сервере Compose по умолчанию слушает localhost. Для проверки с Windows через SSH:

```powershell
ssh -L 18080:127.0.0.1:8080 user@SERVER_IP
```

Пока SSH-туннель открыт, во втором терминале:

```powershell
py scripts/test_endpoints.py --base-url http://localhost:18080
```

Так можно проверить учебное API без публикации его порта в интернет.
Для внешнего приложения настройте reverse proxy (например, Caddy/Nginx) с HTTPS и авторизацией.
У API нет собственного контроля доступа. Внешний proxy может находиться на хосте и обращаться к 127.0.0.1:8080.

## Через Docker Hub

Необязательные команды для ручной публикации из корня проекта:

```powershell
docker login
docker build -t YOUR_USERNAME/refactoring-user-api:1.0.0 ./go_server
docker push YOUR_USERNAME/refactoring-user-api:1.0.0
```

На Linux amd64-сервере:

```bash
docker pull YOUR_USERNAME/refactoring-user-api:1.0.0
docker volume create refactoring_users
docker run -d --name refactoring-api --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  --mount type=volume,source=refactoring_users,target=/data \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  YOUR_USERNAME/refactoring-user-api:1.0.0
docker exec refactoring-api /server -healthcheck
docker logs refactoring-api
```

При несовпадении архитектуры пересоберите на целевом сервере либо используйте buildx `--platform linux/arm64` / `linux/amd64`.
Публикация образа и запуск на реальном удалённом сервере не выполнялись в рамках локальной проверки.

## Обновление и данные

`docker compose up --build -d --wait` обновляет сервис, именованный том остаётся прежним.
Для резервной копии остановите сервис и скопируйте содержимое тома `/data` вместе с SQLite WAL-файлами, затем запустите снова.
Не копируйте только users.db из активно работающего WAL-хранилища: используйте SQLite backup API либо остановку приложения.
Логи доступны через `docker compose logs api`, статус — `docker compose ps`, штатная остановка — `docker compose down`.
