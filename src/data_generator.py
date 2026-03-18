"""
Data Generator for Marketing Campaign Simulation

Generates realistic customer, campaign, and conversion data
for testing and development of the optimization engine.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml


logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "data": {"n_customers": 100_000, "n_campaigns": 12, "treatment_ratio": 0.70},
    "channels": ["Email", "Push", "SMS", "Paid Social", "Search"],
    "costs": {"Email": 0.10, "Push": 0.05, "SMS": 0.15, "Paid Social": 2.50, "Search": 3.00},
    "campaigns": {"baseline_conversion_rate": 0.05},
}




class MarketingDataGenerator:
    """
    Generates realistic marketing campaign data with proper distributions
    and business logic for conversion patterns.
    """
    
    def __init__(self, config_path='config.yaml', random_seed=42):
        """
        Initialize data generator with configuration.
        
        Parameters:
        -----------
        config_path : str
            Path to YAML configuration file
        random_seed : int
            Random seed for reproducibility
        """
        try:
            import yaml
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info("Loaded configuration from '%s'.", config_path)
        except FileNotFoundError:
            logger.warning(
                "Config file '%s' not found — using built-in defaults. "
                "Create config.yaml to customise parameters.", config_path
            )
            self.config = DEFAULT_CONFIG
        except Exception as exc:
            logger.warning("Could not load '%s' (%s) — using defaults.", config_path, exc)
            self.config = DEFAULT_CONFIG
        
        np.random.seed(random_seed)
        self.random_seed = random_seed
        
    def generate_customer_table(self):
        """
        Generate customer demographic and behavioral data.
        
        Returns:
        --------
        pd.DataFrame
            Customer table with demographics and behavior
        """
        n = self.config['data']['n_customers']
        
        # Generate customer IDs
        customer_ids = [f"CUST_{str(i).zfill(8)}" for i in range(1, n+1)]
        
        # Age distribution (18-75, normal-ish around 45)
        ages = np.random.gamma(shape=5, scale=6, size=n) + 18
        ages = np.clip(ages, 18, 75).astype(int)
        
        # Gender distribution
        genders = np.random.choice(['M', 'F', 'Other'], size=n, p=[0.48, 0.48, 0.04])
        
        # Geography - realistic US distribution
        geographies = np.random.choice(
            ['Northeast', 'Southeast', 'Midwest', 'Southwest', 'West'],
            size=n,
            p=[0.18, 0.22, 0.21, 0.15, 0.24]
        )
        
        # Income bands - skewed towards middle/upper-middle
        income_bands = np.random.choice(
            ['<30K', '30-50K', '50-75K', '75-100K', '100-150K', '>150K'],
            size=n,
            p=[0.12, 0.18, 0.25, 0.22, 0.15, 0.08]
        )
        
        # Customer tenure in months (0-120)
        tenure = np.random.exponential(scale=24, size=n)
        tenure = np.clip(tenure, 0, 120).astype(int)
        
        # Historical spend - correlated with income and tenure
        income_multiplier = pd.Series(income_bands).map({
            '<30K': 0.3, '30-50K': 0.5, '50-75K': 0.7,
            '75-100K': 1.0, '100-150K': 1.5, '>150K': 2.5
        }).values
        
        tenure_multiplier = 1 + (tenure / 120) * 0.5
        
        base_spend = np.random.gamma(shape=2, scale=500, size=n)
        historical_spend = base_spend * income_multiplier * tenure_multiplier
        historical_spend = np.round(historical_spend, 2)
        
        # Product count - correlated with tenure and spend
        product_prob = np.clip((tenure / 60) * (historical_spend / 1000), 0.1, 0.8)
        product_count = np.random.binomial(n=5, p=product_prob) + 1
        
        df = pd.DataFrame({
            'customer_id': customer_ids,
            'age': ages,
            'gender': genders,
            'geography': geographies,
            'income_band': income_bands,
            'customer_tenure': tenure,
            'historical_spend': historical_spend,
            'product_count': product_count
        })
        
        return df
    
    def generate_campaign_metadata(self):
        """
        Generate campaign definitions.
        
        Returns:
        --------
        pd.DataFrame
            Campaign metadata
        """
        n_campaigns = self.config['data']['n_campaigns']
        channels = self.config['channels']
        
        campaigns = []
        for i in range(1, n_campaigns + 1):
            campaign = {
                'campaign_id': f"CAMP_{str(i).zfill(3)}",
                'campaign_name': f"Campaign {i}",
                'channel': np.random.choice(channels),
                'start_date': datetime(2024, 1, 1) + timedelta(days=np.random.randint(0, 365)),
                'campaign_type': np.random.choice(['Acquisition', 'Retention', 'Winback', 'Cross-sell'])
            }
            campaigns.append(campaign)
        
        df = pd.DataFrame(campaigns)
        df['end_date'] = df['start_date'] + timedelta(days=30)
        
        return df
    
    def generate_campaign_exposure(self, customer_df, campaign_df):
        """
        Generate campaign exposure data with treatment/control assignment.
        
        Parameters:
        -----------
        customer_df : pd.DataFrame
            Customer table
        campaign_df : pd.DataFrame
            Campaign metadata
            
        Returns:
        --------
        pd.DataFrame
            Campaign exposure table
        """
        exposures = []
        
        for _, campaign in campaign_df.iterrows():
            # Each campaign reaches 15-30% of customer base
            reach_pct = np.random.uniform(0.15, 0.30)
            n_exposed = int(len(customer_df) * reach_pct)
            
            # Randomly select customers (with some logic)
            # Higher tenure/spend customers more likely to be targeted
            weights = (customer_df['customer_tenure'] + 1) * (customer_df['historical_spend'] + 1)
            weights = weights / weights.sum()
            
            exposed_customers = np.random.choice(
                customer_df['customer_id'],
                size=n_exposed,
                replace=False,
                p=weights
            )
            
            # Treatment assignment (70% treatment, 30% control)
            treatment_ratio = self.config['data']['treatment_ratio']
            is_treatment = np.random.random(n_exposed) < treatment_ratio
            
            # Exposure dates during campaign window
            days_range = (campaign['end_date'] - campaign['start_date']).days
            exposure_dates = [
                campaign['start_date'] + timedelta(days=np.random.randint(0, days_range))
                for _ in range(n_exposed)
            ]
            
            # Cost per contact based on channel
            cost = self.config['costs'][campaign['channel']]
            
            for i, cust_id in enumerate(exposed_customers):
                exposures.append({
                    'customer_id': cust_id,
                    'campaign_id': campaign['campaign_id'],
                    'channel': campaign['channel'],
                    'exposure_date': exposure_dates[i],
                    'cost_per_contact': cost,
                    'treatment_group': int(is_treatment[i])
                })
        
        df = pd.DataFrame(exposures)
        return df
    
    def generate_campaign_outcomes(self, customer_df, exposure_df):
        """
        Generate conversion outcomes based on customer attributes and treatment.
        
        Parameters:
        -----------
        customer_df : pd.DataFrame
            Customer table
        exposure_df : pd.DataFrame
            Exposure table
            
        Returns:
        --------
        pd.DataFrame
            Outcome table with conversions
        """
        # Merge to get customer attributes
        df = exposure_df.merge(customer_df, on='customer_id', how='left')
        
        # Base conversion probability
        base_rate = self.config['campaigns']['baseline_conversion_rate']
        
        # Calculate conversion probability based on multiple factors
        conversion_prob = np.full(len(df), base_rate)
        
        # Factor 1: Treatment effect (treatment group gets boost)
        treatment_lift = np.where(df['treatment_group'] == 1, 1.4, 1.0)
        conversion_prob *= treatment_lift
        
        # Factor 2: Customer tenure (longer tenure = higher conversion)
        tenure_effect = 1 + (df['customer_tenure'] / 120) * 0.3
        conversion_prob *= tenure_effect
        
        # Factor 3: Product count (more products = higher engagement)
        product_effect = 1 + (df['product_count'] / 5) * 0.2
        conversion_prob *= product_effect
        
        # Factor 4: Channel effectiveness
        channel_effects = {
            'Email': 1.0,
            'Push': 0.8,
            'SMS': 1.1,
            'Paid Social': 0.9,
            'Search': 1.3
        }
        channel_multiplier = df['channel'].map(channel_effects)
        conversion_prob *= channel_multiplier
        
        # Factor 5: Income band
        income_effects = {
            '<30K': 0.7, '30-50K': 0.85, '50-75K': 1.0,
            '75-100K': 1.15, '100-150K': 1.25, '>150K': 1.4
        }
        income_multiplier = df['income_band'].map(income_effects)
        conversion_prob *= income_multiplier
        
        # Add some random noise
        noise = np.random.normal(1.0, 0.1, len(df))
        conversion_prob *= noise
        
        # Clip to valid probability range
        conversion_prob = np.clip(conversion_prob, 0.001, 0.15)
        
        # Generate actual conversions
        conversions = np.random.random(len(df)) < conversion_prob
        
        # Generate conversion dates (within 14 days of exposure)
        conversion_dates = []
        for i, row in df.iterrows():
            if conversions[i]:
                days_to_convert = np.random.exponential(3)
                days_to_convert = min(int(days_to_convert), 14)
                conv_date = row['exposure_date'] + timedelta(days=days_to_convert)
                conversion_dates.append(conv_date)
            else:
                conversion_dates.append(None)
        
        # Generate revenue (only for conversions)
        revenue = np.where(
            conversions,
            np.random.gamma(shape=3, scale=50, size=len(df)),
            0
        )
        revenue = np.round(revenue, 2)
        
        outcome_df = pd.DataFrame({
            'customer_id': df['customer_id'],
            'campaign_id': df['campaign_id'],
            'treatment_group': df['treatment_group'],
            'converted': conversions.astype(int),
            'conversion_date': conversion_dates,
            'revenue_generated': revenue
        })
        
        return outcome_df
    
    def generate_all_data(self, save_path='data/simulated/'):
        """
        Generate all datasets and save to CSV files.
        
        Parameters:
        -----------
        save_path : str
            Directory path to save CSV files
            
        Returns:
        --------
        dict
            Dictionary containing all generated dataframes
        """
        print("🔄 Generating customer data...")
        customer_df = self.generate_customer_table()
        
        print("🔄 Generating campaign metadata...")
        campaign_df = self.generate_campaign_metadata()
        
        print("🔄 Generating campaign exposures...")
        exposure_df = self.generate_campaign_exposure(customer_df, campaign_df)
        
        print("🔄 Generating campaign outcomes...")
        outcome_df = self.generate_campaign_outcomes(customer_df, exposure_df)
        
        # Save to CSV
        customer_df.to_csv(f'{save_path}customers.csv', index=False)
        campaign_df.to_csv(f'{save_path}campaigns.csv', index=False)
        exposure_df.to_csv(f'{save_path}exposures.csv', index=False)
        outcome_df.to_csv(f'{save_path}outcomes.csv', index=False)
        
        print(f"\n✅ Data generation complete!")
        print(f"   - Customers: {len(customer_df):,}")
        print(f"   - Campaigns: {len(campaign_df):,}")
        print(f"   - Exposures: {len(exposure_df):,}")
        print(f"   - Conversions: {outcome_df['converted'].sum():,}")
        print(f"   - Overall Conversion Rate: {outcome_df['converted'].mean():.2%}")
        
        return {
            'customers': customer_df,
            'campaigns': campaign_df,
            'exposures': exposure_df,
            'outcomes': outcome_df
        }


if __name__ == "__main__":
    # Generate data
    generator = MarketingDataGenerator(config_path='config.yaml')
    data = generator.generate_all_data(save_path='data/simulated/')
    # Generate data
    generator = MarketingDataGenerator(config_path='config.yaml')
    data = generator.generate_all_data(save_path='data/simulated/')