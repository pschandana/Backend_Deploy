from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from flask_cors import CORS
import os
from flask import send_from_directory
from config import Config
from models import db, User, Trip
import uuid
from flask_mail import Mail, Message
import random
from datetime import datetime, timedelta
from analyst import analyst_bp

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


# ---------------- REGISTER ----------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"msg": "User already exists"}), 400
    user = User(
        name=data["name"],
        email=data["email"],
        mobile=data["mobile"],
        place=data["place"],
        password=bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "Registered successfully"})


def send_email(to, otp):
    msg = Message(
        "Your OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[to]
    )
    msg.body = f"""Hello 👋\n\nYour OTP for Travel Tracker is:\n\n{otp}\n\nValid for 5 minutes.\n\nDo not share it.\n\nThanks ❤️"""
    mail.send(msg)


@app.route("/api/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"msg": "Email required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)
    otp_store[email] = {"otp": otp, "expires": expiry, "data": data}
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
    user_data = record["data"]
    hashed = bcrypt.generate_password_hash(user_data["password"]).decode("utf-8")
    user = User(
        name=user_data["name"],
        email=user_data["email"],
        mobile=user_data["mobile"],
        place=user_data["place"],
        password=hashed
    )
    db.session.add(user)
    db.session.commit()
    del otp_store[email]
    return jsonify({"msg": "Registered successfully"}), 200


# ---------------- LOGIN ----------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user:
        return jsonify({"msg": "Invalid credentials"}), 401
    if not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"msg": "Invalid credentials"}), 401
    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token})


# ---------------- PROFILE ----------------
@app.route("/api/profile")
@jwt_required()
def profile():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "place": user.place,
        "photo": user.photo
    })


# ---------------- CREATE TRIP ----------------
@app.route("/api/trips", methods=["POST"])
@jwt_required()
def create_trip():
    try:
        uid = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"msg": "No data provided"}), 400
        trip_no = "TRIP-" + str(uuid.uuid4())[:8]
        start_time = None
        end_time = None
        trip_date = None
        if data.get("start_time"):
            try:
                start_time = datetime.fromisoformat(data.get("start_time").replace("Z", ""))
                trip_date = start_time.date()
            except:
                return jsonify({"msg": "Invalid start_time format"}), 400
        if data.get("end_time"):
            try:
                end_time = datetime.fromisoformat(data.get("end_time").replace("Z", ""))
            except:
                return jsonify({"msg": "Invalid end_time format"}), 400
        trip = Trip(
            user_id=uid, trip_no=trip_no,
            start_lat=data.get("start_lat"), start_lng=data.get("start_lng"),
            end_lat=data.get("end_lat"), end_lng=data.get("end_lng"),
            purpose=data.get("purpose"),
            start_time=start_time, end_time=end_time,
            distance=data.get("distance"), duration=data.get("duration"),
            trip_date=trip_date, mode=data.get("mode"),
            cost=data.get("cost"), companions=data.get("companions"),
            frequency=data.get("frequency", 1),
            route=data.get("route"), map_image=data.get("map_image"),
        )
        db.session.add(trip)
        db.session.commit()
        return jsonify({"msg": "Trip saved"}), 201
    except Exception as e:
        print("❌ ERROR in create_trip:", e)
        return jsonify({"msg": "Internal server error"}), 500


# ---------------- GET USER TRIPS ----------------
@app.route("/api/trips", methods=["GET"])
@jwt_required()
def get_trips():
    uid = int(get_jwt_identity())
    trips = Trip.query.filter_by(user_id=uid).all()
    data = []
    for t in trips:
        data.append({
            "id": t.id,
            "start_lat": t.start_lat, "start_lng": t.start_lng,
            "end_lat": t.end_lat, "end_lng": t.end_lng,
            "purpose": t.purpose,
            "start_time": t.start_time, "end_time": t.end_time,
            "distance": t.distance, "duration": t.duration,
            "mode": t.mode, "cost": t.cost, "companions": t.companions,
            "trip_date": t.trip_date, "frequency": t.frequency,
            "map_image": t.map_image, "route": t.route, "trip_no": t.trip_no,
        })
    return jsonify(data)


