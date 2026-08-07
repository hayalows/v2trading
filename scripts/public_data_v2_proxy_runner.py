from __future__ import annotations

"""Compatibility runner for the public-data V2 proxy experiment.

Pandas 3 can represent text columns with StringDtype instead of object dtype. The
original experiment only classified object columns as categorical, causing symbols
like GBPUSD to reach the numeric median imputer. This runner patches only model
preprocessing; strategy rules, outcomes, features, thresholds, and cost assumptions
remain unchanged.
"""

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import public_data_v2_proxy as proxy


def build_model(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    cats = [c for c in features if not pd.api.types.is_numeric_dtype(frame[c])]
    nums = [c for c in features if c not in cats]

    pre = ColumnTransformer([
        (
            "num",
            Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("sc", StandardScaler()),
            ]),
            nums,
        ),
        (
            "cat",
            Pipeline([
                ("imp", SimpleImputer(strategy="most_frequent")),
                ("oh", OneHotEncoder(handle_unknown="ignore")),
            ]),
            cats,
        ),
    ])

    model = LGBMClassifier(
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=15,
        max_depth=4,
        min_child_samples=45,
        colsample_bytree=0.85,
        subsample=0.9,
        reg_alpha=0.6,
        reg_lambda=1.2,
        random_state=42,
        verbose=-1,
    )
    return Pipeline([("pre", pre), ("model", model)])


if __name__ == "__main__":
    proxy.build_model = build_model
    proxy.main()
