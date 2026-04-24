"""AI Chat module — endpoint definitions.

Thin wrappers that adapt the service layer to the Forge endpoint protocol.
All business logic lives in service.py, skills.py, and llm.py.

Endpoint UUIDs are permanent — never change them after first deployment.
"""
from __future__ import annotations

from typing import Generator

from forge.control import StreamEvent, action_endpoint, streaming_endpoint

from ai_chat_endpoints import service
from ai_chat_endpoints.llm import AVAILABLE_MODELS
from ai_chat_endpoints.skills import list_all_skills

# ── Permanent endpoint UUIDs ──────────────────────────────────────────────────
# NEVER change these after any project has used this module.

_START_SESSION_UUID        = "a1ca4000-0002-0000-0000-000000000001"
_SEND_MESSAGE_UUID         = "a1ca4000-0002-0000-0000-000000000002"
_UPLOAD_CONTEXT_UUID       = "a1ca4000-0002-0000-0000-000000000003"
_GET_SESSION_MESSAGES_UUID = "a1ca4000-0002-0000-0000-000000000004"
_LIST_SESSIONS_UUID        = "a1ca4000-0002-0000-0000-000000000005"
_DELETE_SESSION_UUID       = "a1ca4000-0002-0000-0000-000000000006"
_LIST_MODELS_UUID          = "a1ca4000-0002-0000-0000-000000000007"
_LIST_SKILLS_UUID          = "a1ca4000-0002-0000-0000-000000000008"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@action_endpoint(
    name="start_or_resume_session",
    endpoint_id=_START_SESSION_UUID,
    params=[
        {"name": "title",      "type": "string", "required": False, "default": "New Chat"},
        {"name": "mode",       "type": "string", "required": False, "default": "train"},
        {"name": "model_id",   "type": "string", "required": False,
         "default": "claude-3-5-sonnet-20241022"},
        {"name": "session_id", "type": "string", "required": False, "default": None},
    ],
    description=(
        "Create a new chat session or resume an existing one. "
        "Pass session_id to resume; omit it to create."
    ),
)
def start_or_resume_session(
    title: str = "New Chat",
    mode: str = "train",
    model_id: str = "claude-3-5-sonnet-20241022",
    session_id: str | None = None,
) -> dict:
    if session_id:
        existing = service.resume_session(session_id)
        if existing:
            return existing
    return service.create_session(title=title, mode=mode, model_id=model_id)


@streaming_endpoint(
    name="send_message",
    endpoint_id=_SEND_MESSAGE_UUID,
    params=[
        {"name": "session_id", "type": "string", "required": True},
        {"name": "message",    "type": "string", "required": True},
    ],
    description=(
        "Send a message to the AI. Streams tokens as they arrive. "
        "In Train mode may emit skill_saved events when skill files are written."
    ),
)
def send_message(session_id: str, message: str) -> Generator[StreamEvent, None, None]:
    for event_type, data in service.send_message_stream(session_id, message):
        yield StreamEvent(event=event_type, data=data)


@action_endpoint(
    name="upload_context",
    endpoint_id=_UPLOAD_CONTEXT_UUID,
    params=[
        {"name": "session_id",   "type": "string", "required": True},
        {"name": "content_type", "type": "string", "required": True},  # "text" | "url"
        {"name": "content",      "type": "string", "required": True},
    ],
    description=(
        "Inject training material (plain text or URL) into the session history. "
        "Only available in Train mode."
    ),
)
def upload_context(session_id: str, content_type: str, content: str) -> dict:
    return service.upload_context(
        session_id=session_id,
        content_type=content_type,
        content=content,
    )


@action_endpoint(
    name="get_session_messages",
    endpoint_id=_GET_SESSION_MESSAGES_UUID,
    params=[{"name": "session_id", "type": "string", "required": True}],
    description="Return the full message history for a session.",
)
def get_session_messages(session_id: str) -> dict:
    result = service.resume_session(session_id)
    if result is None:
        return {"error": f"Session {session_id!r} not found."}
    return result


@action_endpoint(
    name="list_sessions",
    endpoint_id=_LIST_SESSIONS_UUID,
    params=[],
    description="Return all chat sessions ordered by most-recently-updated first.",
)
def list_sessions() -> list[dict]:
    return service.list_sessions()


@action_endpoint(
    name="delete_session",
    endpoint_id=_DELETE_SESSION_UUID,
    params=[{"name": "session_id", "type": "string", "required": True}],
    description="Permanently delete a session and all its messages.",
)
def delete_session(session_id: str) -> dict:
    service.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@action_endpoint(
    name="list_available_models",
    endpoint_id=_LIST_MODELS_UUID,
    params=[],
    description="Return the list of LLM models this module supports.",
)
def list_available_models() -> list[dict]:
    return AVAILABLE_MODELS


@action_endpoint(
    name="list_skills",
    endpoint_id=_LIST_SKILLS_UUID,
    params=[],
    description="Return metadata for all available skills (project-local and package defaults).",
)
def list_skills() -> list[dict]:
    return [{k: v for k, v in s.items() if k != "file_path"} for s in list_all_skills()]
