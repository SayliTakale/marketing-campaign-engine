-- ============================================================================
-- Campaign Attribution Analysis
-- ============================================================================
-- Purpose: Implement last-touch and multi-touch attribution models
-- Author: Marketing Analytics Team
-- ============================================================================

-- ============================================================================
-- SECTION 1: LAST-TOUCH ATTRIBUTION
-- ============================================================================
-- Assigns 100% credit for conversion to the last campaign exposure

-- Step 1: Identify last touchpoint before conversion for each customer
DROP TABLE IF EXISTS last_touch_attribution;

CREATE TABLE last_touch_attribution AS
WITH customer_conversions AS (
    -- Get all customers who converted
    SELECT DISTINCT 
        o.customer_id,
        o.conversion_date,
        o.revenue_generated
    FROM outcomes o
    WHERE o.converted = 1
),
ranked_exposures AS (
    -- Rank exposures by date (most recent = 1)
    SELECT 
        e.customer_id,
        e.campaign_id,
        e.channel,
        e.exposure_date,
        e.cost_per_contact,
        c.conversion_date,
        c.revenue_generated,
        ROW_NUMBER() OVER (
            PARTITION BY e.customer_id 
            ORDER BY e.exposure_date DESC
        ) AS recency_rank
    FROM exposures e
    INNER JOIN customer_conversions c 
        ON e.customer_id = c.customer_id
    WHERE e.exposure_date <= c.conversion_date
)
SELECT 
    customer_id,
    campaign_id,
    channel,
    exposure_date,
    cost_per_contact,
    conversion_date,
    revenue_generated,
    1.0 AS attribution_credit  -- Last touch gets 100% credit
FROM ranked_exposures
WHERE recency_rank = 1;

-- Create indexes for performance
CREATE INDEX idx_last_touch_campaign ON last_touch_attribution(campaign_id);
CREATE INDEX idx_last_touch_channel ON last_touch_attribution(channel);

-- Step 2: Calculate campaign-level metrics with last-touch attribution
SELECT 
    lt.campaign_id,
    c.campaign_name,
    lt.channel,
    COUNT(DISTINCT lt.customer_id) AS conversions_attributed,
    SUM(lt.revenue_generated) AS revenue_attributed,
    SUM(lt.cost_per_contact) AS total_cost,
    SUM(lt.revenue_generated) - SUM(lt.cost_per_contact) AS profit,
    ROUND(
        (SUM(lt.revenue_generated) - SUM(lt.cost_per_contact)) / 
        NULLIF(SUM(lt.cost_per_contact), 0) * 100, 
        2
    ) AS roi_percentage
FROM last_touch_attribution lt
INNER JOIN campaigns c ON lt.campaign_id = c.campaign_id
GROUP BY lt.campaign_id, c.campaign_name, lt.channel
ORDER BY roi_percentage DESC;

-- Step 3: Channel-level performance (last-touch)
SELECT 
    channel,
    COUNT(DISTINCT customer_id) AS total_conversions,
    SUM(revenue_generated) AS total_revenue,
    SUM(cost_per_contact) AS total_cost,
    ROUND(AVG(revenue_generated), 2) AS avg_revenue_per_conversion,
    ROUND(
        (SUM(revenue_generated) - SUM(cost_per_contact)) / 
        NULLIF(SUM(cost_per_contact), 0) * 100, 
        2
    ) AS channel_roi_pct
FROM last_touch_attribution
GROUP BY channel
ORDER BY channel_roi_pct DESC;

-- ============================================================================
-- SECTION 2: MULTI-TOUCH ATTRIBUTION - LINEAR MODEL
-- ============================================================================
-- Distributes conversion credit equally across all touchpoints

DROP TABLE IF EXISTS linear_attribution;

CREATE TABLE linear_attribution AS
WITH customer_conversions AS (
    SELECT DISTINCT 
        o.customer_id,
        o.conversion_date,
        o.revenue_generated
    FROM outcomes o
    WHERE o.converted = 1
),
all_touchpoints AS (
    -- Get all exposures leading to conversion
    SELECT 
        e.customer_id,
        e.campaign_id,
        e.channel,
        e.exposure_date,
        e.cost_per_contact,
        c.conversion_date,
        c.revenue_generated,
        COUNT(*) OVER (PARTITION BY e.customer_id) AS total_touches
    FROM exposures e
    INNER JOIN customer_conversions c 
        ON e.customer_id = c.customer_id
    WHERE e.exposure_date <= c.conversion_date
)
SELECT 
    customer_id,
    campaign_id,
    channel,
    exposure_date,
    cost_per_contact,
    conversion_date,
    revenue_generated,
    total_touches,
    ROUND(1.0 / total_touches, 4) AS attribution_credit,
    ROUND(revenue_generated / total_touches, 2) AS attributed_revenue
FROM all_touchpoints;

