-- Load CSVs from the mounted /sample_data volume (see docker-compose.yml).

\echo 'Loading hr_employee_data...'
\copy hr_employee_data (employee_id, joining_year, age, business_travel, daily_rate, department, distance_from_home, education_field, employee_count, employee_number, environment_satisfaction, gender, hourly_rate, job_involvement, job_satisfaction, marital_status, monthly_income, monthly_rate, num_companies_worked, over18, over_time, percent_salary_hike, performance_rating, relationship_satisfaction, standard_hours, stock_option_level, total_working_years, training_times_last_year, work_life_balance, years_at_company, years_in_current_role, years_since_last_promotion, years_with_curr_manager, attrition, leaving_year, reason, relieving_status, office_code, job_level_updated) FROM '/sample_data/HR Employee data.csv' WITH (FORMAT csv, HEADER true, NULL '');

\echo 'Loading employee_office_survey...'
\copy employee_office_survey (emp_id, off_cde, rated_year, rating) FROM '/sample_data/Employee_office_survey.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading job_position_structure...'
\copy job_position_structure (department, job_level, job_role) FROM '/sample_data/Job_position_structure.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading office_codes...'
\copy office_codes (office_code, city, province, country) FROM '/sample_data/Office_codes.csv' WITH (FORMAT csv, HEADER true);

\echo 'Row counts:'
SELECT 'hr_employee_data' AS table_name, COUNT(*)::bigint AS row_count FROM hr_employee_data
UNION ALL
SELECT 'employee_office_survey', COUNT(*)::bigint FROM employee_office_survey
UNION ALL
SELECT 'job_position_structure', COUNT(*)::bigint FROM job_position_structure
UNION ALL
SELECT 'office_codes', COUNT(*)::bigint FROM office_codes;
