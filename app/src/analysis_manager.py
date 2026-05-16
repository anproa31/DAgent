import uuid
import asyncio
import json
import os
import re
import requests
from typing import Dict, List, Any
import openai
from .models.requests import StartAnalysisRequest
from .utils.prompts import (
    get_db_embedded_prompt,
    is_database_registered,
)
from .code_service import CodeService
from .utils.llm_models import (
    get_openai_client,
    get_model_by_id,
)

# Global variable to hold the state of individual analyses
analysis_states: Dict[str, Dict[str, Any]] = {}

# A collection of individual analyses is called a space
spaces: Dict[str, List[str]] = {}  # list of analysis_ids

space_history: Dict[str, List[List[Dict]]] = {}  # List to hold space history (history stored as a 2D array)

code_service = CodeService()

ACTION_MODEL_TEMPERATURE = 0.2

def create_space():
    """Create a new space and return the space_id"""
    global spaces
    global space_history
    space_id = str(uuid.uuid4())
    spaces[space_id] = []
    space_history[space_id] = []
    return space_id

def get_space(space_id: str) -> List[str]:
    """Retrieve the analysis ID list for the specified space_id"""
    return spaces.get(space_id, [])

def delete_space(space_id: str) -> bool:
    """Delete a space and all associated analysis states"""
    global spaces, space_history, analysis_states
    if space_id not in spaces:
        return False
    # Remove all analysis states associated with this space
    for analysis_id in spaces[space_id]:
        analysis_states.pop(analysis_id, None)
    # Remove the space and its history
    del spaces[space_id]
    space_history.pop(space_id, None)
    return True

def start_analysis(request: StartAnalysisRequest) -> str:
    """Start an analysis and return the analysis_id"""
    global analysis_states
    global spaces
    global space_history
    # Validate request
    _validate_request(request)
    if request.index != -1:
        # If a history index is specified, revert history up to that index.
        # Check against spaces (not space_history) because stopped/failed analyses
        # are added to spaces but never to space_history.
        print(f"Reverting to history index {request.index} for space {request.space_id}")
        if 0 <= request.index < len(spaces[request.space_id]):
            # del list[n:] is a no-op when n >= len(list), so this is always safe
            del space_history[request.space_id][request.index:]
            del spaces[request.space_id][request.index:]
        else:
            raise ValueError("Invalid history index")
    analysis_id = str(uuid.uuid4())
    spaces[request.space_id].append(analysis_id)
    
    analysis_states[analysis_id] = {
        "query": request.query,
        "tables": request.tables,
        "mode": request.mode,
        "model": request.model,
        "done": False,
        "cancelled": False,
        "progress": "Analysis in progress...",
        "error": "",
        "python_code": "",
        "content": [],
        "steps": [],
        "full_response": "",
    }

    # Start AI analysis asynchronously
    if request.mode == "agentic":
        # Agentic analysis
        print("Starting agentic analysis...")
        asyncio.create_task(_run_analysis(request.space_id,analysis_id, request))
    else:
        # Standard analysis
        print("Starting standard analysis...")
        asyncio.create_task(_run_analysis(request.space_id,analysis_id, request))
        # asyncio.create_task(_run_analysis_non_streaming(analysis_id, request))

    return analysis_id

def _validate_request(request: StartAnalysisRequest):
    """Validate the request"""
    # Check that a database is registered
    if not is_database_registered():
        raise ValueError("No database registered")

    # Check that the query is long enough
    if len(request.query.strip()) <= 5:
        raise ValueError("Query is too short")


