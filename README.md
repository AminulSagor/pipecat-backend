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

### Session Orchestration API

The API can start and stop a dedicated bot worker per session.

- `POST /session/start`
   - Body:

      ```json
      {
         "sessionId": "abc123"
      }
      ```

   - Behavior:
      - Starts a worker process with `LIVEKIT_SESSION=abc123`.
      - Returns LiveKit details (`url`, `room`, `identity`, `token`) for the same room.
      - Idempotent for active sessions: repeated calls return existing worker details.

- `POST /session/end`
   - Body:

      ```json
      {
         "sessionId": "abc123"
      }
      ```

   - Behavior:
      - Stops the worker process for that session.
      - Cleans up in-memory process state.
      - Idempotent for missing sessions: returns `already_stopped`.

### Flutter / Frontend Connection Flow

1. Call `POST /session/start` with `sessionId`.
2. Receive JSON with `url`, `room`, `identity`, `token`.
3. In Flutter LiveKit client, connect using returned `url` and `token`.
4. When call/session is finished, call `POST /session/end` with the same `sessionId`.

Fallback endpoint remains available:

- `GET /livekit/token?session=<session_id>`

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
- Token API also exposes `POST /session/start` and `POST /session/end` for worker orchestration.
- Bot worker is isolated from web boot path and only handles LiveKit/Pipecat session logic.
- Worker startup does not use Pipecat runner CLI or WebRTC transport mode.

## Project Structure

```
pipecat_voice_service/
├── main.py              # Pipecat bot runner only
├── app.py               # FastAPI health + token endpoints (Service A)
├── livekit_auth.py      # Shared token helper functions
├── session_manager.py   # Worker process lifecycle manager
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