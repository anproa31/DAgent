import os
import json
import base64
import httpx
from .models.requests import VariableRetrievalResponse

CODE_RUNNER_URL = os.getenv("CODE_RUNNER_URL")

class CodeService:
    async def code_execution(self, python_code: str, access_id: str):
        """Executes Python code."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    CODE_RUNNER_URL + "code",
                    json={
                        "code": python_code.replace("\\", "%@"),
                        "id": access_id,
                    }
                )
                
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code.

            # --- Processing the response from code-runner ---
            runner_result = response.json()

            if "error" in runner_result:
                print(f"Error from code runner: {runner_result['error']}")
                return {"code_error": runner_result['error']}

            print("Code executed successfully:")
            return {"result": runner_result}

        except httpx.HTTPStatusError as e:
            print(f"HTTP connection error during code execution: {e}")
            return {"error": "HTTP connection error during code execution"}
        except httpx.TimeoutException:
            print("Request timed out error during code execution")
            return {"error": "Request timed out error during code execution"}
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return {"error": "An unexpected error during code execution"}

    async def code_rollback(self, access_id: str):
        """Performs a rollback of the code."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    CODE_RUNNER_URL + "rollback",
                    json={"id": access_id}
                )
                
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code.

            rollback_result = response.json()
            if "error" in rollback_result:
                print(f"Error during rollback: {rollback_result['error']}")
                return {"error": rollback_result['error']}

            print("Rollback executed successfully")
            return {"result": rollback_result}

        except httpx.HTTPStatusError as e:
            print(f"HTTP connection error during rollback: {e}")
            return {"error": "HTTP connection error during rollback"}
        except httpx.TimeoutException:
            print("Request timed out error during rollback")
            return {"error": "Request timed out error during rollback"}
        except Exception as e:
            print(f"An unexpected error occurred during rollback: {e}")
            return {"error": "An unexpected error during rollback"}

    async def get_variable(self, request: VariableRetrievalResponse):
        """Endpoint to retrieve a variable."""
        endpoint_url = f"{CODE_RUNNER_URL}var"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint_url, json={"id": request.id, "name": request.name})

            if response.status_code != 200:
                return {"error": f"Code runner error: {response.status_code}", "detail": response.text}

            return response.json()
        except httpx.RequestError as e:
            return {"error": "Request failed", "detail": str(e)}

    async def get_variable_value(self, analysis_id: str, variable_name: str):
        """Variable retrieval method for analysis manager."""
        endpoint_url = f"{CODE_RUNNER_URL}var"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint_url, json={"id": analysis_id, "name": variable_name})

            if response.status_code != 200:
                return None
            
            return response.json()
        except Exception as e:
            print(f"Error getting variable {variable_name}: {e}")
            return None