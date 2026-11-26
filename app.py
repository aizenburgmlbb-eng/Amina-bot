import os
import re
import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import or_, and_, text

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

# ============================================================
# Константы и Конфигурация
# ============================================================
KRASNOYARSK_TZ = ZoneInfo("Asia/Krasnoyarsk")

def now_krasnoyarsk():
    return datetime.now(KRASNOYARSK_TZ).replace(tzinfo=None)

app = Flask(__name__)
app.config["SECRET_KEY"] = "sibiria-secret-key-ayzen-2026"

os.makedirs(app.instance_path, exist_ok=True)
db_path = os.path.join(app.instance_path, "site.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================================================
# Модели БД
# ============================================================
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    lastname = db.Column(db.String(32), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)
    last_seen = db.Column(db.DateTime, default=now_krasnoyarsk)
    gender = db.Column(db.String(10), default="Мужской")
    
    role = db.Column(db.String(20), default="user", nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    mute_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    def is_muted(self):
        return self.mute_until and self.mute_until > now_krasnoyarsk()

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)

    user = db.relationship('User', backref=db.backref('messages', lazy=True))
    reply_to = db.relationship('Message', remote_side=[id], backref='replies')

class Dialog(db.Model):
    __tablename__ = "dialogs"
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)

class PrivateMessage(db.Model):
    __tablename__ = "private_messages"
    id = db.Column(db.Integer, primary_key=True)
    dialog_id = db.Column(db.Integer, db.ForeignKey('dialogs.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('private_messages.id'), nullable=True)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id])
    reply_to = db.relationship('PrivateMessage', remote_side=[id], backref='replies')

class ActionLog(db.Model):
    __tablename__ = "action_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)
    user = db.relationship('User')

class HelpMessage(db.Model):
    __tablename__ = "help_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_application = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="new")
    curator_id = db.Column(db.Integer, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    channel = db.Column(db.String(20), default="admin")
    created_at = db.Column(db.DateTime, default=now_krasnoyarsk)
    
    user = db.relationship('User', foreign_keys=[user_id])
    admin = db.relationship('User', foreign_keys=[admin_id])

# ============================================================
# МИГРАЦИЯ БАЗЫ И СОЗДАНИЕ СИСТЕМЫ
# ============================================================
with app.app_context():
    db.create_all()
    try: db.session.execute(text("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE messages ADD COLUMN is_edited BOOLEAN DEFAULT 0")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE private_messages ADD COLUMN reply_to_id INTEGER")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE private_messages ADD COLUMN is_edited BOOLEAN DEFAULT 0")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN is_application BOOLEAN DEFAULT 0")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN is_pinned BOOLEAN DEFAULT 0")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN status VARCHAR(20) DEFAULT 'new'")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN curator_id INTEGER")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN admin_id INTEGER REFERENCES users(id)")); db.session.commit()
    except: db.session.rollback()
    try: db.session.execute(text("ALTER TABLE help_messages ADD COLUMN channel VARCHAR(20) DEFAULT 'admin'")); db.session.commit()
    except: db.session.rollback()

    system_user = db.session.get(User, 777)
    if not system_user:
        sys = User(id=777, username="Система", lastname="Уведомления", role="system")
        sys.set_password("super_secret_random_password_123!")
        db.session.add(sys)
        db.session.commit()
        print("[DB] Создан аккаунт Системы (ID 777)", flush=True)

# ============================================================
# Хелперы
# ============================================================
USERNAME_RE = re.compile(r"^[а-яА-ЯёЁ0-9_]{3,32}$")
PASSWORD_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9]{12,64}$")

def validate_registration(username, password, password2):
    errors = []
    if not USERNAME_RE.match(username or ""): errors.append("Логин: 3–32 символа, только русские буквы, цифры и _")
    if not password: errors.append("Пароль обязателен")
    elif len(password) < 12: errors.append("Пароль должен быть не короче 12 символов")
    elif not PASSWORD_RE.match(password): errors.append("Пароль: только буквы (рус/лат) и цифры")
    if password != password2: errors.append("Пароли не совпадают")
    return errors

