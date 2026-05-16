import os
import tempfile
import pandas as pd
import sqlite3
import psycopg2
import re
from pathlib import Path
from typing import List
from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.sql import quoted_name
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .database import engine
from .utils.prompts import set_db_schema
import unicodedata

# PostgreSQL reserved words
POSTGRESQL_RESERVED_WORDS = {
    "all",
    "and",
    "any",
    "array",
    "as",
    "asc",
    "asymmetric",
    "both",
    "case",
    "cast",
    "check",
    "collate",
    "column",
    "constraint",
    "create",
    "current_catalog",
    "current_date",
    "current_role",
    "current_time",
    "current_timestamp",
    "current_user",
    "default",
    "deferrable",
    "desc",
    "distinct",
    "do",
    "else",
    "end",
    "except",
    "false",
    "fetch",
    "for",
    "foreign",
    "from",
    "grant",
    "group",
    "having",
    "in",
    "initially",
    "intersect",
    "into",
    "leading",
    "limit",
    "localtime",
    "localtimestamp",
    "not",
    "null",
    "offset",
    "on",
    "only",
    "or",
    "order",
    "placing",
    "primary",
    "references",
    "returning",
    "select",
    "session_user",
    "some",
    "symmetric",
    "table",
    "then",
    "to",
    "trailing",
    "true",
    "union",
    "unique",
    "user",
    "using",
    "variadic",
    "when",
    "where",
    "window",
    "with",
}


