"""
Predictive Modeling & Uplift Framework

Includes conversion prediction and uplift modeling to identify
persuadable customers for optimal campaign targeting.

Fixes applied (v2):
- LabelEncoder replaced with OneHotEncoder for nominal categorical features
  (gender, geography, income_band, channel) — LabelEncoder implied false
  ordinal relationships that corrupted logistic regression coefficients.
- income_band handled as a proper ordinal feature with explicit mapping.
- Hardcoded $150 revenue multiplier removed; actual mean revenue passed as a parameter.
- Logging replaces bare print statements.
- Input validation added throughout.
"""

import logging
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OrdinalEncoder, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
)
from typing import Tuple, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ConversionPredictor:
    """
    Logistic regression model for conversion prediction with
    proper feature encoding and business interpretation.
    """

    # income_band ordered from lowest to highest
    INCOME_BAND_ORDER = [["<30K", "30-50K", "50-75K", "75-100K", "100-150K", ">150K"]]

    def __init__(self, random_state: int = 42):
        """
        Initialize conversion predictor.

        Parameters
        ----------
        random_state : int
            Random seed for reproducibility.
        """
        self.random_state = random_state
        self.pipeline: Optional[Pipeline] = None
        self.feature_names_out_: List[str] = []
        logger.info("ConversionPredictor initialised (random_state=%d)", random_state)

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create derived features before encoding.

        Parameters
        ----------
        df : pd.DataFrame
            Raw input dataframe.

        Returns
        -------
        pd.DataFrame
            DataFrame enriched with engineered features.
        """
        features = df.copy()

        features["spend_per_product"] = (
            features["historical_spend"] / (features["product_count"] + 1)
        )

        features["high_value"] = (
            features["historical_spend"] > features["historical_spend"].median()
        ).astype(int)

        features["engagement_score"] = (
            (features["customer_tenure"] / 120) * 0.4
            + (features["product_count"] / 5) * 0.3
            + (features["historical_spend"] / features["historical_spend"].max()) * 0.3
        )

        return features

    # ------------------------------------------------------------------
    # Build preprocessing pipeline
    # ------------------------------------------------------------------

    def _build_pipeline(self) -> Pipeline:
        """
        Build an sklearn Pipeline with correct encoders per feature type.

        Encoding strategy:
        - Nominal categoricals (gender, geography, channel): OneHotEncoder
          — no ordinal relationship implied.
        - Ordinal categorical (income_band): OrdinalEncoder with explicit
          category order so coefficients are monotone.
        - Numerics: StandardScaler.

        Returns
        -------
        sklearn.pipeline.Pipeline
        """
        numeric_features = [
            "age",
            "customer_tenure",
            "historical_spend",
            "product_count",
            "spend_per_product",
            "engagement_score",
        ]

        # Nominal — no ordering; OneHotEncoder prevents implied ordinality
        nominal_features = ["gender", "geography", "channel"]

        # Ordinal — explicit ordering matters for the coefficient direction
        ordinal_features = ["income_band"]

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", StandardScaler(), numeric_features),
                (
                    "nom",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    nominal_features,
                ),
                (
                    "ord",
                    OrdinalEncoder(
                        categories=self.INCOME_BAND_ORDER,
                        handle_unknown="use_encoded_value",
                        unknown_value=-1,
                    ),
                    ordinal_features,
                ),
            ],
            remainder="drop",
        )

        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        random_state=self.random_state,
                        class_weight="balanced",
                        solver="lbfgs",
                    ),
                ),
            ]
        )
        return pipeline

    # ------------------------------------------------------------------
    # Training data preparation
    # ------------------------------------------------------------------

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        target_col: str = "converted",
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Engineer features and return (X, y) ready for training.

        Parameters
        ----------
        df : pd.DataFrame
            Raw input dataframe.
        target_col : str
            Name of the binary target column.

        Returns
        -------
        tuple of (pd.DataFrame, pd.Series)
        """
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataframe.")

        df_feat = self.engineer_features(df)

        feature_cols = [
            "age",
            "customer_tenure",
            "historical_spend",
            "product_count",
            "spend_per_product",
            "engagement_score",
            "gender",
            "geography",
            "income_band",
            "channel",
        ]

        missing = [c for c in feature_cols if c not in df_feat.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {missing}")

        X = df_feat[feature_cols].copy()
        y = df_feat[target_col]
        return X, y

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
    ) -> Dict:
        """
        Train the logistic regression pipeline.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix (raw, before encoding).
        y : pd.Series
            Binary target vector.
        test_size : float
            Proportion of data held out for evaluation.

        Returns
        -------
        dict
            Training metrics and test-set predictions.
        """
        if len(X) == 0:
            raise ValueError("Training data is empty.")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=self.random_state,
            stratify=y,
        )

        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X_train, y_train)

        # Store output feature names for interpretation
        try:
            preprocessor = self.pipeline.named_steps["preprocessor"]
            self.feature_names_out_ = preprocessor.get_feature_names_out().tolist()
        except Exception:
            self.feature_names_out_ = []

        y_pred_proba = self.pipeline.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)

        roc_auc = roc_auc_score(y_test, y_pred_proba)
        avg_precision = average_precision_score(y_test, y_pred_proba)

        cv_scores = cross_val_score(
            self._build_pipeline(), X_train, y_train, cv=5, scoring="roc_auc"
        )

        logger.info(
            "Training complete — ROC-AUC: %.3f | CV mean: %.3f ± %.3f",
            roc_auc, cv_scores.mean(), cv_scores.std(),
        )

        return {
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train,
            "y_test": y_test,
            "y_pred_proba": y_pred_proba,
            "y_pred": y_pred,
            "roc_auc": roc_auc,
            "avg_precision": avg_precision,
            "cv_mean": cv_scores.mean(),
            "cv_std": cv_scores.std(),
        }

    # ------------------------------------------------------------------
    # Feature importance
    # ------------------------------------------------------------------

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Return logistic regression coefficients as a feature importance table.

        Returns
        -------
        pd.DataFrame
            Sorted by absolute coefficient value (descending).
        """
        if self.pipeline is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")

        coef = self.pipeline.named_steps["classifier"].coef_[0]
        names = (
            self.feature_names_out_
            if self.feature_names_out_
            else [f"feature_{i}" for i in range(len(coef))]
        )

        importance_df = pd.DataFrame(
            {
                "feature": names,
                "coefficient": coef,
                "abs_coefficient": np.abs(coef),
            }
        ).sort_values("abs_coefficient", ascending=False)

        return importance_df

    def interpret_coefficients(self, top_n: int = 10) -> str:
        """
        Translate model coefficients into business language.

        Parameters
        ----------
        top_n : int
            Number of top features to show.

        Returns
        -------
        str
            Business interpretation string.
        """
        importance = self.get_feature_importance().head(top_n)
        lines = ["🔍 KEY DRIVERS OF CONVERSION:\n"]
        for _, row in importance.iterrows():
            direction = "increases" if row["coefficient"] > 0 else "decreases"
            magnitude = "significantly" if row["abs_coefficient"] > 0.5 else "moderately"
            lines.append(
                f"   • {row['feature']}: {magnitude} {direction} conversion "
                f"(coef: {row['coefficient']:.3f})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict conversion probability for new data.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix (same columns as training data, before encoding).

        Returns
        -------
        np.ndarray
            Predicted probabilities (P(conversion=1)).
        """
        if self.pipeline is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")
        return self.pipeline.predict_proba(X)[:, 1]


