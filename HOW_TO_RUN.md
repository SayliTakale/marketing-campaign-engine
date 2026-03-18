# 🚀 HOW TO RUN — Marketing Campaign Optimization Engine

> **Complete step-by-step guide to set up and run the entire project from scratch.**

---

## 📋 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.8+ | Backend analytics & ML |
| **pip** | Latest | Package management |
| **Web Browser** | Chrome/Edge/Firefox | Interactive dashboard |
| **VS Code** (optional) | Latest | Code editor |
| **Power BI Desktop** (optional) | Latest | Enterprise BI dashboard |
| **DB Browser for SQLite** (optional) | Latest | SQL query exploration |

### Check Your Python Version:
```powershell
python --version
```
Expected output: `Python 3.8.x` or higher.

---

## ⚡ Quick Run (4 Steps)

If you just want to see results immediately:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the test suite (verify everything works first)
python -m pytest src/ -v

# 3. Run the analysis pipeline
python run_complete_analysis.py

# 4. Open the interactive dashboard
start dashboard.html
```

That's it! The dashboard will open in your browser with all 7 pages of analytics.

---

## 📦 Step 1: Install Dependencies

### Option A — Using requirements.txt (Recommended)
```powershell
cd "c:\Users\omsai\OneDrive\Desktop\Projects\American Express\marketing-campaign-engine"
pip install -r requirements.txt
```

### Option B — Manual Installation
```powershell
pip install pandas numpy scipy scikit-learn matplotlib seaborn plotly statsmodels sqlalchemy pyyaml openpyxl jupyter pytest
```

### Troubleshooting Installation:
| Issue | Solution |
|-------|----------|
| `Permission denied` | Use `pip install --user -r requirements.txt` |
| `pip not found` | Use `python -m pip install -r requirements.txt` |
| `Python not found` | Install from [python.org](https://www.python.org/downloads/) and check "Add to PATH" |
| `Microsoft Visual C++ error` | Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |

---

## ✅ Step 2: Run the Test Suite

> **Always run tests before the analysis pipeline. If all 103 tests pass, the codebase is verified.**

```powershell
python -m pytest src/ -v
```

### Expected Output:
```
src/test_ab_testing.py::TestInit::test_valid_params PASSED
src/test_ab_testing.py::TestConversionMetrics::test_known_lift PASSED
...
src/test_models_utils.py::TestAllocateBudget::test_percentages_sum_to_exactly_100 PASSED
src/test_models_utils.py::TestExportDashboardData::test_output_dir_created_if_absent PASSED

103 passed in ~15s
```

### What the Tests Verify:
| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_ab_testing.py` | 33 | Z-test, t-test, incremental revenue formula, Bonferroni correction, input validation |
| `test_models_utils.py` | 70 | Encoding strategy, uplift segmentation, ROI formula, budget allocation, CSV export |

### If Tests Fail:
```powershell
# Run with detailed failure output
python -m pytest src/ -v --tb=short
```
Do not proceed to the analysis pipeline until all 103 tests pass.

---

## 📊 Step 3: Generate Data (If Needed)

> **Note:** The simulated data files are already included in `data/simulated/`. Skip this step unless you want to regenerate fresh data.

```powershell
python -c "from src.data_generator import MarketingDataGenerator; MarketingDataGenerator().generate_all_data()"
```

This generates:
- `data/simulated/customers.csv` — 100,000 customer profiles
- `data/simulated/campaigns.csv` — 12 campaign definitions
- `data/simulated/exposures.csv` — ~245,000 campaign exposures
- `data/simulated/outcomes.csv` — Conversion outcomes & revenue

**Runtime:** ~30 seconds

---

## 🔬 Step 4: Run the Complete Analysis

```powershell
python run_complete_analysis.py
```

### What Happens:

| Stage | Component | Output |
|-------|-----------|--------|
| **Section 1** | Data Loading | Loads 100K customers, 12 campaigns, 245K exposures |
| **Section 2** | Campaign ROI | Calculates ROI for all 12 campaigns |
| **Section 3** | A/B Testing | Statistical significance for each campaign |
| **Section 4** | Conversion Prediction | Logistic regression model (AUC: 0.546) |
| **Section 5** | Uplift Modeling | Customer segmentation into 4 quadrants |
| **Section 6** | Executive Summary | CMO-ready report generation |
| **Section 7** | Data Export | CSV files for Power BI + dashboard |