class DataService:
    def __init__(self):
        self.engine = engine

    def _normalize_name(self, name: str) -> str:
        """Normalize table / column names (lowercase, replace special chars)
        Note: This function is kept for backward compatibility.
        Use _normalize_name as the secure current implementation.
        """

        if not name or not isinstance(name, str):
            raise ValueError("Table names must be non-empty strings.")
        
        name = unicodedata.normalize("NFKC", str(name))
        # Replace special characters with underscores
        normalized = re.sub(r"[^\w\s]", "_", name)
        # Replace spaces with underscores
        normalized = re.sub(r"\s+", "_", normalized)
        # Replace consecutive underscores with a single one
        normalized = re.sub(r"_+", "_", str(normalized))
        # Remove leading and trailing underscores
        normalized = normalized.strip("_")

        # 4. Convert to lowercase
        normalized = normalized.lower()

        # 5. Length limit (PostgreSQL identifier limit)
        if len(normalized) > 63:
            normalized = normalized[:63].rstrip("_")

        # 6. Minimum length check
        if len(normalized) < 1:
            raise ValueError("Normalized table name became empty")
        
        # 8. PostgreSQL reserved word check
        if normalized.lower() in POSTGRESQL_RESERVED_WORDS:
            normalized = normalized + "_table"
            if len(normalized) > 63:
                normalized = normalized[:59] + "_tbl"

        return normalized
    
    def _create_safe_table_identifier(self, table_name: str):
        """
        Creates a safe table identifier using quoted_name.
        """
        validated_name = self._normalize_name(table_name)
        return quoted_name(validated_name, quote=True)

    def _execute_safe_ddl(self, connection, sql_template: str, *table_identifiers):
        """
        Executes DDL safely using quoted_name.
        """
        # Convert quoted_name objects to strings to build the SQL
        formatted_sql = sql_template.format(
            *[str(identifier) for identifier in table_identifiers]
        )
        query = text(formatted_sql)
        connection.execute(query)

    def _read_csv_with_fallback_encoding(self, file_path: str) -> pd.DataFrame:
        """Try multiple encodings to load a CSV file"""
        # List of encodings to try (most common first)
        encodings = [
            "utf-8",
            "shift_jis",
            "cp932",
            "euc-jp",
            "iso-2022-jp",
            "latin1",
            "utf-16",
        ]

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                print(f"CSV file successfully read with encoding: {encoding}")
                return df
            except (UnicodeDecodeError, UnicodeError):
                print(f"Failed to read with {encoding}. Trying next encoding...")
                continue
            except Exception as e:
                # If the error is not an encoding error, re-raise the exception
                raise e

        # If all encodings fail
        raise ValueError(
            f"Unable to read CSV file '{file_path}' with supported encodings. Tried: {', '.join(encodings)}"
        )

    def get_db_engine(self):
        if self.engine is None:
            raise HTTPException(
                status_code=503,
                detail="Database service is unavailable. Please verify database connection settings.",
            )
        return self.engine

    def process_file_to_postgres(
        self, file_path: str, original_filename: str, db_engine
    ) -> List[str]:
        """Converts files to PostgreSQL database."""
        table_names = []

        try:
            # Determine the loading method based on the file extension
            if file_path.endswith(".csv"):
                df = self._read_csv_with_fallback_encoding(file_path)
                # Normalize column names (lowercase, special character processing)
                df.columns = [self._normalize_name(col) for col in df.columns]
                table_name = self._normalize_name(Path(original_filename).stem)
                table_names.append(table_name)

                # Save to PostgreSQL
                df.to_sql(table_name, db_engine, if_exists="replace", index=False)

            elif file_path.endswith((".xlsx", ".xls")):
                # If it is an Excel file, process multiple sheets
                excel_file = pd.ExcelFile(file_path)

                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    # Normalize column names (lowercase, special character processing)
                    df.columns = [self._normalize_name(col) for col in df.columns]
                    # Use the sheet name as the table name
                    table_name = self._normalize_name(sheet_name)
                    table_names.append(table_name)
                    df.to_sql(table_name, db_engine, if_exists="replace", index=False)

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File processing error: {str(e)}")

        return table_names

    def copy_sqlite_to_postgres(self, source_path: str, db_engine) -> List[str]:
        """Copies data from SQLite file to PostgreSQL database."""
        table_names = []

        try:
            # Connect to the source SQLite database
            source_conn = sqlite3.connect(source_path)
            source_cursor = source_conn.cursor()

            # Get list of tables
            source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in source_cursor.fetchall()]

            for table_name in tables:
                try:
                    #   Read data from source
                    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', source_conn)

                    # Normalize column names (lowercase, special character processing)
                    df.columns = [self._normalize_name(col) for col in df.columns]

                    # Save to PostgreSQL
                    pg_table_name = self._normalize_name(table_name)
                    df.to_sql(
                        pg_table_name, db_engine, if_exists="replace", index=False
                    )
                    table_names.append(pg_table_name)

                except Exception as e:
                    print(f"Error processing table {table_name}: {str(e)}")
                    # Individual table errors are continued
                    continue

            source_cursor.close()
            source_conn.close()

        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"SQLite file processing error: {str(e)}"
            )

        return table_names

    def copy_external_postgres_to_main_postgres(
        self, external_connection_string: str, main_db_engine
    ) -> List[str]:
        """Copies data from external PostgreSQL to main PostgreSQL database."""
        table_names = []

        try:
            # Connect to external PostgreSQL
            external_pg_conn = psycopg2.connect(external_connection_string)
            external_pg_cursor = external_pg_conn.cursor()

            # Get list of tables
            external_pg_cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """
            )

            tables = [row[0] for row in external_pg_cursor.fetchall()]

            for table_name in tables:
                try:
                    # Read data from external PostgreSQL
                    df = pd.read_sql_query(
                        f'SELECT * FROM "{table_name}"', external_pg_conn
                    )

                    # Normalize column names (lowercase, special character processing)
                    df.columns = [self._normalize_name(col) for col in df.columns]

                    # Save to main PostgreSQL
                    main_pg_table_name = self._normalize_name(table_name)
                    df.to_sql(
                        main_pg_table_name,
                        main_db_engine,
                        if_exists="replace",
                        index=False,
                    )
                    table_names.append(main_pg_table_name)

                except Exception as e:
                    print(f"Error processing table {table_name}: {str(e)}")
                    # Individual table errors are continued
                    continue

            external_pg_cursor.close()
            external_pg_conn.close()

        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"External PostgreSQL connection error: {str(e)}"
            )

        return table_names

    def get_table_list(self):
        """Retrieve list of tables in the PostgreSQL database"""
        db_engine = self.get_db_engine()
        try:
            with db_engine.connect() as connection:
                inspector = inspect(db_engine)
                # Get tables from the 'public' schema (change if needed)
                table_names = inspector.get_table_names(schema="public")

                return {
                    "table_count": len(table_names),
                    "table_names": table_names,
                    "message": "Successfully retrieved table list from PostgreSQL database",
                }
        except OperationalError as e:
            raise HTTPException(
                status_code=503, detail=f"Database connection error: {str(e)}"
            )
        except Exception as e:
            print(f"Error getting table list: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving table list: {str(e)}"
            )

    async def upload_csv_xlsx(self, files):
        """Upload CSV/XLSX files and store them in PostgreSQL"""
        db_engine = self.get_db_engine()
        try:
            all_table_names = []

            for file in files:
                # Save the file temporarily
                temp_file_path = os.path.join(tempfile.gettempdir(), file.filename)

                with open(temp_file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)

                # Convert the file to PostgreSQL
                table_names = self.process_file_to_postgres(
                    temp_file_path, file.filename, db_engine
                )
                all_table_names.extend(table_names)

                # Remove temporary files
                os.remove(temp_file_path)

            if not all_table_names:
                raise HTTPException(
                    status_code=400,
                    detail="No readable data found. The file may be empty or an unsupported format.",
                )
            else:
                set_db_schema()  # Update database schema

            return {
                "table_count": len(all_table_names),
                "table_names": all_table_names,
                "message": "Files uploaded and data stored in PostgreSQL successfully",
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

    def connect_external_postgres(self, connection_string: str):
        """Connect to an external PostgreSQL instance and copy all public schema tables into the main PostgreSQL"""
        main_db_engine = self.get_db_engine()
        try:
            # Copy data from external PostgreSQL to main PostgreSQL
            table_names = self.copy_external_postgres_to_main_postgres(
                connection_string, main_db_engine
            )

            if not table_names:
                raise HTTPException(
                    status_code=400,
                    detail="No readable tables found. The external PostgreSQL database may have no tables or the connection string is invalid.",
                )

            return {
                "table_count": len(table_names),
                "table_names": table_names,
                "message": f"Connected to external PostgreSQL and copied {len(table_names)} table(s) into the main PostgreSQL",
            }

        except psycopg2.Error as e:
            raise HTTPException(
                status_code=400, detail=f"External PostgreSQL connection error: {str(e)}"
            )
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    async def upload_sqlite_db(self, file):
        """Upload a SQLite file and copy its data into PostgreSQL"""
        db_engine = self.get_db_engine()
        try:
            # Save the uploaded file temporarily
            uploaded_file_path = os.path.join(
                tempfile.gettempdir(), f"uploaded_{file.filename}"
            )

            with open(uploaded_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Copy data from uploaded SQLite to PostgreSQL
            table_names = self.copy_sqlite_to_postgres(uploaded_file_path, db_engine)

            if not table_names:
                raise HTTPException(
                    status_code=400,
                    detail="No readable tables found. The SQLite file may be empty or contain no tables.",
                )

            # Remove uploaded file
            os.remove(uploaded_file_path)
            set_db_schema()  # Update database schema

            return {
                "table_count": len(table_names),
                "table_names": table_names,
                "message": f"SQLite file uploaded and {len(table_names)} table(s) copied into PostgreSQL",
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def reset_db(self):
        """Reset the database (drop all tables) - secure version"""
        db_engine = self.get_db_engine()
        try:
            with db_engine.connect() as connection:
                inspector = inspect(db_engine)
                table_names = inspector.get_table_names(schema="public")

                if not table_names:
                    return {"message": "Database is already empty."}

                #   Secure table deletion process
                for table_name in table_names:
                    # Validate table name and create safe identifier
                    validated_name = self._normalize_name(table_name)
                    safe_identifier = self._create_safe_table_identifier(validated_name)

                    # SQL injection prevention: secure implementation using quoted_name
                    sql_template = "DROP TABLE IF EXISTS public.{} CASCADE"
                    self._execute_safe_ddl(connection, sql_template, safe_identifier)

                # Explicitly commit the transaction
                connection.commit()

            set_db_schema()  # Update database schema
            return {"message": "Database reset successfully."}

        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Table name validation error: {str(e)}"
            )
        except OperationalError as e:
            raise HTTPException(
                status_code=503, detail=f"Database connection error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Database reset error: {str(e)}"
            )

    def delete_table(self, table_name: str):
        """Delete a specified table (secure version)"""
        try:
            engine = self.get_db_engine()

            #   Strict validation and normalization of table names
            validated_name = self._normalize_name(table_name)

            #   Check if table exists
            inspector = inspect(engine)
            table_names = inspector.get_table_names(schema="public")

            if validated_name not in table_names:
                raise HTTPException(
                    status_code=404,
                    detail=f"Table '{table_name}' not found.",
                )

            # 3. Create a safe table identifier
            safe_identifier = self._create_safe_table_identifier(validated_name)

            # 4. Execute safe table deletion
            with engine.connect() as connection:
                # SQL injection prevention: secure implementation using quoted_name
                sql_template = "DROP TABLE IF EXISTS public.{} CASCADE"
                self._execute_safe_ddl(connection, sql_template, safe_identifier)
                connection.commit()

            # Update database schema
            set_db_schema()

            return {"message": f"Table '{table_name}' deleted successfully."}

        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Table name validation error: {str(e)}"
            )
        except OperationalError as e:
            raise HTTPException(
                status_code=503, detail=f"Database connection error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Table deletion error: {str(e)}")

    def change_table_name(self, table_name: str, new_table_name: str):
        """Rename a specified table (secure version)"""
        try:
            engine = self.get_db_engine()
            inspector = inspect(engine)

            # 1. Strict validation and normalization of table names
            validated_old_name = self._normalize_name(table_name)
            validated_new_name = self._normalize_name(new_table_name)

            # 2. Create a safe table identifier
            safe_old_identifier = self._create_safe_table_identifier(validated_old_name)
            safe_new_identifier = self._create_safe_table_identifier(validated_new_name)

            # 3. Get only tables in schema 'public'
            table_names = inspector.get_table_names(schema="public")

            # 4. Check if the table exists
            if validated_old_name not in table_names:
                raise HTTPException(
                    status_code=404,
                    detail=f"Table '{table_name}' not found.",
                )

            # 5. Check if the new table name is already in use
            if validated_new_name in table_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"Table name '{new_table_name}' is already in use.",
                )

            # 6. Execute safe table rename
            with engine.connect() as connection:
                # SQL injection prevention: secure implementation using quoted_name
                sql_template = "ALTER TABLE public.{} RENAME TO {}"
                self._execute_safe_ddl(
                    connection, sql_template, safe_old_identifier, safe_new_identifier
                )
                connection.commit()

            # Update database schema
            set_db_schema()

            return {"message": f"Table '{table_name}' has been renamed to '{new_table_name}'."}

        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Table name validation error: {str(e)}"
            )
        except OperationalError as e:
            raise HTTPException(
                status_code=503, detail=f"Database connection error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Table rename error: {str(e)}"
            )
