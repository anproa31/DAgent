-- HR analytics demo schema (matches sample_dataset/csv for side-by-side comparison
-- with file-upload datasources in the main app).

CREATE TABLE hr_employee_data (
    employee_id              BIGINT PRIMARY KEY,
    joining_year             INTEGER,
    age                      INTEGER,
    business_travel          TEXT,
    daily_rate               INTEGER,
    department               TEXT,
    distance_from_home       INTEGER,
    education_field          TEXT,
    employee_count           INTEGER,
    employee_number          INTEGER,
    environment_satisfaction INTEGER,
    gender                   TEXT,
    hourly_rate              INTEGER,
    job_involvement          INTEGER,
    job_satisfaction         INTEGER,
    marital_status           TEXT,
    monthly_income           INTEGER,
    monthly_rate             INTEGER,
    num_companies_worked     INTEGER,
    over18                   TEXT,
    over_time                TEXT,
    percent_salary_hike      INTEGER,
    performance_rating       INTEGER,
    relationship_satisfaction INTEGER,
    standard_hours           INTEGER,
    stock_option_level       INTEGER,
    total_working_years      INTEGER,
    training_times_last_year INTEGER,
    work_life_balance        INTEGER,
    years_at_company         INTEGER,
    years_in_current_role    INTEGER,
    years_since_last_promotion INTEGER,
    years_with_curr_manager  INTEGER,
    attrition                TEXT,
    leaving_year             INTEGER,
    reason                   TEXT,
    relieving_status         TEXT,
    office_code              TEXT,
    job_level_updated        TEXT
);

CREATE TABLE employee_office_survey (
    emp_id      BIGINT NOT NULL,
    off_cde     TEXT NOT NULL,
    rated_year  INTEGER NOT NULL,
    rating      NUMERIC(4, 1) NOT NULL,
    PRIMARY KEY (emp_id, off_cde, rated_year)
);

CREATE TABLE job_position_structure (
    department TEXT NOT NULL,
    job_level  TEXT NOT NULL,
    job_role   TEXT NOT NULL,
    PRIMARY KEY (department, job_level, job_role)
);

CREATE TABLE office_codes (
    office_code TEXT PRIMARY KEY,
    city        TEXT NOT NULL,
    province    TEXT NOT NULL,
    country     TEXT NOT NULL
);

CREATE INDEX idx_hr_employee_department ON hr_employee_data (department);
CREATE INDEX idx_hr_employee_office_code ON hr_employee_data (office_code);
CREATE INDEX idx_survey_emp_id ON employee_office_survey (emp_id);
CREATE INDEX idx_survey_off_cde ON employee_office_survey (off_cde);

COMMENT ON DATABASE hr_analytics IS 'Demo database for data-analyst-agent DB connection walkthrough';
