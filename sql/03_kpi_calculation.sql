-- ============================================================================
-- Campaign KPI Calculation & Performance Metrics
-- ============================================================================
-- Purpose: Calculate core marketing KPIs with treatment vs control analysis
-- Author: Marketing Analytics Team
-- ============================================================================

-- ============================================================================
-- SECTION 1: CAMPAIGN-LEVEL KPIs
-- ============================================================================

DROP TABLE IF EXISTS campaign_kpis;

CREATE TABLE campaign_kpis AS
WITH campaign_metrics AS (
    SELECT 
        e.campaign_id,
        c.campaign_name,
        e.channel,
        c.campaign_type,
        c.start_date,
        c.end_date,
        
        -- Treatment group metrics
        COUNT(CASE WHEN e.treatment_group = 1 THEN 1 END) AS treatment_size,
        SUM(CASE WHEN e.treatment_group = 1 THEN e.cost_per_contact ELSE 0 END) AS treatment_cost,
        SUM(CASE WHEN e.treatment_group = 1 AND o.converted = 1 THEN 1 ELSE 0 END) AS treatment_conversions,
        SUM(CASE WHEN e.treatment_group = 1 THEN o.revenue_generated ELSE 0 END) AS treatment_revenue,
        
        -- Control group metrics
        COUNT(CASE WHEN e.treatment_group = 0 THEN 1 END) AS control_size,
        SUM(CASE WHEN e.treatment_group = 0 THEN e.cost_per_contact ELSE 0 END) AS control_cost,
        SUM(CASE WHEN e.treatment_group = 0 AND o.converted = 1 THEN 1 ELSE 0 END) AS control_conversions,
        SUM(CASE WHEN e.treatment_group = 0 THEN o.revenue_generated ELSE 0 END) AS control_revenue
        
    FROM exposures e
    INNER JOIN campaigns c ON e.campaign_id = c.campaign_id
    INNER JOIN outcomes o ON e.customer_id = o.customer_id AND e.campaign_id = o.campaign_id
    GROUP BY e.campaign_id, c.campaign_name, e.channel, c.campaign_type, c.start_date, c.end_date
)
SELECT 
    campaign_id,
    campaign_name,
    channel,
    campaign_type,
    start_date,
    end_date,
    
    -- Sample sizes
    treatment_size,
    control_size,
    treatment_size + control_size AS total_exposed,
    
    -- Costs
    ROUND(treatment_cost, 2) AS treatment_cost,
    ROUND(control_cost, 2) AS control_cost,
    ROUND(treatment_cost + control_cost, 2) AS total_cost,
    ROUND(treatment_cost / NULLIF(treatment_size, 0), 2) AS cost_per_contact,
    
    -- Conversions
    treatment_conversions,
    control_conversions,
    ROUND(treatment_conversions * 1.0 / NULLIF(treatment_size, 0), 4) AS treatment_conv_rate,
    ROUND(control_conversions * 1.0 / NULLIF(control_size, 0), 4) AS control_conv_rate,
    
    -- Conversion lift
    ROUND(
        (treatment_conversions * 1.0 / NULLIF(treatment_size, 0)) - 
        (control_conversions * 1.0 / NULLIF(control_size, 0)),
        4
    ) AS absolute_lift,
    ROUND(
        ((treatment_conversions * 1.0 / NULLIF(treatment_size, 0)) - 
         (control_conversions * 1.0 / NULLIF(control_size, 0))) /
        NULLIF((control_conversions * 1.0 / NULLIF(control_size, 0)), 0) * 100,
        2
    ) AS relative_lift_pct,
    
    -- Revenue
    ROUND(treatment_revenue, 2) AS treatment_revenue,
    ROUND(control_revenue, 2) AS control_revenue,
    ROUND(treatment_revenue / NULLIF(treatment_size, 0), 2) AS treatment_revenue_per_user,
    ROUND(control_revenue / NULLIF(control_size, 0), 2) AS control_revenue_per_user,
    
    -- Incremental revenue (KEY METRIC)
    ROUND(
        (treatment_revenue / NULLIF(treatment_size, 0)) - 
        (control_revenue / NULLIF(control_size, 0)),
        2
    ) AS incremental_revenue_per_user,
    ROUND(
        ((treatment_revenue / NULLIF(treatment_size, 0)) - 
         (control_revenue / NULLIF(control_size, 0))) * treatment_size,
        2
    ) AS total_incremental_revenue,
    
    -- ROI metrics
    ROUND(
        (((treatment_revenue / NULLIF(treatment_size, 0)) - 
          (control_revenue / NULLIF(control_size, 0))) * treatment_size - treatment_cost) /
        NULLIF(treatment_cost, 0) * 100,
        2
    ) AS roi_percentage,
    
    -- Customer acquisition cost (for converters only)
    ROUND(
        treatment_cost / NULLIF(treatment_conversions, 0),
        2
    ) AS cac,
    
    -- Profit
    ROUND(
        ((treatment_revenue / NULLIF(treatment_size, 0)) - 
         (control_revenue / NULLIF(control_size, 0))) * treatment_size - treatment_cost,
        2
    ) AS profit

