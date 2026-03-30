# analyst.py

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.sql import func
from functools import wraps
import jwt
import datetime
import numpy as np

from models import db, User, Trip

analyst_bp = Blueprint("analyst", __name__)


# =============================
# CONFIG
# =============================

ANALYST_EMAIL = "analyst@smartcity.com"
ANALYST_PASSWORD = "SmartCity@123"

# =============================
# AUTH DECORATOR
# =============================

def analyst_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token missing"}), 401
        try:
            decoded = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )
            if decoded["role"] != "analyst":
                return jsonify({"error": "Unauthorized"}), 403
        except:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated

# =============================
# LOGIN
# =============================

@analyst_bp.route("/api/analyst/login", methods=["POST"])
def analyst_login():
    data = request.json

    if data["email"] == ANALYST_EMAIL and data["password"] == ANALYST_PASSWORD:

        token = jwt.encode({
            "role": "analyst",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        }, current_app.config["SECRET_KEY"], algorithm="HS256")

        return jsonify({"token": token})

    return jsonify({"error": "Invalid credentials"}), 401

# =============================
# DASHBOARD STATS
# =============================

@analyst_bp.route("/api/analyst/dashboard")
@analyst_required
def dashboard():

    total_trips = Trip.query.count()
    total_distance = db.session.query(func.sum(Trip.distance)).scalar() or 0
    total_cost = db.session.query(func.sum(Trip.cost)).scalar() or 0
    avg_duration = db.session.query(func.avg(Trip.duration)).scalar() or 0

    return jsonify({
        "total_trips": total_trips,
        "total_distance": round(total_distance, 2),
        "total_cost": round(total_cost, 2),
        "avg_duration": round(avg_duration, 2)
    })

# =============================
# REAL HEATMAP DATA (WEIGHTED)
# =============================
@analyst_bp.route("/api/analyst/heatmap", methods=["GET","POST"]) 
@analyst_required
def heatmap():

    lat = float(request.json["lat"])
    lng = float(request.json["lng"])
    radius = float(request.json.get("radius", 5))  # default 5km

    # Approx degree conversion
    delta = radius / 111  

    trips = Trip.query.filter(
        Trip.start_lat.between(lat - delta, lat + delta),
        Trip.start_lng.between(lng - delta, lng + delta)
    ).all()

    heat_data = {}
    mode_count = {}

    for trip in trips:

        key = (round(trip.start_lat, 3), round(trip.start_lng, 3))
        heat_data[key] = heat_data.get(key, 0) + 1

        mode_count[trip.mode] = mode_count.get(trip.mode, 0) + 1

    formatted_heat = [
        {"lat": k[0], "lng": k[1], "intensity": v}
        for k, v in heat_data.items()
    ]

    return jsonify({
        "heat_points": formatted_heat,
        "top_modes": mode_count
    })

# =============================
# PEAK HOUR BY REGION
# =============================
import requests

@analyst_bp.route("/api/analyst/search-region")
@analyst_required
def search_region():

    query = request.args.get("q")

    url = "https://nominatim.openstreetmap.org/search"

    response = requests.get(
        url,
        params={
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": 5
        },
        headers={
            "User-Agent": "SmartTripTracker/1.0"
        }
    )

    return jsonify(response.json())
from collections import defaultdict
from datetime import datetime
from sqlalchemy import func

from collections import defaultdict
from datetime import datetime
from sqlalchemy import func

@analyst_bp.route("/api/analyst/peak-hour", methods=["POST"])
@analyst_required
def peak_hour():

    data = request.get_json()

    lat = float(data.get("lat"))
    lng = float(data.get("lng"))
    selected_date = data.get("date")

    delta = 10 / 111

    query = Trip.query.filter(
        Trip.start_lat.between(lat - delta, lat + delta),
        Trip.start_lng.between(lng - delta, lng + delta)
    )

    # ✅ FIXED DATE FILTER
    if selected_date and str(selected_date).strip() != "":
        try:
            filter_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
            query = query.filter(
                Trip.trip_date == filter_date
            )
            print("Filtering by trip_date:", filter_date)
        except Exception as e:
            print("Date parsing error:", e)

    trips = query.all()

    print("Trips found:", len(trips))

    if not trips:
        return jsonify({
            "peak_hour": None,
            "trip_count": 0,
            "modes": {}
        })

    hour_count = defaultdict(int)
    mode_count = defaultdict(int)

    for trip in trips:

        if trip.mode:
            mode_count[trip.mode] += 1

        if not trip.start_time:
            continue

        try:
            raw_time = str(trip.start_time).strip()
            dt = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S.%f")
            hour = dt.hour
            hour_count[hour] += 1

        except Exception as e:
            print("Time parse error:", raw_time, e)

    if not hour_count:
        return jsonify({
            "peak_hour": None,
            "trip_count": 0,
            "modes": dict(mode_count)
        })

    peak_hour_value = max(hour_count, key=hour_count.get)

    return jsonify({
        "peak_hour": peak_hour_value,
        "trip_count": hour_count[peak_hour_value],
        "modes": dict(mode_count)
    })
