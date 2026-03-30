from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from datetime import date



db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.Text)
    mobile = db.Column(db.String(15), nullable=False)

    place = db.Column(db.String(100), nullable=False)
    otp_code = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, default=False)

class Trip(db.Model):

    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trip_date = db.Column(
    db.Date,
    default=date.today
)



    id = db.Column(db.Integer, primary_key=True)
    trip_no = db.Column(db.String(50), unique=True)
    route = db.Column(db.JSON)
    mode = db.Column(db.String(50))
    purpose = db.Column(db.String(100))


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    start_lat = db.Column(db.Float)
    start_lng = db.Column(db.Float)

    end_lat = db.Column(db.Float)
    end_lng = db.Column(db.Float)

    start_time = db.Column(db.String(50))
    end_time = db.Column(db.String(50))

    distance = db.Column(db.Float)
    duration = db.Column(db.Float)

    mode = db.Column(db.String(50))

    cost = db.Column(db.Float)
    companions = db.Column(db.Integer)

    frequency = db.Column(db.Integer, default=1)

    map_image = db.Column(db.Text)
