"""LangGraph orchestration for the DialedIN chat coach."""

from __future__ import annotations

from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from services.agent import conversation, llm_extraction
from services.agent.config import get_settings
from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatRequest, ChatResponse, ShotContext

AnalyzeCallback = Callable[[AnalyzeShotRequest], AnalyzeShotResponse]


class CoachGraphState(TypedDict, total=False):
    request: ChatRequest
    context: ShotContext
    message: str
    previous_missing: list[str]
    missing_fields: list[str]
    next_field: str | None
    response: str
    analysis_result: AnalyzeShotResponse | None
    llm_error: str | None


def run_chat_graph(request: ChatRequest, analyze_callback: AnalyzeCallback) -> ChatResponse:
    """Run the compiled coach graph for one chat request."""
    graph = build_chat_graph(analyze_callback)
    state = graph.invoke({"request": request})
    return ChatResponse(
        response=state["response"],
        needs_shot_analysis=False,
        system_prompt="",
        shot_context=state["context"],
        analysis_result=state.get("analysis_result"),
        next_field=state.get("next_field"),
        missing_fields=state.get("missing_fields", []),
    )


def build_chat_graph(analyze_callback: AnalyzeCallback):
    """Build and compile the espresso coach graph."""
    builder = StateGraph(CoachGraphState)
    builder.add_node("load_context", _load_context)
    builder.add_node("llm_extract", _llm_extract)
    builder.add_node("parse_message", _parse_message)
    builder.add_node("compute_missing", _compute_missing)
    builder.add_node("ask_next", _ask_next)
    builder.add_node("analyze_shot", _make_analyze_node(analyze_callback))

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "llm_extract")
    builder.add_edge("llm_extract", "parse_message")
    builder.add_edge("parse_message", "compute_missing")
    builder.add_conditional_edges(
        "compute_missing",
        _route_after_missing,
        {"ask_next": "ask_next", "analyze_shot": "analyze_shot"},
    )
    builder.add_edge("ask_next", END)
    builder.add_edge("analyze_shot", END)
    return builder.compile()


def _load_context(state: CoachGraphState) -> dict[str, Any]:
    request = state["request"]
    context = request.shot_context.model_copy(deep=True) if request.shot_context else ShotContext()
    return {
        "context": context,
        "message": conversation.latest_user_message(request),
        "previous_missing": conversation.missing_chat_fields(context),
    }


def _llm_extract(state: CoachGraphState) -> dict[str, Any]:
    message = state.get("message", "")
    if not message:
        return {}

    settings = get_settings()
    if not settings.chat_llm_extraction_enabled:
        return {}

    try:
        extracted = llm_extraction.extract_context_with_bedrock(
            message=message,
            context=state["context"],
            model_id=settings.chat_llm_model_id,
            region=settings.aws_region,
        )
    except Exception as error:  # pragma: no cover - external Bedrock failures should not break chat.
        return {"llm_error": f"{type(error).__name__}: {error}"}

    return {"context": llm_extraction.merge_extracted_context(state["context"], extracted)}


def _parse_message(state: CoachGraphState) -> dict[str, Any]:
    context = state["context"]
    message = state.get("message", "")
    if message:
        conversation.apply_message_to_context(context, message, state.get("previous_missing", []))
    return {"context": context}


def _compute_missing(state: CoachGraphState) -> dict[str, Any]:
    missing = conversation.missing_chat_fields(state["context"])
    return {"missing_fields": missing, "next_field": missing[0] if missing else None}


def _route_after_missing(state: CoachGraphState) -> Literal["ask_next", "analyze_shot"]:
    if state.get("missing_fields"):
        return "ask_next"
    return "analyze_shot"


def _ask_next(state: CoachGraphState) -> dict[str, Any]:
    message = state.get("message", "")
    context = state["context"]
    missing = state.get("missing_fields", [])
    if not message:
        response = "Hey, I can help dial in your espresso. What machine are you using?"
    elif conversation.is_greeting(message) and conversation.is_empty_context(context):
        response = "Hey, I can help dial in your espresso shot. What machine are you using?"
    else:
        response = conversation.question_for(missing[0], context)
    return {"response": response, "analysis_result": None}


def _make_analyze_node(analyze_callback: AnalyzeCallback):
    def _analyze(state: CoachGraphState) -> dict[str, Any]:
        context = state["context"]
        analysis = analyze_callback(AnalyzeShotRequest(**context.model_dump()))
        return {
            "analysis_result": analysis,
            "response": conversation.analysis_reply(analysis),
            "missing_fields": [],
            "next_field": None,
        }

    return _analyze
