from collections import deque
from enum import Enum
import json
import os
from typing import Callable, Deque, Dict, List, Optional, TypedDict

from fastapi import WebSocket, WebSocketDisconnect
from service_context import ServiceContext
from loguru import logger
import numpy as np
from response_awaiter import response_awaiter


FALLBACK_REPLY = "抱歉,我现在没法回答你的问题,请稍后再试。"


class WSMessage(TypedDict, total=False):
    """Type definition for WebSocket messages"""

    type: str
    action: Optional[str]
    text: Optional[str]
    audio: Optional[List[float]]
    images: Optional[List[str]]
    history_uid: Optional[str]
    file: Optional[str]
    display_text: Optional[dict]


class WebSocketHandler:
    """Handles WebSocket connections and message routing"""

    def __init__(self):
        self.client_connections: Dict[str, WebSocket] = {}
        self.client_contexts: Dict[str, ServiceContext] = {}
        self.received_data_buffers: Dict[str, np.ndarray] = {}
        self.client_histories: Dict[str, Deque[dict]] = {}
        self.message_handlers: Dict[str, Callable] = self._init_message_handlers()

    def _history_for(self, client_uid: str, context: ServiceContext) -> Deque[dict]:
        """Return (creating if needed) the conversation history for a client.

        Capped at `max_history_turns` user/assistant turns (so 2x messages).
        """
        hist = self.client_histories.get(client_uid)
        if hist is None:
            max_msgs = max(2, 2 * getattr(context, "max_history_turns", 8))
            hist = deque(maxlen=max_msgs)
            self.client_histories[client_uid] = hist
        return hist

    async def _generate_reply(
        self, context: ServiceContext, client_uid: str, user_text: str
    ) -> str:
        """Run the LLM (with system prompt + per-client history) and return text."""
        history = self._history_for(client_uid, context)
        if context.llm_engine is None:
            logger.warning("LLM engine not configured; returning fallback reply")
            return FALLBACK_REPLY

        messages = context.llm_engine.build_messages(
            user_text=user_text,
            history=list(history),
            system_prompt=context.system_prompt or None,
        )
        reply = await context.llm_engine.async_chat(messages)
        if not reply:
            return FALLBACK_REPLY

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        return reply

    def _init_message_handlers(self) -> Dict[str, Callable]:
        """Initialize message type to handler mapping"""
        return {
            "interrupt-signal": self._handle_interrupt,
            "mic-audio-data": self._handle_audio_data,
            "mic-audio-end": self._handle_conversation_trigger,
            "raw-audio-data": self._handle_raw_audio_data,
            "text-input": self._handle_conversation_trigger,
            "ai-speak-signal": self._handle_conversation_trigger,
            "fetch-configs": self._handle_fetch_configs,
            "switch-config": self._handle_config_switch,
            "heartbeat": self._handle_heartbeat,
        }

    async def handle_new_connection(
        self, websocket: WebSocket, client_uid: str
    ) -> None:
        """
        Handle new WebSocket connection setup

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client

        Raises:
            Exception: If initialization fails
        """
        try:
            session_service_context = await self._init_service_context(
                websocket.send_text, client_uid
            )

            await self._store_client_data(
                websocket, client_uid, session_service_context
            )

            await self._send_initial_messages(
                websocket, client_uid, session_service_context
            )

            logger.info(f"Connection established for client {client_uid}")

        except Exception as e:
            logger.error(
                f"Failed to initialize connection for client {client_uid}: {e}"
            )
            await self._cleanup_failed_connection(client_uid)
            raise

    async def _init_service_context(
        self, send_text: Callable, client_uid: str
    ) -> ServiceContext:
        """Initialize service context for a new session"""
        # Import here to avoid circular imports
        from service_context import default_service_context
        # Use the pre-initialized global service context
        # Each client shares the same ASR/TTS engines for efficiency
        return default_service_context

    async def handle_websocket_communication(
        self, websocket: WebSocket, client_uid: str
    ) -> None:
        """
        Handle ongoing WebSocket communication

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client
        """
        try:
            while True:
                try:
                    data = await websocket.receive_json()
                    response_awaiter.handle_message(client_uid, data)
                    await self._route_message(websocket, client_uid, data)
                except WebSocketDisconnect:
                    raise
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e)})
                    )
                    continue

        except WebSocketDisconnect:
            logger.info(f"Client {client_uid} disconnected")
            raise
        except Exception as e:
            logger.error(f"Fatal error in WebSocket communication: {e}")
            raise

    async def handle_disconnect(self, client_uid: str) -> None:
        """Handle WebSocket disconnection"""
        self.client_connections.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        self.client_histories.pop(client_uid, None)

        logger.info(f"Client {client_uid} disconnected")
        response_awaiter.cleanup_client(client_uid)

    async def _cleanup_failed_connection(self, client_uid: str) -> None:
        """Clean up resources after a failed connection attempt"""
        self.client_connections.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        self.client_histories.pop(client_uid, None)
        response_awaiter.cleanup_client(client_uid)

    async def _route_message(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """
        Route incoming message to appropriate handler

        Args:
            websocket: The WebSocket connection
            client_uid: Client identifier
            data: Message data
        """
        msg_type = data.get("type")
        if not msg_type:
            logger.warning("Message received without type")
            return

        handler = self.message_handlers.get(msg_type)
        if handler:
            await handler(websocket, client_uid, data)
        else:
            if msg_type != "frontend-playback-complete":
                logger.warning(f"Unknown message type: {msg_type}")

    async def _send_initial_messages(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
    ):
        """Send initial connection messages to the client"""
        await websocket.send_text(
            json.dumps({"type": "full-text", "text": "Connection established"})
        )

        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "client_uid": client_uid,
                    "asr_engine": type(session_service_context.asr_engine).__name__ if session_service_context.asr_engine else None,
                    "tts_engine": type(session_service_context.tts_engine).__name__ if session_service_context.tts_engine else None,
                }
            )
        )

    async def _store_client_data(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
    ):
        """Store client data"""
        self.client_connections[client_uid] = websocket
        self.client_contexts[client_uid] = session_service_context
        self.received_data_buffers[client_uid] = np.array([])

    async def _handle_interrupt(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle conversation interruption"""
        heard_response = data.get("text", "")
        context = self.client_contexts[client_uid]
        # TODO: Handle conversation interruption later

    async def _handle_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming audio data"""
        audio_data = data.get("audio", [])
        if audio_data:
            self.received_data_buffers[client_uid] = np.append(
                self.received_data_buffers[client_uid],
                np.array(audio_data, dtype=np.float32),
            )

    async def _handle_raw_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming raw audio data for VAD processing"""
        context = self.client_contexts.get(client_uid)
        if not context:
            return
            
        chunk = data.get("audio", [])
        if not chunk:
            return
            
        # If VAD is available, use it for speech detection
        if context.vad_engine:
            for audio_bytes in context.vad_engine.detect_speech(chunk):
                if audio_bytes == b"<|PAUSE|>":
                    await websocket.send_text(
                        json.dumps({"type": "control", "text": "vad-pause"})
                    )
                elif audio_bytes == b"<|RESUME|>":
                    await websocket.send_text(
                        json.dumps({"type": "control", "text": "vad-resume"})
                    )
                elif len(audio_bytes) > 1024:
                    # VAD detected speech end - convert and store audio
                    audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    self.received_data_buffers[client_uid] = audio_float
                    
                    # Notify frontend that we detected speech
                    await websocket.send_text(
                        json.dumps({"type": "control", "text": "speech-detected"})
                    )
                    
                    # Process the detected speech immediately
                    await self._process_speech(websocket, client_uid, context)
        else:
            # No VAD - just accumulate audio
            self.received_data_buffers[client_uid] = np.append(
                self.received_data_buffers[client_uid],
                np.array(chunk, dtype=np.float32),
            )
    
    async def _process_speech(self, websocket: WebSocket, client_uid: str, context) -> None:
        """Process detected speech - transcribe and respond"""
        audio_buffer = self.received_data_buffers.get(client_uid)
        
        if audio_buffer is None or len(audio_buffer) == 0:
            return
        
        logger.info(f"Processing speech from {client_uid}, length: {len(audio_buffer)}")
        
        # Transcribe
        if context.asr_engine:
            try:
                text = await context.asr_engine.async_transcribe_np(audio_buffer)
                logger.info(f"Transcribed: {text}")
                
                if text and text.strip():
                    user_text = text.strip()
                    await websocket.send_json({
                        "type": "user-transcription",
                        "text": user_text,
                    })

                    robot_response = await self._generate_reply(
                        context, client_uid, user_text
                    )

                    audio_url = None
                    if context.tts_engine:
                        try:
                            audio_path = context.tts_engine.generate_audio(robot_response)
                            logger.info(f"Generated TTS audio: {audio_path}")
                            if audio_path:
                                audio_filename = os.path.basename(audio_path)
                                audio_url = f"/cache/{audio_filename}"
                        except Exception as e:
                            logger.error(f"TTS error: {e}")

                    await websocket.send_json({
                        "type": "robot-response",
                        "text": robot_response,
                        "audio": audio_url,
                    })
                    
            except Exception as e:
                logger.error(f"ASR error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"ASR error: {str(e)}"
                })
        
        # Clear the buffer
        self.received_data_buffers[client_uid] = np.array([])

    async def _handle_conversation_trigger(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle triggers that start a conversation"""
        msg_type = data.get("type", "")
        context = self.client_contexts.get(client_uid)
        
        if msg_type == "text-input":
            text = (data.get("text") or "").strip()
            if not text:
                return
            logger.info(f"Received text from {client_uid}: {text}")

            response = await self._generate_reply(context, client_uid, text)

            audio_url = None
            if context and context.tts_engine:
                try:
                    audio_path = context.tts_engine.generate_audio(response)
                    if audio_path:
                        audio_filename = os.path.basename(audio_path)
                        audio_url = f"/cache/{audio_filename}"
                except Exception as e:
                    logger.error(f"TTS error: {e}")

            await websocket.send_json({
                "type": "robot-response",
                "text": response,
                "audio": audio_url,
            })
                
        elif msg_type == "mic-audio-end":
            # Handle end of audio recording
            # Audio can come with the message or from the buffer
            audio_data = data.get("audio", [])
            if audio_data:
                # Audio sent with the end signal
                audio_buffer = np.array(audio_data, dtype=np.float32)
            else:
                # Audio was streamed earlier
                audio_buffer = self.received_data_buffers.get(client_uid)
            
            if audio_buffer is not None and len(audio_buffer) > 0:
                logger.info(f"Received audio from {client_uid}, length: {len(audio_buffer)}")

                if context and context.asr_engine:
                    try:
                        text = await context.asr_engine.async_transcribe_np(audio_buffer)
                        logger.info(f"Transcribed: {text}")

                        await websocket.send_json({
                            "type": "user-transcription",
                            "text": text,
                        })

                        user_text = (text or "").strip()
                        if user_text:
                            robot_response = await self._generate_reply(
                                context, client_uid, user_text
                            )
                        else:
                            robot_response = FALLBACK_REPLY

                        audio_url = None
                        if context and context.tts_engine:
                            try:
                                audio_path = context.tts_engine.generate_audio(robot_response)
                                logger.info(f"Generated TTS audio: {audio_path}")
                                if audio_path:
                                    audio_filename = os.path.basename(audio_path)
                                    audio_url = f"/cache/{audio_filename}"
                            except Exception as e:
                                logger.error(f"TTS error: {e}")

                        await websocket.send_json({
                            "type": "robot-response",
                            "text": robot_response,
                            "audio": audio_url,
                        })

                    except Exception as e:
                        logger.error(f"ASR error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"ASR error: {str(e)}",
                        })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "ASR not configured.",
                    })

                self.received_data_buffers[client_uid] = np.array([])
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "No audio data received."
                })
                
        elif msg_type == "ai-speak-signal":
            # Handle AI speak signal (proactive speaking)
            logger.info(f"AI speak signal from {client_uid}")
            await websocket.send_json({
                "type": "text-response",
                "text": "AI speak triggered. (Not implemented yet)"
            })

    async def _handle_fetch_configs(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle fetching available configurations"""
        # TODO: Handle fetching available configurations later

    async def _handle_config_switch(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle switching to a different configuration"""
        # TODO: Handle switching to a different configuration later

    async def _handle_heartbeat(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle heartbeat messages from clients"""
        try:
            await websocket.send_json({"type": "heartbeat-ack"})
        except Exception as e:
            logger.error(f"Error sending heartbeat acknowledgment: {e}")
