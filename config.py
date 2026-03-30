import os

class Config:

    SECRET_KEY = "supersecret"

    _db_url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    # Render gives postgres:// but SQLAlchemy needs postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = "jwtsecretkey"

    # EMAIL CONFIG (GMAIL SMTP)
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "mraviteja.2807@gmail.com"
    MAIL_PASSWORD = "wtug hqgr imbj okce"
    MAIL_DEFAULT_SENDER = "mraviteja.2807@gmail.com"