def clean_text(text):
    if not text: return ""
    return html.escape(text.strip())

@app.before_request
def update_last_seen():
    uid = session.get("user_id")
    if uid:
        user = db.session.get(User, uid)
        if user:
            user.last_seen = now_krasnoyarsk()
            db.session.commit()

def get_current_user():
    uid = session.get("user_id")
    if not uid: return None
    return db.session.get(User, uid)

def can_manage(actor, target, action):
    if not actor or not target or actor.id == target.id: return False
    if actor.id == 1: return True 
    if actor.role == "co_owner":
        if target.id == 1 or target.role in ["owner", "co_owner", "system"]: return False
        return True
    if actor.role == "admin":
        if target.role in ["owner", "co_owner", "admin", "system"]: return False
        return True
    if actor.role == "moderator":
        if target.role != "user": return False
        if action in ["mute", "unmute", "pin"]: return True
        return False
    return False

def get_or_create_dialog(u1_id, u2_id):
    d = Dialog.query.filter(or_(and_(Dialog.user1_id == u1_id, Dialog.user2_id == u2_id), and_(Dialog.user1_id == u2_id, Dialog.user2_id == u1_id))).first()
    if not d:
        d = Dialog(user1_id=u1_id, user2_id=u2_id)
        db.session.add(d)
        db.session.commit()
    return d

def log_action(action_text):
    user = get_current_user()
    if user:
        db.session.add(ActionLog(user_id=user.id, action=action_text))
        db.session.commit()

