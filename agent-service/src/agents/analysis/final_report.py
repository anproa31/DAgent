from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import get_variable_results
from orchestration.streaming import make_delta_emitter
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import RETRIEVAL_RESPONSE_SYSTEM, FINAL_REPORT_SYSTEM, format_language_rule

logger = get_logger("final_report")


def _appendix_block(state: AgentState) -> dict | None:
    """Annotated Appendix holding the SQL and Python that produced the results.

    Computer code belongs in the appendix (data-analysis-report convention),
    annotated so a technical reviewer can follow what was run.
    """
    parts: list[str] = []

    sql = (state.get("sql_draft") or "").strip()
    if sql:
        note = state.get("sql_explanation", "")
        parts.append("### Query (SQL)")
        if note:
            parts.append(f"_{note}_")
        parts.append(f"```sql\n{sql}\n```")

    code = (state.get("python_code") or "").strip()
    if code:
        parts.append("### Analysis Code (Python)")
        parts.append(f"```python\n{code}\n```")

    if not parts:
        return None
    return {"type": "markdown", "content": "## Appendix\n" + "\n\n".join(parts)}


async def _synthesize_framing(state: AgentState, session_id: str) -> tuple[str, str, str, str]:
    """LLM-generate the report Title, Answer, Introduction, and Conclusion.

    Returns ``(title, answer_md, introduction_md, conclusion_md)``; any piece may
    be empty if synthesis fails or a marker is missing, so callers must tolerate
    that.
    """
    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    prompt = FINAL_REPORT_SYSTEM.format(
        query=state.get("query", ""),
        data_summary=state.get("data_summary", "") or "No data summary available",
        eda_summary=state.get("eda_summary", "") or "No EDA performed",
        insights=state.get("insights", "") or "No insights generated",
        language_rule=format_language_rule(state.get("language", "en")),
    )
    try:
        text = await chat_complete(
            client,
            model,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": state.get("query", "")},
            ],
            temperature=0.3,
            log_tag="final_report",
            on_delta=make_delta_emitter(state.get("run_id", ""), "final_report"),
        )
    except Exception as exc:
        logger.warning("framing synthesis failed: %s", exc)
        return "", "", "", ""

    return _parse_framing(text)


def _parse_framing(text: str) -> tuple[str, str, str, str]:
    """Split the LLM framing output on its sentinel markers.

    Returns ``(title, answer, introduction, conclusion)``. Markers are expected
    in order TITLE → ANSWER → INTRODUCTION → CONCLUSION; each split peels the
    tail off, so a missing marker just leaves that piece empty.
    """
    rest = text
    answer, intro, conclusion = "", "", ""

    if "---CONCLUSION---" in rest:
        rest, conclusion = rest.split("---CONCLUSION---", 1)
    if "---INTRODUCTION---" in rest:
        rest, intro = rest.split("---INTRODUCTION---", 1)
    if "---ANSWER---" in rest:
        head, answer = rest.split("---ANSWER---", 1)
    else:
        head = rest

    title = ""
    for line in head.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("TITLE:"):
            title = stripped[len("TITLE:"):].strip().strip('"')
            break

    # No markers at all → treat the whole thing as the answer (don't lose it).
    if not any((title, answer, intro, conclusion)):
        answer = text.strip()

    return title.strip(), answer.strip(), intro.strip(), conclusion.strip()


def _has_reportable_content(state: AgentState) -> bool:
    """True when we can build a substantive report despite an upstream worker error."""
    if state.get("insights") or state.get("eda_summary"):
        return True
    if state.get("result_var_names") or state.get("viz_var_names"):
        return True
    if state.get("sql_draft") or state.get("python_code"):
        return True
    data_summary = state.get("data_summary", "")
    return bool(data_summary and data_summary != "No data returned")


async def final_report_node(state: AgentState) -> dict:
    intent = state.get("intent", "ANALYTICAL")
    logger.info("enter intent=%s", intent)

    session_id = state.get("session_id", state.get("run_id", "default"))
    content = []

    if state.get("error") and not _has_reportable_content(state):
        content.append({"type": "markdown", "content": f"**Error:** {state['error']}"})
        return {"report_content": content, "done": True, "current_agent": "final_report"}

    if intent == "RETRIEVAL":
        content = await _build_retrieval_report(state, session_id)
    else:
        content = await _build_analytical_report(state, session_id)

    logger.info("exit sections=%d", len(content))
    return {
        "report_content": content,
        "done": True,
        "current_agent": "final_report",
        "agent_steps": state.get("agent_steps", []) + ["final_report"],
    }


async def _build_retrieval_report(state: AgentState, session_id: str) -> list:
    content = []

    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        content.extend(data_content)

    data_summary = state.get("data_summary", "")
    if data_summary and data_summary != "No data returned":
        client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
        model = state.get("model", "")
        prompt = RETRIEVAL_RESPONSE_SYSTEM.format(
            query=state.get("query", ""),
            data_summary=data_summary,
            language_rule=format_language_rule(state.get("language", "en")),
        )
        try:
            response_text = await chat_complete(
                client,
                model,
                [{"role": "system", "content": prompt}, {"role": "user", "content": state.get("query", "")}],
                temperature=0.1,
                log_tag="final_report",
                on_delta=make_delta_emitter(state.get("run_id", ""), "final_report"),
            )
            content.append({"type": "markdown", "content": response_text})
        except Exception as exc:
            logger.warning("retrieval response LLM failed: %s", exc)

    appendix = _appendix_block(state)
    if appendix:
        content.append(appendix)

    return content


async def _build_analytical_report(state: AgentState, session_id: str) -> list:
    """Assemble a structured data-analysis report.

    Layout leads with a direct Answer to the user's question, then follows the
    standard data-analysis-report shape:
    Title → Answer → Introduction → Body (Data / Analysis / Key Findings / Charts)
    → Conclusion → Appendix (annotated SQL & Python code).
    """
    content = []

    # --- Title + Answer + Introduction (LLM-synthesized framing) ---
    title, answer, intro, conclusion = await _synthesize_framing(state, session_id)
    if title:
        content.append({"type": "markdown", "content": f"# {title}"})
    # The Answer is the headline — directly resolves the user's question and is
    # rendered first/highlighted so it isn't buried in a generic narrative.
    if answer:
        content.append({"type": "markdown", "content": f"## Answer\n{answer}"})
    if intro:
        content.append({"type": "markdown", "content": f"## Introduction\n{intro}"})

    # --- Body: Data ---
    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        if data_content:
            content.append({"type": "markdown", "content": "## Data"})
            content.extend(data_content)

    # --- Body: Analysis (EDA) ---
    eda = state.get("eda_summary", "")
    if eda:
        content.append({"type": "markdown", "content": f"## Analysis\n{eda}"})

    # --- Body: Key Findings (insights) ---
    insights = state.get("insights", "")
    if insights:
        content.append({"type": "markdown", "content": f"## Key Findings\n{insights}"})

    # --- Body: Visualizations ---
    viz_vars = state.get("viz_var_names", [])
    if viz_vars:
        viz_content = await get_variable_results(session_id, viz_vars)
        if viz_content:
            content.append({"type": "markdown", "content": "## Visualizations"})
            content.extend(viz_content)

    # --- Conclusion ---
    if conclusion:
        content.append({"type": "markdown", "content": f"## Conclusion\n{conclusion}"})

    # --- Appendix: code that produced the results ---
    appendix = _appendix_block(state)
    if appendix:
        content.append(appendix)

    return content
