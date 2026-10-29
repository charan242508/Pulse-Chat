import os
import re
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "messenger.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Enable SESSION_COOKIE_SECURE=True when deployed behind HTTPS.
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins=[], async_mode="threading")


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL,
            last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_messages_pair
          ON messages(sender_id, recipient_id, id);
        """)
        existing = con.execute("SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,)).fetchone()
        if not existing:
            con.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                ("Administrator", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD),
                 "admin", datetime.now(timezone.utc).isoformat())
            )


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as con:
        row = con.execute(
            "SELECT id,name,email,role,created_at,last_seen FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("chat"))
        return fn(*args, **kwargs)
    return wrapper


def conversation_room(user_a, user_b):
    return f"dm_{min(int(user_a), int(user_b))}_{max(int(user_a), int(user_b))}"


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("chat"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(name) < 2 or len(name) > 60:
            flash("Name must be between 2 and 60 characters.", "error")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif email == ADMIN_EMAIL:
            flash("That email is reserved for the administrator.", "error")
        else:
            try:
                with db() as con:
                    con.execute(
                        "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                        (name, email, generate_password_hash(password), "user", utc_now())
                    )
                flash("Account created. You can now sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            with db() as con:
                con.execute("UPDATE users SET last_seen=? WHERE id=?", (utc_now(), user["id"]))
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "chat"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/chat")
@login_required
def chat():
    user = current_user()
    return render_template("chat.html", user=user)


@app.route("/api/me")
@login_required
def api_me():
    return jsonify(current_user())


@app.route("/api/users")
@login_required
def api_users():
    user = current_user()
    query = request.args.get("q", "").strip()[:80]
    with db() as con:
        if query:
            rows = con.execute("""
                SELECT id,name,email,last_seen FROM users
                WHERE id != ? AND role='user' AND (name LIKE ? OR email LIKE ?)
                ORDER BY name LIMIT 50
            """, (user["id"], f"%{query}%", f"%{query}%")).fetchall()
        else:
            rows = con.execute("""
                SELECT id,name,email,last_seen FROM users
                WHERE id != ? AND role='user' ORDER BY name LIMIT 100
            """, (user["id"],)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/messages/<int:other_id>")
@login_required
def api_messages(other_id):
    user = current_user()
    if other_id == user["id"]:
        return jsonify({"error": "You cannot message yourself."}), 400
    with db() as con:
        other = con.execute("SELECT id FROM users WHERE id=? AND role='user'", (other_id,)).fetchone()
        if not other:
            return jsonify({"error": "User not found."}), 404
        rows = con.execute("""
            SELECT m.id,m.sender_id,m.recipient_id,m.body,m.created_at,m.read_at,
                   u.name AS sender_name
            FROM messages m JOIN users u ON u.id=m.sender_id
            WHERE (m.sender_id=? AND m.recipient_id=?)
               OR (m.sender_id=? AND m.recipient_id=?)
            ORDER BY m.id DESC LIMIT 200
        """, (user["id"], other_id, other_id, user["id"])).fetchall()
        con.execute("""
            UPDATE messages SET read_at=?
            WHERE sender_id=? AND recipient_id=? AND read_at IS NULL
        """, (utc_now(), other_id, user["id"]))
    messages = [dict(row) for row in reversed(rows)]
    return jsonify(messages)


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html", user=current_user())


@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    with db() as con:
        users = con.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0]
        admins = con.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        messages = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        today = datetime.now(timezone.utc).date().isoformat()
        today_messages = con.execute(
            "SELECT COUNT(*) FROM messages WHERE substr(created_at,1,10)=?", (today,)
        ).fetchone()[0]
        recent = con.execute("""
            SELECT m.id,m.body,m.created_at,s.name AS sender_name,r.name AS recipient_name
            FROM messages m
            JOIN users s ON s.id=m.sender_id JOIN users r ON r.id=m.recipient_id
            ORDER BY m.id DESC LIMIT 8
        """).fetchall()
        people = con.execute("""
            SELECT id,name,email,role,created_at,last_seen
            FROM users ORDER BY id DESC LIMIT 100
        """).fetchall()
    return jsonify({
        "users": users, "admins": admins, "messages": messages,
        "today_messages": today_messages,
        "recent": [dict(r) for r in recent],
        "people": [dict(r) for r in people]
    })


@app.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = current_user()
    if user_id == user["id"]:
        return jsonify({"error": "You cannot delete your own administrator account."}), 400
    with db() as con:
        target = con.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            return jsonify({"error": "User not found."}), 404
        if target["role"] == "admin":
            return jsonify({"error": "Administrator accounts cannot be deleted here."}), 403
        con.execute("DELETE FROM users WHERE id=?", (user_id,))
    return jsonify({"ok": True})


@socketio.on("connect")
def socket_connect(auth=None):
    user = current_user()
    if not user:
        return False
    join_room(f"user_{user['id']}")
    emit("connected", {"user_id": user["id"]})


@socketio.on("open_conversation")
def open_conversation(data):
    user = current_user()
    if not user:
        return
    try:
        other_id = int(data.get("user_id"))
    except (TypeError, ValueError, AttributeError):
        return
    if other_id == user["id"]:
        return
    with db() as con:
        other = con.execute("SELECT id FROM users WHERE id=? AND role='user'", (other_id,)).fetchone()
    if other:
        join_room(conversation_room(user["id"], other_id))


@socketio.on("send_message")
def send_message(data):
    user = current_user()
    if not user:
        emit("message_error", {"error": "Please sign in again."})
        return
    if not isinstance(data, dict):
        emit("message_error", {"error": "Invalid message."})
        return
    try:
        recipient_id = int(data.get("recipient_id"))
    except (TypeError, ValueError):
        emit("message_error", {"error": "Choose a contact first."})
        return
    body = str(data.get("body", "")).strip()
    if not body or len(body) > 2000:
        emit("message_error", {"error": "Message must contain 1–2000 characters."})
        return
    if recipient_id == user["id"]:
        emit("message_error", {"error": "You cannot message yourself."})
        return
    with db() as con:
        recipient = con.execute(
            "SELECT id,name FROM users WHERE id=? AND role='user'", (recipient_id,)
        ).fetchone()
        if not recipient:
            emit("message_error", {"error": "That contact is not available."})
            return
        cur = con.execute(
            "INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(?,?,?,?)",
            (user["id"], recipient_id, body, utc_now())
        )
        message = {
            "id": cur.lastrowid, "sender_id": user["id"],
            "recipient_id": recipient_id, "body": body,
            "created_at": utc_now(), "read_at": None,
            "sender_name": user["name"]
        }
    room = conversation_room(user["id"], recipient_id)
    socketio.emit("new_message", message, room=room)
    socketio.emit("conversation_update", {
        "other_id": user["id"], "other_name": user["name"],
        "body": body, "created_at": message["created_at"]
    }, room=f"user_{recipient_id}")
    socketio.emit("conversation_update", {
        "other_id": recipient_id, "other_name": recipient["name"],
        "body": body, "created_at": message["created_at"]
    }, room=f"user_{user['id']}")
    emit("message_sent", {"id": message["id"]})


# Initialize tables for both local execution and WSGI servers (for example, Gunicorn).
init_db()

if __name__ == "__main__":
    print("Messenger running at http://127.0.0.1:5000")
    print(f"Admin login email: {ADMIN_EMAIL}")
    print("Set ADMIN_PASSWORD and SECRET_KEY environment variables before deployment.")
    socketio.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
