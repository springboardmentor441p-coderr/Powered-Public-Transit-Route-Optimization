# backend/app/ml/create_dummy_models.py
"""Utility to create placeholder ML models for the ensemble predictor.
Generates:
- `gb_model.pkl` – a simple scikit-learn LinearRegression model trained on dummy data.
- `lstm.h5`    – a minimal Keras LSTM model (single LSTM layer + Dense) compiled.
These files allow the ensemble endpoint to load without requiring real training data.
"""
import os
import pickle
import numpy as np

from sklearn.linear_model import LinearRegression
import tensorflow as tf

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

# ----- Gradient Boosting placeholder (using LinearRegression) -----
X_dummy = np.arange(100).reshape(-1, 1)
y_dummy = X_dummy * 0.5 + 1.0
gb_model = LinearRegression()
gb_model.fit(X_dummy, y_dummy)
with open(os.path.join(MODEL_DIR, "gb_model.pkl"), "wb") as f:
    pickle.dump(gb_model, f)
print("Saved dummy gb_model.pkl")

# ----- LSTM placeholder -----
# Model expects input shape (batch, timesteps, features) – we use 24 timesteps, 3 features.
model = tf.keras.Sequential([
    tf.keras.layers.LSTM(8, input_shape=(24, 3), return_sequences=False),
    tf.keras.layers.Dense(1)
])
model.compile(optimizer="adam", loss="mse")
# No training – just save the architecture & weights.
model.save(os.path.join(MODEL_DIR, "lstm.h5"))
print("Saved dummy lstm.h5")

