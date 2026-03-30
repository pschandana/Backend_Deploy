from flask import Flask, request, jsonify, send_from_directory, Response
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from geopy.geocoders import Nominatim
from collections import defaultdict
from config import Config
from models import db, User, Trip
from analyst import analyst_bp
import os, uuid, random, io, csv
from datetime import datetime, timedelta

app = Flask(__name__)
app.config.from_object(Config)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CORS(app)
app.register_blueprint(analyst_bp)
mail = Mail(app)
otp_store = {}
db.init_app(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


def generate_otp():
    return str(random.randint(100000, 999999))


def send_email(to, otp):
    msg = Message("Your OTP Verification", sender=app.config['MAIL_USERNAME'], recipients=[to])
    msg.body = f"Hello\n\nYour OTP for Travel Tracker is: {otp}\n\nValid for 5 minutes.\n\nDo not share it."
    mail.send(msg)


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"msg": "User already exists"}), 400
    user = User(
        name=data["name"], email=data["email"],
        mobile=data["mobile"], place=data["place"],
        password=bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "Registered successfully"})


@app.route("/api/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"msg": "Email required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400
    otp = generate_otp()
    otp_store[email] = {"otp": otp, "expires": datetime.utcnow() + timedelta(minutes=5), "data": data}
    send_email(email, otp)
    return jsonify({"msg": "OTP sent"}), 200


@app.route("/api/resend-otp", methods=["POST"])
def resend_otp():
    data = request.get_json()
    email = data.get("email")
    if email not in otp_store:
        return jsonify({"msg": "OTP session expired"}), 404
    otp = generate_otp()
    otp_store[email]["otp"] = otp
    otp_store[email]["expires"] = datetime.utcnow() + timedelta(minutes=5)
    send_email(email, otp)
    return jsonify({"msg": "OTP resent"}), 200


@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")
    if email not in otp_store:
        return jsonify({"msg": "OTP not found"}), 404
    record = otp_store[email]
    if record["expires"] < datetime.utcnow():
        del otp_store[email]
        return jsonify({"msg": "OTP expired"}), 400
    if record["otp"] != otp:
        return jsonify({"msg": "Invalid OTP"}), 400
    ud = record["data"]
    user = User(
        name=ud["name"], email=ud["email"], mobile=ud["mobile"], place=ud["place"],
        password=bcrypt.generate_password_hash(ud["password"]).decode("utf-8")
    )
    db.session.add(user)
    db.session.commit()
    del otp_store[email]
    return jsonify({"msg": "Registered successfully"}), 200


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"msg": "Invalid credentials"}), 401
    return jsonify({"token": create_access_token(identity=str(user.id))})


@app.route("/api/profile")
@jwt_required()
def profile():
    user = User.query.get(get_jwt_identity())
    return jsonify({"id": user.id, "name": user.name, "email": user.email,
                    "mobile": user.mobile, "place": user.place, "photo": user.photo})


@app.route("/api/trips", methods=["POST"])
@jwt_required()
def create_trip():
    try:
        uid = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"msg": "No data provided"}), 400
        start_time = end_time = trip_date = None
        if data.get("start_time"):
            start_time = datetime.fromisoformat(data["start_time"].replace("Z", ""))
            trip_date = start_time.date()
        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"].replace("Z", ""))
        trip = Trip(
            user_id=uid, trip_no="TRIP-" + str(uuid.uuid4())[:8],
            start_lat=data.get("start_lat"), start_lng=data.get("start_lng"),
            end_lat=data.get("end_lat"), end_lng=data.get("end_lng"),
            purpose=data.get("purpose"), start_time=start_time, end_time=end_time,
            distance=data.get("distance"), duration=data.get("duration"),
            trip_date=trip_date, mode=data.get("mode"), cost=data.get("cost"),
            companions=data.get("companions"), frequency=data.get("frequency", 1),
            route=data.get("route"), map_image=data.get("map_image"),
        )
        db.session.add(trip)
        db.session.commit()
        return jsonify({"msg": "Trip saved"}), 201
    except Exception as e:
        print("ERROR in create_trip:", e)
        return jsonify({"msg": "Internal server error"}), 500


