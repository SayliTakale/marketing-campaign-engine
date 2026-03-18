"""
Marketing Campaign Optimization - Complete Analysis Pipeline
==============================================================
This script runs the complete analysis from data loading through
uplift modeling and generates all outputs for the executive dashboard.
"""

import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

from ab_testing import ABTestFramework
from models import ConversionPredictor, UpliftModeler
from utils import (
    calculate_campaign_roi, calculate_channel_performance,
    plot_roc_curve, plot_precision_recall_curve, 
    plot_feature_importance, plot_uplift_distribution,
    create_executive_summary, export_dashboard_data
)

# Set plotting style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("="*80)
print("MARKETING CAMPAIGN OPTIMIZATION & PERSONALIZATION ENGINE")
print("="*80)
print()

# ============================================================================
# SECTION 1: DATA LOADING
# ============================================================================
print("📂 SECTION 1: Loading Data")
print("-" * 80)

customers_df = pd.read_csv('data/simulated/customers.csv')
campaigns_df = pd.read_csv('data/simulated/campaigns.csv')
exposures_df = pd.read_csv('data/simulated/exposures.csv')
outcomes_df = pd.read_csv('data/simulated/outcomes.csv')

print(f"✅ Loaded {len(customers_df):,} customers")
print(f"✅ Loaded {len(campaigns_df):,} campaigns")
print(f"✅ Loaded {len(exposures_df):,} exposures")
print(f"✅ Loaded {len(outcomes_df):,} outcomes")
print()

# ============================================================================
# SECTION 2: CAMPAIGN ROI ANALYSIS
# ============================================================================
print("💰 SECTION 2: Campaign ROI Analysis")
print("-" * 80)

campaign_roi = calculate_campaign_roi(exposures_df, outcomes_df)
channel_perf = calculate_channel_performance(campaign_roi)

print("\n📊 Top 5 Campaigns by ROI:")
print(campaign_roi.nlargest(5, 'roi')[
    ['campaign_id', 'channel', 'roi', 'incremental_revenue', 'conversion_lift']
].to_string(index=False))

print("\n📊 Channel Performance:")
print(channel_perf[
    ['channel', 'n_campaigns', 'overall_roi']
].to_string(index=False))
print()

# ============================================================================
# SECTION 3: A/B TESTING FRAMEWORK
# ============================================================================
print("🧪 SECTION 3: A/B Testing Analysis")
print("-" * 80)

ab_test = ABTestFramework(alpha=0.05)

# Merge data for testing
test_data = exposures_df.merge(
    outcomes_df[['customer_id', 'campaign_id', 'converted', 'revenue_generated']],
    on=['customer_id', 'campaign_id'],
    how='left'
)

# Run test for each campaign
print("\n📋 Campaign-by-Campaign A/B Test Results:\n")

ab_results = []
for campaign_id in test_data['campaign_id'].unique():
    camp_data = test_data[test_data['campaign_id'] == campaign_id]
    
    treatment = camp_data[camp_data['treatment_group'] == 1]
    control = camp_data[camp_data['treatment_group'] == 0]
    
    if len(treatment) > 100 and len(control) > 100:  # Minimum sample size
        # Conversion test
        conv_metrics = ab_test.calculate_conversion_metrics(
            treatment_conversions=treatment['converted'].sum(),
            treatment_total=len(treatment),
            control_conversions=control['converted'].sum(),
            control_total=len(control)
        )
        
        # Calculate incremental revenue
        inc_rev = ab_test.calculate_incremental_revenue(
            treatment_revenue_total=treatment['revenue_generated'].sum(),
            treatment_n=len(treatment),
            control_revenue_total=control['revenue_generated'].sum(),
            control_n=len(control)
        )
        
        # Total cost
        total_cost = treatment['cost_per_contact'].sum()
        
        # ROI
        roi_metrics = ab_test.calculate_roi(inc_rev, total_cost)
        
        ab_results.append({
            'campaign_id': campaign_id,
            'channel': camp_data['channel'].iloc[0],
            'treatment_rate': conv_metrics['treatment_rate'],
            'control_rate': conv_metrics['control_rate'],
            'relative_lift': conv_metrics['relative_lift'],
            'p_value': conv_metrics['p_value'],
            'significant': conv_metrics['statistically_significant'],
            'incremental_revenue': inc_rev,
            'roi': roi_metrics['roi']
        })
        
        # Print first 3 campaigns in detail
        if len(ab_results) <= 3:
            print(f"\n{campaign_id} ({camp_data['channel'].iloc[0]})")
            print(ab_test.interpret_results(conv_metrics))
            print(f"   Incremental Revenue: ${inc_rev:,.2f}")
            print(f"   ROI: {roi_metrics['roi']:.1%}\n")

