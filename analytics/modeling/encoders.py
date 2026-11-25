"""
AI_RouteRanker - Categorical Encoders Module
Implements leakage-free One-Hot Encoding for Route and Daytype categories.
Fitted strictly on training partitions with handle_unknown='ignore'.
"""

from typing import List, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder


class RouteEncoder:
    """
    Leakage-free One-Hot Encoder for Route Identifiers.
    Vocabulary is learned strictly from training data.
    Unseen routes produce all-zero vectors without errors.
    """

    def __init__(self):
        self.encoder = OneHotEncoder(
            sparse_output=False,
            handle_unknown="ignore",
            dtype=np.float32,
        )
        self.is_fitted = False
        self.feature_names_: List[str] = []
        self.vocabulary_: List[str] = []

    def fit(self, routes: pd.Series) -> "RouteEncoder":
        """Fits vocabulary strictly on training route Series."""
        routes_df = routes.astype(str).to_frame(name="route")
        self.encoder.fit(routes_df)
        self.vocabulary_ = [str(cat) for cat in self.encoder.categories_[0]]
        self.feature_names_ = [f"route_{r}" for r in self.vocabulary_]
        self.is_fitted = True
        return self

    def transform(self, routes: pd.Series) -> pd.DataFrame:
        """Transforms route Series into binary one-hot DataFrame."""
        if not self.is_fitted:
            raise RuntimeError("RouteEncoder must be fitted before transforming!")
        routes_df = routes.astype(str).to_frame(name="route")
        encoded_array = self.encoder.transform(routes_df)
        return pd.DataFrame(
            encoded_array,
            columns=self.feature_names_,
            index=routes.index,
        )

    def fit_transform(self, routes: pd.Series) -> pd.DataFrame:
        return self.fit(routes).transform(routes)


class DaytypeEncoder:
    """
    Leakage-free One-Hot Encoder for CTA Daytype ('W', 'A', 'U').
    Categories are learned dynamically strictly from training data using categories='auto'.
    Guarantees non-ordinal treatment and handle_unknown='ignore'.
    """

    def __init__(self):
        self.encoder = OneHotEncoder(
            categories="auto",
            sparse_output=False,
            handle_unknown="ignore",
            dtype=np.float32,
        )
        self.is_fitted = False
        self.categories_: List[str] = []
        self.feature_names_: List[str] = []

    def fit(self, daytypes: pd.Series) -> "DaytypeEncoder":
        """Fits encoder strictly on training daytypes."""
        df = daytypes.astype(str).to_frame(name="daytype")
        self.encoder.fit(df)
        self.categories_ = [str(c) for c in self.encoder.categories_[0]]
        self.feature_names_ = [f"daytype_{d}" for d in self.categories_]
        self.is_fitted = True
        return self

    def transform(self, daytypes: pd.Series) -> pd.DataFrame:
        """Transforms daytype Series into binary indicators."""
        if not self.is_fitted:
            raise RuntimeError("DaytypeEncoder must be fitted before transforming!")
        df = daytypes.astype(str).to_frame(name="daytype")
        encoded_array = self.encoder.transform(df)
        return pd.DataFrame(
            encoded_array,
            columns=self.feature_names_,
            index=daytypes.index,
        )

    def fit_transform(self, daytypes: pd.Series) -> pd.DataFrame:
        return self.fit(daytypes).transform(daytypes)
