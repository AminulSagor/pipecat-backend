import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from livekit_auth import build_livekit_token, sanitize_livekit_name

load_dotenv(override=True)

app = FastAPI(title="LiveKit Token API", version="1.0.0")


@app.get("/health", include_in_schema=False)
async def healthcheck():
    return {
        "status": "ok",
    }


@app.get("/livekit/token", include_in_schema=False)
async def livekit_token(
    session: str,
    identity: str | None = None,
    ttl_seconds: int | None = None,
):
    room = sanitize_livekit_name(session, fallback="voice-room")
    token_identity = sanitize_livekit_name(identity or str(uuid.uuid4()), fallback="participant")
    ttl = ttl_seconds or int(os.getenv("LIVEKIT_TOKEN_TTL_SECONDS", "900"))

    if ttl < 60 or ttl > 3600:
        raise HTTPException(status_code=400, detail="ttl_seconds must be between 60 and 3600")

    livekit_url = os.getenv("LIVEKIT_URL")
    if not livekit_url:
        raise HTTPException(status_code=500, detail="LIVEKIT_URL is required")

    try:
        token = build_livekit_token(room=room, identity=token_identity, ttl_seconds=ttl)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "url": livekit_url,
        "room": room,
        "identity": token_identity,
        "token": token,
        "ttl_seconds": ttl,
    }
