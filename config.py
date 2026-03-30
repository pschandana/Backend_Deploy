class Config:

    SECRET_KEY = "supersecret"

    SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = "jwtsecretkey"


    # 🔥 EMAIL CONFIG (GMAIL SMTP)

    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True

    MAIL_USERNAME = "mraviteja.2807@gmail.com"   # 🔴 CHANGE
    MAIL_PASSWORD = "wtug hqgr imbj okce"      # 🔴 CHANGE

    MAIL_DEFAULT_SENDER = "mraviteja.2807@gmail.com" 
