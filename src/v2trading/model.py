from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_pipeline(frame: pd.DataFrame, features: list[str], model: str = "lgbm") -> Pipeline:
    cats = [c for c in features if frame[c].dtype == "object" or str(frame[c].dtype).startswith("bool")]
    nums = [c for c in features if c not in cats]
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), nums),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cats),
    ])
    if model == "logit":
        estimator = LogisticRegression(max_iter=2000, C=0.5)
    elif model == "lgbm":
        estimator = LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=15, max_depth=4,
                                   min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
                                   reg_alpha=0.5, reg_lambda=1.0, random_state=42, verbose=-1)
    else:
        raise ValueError(f"Unknown model: {model}")
    return Pipeline([("pre", pre), ("model", estimator)])


def train_quantile_threshold(model: Pipeline, x_train: pd.DataFrame, quantile: float) -> float:
    p = model.predict_proba(x_train)[:, 1]
    return float(np.quantile(p, quantile))
