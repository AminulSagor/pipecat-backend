# my-voice-bot

A Pipecat AI voice agent built with a cascade pipeline (STT → LLM → TTS).

## Configuration

- **Bot Type**: Web
- **Transport(s)**: LiveKit
- **Pipeline**: Cascade
  - **STT**: OpenAI (Whisper)
  - **LLM**: OpenAI
  - **TTS**: OpenAI TTS

## Setup

### Server

1. **Install dependencies**:

   ```bash
   uv sync
   ```

2. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI and LiveKit credentials
   ```

3. **Run token API (Service A, recommended Railway web service)**:

   ```bash
   uv run uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
   ```

4. **Run bot worker (Service B, separate worker/background service)**:

   ```bash
   uv run python main.py
   ```

### Flutter / Frontend Connection Flow

1. Call backend endpoint: `GET /livekit/token?session=<session_id>`
2. Receive JSON with `url`, `room`, `identity`, `token`
3. In Flutter LiveKit client, connect using returned `url` and `token`

Example token response shape:

```json
{
  "url": "wss://<project>.livekit.cloud",
  "room": "my-session-id",
  "identity": "mobile-user-123",
  "token": "<jwt>",
  "ttl_seconds": 900
}
```

### Railway deployment note

- Use two services for clean separation:
   - Web service command: `uv run uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Worker service command: `uv run python main.py`
- Token API starts fast and exposes `GET /health` and `GET /livekit/token`.
- Bot worker is isolated from web boot path and only handles LiveKit/Pipecat session logic.
- Worker startup does not use Pipecat runner CLI or WebRTC transport mode.

## Project Structure

```
pipecat_voice_service/
├── main.py              # Pipecat bot runner only
├── app.py               # FastAPI health + token endpoints (Service A)
├── livekit_auth.py      # Shared token helper functions
├── pyproject.toml       # Python dependencies
├── .env.example         # Environment variables template
├── .env                 # Your API keys (git-ignored)
└── README.md            # This file
```
## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)