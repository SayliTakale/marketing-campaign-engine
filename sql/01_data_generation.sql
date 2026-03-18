-- ============================================================================
-- Marketing Campaign Database Setup
-- ============================================================================
-- Purpose: Create database schema and load simulated campaign data
-- Author: Marketing Analytics Team
-- Date: 2026-02-08
-- ============================================================================

-- Create database (SQLite)
-- For production, replace with appropriate CREATE DATABASE statement

-- ============================================================================
-- TABLE 1: CUSTOMERS
-- ============================================================================
-- Contains demographic and behavioral data for all customers

DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    age INTEGER NOT NULL,
    gender TEXT CHECK(gender IN ('M', 'F', 'Other')),
    geography TEXT NOT NULL,
    income_band TEXT NOT NULL,
    customer_tenure INTEGER NOT NULL,  -- in months
    historical_spend REAL NOT NULL,
    product_count INTEGER NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance
CREATE INDEX idx_customers_geography ON customers(geography);
CREATE INDEX idx_customers_income ON customers(income_band);
CREATE INDEX idx_customers_tenure ON customers(customer_tenure);

-- Table purpose: customer demographic and behavioral attributes

-- ============================================================================
-- TABLE 2: CAMPAIGNS
-- ============================================================================
-- Campaign metadata and definitions

DROP TABLE IF EXISTS campaigns;

CREATE TABLE campaigns (
    campaign_id TEXT PRIMARY KEY,
    campaign_name TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('Email', 'Push', 'SMS', 'Paid Social', 'Search')),
    campaign_type TEXT CHECK(campaign_type IN ('Acquisition', 'Retention', 'Winback', 'Cross-sell')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_channel ON campaigns(channel);
CREATE INDEX idx_campaigns_dates ON campaigns(start_date, end_date);

-- Table purpose: campaign definitions and metadata

-- ============================================================================
-- TABLE 3: CAMPAIGN EXPOSURES
-- ============================================================================
-- Records of customer exposures to campaigns (treatment + control)

DROP TABLE IF EXISTS exposures;

CREATE TABLE exposures (
    exposure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    exposure_date DATE NOT NULL,
    cost_per_contact REAL NOT NULL,
    treatment_group INTEGER NOT NULL CHECK(treatment_group IN (0, 1)),  -- 1 = treatment, 0 = control
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

-- Indexes for query performance
CREATE INDEX idx_exposures_customer ON exposures(customer_id);
CREATE INDEX idx_exposures_campaign ON exposures(campaign_id);
CREATE INDEX idx_exposures_treatment ON exposures(treatment_group);
CREATE INDEX idx_exposures_date ON exposures(exposure_date);

-- Ensure one exposure per customer per campaign
CREATE UNIQUE INDEX idx_exposures_unique ON exposures(customer_id, campaign_id);

-- Table purpose: campaign exposure tracking with treatment assignment

-- ============================================================================
-- TABLE 4: CAMPAIGN OUTCOMES
-- ============================================================================
-- Conversion events and revenue generated

DROP TABLE IF EXISTS outcomes;

CREATE TABLE outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    treatment_group INTEGER NOT NULL,
    converted INTEGER NOT NULL CHECK(converted IN (0, 1)),
    conversion_date DATE,
    revenue_generated REAL NOT NULL DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX idx_outcomes_customer ON outcomes(customer_id);
CREATE INDEX idx_outcomes_campaign ON outcomes(campaign_id);
CREATE INDEX idx_outcomes_converted ON outcomes(converted);
CREATE INDEX idx_outcomes_treatment ON outcomes(treatment_group);

-- Table purpose: campaign conversion outcomes and revenue

-- ============================================================================
-- DATA LOADING
-- ============================================================================
-- Load data from CSV files
-- Adjust paths as needed for your environment

.mode csv

.import data/simulated/customers.csv customers
.import data/simulated/campaigns.csv campaigns
.import data/simulated/exposures.csv exposures
.import data/simulated/outcomes.csv outcomes

-- ============================================================================
-- DATA QUALITY CHECKS
-- ============================================================================

-- Check row counts
SELECT 'Customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL
SELECT 'Campaigns', COUNT(*) FROM campaigns
UNION ALL
SELECT 'Exposures', COUNT(*) FROM exposures
UNION ALL
SELECT 'Outcomes', COUNT(*) FROM outcomes;

-- Check for NULL values in critical columns
SELECT 'NULL customer_id' AS issue, COUNT(*) AS count 
FROM customers WHERE customer_id IS NULL
UNION ALL
SELECT 'NULL campaign_id', COUNT(*) 
FROM campaigns WHERE campaign_id IS NULL
UNION ALL
SELECT 'NULL exposure treatment', COUNT(*) 
FROM exposures WHERE treatment_group IS NULL;

-- Verify foreign key integrity
SELECT 'Orphaned exposures' AS issue, COUNT(*) AS count
FROM exposures e
LEFT JOIN customers c ON e.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

-- Check data distributions
SELECT 
    'Customer Demographics' AS metric,
    COUNT(DISTINCT geography) AS geographies,
    COUNT(DISTINCT income_band) AS income_bands,
    MIN(age) AS min_age,
    MAX(age) AS max_age,
    AVG(customer_tenure) AS avg_tenure
FROM customers;

SELECT
    'Campaign Summary' AS metric,
    COUNT(*) AS total_campaigns,
    COUNT(DISTINCT channel) AS channels,
    MIN(start_date) AS earliest_campaign,
    MAX(end_date) AS latest_campaign
FROM campaigns;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

SELECT '✅ Database setup complete!' AS status;
SELECT 'Ready for attribution analysis' AS next_step;