"""
Seed script: adds 4 users (if not present) and their sample trips.
Run with: py seed_sample_trips.py
"""
import sqlite3
import uuid
from datetime import datetime, timedelta, date

DB_PATH = "instance/app.db"

# Vijayawada / Guntur area coordinates
COORDS = {
    "Vijayawada": {"lat": 16.5062, "lng": 80.6480},
    "Guntur":     {"lat": 16.3067, "lng": 80.4365},
    "Amaravati":  {"lat": 16.5150, "lng": 80.5160},
    "Tenali":     {"lat": 16.2432, "lng": 80.6400},
    "Mangalagiri":{"lat": 16.4307, "lng": 80.5525},
}

def make_route(origin, destination):
    o = COORDS.get(origin, {"lat": 16.5062, "lng": 80.6480})
    d = COORDS.get(destination, {"lat": 16.3067, "lng": 80.4365})
    mid_lat = round((o["lat"] + d["lat"]) / 2, 4)
    mid_lng = round((o["lng"] + d["lng"]) / 2, 4)
    import json
    return json.dumps([
        {"lat": o["lat"], "lng": o["lng"]},
        {"lat": mid_lat,  "lng": mid_lng},
        {"lat": d["lat"], "lng": d["lng"]},
    ])

# Placeholder bcrypt hash for password "Sample@123"
PLACEHOLDER_HASH = "$2b$12$placeholderhashabcdefghijklmnopqrstuvwxyz012345678"

USERS = [
    {"email": "pschandana2924@gmail.com", "name": "Chandana",  "mobile": "9000000001", "place": "Vijayawada"},
    {"email": "skhamidha08@gmail.com",    "name": "Khamidha",  "mobile": "9000000002", "place": "Vijayawada"},
    {"email": "bhavana2k5sistla@gmail.com","name": "Bhavana",  "mobile": "9000000003", "place": "Vijayawada"},
    {"email": "skrihana628@gmail.com",    "name": "Krihana",   "mobile": "9000000004", "place": "Guntur"},
]

# Trips keyed by email. user_id fields in original data are ignored;
# we assign the real DB user_id at insert time.
TRIPS_BY_EMAIL = {
    "pschandana2924@gmail.com": [
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.2,"duration":48,"cost":240,"purpose":"work","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.3,"duration":49,"cost":245,"purpose":"work","companions":2},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.1,"duration":47,"cost":235,"purpose":"work","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bike","distance":29.8,"duration":42,"cost":90,"purpose":"work","companions":0},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bike","distance":29.7,"duration":41,"cost":85,"purpose":"work","companions":0},
        {"origin":"Vijayawada","destination":"Amaravati","mode":"car","distance":22,"duration":30,"cost":200,"purpose":"work","companions":1},
        {"origin":"Amaravati","destination":"Vijayawada","mode":"car","distance":22,"duration":32,"cost":200,"purpose":"return","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30,"duration":45,"cost":250,"purpose":"meeting","companions":2},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30,"duration":50,"cost":250,"purpose":"return","companions":2},
        {"origin":"Vijayawada","destination":"Tenali","mode":"car","distance":35,"duration":55,"cost":300,"purpose":"personal","companions":3},
        {"origin":"Tenali","destination":"Vijayawada","mode":"car","distance":35,"duration":60,"cost":300,"purpose":"return","companions":3},
        {"origin":"Vijayawada","destination":"Mangalagiri","mode":"bike","distance":13,"duration":25,"cost":70,"purpose":"quick","companions":0},
        {"origin":"Mangalagiri","destination":"Vijayawada","mode":"bike","distance":13,"duration":27,"cost":70,"purpose":"return","companions":0},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bus","distance":30,"duration":70,"cost":60,"purpose":"low cost","companions":0},
        {"origin":"Guntur","destination":"Vijayawada","mode":"bus","distance":30,"duration":65,"cost":60,"purpose":"return","companions":0},
    ],
    "skhamidha08@gmail.com": [
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.2,"duration":48,"cost":240,"purpose":"work","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bike","distance":29.8,"duration":42,"cost":90,"purpose":"work","companions":0},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.5,"duration":50,"cost":250,"purpose":"work","companions":2},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30.1,"duration":47,"cost":245,"purpose":"work","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bike","distance":29.7,"duration":41,"cost":85,"purpose":"work","companions":0},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.3,"duration":52,"cost":240,"purpose":"return","companions":1},
        {"origin":"Guntur","destination":"Vijayawada","mode":"bike","distance":29.6,"duration":43,"cost":90,"purpose":"return","companions":0},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.4,"duration":51,"cost":250,"purpose":"return","companions":2},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.0,"duration":49,"cost":245,"purpose":"return","companions":1},
        {"origin":"Guntur","destination":"Vijayawada","mode":"bike","distance":29.9,"duration":44,"cost":88,"purpose":"return","companions":0},
    ],
    "bhavana2k5sistla@gmail.com": [
        {"origin":"Vijayawada","destination":"Amaravati","mode":"car","distance":22,"duration":30,"cost":200,"purpose":"work","companions":1},
        {"origin":"Amaravati","destination":"Vijayawada","mode":"car","distance":22,"duration":32,"cost":200,"purpose":"return","companions":1},
        {"origin":"Vijayawada","destination":"Guntur","mode":"car","distance":30,"duration":45,"cost":250,"purpose":"meeting","companions":2},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30,"duration":50,"cost":250,"purpose":"return","companions":2},
        {"origin":"Vijayawada","destination":"Tenali","mode":"car","distance":35,"duration":55,"cost":300,"purpose":"personal","companions":3},
        {"origin":"Tenali","destination":"Vijayawada","mode":"car","distance":35,"duration":60,"cost":300,"purpose":"return","companions":3},
        {"origin":"Vijayawada","destination":"Mangalagiri","mode":"bike","distance":13,"duration":25,"cost":70,"purpose":"quick","companions":0},
        {"origin":"Mangalagiri","destination":"Vijayawada","mode":"bike","distance":13,"duration":27,"cost":70,"purpose":"return","companions":0},
        {"origin":"Vijayawada","destination":"Guntur","mode":"bus","distance":30,"duration":70,"cost":60,"purpose":"low cost","companions":0},
        {"origin":"Guntur","destination":"Vijayawada","mode":"bus","distance":30,"duration":65,"cost":60,"purpose":"return","companions":0},
    ],
    "skrihana628@gmail.com": [
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.3,"duration":52,"cost":240,"purpose":"return","companions":1},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.4,"duration":51,"cost":250,"purpose":"return","companions":2},
        {"origin":"Guntur","destination":"Vijayawada","mode":"car","distance":30.2,"duration":50,"cost":245,"purpose":"return","companions":1},
        {"origin":"Guntur","destination":"Vijayawada","mode":"bike","distance":29.9,"duration":44,"cost":88,"purpose":"return","companions":0},
    ],
}

