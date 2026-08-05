"""LangGraph orchestration for the DialedIN chat coach."""

from __future__ import annotations

from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from services.agent import conversation, equipment_validation, image_identification, llm_extraction
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
    image_guess: dict[str, Any] | None
    image_error: str | None
    invalid_gear: dict[str, Any] | None
    invalid_field: dict[str, Any] | None


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
        image_guess=state.get("image_guess"),
    )


def build_chat_graph(analyze_callback: AnalyzeCallback):
    """Build and compile the espresso coach graph."""
    builder = StateGraph(CoachGraphState)
    builder.add_node("load_context", _load_context)
    builder.add_node("image_identify", _image_identify)
    builder.add_node("llm_extract", _llm_extract)
    builder.add_node("parse_message", _parse_message)
    builder.add_node("validate_equipment", _validate_equipment)
    builder.add_node("validate_field_answer", _validate_field_answer)
    builder.add_node("compute_missing", _compute_missing)
    builder.add_node("ask_next", _ask_next)
    builder.add_node("analyze_shot", _make_analyze_node(analyze_callback))

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "image_identify")
    builder.add_edge("image_identify", "llm_extract")
    builder.add_edge("llm_extract", "parse_message")
    builder.add_edge("parse_message", "validate_equipment")
    builder.add_edge("validate_equipment", "validate_field_answer")
    builder.add_edge("validate_field_answer", "compute_missing")
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
    context = conversation.sanitize_context(context)
    return {
        "context": context,
        "message": conversation.latest_user_message(request),
        "previous_missing": conversation.missing_chat_fields(context),
    }


def _image_identify(state: CoachGraphState) -> dict[str, Any]:
    request = state["request"]
    message = _latest_user_message_object(request)
    if not message or not message.image_base64 or not message.image_kind:
        return {}

    settings = get_settings()
    if not settings.chat_llm_extraction_enabled:
        return {}

    try:
        guess = image_identification.identify_gear_image_with_bedrock(
            image_base64=message.image_base64,
            media_type=message.image_media_type or "image/jpeg",
            gear_type=message.image_kind,
            model_id=settings.chat_llm_model_id,
            region=settings.aws_region,
        )
    except Exception as error:  # pragma: no cover - external Bedrock failures should not break chat.
        return {"image_error": f"{type(error).__name__}: {error}"}

    gear_type = guess.get("gear_type") or message.image_kind
    gear_name = guess.get("name")
    confidence = str(guess.get("confidence") or "low").lower()
    updates: dict[str, Any] = {}
    if gear_name and str(gear_name).lower() != "unknown" and confidence in {"medium", "high"}:
        canonical_name = conversation.canonical_gear_name(str(gear_name), gear_type)
        updates = {
            "pending_gear_type": gear_type,
            "pending_gear_name": canonical_name,
            "pending_gear_confidence": confidence,
        }
        guess = {**guess, "name": canonical_name, "confidence": confidence}

    context = state["context"].model_copy(update=updates) if updates else state["context"]
    return {"context": context, "image_guess": guess}


def _latest_user_message_object(request: ChatRequest):
    for message in reversed(request.messages):
        if message.role == "user":
            return message
    return None


def _llm_extract(state: CoachGraphState) -> dict[str, Any]:
    latest_message = _latest_user_message_object(state["request"])
    if latest_message and latest_message.image_base64:
        return {}

    message = state.get("message", "")
    if not message:
        return {}
    if conversation.is_compact_setup_message(message):
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

    extracted = _filter_extracted_context(extracted, message, state.get("previous_missing", []))
    return {"context": llm_extraction.merge_extracted_context(state["context"], extracted)}


def _filter_extracted_context(extracted: dict[str, Any], message: str, previous_missing: list[str]) -> dict[str, Any]:
    """Keep LLM extraction aligned with the field the coach asked for."""
    expected_field = previous_missing[0] if previous_missing else None
    filtered = dict(extracted)
    if expected_field != "timing" and not conversation.has_explicit_timing(message):
        filtered.pop("total_shot_seconds", None)
        filtered.pop("video_s3_key", None)
    if expected_field == "grind_setting" and not conversation.has_labeled_dose(message):
        filtered.pop("dose_g", None)
    if expected_field == "taste" and conversation.is_structured_field_correction(message) and not conversation.has_labeled_taste(message):
        filtered.pop("taste", None)
    if filtered.get("machine"):
        filtered["machine"] = conversation.canonical_gear_name(str(filtered["machine"]), "machine")
    if filtered.get("grinder"):
        filtered["grinder"] = conversation.canonical_gear_name(str(filtered["grinder"]), "grinder")
    return filtered


