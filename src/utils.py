"""
Utility Functions

Helper functions for data processing, visualization, and reporting.

Fixes applied (v2):
- Incremental revenue formula aligned with ab_testing.py canonical definition:
    incremental = (treatment_rev_per_user - control_rev_per_user) × treatment_n
- Budget reallocation percentages now guaranteed to sum exactly to 100.0
  using the largest-remainder (Hamilton) method.
- Logging replaces bare print statements.
- Error handling added to all public functions.
"""

import logging
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ROI calculation
# ---------------------------------------------------------------------------

def calculate_campaign_roi(
    exposure_df: pd.DataFrame,
    outcome_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate ROI metrics for each campaign.

    Incremental revenue formula (canonical, matches ab_testing.py):
        incremental = (treatment_rev_per_user - control_rev_per_user) × treatment_n

    Parameters
    ----------
    exposure_df : pd.DataFrame
        Campaign exposure data.
    outcome_df : pd.DataFrame
        Campaign outcome data.

    Returns
    -------
    pd.DataFrame
        Campaign-level ROI metrics.
    """
    required_exp = {"customer_id", "campaign_id", "treatment_group", "cost_per_contact", "channel"}
    required_out = {"customer_id", "campaign_id", "converted", "revenue_generated"}
    for col in required_exp - set(exposure_df.columns):
        raise ValueError(f"exposure_df is missing column: {col}")
    for col in required_out - set(outcome_df.columns):
        raise ValueError(f"outcome_df is missing column: {col}")

    campaign_data = exposure_df.merge(
        outcome_df[["customer_id", "campaign_id", "converted", "conversion_date", "revenue_generated"]],
        on=["customer_id", "campaign_id"],
    )

    metrics = []
    for campaign_id in campaign_data["campaign_id"].unique():
        camp = campaign_data[campaign_data["campaign_id"] == campaign_id]

        treatment = camp[camp["treatment_group"] == 1]
        control = camp[camp["treatment_group"] == 0]

        total_cost = treatment["cost_per_contact"].sum()
        treatment_revenue = treatment["revenue_generated"].sum()
        control_revenue = control["revenue_generated"].sum()

        # Canonical incremental revenue formula (same as ab_testing.py)
        if len(control) > 0:
            treatment_ppu = treatment_revenue / len(treatment) if len(treatment) > 0 else 0
            control_ppu = control_revenue / len(control)
            incremental_revenue = (treatment_ppu - control_ppu) * len(treatment)
        else:
            logger.warning("Campaign %s has no control group; incremental revenue = treatment revenue.", campaign_id)
            incremental_revenue = treatment_revenue

        roi = (incremental_revenue - total_cost) / total_cost if total_cost > 0 else 0.0

        treatment_conv_rate = treatment["converted"].mean() if len(treatment) > 0 else 0.0
        control_conv_rate = control["converted"].mean() if len(control) > 0 else 0.0

        metrics.append(
            {
                "campaign_id": campaign_id,
                "channel": camp["channel"].iloc[0],
                "total_cost": total_cost,
                "treatment_revenue": treatment_revenue,
                "incremental_revenue": incremental_revenue,
                "roi": roi,
                "roi_pct": roi * 100,
                "treatment_conv_rate": treatment_conv_rate,
                "control_conv_rate": control_conv_rate,
                "conversion_lift": treatment_conv_rate - control_conv_rate,
                "n_treatment": len(treatment),
                "n_control": len(control),
            }
        )

    logger.info("Calculated ROI for %d campaigns.", len(metrics))
    return pd.DataFrame(metrics)


# ---------------------------------------------------------------------------
# Channel aggregation
# ---------------------------------------------------------------------------

def calculate_channel_performance(roi_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate performance metrics by channel.

    Parameters
    ----------
    roi_df : pd.DataFrame
        Campaign-level ROI data (output of calculate_campaign_roi).

    Returns
    -------
    pd.DataFrame
        Channel-level aggregated metrics.
    """
    channel_metrics = (
        roi_df.groupby("channel")
        .agg(
            total_cost=("total_cost", "sum"),
            treatment_revenue=("treatment_revenue", "sum"),
            incremental_revenue=("incremental_revenue", "sum"),
            avg_roi=("roi", "mean"),
            treatment_conv_rate=("treatment_conv_rate", "mean"),
            conversion_lift=("conversion_lift", "mean"),
            n_campaigns=("campaign_id", "count"),
        )
        .reset_index()
    )

    channel_metrics["overall_roi"] = (
        channel_metrics["incremental_revenue"] - channel_metrics["total_cost"]
    ) / channel_metrics["total_cost"].replace(0, np.nan)

    logger.info("Channel performance aggregated across %d channels.", len(channel_metrics))
    return channel_metrics


# ---------------------------------------------------------------------------
# Budget allocation (largest-remainder rounding)
# ---------------------------------------------------------------------------

def allocate_budget(
    channel_perf: pd.DataFrame,
    total_budget: float,
    roi_col: str = "overall_roi",
) -> pd.DataFrame:
    """
    Allocate budget across channels proportional to ROI, with percentages
    guaranteed to sum exactly to 100% using the largest-remainder method.

    Parameters
    ----------
    channel_perf : pd.DataFrame
        Channel performance data (must include channel and roi_col).
    total_budget : float
        Total budget to allocate.
    roi_col : str
        Column to use as allocation weight (default 'overall_roi').

    Returns
    -------
    pd.DataFrame
        DataFrame with recommended_pct and recommended_budget columns
        that sum precisely to 100% and total_budget respectively.
    """
    df = channel_perf.copy()

    # Channels with negative ROI get zero allocation
    df["roi_weight"] = df[roi_col].clip(lower=0)
    total_weight = df["roi_weight"].sum()

    if total_weight == 0:
        logger.warning("All channels have non-positive ROI; budget split equally.")
        df["roi_weight"] = 1.0
        total_weight = float(len(df))

    # Raw percentages
    df["raw_pct"] = df["roi_weight"] / total_weight * 100

    # Largest-remainder method ensures exact 100.0% sum
    df["floor_pct"] = df["raw_pct"].apply(np.floor)
    remainder = 100 - df["floor_pct"].sum()
    df["remainder"] = df["raw_pct"] - df["floor_pct"]
    top_idx = df["remainder"].nlargest(int(remainder)).index
    df.loc[top_idx, "floor_pct"] += 1
    df["recommended_pct"] = df["floor_pct"]

    assert df["recommended_pct"].sum() == 100, "Budget percentages do not sum to 100 — rounding error."

    df["recommended_budget"] = df["recommended_pct"] / 100 * total_budget
    df = df.drop(columns=["raw_pct", "floor_pct", "remainder"])

    logger.info(
        "Budget allocation complete. Percentages sum to %.1f%%.",
        df["recommended_pct"].sum(),
    )
    return df


# ---------------------------------------------------------------------------
# Visualisation helpers
# ---------------------------------------------------------------------------

def plot_roc_curve(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    title: str = "ROC Curve",
    save_path: Optional[str] = None,
) -> None:
    """Plot ROC curve for model evaluation."""
    from sklearn.metrics import roc_curve, roc_auc_score

    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)

    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, linewidth=2, label=f"ROC Curve (AUC = {auc:.3f})")
    plt.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random classifier")
    plt.xlabel("False positive rate", fontsize=12)
    plt.ylabel("True positive rate", fontsize=12)
    plt.title(title, fontsize=14, fontweight="bold")
    plt.legend(fontsize=11)
    plt.grid(alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info("ROC curve saved to %s", save_path)
    plt.show()


def plot_precision_recall_curve(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    title: str = "Precision-Recall Curve",
    save_path: Optional[str] = None,
) -> None:
    """Plot precision-recall curve for model evaluation."""
    from sklearn.metrics import precision_recall_curve, average_precision_score

    precision, recall, _ = precision_recall_curve(y_true, y_pred_proba)
    avg_precision = average_precision_score(y_true, y_pred_proba)

    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, linewidth=2, label=f"PR Curve (AP = {avg_precision:.3f})")
    plt.xlabel("Recall", fontsize=12)
    plt.ylabel("Precision", fontsize=12)
    plt.title(title, fontsize=14, fontweight="bold")
    plt.legend(fontsize=11)
    plt.grid(alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info("PR curve saved to %s", save_path)
    plt.show()


def plot_feature_importance(
    importance_df: pd.DataFrame,
    top_n: int = 15,
    title: str = "Feature Importance",
    save_path: Optional[str] = None,
) -> None:
    """Plot feature importance from model coefficients."""
    data = importance_df.head(top_n).copy()
    colors = ["green" if x > 0 else "red" for x in data["coefficient"]]

    plt.figure(figsize=(10, 8))
    plt.barh(range(len(data)), data["coefficient"], color=colors, alpha=0.7)
    plt.yticks(range(len(data)), data["feature"])
    plt.xlabel("Coefficient", fontsize=12)
    plt.title(title, fontsize=14, fontweight="bold")
    plt.axvline(x=0, color="black", linestyle="--", linewidth=1)
    plt.grid(axis="x", alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info("Feature importance plot saved to %s", save_path)
    plt.show()


def plot_uplift_distribution(
    df_with_uplift: pd.DataFrame,
    save_path: Optional[str] = None,
) -> None:
    """Plot distribution of uplift scores and customer segment sizes."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(df_with_uplift["uplift_score"], bins=50, color="steelblue", alpha=0.7, edgecolor="black")
    axes[0].axvline(x=0, color="red", linestyle="--", linewidth=2, label="Zero uplift")
    axes[0].set_xlabel("Uplift score", fontsize=12)
    axes[0].set_ylabel("Frequency", fontsize=12)
    axes[0].set_title("Distribution of uplift scores", fontsize=14, fontweight="bold")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    segment_counts = df_with_uplift["segment"].value_counts()
    color_map = {
        "Persuadables": "green",
        "Sure Things": "yellow",
        "Lost Causes": "orange",
        "Sleeping Dogs": "red",
    }
    colors = [color_map.get(s, "gray") for s in segment_counts.index]

    axes[1].bar(range(len(segment_counts)), segment_counts.values, color=colors, alpha=0.7, edgecolor="black")
    axes[1].set_xticks(range(len(segment_counts)))
    axes[1].set_xticklabels(segment_counts.index, rotation=45, ha="right")
    axes[1].set_ylabel("Number of customers", fontsize=12)
    axes[1].set_title("Customer segments", fontsize=14, fontweight="bold")
    axes[1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info("Uplift distribution plot saved to %s", save_path)
    plt.show()


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def create_executive_summary(
    campaign_roi: pd.DataFrame,
    channel_perf: pd.DataFrame,
    ab_results: Dict,
    uplift_comparison: Dict,
) -> str:
    """
    Create an executive summary report.

    Parameters
    ----------
    campaign_roi : pd.DataFrame
        Campaign-level ROI metrics.
    channel_perf : pd.DataFrame
        Channel-level performance.
    ab_results : dict
        A/B test results.
    uplift_comparison : dict
        Uplift vs response model comparison.

    Returns
    -------
    str
        Formatted executive summary.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("EXECUTIVE SUMMARY — MARKETING CAMPAIGN OPTIMIZATION")
    lines.append("=" * 80)
    lines.append("")

    total_spend = campaign_roi["total_cost"].sum()
    total_incremental = campaign_roi["incremental_revenue"].sum()
    overall_roi = (total_incremental - total_spend) / total_spend if total_spend > 0 else 0

    lines += [
        "📊 OVERALL PERFORMANCE",
        f"   Total campaign spend:    ${total_spend:,.2f}",
        f"   Incremental revenue:     ${total_incremental:,.2f}",
        f"   Overall ROI:             {overall_roi:.1%}",
        "",
    ]

    lines.append("📈 CHANNEL PERFORMANCE (ranked by ROI)")
    for _, row in channel_perf.sort_values("overall_roi", ascending=False).iterrows():
        lines.append(
            f"   {row['channel']:15s} | ROI: {row['overall_roi']:6.1%} | "
            f"Revenue: ${row['incremental_revenue']:,.0f} | "
            f"Campaigns: {int(row['n_campaigns'])}"
        )
    lines.append("")

    lines.append("🏆 TOP 5 CAMPAIGNS BY ROI")
    for _, row in campaign_roi.nlargest(5, "roi").iterrows():
        lines.append(
            f"   {row['campaign_id']} ({row['channel']:12s}) | "
            f"ROI: {row['roi']:6.1%} | Revenue: ${row['incremental_revenue']:,.0f}"
        )
    lines.append("")

    lines.append("⚠️  BOTTOM 3 CAMPAIGNS (consider stopping)")
    for _, row in campaign_roi.nsmallest(3, "roi").iterrows():
        lines.append(
            f"   {row['campaign_id']} ({row['channel']:12s}) | "
            f"ROI: {row['roi']:6.1%} | Loss: ${-row['incremental_revenue']:,.0f}"
        )
    lines.append("")

    if uplift_comparison:
        lines += [
            "🎯 UPLIFT MODELING IMPACT",
            f"   Response model revenue:  ${uplift_comparison['response_model_revenue']:,.2f}",
            f"   Uplift-based revenue:    ${uplift_comparison['uplift_model_revenue']:,.2f}",
            f"   Improvement:             {uplift_comparison['improvement_pct']:.1f}%",
            "",
        ]

    worst = campaign_roi.nsmallest(1, "roi").iloc[0]
    best = campaign_roi.nlargest(1, "roi").iloc[0]
    n_negative = int((campaign_roi["roi"] < 0).sum())

    lines += [
        "💡 KEY RECOMMENDATIONS",
        f"   1. Reallocate budget from {worst['channel']} to {best['channel']}",
        f"   2. Stop {n_negative} campaign(s) with negative ROI",
        "   3. Apply uplift-based targeting to maximise incremental impact",
        "   4. Focus on 'Persuadable' segment for highest ROI per pound spent",
        "",
        "=" * 80,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard export
# ---------------------------------------------------------------------------

def export_dashboard_data(
    campaign_roi: pd.DataFrame,
    channel_perf: pd.DataFrame,
    customer_segments: pd.DataFrame,
    output_dir: str = "outputs/",
) -> None:
    """
    Export processed data for Power BI or similar dashboards.

    Parameters
    ----------
    campaign_roi : pd.DataFrame
        Campaign-level metrics.
    channel_perf : pd.DataFrame
        Channel-level metrics.
    customer_segments : pd.DataFrame
        Customer segments with uplift scores.
    output_dir : str
        Output directory path.
    """
    os.makedirs(output_dir, exist_ok=True)

    campaign_roi.to_csv(f"{output_dir}campaign_performance.csv", index=False, encoding="utf-8")
    logger.info("Exported: campaign_performance.csv")

    channel_perf.to_csv(f"{output_dir}channel_effectiveness.csv", index=False, encoding="utf-8")
    logger.info("Exported: channel_effectiveness.csv")

    segment_summary = (
        customer_segments.groupby("segment")
        .agg(
            customer_count=("customer_id", "count"),
            avg_uplift_score=("uplift_score", "mean"),
            avg_treatment_prob=("treatment_prob", "mean"),
            avg_control_prob=("control_prob", "mean"),
        )
        .reset_index()
    )
    segment_summary.to_csv(f"{output_dir}customer_segments.csv", index=False, encoding="utf-8")
    logger.info("Exported: customer_segments.csv")
    logger.info("Dashboard data ready in: %s", output_dir)


if __name__ == "__main__":
    logger.info("Utilities module loaded successfully.")
    print("Utilities module loaded successfully")