FROM campaign_metrics;

-- Create indexes
CREATE INDEX idx_campaign_kpis_campaign ON campaign_kpis(campaign_id);
CREATE INDEX idx_campaign_kpis_channel ON campaign_kpis(channel);
CREATE INDEX idx_campaign_kpis_roi ON campaign_kpis(roi_percentage);

-- Display top performers
SELECT 
    campaign_id,
    campaign_name,
    channel,
    treatment_conv_rate,
    control_conv_rate,
    relative_lift_pct,
    total_incremental_revenue,
    roi_percentage,
    profit
FROM campaign_kpis
ORDER BY roi_percentage DESC
LIMIT 10;

-- ============================================================================
-- SECTION 2: CHANNEL-LEVEL KPIs
-- ============================================================================

DROP TABLE IF EXISTS channel_kpis;

CREATE TABLE channel_kpis AS
SELECT 
    channel,
    
    -- Campaign count
    COUNT(DISTINCT campaign_id) AS n_campaigns,
    
    -- Sample sizes
    SUM(treatment_size) AS total_treatment,
    SUM(control_size) AS total_control,
    SUM(total_exposed) AS total_exposed,
    
    -- Costs
    ROUND(SUM(treatment_cost), 2) AS total_cost,
    ROUND(AVG(cost_per_contact), 2) AS avg_cost_per_contact,
    
    -- Conversions
    SUM(treatment_conversions) AS total_conversions,
    ROUND(
        SUM(treatment_conversions) * 1.0 / NULLIF(SUM(treatment_size), 0),
        4
    ) AS avg_conv_rate,
    ROUND(
        AVG(relative_lift_pct),
        2
    ) AS avg_lift_pct,
    
    -- Revenue
    ROUND(SUM(treatment_revenue), 2) AS total_revenue,
    ROUND(SUM(total_incremental_revenue), 2) AS total_incremental_revenue,
    ROUND(AVG(treatment_revenue_per_user), 2) AS avg_revenue_per_user,
    
    -- ROI
    ROUND(
        (SUM(total_incremental_revenue) - SUM(treatment_cost)) / 
        NULLIF(SUM(treatment_cost), 0) * 100,
        2
    ) AS channel_roi_pct,
    
    -- CAC
    ROUND(
        SUM(treatment_cost) / NULLIF(SUM(treatment_conversions), 0),
        2
    ) AS avg_cac,
    
    -- Profit
    ROUND(SUM(profit), 2) AS total_profit

FROM campaign_kpis
GROUP BY channel
ORDER BY channel_roi_pct DESC;

-- Display channel summary
SELECT * FROM channel_kpis;

-- ============================================================================
-- SECTION 3: TIME-SERIES PERFORMANCE
-- ============================================================================

-- Weekly campaign performance
SELECT 
    STRFTIME('%Y-%W', start_date) AS week,
    COUNT(DISTINCT campaign_id) AS campaigns_launched,
    SUM(treatment_size) AS total_reached,
    SUM(treatment_conversions) AS total_conversions,
    ROUND(SUM(treatment_revenue), 2) AS total_revenue,
    ROUND(SUM(treatment_cost), 2) AS total_cost,
    ROUND(
        (SUM(total_incremental_revenue) - SUM(treatment_cost)) / 
        NULLIF(SUM(treatment_cost), 0) * 100,
        2
    ) AS weekly_roi_pct
FROM campaign_kpis
GROUP BY STRFTIME('%Y-%W', start_date)
ORDER BY week;

-- ============================================================================
-- SECTION 4: SEGMENT PERFORMANCE
-- ============================================================================