def _parse_message(state: CoachGraphState) -> dict[str, Any]:
    context = state["context"]
    latest_message = _latest_user_message_object(state["request"])
    if latest_message and latest_message.image_base64:
        return {"context": context}

    message = state.get("message", "")
    if message:
        conversation.apply_message_to_context(context, message, state.get("previous_missing", []))
    return {"context": context}



def _validate_equipment(state: CoachGraphState) -> dict[str, Any]:
    latest_message = _latest_user_message_object(state["request"])
    if latest_message and latest_message.image_base64:
        return {}

    expected_field = (state.get("previous_missing") or [None])[0]
    if expected_field not in {"machine", "grinder"}:
        return {}

    context = state["context"]
    if expected_field == "grinder" and context.uses_built_in_grinder:
        if _machine_disallows_built_in_grinder(context):
            return {
                "context": context.model_copy(update={"uses_built_in_grinder": False, "grinder": None}),
                "invalid_field": {
                    "field": "grinder",
                    "reason": f"{context.machine} does not have a built-in grinder, so I need the separate grinder model.",
                },
            }
        return {}

    name = getattr(context, expected_field)
    if not name:
        message = state.get("message", "")
        if _should_reject_missing_equipment_reply(message):
            return {
                "invalid_gear": {
                    "gear_type": expected_field,
                    "name": message.strip(),
                    "reason": "That does not look like a real espresso machine or grinder model.",
                }
            }
        return {}

    settings = get_settings()
    if not settings.chat_llm_extraction_enabled:
        return {}

    validation = equipment_validation.validate_equipment_name(
        name=name,
        gear_type=expected_field,
        model_id=settings.chat_llm_model_id,
        region=settings.aws_region,
    )
    if validation.get("is_equipment"):
        corrected_name = validation.get("corrected_name") or name
        updates = {expected_field: conversation.canonical_gear_name(str(corrected_name), expected_field)}
        if expected_field == "machine" and context.uses_built_in_grinder and not context.grinder:
            updates["grinder"] = f"{updates['machine']} built-in grinder"
        return {"context": context.model_copy(update=updates)}

    updates = {expected_field: None}
    if expected_field == "machine":
        updates.update({"uses_built_in_grinder": False, "grinder": None})
    return {
        "context": context.model_copy(update=updates),
        "invalid_gear": {
            "gear_type": expected_field,
            "name": name,
            "reason": validation.get("reason") or "That does not look like espresso equipment.",
        },
    }



def _validate_field_answer(state: CoachGraphState) -> dict[str, Any]:
    expected_field = (state.get("previous_missing") or [None])[0]
    if expected_field not in {"grind_setting", "roast_level", "timing"}:
        return {}

    message = state.get("message", "")
    if not message or conversation.is_small_talk(message):
        return {}

    context = state["context"]
    updates: dict[str, Any] = {}
    reason: str | None = None

    if expected_field == "grind_setting":
        if not context.grind_setting or not _looks_numeric(context.grind_setting):
            updates["grind_setting"] = None
            reason = "Grind setting should be the number or mark on your grinder, like 12 or 2.1."
    elif expected_field == "roast_level" and context.roast_level not in {"light", "medium", "dark"}:
        updates["roast_level"] = None
        reason = "Roast level should be light, medium, or dark."
    elif expected_field == "timing" and not context.video_s3_key and context.total_shot_seconds is None:
        reason = "Please attach or send a shot video, or type the total time if you timed it yourself, like 27 seconds."

    if not reason:
        return {}

    next_context = context.model_copy(update=updates) if updates else context
    return {
        "context": next_context,
        "invalid_field": {
            "field": expected_field,
            "reason": reason,
        },
    }