async def _run_analysis(space_id:str,analysis_id: str, request: StartAnalysisRequest):
    """Perform the actual analysis processing"""
    global analysis_states
    global space_history
    try:
        state = analysis_states[analysis_id]

        # Update progress
        state["progress"] = "Thinking..."

        # Configure the OpenAI client
        print("Starting analysis with model:", request.model)
        # Custom model specification is not yet supported
        # Generate AI response
        actionmodel_client = get_openai_client(request.model)
        model = get_model_by_id(request.model)
        if "data-analysis-agent" in model["model_name"] or "lightning" in model["model_name"]:
            messages = [{"role": "system", "content": get_db_embedded_prompt(request.tables)[1]}]
        else:
            messages = [{"role": "system", "content": get_db_embedded_prompt(request.tables)[0]}]
        for history in space_history[space_id]:
            messages.extend(history)
        messages.append({"role": "user", "content": request.query})
        stream = await actionmodel_client.chat.completions.create(
            model=model["model_name"],
            messages=messages,
            temperature=ACTION_MODEL_TEMPERATURE,
            stream=True,
            **model["config"],
        )
        full_response = ""
        executed = False
        code_task = None

        # Process the stream
        async for chunk in stream:
            # Check for cancellation before processing each chunk
            if state.get("cancelled"):
                await stream.close()
                break

            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_response += content
            if "<python>" not in full_response:
                state["progress"] = f"Thinking... {full_response[-20:]}"
            # Detect start of Python code execution
            if "<python>" in full_response and "</python>" not in full_response:
                state["progress"] = "Executing Python code..."

            # Execute Python code
            if not executed and "</python>" in full_response:
                executed = True
                python_code = _del_think_tag(full_response).split("<python>")[1].split("</python>")[0]
                state["python_code"] = python_code
                # Start code execution in non-blocking mode
                code_task = asyncio.create_task(
                    code_service.code_execution(python_code, space_id)
                )

            # Detect report generation
            if "<report>" in full_response and "</report>" not in full_response:
                state["progress"] = "Generating report..."
                report_buffer = _del_think_tag(full_response).split("<report>")[1]
                state["content"] = [{"type": "markdown", "content": report_buffer}]

        # If cancelled, cancel any running code task and exit
        if state.get("cancelled"):
            if code_task and not code_task.done():
                code_task.cancel()
            state["done"] = True
            state["progress"] = ""
            state["error"] = "Generation stopped by user."
            return

        # Wait for code execution to complete (with timeout)
        if code_task and not code_task.done():
            try:
                # Wait up to 10 seconds
                code_result = await asyncio.wait_for(code_task, timeout=10.0)
            except asyncio.TimeoutError:
                state["error"] = "Code execution timed out"
                state["done"] = True
                return
        else:
            code_result = (
                code_task.result() if code_task else {"result": "No code executed"}
            )
        print(full_response)
        if full_response == "":
            state["error"] = "No response from model"
            state["done"] = True
            return

        if code_result and ("error" in code_result or "code_error" in code_result):
            error_msg = code_result.get(
                "error", code_result.get("code_error", "Unknown error")
            )
            # An error occurred
            #### new⭐️ Use LLM to rewrite and re-execute the python code
            #
            #
            state["progress"] = "Fixing code execution error..."
            message = f"The following error occurred.\n{error_msg}\n\nPlease return the corrected python code wrapped in <python></python> tags."
            messages.append({"role": "assistant", "content": full_response})
            messages.append({"role": "user", "content": message})
            fixed_response = await actionmodel_client.chat.completions.create(
                model=model["model_name"],
                messages=messages,
                temperature=ACTION_MODEL_TEMPERATURE,
            )
            if not fixed_response.choices or not fixed_response.choices[0].message:
                state["error"] = "No response from model."
                state["done"] = True
                return
            fixed_full_response = fixed_response.choices[0].message.content
            print("## Fixed code")
            print(fixed_full_response)
            if (
                "<python>" not in fixed_full_response
                or "</python>" not in fixed_full_response
            ):
                state["error"] = "No corrected python code found."
                state["done"] = True
                return
            fixed_python_code = _del_think_tag(fixed_full_response).split("<python>")[1].split(
                "</python>"
            )[0]
            state["python_code"] = fixed_python_code
            # Replace the python tag content in full_response with fixed_python_code
            full_response = full_response.split("<python>")[0] + "<python>" + fixed_python_code + "</python>" + full_response.split("</python>")[1]
            # Re-execute the corrected code
            code_task = await code_service.code_execution(
                fixed_python_code, space_id
            )
            if code_task and ("error" in code_task or "code_error" in code_task):
                error_msg = code_task.get(
                    "error", code_task.get("code_error", "Unknown error")
                )
                state["progress"] = f"Code execution error after re-run: {error_msg}"
                state["done"] = True
                state["error"] = f"Code execution error after re-run: {error_msg}"
                return
        if "</report>" not in full_response:
            full_response += "\n</report>"
        state["full_response"] = full_response
        # Parse the response and generate content
        content = await _parse_response_to_content(
            full_response, space_id, ignore_errors=True
        )
        state["content"] = content

        # Done
        state["done"] = True
        state["progress"] = ""

        # Save the report
        # save_report(request.model or "default", request.query, full_response, "ok")

        # For standard analyses, add everything to history
        space_history[space_id].append([{"role":"user", "content": request.query},{"role":"assistant", "content": full_response}])

    except Exception as e:
        print(f"Analysis error for {analysis_id}: {str(e)}")
        state = analysis_states.get(analysis_id, {})
        state["error"] = f"Error: {str(e)}"
        state["done"] = True
        state["progress"] = ""