# ============================================================
# Роуты: Авторизация и Профиль
# ============================================================
@app.route("/")
def index():
    return redirect(url_for("profile") if "user_id" in session else url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        lastname = request.form.get("lastname", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = validate_registration(username, password, password2)
        if not errors and User.query.filter_by(username=username).first():
            errors.append("Такой логин уже занят")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("register.html", username=username, lastname=lastname)

        is_first = User.query.filter(User.role != "system").count() == 0
        user = User(username=username, lastname=lastname, role="owner" if is_first else "user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session.clear()
        session["user_id"] = user.id
        flash("Добро пожаловать!", "success")
        return redirect(url_for("profile"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.is_banned:
                flash("Ваш аккаунт заблокирован администрацией.", "error")
                return render_template("login.html")
            if user.role == "system":
                flash("Вход в системный аккаунт запрещен.", "error")
                return render_template("login.html")
                
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("profile"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    if user.is_banned: session.clear(); return redirect(url_for("login"))
    
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_info":
            user.lastname = clean_text(request.form.get("lastname", ""))
            user.gender = request.form.get("gender", "Мужской")
            db.session.commit()
            flash("Профиль обновлён", "success")
        elif action == "change_password":
            old_pass = request.form.get("old_password", "")
            new_pass = request.form.get("new_password", "")
            new_pass2 = request.form.get("new_password2", "")
            
            if not user.check_password(old_pass): flash("Неверный старый пароль", "error")
            elif new_pass != new_pass2: flash("Новые пароли не совпадают", "error")
            elif len(new_pass) < 12 or not PASSWORD_RE.match(new_pass): flash("Новый пароль должен быть от 12 символов", "error")
            else:
                user.set_password(new_pass)
                db.session.commit()
                flash("Пароль успешно изменён!", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)

@app.route("/user/<int:user_id>")
def user_profile(user_id):
    actor = get_current_user()
    if not actor: return redirect(url_for("login"))
    target = db.session.get(User, user_id)
    if not target: return "Пользователь не найден", 404

    perms = {
        "mute": can_manage(actor, target, "mute"),
        "ban": can_manage(actor, target, "ban"),
        "admin": actor.id == 1 and target.id != 1,
        "moderator": (actor.id == 1 or actor.role in ["co_owner", "admin"]) and target.role in ["user", "moderator"],
        "co_owner": actor.id == 1 and target.id != 1
    }
    return render_template("user_profile.html", target=target, perms=perms, now=now_krasnoyarsk())

@app.route("/user/<int:user_id>/action", methods=["POST"])
def user_action(user_id):
    actor = get_current_user()
    target = db.session.get(User, user_id)
    if not actor or not target: return redirect(url_for("profile"))
    action = request.form.get("action")
    
    if action in ["mute", "unmute"] and can_manage(actor, target, action):
        if action == "mute":
            mins = int(request.form.get("minutes", 10))
            target.mute_until = now_krasnoyarsk() + timedelta(minutes=max(10, min(mins, 4320)))
            log_action(f"Замутил {target.username} на {mins} мин.")
            flash(f"Пользователь замучен на {mins} мин.", "success")
        else:
            target.mute_until = None
            log_action(f"Снял мут с {target.username}")
            flash("Мут снят.", "success")
    elif action in ["ban", "unban"] and can_manage(actor, target, "ban"):
        target.is_banned = (action == "ban")
        log_action(f"Забанил {target.username}" if action == "ban" else f"Разбанил {target.username}")
        flash("Пользователь забанен." if action == "ban" else "Пользователь разбанен.", "success")
    elif action in ["set_mod", "unset_mod"] and can_manage(actor, target, "moderator"):
        target.role = "moderator" if action == "set_mod" else "user"
        log_action(f"Выдал модерку {target.username}" if action == "set_mod" else f"Снял модерку с {target.username}")
        flash("Права модератора изменены.", "success")
    elif action in ["set_admin", "unset_admin"] and can_manage(actor, target, "admin"):
        target.role = "admin" if action == "set_admin" else "user"
        log_action(f"Выдал админку {target.username}" if action == "set_admin" else f"Снял админку с {target.username}")
        flash("Права администратора изменены.", "success")
    elif action == "set_co_owner" and actor.id == 1 and target.id != 1:
        target.role = "co_owner"
        log_action(f"Выдал со-владельца {target.username}")
        flash("Права со-владельца выданы.", "success")
    elif action == "unset_co_owner" and actor.id == 1 and target.role == "co_owner":
        target.role = "user"
        log_action(f"Снял со-владельца с {target.username}")
        flash("Права со-владельца сняты.", "success")

    db.session.commit()
    return redirect(url_for("user_profile", user_id=user_id))

# ============================================================
# Роуты: Поддержка, Мастера, Админы, Чат помощи
# ============================================================
@app.route("/support")
def support():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    
    # Ищем диалог с системой для карточки уведомлений
    sys_dialog = Dialog.query.filter(or_(
        and_(Dialog.user1_id == user.id, Dialog.user2_id == 777),
        and_(Dialog.user1_id == 777, Dialog.user2_id == user.id)
    )).first()
    
    return render_template("support.html", sys_dialog=sys_dialog)

@app.route("/volunteer_apply", methods=["POST"])
def volunteer_apply():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    
    name = clean_text(request.form.get("name", ""))
    age = clean_text(request.form.get("age", ""))
    # Получаем список выбранных сфер (чекбоксы)
    spheres_list = request.form.getlist("sphere")
    spheres_list = [clean_text(s) for s in spheres_list if s.strip()]
    sphere_text = ", ".join(spheres_list)
    
    info = clean_text(request.form.get("info", ""))
    
    if not name or not age or not spheres_list:
        flash("Заполните обязательные поля анкеты (Имя, Возраст, Сфера)", "error")
        return redirect(url_for("support"))
        
    if len(spheres_list) > 2:
        flash("Можно выбрать не более 2 сфер.", "error")
        return redirect(url_for("support"))
    
    text_body = f"📝 ЗАЯВКА НА ВОЛОНТЁРСТВО\n\nОт кого: {user.username} (ID: {user.id})\nИмя: {name}\nВозраст: {age}\nСфера: {sphere_text}\nДоп. инфо: {info}"
    
    msg = HelpMessage(user_id=user.id, text=text_body, is_application=True, status="new", channel="admin")
    db.session.add(msg)
    db.session.commit()
    
    flash("Спасибо! Ваша заявка отправлена в Чат администрации.", "success")
    return redirect(url_for("support"))

@app.route("/application/<int:msg_id>/action", methods=["POST"])
def application_action(msg_id):
    admin = get_current_user()
    if not admin or admin.role not in ["owner", "co_owner", "admin", "moderator"]:
        return jsonify({"error": "denied"}), 403
        
    app_msg = db.session.get(HelpMessage, msg_id)
    if not app_msg or not app_msg.is_application: return jsonify({"error": "not found"}), 404
    
    action = request.json.get("action")
    applicant = db.session.get(User, app_msg.user_id)
    sys_user = db.session.get(User, 777)
    
    if action == "approve":
        app_msg.status = "approved"
        app_msg.curator_id = 7
        app_msg.admin_id = admin.id
        db.session.commit()
        
        d = get_or_create_dialog(applicant.id, sys_user.id)
        text_pm = f"🎉 <b>Ваша заявка на волонтёрство одобрена!</b>\n\nПожалуйста, свяжитесь с организатором: <a href='/chats/start/7' style='color:#2563eb; font-weight:bold;'>Организатор</a>"
        db.session.add(PrivateMessage(dialog_id=d.id, sender_id=sys_user.id, text=text_pm))
        
        db.session.commit()
        return jsonify({"ok": True})
        
    elif action == "reject":
        app_msg.status = "rejected"
        app_msg.admin_id = admin.id
        db.session.commit()
        
        d = get_or_create_dialog(applicant.id, sys_user.id)
        text_pm = "😔 К сожалению, ваша заявка на волонтёрство была отклонена. Спасибо за отклик!"
        db.session.add(PrivateMessage(dialog_id=d.id, sender_id=sys_user.id, text=text_pm))
        
        db.session.commit()
        return jsonify({"ok": True})
        
    return jsonify({"error": "invalid"}), 400

@app.route("/masters")
def masters():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    return render_template("masters.html")

@app.route("/help_chat")
def help_chat():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    return render_template("help_chat.html", user=user)

@app.route("/help_chat/messages")
def help_chat_messages():
    user = get_current_user()
    if not user: return jsonify([])
    msgs = HelpMessage.query.filter(
        HelpMessage.channel == "admin",
        HelpMessage.id > request.args.get("since", 0, type=int)
    ).order_by(HelpMessage.id.asc()).all()
    result = []
    for m in msgs:
        result.append({
            "id": m.id, "username": m.user.username, "lastname": m.user.lastname, "user_id": m.user.id,
            "role": m.user.role, "text": m.text, "time": m.created_at.strftime("%H:%M"),
            "is_application": m.is_application,
            "status": m.status,
            "admin_name": m.admin.username if m.admin else None
        })
    return jsonify(result)

@app.route("/help_chat/send", methods=["POST"])
def help_chat_send():
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin", "moderator"]:
        return jsonify({"error": "denied"}), 403
    
    text = clean_text(request.json.get("text", ""))
    if text:
        db.session.add(HelpMessage(user_id=user.id, text=text, is_application=False, channel="admin"))
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "empty"}), 400

@app.route("/help_chat/delete/<int:msg_id>", methods=["POST"])
def help_chat_delete(msg_id):
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin"]:
        return jsonify({"error": "denied"}), 403
        
    msg = db.session.get(HelpMessage, msg_id)
    if not msg or msg.channel != "admin": return jsonify({"error": "not found"}), 404
    
    db.session.delete(msg)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/help_chat/pin/<int:msg_id>", methods=["POST"])
def help_chat_pin(msg_id):
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin"]:
        return jsonify({"error": "denied"}), 403
        
    msg = db.session.get(HelpMessage, msg_id)
    if not msg or msg.channel != "admin": return jsonify({"error": "not found"}), 404
    
    msg.is_pinned = not msg.is_pinned
    db.session.commit()
    return jsonify({"ok": True, "pinned": msg.is_pinned})

# ============================================================
# Роуты: ОБЪЯВЛЕНИЯ (отдельный канал)
# ============================================================
@app.route("/announcements")
def announcements():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    return render_template("announcements.html", user=user)

@app.route("/announcements/messages")
def announcements_messages():
    user = get_current_user()
    if not user: return jsonify([])
    msgs = HelpMessage.query.filter(
        HelpMessage.channel == "announcements",
        HelpMessage.id > request.args.get("since", 0, type=int)
    ).order_by(HelpMessage.id.asc()).all()
    result = []
    for m in msgs:
        result.append({
            "id": m.id, "username": m.user.username, "lastname": m.user.lastname,
            "user_id": m.user.id, "role": m.user.role, "text": m.text,
            "time": m.created_at.strftime("%H:%M"), "is_pinned": m.is_pinned
        })
    return jsonify(result)

@app.route("/announcements/send", methods=["POST"])
def announcements_send():
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin", "moderator"]:
        return jsonify({"error": "denied"}), 403
    text = clean_text(request.json.get("text", ""))
    if text:
        db.session.add(HelpMessage(
            user_id=user.id, text=text, is_application=False,
            channel="announcements", status="new"
        ))
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "empty"}), 400

@app.route("/announcements/delete/<int:msg_id>", methods=["POST"])
def announcements_delete(msg_id):
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin", "moderator"]:
        return jsonify({"error": "denied"}), 403
    msg = db.session.get(HelpMessage, msg_id)
    if not msg or msg.channel != "announcements":
        return jsonify({"error": "not found"}), 404
    db.session.delete(msg)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/announcements/pin/<int:msg_id>", methods=["POST"])
def announcements_pin(msg_id):
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin", "moderator"]:
        return jsonify({"error": "denied"}), 403
    msg = db.session.get(HelpMessage, msg_id)
    if not msg or msg.channel != "announcements":
        return jsonify({"error": "not found"}), 404
    msg.is_pinned = not msg.is_pinned
    db.session.commit()
    return jsonify({"ok": True, "pinned": msg.is_pinned})

@app.route("/administration")
def administration():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    owner = User.query.filter_by(role="owner").first()
    staff = User.query.filter(User.role.in_(["co_owner", "admin", "moderator"])).order_by(User.id).all()
    return render_template("administration.html", owner=owner, staff=staff)

@app.route("/logs")
def logs():
    user = get_current_user()
    if not user or user.role not in ["owner", "co_owner", "admin", "moderator"]: return redirect(url_for("profile"))
    return render_template("logs.html", logs=ActionLog.query.order_by(ActionLog.id.desc()).limit(100).all())

# ============================================================
# Роуты: Медиа (Список чатов и сам чат)
# ============================================================
@app.route("/chat_sibiria")
def chat_sibiria():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    sys_user = db.session.get(User, 777)
    sys_dialog = Dialog.query.filter(or_(
        and_(Dialog.user1_id == user.id, Dialog.user2_id == 777),
        and_(Dialog.user1_id == 777, Dialog.user2_id == user.id)
    )).first()
    return render_template("media_list.html", sys_dialog=sys_dialog)

@app.route("/media_chat")
def media_chat():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    pinned = Message.query.filter_by(is_pinned=True).order_by(Message.id.desc()).all()
    return render_template("media.html", user=user, pinned=pinned)

@app.route("/chat_sibiria/messages")
def chat_messages():
    user = get_current_user()
    if not user: return jsonify([])
    msgs = Message.query.filter(Message.id > request.args.get("since", 0, type=int)).order_by(Message.id.asc()).all()
    result = []
    for m in msgs:
        reply_user = m.reply_to.user.username if m.reply_to else None
        reply_text = m.reply_to.text[:50] + "..." if m.reply_to and len(m.reply_to.text) > 50 else (m.reply_to.text if m.reply_to else None)
        result.append({
            "id": m.id, "username": m.user.username, "lastname": m.user.lastname, "user_id": m.user.id,
            "role": m.user.role, "text": m.text, "time": m.created_at.strftime("%H:%M"),
            "is_edited": m.is_edited, "is_pinned": m.is_pinned, "reply_user": reply_user, "reply_text": reply_text,
            "can_delete": (m.user_id == user.id or user.role in ["owner", "co_owner", "admin", "moderator"]),
            "can_pin": user.role in ["owner", "co_owner", "admin", "moderator"], "can_edit": (m.user_id == user.id)
        })
    return jsonify(result)

@app.route("/chat_sibiria/send", methods=["POST"])
def chat_send():
    user = get_current_user()
    if not user: return jsonify({"error": "auth"}), 401
    if user.is_muted(): return jsonify({"error": "muted"}), 403
    text = clean_text(request.json.get("text", ""))
    if text:
        db.session.add(Message(user_id=user.id, text=text, reply_to_id=request.json.get("reply_to_id")))
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "empty"}), 400