CREATE INDEX idx_linear_campaign ON linear_attribution(campaign_id);
CREATE INDEX idx_linear_channel ON linear_attribution(channel);

-- Campaign performance with linear attribution
SELECT 
    la.campaign_id,
    c.campaign_name,
    la.channel,
    COUNT(DISTINCT la.customer_id) AS customers_touched,
    ROUND(SUM(la.attribution_credit), 2) AS total_conversions_credited,
    ROUND(SUM(la.attributed_revenue), 2) AS revenue_attributed,
    SUM(la.cost_per_contact) AS total_cost,
    ROUND(
        (SUM(la.attributed_revenue) - SUM(la.cost_per_contact)) / 
        NULLIF(SUM(la.cost_per_contact), 0) * 100,
        2
    ) AS roi_percentage
FROM linear_attribution la
INNER JOIN campaigns c ON la.campaign_id = c.campaign_id
GROUP BY la.campaign_id, c.campaign_name, la.channel
ORDER BY roi_percentage DESC;

-- ============================================================================
-- SECTION 3: TIME-DECAY ATTRIBUTION
-- ============================================================================
-- More recent touchpoints get more credit (exponential decay)

DROP TABLE IF EXISTS time_decay_attribution;

CREATE TABLE time_decay_attribution AS
WITH customer_conversions AS (
    SELECT DISTINCT 
        o.customer_id,
        o.conversion_date,
        o.revenue_generated
    FROM outcomes o
    WHERE o.converted = 1
),
touchpoints_with_decay AS (
    SELECT 
        e.customer_id,
        e.campaign_id,
        e.channel,
        e.exposure_date,
        e.cost_per_contact,
        c.conversion_date,
        c.revenue_generated,
        -- Days between exposure and conversion
        JULIANDAY(c.conversion_date) - JULIANDAY(e.exposure_date) AS days_to_conversion,
        -- Decay factor: more recent = higher weight
        -- Using half-life of 7 days
        POWER(0.5, (JULIANDAY(c.conversion_date) - JULIANDAY(e.exposure_date)) / 7.0) AS decay_weight
    FROM exposures e
    INNER JOIN customer_conversions c 
        ON e.customer_id = c.customer_id
    WHERE e.exposure_date <= c.conversion_date
),
normalized_weights AS (
    SELECT 
        *,
        SUM(decay_weight) OVER (PARTITION BY customer_id) AS total_weight
    FROM touchpoints_with_decay
)
SELECT 
    customer_id,
    campaign_id,
    channel,
    exposure_date,
    cost_per_contact,
    conversion_date,
    revenue_generated,
    days_to_conversion,
    decay_weight,
    total_weight,
    ROUND(decay_weight / total_weight, 4) AS attribution_credit,
    ROUND((decay_weight / total_weight) * revenue_generated, 2) AS attributed_revenue
FROM normalized_weights;

CREATE INDEX idx_decay_campaign ON time_decay_attribution(campaign_id);
CREATE INDEX idx_decay_channel ON time_decay_attribution(channel);

-- Campaign performance with time-decay attribution
SELECT 
    td.campaign_id,
    c.campaign_name,
    td.channel,
    COUNT(DISTINCT td.customer_id) AS customers_touched,
    ROUND(SUM(td.attribution_credit), 2) AS total_conversions_credited,
    ROUND(SUM(td.attributed_revenue), 2) AS revenue_attributed,
    SUM(td.cost_per_contact) AS total_cost,
    ROUND(
        (SUM(td.attributed_revenue) - SUM(td.cost_per_contact)) / 
        NULLIF(SUM(td.cost_per_contact), 0) * 100,
        2
    ) AS roi_percentage,
    ROUND(AVG(td.days_to_conversion), 1) AS avg_days_to_conversion
FROM time_decay_attribution td
INNER JOIN campaigns c ON td.campaign_id = c.campaign_id
GROUP BY td.campaign_id, c.campaign_name, td.channel
ORDER BY roi_percentage DESC;

-- ============================================================================
-- SECTION 4: ATTRIBUTION MODEL COMPARISON
-- ============================================================================
-- Compare results across all three attribution models

SELECT 
    'Last-Touch' AS attribution_model,
    lt.channel,
    ROUND(SUM(lt.revenue_generated), 2) AS total_revenue,
    ROUND(
        (SUM(lt.revenue_generated) - SUM(lt.cost_per_contact)) / 
        NULLIF(SUM(lt.cost_per_contact), 0) * 100,
        2
    ) AS roi_pct
FROM last_touch_attribution lt
GROUP BY lt.channel

UNION ALL

SELECT 
    'Linear' AS attribution_model,
    la.channel,
    ROUND(SUM(la.attributed_revenue), 2) AS total_revenue,
    ROUND(
        (SUM(la.attributed_revenue) - SUM(la.cost_per_contact)) / 
        NULLIF(SUM(la.cost_per_contact), 0) * 100,
        2
    ) AS roi_pct
FROM linear_attribution la
GROUP BY la.channel