# =============================
# MODE DISTRIBUTION
# =============================

@analyst_bp.route("/api/analyst/mode-distribution")
@analyst_required
def mode_distribution():

    modes = db.session.query(
        Trip.mode,
        func.count(Trip.mode)
    ).group_by(Trip.mode).all()

    return jsonify(dict(modes))

# =============================
# AI INSIGHTS (MODEL READY)
# =============================

from collections import defaultdict
from datetime import datetime
from sqlalchemy import func
import math

from ml_model import train_model, predict_next
from collections import defaultdict
from datetime import datetime

from ml_model import run_ai_engine
from datetime import datetime

@analyst_bp.route("/api/analyst/ai-insights", methods=["POST"])
@analyst_required
def ai_insights():

    data = request.get_json()

    lat = float(data.get("lat"))
    lng = float(data.get("lng"))
    selected_date = data.get("date")

    delta = 10 / 111

    query = Trip.query.filter(
        Trip.start_lat.between(lat - delta, lat + delta),
        Trip.start_lng.between(lng - delta, lng + delta)
    )

    if selected_date:
        filter_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        query = query.filter(Trip.trip_date == filter_date)

    trips = query.all()

    if not trips:
        return jsonify({"error": "No data found"})

    result = run_ai_engine(trips)

    return jsonify(result)

# =============================
# SMART CITY SIMULATION
# =============================
@analyst_bp.route("/api/analyst/ai-retrain", methods=["POST"])
@analyst_required
def ai_retrain():

    trips = Trip.query.all()

    hour_count = defaultdict(int)

    for trip in trips:
        dt = datetime.strptime(str(trip.start_time), "%Y-%m-%d %H:%M:%S.%f")
        hour_count[dt.hour] += 1

    hourly_values = [hour_count[h] for h in sorted(hour_count)]

    train_model(hourly_values)

    return jsonify({"status": "Model retrained"})
@analyst_bp.route("/api/analyst/simulation")
@analyst_required
def simulation():

    total_trips = Trip.query.count()
    projected_growth = total_trips * 1.18
    co2_projection = projected_growth * 0.21

    return jsonify({
        "projected_trips": projected_growth,
        "co2_projection": co2_projection,
        "policy_recommendation":
            "Increase public transport and optimize signal timings"
    })

@analyst_bp.route("/api/analyst/hourly-distribution", methods=["GET"])
@analyst_required
def hourly_distribution():

    from collections import defaultdict

    hour_count = defaultdict(int)

    trips = Trip.query.all()

    for trip in trips:
        try:
            dt = trip.start_time
            if isinstance(dt, str):
                from datetime import datetime
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S.%f")
            hour_count[dt.hour] += 1
        except:
            continue

    return jsonify(dict(sorted(hour_count.items())))

@analyst_bp.route("/api/analyst/analytics-data", methods=["POST"])
@analyst_required
def analytics_data():

    from collections import defaultdict
    from datetime import datetime

    data = request.get_json()

    lat = data.get("lat")
    lng = data.get("lng")
    from_date = data.get("from_date")
    to_date = data.get("to_date")

    query = Trip.query

    # Region filter (10km)
    if lat and lng:
        delta = 10 / 111
        query = query.filter(
            Trip.start_lat.between(float(lat) - delta, float(lat) + delta),
            Trip.start_lng.between(float(lng) - delta, float(lng) + delta)
        )

    # Date range filter
    if from_date:
        query = query.filter(Trip.trip_date >= from_date)
    if to_date:
        query = query.filter(Trip.trip_date <= to_date)

    trips = query.all()

    mode_count = defaultdict(int)
    hour_count = defaultdict(int)

    for trip in trips:

        if trip.mode:
            mode_count[trip.mode] += 1

        try:
            dt = trip.start_time
            if isinstance(dt, str):
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S.%f")
            hour_count[dt.hour] += 1
        except:
            continue

    return jsonify({
        "mode_distribution": dict(mode_count),
        "hourly_distribution": dict(sorted(hour_count.items()))
    })