@app.route("/chat_sibiria/edit/<int:msg_id>", methods=["POST"])
def chat_edit(msg_id):
    user = get_current_user()
    msg = db.session.get(Message, msg_id)
    if user and msg and msg.user_id == user.id:
        new_text = clean_text(request.json.get("text", ""))
        if new_text:
            msg.text = new_text
            msg.is_edited = True
            db.session.commit()
            return jsonify({"ok": True})
    return jsonify({"error": "denied"}), 403

@app.route("/chat_sibiria/delete/<int:msg_id>", methods=["POST"])
def chat_delete(msg_id):
    user = get_current_user()
    msg = db.session.get(Message, msg_id)
    if user and msg and (msg.user_id == user.id or user.role in ["owner", "co_owner", "admin", "moderator"]):
        db.session.delete(msg)
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "denied"}), 403

@app.route("/chat_sibiria/pin/<int:msg_id>", methods=["POST"])
def chat_pin(msg_id):
    user = get_current_user()
    msg = db.session.get(Message, msg_id)
    if user and msg and user.role in ["owner", "co_owner", "admin", "moderator"]:
        msg.is_pinned = not msg.is_pinned
        db.session.commit()
        return jsonify({"ok": True, "pinned": msg.is_pinned})
    return jsonify({"error": "denied"}), 403