def _del_think_tag(content:str) ->str:
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)

import re
from typing import List, Dict, Any

async def _parse_response_to_content(
    response: str,
    analysis_id: str,
    ignore_errors: bool = True
) -> List[Dict[str, Any]]:
    """Parse the AI response and convert to content format (safe version)"""
    content: List[Dict[str, Any]] = []

    # Input check
    if not isinstance(response, str):
        raise TypeError(f"response must be str, got {type(response).__name__}")

    # Extract <report> tag (case-insensitive)
    match = re.search(r"<report>(.*?)</report>", response, re.IGNORECASE | re.DOTALL)
    report_content = match.group(1) if match else response

    # Variable pattern (also allows newlines)
    variable_pattern = r"\{([^\{\}]+?)\}"
    variables_iter = list(re.finditer(variable_pattern, report_content))
    print(f"Found {len(variables_iter)} variables in report content")

    # Processing cursor
    cursor = 0

    for var_match in variables_iter:
        placeholder = var_match.group(0)
        var_name = var_match.group(1)

        # Append text before the placeholder
        before_text = report_content[cursor:var_match.start()]
        if before_text.strip():
            content.append({"type": "markdown", "content": before_text.strip()})

        # Retrieve the variable value
        try:
            var_result = await code_service.get_variable_value(analysis_id, var_name)
        except Exception as e:
            if ignore_errors:
                print(f"Error retrieving variable '{var_name}': {e}")
                cursor = var_match.end()
                continue
            else:
                raise

        if var_result and isinstance(var_result, dict):
            if "result" in var_result and isinstance(var_result["result"], list):
                for var_content in var_result["result"]:
                    var_type = var_content.get("type", "string")
                    data = var_content.get("data")

                    if var_type == "image":
                        content.append({"type": "image", "base64": data})
                    elif var_type == "table":
                        content.append({"type": "table", "table": data})
                    else:
                        content.append({"type": "variable", "data": data})

            elif "error" in var_result:
                if ignore_errors:
                    print(f"Variable retrieval error for {var_name}: {var_result['error']}")
                else:
                    raise ValueError(
                        f"Variable retrieval error for {var_name}: {var_result['error']}"
                    )
            else:
                if ignore_errors:
                    print(f"Unexpected variable result format for {var_name}: {var_result}")
        else:
            if ignore_errors:
                print(f"No data returned for variable '{var_name}'")
            else:
                raise ValueError(f"No data returned for variable '{var_name}'")

        cursor = var_match.end()

    # Append remaining text as markdown
    remaining_text = report_content[cursor:]
    if remaining_text.strip():
        content.append({"type": "markdown", "content": remaining_text.strip()})

    return content



def stop_analysis(analysis_id: str) -> bool:
    """Signal a running analysis to stop. Returns True if the analysis was found."""
    global analysis_states
    if analysis_id not in analysis_states:
        return False
    state = analysis_states[analysis_id]
    if not state.get("done"):
        state["cancelled"] = True
    return True


def get_analysis_state(analysis_id: str) -> Dict[str, Any]:
    global analysis_states
    if analysis_id not in analysis_states:
        return {
            "done": True,
            "error": "Analysis ID not found",
            "progress": "",
            "query": "",
            "python_code": "",
            "content": [],
        }

    # Return a copy of the state to make it thread-safe
    state = analysis_states[analysis_id].copy()
    return state