ab_results_df = pd.DataFrame(ab_results)

# Summary statistics
significant_wins = ab_results_df[
    (ab_results_df['significant']) & (ab_results_df['relative_lift'] > 0)
]
significant_losses = ab_results_df[
    (ab_results_df['significant']) & (ab_results_df['relative_lift'] < 0)
]

print(f"\n📊 A/B Test Summary:")
print(f"   Total Campaigns Tested: {len(ab_results_df)}")
print(f"   Statistically Significant Wins: {len(significant_wins)}")
print(f"   Statistically Significant Losses: {len(significant_losses)}")
print(f"   Inconclusive Tests: {len(ab_results_df) - len(significant_wins) - len(significant_losses)}")
print()

# ============================================================================
# SECTION 4: CONVERSION PREDICTION MODEL
# ============================================================================
print("🤖 SECTION 4: Conversion Prediction Model")
print("-" * 80)

# Merge customer data with exposure and outcome data
modeling_data = exposures_df.merge(customers_df, on='customer_id')
modeling_data = modeling_data.merge(
    outcomes_df[['customer_id', 'campaign_id', 'converted', 'revenue_generated']],
    on=['customer_id', 'campaign_id']
)

# Use only treatment group for prediction model
treatment_data = modeling_data[modeling_data['treatment_group'] == 1].copy()

print(f"\n📊 Building model on {len(treatment_data):,} treatment group exposures...")

# Initialize and train model
predictor = ConversionPredictor(random_state=42)
X, y = predictor.prepare_training_data(treatment_data, target_col='converted')
results = predictor.train(X, y, test_size=0.2)

print(f"\n✅ Model Performance:")
print(f"   ROC-AUC Score: {results['roc_auc']:.3f}")
print(f"   Average Precision: {results['avg_precision']:.3f}")
print(f"   Cross-validation AUC: {results['cv_mean']:.3f} (±{results['cv_std']:.3f})")

# Feature importance
print(f"\n{predictor.interpret_coefficients(top_n=10)}")

# Plot ROC curve
plot_roc_curve(
    results['y_test'],
    results['y_pred_proba'],
    title="Conversion Prediction Model - ROC Curve",
    save_path='outputs/figures/roc_curve.png'
)

# Plot feature importance
importance_df = predictor.get_feature_importance()
plot_feature_importance(
    importance_df,
    top_n=15,
    title="Top Features Driving Conversion",
    save_path='outputs/figures/feature_importance.png'
)

print()

# ============================================================================
# SECTION 5: UPLIFT MODELING
# ============================================================================
print("🎯 SECTION 5: Uplift Modeling (KEY DIFFERENTIATOR)")
print("-" * 80)

print("\n📊 Training uplift models (this may take a moment)...")

uplift_modeler = UpliftModeler(random_state=42)
uplift_results = uplift_modeler.train_uplift_models(modeling_data)

# Calculate uplift scores
print("\n📊 Calculating uplift scores for all customers...")
df_with_uplift = uplift_modeler.calculate_uplift(modeling_data)

# Segment customers
print("📊 Segmenting customers into quadrants...")
df_segmented = uplift_modeler.segment_customers(df_with_uplift)