from geopy.geocoders import Nominatim
from collections import defaultdict


# ---------------- DASHBOARD ----------------
@app.route("/api/dashboard")
@jwt_required()
def dashboard():
    uid = get_jwt_identity()
    trips = Trip.query.filter_by(user_id=uid).all()
    total_trips = len(trips)
    total_distance = sum([t.distance or 0 for t in trips])
    total_cost = sum([t.cost or 0 for t in trips])
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
        sorted_areas = sorted(area_count.items(), key=lambda x: x[1], reverse=True)
        most_area = sorted_areas[0]
        least_area = sorted_areas[-1]
    geolocator = Nominatim(user_agent="travel_tracker")

    def get_area_name(lat, lng):
        try:
            location = geolocator.reverse((lat, lng), exactly_one=True, timeout=10)
            if location and location.raw:
                address = location.raw.get("address", {})
                area = (address.get("suburb") or address.get("neighbourhood") or
                        address.get("road") or address.get("village") or
                        address.get("town") or address.get("city"))
                city = address.get("city") or address.get("town") or address.get("state")
                if area and city:
                    return f"{area}, {city}"
                if city:
                    return city
        except Exception as e:
            print("Geo error:", e)
        return "Unknown Area"

    most_area_name = least_area_name = None
    if most_area:
        lat, lng = most_area[0].split(",")
        most_area_name = get_area_name(float(lat), float(lng))
    if least_area:
        lat, lng = least_area[0].split(",")
        least_area_name = get_area_name(float(lat), float(lng))
    return jsonify({
        "total_trips": total_trips,
        "total_distance": round(total_distance, 2),
        "total_cost": round(total_cost, 2),
        "top_mode": top_mode,
        "most_travelled_area": most_area_name,
        "least_travelled_area": least_area_name
    })


# ---------------- ANALYTICS ----------------
@app.route("/api/analytics")
@jwt_required()
def analytics():
    uid = get_jwt_identity()
    trips = Trip.query.filter_by(user_id=uid).all()
    monthly = defaultdict(lambda: {"trips": 0, "distance": 0, "cost": 0})
    for t in trips:
        if t.created_at:
            month = t.created_at.strftime("%Y-%m")
            monthly[month]["trips"] += 1
            monthly[month]["distance"] += t.distance or 0
            monthly[month]["cost"] += t.cost or 0
    data = []
    for k in sorted(monthly.keys()):
        data.append({
            "month": k,
            "trips": monthly[k]["trips"],
            "distance": round(monthly[k]["distance"], 2),
            "cost": round(monthly[k]["cost"], 2)
        })
    return jsonify(data)


# ---------------- WEEKLY ANALYTICS ----------------
@app.route("/api/weekly-analytics")
@jwt_required()
def weekly_analytics():
    uid = get_jwt_identity()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    trips = Trip.query.filter(Trip.user_id == uid, Trip.created_at >= week_ago).all()
    total_trips = len(trips)
    total_distance = total_time = total_cost = 0
    mode_count = defaultdict(int)
    for t in trips:
        total_distance += t.distance or 0
        total_cost += t.cost or 0
        if t.duration:
            total_time += t.duration
        if t.mode:
            mode_count[t.mode] += 1
    mode_percent = {k: round((v / total_trips) * 100, 1) if total_trips else 0 for k, v in mode_count.items()}
    insights = []
    if total_cost > 500:
        insights.append("💰 Consider public transport to reduce expenses")
    if total_time > 600:
        insights.append("⏱️ You spend a lot of time traveling. Try optimizing routes")
    if mode_count.get("Walk", 0) > 5:
        insights.append("🏃 Great job! You are staying active")
    carbon = sum((t.distance or 0) * (0.21 if t.mode == "Car" else 0.08 if t.mode == "Bus" else 0) for t in trips)
    if carbon > 0:
        insights.append(f"🌱 Estimated CO₂: {round(carbon,2)} kg")
    return jsonify({
        "total_trips": total_trips,
        "total_distance": round(total_distance, 2),
        "total_time": round(total_time, 2),
        "total_cost": round(total_cost, 2),
        "mode_percent": mode_percent,
        "insights": insights
    })