def get_or_create_user(cur, user_data):
    cur.execute("SELECT id FROM user WHERE email = ?", (user_data["email"],))
    row = cur.fetchone()
    if row:
        print(f"  User exists: {user_data['email']} -> id={row[0]}")
        return row[0]
    cur.execute(
        "INSERT INTO user (name, email, password, mobile, place, is_verified) VALUES (?,?,?,?,?,?)",
        (user_data["name"], user_data["email"], PLACEHOLDER_HASH,
         user_data["mobile"], user_data["place"], 1)
    )
    uid = cur.lastrowid
    print(f"  Created user: {user_data['email']} -> id={uid}")
    return uid

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get current max trip id to generate unique trip_no
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM trip")
    trip_counter = cur.fetchone()[0]

    now = datetime.utcnow()

    for user_data in USERS:
        email = user_data["email"]
        uid = get_or_create_user(cur, user_data)

        trips = TRIPS_BY_EMAIL.get(email, [])
        inserted = 0

        for i, t in enumerate(trips):
            trip_counter += 1
            trip_no = f"TRIP-{str(uuid.uuid4())[:8].upper()}"

            # Spread trips over past 30 days, one per ~2 days
            days_ago = len(trips) - i
            start_dt = now - timedelta(days=days_ago, hours=8)
            end_dt = start_dt + timedelta(minutes=t["duration"])
            trip_date = start_dt.date().isoformat()
            start_time_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_time_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            created_at = start_dt.strftime("%Y-%m-%d %H:%M:%S")

            origin = t["origin"]
            destination = t["destination"]
            o_coords = COORDS.get(origin, {"lat": 16.5062, "lng": 80.6480})
            d_coords = COORDS.get(destination, {"lat": 16.3067, "lng": 80.4365})
            route = make_route(origin, destination)

            cur.execute("""
                INSERT INTO trip (
                    trip_no, user_id, mode, purpose,
                    start_lat, start_lng, end_lat, end_lng,
                    start_time, end_time, trip_date,
                    distance, duration, cost, companions,
                    frequency, route, map_image, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trip_no, uid, t["mode"].capitalize(), t["purpose"],
                o_coords["lat"], o_coords["lng"],
                d_coords["lat"], d_coords["lng"],
                start_time_str, end_time_str, trip_date,
                t["distance"], t["duration"], t["cost"], t["companions"],
                1, route, None, created_at
            ))
            inserted += 1

        print(f"  -> Inserted {inserted} trips for {email}")

    conn.commit()
    conn.close()
    print("\nDone. All sample trips seeded successfully.")

if __name__ == "__main__":
    seed()
