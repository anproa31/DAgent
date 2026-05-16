from fastapi import APIRouter, File, UploadFile, Form, Depends, Query, HTTPException
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.types import String, Text
from typing import List, Optional
from ..models.responses import ConnectionResponse
from ..data_service import DataService
from ..database import engine, get_db

router = APIRouter()
data_service = DataService()

@router.get("/api/get-table-list", response_model=ConnectionResponse)
async def get_table_list():
    """Retrieve list of tables from PostgreSQL database"""
    return data_service.get_table_list()

@router.post("/api/upload-csv-xlsx", response_model=ConnectionResponse)
async def upload_csv_xlsx(files: List[UploadFile] = File(...)):
    """Upload CSV/XLSX files and save to PostgreSQL"""
    return await data_service.upload_csv_xlsx(files)

@router.post("/api/connect-external-postgres", response_model=ConnectionResponse)
async def connect_external_postgres(connection_string: str = Form(...)):
    """Connect to external PostgreSQL database and copy all data to main PostgreSQL"""
    return data_service.connect_external_postgres(connection_string)

@router.post("/api/upload-sqlite-db", response_model=ConnectionResponse)
async def upload_sqlite_db(file: UploadFile = File(...)):
    """Upload SQLite file and copy data to PostgreSQL"""
    return await data_service.upload_sqlite_db(file)

@router.delete("/api/delete-table/{table_name}")
async def delete_table(table_name: str):
    """Delete the specified table"""
    return data_service.delete_table(table_name)

@router.put("/api/rename-table/{table_name}", response_model=ConnectionResponse)
async def rename_table(table_name: str, new_table_name: str = Form(...)):
    """Rename the specified table"""
    result = data_service.change_table_name(table_name, new_table_name)
    return {
        "message": result["message"],
        "table_count": 1,
        "table_names": [new_table_name]
    }

@router.get("/api/table-data/{table_name}")
async def get_table_data(
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    sort_column: Optional[str] = None,
    sort_direction: Optional[str] = None,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Retrieve PostgreSQL table data safely and efficiently (for preview)"""
    try:
        inspector = inspect(engine)
        
        # Check table existence and retrieve column info in one call
        try:
            columns_info = inspector.get_columns(table_name, schema='public')
            if not columns_info:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}'  not found.")
        except Exception:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}'  not found.")

        # Build column name list (cached)
        valid_columns = {col['name']: col['type'] for col in columns_info}

        # --- Validate parameters ---
        if sort_column:
            if sort_column not in valid_columns:
                raise HTTPException(status_code=400, detail=f"Invalid sort column: {sort_column}")
            if not sort_direction or sort_direction.lower() not in ['asc', 'desc']:
                raise HTTPException(status_code=400, detail=f"Invalid sort direction: {sort_direction}")

        if filter_column and filter_column not in valid_columns:
            raise HTTPException(status_code=400, detail=f"Invalid filter column: {filter_column}")

        # --- Build efficient query ---
        params = {"limit_val": limit, "offset_val": offset}
        where_clause = []


        # Build filter conditions
        if filter_column and filter_value is not None:
            column_type = valid_columns[filter_column]
            param_name = f"filter_val_{filter_column}"
            
            # Build filter condition based on type
            if isinstance(column_type, (String, Text)):
                where_clause.append(f'"{filter_column}" ILIKE :{param_name}')
                params[param_name] = f"%{filter_value}%"
            else:
                where_clause.append(f'"{filter_column}" = :{param_name}')
                params[param_name] = filter_value

        # Build WHERE clause
        where_str = " WHERE " + " AND ".join(where_clause) if where_clause else ""

        # Build ORDER BY clause
        order_str = f' ORDER BY "{sort_column}" {sort_direction.upper()}' if sort_column and sort_direction else ""

        # --- Execute efficient queries ---
        # 1. Get total row count (after filter applied)
        count_query = text(f'SELECT COUNT(*) FROM public."{table_name}"{where_str}')
        total_rows = db.execute(count_query, params).scalar_one()

        # 2. Retrieve data with pagination applied
        data_query = text(
            f'SELECT * FROM public."{table_name}"{where_str}{order_str} '
            'LIMIT :limit_val OFFSET :offset_val'
        )
        result = db.execute(data_query, params)
        
        columns = result.keys()
        data = [dict(row) for row in result.mappings()]

        return {
            "table_name": table_name,
            "columns": list(columns),
            "data": data,
            "total_rows": total_rows,
            "preview_rows": len(data),
            "sort_column": sort_column,
            "sort_direction": sort_direction,
            "filter_column": filter_column,
            "filter_value": filter_value
        }
        
    except ProgrammingError as e:
        # Type mismatches (e.g., passing 'abc' to an INT column) are also caught here.
        raise HTTPException(status_code=400, detail=f"Query execution error: {e.orig}")
    except OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database connection error: {e.orig}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unknown server error: {str(e)}")
