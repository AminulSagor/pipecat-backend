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

4. **Run bot worker directly (optional, local/manual only)**:

   ```bash
   uv run python main.py --session-id my-test-session
   ```

### Session Orchestration API

The API can start and stop a dedicated bot worker per session.

- `GET /session/start`
   - Query params (optional):
      - `identity` (string): caller identity. If omitted, backend generates one.
      - `ttlSeconds` (int, default `900`, min `60`, max `3600`): token TTL.

   - Behavior:
      - Backend generates a new session id (source of truth).
      - Backend sanitizes that value and uses it as both `sessionId` and LiveKit `room`.
      - Starts a worker process with `--session-id <generated-session-id>`.
      - Returns LiveKit details (`url`, `room`, `identity`, `token`) for that same generated room.

   - Example request:

      ```bash
      curl "http://localhost:8080/session/start?identity=mobile-user-123&ttlSeconds=900"
      ```

   - Example response:

      ```json
      {
        "sessionId": "f9db2c39-1f5d-4e27-a868-fb08d0f22722",
        "status": "running",
        "created": true,
        "pid": 48102,
        "startedAt": "2026-04-05T11:20:14.402013+00:00",
        "url": "wss://<project>.livekit.cloud",
        "room": "f9db2c39-1f5d-4e27-a868-fb08d0f22722",
        "identity": "mobile-user-123",
        "token": "<jwt>",
        "ttlSeconds": 900
      }
      ```

   - Notes:
      - `sessionId` and `room` are equivalent for join/stop operations.
      - Each call creates a new backend-generated session.

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

1. Call `GET /session/start` (optionally pass `identity` and `ttlSeconds`).
2. Receive JSON with backend-generated `sessionId`, plus `url`, `room`, `identity`, `token`.
3. Persist the returned `sessionId` on the frontend (local state/store) for session lifecycle actions.
4. In Flutter LiveKit client, connect using returned `url` and `token`.
5. Treat backend response as source of truth: use returned `room` for joins and returned `sessionId` for stop requests.
6. When call/session is finished, call `POST /session/end` with that same returned `sessionId`.

Recommended frontend pseudo-flow:

```text
GET /session/start
   -> store sessionId
   -> connect LiveKit(url, token)
   -> UI/session active
   -> POST /session/end { sessionId }
```

Important integration rule:

- Do not generate room or session ids on the client. The backend-generated `sessionId` is the canonical value.

### Transcript Data Channel Integration (Flutter)

The bot now publishes final transcript messages into the same LiveKit room data channel used by the call session.

- Topic: `transcript.v1`
- Delivery mode: `reliable=true`
- Packet type: small JSON payloads
- Events emitted by backend:
    - final user transcript after VAD ends the user turn (`on_user_turn_stopped`)
    - final assistant transcript when assistant turn ends (`on_assistant_turn_stopped`)

This is intentionally final-only with the current STT stack (`OpenAISTTService`), so user text appears after speech ends, not word-by-word.

#### Transcript payload schema

Each packet on topic `transcript.v1` has this shape:

```json
{
   "type": "transcript",
   "version": 1,
   "role": "user",
   "text": "hello, can you help me book a flight",
   "timestamp": "2026-04-05T11:20:14.402013Z",
   "final": true,
   "sessionId": "f9db2c39-1f5d-4e27-a868-fb08d0f22722"
}
```

Field notes:

- `role`: `user` or `assistant`
- `final`: always `true` in current implementation
- `sessionId`: backend-resolved worker session id (same value returned by `/session/start`)

#### Flutter handling steps

1. Call `GET /session/start` and store returned `sessionId`.
2. Connect to LiveKit using returned `url` and `token`.
3. Subscribe to room data messages.
4. Filter for topic `transcript.v1`.
5. Parse JSON and ignore packets where `type != transcript` or `version != 1`.
6. Optionally ignore packets whose `sessionId` does not match local active session.
7. Render `role=user` as user bubble and `role=assistant` as assistant bubble.

#### Flutter example (Dart)

```dart
import 'dart:convert';

import 'package:livekit_client/livekit_client.dart';

class TranscriptMessage {
   final String type;
   final int version;
   final String role;
   final String text;
   final String timestamp;
   final bool finalFlag;
   final String sessionId;

   TranscriptMessage({
      required this.type,
      required this.version,
      required this.role,
      required this.text,
      required this.timestamp,
      required this.finalFlag,
      required this.sessionId,
   });

   static TranscriptMessage? fromJson(Map<String, dynamic> json) {
      if (json['type'] != 'transcript') return null;
      if (json['version'] != 1) return null;
      final role = json['role'];
      final text = json['text'];
      final timestamp = json['timestamp'];
      final finalFlag = json['final'];
      final sessionId = json['sessionId'];
      if (role is! String || text is! String || timestamp is! String || finalFlag is! bool || sessionId is! String) {
         return null;
      }
      return TranscriptMessage(
         type: 'transcript',
         version: 1,
         role: role,
         text: text,
         timestamp: timestamp,
         finalFlag: finalFlag,
         sessionId: sessionId,
      );
   }
}

void attachTranscriptListener(Room room, String activeSessionId, void Function(TranscriptMessage msg) onTranscript) {
   room.events.listen((event) {
      if (event is! DataReceivedEvent) return;
      if (event.topic != 'transcript.v1') return;

      final raw = utf8.decode(event.data);
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return;

      final message = TranscriptMessage.fromJson(decoded);
      if (message == null) return;
      if (message.sessionId != activeSessionId) return;

      onTranscript(message);
   });
}
```

#### UI recommendations

- Keep transcript state ordered by receive time; `reliable=true` provides ordered delivery per sender.
- Show role-based styling (`user` vs `assistant`).
- Do not wait for `final=false` updates; current backend emits final packets only.
- If the assistant is interrupted, still handle the final assistant packet for that partial completion.

#### Backend permission requirement

Token grants include `can_publish_data=true` so bot and clients can publish/receive data packets in the room.
If you mint tokens outside this service, make sure that grant is also enabled.

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

- Orchestration mode uses one web service that spawns per-session workers on demand:
   - Web service command: `uv run uvicorn app:app --host 0.0.0.0 --port $PORT`
- Do not run `uv run python main.py` as an always-on background service unless you pass a fixed `--session-id`.
- Token API starts fast and exposes `GET /health` and `GET /livekit/token`.
- Token API also exposes `GET /session/start` and `POST /session/end` for worker orchestration.
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