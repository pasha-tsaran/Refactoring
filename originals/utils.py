<code class="language-python" style="white-space:pre-wrap;word-break:break-all">import sqlite3
import threading
import time
import json
# Глобальная переменная — плохая идея
CACHE = {}
# Мутируемый дефолтный аргумент — плохая документация
def add_user(name, tags=[]):
    """
    Добавляет пользователя в локальную базу.
    Возвращает id (int) — но на деле возвращает строку.
    """
    tags.append("new")  # неожиданно модифицирует аргумент зовущего
    conn = sqlite3.connect('users.db')  # соединение не закрывается при ошибке
    cur = conn.cursor()
    # Небезопасная вставка — уязвимость SQL-инъекции
    query = f"INSERT INTO users (name, tags) VALUES ('{name}', '{json.dumps(tags)}')"
    cur.execute(query)
    conn.commit()
    # Возвращаем строку (ошибка типов)
    return cur.lastrowid + ""
# Неправильная обработка паролей — "хеширование" через простой срез
def store_password(user_id, password):
    # pretend hashing
    hashed = password[::-1]  # не-хеш!
    f = open('passwords.txt', 'a')  # файл не закрывается в случае ошибки
    f.write(f"{user_id}:{hashed}\\n")
    # забыли закрыть файл</code>
    <code class="language-python" style="white-space:pre-wrap;word-break:break-all">def store_password(user_id, password):
    # pretend hashing
    hashed = password[::-1]  # не-хеш!
    f = open('passwords.txt', 'a')  # файл не закрывается в случае ошибки
    f.write(f"{user_id}:{hashed}\\n")
    # забыли закрыть файл
# Функция с гонкой потоков (общий список без блокировок)
active_users = []
def set_active(user_id):
    # имитируем задержку, чтобы гонка проявилась
    active_users.append(user_id)
    time.sleep(0.1)
    # иногда удаляем первый элемент — логика странная
    if len(active_users) > 5:
        active_users.pop(0)
# Неверный пример запроса (SQL-инъекция + неправильный тип возврата)
def get_user_by_name(name):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    # опасный способ составления запроса
    cur.execute("SELECT id, name, tags FROM users WHERE name = '%s'" % name)
    row = cur.fetchone()
    # не закрываем соединение
    if not row:
        # возвращаем пустой dict вместо None — контракт не соблюдается
        return {}
    uid, uname, tags_json = row
    # забываем декодировать теги корректно — возможно выброс исключения
    return {"id": uid, "name": uname, "tags": tags_json}</code>