@app.route("/api/trips", methods=["GET"])
@jwt_required()
def get_trips():
    uid = int(get_jwt_identity())
    trips = Trip.query.filter_by(user_id=uid).all()
    return jsonify([{
        "id": t.id, "start_lat": t.start_lat, "start_lng": t.start_lng,
        "end_lat": t.end_lat, "end_lng": t.end_lng, "purpose": t.purpose,
        "start_time": t.start_time, "end_time": t.end_time,
        "distance": t.distance, "duration": t.duration, "mode": t.mode,
        "cost": t.cost, "companions": t.companions, "trip_date": t.trip_date,
        "frequency": t.frequency, "map_image": t.map_image,
        "route": t.route, "trip_no": t.trip_no,
    } for t in trips])


@app.route("/api/trips/<int:trip_id>", methods=["DELETE"])
@jwt_required()
def delete_trip(trip_id):
    uid = get_jwt_identity()
    trip = Trip.query.filter_by(id=trip_id, user_id=uid).first()
    if not trip:
        return jsonify({"msg": "Not found"}), 404
    db.session.delete(trip)
    db.session.commit()
    return jsonify({"msg": "Trip deleted"})


@app.route("/api/dashboard")
@jwt_required()
def dashboard():
    uid = get_jwt_identity()
    trips = Trip.query.filter_by(user_id=uid).all()
    total_trips = len(trips)
    total_distance = sum(t.distance or 0 for t in trips)
    total_cost = sum(t.cost or 0 for t in trips)
    mode_count = {}
    for t in trips:
        if t.mode:
            mode_count[t.mode] = mode_count.get(t.mode, 0) + 1
    top_mode = max(mode_count, key=mode_count.get) if mode_count else None
    area_count = {}
    for t in trips:
        if t.route:
            for p in t.route:
                key = f"{round(p['lat'],3)},{round(p['lng'],3)}"
                area_count[key] = area_count.get(key, 0) + 1
    most_area = least_area = None
    if area_count:
        s = sorted(area_count.items(), key=lambda x: x[1], reverse=True)
        most_area, least_area = s[0], s[-1]
    geolocator = Nominatim(user_agent="travel_tracker")

    def get_area_name(lat, lng):
        try:
            loc = geolocator.reverse((lat, lng), exactly_one=True, timeout=10)
            if loc and loc.raw:
                addr = loc.raw.get("address", {})
                area = addr.get("suburb") or addr.get("neighbourhood") or addr.get("road") or addr.get("village") or addr.get("town") or addr.get("city")
                city = addr.get("city") or addr.get("town") or addr.get("state")
                if area and city:
                    return f"{area}, {city}"
                if city:
                    return city
        except Exception as e:
            print("Geo error:", e)
        return "Unknown Area"

    most_name = least_name = None
    if most_area:
        la, ln = most_area[0].split(",")
        most_name = get_area_name(float(la), float(ln))
    if least_area:
        la, ln = least_area[0].split(",")
        least_name = get_area_name(float(la), float(ln))
    return jsonify({"total_trips": total_trips, "total_distance": round(total_distance, 2),
                    "total_cost": round(total_cost, 2), "top_mode": top_mode,
                    "most_travelled_area": most_name, "least_travelled_area": least_name})


@app.route("/api/analytics")
@jwt_required()
def analytics():
    uid = get_jwt_identity()
    trips = Trip.query.filter_by(user_id=uid).all()
    monthly = defaultdict(lambda: {"trips": 0, "distance": 0, "cost": 0})
    for t in trips:
        if t.created_at:
            m = t.created_at.strftime("%Y-%m")
            monthly[m]["trips"] += 1
            monthly[m]["distance"] += t.distance or 0
            monthly[m]["cost"] += t.cost or 0
    return jsonify([{"month": k, "trips": monthly[k]["trips"],
                     "distance": round(monthly[k]["distance"], 2),
                     "cost": round(monthly[k]["cost"], 2)} for k in sorted(monthly)])


