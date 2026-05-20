"""Analysis orchestration: LLM streaming, code execution, report parsing."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from ...infrastructure.external.llm_client import LLMClient, get_llm_client
from ...infrastructure.external.sandbox_client import SandboxClient
from ...models.requests import StartAnalysisRequest
from .analysis_state_store import AnalysisStateStore, get_analysis_state_store
from .prompt_service import PromptService, get_prompt_service
from .response_parser import del_think_tag, parse_response_to_content

ACTION_MODEL_TEMPERATURE = 0.2
logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(
        self,
        store: Optional[AnalysisStateStore] = None,
        sandbox: Optional[SandboxClient] = None,
        llm: Optional[LLMClient] = None,
        prompts: Optional[PromptService] = None,
    ) -> None:
        self._store = store or get_analysis_state_store()
        self._sandbox = sandbox or SandboxClient()
        self._llm = llm or get_llm_client()
        self._prompts = prompts or get_prompt_service()

    def start_analysis(self, request: StartAnalysisRequest) -> str:
        self._validate_request(request)
        self._store.ensure_space(request.space_id)

        if request.index != -1:
            if 0 <= request.index < self._store.space_analysis_count(request.space_id):
                self._store.truncate_space_history(request.space_id, request.index)
            else:
                raise ValueError("Invalid history index")

        analysis_id = str(uuid.uuid4())
        self._store.append_analysis(request.space_id, analysis_id)
        self._store.set_analysis(
            analysis_id,
            {
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
            },
        )

        asyncio.create_task(self._run_analysis(request.space_id, analysis_id, request))
        return analysis_id

    def stop_analysis(self, analysis_id: str) -> bool:
        state = self._store.get_analysis_ref(analysis_id)
        if state is None:
            return False
        if not state.get("done"):
            state["cancelled"] = True
        return True

    def get_analysis_state(self, analysis_id: str) -> Dict[str, Any]:
        state = self._store.get_analysis(analysis_id)
        if state is None:
            return {
                "done": True,
                "error": "Analysis ID not found",
                "progress": "",
                "query": "",
                "python_code": "",
                "content": [],
            }
        return state

    def _validate_request(self, request: StartAnalysisRequest) -> None:
        if not self._prompts.is_database_registered():
            raise ValueError("No database registered")
        if len(request.query.strip()) <= 5:
            raise ValueError("Query is too short")

    async def _run_analysis(
        self, space_id: str, analysis_id: str, request: StartAnalysisRequest
    ) -> None:
        state = self._store.get_analysis_ref(analysis_id)
        if state is None:
            return

        try:
            state["progress"] = "Thinking..."
            actionmodel_client = self._llm.get_openai_client(request.model)
            model = self._llm.get_model_by_id(request.model)

            if "data-analysis-agent" in model["model_name"] or "lightning" in model["model_name"]:
                messages = [
                    {"role": "system", "content": self._prompts.get_db_embedded_prompt(request.tables)[1]}
                ]
            else:
                messages = [
                    {"role": "system", "content": self._prompts.get_db_embedded_prompt(request.tables)[0]}
                ]

            for history in self._store.get_history(space_id):
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

            async for chunk in stream:
                if state.get("cancelled"):
                    await stream.close()
                    break
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                if "<python>" not in full_response:
                    state["progress"] = f"Thinking... {full_response[-20:]}"
                if "<python>" in full_response and "</python>" not in full_response:
                    state["progress"] = "Executing Python code..."
                if not executed and "</python>" in full_response:
                    executed = True
                    python_code = del_think_tag(full_response).split("<python>")[1].split("</python>")[0]
                    state["python_code"] = python_code
                    code_task = asyncio.create_task(
                        self._sandbox.execute_code(python_code, space_id)
                    )
                if "<report>" in full_response and "</report>" not in full_response:
                    state["progress"] = "Generating report..."
                    report_buffer = del_think_tag(full_response).split("<report>")[1]
                    state["content"] = [{"type": "markdown", "content": report_buffer}]

            if state.get("cancelled"):
                if code_task and not code_task.done():
                    code_task.cancel()
                state["done"] = True
                state["progress"] = ""
                state["error"] = "Generation stopped by user."
                return

            if code_task and not code_task.done():
                try:
                    code_result = await asyncio.wait_for(code_task, timeout=10.0)
                except asyncio.TimeoutError:
                    state["error"] = "Code execution timed out"
                    state["done"] = True
                    return
            else:
                code_result = code_task.result() if code_task else {"result": "No code executed"}

            if full_response == "":
                state["error"] = "No response from model"
                state["done"] = True
                return

            if code_result and ("error" in code_result or "code_error" in code_result):
                error_msg = code_result.get(
                    "error", code_result.get("code_error", "Unknown error")
                )
                state["progress"] = "Fixing code execution error..."
                messages.append({"role": "assistant", "content": full_response})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"The following error occurred.\n{error_msg}\n\n"
                            "Please return the corrected python code wrapped in "
                            "<python></python> tags."
                        ),
                    }
                )
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
                if (
                    "<python>" not in fixed_full_response
                    or "</python>" not in fixed_full_response
                ):
                    state["error"] = "No corrected python code found."
                    state["done"] = True
                    return
                fixed_python_code = del_think_tag(fixed_full_response).split("<python>")[1].split(
                    "</python>"
                )[0]
                state["python_code"] = fixed_python_code
                full_response = (
                    full_response.split("<python>")[0]
                    + "<python>"
                    + fixed_python_code
                    + "</python>"
                    + full_response.split("</python>")[1]
                )
                code_task = await self._sandbox.execute_code(fixed_python_code, space_id)
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
            content = await parse_response_to_content(
                full_response, space_id, self._sandbox, ignore_errors=True
            )
            state["content"] = content
            state["done"] = True
            state["progress"] = ""
            self._store.append_history(
                space_id,
                [
                    {"role": "user", "content": request.query},
                    {"role": "assistant", "content": full_response},
                ],
            )

        except Exception as e:
            logger.exception("Analysis error for %s", analysis_id)
            state["error"] = f"Error: {str(e)}"
            state["done"] = True
            state["progress"] = ""


_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    global _service
    if _service is None:
        _service = AnalysisService()
    return _service


def reset_analysis_service() -> None:
    global _service
    _service = None
