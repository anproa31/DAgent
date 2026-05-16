import os
import io
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import json 
import re
import matplotlib.pyplot as plt
import japanize_matplotlib
import base64
import time

app = FastAPI()

# --- Retrieve DB connection info from environment variables ---

DB_READER_USER = os.getenv("DB_READER_USER")
DB_READER_PASSWORD = os.getenv("DB_READER_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
DEFAULT_DB_URL = f"postgresql://{DB_READER_USER}:{DB_READER_PASSWORD}@data-analysis-agent-db:5432/{POSTGRES_DB}"

# If USER_DATABASE_URL is set, use it preferentially
DATABASE_URL = os.getenv("USER_DATABASE_URL", DEFAULT_DB_URL)

try:
    engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        print("Database connection successful for code_runner.")
except Exception as e:
    print(f"Error connecting to database: {e}")
    engine = None

### Container state management ###
QUE = 0
STRAGE = {}
STRAGE_ROLLBACK = {}

IS_RUNNING = {}


### Endpoints ###
# Returns the number of items in the container queue
@app.get("/status")
def get_status():
    return {"que": QUE}

# Execute code
class CodeExecutionRequest(BaseModel):
    id :str
    code: str
@app.post("/code")
def execute_code(request: CodeExecutionRequest):
    if engine is None:
        raise HTTPException(status_code=503, detail="Database connection not available")
    global QUE
    global STRAGE
    global STRAGE_ROLLBACK
    global IS_RUNNING
    QUE += 1
    if request.id in STRAGE and STRAGE[request.id] is not None:
        localvars = STRAGE[request.id]
    else:
        localvars = {"engine": engine }

    # Save variables for rollback
    STRAGE_ROLLBACK[request.id] = localvars.copy()

    # Pre-process the code
    code = request.code
    # Restore backslashes
    code = code.replace("%@", "\\")
    # Remove lines starting with engine =
    code = re.sub(r'^engine\s*=.*\n?', '', code, flags=re.MULTILINE)

    IS_RUNNING[request.id] = True

    # Execute the code
    try:
        exec(code, localvars)
    except Exception as e:
        QUE -= 1
        IS_RUNNING[request.id] = False
        return {"error": str(e), "trace": traceback.format_exc(), "id": request.id}

    # Save variables
    STRAGE[request.id] = localvars
    QUE -= 1
    IS_RUNNING[request.id] = False
    return {"ok": "code executed successfully"}

# Rollback variables (e.g. when an error occurs during action model execution)
class VariableRollbackRequest(BaseModel):
    id: str
@app.post("/rollback")
def rollback_variable(request: VariableRollbackRequest):
    global STRAGE
    global STRAGE_ROLLBACK
    global IS_RUNNING
    if request.id not in STRAGE or request.id not in STRAGE_ROLLBACK:
        return {"error": "Id not found"}
    
    # Wait until IS_RUNNING[request.id] = False
    timeout = 10
    start_time = time.time()
    while IS_RUNNING[request.id] and (time.time() - start_time) < timeout:
        pass
    if IS_RUNNING[request.id]:
        return {"error": "Code is still running, please try again later"}
    
    # Rollback
    STRAGE[request.id] = STRAGE_ROLLBACK[request.id]
    return {"ok": "variables rolled back successfully"}


# Retrieve saved variables
class VariableRetrievalResponse(BaseModel):
    id: str
    name: str
@app.post("/var")
def get_variable(request: VariableRetrievalResponse):
    global STRAGE
    global IS_RUNNING
    if request.id not in STRAGE or request.id not in IS_RUNNING:
        return {"error": "Id not found"}
    
    # Wait until IS_RUNNING[request.id] = False
    timeout = 10
    start_time = time.time()
    while IS_RUNNING[request.id] and (time.time() - start_time) < timeout:
        pass
    if IS_RUNNING[request.id]:
        return {"error": "Code is still running, please try again later"}
    
    currentstrage = STRAGE[request.id]

    # Handle the case of ":." in the request name
    if ":." in request.name:
        requestcode = f"f'''{{{request.name}}}'''"
    else:
        requestcode = request.name

    # Allow eval to execute expressions like "df.shape" or "df.columns" (variables like df are stored in currentstrage)
    try:
        result = eval(requestcode, {}, currentstrage)
    except Exception as e:
        if "error" in request.name or "log" in request.name:
            return {"data": "", "type": "string"}
        return {"error": "Error: " + str(e)}
    
    def _to_json(result):
        if isinstance(result, pd.DataFrame):
            # Check if the index holds meaningful values
            df_copy = result.copy()
            if not df_copy.index.equals(pd.RangeIndex(len(df_copy))):
                # If the index has meaningful values, prepend it as a column with an empty name
                df_copy.insert(0, '', df_copy.index)
            return {"data": df_copy.to_json(orient="records"), "type": "table"}
        elif isinstance(result, pd.Series):
            # Also check the index for Series
            series_copy = result.copy()
            df_from_series = pd.DataFrame([series_copy])
            if not series_copy.index.equals(pd.RangeIndex(len(series_copy))):
                # If the index has meaningful values, prepend it as a column with an empty name
                df_from_series.insert(0, '', series_copy.index)
            return {"data": df_from_series.to_json(orient="records"), "type": "table"}
        # 2. When result is a plt Figure: encode as base64 image and return
        elif isinstance(result, plt.Figure):
            buf = io.BytesIO()
            result.savefig(buf, format='jpeg')
            buf.seek(0)
            base64_image = base64.b64encode(buf.getvalue()).decode('utf-8')
            plt.close(result)  # Close the Figure to prevent memory leaks
            return {"data": base64_image, "type": "image"}
        # 3. Otherwise: return as string
        else:
            return {"data": str(result), "type": "string"}
    
    if isinstance(result, list):
        # For a list: convert each element to JSON
        result_data = [_to_json(item) for item in result]
    elif isinstance(result, dict):
        # For a dict: convert each key to String and each value to JSON
        result_data = []
        for key, value in result.items():
            result_data.append({"data": str(key), "type": "string"})
            result_data.append(_to_json(value))
    else:
        # For a single object: convert directly to JSON
        result_data = [_to_json(result)]
    
    return {"result": result_data}
