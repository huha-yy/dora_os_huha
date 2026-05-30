from typing import Any, Dict, List, Optional, Union, Tuple
import asyncio
import json
from loguru import logger
from fastapi import WebSocket
import numpy as np

from ..agent.output_types import AudioOutput, SentenceOutput, DisplayText, Actions

from .conversation_utils import (
    create_batch_input,
    process_agent_output,
    process_user_input,
    finalize_conversation_turn,
    cleanup_conversation,
    handle_sentence_output,
    EMOJI_LIST,
)
from .types import (
    BroadcastFunc,
    GroupConversationState,
    BroadcastContext,
    WebSocketSend,
)
from ..service_context import ServiceContext
from ..chat_history_manager import store_message
from .tts_manager import TTSTaskManager


async def process_group_conversation(
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
    user_input: Union[str, np.ndarray],
    images: Optional[List[Dict[str, Any]]] = None,
    session_emoji: str = np.random.choice(EMOJI_LIST),
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Process group conversation

    Args:
        client_contexts: Dictionary of client contexts
        client_connections: Dictionary of client WebSocket connections
        broadcast_func: Function to broadcast messages to group
        group_members: List of group member UIDs
        initiator_client_uid: UID of conversation initiator
        user_input: Text or audio input from user
        images: Optional list of image data
        session_emoji: Emoji identifier for the conversation
        metadata: Optional metadata for special processing flags
    """
    # Create TTSTaskManager for each member
    tts_managers = {uid: TTSTaskManager() for uid in group_members}

    try:
        logger.info(f"Group Conversation Chain {session_emoji} started!")

        # Initialize state with group_id
        state = GroupConversationState(
            group_id=f"group_{initiator_client_uid}",  # Use same format as chat_group
            session_emoji=session_emoji,
            group_queue=list(group_members),
            memory_index={
                uid: 0 for uid in group_members
            },  # Initialize memory index for each member
        )

        # Initialize group conversation context for each AI
        init_group_conversation_contexts(client_contexts)

        # Get initiator context
        initiator_context = client_contexts.get(initiator_client_uid)

        # Get human name from initiator context
        if initiator_context:
            human_name = initiator_context.character_config.human_name
        else:
            human_name = "Human"

        # Process initial input
        input_text, just_woke_up, just_slept = await process_group_input(
            user_input=user_input,
            initiator_context=initiator_context,
            initiator_ws_send=client_connections[initiator_client_uid].send_text,
            broadcast_func=broadcast_func,
            group_members=group_members,
            initiator_client_uid=initiator_client_uid,
        )

        if just_slept and initiator_context:
            # Handle group sleep response
            sleep_response = initiator_context.system_config.sleep_response
            logger.info(f"Group AI going to sleep with response: {sleep_response}")

            initiator_ws_send = client_connections[initiator_client_uid].send_text

            from .conversation_utils import speak_specific_text

            await speak_specific_text(
                text=sleep_response,
                context=initiator_context,
                websocket_send=initiator_ws_send,
                tts_manager=tts_managers[initiator_client_uid],
            )

        if just_woke_up and initiator_context:
            # Wake up all members in the group
            for member_uid in group_members:
                client_contexts[member_uid].is_awake = True
                client_contexts[member_uid].update_activity_time()

            # Handle direct wake-up response
            wake_response = initiator_context.system_config.wake_response
            logger.info(f"Group AI Waking up with response: {wake_response}")
            initiator_context.update_activity_time()

            # Use initiator's TTS to say the wake response
            initiator_ws_send = client_connections[initiator_client_uid].send_text

            from .conversation_utils import speak_specific_text

            await speak_specific_text(
                text=wake_response,
                context=initiator_context,
                websocket_send=initiator_ws_send,
                tts_manager=tts_managers[initiator_client_uid],
            )

            # If there's no command after the wake word, we end the turn here
            if not input_text:
                await finalize_conversation_turn(
                    tts_manager=tts_managers[initiator_client_uid],
                    websocket_send=initiator_ws_send,
                    client_uid=initiator_client_uid,
                )
                initiator_context.update_activity_time()
                return
            
            # If there IS a command, we continue to the LLM part
            logger.info(f"Continuing with group command after wake word: {input_text}")

        if not input_text:
            logger.info("Empty input after processing (possibly wake word not detected). Ending turn.")
            GroupConversationState.remove_state(state.group_id)
            return

        # Check if we should skip storing this input to history
        skip_history = metadata and metadata.get("skip_history", False)

        if not skip_history:
            for member_uid in group_members:
                member_context = client_contexts[member_uid]
                store_message(
                    conf_uid=member_context.character_config.conf_uid,
                    history_uid=member_context.history_uid,
                    role="human",
                    content=input_text,
                    name=human_name,
                )
        else:
            logger.debug("Skipping storing proactive speak input to group history")

        state.conversation_history = [f"{human_name}: {input_text}"]

        is_first_responder = False
        # Main conversation loop
        while state.group_queue:
            try:
                current_member_uid = state.group_queue.pop(0)

                # Only pass metadata to the first responder
                current_metadata = None
                if is_first_responder:
                    current_metadata = metadata
                    is_first_responder = False

                await handle_group_member_turn(
                    current_member_uid=current_member_uid,
                    state=state,
                    client_contexts=client_contexts,
                    client_connections=client_connections,
                    broadcast_func=broadcast_func,
                    group_members=group_members,
                    images=images,
                    tts_manager=tts_managers[current_member_uid],
                    metadata=current_metadata,
                )
            except Exception as e:
                logger.error(f"Error in group member turn: {e}")
                await handle_member_error(
                    broadcast_func, group_members, f"Error in conversation: {str(e)}"
                )

    except asyncio.CancelledError:
        logger.info(
            f"🤡👍 Group Conversation {session_emoji} cancelled because interrupted."
        )
        raise
    except Exception as e:
        logger.error(f"Error in group conversation chain: {e}")
        await handle_member_error(
            broadcast_func, group_members, f"Fatal error in conversation: {str(e)}"
        )
        raise
    finally:
        # Cleanup all TTS managers
        for tts_manager in tts_managers.values():
            cleanup_conversation(tts_manager, session_emoji)
        # Clean up
        if 'state' in locals():
            GroupConversationState.remove_state(state.group_id)


def init_group_conversation_state(
    group_id: str, group_members: List[str], session_emoji: str
) -> GroupConversationState:
    """Initialize group conversation state"""
    return GroupConversationState(
        group_id=group_id,
        conversation_history=[],
        memory_index={uid: 0 for uid in group_members},
        group_queue=list(group_members),
        session_emoji=session_emoji,
    )


def init_group_conversation_contexts(
    client_contexts: Dict[str, ServiceContext],
) -> None:
    """Initialize group conversation context for each AI participant"""
    ai_names = [ctx.character_config.character_name for ctx in client_contexts.values()]

    for context in client_contexts.values():
        agent = context.agent_engine
        # Use getattr to avoid linter error if start_group_conversation is dynamic
        start_func = getattr(agent, "start_group_conversation", None)
        if start_func:
            start_func(
                human_name="Human",
                ai_participants=[
                    name
                    for name in ai_names
                    if name != context.character_config.character_name
                ],
            )
            logger.debug(
                f"Initialized group conversation context for "
                f"{context.character_config.character_name}"
            )


async def process_group_input(
    user_input: Union[str, np.ndarray],
    initiator_context: Optional[ServiceContext],
    initiator_ws_send: WebSocketSend,
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
) -> Tuple[str, bool, bool]:
    """Process and broadcast user input to group"""
    if initiator_context:
        input_text, just_woke_up, just_slept = await process_user_input(
            user_input, 
            initiator_context.asr_engine, 
            initiator_ws_send,
            context=initiator_context
        )
    else:
        # Fallback if context is missing (unlikely but for safety)
        input_text = str(user_input) if isinstance(user_input, str) else ""
        just_woke_up = False
        just_slept = False

    if input_text:
        await broadcast_transcription(
            broadcast_func, group_members, input_text, initiator_client_uid
        )
    return input_text, just_woke_up, just_slept


async def broadcast_transcription(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    text: str,
    exclude_uid: str,
) -> None:
    """Broadcast transcription to group members"""
    await broadcast_func(
        group_members,
        {
            "type": "user-input-transcription",
            "text": text,
        },
        exclude_uid,
    )


async def handle_group_member_turn(
    current_member_uid: str,
    state: GroupConversationState,
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    images: Optional[List[Dict[str, Any]]],
    tts_manager: TTSTaskManager,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Handle a single group member's conversation turn"""
    # Update current speaker before processing
    state.current_speaker_uid = current_member_uid

    await broadcast_thinking_state(broadcast_func, group_members)

    context = client_contexts[current_member_uid]
    current_ws_send = client_connections[current_member_uid].send_text

    new_messages = state.conversation_history[state.memory_index[current_member_uid] :]
    new_context = "\n".join(new_messages) if new_messages else ""

    batch_input = create_batch_input(
        input_text=new_context,
        images=images,
        from_name="Human",
        metadata=metadata,
    )

    logger.info(
        f"AI {context.character_config.character_name} "
        f"(client {current_member_uid}) receiving context:\n{new_context}"
    )

    context.update_activity_time()
    full_response = await process_member_response(
        context=context,
        batch_input=batch_input,
        current_ws_send=current_ws_send,
        tts_manager=tts_manager,
        broadcast_func=broadcast_func,
        group_members=group_members,
    )

    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)
        await current_ws_send(json.dumps({"type": "backend-synth-complete"}))

        broadcast_ctx = BroadcastContext(
            broadcast_func=broadcast_func,
            group_members=group_members,
            current_client_uid=current_member_uid,
        )

        await finalize_conversation_turn(
            tts_manager=tts_manager,
            websocket_send=current_ws_send,
            client_uid=current_member_uid,
            broadcast_ctx=broadcast_ctx,
        )
        context.update_activity_time()

    if full_response:
        ai_message = f"{context.character_config.character_name}: {full_response}"
        state.conversation_history.append(ai_message)
        logger.info(f"Appended complete response: {ai_message}")

        # Check if we should skip storing this response to history
        skip_history = metadata and metadata.get("skip_history", False)

        if not skip_history:
            for member_uid in group_members:
                member_context = client_contexts[member_uid]
                store_message(
                    conf_uid=member_context.character_config.conf_uid,
                    history_uid=member_context.history_uid,
                    role="ai",
                    content=full_response,
                    name=context.character_config.character_name,
                    avatar=context.character_config.avatar,
                )
        else:
            logger.debug("Skipping storing AI response to history (proactive speak)")

    state.memory_index[current_member_uid] = len(state.conversation_history)
    state.group_queue.append(current_member_uid)

    # Clear speaker after turn completes
    state.current_speaker_uid = None