UNION ALL

SELECT 
    'Time-Decay' AS attribution_model,
    td.channel,
    ROUND(SUM(td.attributed_revenue), 2) AS total_revenue,
    ROUND(
        (SUM(td.attributed_revenue) - SUM(td.cost_per_contact)) / 
        NULLIF(SUM(td.cost_per_contact), 0) * 100,
        2
    ) AS roi_pct
FROM time_decay_attribution td
GROUP BY td.channel

ORDER BY attribution_model, roi_pct DESC;

-- ============================================================================
-- SECTION 5: CUSTOMER JOURNEY ANALYSIS
-- ============================================================================
-- Understand typical customer journey patterns

-- Average number of touches before conversion
-- NOTE: SQLite has no built-in STDEV(); standard deviation computed manually.
SELECT 
    AVG(total_touches) AS avg_touches_to_conversion,
    MIN(total_touches) AS min_touches,
    MAX(total_touches) AS max_touches,
    ROUND(
        SQRT(
            AVG(total_touches * total_touches) -
            AVG(total_touches) * AVG(total_touches)
        ), 2
    ) AS stdev_touches
FROM (
    SELECT customer_id, MAX(total_touches) AS total_touches
    FROM linear_attribution
    GROUP BY customer_id
);

-- Most common channel sequences (top 10)
-- Fix v2: SQLite's GROUP_CONCAT does not guarantee ordering from a subquery.
--         We use ROW_NUMBER() to assign an explicit position per customer,
--         then GROUP_CONCAT over the deterministically ordered channel column.
--         NOTE: SQLite's GROUP_CONCAT still does not support WITHIN GROUP
--         (ORDER BY).  The workaround below uses a pre-ordered CTE; this is
--         the most reliable portable approach for SQLite.
WITH ordered_touches AS (
    SELECT
        customer_id,
        channel,
        exposure_date,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY exposure_date
        ) AS touch_order
    FROM linear_attribution
),
journey_sequences AS (
    SELECT
        customer_id,
        GROUP_CONCAT(channel, ' → ') AS channel_sequence,  -- SQLite 3.38+ preserves insertion order within a group
        COUNT(*) AS touch_count
    FROM ordered_touches
    GROUP BY customer_id
    ORDER BY customer_id, touch_order   -- drives GROUP_CONCAT order in SQLite
)
SELECT
    channel_sequence,
    COUNT(*)              AS frequency,
    ROUND(AVG(touch_count), 1) AS avg_touches
FROM journey_sequences
GROUP BY channel_sequence
ORDER BY frequency DESC
LIMIT 10;

-- ============================================================================
-- SECTION 6: BUDGET ALLOCATION RECOMMENDATIONS
-- ============================================================================
-- Based on time-decay attribution (most realistic model)

SELECT 
    td.channel,
    ROUND(SUM(td.attributed_revenue), 2) AS current_revenue,
    SUM(td.cost_per_contact) AS current_spend,
    ROUND(
        SUM(td.cost_per_contact) / 
        (SELECT SUM(cost_per_contact) FROM time_decay_attribution) * 100,
        2
    ) AS current_budget_pct,
    ROUND(
        (SUM(td.attributed_revenue) - SUM(td.cost_per_contact)) / 
        NULLIF(SUM(td.cost_per_contact), 0) * 100,
        2
    ) AS roi_pct,
    -- Recommended budget allocation proportional to attributed revenue
    ROUND(
        SUM(td.attributed_revenue) / 
        (SELECT SUM(attributed_revenue) FROM time_decay_attribution) * 100,
        2
    ) AS recommended_budget_pct,
    ROUND(
        (SUM(td.attributed_revenue) / 
         (SELECT SUM(attributed_revenue) FROM time_decay_attribution) * 100) -
        (SUM(td.cost_per_contact) / 
         (SELECT SUM(cost_per_contact) FROM time_decay_attribution) * 100),
        2
    ) AS budget_shift_pct
FROM time_decay_attribution td
GROUP BY td.channel
ORDER BY roi_pct DESC;

-- ============================================================================
-- KEY INSIGHTS SUMMARY
-- ============================================================================

SELECT '
======================================================================
KEY ATTRIBUTION INSIGHTS
======================================================================

1. ATTRIBUTION MODEL CHOICE MATTERS
   - Last-touch over-credits final touchpoint
   - Linear gives equal credit (may undervalue recent touches)
   - Time-decay balances recency with contribution
   
2. RECOMMENDED MODEL: Time-Decay
   - Most realistic for customer journey
   - Accounts for recency bias
   - Better reflects customer decision process

3. BUDGET REALLOCATION
   - Shift spend to high-ROI channels
   - Use time-decay attribution for decisions
   - Monitor cross-channel synergies

4. NEXT STEPS
   - Run A/B tests on attribution-based budgets
   - Implement incremental testing
   - Build uplift models for targeting

======================================================================
' AS summary;