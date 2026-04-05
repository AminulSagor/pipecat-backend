import os
import uuid
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from livekit_auth import build_livekit_token, sanitize_livekit_name

load_dotenv()

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}


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