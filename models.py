from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    # Внутренний PK
    id = db.Column(db.Integer, primary_key=True)

    # Публичный UUID — его можно показывать юзеру
    public_id = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # Храним ТОЛЬКО хеш, никогда сам пароль
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"