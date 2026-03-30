from app import app
from models import db, User, Trip

with app.app_context():
    users = User.query.all()
    for u in users:
        print(f"id={u.id}, email={u.email}, name={u.name}")
    print("---")
    trips = Trip.query.all()
    print(f"Total trips: {len(trips)}")
    for t in trips:
        print(f"  trip id={t.id}, user_id={t.user_id}, trip_no={t.trip_no}")
