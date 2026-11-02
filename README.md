# Call Center Performance Analysis

An end-to-end look at call center performance data: profiling and cleaning it with SQL in Google BigQuery, validating the results, and visualizing it in Power BI.

## Tools

- **SQL** (Google BigQuery) for profiling, cleaning, and validation
- **Git / GitHub** for version control
- **Power BI** for dashboards and visual analysis 

## Dataset

**Source:** [Call Center Data on Kaggle](https://www.kaggle.com/datasets/satvicoder/call-center-data)

`Call Center Data.csv`: 1,251 rows, one per day. Each row includes:

- Incoming, answered, and abandoned call counts
- Answer rate
- Average answer speed, talk duration, and waiting time
- Service level (calls answered within 20 seconds)

## Pipeline

| Step | File | What it does |
|---|---|---|
| 1. Explore | [`sql/01_explore.sql`](sql/01_explore.sql) | Profiles the raw data: column types, duplicates, missing values, value ranges, and logic checks |
| 2. Clean | [`sql/02_clean.sql`](sql/02_clean.sql) | Builds a `clean_data` table: renames columns to snake_case, converts time fields to seconds, filters out invalid rows |
| 3. Validate | [`sql/03_validate.sql`](sql/03_validate.sql) | Proves the cleaned table is right: raw vs clean row counts and call totals, answered + abandoned = incoming, answer rate matches answered ÷ incoming, no nulls or duplicate IDs, time conversion spot check, value ranges |

## Data Quality Findings

I checked the data before trusting it, rather than assuming it was clean:

| Check | Result |
|---|---|
| Total rows | 1,251 |
| Duplicate IDs | 0 |
| Missing values (all 9 columns) | 0 |
| Rows with more calls answered than received | 0 |
| Rows where answered + abandoned ≠ incoming | 0 |
| Rows where answer rate ≠ answered ÷ incoming | 0 (checked against the source CSV) |
| Rows after cleaning | 1,251 (no rows lost) |

**Cleaning decisions:**

- **Time fields** (answer speed, talk duration, waiting time) were stored as `TIME` values. I converted them to whole seconds so they can be averaged and charted.
- **Answer rate** loaded as a decimal (0.553 = 55.3%), so it gets formatted as a percentage in reporting.
- **Validation filters** for missing IDs and impossible call counts are kept in the cleaning script as a safety net, even though this dataset passed every check.

## Dashboard

![Call Center Performance Dashboard](Power%20BI/dashboard.png)

Built in Power BI from the cleaned BigQuery table. Daily rows were grouped into 30-day periods ("months") to show trends clearly. Rates and averages are weighted by call volume, so busy days count more than quiet ones. The Power BI file and a PDF export are in the [Power BI folder](Power%20BI/).

### What the dashboard shows

- **Overall performance:** 248K incoming calls, an 89.1% answer rate, and a 10.9% abandon rate. Only 63.8% of calls were answered within 20 seconds, well below the common 80/20 service level target.
- **A demand spike broke service:** Around months 27–30, monthly volume jumped from a typical 4K–6K calls to as high as ~15.6K, and service level fell to about 30%.
- **Volume drives the big drops, but not all of them:** Service level falls sharply once monthly volume passes ~8K. At normal volume it still ranges from ~53% to ~88%, which points to other factors like staffing or handle time.

## Key Insights

- **Call volume varies widely.** Incoming calls per day range from 5 to 1,575, against an average of 198.5.
- **There is a distinct demand spike.** The busiest rows cluster around days 839–884, peaking at 1,575 calls, roughly 8 times the average. The totals reconcile in every row, so this is a real surge, not a data error, and it was kept in the analysis.
- **Service suffered during the spike.** Answer rates in the busiest rows dropped to about 55–60%, meaning roughly 4 in 10 callers hung up before reaching an agent.
- **Waiting time is the pressure point.** Talk duration stayed fairly steady (about 1 to 5 minutes), but average waiting time reached as high as 25 minutes 51 seconds, which points to a capacity problem rather than a call-handling problem.

## Next Steps

- Build a Tableau KPI dashboard
- Explore staffing recommendations for demand spikes
