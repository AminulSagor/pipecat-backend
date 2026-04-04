import os

from pipecat.runner.livekit import generate_token


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

    try:
        token = generate_token(
            api_key=api_key,
            api_secret=api_secret,
            room_name=room,
            participant_name=identity,
            ttl=ttl_seconds,
        )
    except TypeError:
        # Compatibility fallback for older/newer Pipecat signatures.
        token = generate_token(api_key, api_secret, room, identity, ttl_seconds)

    return token