@app.route("/api/weekly-analytics")
@jwt_required()
def weekly_analytics():
    uid = get_jwt_identity()
    now = datetime.utcnow()
    trips = Trip.query.filter(Trip.user_id == uid, Trip.created_at >= now - timedelta(days=7)).all()
    total_trips = len(trips)
    total_distance = total_time = total_cost = 0
    mode_count = defaultdict(int)
    for t in trips:
        total_distance += t.distance or 0
        total_cost += t.cost or 0
        total_time += t.duration or 0
        if t.mode:
            mode_count[t.mode] += 1
    mode_percent = {k: round((v/total_trips)*100, 1) if total_trips else 0 for k, v in mode_count.items()}
    insights = []
    if total_cost > 500:
        insights.append("Consider public transport to reduce expenses")
    if total_time > 600:
        insights.append("You spend a lot of time traveling. Try optimizing routes")
    carbon = sum((t.distance or 0) * (0.21 if t.mode == "Car" else 0.08 if t.mode == "Bus" else 0) for t in trips)
    if carbon > 0:
        insights.append(f"Estimated CO2: {round(carbon,2)} kg")
    return jsonify({"total_trips": total_trips, "total_distance": round(total_distance, 2),
                    "total_time": round(total_time, 2), "total_cost": round(total_cost, 2),
                    "mode_percent": mode_percent, "insights": insights})


@app.route("/api/range-analytics")
@jwt_required()
def range_analytics():
    uid = get_jwt_identity()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"msg": "Start and end required"}), 400
    trips = Trip.query.filter(Trip.user_id == uid,
                              Trip.trip_date >= datetime.fromisoformat(start).date(),
                              Trip.trip_date <= datetime.fromisoformat(end).date()).all()
    total_trips = len(trips)
    total_distance = total_time = total_cost = carbon = 0
    mode_count = {}
    for t in trips:
        total_distance += t.distance or 0
        total_time += t.duration or 0
        total_cost += t.cost or 0
        if t.mode:
            mode_count[t.mode] = mode_count.get(t.mode, 0) + 1
        if t.mode == "Car":
            carbon += (t.distance or 0) * 0.21
        elif t.mode == "Bus":
            carbon += (t.distance or 0) * 0.08
        elif t.mode == "Bike":
            carbon += (t.distance or 0) * 0.01
    mode_percent = {k: round((v/total_trips)*100, 1) if total_trips else 0 for k, v in mode_count.items()}
    insights = []
    if total_cost > 500:
        insights.append("You are spending a lot on travel. Consider public transport.")
    if total_time > 500:
        insights.append("You spend a lot of time traveling. Try route optimization.")
    if mode_count.get("Walk", 0) >= 3:
        insights.append("Great! You are staying active by walking.")
    if carbon > 5:
        insights.append(f"High carbon footprint: {round(carbon,2)} kg CO2")
    if carbon < 2 and total_trips > 0:
        insights.append("Eco-friendly travel habits. Keep it up!")
    if mode_count.get("Car", 0) > mode_count.get("Bus", 0):
        insights.append("Try using bus more often to save money & fuel.")
    return jsonify({"total_trips": total_trips, "total_distance": round(total_distance, 2),
                    "total_time": round(total_time, 2), "total_cost": round(total_cost, 2),
                    "mode_percent": mode_percent, "insights": insights})


