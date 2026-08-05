"""Espresso MCP server tools.

This module exposes the existing audio timing, recommendation, and machine
profile logic as MCP-callable functions. During local tests the functions are
called directly; when the optional ``mcp`` package is installed, they are also
registered on a FastMCP server.
"""

from __future__ import annotations

from typing import Any

import json

try:  # pragma: no cover - import behavior depends on installed MCP package.
    from mcp import types
    from mcp.server.lowlevel import Server
except ImportError:  # pragma: no cover - direct unit tests can still run without MCP.
    types = None  # type: ignore[assignment]
    Server = None  # type: ignore[assignment]

from services.espresso_mcp import audio_analysis
from services.espresso_mcp import grinder_profiles
from services.espresso_mcp import machine_profiles
from services.espresso_mcp import profile_candidates
from services.espresso_mcp import profile_research
from services.espresso_mcp import recommendations
from services.espresso_mcp import storage as result_storage

TOOL_NAMES = [
    "extract_audio_track",
    "detect_machine_audio_window",
    "calculate_total_shot_time",
    "analyze_audio_timing",
    "recommend_grind_adjustment",
    "get_machine_profile",
    "save_shot_result",
    "compare_previous_shots",
    "capture_unknown_gear",
    "list_profile_candidates",
    "prepare_profile_research",
    "attach_draft_profile",
]

TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "extract_audio_track": {
        "type": "object",
        "properties": {"video_s3_key": {"type": "string"}, "fps": {"type": ["number", "null"]}},
        "required": ["video_s3_key"],
    },
    "detect_machine_audio_window": {
        "type": "object",
        "properties": {"audio_s3_key": {"type": "string"}},
        "required": ["audio_s3_key"],
    },
    "calculate_total_shot_time": {
        "type": "object",
        "properties": {
            "machine_start_time": {"type": "number"},
            "machine_stop_time": {"type": "number"},
        },
        "required": ["machine_start_time", "machine_stop_time"],
    },
    "analyze_audio_timing": {
        "type": "object",
        "properties": {"video_s3_key": {"type": "string"}, "fps": {"type": ["number", "null"]}},
        "required": ["video_s3_key"],
    },
    "recommend_grind_adjustment": {
        "type": "object",
        "properties": {"shot_context": {"type": "object"}},
        "required": ["shot_context"],
    },
    "get_machine_profile": {
        "type": "object",
        "properties": {"machine_name": {"type": ["string", "null"]}},
        "required": ["machine_name"],
    },
    "save_shot_result": {
        "type": "object",
        "properties": {"user_id": {"type": "string"}, "result": {"type": "object"}},
        "required": ["user_id", "result"],
    },
    "compare_previous_shots": {
        "type": "object",
        "properties": {"user_id": {"type": "string"}, "current_result": {"type": "object"}},
        "required": ["user_id", "current_result"],
    },
    "capture_unknown_gear": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "machine": {"type": ["string", "null"]},
            "grinder": {"type": ["string", "null"]},
            "shot_context": {"type": "object"},
        },
        "required": ["user_id", "shot_context"],
    },
    "list_profile_candidates": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "prepare_profile_research": {
        "type": "object",
        "properties": {"candidate_key": {"type": "string"}},
        "required": ["candidate_key"],
    },
    "attach_draft_profile": {
        "type": "object",
        "properties": {
            "candidate_key": {"type": "string"},
            "draft_profile": {"type": "object"},
            "source_summary": {"type": ["string", "null"]},
        },
        "required": ["candidate_key", "draft_profile"],
    },
}

TOOL_DESCRIPTIONS = {
    "extract_audio_track": "Extract a mono WAV audio track from a local development video key/path.",
    "detect_machine_audio_window": "Detect machine/pump start and stop timestamps from WAV audio.",
    "calculate_total_shot_time": "Calculate total shot duration from machine start and stop timestamps.",
    "analyze_audio_timing": "Analyze audio timing for an uploaded video key/path.",
    "recommend_grind_adjustment": "Return the next grind or extraction adjustment for a shot.",
    "get_machine_profile": "Look up a curated machine profile by exact name or alias.",
    "save_shot_result": "Save a shot result in local in-memory history for the MVP.",
    "compare_previous_shots": "Compare current shot timing with the user's previous saved shot.",
    "capture_unknown_gear": "Save unknown machine/grinder names as profile candidates for later research.",
    "list_profile_candidates": "List captured unknown machine/grinder profile candidates.",
    "prepare_profile_research": "Prepare an LLM/search prompt packet for one profile candidate.",
    "attach_draft_profile": "Attach a sourced draft profile to a candidate for human review.",
}

SHOT_HISTORY = result_storage.SHOT_HISTORY

mcp = None


def extract_audio_track(video_s3_key: str, fps: float | None = None) -> dict[str, Any]:
    """Extract a mono WAV audio track from a local video key/path."""
    _ = fps
    return audio_analysis.extract_audio_track(video_s3_key)


def detect_machine_audio_window(audio_s3_key: str) -> dict[str, Any]:
    """Detect machine/pump start and stop timestamps from WAV audio."""
    return audio_analysis.detect_machine_audio_window(audio_s3_key)


def calculate_total_shot_time(machine_start_time: float, machine_stop_time: float) -> dict[str, Any]:
    """Calculate total shot duration from machine start and stop timestamps."""
    return audio_analysis.calculate_total_shot_time(machine_start_time, machine_stop_time)


