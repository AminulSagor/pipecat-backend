import os
from datetime import timedelta

from livekit import api


def sanitize_livekit_name(value: str, fallback: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip().lower())
    safe = "-".join(part for part in safe.split("-") if part)
    if not safe:
        safe = fallback
    return safe[:64]


def build_livekit_token(room: str, identity: str, ttl_seconds: int) -> str:
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError("LIVEKIT_API_KEY/LIVEKIT_API_SECRET are required")

    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_ttl(timedelta(seconds=ttl_seconds))
    )

    return token.to_jwt()