# ============================================================
# Роуты: Личные Чаты (ЛС)
# ============================================================
@app.route("/chats/new")
def chats_new():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    users = User.query.filter(User.role.in_(["owner", "co_owner", "admin", "moderator"]), User.id != user.id, User.is_banned == False).order_by(User.username).all()
    return render_template("chats_new.html", users=users)

@app.route("/chats/start/<int:target_id>")
def chats_start(target_id):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    d = get_or_create_dialog(user.id, target_id)
    return redirect(url_for("chat_dialog", dialog_id=d.id))

@app.route("/chats/<int:dialog_id>")
def chat_dialog(dialog_id):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    d = db.session.get(Dialog, dialog_id)
    if not d or user.id not in [d.user1_id, d.user2_id]:
        flash("Диалог не найден", "error")
        return redirect(url_for("administration"))
        
    other_id = d.user2_id if d.user1_id == user.id else d.user1_id
    other_user = db.session.get(User, other_id)
    PrivateMessage.query.filter_by(dialog_id=d.id, is_read=False).filter(PrivateMessage.sender_id != user.id).update({"is_read": True})
    db.session.commit()
    pinned = PrivateMessage.query.filter_by(dialog_id=d.id, is_pinned=True).order_by(PrivateMessage.id.desc()).all()
    return render_template("chat_dialog.html", dialog=d, other_user=other_user, user=user, pinned=pinned)

