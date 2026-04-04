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

3. **Run the bot**:

   ```bash
   uv run main.py -t livekit
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

- The app must listen on `0.0.0.0:$PORT` in Railway.
- `main.py` auto-uses `HOST` (default `0.0.0.0`) and `PORT` (default `7860`) when starting.
- For Pipecat versions that expose the FastAPI app object, `main.py` registers `GET /health` and `GET /livekit/token`.

## Project Structure

```
pipecat_voice_service/
├── main.py              # Main bot + endpoint registration
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