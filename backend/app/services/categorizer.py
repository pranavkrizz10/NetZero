"""Loads the trained categorisation model and exposes predict().

The model is loaded lazily and cached in module state. If the model file is
missing (fresh checkout), we train it on the bootstrap set on demand so the
app never hard-fails on a missing artifact.

This feature is deliberately OFF the critical path: a wrong prediction just
gets corrected by the user in the form. The categoriser can never block or
break the settlement flow.
"""
import os
import threading

import joblib

from ml.train import MODEL_PATH, train_model

_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            if not os.path.exists(MODEL_PATH):
                train_model()  # cold-start: build from bootstrap set
            _model = joblib.load(MODEL_PATH)
    return _model


def reload_model():
    """Force a reload after retraining."""
    global _model
    with _lock:
        _model = None
    _load()


def predict(description: str):
    """Return (category, confidence). Confidence is the model's top class
    probability. Empty text falls back to 'Other'."""
    text = (description or "").strip()
    if not text:
        return "Other", 0.0
    model = _load()
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    best_idx = proba.argmax()
    return str(classes[best_idx]), float(proba[best_idx])
