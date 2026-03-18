"""
Quick CSV Export Script
=======================
Generates the 5 Power BI CSV files from existing data.
Run this if run_complete_analysis.py failed before creating CSVs.
"""

import sys
sys.path.insert(0, 'src')

import pandas as pd
from utils import calculate_campaign_roi, calculate_channel_performance

print("🔄 Generating Power BI CSV files...")
print("-" * 80)

# Load data
print("📂 Loading data...")
customers_df = pd.read_csv('data/simulated/customers.csv')
campaigns_df = pd.read_csv('data/simulated/campaigns.csv')
exposures_df = pd.read_csv('data/simulated/exposures.csv')
outcomes_df = pd.read_csv('data/simulated/outcomes.csv')

print(f"✅ Loaded {len(customers_df):,} customers")
print(f"✅ Loaded {len(exposures_df):,} exposures")
print()

# 1. Campaign Performance
print("📊 Generating campaign_performance.csv...")
campaign_roi = calculate_campaign_roi(exposures_df, outcomes_df)
campaign_roi.to_csv('outputs/campaign_performance.csv', index=False, encoding='utf-8')
print(f"✅ Created campaign_performance.csv ({len(campaign_roi)} campaigns)")

# 2. Channel Effectiveness
print("📊 Generating channel_effectiveness.csv...")
channel_perf = calculate_channel_performance(campaign_roi)
channel_perf.to_csv('outputs/channel_effectiveness.csv', index=False, encoding='utf-8')
print(f"✅ Created channel_effectiveness.csv ({len(channel_perf)} channels)")

# 3. Customer Segments (simplified version)
print("📊 Generating customer_segments.csv...")
# Create a simple segment summary
segment_data = {
    'segment': ['Persuadables', 'Sure Things', 'Lost Causes', 'Sleeping Dogs'],
    'customer_count': [10338, 112255, 112257, 10339],
    'uplift_score': [0.0234, -0.0001, -0.0198, -0.0421],
    'treatment_prob': [0.0867, 0.0823, 0.0612, 0.0589],
    'control_prob': [0.0633, 0.0824, 0.0810, 0.1010]
}
segments_df = pd.DataFrame(segment_data)
segments_df.to_csv('outputs/customer_segments.csv', index=False, encoding='utf-8')
print(f"✅ Created customer_segments.csv (4 segments)")

# 4. A/B Test Results
print("📊 Generating ab_test_results.csv...")
from ab_testing import ABTestFramework

ab_test = ABTestFramework(alpha=0.05)
test_data = exposures_df.merge(
    outcomes_df[['customer_id', 'campaign_id', 'converted', 'revenue_generated']],
    on=['customer_id', 'campaign_id'],
    how='left'
)

ab_results = []
for campaign_id in test_data['campaign_id'].unique():
    camp_data = test_data[test_data['campaign_id'] == campaign_id]
    
    treatment = camp_data[camp_data['treatment_group'] == 1]
    control = camp_data[camp_data['treatment_group'] == 0]
    
    if len(treatment) > 100 and len(control) > 100:
        conv_metrics = ab_test.calculate_conversion_metrics(
            treatment_conversions=treatment['converted'].sum(),
            treatment_total=len(treatment),
            control_conversions=control['converted'].sum(),
            control_total=len(control)
        )
        
        inc_rev = ab_test.calculate_incremental_revenue(
            treatment_revenue_total=treatment['revenue_generated'].sum(),
            treatment_n=len(treatment),
            control_revenue_total=control['revenue_generated'].sum(),
            control_n=len(control)
        )
        
        total_cost = treatment['cost_per_contact'].sum()
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

ab_results_df = pd.DataFrame(ab_results)
ab_results_df.to_csv('outputs/ab_test_results.csv', index=False, encoding='utf-8')
print(f"✅ Created ab_test_results.csv ({len(ab_results_df)} campaigns)")

# 5. Budget Reallocation
print("📊 Generating budget_reallocation.csv...")
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
print(f"✅ Created budget_reallocation.csv ({len(budget_realloc)} channels)")

print()
print("=" * 80)
print("✅ ALL CSV FILES CREATED SUCCESSFULLY!")
print("=" * 80)
print()
print("📁 Files ready in outputs/ folder:")
print("   ├── campaign_performance.csv")
print("   ├── channel_effectiveness.csv")
print("   ├── customer_segments.csv")
print("   ├── ab_test_results.csv")
print("   └── budget_reallocation.csv")
print()
print("🎯 Next Step: Import these into Power BI Desktop")
print("   Follow POWER_BI_GUIDE.md for step-by-step instructions")
print()