### Expected Console Output:
```
================================================================================
MARKETING CAMPAIGN OPTIMIZATION & PERSONALIZATION ENGINE
================================================================================

📂 SECTION 1: Loading Data
✅ Loaded 100,000 customers
✅ Loaded 12 campaigns
✅ Loaded 245,189 exposures
✅ Loaded 245,189 outcomes

💰 SECTION 2: Campaign ROI Analysis
📊 Top 5 Campaigns by ROI:
...

🧪 SECTION 3: A/B Testing Analysis
...

🤖 SECTION 4: Conversion Prediction Model
✅ Model Performance:
   ROC-AUC Score: 0.546
   Cross-validation AUC: 0.548 (±0.003)
...

🎯 SECTION 5: Uplift Modeling (KEY DIFFERENTIATOR)
...

✅ ANALYSIS COMPLETE!
================================================================================
```

**Runtime:** ~3-4 minutes

### Alternative — CSV Export Only (Faster)
If you just need the CSV files for the dashboard:
```powershell
python generate_csv_files.py
```
**Runtime:** ~30 seconds

---

## 🖥️ Step 5: Open the Interactive Dashboard

### Option A — Direct Open
```powershell
start dashboard.html
```
Or double-click `dashboard.html` in File Explorer.

### Option B — Using the Batch File
```powershell
START_DASHBOARD.bat
```

### Option C — With Live Server (VS Code)
1. Install the **Live Server** extension in VS Code
2. Right-click `dashboard.html` → "Open with Live Server"
3. Dashboard opens at `http://127.0.0.1:5500/dashboard.html`

> **⚠️ Important:** The dashboard loads CSV data from the `outputs/` folder. If you see a data loading error, ensure you've run the analysis or CSV generation script first.

### Dashboard Pages:
| Tab | Content |
|-----|---------|
| **Executive Summary** | KPI cards, ROI by channel chart, revenue pie chart |
| **Campaign Analysis** | Sortable campaign table with drill-down |
| **Channel Performance** | Channel ROI comparison, budget allocation chart |
| **Attribution Models** | Last-touch, linear, and time-decay comparison |
| **Customer Segments** | Uplift quadrant bubble chart, segment table |
| **Campaign Comparison** | Side-by-side campaign comparison tool |
| **Key Insights** | Executive findings and strategic recommendations |

---

## 🗄️ Step 6: Explore SQL Analytics (Optional)

