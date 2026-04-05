import os
import sys

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
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.livekit.transport import LiveKitParams

load_dotenv(override=True)

transport_params = {
    "livekit": lambda: LiveKitParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


def build_system_instruction() -> str:
    return (
        "You are a warm, natural, human-like voice assistant. "
        "Keep responses short, helpful, and easy to listen to. "
        "Do not use bullet points. "
        "Ask at most one short follow-up question when helpful. "
        "Respond naturally and conversationally. "
        "If the user interrupts, stop and respond to the new input."
    )


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
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
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
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

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


def ensure_cli_arg(flag: str, value: str):
    if flag not in sys.argv:
        sys.argv.extend([flag, value])


if __name__ == "__main__":
    from pipecat.runner.run import main

    host = "0.0.0.0"
    port = os.getenv("PORT", "8080")

    print("======== Railway boot debug ========")
    print(f"ENV PORT        : {os.getenv('PORT')}")
    print(f"Resolved host   : {host}")
    print(f"Resolved port   : {port}")
    print(f"Initial argv    : {sys.argv}")
    print("====================================")

    ensure_cli_arg("--host", host)
    ensure_cli_arg("--port", str(port))
    # ensure_cli_arg("-t", "webrtc")

    print(f"Final argv      : {sys.argv}")
    print("Starting Pipecat...")
    main()