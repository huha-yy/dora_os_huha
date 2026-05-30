import asyncio
import re
import time
from typing import Optional, Union, Any, List, Dict, Tuple
import numpy as np
import json
from loguru import logger

from ..message_handler import message_handler
from .types import WebSocketSend, BroadcastContext
from .tts_manager import TTSTaskManager
from ..agent.output_types import SentenceOutput, AudioOutput
from ..agent.input_types import BatchInput, TextData, ImageData, TextSource, ImageSource
from ..asr.asr_interface import ASRInterface
from ..live2d_model import Live2dModel
from ..tts.tts_interface import TTSInterface
from ..utils.stream_audio import prepare_audio_payload
from ..service_context import ServiceContext


# Convert class methods to standalone functions
def create_batch_input(
    input_text: str,
    images: Optional[List[Dict[str, Any]]],
    from_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> BatchInput:
    """Create batch input for agent processing"""
    return BatchInput(
        texts=[
            TextData(source=TextSource.INPUT, content=input_text, from_name=from_name)
        ],
        images=[
            ImageData(
                source=ImageSource(img["source"]),
                data=img["data"],
                mime_type=img["mime_type"],
            )
            for img in (images or [])
        ]
        if images
        else None,
        metadata=metadata,
    )


async def process_agent_output(
    output: Union[AudioOutput, SentenceOutput],
    character_config: Any,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
) -> str:
    """Process agent output with character information and optional translation"""
    output.display_text.name = character_config.character_name
    output.display_text.avatar = character_config.avatar

    full_response = ""
    try:
        if isinstance(output, SentenceOutput):
            full_response = await handle_sentence_output(
                output,
                live2d_model,
                tts_engine,
                websocket_send,
                tts_manager,
                translate_engine,
            )
        elif isinstance(output, AudioOutput):
            full_response = await handle_audio_output(output, websocket_send)
        else:
            logger.warning(f"Unknown output type: {type(output)}")
    except Exception as e:
        logger.error(f"Error processing agent output: {e}")
        await websocket_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response


async def handle_sentence_output(
    output: SentenceOutput,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
) -> str:
    """Handle sentence output type with optional translation support"""
    full_response = ""
    async for display_text, tts_text, actions in output:
        logger.debug(f"🏃 Processing output: '''{tts_text}'''...")

        if translate_engine:
            if len(re.sub(r'[\s.,!?，。！？\'"』」）】\s]+', "", tts_text)):
                tts_text = translate_engine.translate(tts_text)
            logger.info(f"🏃 Text after translation: '''{tts_text}'''...")
        else:
            logger.debug("🚫 No translation engine available. Skipping translation.")

        full_response += display_text.text
        await tts_manager.speak(
            tts_text=tts_text,
            display_text=display_text,
            actions=actions,
            live2d_model=live2d_model,
            tts_engine=tts_engine,
            websocket_send=websocket_send,
        )
    return full_response


async def handle_audio_output(
    output: AudioOutput,
    websocket_send: WebSocketSend,
) -> str:
    """Process and send AudioOutput directly to the client"""
    full_response = ""
    async for audio_path, display_text, transcript, actions in output:
        full_response += transcript
        audio_payload = prepare_audio_payload(
            audio_path=audio_path,
            display_text=display_text,
            actions=actions,
        )
        await websocket_send(json.dumps(audio_payload))
    return full_response


async def send_conversation_start_signals(websocket_send: WebSocketSend) -> None:
    """Send initial conversation signals"""
    await websocket_send(
        json.dumps(
            {
                "type": "control",
                "text": "conversation-chain-start",
            }
        )
    )
    await websocket_send(json.dumps({"type": "full-text", "text": "Thinking..."}))


def clean_text_for_matching(text: str) -> str:
    """Remove punctuation and normalize text for fuzzy matching."""
    # Remove common punctuation and spaces
    return re.sub(r'[，。！？、,.!?\s]+', "", text).lower()


async def process_user_input(
    user_input: Union[str, np.ndarray],
    asr_engine: ASRInterface,
    websocket_send: WebSocketSend,
    context: ServiceContext,
) -> Tuple[str, bool, bool]:
    """Process user input, converting audio to text if needed.
    Handles wake-word state logic (sleeping/awake) and timeouts.

    Returns:
        Tuple[str, bool, bool]: (processed_text, just_woke_up_flag, just_slept_flag)
    """
    wake_word = context.system_config.wake_word
    wake_timeout = context.system_config.wake_timeout
    current_time = time.time()
    just_slept = False

    if isinstance(user_input, np.ndarray):
        logger.info("Transcribing audio input...")
        input_text = await asr_engine.async_transcribe_np(user_input)
        await websocket_send(
            json.dumps({"type": "user-input-transcription", "text": input_text})
        )
    else:
        input_text = user_input

    if not input_text:
        return "", False, False

    # Check for timeout if already awake
    if context.is_awake and wake_timeout > 0:
        time_diff = current_time - context.last_activity_time
        logger.debug(f"AI Activity Check: is_awake={context.is_awake}, diff={time_diff:.2f}s, timeout={wake_timeout}s")
        if time_diff > wake_timeout:
            logger.info(
                f"AI timed out after {time_diff:.2f}s of inactivity (last activity at {time.strftime('%H:%M:%S', time.localtime(context.last_activity_time))}). Going to sleep."
            )
            context.is_awake = False
            just_slept = True

    # Normalize texts for comparison
    clean_input = clean_text_for_matching(input_text)
    clean_wake_word = clean_text_for_matching(wake_word) if wake_word else ""

    # If sleeping, look for wake word
    if not context.is_awake:
        if clean_wake_word and clean_wake_word in clean_input:
            logger.info(f"Wake word '{wake_word}' detected! Waking up.")
            context.is_awake = True
            context.update_activity_time()

            # Strip the wake word from the original text for the LLM
            pattern = re.compile(re.escape(wake_word), re.IGNORECASE)
            remaining_text = pattern.sub("", input_text).strip()
            if remaining_text == input_text:
                if clean_input == clean_wake_word:
                    remaining_text = ""

            return remaining_text, True, False
        else:
            if wake_word:
                logger.debug(
                    f"AI is sleeping. Wake word '{wake_word}' not detected in '{input_text}'. Ignoring."
                )
                return "", False, just_slept
            else:
                # If no wake word configured, always awake
                context.is_awake = True
                context.update_activity_time()
                return input_text, False, False

    # If awake, update activity time and return text
    context.update_activity_time()

    # Optional: strip wake word if mentioned while already awake
    pattern = re.compile(re.escape(wake_word), re.IGNORECASE)
    input_text = pattern.sub("", input_text).strip()

    return input_text, False, False


async def finalize_conversation_turn(
    tts_manager: TTSTaskManager,
    websocket_send: WebSocketSend,
    client_uid: str,
    broadcast_ctx: Optional[BroadcastContext] = None,
) -> None:
    """Finalize a conversation turn"""
    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)
        await websocket_send(json.dumps({"type": "backend-synth-complete"}))

        response = await message_handler.wait_for_response(
            client_uid, "frontend-playback-complete"
        )

        if not response:
            logger.warning(f"No playback completion response from {client_uid}")
            return

    await websocket_send(json.dumps({"type": "force-new-message"}))

    if broadcast_ctx and broadcast_ctx.broadcast_func and broadcast_ctx.group_members:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            {"type": "force-new-message"},
            broadcast_ctx.current_client_uid,
        )

    await send_conversation_end_signal(websocket_send, broadcast_ctx)


