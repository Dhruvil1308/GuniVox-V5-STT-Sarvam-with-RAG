import os
import asyncio
from typing import Optional

from pipecat.frames.frames import EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregator, LLMUserAggregator
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport, FastAPIWebsocketParams
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

async def run_unmute_pipeline(websocket):
    """
    Implements a real-time voice-to-voice pipeline inspired by Unmute/Kyutai
    using Pipecat and Sarvam AI.
    """
    
    # 1. Initialize Transport (WebSocket for real-time audio)
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            vad_enabled=True,
            vad_analyzer=None, # Use default VAD
        )
    )

    # 2. Initialize Services
    # Unmute-style low latency using Sarvam's specialized Indian language models
    stt = SarvamSTTService(
        api_key=os.getenv("SARVAM_API_KEY"),
        model="saaras:v3"
    )
    
    tts = SarvamTTSService(
        api_key=os.getenv("SARVAM_API_KEY"),
        voice="anushka",
        model="bulbul:v2",
        language="gu-IN"
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini"
    )

    # 3. Context & Aggregators
    context = LLMContext()
    user_aggregator = LLMUserAggregator(context)
    assistant_aggregator = LLMAssistantAggregator(context)

    # 4. Pipeline Setup
    # This architecture follows the Unmute/Kyutai cascaded approach:
    # [Audio In] -> [STT] -> [LLM] -> [TTS] -> [Audio Out]
    pipeline = Pipeline([
        transport.input(),              # Real-time audio input
        stt,                            # STT (Streaming transcription)
        user_aggregator,                # Aggregates user speech for LLM
        llm,                            # LLM (Streaming tokens)
        tts,                            # TTS (Streaming audio generation)
        transport.output(),             # Real-time audio output
        assistant_aggregator            # Aggregates assistant response for session history
    ])

    task = PipelineTask(pipeline)

    # 4. Run the pipeline
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    # Example standalone runner (would be called from server.py)
    print("Unmute-style pipeline ready.")
