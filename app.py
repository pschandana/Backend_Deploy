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
# 🔥 TEMP OTP STORAGE
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


    # Check existing user
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"msg": "User already exists"}), 400


    # Create user
    user = User(

        name=data["name"],
        email=data["email"],
        mobile=data["mobile"],   # 🔥 NEW
        place=data["place"],     # 🔥 NEW

        password=bcrypt.generate_password_hash(
            data["password"]
        ).decode("utf-8")

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

    msg.body = f"""
Hello 👋

Your OTP for Travel Tracker is:

{otp}

Valid for 5 minutes.

Do not share it.

Thanks ❤️
"""

    mail.send(msg)

@app.route("/api/send-otp", methods=["POST"])
def send_otp():

    data = request.get_json()

    email = data.get("email")

    if not email:
        return jsonify({"msg": "Email required"}), 400


    # Already registered?
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400


    otp = generate_otp()

    expiry = datetime.utcnow() + timedelta(minutes=5)


    # Store in memory (TEMP)
    otp_store[email] = {
        "otp": otp,
        "expires": expiry,
        "data": data   # full form
    }


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




    data = request.json

    email = data.get("email")


    if not email:
        return jsonify({"msg": "Email required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400

    # Generate OTP
    otp = str(random.randint(100000, 999999))


    # Expiry (5 min)
    expiry = datetime.utcnow() + timedelta(minutes=5)


    otp_store[email] = {
        "otp": otp,
        "expires": expiry,
        "data": data   # store registration data
    }


    try:

        msg = Message(
            "Your Smart Trip OTP",
            recipients=[email]
        )

        msg.body = f"""
Your OTP is: {otp}

Valid for 5 minutes.

Smart Trip Tracker Team
"""

        mail.send(msg)

        return jsonify({"msg": "OTP sent"})


    except Exception as e:

        print(e)
        return jsonify({"msg": "Failed to send OTP"}), 500
@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()

    email = data.get("email")
    otp = data.get("otp")


    if email not in otp_store:
        return jsonify({"msg": "OTP not found"}), 404


    record = otp_store[email]


    # Expired?
    if record["expires"] < datetime.utcnow():
        del otp_store[email]
        return jsonify({"msg": "OTP expired"}), 400


    # Wrong OTP?
    if record["otp"] != otp:
        return jsonify({"msg": "Invalid OTP"}), 400


    user_data = record["data"]


    # Create user now (ONLY AFTER VERIFY)
    hashed = bcrypt.generate_password_hash(
        user_data["password"]
    ).decode("utf-8")


    user = User(
        name=user_data["name"],
        email=user_data["email"],
        mobile=user_data["mobile"],
        place=user_data["place"],
        password=hashed
    )


    db.session.add(user)
    db.session.commit()


    # Cleanup OTP
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


# ---------------- PROFILE (Protected) ----------------
@app.route("/api/profile")
@jwt_required()
def profile():

    uid = get_jwt_identity()

    user = User.query.get(uid)


    return jsonify({

        "id": user.id,
        "name": user.name,
        "email": user.email,

        "mobile": user.mobile,   # 🔥
        "place": user.place,     # 🔥

        "photo": user.photo
    })


from datetime import datetime
import uuid
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route("/api/trips", methods=["POST"])
@jwt_required()
def create_trip():
    try:
        # ✅ FIX 1: Convert UID to int
        uid = int(get_jwt_identity())

        data = request.get_json()

        if not data:
            return jsonify({"msg": "No data provided"}), 400

        trip_no = "TRIP-" + str(uuid.uuid4())[:8]

        # ✅ SAFE datetime handling
        start_time = None
        end_time = None
        trip_date = None

        if data.get("start_time"):
            try:
                start_time = datetime.fromisoformat(
                    data.get("start_time").replace("Z", "")
                )
                trip_date = start_time.date()
            except:
                return jsonify({"msg": "Invalid start_time format"}), 400

        if data.get("end_time"):
            try:
                end_time = datetime.fromisoformat(
                    data.get("end_time").replace("Z", "")
                )
            except:
                return jsonify({"msg": "Invalid end_time format"}), 400

        # ✅ CREATE TRIP OBJECT
        trip = Trip(
            user_id=uid,
            trip_no=trip_no,

            start_lat=data.get("start_lat"),
            start_lng=data.get("start_lng"),

            end_lat=data.get("end_lat"),
            end_lng=data.get("end_lng"),

            purpose=data.get("purpose"),

            start_time=start_time,
            end_time=end_time,

            distance=data.get("distance"),
            duration=data.get("duration"),
            trip_date=trip_date,

            mode=data.get("mode"),

            cost=data.get("cost"),
            companions=data.get("companions"),

            frequency=data.get("frequency", 1),

            route=data.get("route"),   # (use json.dumps if needed)
            map_image=data.get("map_image"),
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

            "start_lat": t.start_lat,
            "start_lng": t.start_lng,

            "end_lat": t.end_lat,
            "end_lng": t.end_lng,

            "purpose": t.purpose,


            "start_time": t.start_time,
            "end_time": t.end_time,

            "distance": t.distance,
            "duration": t.duration,

            "mode": t.mode,

            "cost": t.cost,
            "companions": t.companions,

            "trip_date": t.trip_date,


            "frequency": t.frequency,

            "map_image": t.map_image,
            "route": t.route,
            
            "trip_no": t.trip_no,
        })

    return jsonify(data)

from geopy.geocoders import Nominatim


# ---------------- DASHBOARD ----------------
@app.route("/api/dashboard")
@jwt_required()
def dashboard():

    uid = get_jwt_identity()

    trips = Trip.query.filter_by(user_id=uid).all()

    total_trips = len(trips)

    total_distance = sum([t.distance or 0 for t in trips])
    total_cost = sum([t.cost or 0 for t in trips])


    # -------- MODE COUNT --------
    mode_count = {}

    for t in trips:
        if t.mode:
            mode_count[t.mode] = mode_count.get(t.mode, 0) + 1

    top_mode = max(mode_count, key=mode_count.get) if mode_count else None


    # -------- LOCATION CLUSTER --------
    area_count = {}

    for t in trips:

        if t.route:

            for p in t.route:

                lat = round(p["lat"], 3)
                lng = round(p["lng"], 3)

                key = f"{lat},{lng}"

                area_count[key] = area_count.get(key, 0) + 1


    most_area = None
    least_area = None


    if area_count:

        sorted_areas = sorted(
            area_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        most_area = sorted_areas[0]
        least_area = sorted_areas[-1]


    # -------- REVERSE GEOCODE --------
    geolocator = Nominatim(user_agent="travel_tracker")


    def get_area_name(lat, lng):

                      

            try:
                location = geolocator.reverse(
                    (lat, lng),
                    exactly_one=True,
                    timeout=10
                )

                if location and location.raw:

                    address = location.raw.get("address", {})

                    # Try best fields
                    area = (
                        address.get("suburb")
                        or address.get("neighbourhood")
                        or address.get("road")
                        or address.get("village")
                        or address.get("town")
                        or address.get("city")
                    )

                    city = (
                        address.get("city")
                        or address.get("town")
                        or address.get("state")
                    )

                    if area and city:
                        return f"{area}, {city}"

                    if city:
                        return city

            except Exception as e:
                print("Geo error:", e)

            return "Unknown Area"



    most_area_name = None
    least_area_name = None


    if most_area:

        lat, lng = most_area[0].split(",")

        lat = float(lat)
        lng = float(lng)

        most_area_name = get_area_name(lat, lng)



    if least_area:

        lat, lng = least_area[0].split(",")

        lat = float(lat)
        lng = float(lng)

        least_area_name = get_area_name(lat, lng)



    return jsonify({

        "total_trips": total_trips,
        "total_distance": round(total_distance, 2),
        "total_cost": round(total_cost, 2),

        "top_mode": top_mode,

        # 🔥 NEW
        "most_travelled_area": most_area_name,
        "least_travelled_area": least_area_name
    })

from collections import defaultdict


@app.route("/api/analytics")
@jwt_required()
def analytics():

    uid = get_jwt_identity()

    trips = Trip.query.filter_by(user_id=uid).all()

    monthly = defaultdict(lambda: {
        "trips": 0,
        "distance": 0,
        "cost": 0
    })


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

from datetime import datetime, timedelta
from collections import defaultdict


@app.route("/api/weekly-analytics")
@jwt_required()
def weekly_analytics():

    uid = get_jwt_identity()

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    trips = Trip.query.filter(
        Trip.user_id == uid,
        Trip.created_at >= week_ago
    ).all()


    total_trips = len(trips)
    total_distance = 0
    total_time = 0
    total_cost = 0


    mode_count = defaultdict(int)


    for t in trips:

        total_distance += t.distance or 0
        total_cost += t.cost or 0

        if t.duration:
            total_time += t.duration

        if t.mode:
            mode_count[t.mode] += 1


    # Mode %
    mode_percent = {}

    for k, v in mode_count.items():
        mode_percent[k] = round((v / total_trips) * 100, 1) if total_trips else 0


    # -------- SMART INSIGHTS --------

    insights = []


    # Cost saving
    if total_cost > 500:
        insights.append("💰 Consider public transport to reduce expenses")


    # Time optimization
    if total_time > 600:
        insights.append("⏱️ You spend a lot of time traveling. Try optimizing routes")


    # Fitness
    if mode_count.get("Walk", 0) > 5:
        insights.append("🏃 Great job! You are staying active")


    # Carbon footprint (rough estimate)
    carbon = 0

    for t in trips:
        if t.mode == "Car":
            carbon += (t.distance or 0) * 0.21
        if t.mode == "Bus":
            carbon += (t.distance or 0) * 0.08


    if carbon > 0:
        insights.append(f"🌱 Estimated CO₂: {round(carbon,2)} kg")


    return jsonify({

        "total_trips": total_trips,
        "total_distance": round(total_distance,2),
        "total_time": round(total_time,2),
        "total_cost": round(total_cost,2),

        "mode_percent": mode_percent,

        "insights": insights
    })

@app.route("/api/trips/<int:trip_id>", methods=["DELETE"])
@jwt_required()
def delete_trip(trip_id):

    uid = get_jwt_identity()

    trip = Trip.query.filter_by(
        id=trip_id,
        user_id=uid
    ).first()

    if not trip:
        return jsonify({"msg": "Not found"}), 404


    db.session.delete(trip)
    db.session.commit()

    return jsonify({"msg": "Trip deleted"})
import csv
from flask import Response


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

        query = query.filter(
            Trip.trip_date >= start_date,
            Trip.trip_date <= end_date
        )


    trips = query.all()


    output = io.StringIO()
    writer = csv.writer(output)


    writer.writerow([
        "Trip No",
        "Mode",
        "Distance",
        "Duration",
        "Cost",
        
        "Trip Date",
        "Start Time",
        "End Time"
        "Trip Purpose",
        
    ])


    for t in trips:

        writer.writerow([
            t.trip_no,
            t.mode,
            t.distance,
            t.duration,
            t.cost,
            t.trip_date,
            t.start_time,
            t.end_time,
            t.purpose
        ])


    csv_data = output.getvalue()
    output.close()


    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=trips_report.csv"
        }
    )

# Update Password
@app.route("/api/update-password", methods=["POST"])
@jwt_required()
def update_password():

    uid = get_jwt_identity()

    data = request.json

    user = User.query.get(uid)

    if not bcrypt.check_password_hash(
        user.password,
        data["old_password"]
    ):
        return jsonify({"msg": "Wrong password"}), 400


    new_hash = bcrypt.generate_password_hash(
        data["new_password"]
    ).decode("utf-8")


    user.password = new_hash

    db.session.commit()


    return jsonify({"msg": "Password updated"})


from werkzeug.utils import secure_filename


@app.route("/api/update-photo", methods=["POST"])
@jwt_required()
def update_photo():

    uid = get_jwt_identity()

    if "photo" not in request.files:
        return jsonify({"msg": "No file"}), 400


    file = request.files["photo"]

    filename = secure_filename(f"user_{uid}.jpg")

    path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(path)


    user = User.query.get(uid)

    user.photo = f"/uploads/{filename}"

    db.session.commit()


    return jsonify({"photo": user.photo})


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


    trips = Trip.query.filter(
        Trip.user_id == uid,
        Trip.trip_date >= start_date,
        Trip.trip_date <= end_date
    ).all()


    total_trips = len(trips)

    total_distance = 0
    total_time = 0
    total_cost = 0

    mode_count = {}

    carbon = 0


    for t in trips:

        total_distance += t.distance or 0
        total_time += t.duration or 0
        total_cost += t.cost or 0


        if t.mode:
            mode_count[t.mode] = mode_count.get(t.mode, 0) + 1


        # Carbon estimate
        if t.mode == "Car":
            carbon += (t.distance or 0) * 0.21

        elif t.mode == "Bus":
            carbon += (t.distance or 0) * 0.08

        elif t.mode == "Bike":
            carbon += (t.distance or 0) * 0.01

        elif t.mode == "Walk":
            carbon += 0


    # Mode %
    mode_percent = {}

    for k, v in mode_count.items():
        mode_percent[k] = round((v / total_trips) * 100, 1) if total_trips else 0


    # ---------- SMART INSIGHTS ----------
    insights = []


    # Cost insight
    if total_cost > 500:
        insights.append("💰 You are spending a lot on travel. Consider public transport.")


    # Time insight
    if total_time > 500:
        insights.append("⏱️ You spend a lot of time traveling. Try route optimization.")


    # Fitness insight
    if mode_count.get("Walk", 0) >= 3:
        insights.append("🏃 Great! You are staying active by walking.")


    # Carbon insight
    if carbon > 5:
        insights.append(f"🌱 High carbon footprint: {round(carbon,2)} kg CO₂")


    if carbon < 2 and total_trips > 0:
        insights.append("🌍 Eco-friendly travel habits. Keep it up!")


    # Transport suggestion
    if mode_count.get("Car", 0) > mode_count.get("Bus", 0):
        insights.append("🚍 Try using bus more often to save money & fuel.")


    return jsonify({

        "total_trips": total_trips,
        "total_distance": round(total_distance,2),
        "total_time": round(total_time,2),
        "total_cost": round(total_cost,2),

        "mode_percent": mode_percent,

        "insights": insights
    })

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

if __name__ == "__main__":

    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)