async def speak_specific_text(
    text: str,
    context: ServiceContext,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
) -> None:
    """Make the agent speak a specific piece of text without querying the LLM."""
    from ..agent.output_types import SentenceOutput, DisplayText, Actions

    mock_output = SentenceOutput(
        display_text=DisplayText(
            text=text,
            name=context.character_config.character_name,
            avatar=context.character_config.avatar,
        ),
        tts_text=text,
        actions=Actions(),
    )

    await handle_sentence_output(
        mock_output,
        context.live2d_model,
        context.tts_engine,
        websocket_send,
        tts_manager,
        context.translate_engine,
    )


async def send_conversation_end_signal(
    websocket_send: WebSocketSend,
    broadcast_ctx: Optional[BroadcastContext],
    session_emoji: str = "😊",
) -> None:
    """Send conversation chain end signal"""
    chain_end_msg = {
        "type": "control",
        "text": "conversation-chain-end",
    }

    await websocket_send(json.dumps(chain_end_msg))

    if broadcast_ctx and broadcast_ctx.broadcast_func and broadcast_ctx.group_members:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            chain_end_msg,
            broadcast_ctx.current_client_uid,
        )

    logger.info(f"😎👍✅ Conversation Chain {session_emoji} completed!")


def cleanup_conversation(tts_manager: TTSTaskManager, session_emoji: str) -> None:
    """Clean up conversation resources"""
    tts_manager.clear()
    logger.debug(f"🧹 Clearing up conversation {session_emoji}.")


EMOJI_LIST = [
    "🐶",
    "🐱",
    "🐭",
    "🐹",
    "🐰",
    "🦊",
    "🐻",
    "🐼",
    "🐨",
    "🐯",
    "🦁",
    "🐮",
    "🐷",
    "🐸",
    "🐵",
    "🐔",
    "🐧",
    "🐦",
    "🐤",
    "🐣",
    "🐥",
    "🦆",
    "🦅",
    "🦉",
    "🦇",
    "🐺",
    "🐗",
    "🐴",
    "🦄",
    "🐝",
    "🌵",
    "🎄",
    "🌲",
    "🌳",
    "🌴",
    "🌱",
    "🌿",
    "☘️",
    "🍀",
    "🍂",
    "🍁",
    "🍄",
    "🌾",
    "💐",
    "🌹",
    "🌸",
    "🌛",
    "🌍",
    "⭐️",
    "🔥",
    "🌈",
    "🌩",
    "⛄️",
    "🎃",
    "🎄",
    "🎉",
    "🎏",
    "🎗",
    "🀄️",
    "🎭",
    "🎨",
    "🧵",
    "🪡",
    "🧶",
    "🥽",
    "🥼",
    "🦺",
    "👔",
    "👕",
    "👜",
    "👑",
]