# ===========================================================================
# Uplift modeler
# ===========================================================================

class UpliftModeler:
    """
    Two-model uplift approach to identify persuadable customers.
    """

    def __init__(self, random_state: int = 42):
        """
        Initialize uplift modeler.

        Parameters
        ----------
        random_state : int
            Random seed for reproducibility.
        """
        self.random_state = random_state
        self.treatment_model = ConversionPredictor(random_state)
        self.control_model = ConversionPredictor(random_state)
        logger.info("UpliftModeler initialised")

    def train_uplift_models(self, df: pd.DataFrame) -> Dict:
        """
        Train separate models for treatment and control groups.

        Parameters
        ----------
        df : pd.DataFrame
            Full dataset with treatment_group (0/1) and converted (0/1).

        Returns
        -------
        dict
            Training metrics for both models.
        """
        treatment_data = df[df["treatment_group"] == 1].copy()
        control_data = df[df["treatment_group"] == 0].copy()

        if len(treatment_data) < 100 or len(control_data) < 100:
            logger.warning(
                "Small group sizes: treatment=%d, control=%d. "
                "Results may be unreliable.",
                len(treatment_data), len(control_data),
            )

        logger.info("Training treatment model (n=%d)…", len(treatment_data))
        X_treat, y_treat = self.treatment_model.prepare_training_data(treatment_data)
        treatment_results = self.treatment_model.train(X_treat, y_treat)

        logger.info("Training control model (n=%d)…", len(control_data))
        X_ctrl, y_ctrl = self.control_model.prepare_training_data(control_data)
        control_results = self.control_model.train(X_ctrl, y_ctrl)

        logger.info(
            "Uplift models trained — Treatment AUC: %.3f | Control AUC: %.3f",
            treatment_results["roc_auc"], control_results["roc_auc"],
        )

        return {
            "treatment_results": treatment_results,
            "control_results": control_results,
        }

    def calculate_uplift(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate uplift score for each customer.

        Uplift = P(convert | treatment) - P(convert | control)

        Parameters
        ----------
        df : pd.DataFrame
            Customer data (must include all feature columns).

        Returns
        -------
        pd.DataFrame
            Original dataframe with uplift scores appended.
        """
        X, _ = self.treatment_model.prepare_training_data(df)

        treatment_prob = self.treatment_model.predict_proba(X)
        control_prob = self.control_model.predict_proba(X)

        result = df.copy()
        result["treatment_prob"] = treatment_prob
        result["control_prob"] = control_prob
        result["uplift_score"] = treatment_prob - control_prob

        logger.info(
            "Uplift calculated — mean=%.4f, positive_pct=%.1f%%",
            result["uplift_score"].mean(),
            (result["uplift_score"] > 0).mean() * 100,
        )
        return result

    def segment_customers(self, df_with_uplift: pd.DataFrame) -> pd.DataFrame:
        """
        Segment customers into the four classic uplift quadrants.

        Persuadables  : High treatment prob, low control prob  → TARGET
        Sure Things   : High treatment prob, high control prob  → deprioritise
        Lost Causes   : Low treatment prob, low control prob    → suppress
        Sleeping Dogs : Low treatment prob, high control prob   → NEVER target

        Parameters
        ----------
        df_with_uplift : pd.DataFrame
            DataFrame with treatment_prob and control_prob columns.

        Returns
        -------
        pd.DataFrame
            DataFrame with segment and recommendation columns appended.
        """
        df = df_with_uplift.copy()
        treat_med = df["treatment_prob"].median()
        ctrl_med = df["control_prob"].median()

        conditions = [
            (df["treatment_prob"] > treat_med) & (df["control_prob"] <= ctrl_med),
            (df["treatment_prob"] > treat_med) & (df["control_prob"] > ctrl_med),
            (df["treatment_prob"] <= treat_med) & (df["control_prob"] <= ctrl_med),
            (df["treatment_prob"] <= treat_med) & (df["control_prob"] > ctrl_med),
        ]
        segments = ["Persuadables", "Sure Things", "Lost Causes", "Sleeping Dogs"]
        recommendations = {
            "Persuadables": "TARGET — high incremental impact",
            "Sure Things": "OPTIONAL — will convert anyway",
            "Lost Causes": "SUPPRESS — low conversion probability",
            "Sleeping Dogs": "NEVER TARGET — campaign hurts conversion",
        }

        df["segment"] = np.select(conditions, segments, default="Unknown")
        df["recommendation"] = df["segment"].map(recommendations)

        segment_counts = df["segment"].value_counts()
        logger.info("Customer segments: %s", segment_counts.to_dict())
        return df

    def compare_to_response_model(
        self,
        df_with_segments: pd.DataFrame,
        budget_constraint: float = 0.3,
        mean_revenue_per_uplift_unit: Optional[float] = None,
    ) -> Dict:
        """
        Compare uplift targeting against traditional response modelling.

        Parameters
        ----------
        df_with_segments : pd.DataFrame
            DataFrame with segment and uplift scores.
        budget_constraint : float
            Fraction of customers that can be targeted (default 0.30).
        mean_revenue_per_uplift_unit : float, optional
            Average revenue per unit of uplift score.  When None, the mean
            of actual revenue_generated is used if the column exists;
            otherwise an error is raised to prevent silent assumptions.

        Returns
        -------
        dict
            Comparison metrics for both targeting strategies.
        """
        if mean_revenue_per_uplift_unit is None:
            if "revenue_generated" in df_with_segments.columns:
                converters = df_with_segments[df_with_segments.get("converted", pd.Series(dtype=int)) == 1]
                mean_revenue_per_uplift_unit = (
                    converters["revenue_generated"].mean()
                    if len(converters) > 0
                    else df_with_segments["revenue_generated"].mean()
                )
                logger.info(
                    "mean_revenue_per_uplift_unit derived from data: %.2f",
                    mean_revenue_per_uplift_unit,
                )
            else:
                raise ValueError(
                    "mean_revenue_per_uplift_unit must be supplied explicitly "
                    "when revenue_generated is not in the dataframe. "
                    "Hardcoding a magic number is not acceptable."
                )

        n_target = int(len(df_with_segments) * budget_constraint)

        response_targets = df_with_segments.nlargest(n_target, "treatment_prob")
        response_revenue = response_targets["uplift_score"].sum() * mean_revenue_per_uplift_unit

        uplift_targets = df_with_segments.nlargest(n_target, "uplift_score")
        uplift_revenue = uplift_targets["uplift_score"].sum() * mean_revenue_per_uplift_unit

        improvement = (
            (uplift_revenue - response_revenue) / abs(response_revenue)
            if response_revenue != 0
            else 0.0
        )

        logger.info(
            "Model comparison — response: %.2f, uplift: %.2f, improvement: %.1f%%",
            response_revenue, uplift_revenue, improvement * 100,
        )

        return {
            "response_model_revenue": response_revenue,
            "uplift_model_revenue": uplift_revenue,
            "improvement": improvement,
            "improvement_pct": improvement * 100,
            "n_targeted": n_target,
            "mean_revenue_per_uplift_unit": mean_revenue_per_uplift_unit,
        }


if __name__ == "__main__":
    logger.info("Modeling module loaded successfully.")
    print("Modeling module loaded successfully")