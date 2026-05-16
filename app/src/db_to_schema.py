
import pandas as pd
from sqlalchemy import create_engine, inspect, text

def main(engine):
    
    # Get table names
    with engine.connect() as connection:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    
    # Retrieve the schema for each table
    schema_markdown = {}
    for table_name in tables:
        try:
            schema = save_schema_to_file(table_name, engine)
            if schema:
                schema_markdown[table_name] = schema
        except Exception as e:
            print(f"Error processing table '{table_name}': {e}")

    # Merge all schemas and return
    if schema_markdown:
        # full_schema = "\n\n".join(schema_markdown)
        # return full_schema
        return schema_markdown
    else:
        return {"error": "No tables found or failed to retrieve schemas."}


def save_schema_to_file(table_name,engine):
    """
    Return the table schema information as a Markdown-formatted string.
    Uses random sampling to obtain more diverse examples.
    """
    try:

        with engine.connect() as connection:
            inspector = inspect(engine)
            columns = inspector.get_columns(table_name)
            
            # Get the total row count of the table
            row_count_result = connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            total_rows = row_count_result.scalar()
            
            # Retrieve data using random sampling
            if total_rows > 100:
                # For large tables, use random sampling
                sample_df = pd.read_sql(text(f'SELECT * FROM "{table_name}" ORDER BY RANDOM() LIMIT 100'), connection)
            else:
                # For small tables, retrieve all data
                sample_df = pd.read_sql(text(f'SELECT * FROM "{table_name}"'), connection)

            markdown_lines = []
            markdown_lines.append(f"## Table: {table_name}\n")
            markdown_lines.append("| Column Name | Type | Example Value 1 | Example Value 2 | Example Value 3 |")
            markdown_lines.append("|---|---|---|---|---|")

            for col_info in columns:
                col_name = col_info['name']
                col_type = str(col_info['type'])
                
                # Get unique values for the column (excluding NaN/Null)
                unique_values = sample_df[col_name].dropna().drop_duplicates()
                
                # Select samples taking value distribution into account
                if len(unique_values) == 0:
                    sample1 = sample2 = sample3 = ''
                elif len(unique_values) == 1:
                    sample1 = str(unique_values.iloc[0])
                    sample2 = sample3 = ''
                elif len(unique_values) == 2:
                    sample1 = str(unique_values.iloc[0])
                    sample2 = str(unique_values.iloc[1])
                    sample3 = ''
                else:
                    # Randomly select 3 values (without duplicates)
                    sampled_values = unique_values.sample(min(3, len(unique_values)), random_state=42)
                    sample1 = str(sampled_values.iloc[0])
                    sample2 = str(sampled_values.iloc[1]) if len(sampled_values) > 1 else ''
                    sample3 = str(sampled_values.iloc[2]) if len(sampled_values) > 2 else ''
                
                markdown_lines.append(f"| {col_name} | {col_type} | {sample1} | {sample2} | {sample3} |")
            return "\n".join(markdown_lines)
            
    except Exception as e:
        print(f"Failed to save schema for table '{table_name}': {e}")