-- db_init/init.sql

CREATE USER reader WITH PASSWORD 'data-analysis-agent_reader_pass_j30hcnidm3cbirubco3JKN';

-- Grant CONNECT privilege to the reader user on the main_db database.
GRANT CONNECT ON DATABASE main_db TO reader;

-- Grant USAGE privilege on the public schema.
GRANT USAGE ON SCHEMA public TO reader;

-- Grant SELECT privileges on all existing tables in the public schema.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reader;

-- Configure automatic granting of SELECT privileges for tables created in the future as well.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reader;