"""
A/B Testing Framework

Rigorous statistical testing framework for campaign evaluation
with proper significance testing and business interpretation.

Fixes applied (v2):
- Survivorship bias: revenue t-test now uses ALL exposed users (0 for non-converters)
- Incremental revenue: single canonical formula used everywhere in the codebase
- Multiple testing: Bonferroni correction option added
- Welch's t-test: no equal-variance assumption for revenue comparison
- Input validation: guards against bad inputs throughout
- Logging: replaces bare print statements
"""

import logging
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ABTestFramework:
    """
    Production-grade A/B testing framework for marketing campaigns.
    """

    def __init__(self, alpha: float = 0.05, confidence_level: float = 0.95):
        """
        Initialize A/B testing framework.

        Parameters
        ----------
        alpha : float
            Significance level (default 0.05).
        confidence_level : float
            Confidence level for intervals (default 0.95).
        """
        if not (0 < alpha < 1):
            raise ValueError(f"alpha must be between 0 and 1, got {alpha}")
        if not (0 < confidence_level < 1):
            raise ValueError(f"confidence_level must be between 0 and 1, got {confidence_level}")

        self.alpha = alpha
        self.confidence_level = confidence_level
        logger.info(
            "ABTestFramework initialised (alpha=%.2f, CI=%.0f%%)",
            alpha, confidence_level * 100,
        )

    # ------------------------------------------------------------------
    # Conversion metrics
    # ------------------------------------------------------------------

    def calculate_conversion_metrics(
        self,
        treatment_conversions: int,
        treatment_total: int,
        control_conversions: int,
        control_total: int,
        apply_bonferroni: bool = False,
        n_tests: int = 1,
    ) -> Dict:
        """
        Calculate conversion rate metrics for treatment vs control.

        Parameters
        ----------
        treatment_conversions : int
            Number of conversions in treatment group.
        treatment_total : int
            Total size of treatment group.
        control_conversions : int
            Number of conversions in control group.
        control_total : int
            Total size of control group.
        apply_bonferroni : bool
            Apply Bonferroni correction for multiple simultaneous tests.
        n_tests : int
            Total number of simultaneous tests (used when apply_bonferroni=True).

        Returns
        -------
        dict
            Metrics including rates, lift, p-value, and confidence interval.
        """
        if treatment_total <= 0:
            raise ValueError(f"treatment_total must be > 0, got {treatment_total}")
        if control_total <= 0:
            raise ValueError(f"control_total must be > 0, got {control_total}")
        if treatment_conversions > treatment_total:
            raise ValueError(f"treatment_conversions ({treatment_conversions}) exceeds treatment_total ({treatment_total})")
        if control_conversions > control_total:
            raise ValueError(f"control_conversions ({control_conversions}) exceeds control_total ({control_total})")

        effective_alpha = self.alpha / n_tests if apply_bonferroni else self.alpha
        if apply_bonferroni:
            logger.info(
                "Bonferroni correction applied: alpha %.4f → %.4f (%d tests)",
                self.alpha, effective_alpha, n_tests,
            )

        treatment_rate = treatment_conversions / treatment_total
        control_rate = control_conversions / control_total
        absolute_lift = treatment_rate - control_rate
        relative_lift = (absolute_lift / control_rate) if control_rate > 0 else 0.0

        # Pooled z-test for two proportions
        pooled_rate = (treatment_conversions + control_conversions) / (treatment_total + control_total)
        pooled_se = np.sqrt(
            pooled_rate * (1 - pooled_rate) * (1 / treatment_total + 1 / control_total)
        )
        z_score = absolute_lift / pooled_se if pooled_se > 0 else 0.0
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

        # Confidence interval for the difference in proportions
        ci_margin = stats.norm.ppf(1 - effective_alpha / 2) * np.sqrt(
            treatment_rate * (1 - treatment_rate) / treatment_total
            + control_rate * (1 - control_rate) / control_total
        )

        return {
            "treatment_rate": treatment_rate,
            "control_rate": control_rate,
            "absolute_lift": absolute_lift,
            "relative_lift": relative_lift,
            "z_score": z_score,
            "p_value": p_value,
            "statistically_significant": bool(p_value < effective_alpha),
            "ci_lower": absolute_lift - ci_margin,
            "ci_upper": absolute_lift + ci_margin,
            "treatment_n": treatment_total,
            "control_n": control_total,
            "bonferroni_applied": apply_bonferroni,
            "effective_alpha": effective_alpha,
        }

    # ------------------------------------------------------------------
    # Revenue metrics
    # ------------------------------------------------------------------

    def calculate_revenue_metrics(
        self,
        treatment_revenue_all: np.ndarray,
        control_revenue_all: np.ndarray,
    ) -> Dict:
        """
        Calculate per-user revenue metrics using Welch's t-test.

        IMPORTANT — pass revenue for ALL exposed users, not just converters.
        Non-converters must appear as 0. Filtering to converters only
        introduces survivorship bias that inflates both group means and
        hides the true per-user revenue impact.

        Parameters
        ----------
        treatment_revenue_all : np.ndarray
            Revenue for every treatment-group user (0 for non-converters).
        control_revenue_all : np.ndarray
            Revenue for every control-group user (0 for non-converters).

        Returns
        -------
        dict
            Revenue metrics and Welch's t-test results.
        """
        if len(treatment_revenue_all) == 0 or len(control_revenue_all) == 0:
            raise ValueError("Revenue arrays must not be empty.")

        treatment_mean = np.mean(treatment_revenue_all)
        control_mean = np.mean(control_revenue_all)
        treatment_std = np.std(treatment_revenue_all, ddof=1)
        control_std = np.std(control_revenue_all, ddof=1)

        n_t = len(treatment_revenue_all)
        n_c = len(control_revenue_all)

        # Welch's t-test — does NOT assume equal variance across groups
        t_stat, p_value = stats.ttest_ind(
            treatment_revenue_all, control_revenue_all, equal_var=False
        )

        absolute_lift = treatment_mean - control_mean
        relative_lift = (absolute_lift / control_mean) if control_mean > 0 else 0.0

        # Welch–Satterthwaite degrees of freedom
        se_diff = np.sqrt(treatment_std ** 2 / n_t + control_std ** 2 / n_c)
        df_num = (treatment_std ** 2 / n_t + control_std ** 2 / n_c) ** 2
        df_den = (
            (treatment_std ** 2 / n_t) ** 2 / (n_t - 1)
            + (control_std ** 2 / n_c) ** 2 / (n_c - 1)
        )
        df = df_num / df_den if df_den > 0 else n_t + n_c - 2
        t_critical = stats.t.ppf(1 - self.alpha / 2, df)

        return {
            "treatment_mean": treatment_mean,
            "control_mean": control_mean,
            "absolute_lift": absolute_lift,
            "relative_lift": relative_lift,
            "t_statistic": t_stat,
            "p_value": p_value,
            "statistically_significant": bool(p_value < self.alpha),
            "ci_lower": absolute_lift - t_critical * se_diff,
            "ci_upper": absolute_lift + t_critical * se_diff,
            "treatment_n": n_t,
            "control_n": n_c,
        }

    # ------------------------------------------------------------------
    # Incremental revenue — SINGLE canonical definition
    # ------------------------------------------------------------------

    def calculate_incremental_revenue(
        self,
        treatment_revenue_total: float,
        treatment_n: int,
        control_revenue_total: float,
        control_n: int,
    ) -> float:
        """
        Calculate incremental revenue attributable to the campaign.

        Canonical formula (used identically in utils.py):
            incremental = (treatment_rev_per_user - control_rev_per_user)
                          × treatment_n

        This measures the extra revenue produced by the treatment group
        relative to what they would have generated under the control.

        Parameters
        ----------
        treatment_revenue_total : float
            Sum of revenue from the treatment group (all users, not just converters).
        treatment_n : int
            Number of users in the treatment group.
        control_revenue_total : float
            Sum of revenue from the control group (all users, not just converters).
        control_n : int
            Number of users in the control group.

        Returns
        -------
        float
            Incremental revenue.
        """
        if treatment_n <= 0:
            raise ValueError(f"treatment_n must be > 0, got {treatment_n}")
        if control_n <= 0:
            raise ValueError(f"control_n must be > 0, got {control_n}")

        treatment_ppu = treatment_revenue_total / treatment_n
        control_ppu = control_revenue_total / control_n
        incremental = (treatment_ppu - control_ppu) * treatment_n

        logger.debug(
            "Incremental revenue: treat_ppu=%.4f ctrl_ppu=%.4f n_treat=%d → %.2f",
            treatment_ppu, control_ppu, treatment_n, incremental,
        )
        return incremental

    # ------------------------------------------------------------------
    # ROI
    # ------------------------------------------------------------------

    def calculate_roi(self, incremental_revenue: float, total_cost: float) -> Dict:
        """
        Calculate campaign ROI.

        Parameters
        ----------
        incremental_revenue : float
            Incremental revenue from the campaign.
        total_cost : float
            Total campaign spend.

        Returns
        -------
        dict
            ROI metrics including profit and ROI percentage.
        """
        if total_cost < 0:
            raise ValueError(f"total_cost must be >= 0, got {total_cost}")
        if total_cost == 0:
            logger.warning("total_cost is 0; ROI will be returned as 0.")
            roi = 0.0
        else:
            roi = (incremental_revenue - total_cost) / total_cost

        return {
            "incremental_revenue": incremental_revenue,
            "total_cost": total_cost,
            "profit": incremental_revenue - total_cost,
            "roi": roi,
            "roi_percentage": roi * 100,
        }

    # ------------------------------------------------------------------
    # Sample size calculator
    # ------------------------------------------------------------------

    def check_minimum_sample_size(
        self,
        baseline_rate: float,
        mde: float,
        power: float = 0.8,
    ) -> int:
        """
        Calculate the minimum required sample size per group.

        Parameters
        ----------
        baseline_rate : float
            Expected baseline conversion rate.
        mde : float
            Minimum detectable effect as a relative lift (e.g. 0.10 = 10%).
        power : float
            Desired statistical power (default 0.80).

        Returns
        -------
        int
            Minimum sample size per group.
        """
        if not (0 < baseline_rate < 1):
            raise ValueError("baseline_rate must be between 0 and 1.")
        if mde <= 0:
            raise ValueError("mde must be positive.")

        p1 = baseline_rate
        p2 = baseline_rate * (1 + mde)
        z_alpha = stats.norm.ppf(1 - self.alpha / 2)
        z_beta = stats.norm.ppf(power)
        pooled_p = (p1 + p2) / 2
        n = (2 * pooled_p * (1 - pooled_p) * (z_alpha + z_beta) ** 2) / (p2 - p1) ** 2
        n_ceil = int(np.ceil(n))

        logger.info(
            "Minimum sample size: %d per group "
            "(baseline=%.2f%%, MDE=%.1f%%, power=%.0f%%)",
            n_ceil, baseline_rate * 100, mde * 100, power * 100,
        )
        return n_ceil

    # ------------------------------------------------------------------
    # Business interpretation
    # ------------------------------------------------------------------


    def apply_bonferroni_correction(self, p_values: List[float]) -> Dict:
        """
        Apply Bonferroni correction for multiple simultaneous A/B tests.

        When running N campaigns simultaneously, the probability of at least
        one false positive rises. Bonferroni divides alpha by N, requiring
        each individual test to clear a stricter threshold.

        Parameters
        ----------
        p_values : list of float
            Raw p-values from individual campaign tests.

        Returns
        -------
        dict
            adjusted_alpha, adjusted_p_values, bonferroni_significant flags.
        """
        n_tests = len(p_values)
        if n_tests == 0:
            raise ValueError("p_values list must not be empty.")
        adjusted_alpha = self.alpha / n_tests
        adjusted_p_values = [min(p * n_tests, 1.0) for p in p_values]
        significant = [bool(p < adjusted_alpha) for p in p_values]

        logger.info(
            "Bonferroni correction — %d tests, adjusted_alpha=%.4f, %d/%d significant",
            n_tests, adjusted_alpha, sum(significant), n_tests,
        )
        return {
            "n_tests": n_tests,
            "adjusted_alpha": adjusted_alpha,
            "adjusted_p_values": adjusted_p_values,
            "bonferroni_significant": significant,
        }
    def interpret_results(self, metrics: Dict, cost: Optional[float] = None) -> str:
        """
        Provide a plain-English business interpretation of test results.

        Parameters
        ----------
        metrics : dict
            Output of calculate_conversion_metrics or calculate_revenue_metrics.
        cost : float, optional
            Campaign cost; when supplied an ROI line is appended.

        Returns
        -------
        str
            Formatted interpretation string.
        """
        lines = []

        if metrics["statistically_significant"]:
            lines.append(f"✅ STATISTICALLY SIGNIFICANT (p={metrics['p_value']:.4f})")
        else:
            lines.append(f"❌ NOT STATISTICALLY SIGNIFICANT (p={metrics['p_value']:.4f})")

        if "treatment_rate" in metrics:
            lines.append(
                f"   Treatment: {metrics['treatment_rate']:.2%} | "
                f"Control: {metrics['control_rate']:.2%}"
            )
        else:
            lines.append(
                f"   Treatment: ${metrics['treatment_mean']:.2f} | "
                f"Control: ${metrics['control_mean']:.2f}"
            )

        lines.append(f"   Relative lift: {metrics['relative_lift']:.2%}")
        lines.append(f"   95% CI: [{metrics['ci_lower']:.4f}, {metrics['ci_upper']:.4f}]")

        if metrics.get("bonferroni_applied"):
            lines.append(
                f"   ⚠️  Bonferroni correction applied "
                f"(effective α = {metrics['effective_alpha']:.4f})"
            )

        if abs(metrics["relative_lift"]) < 0.05:
            lines.append("⚠️  SMALL EFFECT — may not be practically meaningful")

        if metrics["statistically_significant"] and metrics["relative_lift"] > 0.05:
            lines.append("📊 RECOMMENDATION: SCALE this campaign")
        elif metrics["statistically_significant"] and metrics["relative_lift"] < -0.05:
            lines.append("📊 RECOMMENDATION: KILL this campaign")
        else:
            lines.append("📊 RECOMMENDATION: ITERATE or extend the test duration")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Full campaign test runner
    # ------------------------------------------------------------------

    def run_campaign_test(
        self,
        campaign_data: pd.DataFrame,
        campaign_cost: float = 0.0,
    ) -> Dict:
        """
        Run a complete A/B test for a single campaign.

        Parameters
        ----------
        campaign_data : pd.DataFrame
            Must contain columns: treatment_group (0/1), converted (0/1),
            revenue_generated (float — 0 for non-converters).
        campaign_cost : float
            Total cost of the campaign for ROI calculation.

        Returns
        -------
        dict
            Full test results: conversion_metrics, revenue_metrics,
            incremental_revenue, and roi_metrics.
        """
        required_cols = {"treatment_group", "converted", "revenue_generated"}
        missing = required_cols - set(campaign_data.columns)
        if missing:
            raise ValueError(f"campaign_data is missing columns: {missing}")

        treatment = campaign_data[campaign_data["treatment_group"] == 1]
        control = campaign_data[campaign_data["treatment_group"] == 0]

        if len(treatment) == 0 or len(control) == 0:
            raise ValueError("Both treatment and control groups must be non-empty.")

        logger.info(
            "Running campaign test — treatment n=%d, control n=%d",
            len(treatment), len(control),
        )

        # Conversion
        conversion_metrics = self.calculate_conversion_metrics(
            treatment_conversions=int(treatment["converted"].sum()),
            treatment_total=len(treatment),
            control_conversions=int(control["converted"].sum()),
            control_total=len(control),
        )

        # Revenue — ALL users (non-converters = 0); no survivorship bias
        revenue_metrics = self.calculate_revenue_metrics(
            treatment_revenue_all=treatment["revenue_generated"].values,
            control_revenue_all=control["revenue_generated"].values,
        )

        # Incremental revenue (canonical formula)
        incremental_rev = self.calculate_incremental_revenue(
            treatment_revenue_total=float(treatment["revenue_generated"].sum()),
            treatment_n=len(treatment),
            control_revenue_total=float(control["revenue_generated"].sum()),
            control_n=len(control),
        )

        roi_metrics = self.calculate_roi(incremental_rev, campaign_cost) if campaign_cost > 0 else None

        logger.info(
            "Test complete — incremental_revenue=%.2f, significant=%s",
            incremental_rev, conversion_metrics["statistically_significant"],
        )

        return {
            "conversion_metrics": conversion_metrics,
            "revenue_metrics": revenue_metrics,
            "incremental_revenue": incremental_rev,
            "roi_metrics": roi_metrics,
        }


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ab = ABTestFramework(alpha=0.05)
    results = ab.calculate_conversion_metrics(
        treatment_conversions=520,
        treatment_total=10_000,
        control_conversions=380,
        control_total=5_000,
    )
    print(ab.interpret_results(results))
    # Example usage
    ab_test = ABTestFramework(alpha=0.05)
    
    # Example test
    results = ab_test.calculate_conversion_metrics(
        treatment_conversions=520,
        treatment_total=10000,
        control_conversions=380,
        control_total=5000
    )
    
    print(ab_test.interpret_results(results))