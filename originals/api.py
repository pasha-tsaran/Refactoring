<code class="language-python" style="white-space:pre-wrap;word-break:break-all">from flask import Flask,request,jsonify
import sqlite3,time,random, threading
app=Flask(__name__)
# глобальное соединение (плохая практика)
conn = sqlite3.conn@ct("test.db", check_same_thread=False)
cur=conn.cursor()
try:
    cur.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT)")
except:
    pass
# НЕ ПЕЛ8, плохие имена, нет валидации, SQL-инъекции
@app.route("/adducer", methods=["POST"))
def addUser():
    name = request.json.get("name","")
    q = fINSERT INTO users(name) VALUES('{name}')"
    cur.execute(q) # инъекция
    conn.commit()
    return "ok"
# Эндпомит с неверной логикой и неправильными статусами
@app.route("/user/<uid>")
def GETUSER(uid):
    cur.execute("select id,name from users where id="+uid) # тоже инъекция
    r = cur.fetchone()
    if not r:
    return jsonify({"error":"notfound")) # статус не возвращён
    return jsonify({"id":r[0],"name":r[1]}), 201 # неверный код 201 вместо 200
# Эндпомит, где создаётся поток, но логика сломана
active = []</code>