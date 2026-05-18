You have been provided with four interconnected datasets representing our company's workforce health:
1. `HR Employee data.csv` (Core demographics, tenure, and compensation metrics)
2. `Employee_office_survey.csv` (Workplace sentiment and satisfaction metrics)
3. `Job_position_structure.csv` (Job level and role architecture)
4. `Office_codes.csv` (Geographic location maps and branch office sizes)

### Objective:
Conduct a comprehensive "Workforce Experience and Cost-Efficiency Optimization Study." We want to understand if employee workplace satisfaction deeply correlates with organizational demographics, costs, and branch locations.

### Your Tasks:
1. Data Integration: Safely merge the datasets using common keys (such as employee IDs, office/location codes, or job roles). Identify and clean any missing values or inconsistent types.
2. Cross-Analysis: Analyze employee satisfaction scores from the office survey against:
   - Compensation tiers (calculated from Daily Rates in the HR data).
   - Tenures (calculated from the Joining Year).
   - Geographic regions or branch sizes (mapped from the office codes).
3. Statistical Identification: Identify the top 3 job positions or branch offices displaying the lowest average office survey satisfaction. Are these low scores accompanied by below-average daily rates?
4. Visualizations: Generate presentation-ready charts to illustrate your findings:
   - A box plot showing the distribution of satisfaction scores across different job levels or regions.
   - A correlation heatmap or scatter plot comparing compensation metrics with survey scores.

Provide a structured final response including an Executive Summary, Key Findings per region/role, and 3 actionable business recommendations to improve workforce sentiment in struggling areas.