# ---------------- DELETE TRIP ----------------
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


# ---------------- EXPORT ----------------
import io
import csv
from flask import Response

@app.route("/api/export")
@jwt_required()
def export_trips():
    uid = get_jwt_identity()
    start = request.args.get("start")
    end = request.args.get("end")
    query = Trip.query.filter_by(user_id=uid)
    if start and end:
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()
        query = query.filter(Trip.trip_date >= start_date, Trip.trip_date <= end_date)
    trips = query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Trip No", "Mode", "Distance", "Duration", "Cost", "Trip Date", "Start Time", "End Time", "Trip Purpose"])
    for t in trips:
        writer.writerow([t.trip_no, t.mode, t.distance, t.duration, t.cost, t.trip_date, t.start_time, t.end_time, t.purpose])
    csv_data = output.getvalue()
    output.close()
    return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=trips_report.csv"})


# ---------------- UPDATE PASSWORD ----------------
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


# ---------------- UPDATE PHOTO ----------------
from werkzeug.utils import secure_filename

@app.route("/api/update-photo", methods=["POST"])
@jwt_required()
def update_photo():
    uid = get_jwt_identity()
    if "photo" not in request.files:
        return jsonify({"msg": "No file"}), 400
    file = request.files["photo"]
    filename = secure_filename(f"user_{uid}.jpg")
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    user = User.query.get(uid)
    user.photo = f"/uploads/{filename}"
    db.session.commit()
    return jsonify({"photo": user.photo})