### Using DB Browser for SQLite:
1. Download [DB Browser for SQLite](https://sqlitebrowser.org/)
2. Open `marketing_campaigns.db` (already included)
3. Run the SQL scripts in order:

```
sql/01_data_generation.sql    → Schema & data loading
sql/02_attribution_analysis.sql → Attribution models
sql/03_kpi_calculation.sql     → KPI views & metrics
```

### Key SQL Outputs:
- Multi-touch attribution results
- Campaign performance views
- Budget allocation recommendations
- Customer journey analysis

---

## 📊 Step 7: Power BI Dashboard (Optional)

### Quick Setup:
1. Open **Power BI Desktop**
2. Click **Get Data** → **Text/CSV**
3. Import all 5 CSV files from the `outputs/` folder
4. Or open `Final Dashboard.pbix` directly

### Files to Import:
```
outputs/campaign_performance.csv
outputs/channel_effectiveness.csv
outputs/customer_segments.csv
outputs/ab_test_results.csv
outputs/budget_reallocation.csv
```

See `POWER_BI_GUIDE.md` for detailed dashboard creation instructions.

---

## 📁 Output Files Reference

After running the analysis, you'll find these files:

### Data Files (for Dashboard & Power BI)
| File | Description | Rows |
|------|-------------|------|
| `outputs/campaign_performance.csv` | Campaign-level ROI & conversion metrics | 12 |
| `outputs/channel_effectiveness.csv` | Channel aggregated performance | 5 |
| `outputs/customer_segments.csv` | Uplift-based customer segments | 4 |
| `outputs/ab_test_results.csv` | A/B test significance results | 12 |
| `outputs/budget_reallocation.csv` | Recommended budget shifts | 5 |

### Reports
| File | Description |
|------|-------------|
| `outputs/reports/executive_summary.txt` | CMO-ready executive summary |

### Visualizations
| File | Description |
|------|-------------|
| `outputs/figures/roc_curve.png` | Model ROC curve (AUC: 0.546) |
| `outputs/figures/feature_importance.png` | Top conversion drivers |
| `outputs/figures/uplift_distribution.png` | Uplift score distribution & segments |

---

## 🆘 Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError` | Missing Python package | `pip install <package-name>` |
| `FileNotFoundError: data/simulated/` | Data not generated | Run `python -c "from src.data_generator import ..."` |
| `FileNotFoundError: config.yaml` | Config file missing | Ensure `config.yaml` is in the project root |
| Dashboard shows "Cannot find CSV" | CSVs not generated | Run `python generate_csv_files.py` |
| Dashboard shows blank charts | Browser CORS restriction | Use Live Server in VS Code instead of `file://` |
| `Permission denied` | Admin rights needed | `pip install --user -r requirements.txt` |
| Matplotlib plots don't show | Headless environment | Plots are saved as PNGs in `outputs/figures/` |
| Power BI can't open .pbix | Wrong Power BI version | Download latest from Microsoft |
| Tests fail | Stale `.pyc` cache | Run `rmdir /s /q src\__pycache__` then retry |
| GitHub Actions not running | `.github` folder hidden | Ensure `.github/workflows/ci.yml` is committed and pushed |
| GitHub Actions failing | Dependency version mismatch | Check `requirements.txt` matches Python version in `ci.yml` |

---

## 🤖 Step 8: Set Up CI/CD with GitHub Actions (Recommended)

> **This makes all 103 tests run automatically on every commit — no manual steps needed.**

### One-time setup:

**1. Create this folder structure in your project root:**
```
MARKETING-CAMPAIGN-ENGINE/
└── .github/
    └── workflows/
        └── ci.yml    ← place the downloaded ci.yml file here
```

**2. Commit and push:**
```powershell
git add .github/workflows/ci.yml
git commit -m "Add GitHub Actions CI pipeline"
git push
```

**3. Go to your GitHub repo → click the Actions tab** — the pipeline will already be running.

### What runs automatically on every push:

| Step | What happens |
|------|-------------|
| Trigger | Any push to main/master, or any pull request |
| Machine | Fresh Ubuntu server on GitHub's cloud |
| Python | Tests run on Python 3.9, 3.10, and 3.11 simultaneously |
| Command | `python -m pytest src/test_ab_testing.py src/test_models_utils.py --verbose` |
| Pass | Green tick on the commit — safe to use |
| Fail | Red X on the commit — GitHub emails your student with which test broke |

### What it looks like on GitHub after setup:
```
✅  "Updated uplift model"       — 103 passed in 8s (Python 3.9, 3.10, 3.11)
✅  "Fixed budget allocation"    — 103 passed in 8s (Python 3.9, 3.10, 3.11)
❌  "Changed revenue formula"    — 1 failed  in 4s — email sent
```

> **Note:** The `.github` folder name starts with a dot. On Windows, make sure it is not excluded by `.gitignore` and is visible in your file explorer (enable "Show hidden items").

---

## 🔄 Workflow Summary

```
Step 1: pip install -r requirements.txt          (one-time setup)
Step 2: python -m pytest src/ -v                 (verify 103 tests pass)
Step 3: python run_complete_analysis.py          (generates all outputs)
Step 4: start dashboard.html                     (view interactive analytics)
Step 5: Open Power BI (optional)                 (enterprise dashboards)
Step 6: Explore SQL (optional)                   (database analytics)
Step 7: git push                                 (CI runs 103 tests automatically)
```

---

## ✅ Verification Checklist

After completing all steps, verify you have:

- [ ] All Python packages installed successfully
- [ ] **103 tests passing** (`python -m pytest src/ -v`)
- [ ] `run_complete_analysis.py` completed without errors
- [ ] 5 CSV files generated in `outputs/` folder
- [ ] Executive summary generated in `outputs/reports/`
- [ ] 3 visualization PNGs in `outputs/figures/`
- [ ] Dashboard loads with all 7 tabs functional
- [ ] KPI cards display correct values
- [ ] Charts render with animations
- [ ] Filters work correctly
- [ ] Export functionality works (PDF, CSV, Email)
- [ ] CI/CD pipeline active — green tick visible on GitHub Actions tab

---