# Display segment distribution
segment_counts = df_segmented['segment'].value_counts()
print("\n📊 Customer Segments:")
for segment, count in segment_counts.items():
    pct = count / len(df_segmented) * 100
    rec = df_segmented[df_segmented['segment'] == segment]['recommendation'].iloc[0]
    print(f"   {segment:20s}: {count:6,} ({pct:5.1f}%) - {rec}")

# Compare to traditional response model
print("\n📊 Comparing Uplift Model vs Traditional Response Model...")
comparison = uplift_modeler.compare_to_response_model(
    df_segmented,
    budget_constraint=0.3  # Target 30% of customers
)

print(f"\n✅ Uplift Model Advantage:")
print(f"   Response Model Expected Revenue: ${comparison['response_model_revenue']:,.2f}")
print(f"   Uplift Model Expected Revenue: ${comparison['uplift_model_revenue']:,.2f}")
print(f"   Improvement: {comparison['improvement_pct']:.1f}%")
print(f"   (Targeting top {comparison['n_targeted']:,} customers)")

# Plot uplift distribution
plot_uplift_distribution(
    df_segmented,
    save_path='outputs/figures/uplift_distribution.png'
)

print()

# ============================================================================
# SECTION 6: EXECUTIVE SUMMARY & RECOMMENDATIONS
# ============================================================================
print("📊 SECTION 6: Executive Summary")
print("-" * 80)

executive_summary = create_executive_summary(
    campaign_roi=campaign_roi,
    channel_perf=channel_perf,
    ab_results=ab_results_df.to_dict('records'),
    uplift_comparison=comparison
)

print(executive_summary)

# Save to file
with open('outputs/reports/executive_summary.txt', 'w') as f:
    f.write(executive_summary)

print("\n✅ Executive summary saved to: outputs/reports/executive_summary.txt")

# ============================================================================
# SECTION 7: EXPORT DATA FOR POWER BI
# ============================================================================
print("\n📊 SECTION 7: Exporting Data for Power BI Dashboard")
print("-" * 80)

export_dashboard_data(
    campaign_roi=campaign_roi,
    channel_perf=channel_perf,
    customer_segments=df_segmented,
    output_dir='outputs/'
)

# Additional exports
ab_results_df.to_csv('outputs/ab_test_results.csv', index=False, encoding='utf-8')
print("✅ Exported: ab_test_results.csv")

# Budget reallocation recommendations
budget_realloc = channel_perf[['channel', 'total_cost', 'overall_roi']].copy()
total_budget = budget_realloc['total_cost'].sum()
budget_realloc['current_pct'] = (budget_realloc['total_cost'] / total_budget * 100).round(1)

# Recommended allocation based on ROI
budget_realloc['roi_weight'] = budget_realloc['overall_roi'].clip(lower=0)
budget_realloc['recommended_pct'] = (
    budget_realloc['roi_weight'] / budget_realloc['roi_weight'].sum() * 100
).round(1)
budget_realloc['shift_pct'] = budget_realloc['recommended_pct'] - budget_realloc['current_pct']

budget_realloc.to_csv('outputs/budget_reallocation.csv', index=False, encoding='utf-8')
print("✅ Exported: budget_reallocation.csv")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE!")
print("="*80)
print("\n📁 Output Files Generated:")
print("   ├── outputs/campaign_performance.csv")
print("   ├── outputs/channel_effectiveness.csv")
print("   ├── outputs/customer_segments.csv")
print("   ├── outputs/ab_test_results.csv")
print("   ├── outputs/budget_reallocation.csv")
print("   ├── outputs/reports/executive_summary.txt")
print("   ├── outputs/figures/roc_curve.png")
print("   ├── outputs/figures/feature_importance.png")
print("   └── outputs/figures/uplift_distribution.png")
print("\n🎯 Next Steps:")
print("   1. Review executive summary in outputs/reports/")
print("   2. Import CSV files into Power BI")
print("   3. Use budget reallocation recommendations")
print("   4. Implement uplift-based targeting strategy")
print("\n" + "="*80)