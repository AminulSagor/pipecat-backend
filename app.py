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

@app.get("/livekit/token")
async def livekit_token(session: str, identity: str | None = None, ttl_seconds: int = 900):
    if ttl_seconds < 60 or ttl_seconds > 3600:
        raise HTTPException(status_code=400, detail="ttl_seconds must be between 60 and 3600")

    room = sanitize_livekit_name(session, "voice-room")
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