async def broadcast_thinking_state(
    broadcast_func: BroadcastFunc, group_members: List[str]
) -> None:
    """Broadcast thinking state to group"""
    await broadcast_func(
        group_members,
        {"type": "control", "text": "conversation-chain-start"},
        None,
    )
    await broadcast_func(
        group_members,
        {"type": "full-text", "text": "Thinking..."},
        None,
    )


async def handle_member_error(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    error_message: str,
) -> None:
    """Handle and broadcast member error"""
    await broadcast_func(
        group_members,
        {
            "type": "error",
            "message": error_message,
        },
        None,
    )


async def process_member_response(
    context: ServiceContext,
    batch_input: Any,
    current_ws_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    broadcast_func: Optional[BroadcastFunc] = None,
    group_members: Optional[List[str]] = None,
) -> str:
    """Process group member's response, handling text/audio and tool status events."""
    full_response = ""

    try:
        # agent.chat now yields Union[SentenceOutput, Dict[str, Any]]
        agent_output_stream = context.agent_engine.chat(batch_input)

        async for output_item in agent_output_stream:
            if (
                isinstance(output_item, dict)
                and output_item.get("type") == "tool_call_status"
            ):
                if broadcast_func and group_members:
                    logger.debug(f"Broadcasting tool status update: {output_item}")
                    output_item["name"] = context.character_config.character_name
                    await broadcast_func(group_members, output_item, None)
                else:
                    logger.warning(
                        "Cannot broadcast tool status: broadcast_func or group_members missing."
                    )
            elif isinstance(output_item, (SentenceOutput, AudioOutput)):
                # Handle SentenceOutput or AudioOutput: Send to current user, broadcast audio later if needed
                context.update_activity_time()
                response_part = await process_agent_output(
                    output=output_item,
                    character_config=context.character_config,
                    live2d_model=context.live2d_model,
                    tts_engine=context.tts_engine,
                    websocket_send=current_ws_send,  # Send TTS/display text directly to speaker's client
                    tts_manager=tts_manager,
                    translate_engine=context.translate_engine,
                )
                full_response += response_part  # Accumulate text response
            else:
                logger.warning(
                    f"Received unexpected item type from agent chat stream: {type(output_item)}"
                )

    except Exception as e:
        logger.exception(f"Error processing group member response stream: {e}")
        await current_ws_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response
