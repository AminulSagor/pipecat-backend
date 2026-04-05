import asyncio
import argparse
import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.interruptions.min_words_interruption_strategy import (
    MinWordsInterruptionStrategy,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport

from livekit_auth import build_livekit_token, sanitize_livekit_name

load_dotenv(override=True)


def build_system_instruction() -> str:
    return (
        "You are a warm, natural, human-like voice assistant. "
        "Keep responses short, helpful, and easy to listen to. "
        "Do not use bullet points. "
        "Ask at most one short follow-up question when helpful. "
        "Respond naturally and conversationally. "
        "If the user interrupts, stop and respond to the new input."
    )


def create_livekit_transport(session_id: str) -> LiveKitTransport:
    url = os.getenv("LIVEKIT_URL")
    room_name = sanitize_livekit_name(session_id, "voice-room")
    bot_identity = os.getenv("LIVEKIT_BOT_IDENTITY", "voice-bot")
    bot_token = os.getenv("LIVEKIT_BOT_TOKEN")

    if not url:
        raise RuntimeError("LIVEKIT_URL is required")

    if not session_id.strip():
        raise RuntimeError("session_id is required for bot worker room selection")

    if not bot_token:
        token_ttl_seconds = int(os.getenv("LIVEKIT_BOT_TOKEN_TTL_SECONDS", "3600"))
        bot_token = build_livekit_token(room_name, bot_identity, token_ttl_seconds)

    return LiveKitTransport(
        url=url,
        token=bot_token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )


async def run_bot(transport: BaseTransport):
    logger.info("Starting OpenAI voice bot")

    stt = OpenAISTTService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAISTTService.Settings(
            model="gpt-4o-transcribe",
            language="en",
        ),
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAILLMService.Settings(
            model="gpt-4o-mini",
            system_instruction=build_system_instruction(),
        ),
    )

    tts = OpenAITTSService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAITTSService.Settings(
            model="gpt-4o-mini-tts",
            voice=os.getenv("BOT_VOICE", "marin"),
            instructions=(
                "Speak warmly, naturally, and conversationally. "
                "Use a human-like pace and gentle tone."
            ),
        ),
    )

    context = LLMContext()

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            allow_interruptions=True,
            interruption_strategies=[
                MinWordsInterruptionStrategy(min_words=2),
            ],
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=int(os.getenv("PIPELINE_IDLE_TIMEOUT_SECS", "0")) or None,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")

        context.add_message(
            {
                "role": "developer",
                "content": (
                    "Say hello in one short sentence, introduce yourself briefly, "
                    "and ask one short question about how you can help."
                ),
            }
        )

        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=True)
    await runner.run(task)


async def bot_worker(session_id: str):
    transport = create_livekit_transport(session_id)
    await run_bot(transport)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a LiveKit voice bot worker")
    parser.add_argument("--session-id", dest="session_id", default=None)
    return parser.parse_args()


def resolve_session_id(cli_session_id: str | None) -> str | None:
    value = (cli_session_id or "").strip() or (os.getenv("LIVEKIT_SESSION") or "").strip()
    if not value:
        return None
    return sanitize_livekit_name(value, "voice-room")


if __name__ == "__main__":
    args = parse_args()
    session_id = resolve_session_id(args.session_id)
    if not session_id:
        logger.warning(
            "No session id provided. Worker expects --session-id from session orchestration API; "
            "exiting idle."
        )
        raise SystemExit(0)
    asyncio.run(bot_worker(session_id))