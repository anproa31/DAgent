# PostgreSQL sample — HR workforce (`db_test`)

## Data

Start the demo database (see `README.md` in this folder), then connect via **Connect database → PostgreSQL**:

| Setting | Value |
|---------|--------|
| Connection string | `postgresql://demo:demo@localhost:5433/hr_analytics` |
| Tables | `hr_employee_data`, `employee_office_survey`, `job_position_structure`, `office_codes` |

Same HR schema as `sample_dataset/csv/` — use this preset to test live database attach instead of file upload.

## Preset prompt

You have access to the HR analytics PostgreSQL database with tables `hr_employee_data`, `employee_office_survey`, `job_position_structure`, and `office_codes`.

Conduct a comprehensive "Workforce Experience and Cost-Efficiency Optimization Study." We want to understand if employee workplace satisfaction deeply correlates with organizational demographics, costs, and branch locations.

Your tasks:

1. **Data integration:** Join employees, survey ratings, job structure, and office codes on employee IDs and office codes. Handle nulls and type inconsistencies.
2. **Cross-analysis:** Relate office survey ratings to daily rates, tenure (joining year), and country or city from office codes.
3. **Statistical identification:** Find the top 3 departments or offices with the lowest average survey rating. Are they associated with below-average daily rates?
4. **Visualizations:** Box plot of ratings by department or country; correlation or scatter plot of compensation vs. satisfaction.

Provide an Executive Summary, key findings per region/role, and 3 actionable recommendations.

## Test prompts

1. Show 5 employees from the Sales department.
2. Average office rating by city.
3. Join employees with `office_codes` and list headcount by country.
4. How many employees left voluntarily in 2019?

## Expected results

- SQL runs against attached Postgres views (not file copies).
- Correct joins and aggregations on HR tables.
- Clear narrative suitable for a demo of database-connected analysis.
