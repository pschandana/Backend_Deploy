import numpy as np
import os
import math
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
from collections import defaultdict

MODEL_PATH = "traffic_lstm.keras"
scaler = MinMaxScaler()


# =========================
# DATA PREPARATION
# =========================
def prepare_data(hour_counts):

    data = np.array(hour_counts).reshape(-1, 1)
    scaled = scaler.fit_transform(data)

    X, y = [], []

    for i in range(len(scaled) - 3):
        X.append(scaled[i:i+3])
        y.append(scaled[i+3])

    return np.array(X), np.array(y)


# =========================
# TRAIN MODEL
# =========================
def train_model(hour_counts):

    if len(hour_counts) < 5:
        return None, None

    X, y = prepare_data(hour_counts)

    model = keras.Sequential([
        layers.Input(shape=(3, 1)),
        layers.LSTM(50, activation="relu"),
        layers.Dense(1)
    ])

    model.compile(
        optimizer="adam",
        loss="mean_squared_error"
    )

    model.fit(X, y, epochs=40, verbose=0)

    predictions = model.predict(X, verbose=0)

    mse = mean_squared_error(y, predictions)
    rmse = math.sqrt(mse)

    model.save(MODEL_PATH)

    return model, round(rmse, 3)


# =========================
# PREDICT NEXT HOUR
# =========================
def predict_next(hour_counts):

    if not os.path.exists(MODEL_PATH):
        return None

    model = keras.models.load_model(
        MODEL_PATH,
        compile=False
    )

    data = np.array(hour_counts[-3:]).reshape(-1, 1)
    scaled = scaler.fit_transform(data)

    X = np.array([scaled])
    prediction = model.predict(X, verbose=0)

    predicted_value = scaler.inverse_transform(prediction)[0][0]

    return int(max(predicted_value, 0))


# =========================
# FULL AI ENGINE
# =========================
def run_ai_engine(trips):

    if not trips:
        return None

    hour_count = defaultdict(int)
    mode_count = defaultdict(int)
    total_distance = 0
    total_duration = 0

    for trip in trips:

        try:
            if isinstance(trip.start_time, str):

                # Case 1: "06:48"
                if ":" in trip.start_time and len(trip.start_time) <= 8:
                    hour = int(trip.start_time.split(":")[0])

                # Case 2: "2026-02-07 06:48:22.879323"
                else:
                    from datetime import datetime
                    dt = datetime.strptime(
                        trip.start_time,
                        "%Y-%m-%d %H:%M:%S.%f"
                    )
                    hour = dt.hour

            else:
                hour = trip.start_time.hour

            hour_count[hour] += 1

        except Exception as e:
            print("Time parse failed:", trip.start_time, e)       

        mode_count[trip.mode] += 1
        total_distance += trip.distance or 0
        total_duration += trip.duration or 0

    hourly_values = [hour_count[h] for h in sorted(hour_count)]

    model, accuracy = train_model(hourly_values)
    predicted_next = predict_next(hourly_values)

    total_trips = len(trips)

    congestion_score = min(100, sum(hourly_values))

    if congestion_score < 30:
        risk = "Low"
    elif congestion_score < 70:
        risk = "Medium"
    else:
        risk = "High"

    # =========================
    # CO2 Calculation
    # =========================
    co2_factor = {
        "Car": 0.21,
        "Bike": 0.09,
        "Bus": 0.05,
        "Train": 0.04,
        "Cycle": 0.0,
        "Walk": 0.0
    }

    total_co2 = 0
    for trip in trips:
        total_co2 += (trip.distance or 0) * co2_factor.get(trip.mode, 0.15)

    total_co2 = round(total_co2, 2)

    # =========================
    # RECOMMENDATION ENGINE
    # =========================
    recommendation = "Traffic stable."

    if mode_count.get("Bike", 0) > mode_count.get("Bus", 0):
        recommendation = "Bike usage is high. Increase public bus routes to reduce road load."

    if mode_count.get("Car", 0) > total_trips * 0.4:
        recommendation = "Private car usage dominant. Encourage carpool or public transport."

    if total_co2 > 20:
        recommendation += " High CO₂ detected. Promote eco-friendly transport."

    return {
        "model_type": "LSTM Time-Series Traffic Predictor",
        "model_accuracy_rmse": accuracy,
        "congestion_score": congestion_score,
        "risk_level": risk,
        "predicted_next_hour_traffic": predicted_next,
        "avg_distance": round(total_distance / total_trips, 2),
        "avg_duration": round(total_duration / total_trips, 2),
        "co2_emission": total_co2,
        "recommendation": recommendation,
        "mode_distribution": dict(mode_count),
        "metric_meanings": {
            "congestion_score": "Traffic intensity index based on historical hourly distribution.",
            "risk_level": "Traffic risk classification derived from congestion.",
            "predicted_next_hour_traffic": "AI predicted traffic volume for next hour.",
            "co2_emission": "Estimated total carbon emission (kg).",
            "model_accuracy_rmse": "Root Mean Square Error — lower value means better model performance."
        }
    }