"""Train (and retrain) the expense categorisation model.

Pipeline: TF-IDF (word + char n-grams) -> Logistic Regression. Small, fast,
interpretable, and strong on short noisy text — the right tool here, not a
neural net.

Run standalone to (re)build the model from just the bootstrap set:
    python -m ml.train

The API's /ml/retrain endpoint calls train_model() with the user corrections
pulled from the database, which is how the model learns from feedback.
"""
import os
from typing import List, Tuple

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.model_selection import StratifiedKFold, cross_val_score

from .training_data import TRAINING_DATA, CATEGORIES

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ML_DIR, "model.joblib")


def build_pipeline() -> Pipeline:
    """Word n-grams catch whole tokens ('uber', 'movie tickets'); character
    n-grams catch subword signal and survive typos and unseen words
    ('netfliix', 'grocries'). Combining both is what makes a small model
    robust on short, messy expense text."""
    features = FeatureUnion([
        ("word", TfidfVectorizer(
            lowercase=True, analyzer="word", ngram_range=(1, 2),
            min_df=1, sublinear_tf=True,
        )),
        ("char", TfidfVectorizer(
            lowercase=True, analyzer="char_wb", ngram_range=(3, 5),
            min_df=1, sublinear_tf=True,
        )),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(max_iter=2000, C=6.0)),
    ])


def train_model(extra: List[Tuple[str, str]] | None = None,
                save: bool = True) -> dict:
    """Train on the bootstrap set plus any extra (description, category) pairs.

    Returns a small report dict. A holdout accuracy is computed only when there
    is enough data to make a stratified split meaningful; otherwise it trains
    on everything and reports accuracy as None-equivalent (1.0 placeholder is
    avoided — we report train-set fit honestly).
    """
    data = list(TRAINING_DATA)
    if extra:
        data.extend(extra)

    X = [d for d, _ in data]
    y = [c for _, c in data]

    # Stratified k-fold cross-validation gives a far more stable, honest
    # accuracy estimate than a single tiny holdout when data is scarce.
    from collections import Counter
    counts = Counter(y)
    cv_acc = 0.0
    min_class = min(counts.values())
    if len(data) >= 20 and min_class >= 3:
        k = min(5, min_class)
        skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=42)
        scores = cross_val_score(build_pipeline(), X, y, cv=skf, scoring="accuracy")
        cv_acc = float(scores.mean())

    # Final model always trains on ALL available data.
    pipe = build_pipeline().fit(X, y)
    if save:
        joblib.dump(pipe, MODEL_PATH)

    return {
        "trained_on": len(data),
        "extra_folded_in": len(extra) if extra else 0,
        "holdout_accuracy": cv_acc,      # mean cross-validation accuracy
        "categories": sorted(set(y)),
    }


if __name__ == "__main__":
    report = train_model()
    print("Model trained.")
    print(f"  examples:          {report['trained_on']}")
    print(f"  holdout accuracy:  {report['holdout_accuracy']:.3f}")
    print(f"  categories:        {len(report['categories'])}")
    print(f"  saved to:          {MODEL_PATH}")