@app.route("/chats/<int:dialog_id>/messages")
def chat_dialog_messages(dialog_id):
    user = get_current_user()
    if not user: return jsonify([])
    d = db.session.get(Dialog, dialog_id)
    if not d or user.id not in [d.user1_id, d.user2_id]: return jsonify([])
    
    msgs = PrivateMessage.query.filter(PrivateMessage.dialog_id == dialog_id, PrivateMessage.id > request.args.get("since", 0, type=int)).order_by(PrivateMessage.id.asc()).all()
    result = []
    for m in msgs:
        reply_user = m.reply_to.sender.username if m.reply_to else None
        reply_text = m.reply_to.text[:50] + "..." if m.reply_to and len(m.reply_to.text) > 50 else (m.reply_to.text if m.reply_to else None)
        result.append({
            "id": m.id, "sender_id": m.sender_id, "text": m.text, "time": m.created_at.strftime("%H:%M"),
            "is_mine": m.sender_id == user.id, "is_edited": m.is_edited, "is_pinned": m.is_pinned,
            "reply_user": reply_user, "reply_text": reply_text, 
            "can_pin": user.role in ["owner", "co_owner", "admin", "moderator"] and m.sender_id != 777, 
            "can_edit": m.sender_id == user.id
        })
    return jsonify(result)

