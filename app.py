import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv
from livekit_auth import build_livekit_token, sanitize_livekit_name
from session_manager import SessionManager

load_dotenv()

app = FastAPI()
session_manager = SessionManager()


class SessionStartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId", min_length=1)
    identity: str | None = None
    ttl_seconds: int = Field(default=900, alias="ttlSeconds", ge=60, le=3600)


class SessionStartResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    status: str
    created: bool
    pid: int
    started_at: str = Field(alias="startedAt")
    url: str | None
    room: str
    identity: str
    token: str
    ttl_seconds: int = Field(alias="ttlSeconds")


class SessionEndRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId", min_length=1)


class SessionEndResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    status: str
    stopped: bool

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("shutdown")
def shutdown_cleanup() -> None:
    session_manager.stop_all_sessions()


def resolve_room_name(session: str | None) -> str:
    # Priority: explicit query session -> shared env session
    session_value = (session or "").strip() or (os.getenv("LIVEKIT_SESSION") or "").strip()
    if not session_value:
        raise HTTPException(
            status_code=400,
            detail="session is required (query ?session=... or set LIVEKIT_SESSION)",
        )
    return sanitize_livekit_name(session_value, "voice-room")


@app.get("/livekit/token")
async def livekit_token(
    session: str | None = None, identity: str | None = None, ttl_seconds: int = 900
):
    if ttl_seconds < 60 or ttl_seconds > 3600:
        raise HTTPException(status_code=400, detail="ttl_seconds must be between 60 and 3600")

    room = resolve_room_name(session)
    user_identity = sanitize_livekit_name(identity or str(uuid.uuid4()), "guest")

    try:
        token = build_livekit_token(room, user_identity, ttl_seconds)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "url": os.getenv("LIVEKIT_URL"),
        "room": room,
        "identity": user_identity,
        "token": token,
        "ttl_seconds": ttl_seconds,
    }


@app.post("/session/start", response_model=SessionStartResponse)
async def session_start(payload: SessionStartRequest):
    room = sanitize_livekit_name(payload.session_id, "voice-room")
    user_identity = sanitize_livekit_name(payload.identity or str(uuid.uuid4()), "guest")

    session_details = session_manager.start_session(room)

    try:
        token = build_livekit_token(room, user_identity, payload.ttl_seconds)
    except RuntimeError as exc:
        if session_details.get("created"):
            session_manager.end_session(room)
        raise HTTPException(status_code=500, detail=str(exc))

    return SessionStartResponse(
        sessionId=room,
        status=str(session_details["status"]),
        created=bool(session_details["created"]),
        pid=int(session_details["pid"]),
        startedAt=str(session_details["started_at"]),
        url=os.getenv("LIVEKIT_URL"),
        room=room,
        identity=user_identity,
        token=token,
        ttlSeconds=payload.ttl_seconds,
    )


@app.post("/session/end", response_model=SessionEndResponse)
async def session_end(payload: SessionEndRequest):
    room = sanitize_livekit_name(payload.session_id, "voice-room")
    end_details = session_manager.end_session(room)

    return SessionEndResponse(
        sessionId=room,
        status=str(end_details["status"]),
        stopped=bool(end_details["stopped"]),
    )