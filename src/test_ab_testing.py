"""
Unit Tests — A/B Testing Framework

Covers:
  - ABTestFramework: conversion metrics, revenue metrics, incremental revenue,
    ROI, sample size, Bonferroni correction, run_campaign_test
  - Input validation (ValueError guards)
  - Survivorship bias fix verification

Run with:
    python -m pytest tests/test_ab_testing.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
import numpy as np
import pandas as pd

from ab_testing import ABTestFramework


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ab():
    """Default ABTestFramework instance."""
    return ABTestFramework(alpha=0.05)


@pytest.fixture
def sample_campaign_data():
    """Minimal campaign DataFrame with treatment + control rows."""
    np.random.seed(0)
    n_treat, n_ctrl = 1000, 500
    treat_conv = np.random.binomial(1, 0.10, n_treat)
    ctrl_conv = np.random.binomial(1, 0.06, n_ctrl)
    treat_rev = np.where(treat_conv, np.random.gamma(3, 50, n_treat), 0.0)
    ctrl_rev = np.where(ctrl_conv, np.random.gamma(3, 50, n_ctrl), 0.0)
    return pd.DataFrame(
        {
            "treatment_group": [1] * n_treat + [0] * n_ctrl,
            "converted": list(treat_conv) + list(ctrl_conv),
            "revenue_generated": list(treat_rev) + list(ctrl_rev),
        }
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_valid_params(self):
        ab = ABTestFramework(alpha=0.01, confidence_level=0.99)
        assert ab.alpha == 0.01
        assert ab.confidence_level == 0.99

    def test_invalid_alpha_zero(self):
        with pytest.raises(ValueError, match="alpha"):
            ABTestFramework(alpha=0.0)

    def test_invalid_alpha_one(self):
        with pytest.raises(ValueError, match="alpha"):
            ABTestFramework(alpha=1.0)

    def test_invalid_confidence_level(self):
        with pytest.raises(ValueError, match="confidence_level"):
            ABTestFramework(confidence_level=1.5)


# ---------------------------------------------------------------------------
# Conversion metrics
# ---------------------------------------------------------------------------

class TestConversionMetrics:
    def test_known_lift(self, ab):
        result = ab.calculate_conversion_metrics(
            treatment_conversions=100,
            treatment_total=1000,
            control_conversions=50,
            control_total=1000,
        )
        assert result["treatment_rate"] == pytest.approx(0.10)
        assert result["control_rate"] == pytest.approx(0.05)
        assert result["relative_lift"] == pytest.approx(1.0)   # 100% lift
        assert result["statistically_significant"] is True

    def test_no_lift_not_significant(self, ab):
        result = ab.calculate_conversion_metrics(
            treatment_conversions=50,
            treatment_total=1000,
            control_conversions=50,
            control_total=1000,
        )
        assert result["relative_lift"] == pytest.approx(0.0)
        assert result["statistically_significant"] is False

    def test_ci_contains_zero_when_not_significant(self, ab):
        result = ab.calculate_conversion_metrics(50, 1000, 50, 1000)
        assert result["ci_lower"] < 0 < result["ci_upper"]

    def test_zero_treatment_total_raises(self, ab):
        with pytest.raises(ValueError, match="treatment_total"):
            ab.calculate_conversion_metrics(0, 0, 10, 100)

    def test_conversions_exceed_total_raises(self, ab):
        with pytest.raises(ValueError, match="treatment_conversions"):
            ab.calculate_conversion_metrics(200, 100, 10, 100)

    def test_output_keys_present(self, ab):
        result = ab.calculate_conversion_metrics(10, 100, 5, 100)
        for key in [
            "treatment_rate", "control_rate", "absolute_lift",
            "relative_lift", "z_score", "p_value",
            "statistically_significant", "ci_lower", "ci_upper",
        ]:
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Revenue metrics — survivorship bias fix
# ---------------------------------------------------------------------------

class TestRevenueMetrics:
    def test_includes_zeros_for_non_converters(self, ab):
        """Passing full arrays (zeros for non-converters) should produce
        lower means than passing only converter revenue."""
        np.random.seed(42)
        converter_revenue = np.random.gamma(3, 50, 100)

        # All users — 10 % converters
        all_treat = np.concatenate([converter_revenue, np.zeros(900)])
        all_ctrl = np.concatenate([np.random.gamma(3, 50, 60), np.zeros(940)])

        full_result = ab.calculate_revenue_metrics(all_treat, all_ctrl)

        # Converters only (survivorship-biased — wrong way)
        biased_result = ab.calculate_revenue_metrics(converter_revenue, all_ctrl[:60])

        # Full-array mean must be lower (non-converters dilute it)
        assert full_result["treatment_mean"] < biased_result["treatment_mean"]

    def test_empty_array_raises(self, ab):
        with pytest.raises(ValueError, match="empty"):
            ab.calculate_revenue_metrics(np.array([]), np.array([10.0, 20.0]))

    def test_output_keys_present(self, ab):
        t = np.array([10.0, 0.0, 20.0, 0.0])
        c = np.array([5.0, 0.0, 8.0, 0.0])
        result = ab.calculate_revenue_metrics(t, c)
        for key in [
            "treatment_mean", "control_mean", "absolute_lift",
            "relative_lift", "t_statistic", "p_value",
            "statistically_significant", "ci_lower", "ci_upper",
        ]:
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Incremental revenue (canonical formula)
# ---------------------------------------------------------------------------

class TestIncrementalRevenue:
    def test_positive_lift(self, ab):
        """Treatment earns $10/user, control earns $6/user, 1000 treated."""
        inc = ab.calculate_incremental_revenue(10_000, 1000, 3_000, 500)
        # treat_per = 10, ctrl_per = 6, inc = (10-6)*1000 = 4000
        assert inc == pytest.approx(4_000.0)

    def test_negative_lift(self, ab):
        """Treatment earns less than control → negative incremental revenue."""
        inc = ab.calculate_incremental_revenue(3_000, 1000, 4_000, 500)
        # treat_per=3, ctrl_per=8, inc=(3-8)*1000 = -5000
        assert inc == pytest.approx(-5_000.0)

    def test_zero_lift(self, ab):
        inc = ab.calculate_incremental_revenue(5_000, 1000, 2_500, 500)
        assert inc == pytest.approx(0.0)

    def test_zero_treatment_n_raises(self, ab):
        with pytest.raises(ValueError, match="treatment_n"):
            ab.calculate_incremental_revenue(1000, 0, 500, 100)

    def test_zero_control_n_raises(self, ab):
        with pytest.raises(ValueError, match="control_n"):
            ab.calculate_incremental_revenue(1000, 100, 500, 0)


# ---------------------------------------------------------------------------
# ROI calculation
# ---------------------------------------------------------------------------

class TestROI:
    def test_positive_roi(self, ab):
        result = ab.calculate_roi(incremental_revenue=10_000, total_cost=2_000)
        assert result["roi"] == pytest.approx(4.0)          # 400 %
        assert result["roi_percentage"] == pytest.approx(400.0)
        assert result["profit"] == pytest.approx(8_000.0)

    def test_zero_cost_returns_zero_roi(self, ab):
        result = ab.calculate_roi(incremental_revenue=5_000, total_cost=0)
        assert result["roi"] == pytest.approx(0.0)

    def test_negative_cost_raises(self, ab):
        with pytest.raises(ValueError, match="total_cost"):
            ab.calculate_roi(1000, -100)


# ---------------------------------------------------------------------------
# Sample size
# ---------------------------------------------------------------------------

class TestSampleSize:
    def test_returns_positive_integer(self, ab):
        n = ab.check_minimum_sample_size(baseline_rate=0.05, mde=0.20)
        assert isinstance(n, int)
        assert n > 0

    def test_larger_mde_needs_fewer_samples(self, ab):
        n_small_mde = ab.check_minimum_sample_size(0.05, 0.10)
        n_large_mde = ab.check_minimum_sample_size(0.05, 0.50)
        assert n_small_mde > n_large_mde

    def test_invalid_baseline_rate_raises(self, ab):
        with pytest.raises(ValueError):
            ab.check_minimum_sample_size(1.5, 0.10)

    def test_invalid_mde_raises(self, ab):
        with pytest.raises(ValueError):
            ab.check_minimum_sample_size(0.05, 0.0)


# ---------------------------------------------------------------------------
# Bonferroni correction
# ---------------------------------------------------------------------------

class TestBonferroni:
    def test_adjusted_alpha(self, ab):
        result = ab.apply_bonferroni_correction([0.01, 0.03, 0.02, 0.04])
        assert result["adjusted_alpha"] == pytest.approx(0.05 / 4)

    def test_significant_flags(self, ab):
        result = ab.apply_bonferroni_correction([0.001, 0.04, 0.03])
        # adjusted_alpha = 0.05/3 ≈ 0.0167; only 0.001 passes
        assert result["bonferroni_significant"] == [True, False, False]

    def test_adjusted_p_values_capped_at_1(self, ab):
        result = ab.apply_bonferroni_correction([0.9, 0.8])
        assert all(p <= 1.0 for p in result["adjusted_p_values"])


# ---------------------------------------------------------------------------
# Full campaign test
# ---------------------------------------------------------------------------

class TestRunCampaignTest:
    def test_returns_expected_keys(self, ab, sample_campaign_data):
        result = ab.run_campaign_test(sample_campaign_data)
        assert "conversion_metrics" in result
        assert "revenue_metrics" in result
        assert "incremental_revenue" in result

    def test_missing_column_raises(self, ab):
        bad_df = pd.DataFrame({"treatment_group": [1, 0], "converted": [1, 0]})
        with pytest.raises(ValueError, match="missing columns"):
            ab.run_campaign_test(bad_df)

    def test_empty_treatment_raises(self, ab):
        df = pd.DataFrame(
            {
                "treatment_group": [0, 0, 0],
                "converted": [1, 0, 1],
                "revenue_generated": [50.0, 0.0, 30.0],
            }
        )
        with pytest.raises(ValueError, match="treatment and control"):
            ab.run_campaign_test(df)

    def test_revenue_metrics_uses_all_users(self, ab, sample_campaign_data):
        """Revenue metrics must include non-converters (revenue = 0)."""
        result = ab.run_campaign_test(sample_campaign_data)
        rm = result["revenue_metrics"]
        # treatment_n should equal full treatment group size, not just converters
        treat_n_full = (sample_campaign_data["treatment_group"] == 1).sum()
        assert rm["treatment_n"] == treat_n_full

    def test_incremental_revenue_consistent_with_standalone(
        self, ab, sample_campaign_data
    ):
        """run_campaign_test incremental revenue must match direct calculation."""
        result = ab.run_campaign_test(sample_campaign_data)

        treatment = sample_campaign_data[sample_campaign_data["treatment_group"] == 1]
        control = sample_campaign_data[sample_campaign_data["treatment_group"] == 0]

        expected = ab.calculate_incremental_revenue(
            treatment["revenue_generated"].sum(),
            len(treatment),
            control["revenue_generated"].sum(),
            len(control),
        )
        assert result["incremental_revenue"] == pytest.approx(expected)