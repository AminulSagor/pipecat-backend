import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SessionProcess:
    session_id: str
    process: subprocess.Popen
    started_at: datetime


class SessionManager:
    def __init__(self, worker_script: str = "main.py"):
        self._worker_script = str(Path(__file__).resolve().parent / worker_script)
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionProcess] = {}

    def _is_alive(self, process: subprocess.Popen) -> bool:
        return process.poll() is None

    def _cleanup_stale_sessions_locked(self) -> None:
        stale = [key for key, value in self._sessions.items() if not self._is_alive(value.process)]
        for key in stale:
            del self._sessions[key]

    def start_session(self, session_id: str) -> dict[str, object]:
        with self._lock:
            self._cleanup_stale_sessions_locked()
            existing = self._sessions.get(session_id)
            if existing and self._is_alive(existing.process):
                return {
                    "session_id": session_id,
                    "pid": existing.process.pid,
                    "started_at": existing.started_at.isoformat(),
                    "status": "running",
                    "created": False,
                }

            process = subprocess.Popen(
                [sys.executable, "-u", self._worker_script, "--session-id", session_id],
            )
            current = SessionProcess(
                session_id=session_id,
                process=process,
                started_at=datetime.now(UTC),
            )
            self._sessions[session_id] = current
            return {
                "session_id": session_id,
                "pid": process.pid,
                "started_at": current.started_at.isoformat(),
                "status": "running",
                "created": True,
            }

    def end_session(self, session_id: str, timeout_seconds: float = 10.0) -> dict[str, object]:
        with self._lock:
            self._cleanup_stale_sessions_locked()
            current = self._sessions.get(session_id)
            if not current:
                return {
                    "session_id": session_id,
                    "status": "already_stopped",
                    "stopped": False,
                }

            process = current.process
            if self._is_alive(process):
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3.0)

            del self._sessions[session_id]
            return {
                "session_id": session_id,
                "status": "stopped",
                "stopped": True,
            }

    def stop_all_sessions(self, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            session_ids = list(self._sessions.keys())

        for session_id in session_ids:
            self.end_session(session_id, timeout_seconds=timeout_seconds)