def _looks_numeric(value: str | None) -> bool:
    if value is None:
        return False
    try:
        float(str(value).strip())
    except ValueError:
        return False
    return True


def _machine_disallows_built_in_grinder(context: ShotContext) -> bool:
    if not context.machine:
        return False
    profile = conversation.machine_profiles.get_machine_profile(context.machine)
    specs = profile.get("specs") or {}
    return specs.get("has_built_in_grinder") is False



def _should_reject_missing_equipment_reply(message: str) -> bool:
    cleaned = message.strip()
    if not cleaned:
        return False
    if conversation.is_greeting(cleaned) or conversation.is_small_talk(cleaned):
        return False
    lowered = cleaned.lower()
    if any(phrase in lowered for phrase in ["help", "dial in", "espresso shot", "shot analysis"]):
        return False
    return True

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
    previous_missing = state.get("previous_missing", [])
    if invalid_prompt := _invalid_gear_prompt(state):
        response = invalid_prompt
    elif invalid_field_prompt := _invalid_field_prompt(state, context):
        response = invalid_field_prompt
    elif image_prompt := _low_confidence_image_prompt(state):
        response = image_prompt
    elif not message:
        response = "Hey, I can help dial in your espresso. What machine are you using?"
    elif previous_missing[:1] == ["confirm_machine"] and conversation.is_confirmation_no(message):
        response = "No problem. What machine is it?"
    elif previous_missing[:1] == ["confirm_grinder"] and conversation.is_confirmation_no(message):
        response = "No problem. What grinder is it?"
    elif conversation.is_greeting(message) and conversation.is_empty_context(context):
        response = "Hey, I can help dial in your espresso shot. What machine are you using?"
    elif small_talk_response := conversation.small_talk_reply(message, missing[0], context):
        response = small_talk_response
    else:
        response = conversation.question_for(missing[0], context)
    return {"response": response, "analysis_result": None}





def _invalid_field_prompt(state: CoachGraphState, context: ShotContext) -> str | None:
    invalid = state.get("invalid_field")
    if not invalid:
        return None
    field = invalid.get("field")
    reason = invalid.get("reason") or "That value does not look right."
    return f"{reason} {conversation.question_for(str(field), context)}"

def _invalid_gear_prompt(state: CoachGraphState) -> str | None:
    invalid = state.get("invalid_gear")
    if not invalid:
        return None
    gear_type = invalid.get("gear_type") or "equipment"
    name = invalid.get("name") or "that"
    if gear_type == "machine":
        return f"I could not confirm '{name}' as an espresso machine. Please enter the machine brand and model, like Rancilio Silvia or Breville Bambino."
    return f"I could not confirm '{name}' as a coffee grinder. Please enter the grinder brand and model, like Varia VS3 or DF54."

def _low_confidence_image_prompt(state: CoachGraphState) -> str | None:
    guess = state.get("image_guess") or {}
    latest_message = _latest_user_message_object(state["request"])
    if not latest_message or not latest_message.image_base64:
        return None
    if guess.get("name") and str(guess.get("confidence") or "low").lower() in {"medium", "high"}:
        return None
    gear_type = guess.get("gear_type") or latest_message.image_kind or "machine"
    if gear_type == "grinder":
        return "I could not identify the grinder confidently from the photo. What grinder is it?"
    return "I could not identify the machine confidently from the photo. What machine is it?"


def _make_analyze_node(analyze_callback: AnalyzeCallback):
    def _analyze(state: CoachGraphState) -> dict[str, Any]:
        context = state["context"]
        try:
            analysis = analyze_callback(AnalyzeShotRequest(**context.model_dump()))
        except ValueError as error:
            if "grind setting" in str(error).lower() or "numeric" in str(error).lower():
                context.grind_setting = None
                return {
                    "context": context,
                    "analysis_result": None,
                    "response": f"That grind setting needs to be numeric. What grind setting are you currently using?",
                    "missing_fields": ["grind_setting"],
                    "next_field": "grind_setting",
                }
            raise
        return {
            "analysis_result": analysis,
            "response": conversation.analysis_reply(analysis),
            "missing_fields": [],
            "next_field": None,
        }

    return _analyze