@app.route("/chats/<int:dialog_id>/send", methods=["POST"])
def chat_dialog_send(dialog_id):
    user = get_current_user()
    if not user or user.is_muted(): return jsonify({"error": "denied"}), 403
    d = db.session.get(Dialog, dialog_id)
    if not d or user.id not in [d.user1_id, d.user2_id]: return jsonify({"error": "denied"}), 403
    
    other_id = d.user2_id if d.user1_id == user.id else d.user1_id
    if other_id == 777:
        return jsonify({"error": "system_protected"}), 403

    text = clean_text(request.json.get("text", ""))
    if text:
        db.session.add(PrivateMessage(dialog_id=d.id, sender_id=user.id, text=text, reply_to_id=request.json.get("reply_to_id")))
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "empty"}), 400

@app.route("/chats/<int:dialog_id>/edit/<int:msg_id>", methods=["POST"])
def chat_dialog_edit(dialog_id, msg_id):
    user = get_current_user()
    msg = db.session.get(PrivateMessage, msg_id)
    if user and msg and msg.sender_id == user.id:
        new_text = clean_text(request.json.get("text", ""))
        if new_text:
            msg.text = new_text
            msg.is_edited = True
            db.session.commit()
            return jsonify({"ok": True})
    return jsonify({"error": "denied"}), 403

@app.route("/chats/<int:dialog_id>/delete/<int:msg_id>", methods=["POST"])
def chat_dialog_delete(dialog_id, msg_id):
    user = get_current_user()
    msg = db.session.get(PrivateMessage, msg_id)
    if user and msg and (msg.sender_id == user.id or user.role in ["owner", "co_owner", "admin", "moderator"]) and msg.sender_id != 777:
        db.session.delete(msg)
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "denied"}), 403

@app.route("/chats/<int:dialog_id>/pin/<int:msg_id>", methods=["POST"])
def chat_dialog_pin(dialog_id, msg_id):
    user = get_current_user()
    msg = db.session.get(PrivateMessage, msg_id)
    if user and msg and user.role in ["owner", "co_owner", "admin", "moderator"] and msg.sender_id != 777:
        msg.is_pinned = not msg.is_pinned
        db.session.commit()
        return jsonify({"ok": True, "pinned": msg.is_pinned})
    return jsonify({"error": "denied"}), 403

@app.route("/api/unread")
def api_unread():
    user = get_current_user()
    if not user: return jsonify({"count": 0})
    count = db.session.query(PrivateMessage).join(Dialog).filter(
        or_(Dialog.user1_id == user.id, Dialog.user2_id == user.id), PrivateMessage.sender_id != user.id, PrivateMessage.is_read == False
    ).count()
    return jsonify({"count": count})

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=False)