@app.route("/api/export")
@jwt_required()
def export_trips():
    uid = get_jwt_identity()
    start = request.args.get("start")
    end = request.args.get("end")
    query = Trip.query.filter_by(user_id=uid)
    if start and end:
        query = query.filter(Trip.trip_date >= datetime.fromisoformat(start).date(),
                             Trip.trip_date <= datetime.fromisoformat(end).date())
    trips = query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Trip No", "Mode", "Distance", "Duration", "Cost", "Trip Date", "Start Time", "End Time", "Trip Purpose"])
    for t in trips:
        writer.writerow([t.trip_no, t.mode, t.distance, t.duration, t.cost, t.trip_date, t.start_time, t.end_time, t.purpose])
    csv_data = output.getvalue()
    output.close()
    return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=trips_report.csv"})


@app.route("/api/update-password", methods=["POST"])
@jwt_required()
def update_password():
    uid = get_jwt_identity()
    data = request.json
    user = User.query.get(uid)
    if not bcrypt.check_password_hash(user.password, data["old_password"]):
        return jsonify({"msg": "Wrong password"}), 400
    user.password = bcrypt.generate_password_hash(data["new_password"]).decode("utf-8")
    db.session.commit()
    return jsonify({"msg": "Password updated"})


@app.route("/api/update-photo", methods=["POST"])
@jwt_required()
def update_photo():
    uid = get_jwt_identity()
    if "photo" not in request.files:
        return jsonify({"msg": "No file"}), 400
    file = request.files["photo"]
    filename = secure_filename(f"user_{uid}.jpg")
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    user = User.query.get(uid)
    user.photo = f"/uploads/{filename}"
    db.session.commit()
    return jsonify({"photo": user.photo})


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------- AUTO SEED ----------------
def run_seed():
    COORDS = {
        "Vijayawada":  {"lat": 16.5062, "lng": 80.6480},
        "Guntur":      {"lat": 16.3067, "lng": 80.4365},
        "Amaravati":   {"lat": 16.5150, "lng": 80.5160},
        "Tenali":      {"lat": 16.2432, "lng": 80.6400},
        "Mangalagiri": {"lat": 16.4307, "lng": 80.5525},
    }

    def make_route(o_name, d_name):
        o = COORDS.get(o_name, COORDS["Vijayawada"])
        d = COORDS.get(d_name, COORDS["Guntur"])
        return [
            {"lat": o["lat"], "lng": o["lng"]},
            {"lat": round((o["lat"]+d["lat"])/2, 4), "lng": round((o["lng"]+d["lng"])/2, 4)},
            {"lat": d["lat"], "lng": d["lng"]},
        ]

    USERS = [
        {"email": "pschandana2924@gmail.com", "name": "Chandana", "mobile": "9000000001", "place": "Vijayawada"},
        {"email": "skhamidha08@gmail.com",    "name": "Khamidha", "mobile": "9000000002", "place": "Vijayawada"},
        {"email": "bhavana2k5sistla@gmail.com","name": "Bhavana",  "mobile": "9000000003", "place": "Vijayawada"},
        {"email": "skrihana628@gmail.com",    "name": "Krihana",  "mobile": "9000000004", "place": "Guntur"},
    ]

    T = {
        "pschandana2924@gmail.com": [
            ("Vijayawada","Guntur","Car",30.2,48,240,"work",1),
            ("Vijayawada","Guntur","Car",30.3,49,245,"work",2),
            ("Vijayawada","Guntur","Car",30.1,47,235,"work",1),
            ("Vijayawada","Guntur","Bike",29.8,42,90,"work",0),
            ("Vijayawada","Guntur","Bike",29.7,41,85,"work",0),
            ("Vijayawada","Amaravati","Car",22,30,200,"work",1),
            ("Amaravati","Vijayawada","Car",22,32,200,"return",1),
            ("Vijayawada","Guntur","Car",30,45,250,"meeting",2),
            ("Guntur","Vijayawada","Car",30,50,250,"return",2),
            ("Vijayawada","Tenali","Car",35,55,300,"personal",3),
            ("Tenali","Vijayawada","Car",35,60,300,"return",3),
            ("Vijayawada","Mangalagiri","Bike",13,25,70,"quick",0),
            ("Mangalagiri","Vijayawada","Bike",13,27,70,"return",0),
            ("Vijayawada","Guntur","Bus",30,70,60,"low cost",0),
            ("Guntur","Vijayawada","Bus",30,65,60,"return",0),
        ],
        "skhamidha08@gmail.com": [
            ("Vijayawada","Guntur","Car",30.2,48,240,"work",1),
            ("Vijayawada","Guntur","Bike",29.8,42,90,"work",0),
            ("Vijayawada","Guntur","Car",30.5,50,250,"work",2),
            ("Vijayawada","Guntur","Car",30.1,47,245,"work",1),
            ("Vijayawada","Guntur","Bike",29.7,41,85,"work",0),
            ("Guntur","Vijayawada","Car",30.3,52,240,"return",1),
            ("Guntur","Vijayawada","Bike",29.6,43,90,"return",0),
            ("Guntur","Vijayawada","Car",30.4,51,250,"return",2),
            ("Guntur","Vijayawada","Car",30.0,49,245,"return",1),
            ("Guntur","Vijayawada","Bike",29.9,44,88,"return",0),
        ],
        "bhavana2k5sistla@gmail.com": [
            ("Vijayawada","Amaravati","Car",22,30,200,"work",1),
            ("Amaravati","Vijayawada","Car",22,32,200,"return",1),
            ("Vijayawada","Guntur","Car",30,45,250,"meeting",2),
            ("Guntur","Vijayawada","Car",30,50,250,"return",2),
            ("Vijayawada","Tenali","Car",35,55,300,"personal",3),
            ("Tenali","Vijayawada","Car",35,60,300,"return",3),
            ("Vijayawada","Mangalagiri","Bike",13,25,70,"quick",0),
            ("Mangalagiri","Vijayawada","Bike",13,27,70,"return",0),
            ("Vijayawada","Guntur","Bus",30,70,60,"low cost",0),
            ("Guntur","Vijayawada","Bus",30,65,60,"return",0),
        ],
        "skrihana628@gmail.com": [
            ("Guntur","Vijayawada","Car",30.3,52,240,"return",1),
            ("Guntur","Vijayawada","Car",30.4,51,250,"return",2),
            ("Guntur","Vijayawada","Car",30.2,50,245,"return",1),
            ("Guntur","Vijayawada","Bike",29.9,44,88,"return",0),
        ],
    }

    pw_hash = bcrypt.generate_password_hash("123456").decode("utf-8")
    now = datetime.utcnow()

    for u in USERS:
        user = User.query.filter_by(email=u["email"]).first()
        if not user:
            user = User(name=u["name"], email=u["email"], password=pw_hash,
                        mobile=u["mobile"], place=u["place"], is_verified=True)
            db.session.add(user)
            db.session.flush()

        if Trip.query.filter_by(user_id=user.id).count() == 0:
            rows = T.get(u["email"], [])
            for i, row in enumerate(rows):
                orig, dest, mode, dist, dur, cost, purpose, comp = row
                start_dt = now - timedelta(days=len(rows)-i, hours=8)
                o = COORDS.get(orig, COORDS["Vijayawada"])
                d = COORDS.get(dest, COORDS["Guntur"])
                db.session.add(Trip(
                    trip_no="TRIP-" + str(uuid.uuid4())[:8].upper(),
                    user_id=user.id, mode=mode, purpose=purpose,
                    start_lat=o["lat"], start_lng=o["lng"],
                    end_lat=d["lat"], end_lng=d["lng"],
                    start_time=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    end_time=(start_dt + timedelta(minutes=dur)).strftime("%Y-%m-%dT%H:%M:%S"),
                    trip_date=start_dt.date(), distance=dist, duration=dur,
                    cost=cost, companions=comp, frequency=1,
                    route=make_route(orig, dest), map_image=None, created_at=start_dt
                ))

    db.session.commit()
    print("Seed complete")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        run_seed()
    app.run(host="0.0.0.0", port=5000)