-- Campaign type performance
SELECT 
    campaign_type,
    COUNT(*) AS n_campaigns,
    ROUND(AVG(treatment_conv_rate), 4) AS avg_conv_rate,
    ROUND(AVG(relative_lift_pct), 2) AS avg_lift_pct,
    ROUND(SUM(total_incremental_revenue), 2) AS total_incremental_revenue,
    ROUND(AVG(roi_percentage), 2) AS avg_roi_pct,
    SUM(CASE WHEN roi_percentage > 0 THEN 1 ELSE 0 END) AS profitable_campaigns,
    ROUND(
        SUM(CASE WHEN roi_percentage > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS profitable_pct
FROM campaign_kpis
GROUP BY campaign_type
ORDER BY avg_roi_pct DESC;

-- ============================================================================
-- SECTION 5: COST EFFICIENCY ANALYSIS
-- ============================================================================

-- Cost per conversion by channel
SELECT 
    channel,
    ROUND(AVG(cac), 2) AS avg_cac,
    ROUND(MIN(cac), 2) AS min_cac,
    ROUND(MAX(cac), 2) AS max_cac,
    ROUND(AVG(treatment_revenue_per_user / NULLIF(cac, 0)), 2) AS revenue_to_cac_ratio
FROM campaign_kpis
WHERE cac IS NOT NULL
GROUP BY channel
ORDER BY avg_cac;

-- Budget efficiency score (combination of ROI and conversion lift)
SELECT 
    campaign_id,
    campaign_name,
    channel,
    roi_percentage,
    relative_lift_pct,
    -- Composite efficiency score (weighted average)
    ROUND(
        (roi_percentage * 0.6) + (relative_lift_pct * 0.4),
        2
    ) AS efficiency_score
FROM campaign_kpis
ORDER BY efficiency_score DESC
LIMIT 20;

-- ============================================================================
-- SECTION 6: ACTIONABLE INSIGHTS & RECOMMENDATIONS
-- ============================================================================

-- Campaigns to KILL (negative ROI)
CREATE VIEW campaigns_to_kill AS
SELECT 
    campaign_id,
    campaign_name,
    channel,
    roi_percentage,
    profit,
    'KILL - Negative ROI' AS recommendation
FROM campaign_kpis
WHERE roi_percentage < 0
ORDER BY profit;

-- Campaigns to SCALE (high ROI, statistically significant lift)
CREATE VIEW campaigns_to_scale AS
SELECT 
    campaign_id,
    campaign_name,
    channel,
    roi_percentage,
    relative_lift_pct,
    total_incremental_revenue,
    'SCALE - High Performance' AS recommendation
FROM campaign_kpis
WHERE roi_percentage > 50 
  AND relative_lift_pct > 10
  AND treatment_size > 1000  -- Sufficient sample size
ORDER BY roi_percentage DESC;

-- Campaigns to OPTIMIZE (positive but low ROI)
CREATE VIEW campaigns_to_optimize AS
SELECT 
    campaign_id,
    campaign_name,
    channel,
    roi_percentage,
    relative_lift_pct,
    'OPTIMIZE - Improve Efficiency' AS recommendation
FROM campaign_kpis
WHERE roi_percentage BETWEEN 0 AND 30
ORDER BY treatment_size DESC;  -- Prioritize large campaigns

-- ============================================================================
-- SECTION 7: EXECUTIVE DASHBOARD EXPORT
-- ============================================================================

-- Summary metrics for dashboard
CREATE VIEW executive_summary AS
SELECT 
    -- Overall metrics
    COUNT(DISTINCT campaign_id) AS total_campaigns,
    SUM(total_exposed) AS total_customers_reached,
    ROUND(SUM(treatment_cost), 2) AS total_spend,
    SUM(treatment_conversions) AS total_conversions,
    ROUND(SUM(treatment_revenue), 2) AS total_revenue,
    ROUND(SUM(total_incremental_revenue), 2) AS total_incremental_revenue,
    ROUND(
        (SUM(total_incremental_revenue) - SUM(treatment_cost)) / 
        NULLIF(SUM(treatment_cost), 0) * 100,
        2
    ) AS overall_roi_pct,
    ROUND(SUM(profit), 2) AS total_profit,
    
    -- Performance indicators
    SUM(CASE WHEN roi_percentage > 0 THEN 1 ELSE 0 END) AS profitable_campaigns,
    SUM(CASE WHEN roi_percentage < 0 THEN 1 ELSE 0 END) AS unprofitable_campaigns,
    ROUND(AVG(treatment_conv_rate), 4) AS avg_conversion_rate,
    ROUND(AVG(relative_lift_pct), 2) AS avg_lift_pct
    
FROM campaign_kpis;

-- Display executive summary
SELECT * FROM executive_summary;

-- Top and bottom performers
SELECT 'TOP 5 CAMPAIGNS' AS category, campaign_name, channel, roi_percentage 
FROM campaign_kpis ORDER BY roi_percentage DESC LIMIT 5
UNION ALL
SELECT 'BOTTOM 5 CAMPAIGNS' AS category, campaign_name, channel, roi_percentage 
FROM campaign_kpis ORDER BY roi_percentage LIMIT 5;

-- ============================================================================
-- FINAL KPI SUMMARY
-- ============================================================================

SELECT '
======================================================================
KPI CALCULATION COMPLETE
======================================================================

Tables Created:
✅ campaign_kpis    - Campaign-level performance metrics
✅ channel_kpis     - Channel aggregated metrics
✅ executive_summary - High-level dashboard metrics

Views Created:
✅ campaigns_to_kill     - Negative ROI campaigns
✅ campaigns_to_scale    - High-performing campaigns
✅ campaigns_to_optimize - Mid-tier campaigns

Key Metrics Available:
- Conversion rates (treatment vs control)
- Incremental revenue
- ROI percentage
- Customer acquisition cost (CAC)
- Profit/loss by campaign

Next Steps:
→ Export data for Power BI
→ Run statistical significance tests
→ Build predictive models

======================================================================
' AS summary;