def analyze_audio_timing(video_s3_key: str, fps: float | None = None) -> dict[str, Any]:
    """Analyze audio timing for an uploaded video key/path."""
    _ = fps
    return audio_analysis.analyze_audio_timing(video_s3_key)


def recommend_grind_adjustment(shot_context: dict[str, Any]) -> dict[str, Any]:
    """Return the next grind or extraction adjustment for a shot."""
    context = dict(shot_context)
    grind_setting_error = grinder_profiles.validate_grind_setting(context.get("grinder"), context.get("grind_setting"))
    if grind_setting_error:
        raise ValueError(grind_setting_error)
    if context.get("machine") and not context.get("machine_profile"):
        context["machine_profile"] = machine_profiles.get_machine_profile(context["machine"])
    return recommendations.recommend_grind_adjustment(context)


def get_machine_profile(machine_name: str | None) -> dict[str, Any]:
    """Look up a curated machine profile by exact name or alias."""
    return machine_profiles.get_machine_profile(machine_name)


def capture_unknown_gear(user_id: str, machine: str | None = None, grinder: str | None = None, shot_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Save unknown machine/grinder names as profile candidates for later research."""
    return profile_candidates.capture_unknown_gear(user_id, machine, grinder, shot_context or {})


def list_profile_candidates() -> list[dict[str, Any]]:
    """List captured unknown machine/grinder profile candidates."""
    return profile_candidates.load_profile_candidates()


def prepare_profile_research(candidate_key: str) -> dict[str, Any]:
    """Prepare an LLM/search prompt packet for one profile candidate."""
    return profile_research.prepare_research_packet(candidate_key)


def attach_draft_profile(candidate_key: str, draft_profile: dict[str, Any], source_summary: str | None = None) -> dict[str, Any]:
    """Attach a sourced draft profile to a candidate for human review."""
    return profile_research.attach_draft_profile(candidate_key, draft_profile, source_summary)


def save_shot_result(user_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Save a shot result in local in-memory history for the MVP."""
    return result_storage.save_shot_result(user_id, result)


def compare_previous_shots(user_id: str, current_result: dict[str, Any]) -> dict[str, Any]:
    """Compare current shot timing with the user's previous saved shot."""
    return result_storage.compare_previous_shots(user_id, current_result)


def get_registered_tool_names() -> list[str]:
    """Return tool names exposed by this service."""
    return list(TOOL_NAMES)


TOOL_FUNCTIONS = {
    "extract_audio_track": extract_audio_track,
    "detect_machine_audio_window": detect_machine_audio_window,
    "calculate_total_shot_time": calculate_total_shot_time,
    "analyze_audio_timing": analyze_audio_timing,
    "recommend_grind_adjustment": recommend_grind_adjustment,
    "get_machine_profile": get_machine_profile,
    "save_shot_result": save_shot_result,
    "compare_previous_shots": compare_previous_shots,
    "capture_unknown_gear": capture_unknown_gear,
    "list_profile_candidates": list_profile_candidates,
    "prepare_profile_research": prepare_profile_research,
    "attach_draft_profile": attach_draft_profile,
}


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return JSON-schema-style tool metadata used by MCP."""
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "input_schema": TOOL_INPUT_SCHEMAS[name],
        }
        for name in TOOL_NAMES
    ]


async def list_mcp_tools(_context: Any = None, _params: Any = None) -> Any:
    """MCP handler that lists registered tools."""
    if types is None:
        raise RuntimeError("Install MCP dependencies with `pip install -r services/espresso_mcp/requirements.txt`.")
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name=schema["name"],
                description=schema["description"],
                inputSchema=schema["input_schema"],
            )
            for schema in get_tool_schemas()
        ]
    )


async def call_mcp_tool(_context: Any, params: Any) -> Any:
    """MCP handler that calls one registered tool and returns structured content."""
    if types is None:
        raise RuntimeError("Install MCP dependencies with `pip install -r services/espresso_mcp/requirements.txt`.")

    name = params.name
    arguments = params.arguments or {}
    if name not in TOOL_FUNCTIONS:
        return types.CallToolResult(
            content=[types.TextContent(text=f"Unknown tool: {name}")],
            structuredContent={"error": f"Unknown tool: {name}"},
            isError=True,
        )

    try:
        result = TOOL_FUNCTIONS[name](**arguments)
    except Exception as error:  # pragma: no cover - exercised through integration callers.
        return types.CallToolResult(
            content=[types.TextContent(text=str(error))],
            structuredContent={"error": str(error)},
            isError=True,
        )

    return types.CallToolResult(
        content=[types.TextContent(text=json.dumps(result, default=str))],
        structuredContent=result,
        isError=False,
    )


def create_mcp_server() -> Any:
    """Create the MCP server object using the installed MCP 2.x API."""
    if Server is None:
        return None
    return Server(
        "espresso-mcp",
        version="0.1.0",
        description="Espresso shot timing and recommendation tools.",
        on_list_tools=list_mcp_tools,
        on_call_tool=call_mcp_tool,
    )


mcp = create_mcp_server()


if __name__ == "__main__":  # pragma: no cover - manual server entrypoint.
    if mcp is None:
        raise RuntimeError("Install MCP dependencies with `pip install -r services/espresso_mcp/requirements.txt`.")
    raise RuntimeError("MCP stdio runner wiring will be added with the agent integration checkpoint.")
