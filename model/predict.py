import pickle
import numpy as np
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "flood_risk_model.pkl")

# load model once
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)


def predict_flood(rain_today, rain_3day, rain_7day, elevation):

    features = np.array([[
        float(rain_today),
        float(rain_3day),
        float(rain_7day),
        float(elevation)
    ]])

    prediction = model.predict(features)[0]

    if prediction == 0:
        return "LOW RISK"
    elif prediction == 1:
        return "MODERATE RISK"
    else:
        return "HIGH RISK"