# ---------------- RANGE ANALYTICS ----------------
@app.route("/api/range-analytics")
@jwt_required()
def range_analytics():
    uid = get_jwt_identity()
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"msg": "Start and end required"}), 400
    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    trips = Trip.query.filter(Trip.user_id == uid, Trip.trip_date >= start_date, Trip.trip_date <= end_date).all()
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
    mode_percent = {k: round((v / total_trips) * 100, 1) if total_trips else 0 for k, v in mode_count.items()}
    insights = []
    if total_cost > 500:
        insights.append("💰 You are spending a lot on travel. Consider public transport.")
    if total_time > 500:
        insights.append("⏱️ You spend a lot of time traveling. Try route optimization.")
    if mode_count.get("Walk", 0) >= 3:
        insights.append("🏃 Great! You are staying active by walking.")
    if carbon > 5:
        insights.append(f"🌱 High carbon footprint: {round(carbon,2)} kg CO₂")
    if carbon < 2 and total_trips > 0:
        insights.append("🌍 Eco-friendly travel habits. Keep it up!")
    if mode_count.get("Car", 0) > mode_count.get("Bus", 0):
        insights.append("🚍 Try using bus more often to save money & fuel.")
    return jsonify({
        "total_trips": total_trips,
        "total_distance": round(total_distance, 2),
        "total_time": round(total_time, 2),
        "total_cost": round(total_cost, 2),
        "mode_percent": mode_percent,
        "insights": insights
    })


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------- AUTO SEED ----------------
def run_seed():
    COORDS = {
        "Vijayawada":   {"lat": 16.5062, "lng": 80.6480},
        "Guntur":       {"lat": 16.3067, "lng": 80.4365},
        "Amaravati":    {"lat": 16.5150, "lng": 80.5160},
        "Tenali":       {"lat": 16.2432, "lng": 80.6400},
        "Mangalagiri":  {"lat": 16.4307, "lng": 80.5525},
    }

    def make_route(origin, dest):
        o = COORDS.get(origin, COORDS["Vijayawada"])
        d = COORDS.get(dest, COORDS["Guntur"])
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

    TRIPS_BY_EMAIL = {
        "pschandana2924@gmail.com": [
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30.2,"duration":48,"cost":240,"purpose":"work","companions":1},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30.3,"duration":49,"cost":245,"purpose":"work","companions":2},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30.1,"duration":47,"cost":235,"purpose":"work","companions":1},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Bike","distance":29.8,"duration":42,"cost":90,"purpose":"work","companions":0},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Bike","distance":29.7,"duration":41,"cost":85,"purpose":"work","companions":0},
            {"origin":"Vijayawada","destination":"Amaravati","mode":"Car","distance":22,"duration":30,"cost":200,"purpose":"work","companions":1},
            {"origin":"Amaravati","destination":"Vijayawada","mode":"Car","distance":22,"duration":32,"cost":200,"purpose":"return","companions":1},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30,"duration":45,"cost":250,"purpose":"meeting","companions":2},
            {"origin":"Guntur","destination":"Vijayawada","mode":"Car","distance":30,"duration":50,"cost":250,"purpose":"return","companions":2},
            {"origin":"Vijayawada","destination":"Tenali","mode":"Car","distance":35,"duration":55,"cost":300,"purpose":"personal","companions":3},
            {"origin":"Tenali","destination":"Vijayawada","mode":"Car","distance":35,"duration":60,"cost":300,"purpose":"return","companions":3},
            {"origin":"Vijayawada","destination":"Mangalagiri","mode":"Bike","distance":13,"duration":25,"cost":70,"purpose":"quick","companions":0},
            {"origin":"Mangalagiri","destination":"Vijayawada","mode":"Bike","distance":13,"duration":27,"cost":70,"purpose":"return","companions":0},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Bus","distance":30,"duration":70,"cost":60,"purpose":"low cost","companions":0},
            {"origin":"Guntur","destination":"Vijayawada","mode":"Bus","distance":30,"duration":65,"cost":60,"purpose":"return","companions":0},
        ],
        "skhamidha08@gmail.com": [
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30.2,"duration":48,"cost":240,"purpose":"work","companions":1},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Bike","distance":29.8,"duration":42,"cost":90,"purpose":"work","companions":0},
            {"origin":"Vijayawada","destination":"Guntur","mode":"Car","distance":30.5,"duration":50,"cost":250,"purpose":"work","companions":2},
            {"ori


# ---------------- AUTO SEED ----------------
def run_seed():
    COORDS = {
        "Vijayawada":   {"lat": 16.5062, "lng": 80.6480},
        "Guntur":       {"lat": 16.3067, "lng": 80.4365},
        "Amaravati":    {"lat": 16.5150, "lng": 80.5160},
        "Tenali":       {"lat": 16.2432, "lng": 80.6400},
        "Mangalagiri":  {"lat": 16.4307, "lng": 80.5525},
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
            user = User(
                name=u["name"], email=u["email"], password=pw_hash,
                mobile=u["mobile"], place=u["place"], is_verified=True
            )
            db.session.add(user)
            db.session.flush()

        if Trip.query.filter_by(user_id=user.id).count() == 0:
            trips = T.get(u["email"], [])
            for i, row in enumerate(trips):
                orig, dest, mode, dist, dur, cost, purpose, comp = row
                start_dt = now - timedelta(days=len(trips)-i, hours=8)
                end_dt = start_dt + timedelta(minutes=dur)
                o = COORDS.get(orig, COORDS["Vijayawada"])
                d = COORDS.get(dest, COORDS["Guntur"])
                db.session.add(Trip(
                    trip_no="TRIP-" + str(uuid.uuid4())[:8].upper(),
                    user_id=user.id, mode=mode, purpose=purpose,
                    start_lat=o["lat"], start_lng=o["lng"],
                    end_lat=d["lat"], end_lng=d["lng"],
                    start_time=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    end_time=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    trip_date=start_dt.date(),
                    distance=dist, duration=dur, cost=cost, companions=comp,
                    frequency=1, route=make_route(orig, dest),
                    map_image=None, created_at=start_dt
                ))

    db.session.commit()
    print("✅ Seed complete")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        run_seed()
    app.run(host="0.0.0.0", port=5000)
