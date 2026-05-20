# CSV sample — HR workforce analytics

## Data

Upload all four files from `sample_dataset/csv/`:

| View | File |
|------|------|
| `hr_employee_data` | `HR Employee data.csv` |
| `employee_office_survey` | `Employee_office_survey.csv` |
| `job_position_structure` | `Job_position_structure.csv` |
| `office_codes` | `Office_codes.csv` |

## Preset prompt

You have been provided with four interconnected datasets representing our company's workforce health:

1. `hr_employee_data` — core demographics, tenure, and compensation metrics
2. `employee_office_survey` — workplace sentiment and satisfaction metrics
3. `job_position_structure` — job level and role architecture
4. `office_codes` — geographic locations and branch offices

Conduct a comprehensive "Workforce Experience and Cost-Efficiency Optimization Study." We want to understand if employee workplace satisfaction deeply correlates with organizational demographics, costs, and branch locations.

Your tasks:

1. **Data integration:** Safely merge the datasets using common keys (employee IDs, office codes, or job roles). Identify and clean missing values or inconsistent types.
2. **Cross-analysis:** Analyze office survey satisfaction against compensation tiers (daily rates), tenure (joining year), and geographic region or branch (office codes).
3. **Statistical identification:** Find the top 3 job positions or branch offices with the lowest average office survey satisfaction. Are those low scores accompanied by below-average daily rates?
4. **Visualizations:** Include a box plot of satisfaction by job level or region, and a correlation heatmap or scatter plot of compensation vs. survey scores.

Provide an Executive Summary, key findings per region/role, and 3 actionable recommendations to improve workforce sentiment in struggling areas.

## Test prompts

1. Scatter plot of age vs. total working years.
2. Chi-square test: business travel frequency for single vs. married employees.
3. Box plot: attrition vs. monthly income.
4. Top 3 offices with lowest average survey rating.

## Expected results

- Successful multi-table joins on employee and office keys.
- Valid statistical tests and charts.
- Actionable HR recommendations backed by the data.
