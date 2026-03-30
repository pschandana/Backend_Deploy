"""
Fix placeholder password hashes for seeded users.
Sets password to '123456' for all 4 accounts.
"""
import sqlite3
from flask_bcrypt import Bcrypt
from flask import Flask

app = Flask(__name__)
bcrypt = Bcrypt(app)

DB_PATH = "instance/app.db"

EMAILS = [
    "pschandana2924@gmail.com",
    "skhamidha08@gmail.com",
    "bhavana2k5sistla@gmail.com",
    "skrihana628@gmail.com",
]

with app.app_context():
    real_hash = bcrypt.generate_password_hash("123456").decode("utf-8")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for email in EMAILS:
        cur.execute(
            "UPDATE user SET password = ? WHERE email = ?",
            (real_hash, email)
        )
        print(f"Updated password for {email}")

    conn.commit()
    conn.close()
    print("\nDone.")
