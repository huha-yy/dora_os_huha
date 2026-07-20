/**
 * Chatbot Demo Frontend
 * Connects to WebSocket server and handles chat interactions
 */

class ChatbotClient {
    constructor() {
        this.ws = null;
        this.clientUid = null;
        this.isRecording = false;
        this.isMicActive = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioBuffer = [];
        this.lastUserAudioMessage = null;
        this.silenceStart = null;
        this.heartbeatInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.embedMode = new URLSearchParams(window.location.search).get('embed') === '1';
        if (this.embedMode) {
            document.body.classList.add('embed');
        }

        // DOM Elements
        this.elements = {
            connectionStatus: document.getElementById('connection-status'),
            statusText: document.querySelector('.status-text'),
            messages: document.getElementById('messages'),
            textInput: document.getElementById('text-input'),
            sendBtn: document.getElementById('send-btn'),
            micBtn: document.getElementById('mic-btn'),
            interruptBtn: document.getElementById('interrupt-btn'),
            debugToggleBtn: document.getElementById('debug-toggle-btn'),
            debugPanel: document.getElementById('debug-panel'),
            debugLog: document.getElementById('debug-log'),
            clearDebug: document.getElementById('clear-debug'),
            audioPlayer: document.getElementById('audio-player'),
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.connect();
    }

    bindEvents() {
        // Send button
        this.elements.sendBtn.addEventListener('click', () => this.sendTextMessage());

        // Enter key to send
        this.elements.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendTextMessage();
            }
        });

        // Microphone button (toggle mute/unmute)
        this.elements.micBtn.addEventListener('click', () => this.toggleMicrophone());

        // Interrupt button
        this.elements.interruptBtn.addEventListener('click', () => this.sendInterrupt());

        // Debug log toggle
        this.elements.debugToggleBtn.addEventListener('click', () => this.toggleDebugPanel());

        // Clear debug log
        this.elements.clearDebug.addEventListener('click', () => {
            this.elements.debugLog.innerHTML = '';
        });
    }

    toggleDebugPanel() {
        const panel = this.elements.debugPanel;
        const open = panel.hasAttribute('hidden');
        if (open) {
            panel.removeAttribute('hidden');
            this.elements.debugToggleBtn.classList.add('active');
        } else {
            panel.setAttribute('hidden', '');
            this.elements.debugToggleBtn.classList.remove('active');
        }
    }

    notifyParentConnection(connected) {
        if (window.parent === window) {
            return;
        }
        window.parent.postMessage(
            { source: 'dorabot-chatbot', type: 'connection', connected },
            '*',
        );
    }

    // ==================== WebSocket Connection ====================

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.log('send', `Connecting to ${wsUrl}...`);

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => this.onOpen();
            this.ws.onmessage = (event) => this.onMessage(event);
            this.ws.onclose = (event) => this.onClose(event);
            this.ws.onerror = (error) => this.onError(error);
        } catch (error) {
            this.log('error', `Failed to create WebSocket: ${error.message}`);
        }
    }

    onOpen() {
        this.log('receive', 'Connected to server');
        this.elements.micBtn.classList.remove('mic-offline');
        this.updateConnectionStatus(true);
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        
        // Auto-start listening when connected
        setTimeout(() => {
            this.startListening();
        }, 500);
    }

    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log('receive', `${data.type}: ${JSON.stringify(data).slice(0, 100)}...`);
            this.handleMessage(data);
        } catch (error) {
            this.log('error', `Failed to parse message: ${error.message}`);
        }
    }

    onClose(event) {
        this.log('error', `Disconnected (code: ${event.code})`);
        this.updateConnectionStatus(false);
        this.stopHeartbeat();
        this.stopListening();
        this.setMicState('offline', 'Disconnected');

        // Attempt to reconnect
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            this.log('send', `Reconnecting in ${delay / 1000}s... (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        }
    }

    onError(error) {
        this.log('error', `WebSocket error: ${error.message || 'Unknown error'}`);
    }

    // ==================== Message Handling ====================

    handleMessage(data) {
        switch (data.type) {
            case 'full-text':
                this.addMessage('system', data.text);
                break;

            case 'set-model-and-conf':
                this.clientUid = data.client_uid;
                if (!this.embedMode) {
                    this.addMessage('system', `Connected as ${data.client_uid?.slice(0, 8)}...`);
                    if (data.conf_name) {
                        this.addMessage('system', `Config: ${data.conf_name}`);
                    }
                }
                break;

            case 'control':
                this.handleControlMessage(data.text);
                break;

            case 'audio-response':
                this.ttsPlaying = true;
                this.playAudio(data.audioPath);
                break;

            case 'text-response':
                this.addMessage('assistant', data.text);
                break;

            case 'user-transcription':
                // Update the last user audio message with transcription
                this.updateLastUserMessage(data.text);
                break;

            case 'robot-response':
                // Display robot response
                this.addMessage('robot', data.text);
                // Play audio if available - pause mic to avoid echo loop
                if (data.audio) {
                    this.ttsPlaying = true;
                    this.playAudio(data.audio);
                }
                break;

            case 'partial-text':
                this.updatePartialMessage(data.text);
                break;

            case 'heartbeat-ack':
                // Heartbeat acknowledged, connection is alive
                break;

            case 'error':
                this.addMessage('system', `Error: ${data.message}`);
                break;

            default:
                // Log unknown message types for debugging
                console.log('Unknown message type:', data.type, data);
        }
    }

    handleControlMessage(text) {
        switch (text) {
            case 'start-mic':
                this.log('receive', 'Server requested microphone start');
                break;
            case 'interrupt':
                this.log('receive', 'Conversation interrupted');
                break;
            case 'speech-detected':
                this.log('receive', 'VAD detected speech end');
                if (!this.embedMode) {
                    this.addMessage('system', '[Speech detected, processing...]');
                }
                break;
            case 'vad-pause':
                this.log('receive', 'VAD pause');
                break;
            case 'vad-resume':
                this.log('receive', 'VAD resume');
                break;
            default:
                this.log('receive', `Control: ${text}`);
        }
    }

    // ==================== Sending Messages ====================

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = JSON.stringify(data);
            this.ws.send(message);
            this.log('send', `${data.type}: ${message.slice(0, 100)}...`);
        } else {
            this.log('error', 'Cannot send: WebSocket not connected');
        }
    }

    sendTextMessage() {
        const text = this.elements.textInput.value.trim();
        if (!text) return;

        // Add to UI immediately
        this.addMessage('user', text);

        // Send to server
        this.send({
            type: 'text-input',
            text: text
        });

        // Clear input
        this.elements.textInput.value = '';
    }

    sendInterrupt() {
        this.elements.audioPlayer.pause();
        this.ttsPlaying = false;
        this.send({
            type: 'interrupt-signal',
            text: ''
        });
        if (!this.embedMode) {
            this.addMessage('system', 'Interrupt sent');
        }
    }

    // ==================== Audio Recording ====================

    async toggleMicrophone() {
        if (this.isMicActive) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    async startListening() {
        if (this.isMicActive) return;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                } 
            });
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            await this.audioContext.resume();
            
            // Load AudioWorklet processor (modern replacement for deprecated ScriptProcessorNode)
            await this.audioContext.audioWorklet.addModule('mic-processor.js');

            const source = this.audioContext.createMediaStreamSource(stream);
            this.micWorkletNode = new AudioWorkletNode(this.audioContext, 'mic-processor', {
                numberOfInputs: 1,
                numberOfOutputs: 0
            });
            this.stream = stream;

            this.micWorkletNode.port.onmessage = (event) => {
                if (!this.isMicActive) return;
                if (event.data.type === 'ready') {
                    this.log('receive', 'AudioWorklet ready');
                } else if (event.data.type === 'audio-chunk') {
                    if (this.ttsPlaying) return;
                    this.send({
                        type: 'raw-audio-data',
                        audio: Array.from(event.data.audio)
                    });
                }
            };

            source.connect(this.micWorkletNode);

            this.isMicActive = true;
            this.isRecording = true;
            this.setMicState('listening', 'Listening');
            this.log('send', 'Microphone activated - streaming to server');
            if (!this.embedMode) {
                this.addMessage('system', '🎤 Listening started. Speak anytime - I will detect when you finish.');
            }

        } catch (error) {
            this.log('error', `Microphone access denied: ${error.message}`);
            this.setMicState('muted', 'Muted');
            if (!this.embedMode) {
                this.addMessage('system', 'Microphone access denied. Please allow microphone access.');
            }
        }
    }

    stopListening() {
        if (!this.isMicActive) return;

        this.isMicActive = false;
        this.isRecording = false;
        
        if (this.micWorkletNode) {
            this.micWorkletNode.disconnect();
            this.micWorkletNode.port.onmessage = null;
            this.micWorkletNode = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.setMicState('muted', 'Muted');
        this.log('send', 'Microphone deactivated');
        if (!this.embedMode) {
            this.addMessage('system', '🔇 Microphone muted. Click to resume listening.');
        }
    }

    setMicState(state, label) {
        const btn = this.elements.micBtn;
        btn.classList.remove('mic-listening', 'mic-muted', 'mic-offline');
        if (state === 'listening') {
            btn.classList.add('mic-listening');
        } else if (state === 'muted') {
            btn.classList.add('mic-muted');
        } else if (state === 'offline') {
            btn.classList.add('mic-offline');
        }
        this.setMicLabel(label);
    }

    setMicLabel(text) {
        const label = this.elements.micBtn.querySelector('.mic-text');
        if (label) {
            label.textContent = text;
        }
    }

    // ==================== Audio Playback ====================

    playAudio(audioPath) {
        if (!audioPath) return;

        // audioPath should be like "/cache/filename.mp3"
        const audioUrl = audioPath.startsWith('http') ? audioPath : 
                         audioPath.startsWith('/') ? audioPath : `/${audioPath}`;
        
        this.log('send', `Playing audio: ${audioUrl}`);
        this.elements.audioPlayer.src = audioUrl;
        this.elements.audioPlayer.play().catch(error => {
            this.log('error', `Failed to play audio: ${error.message}`);
            this.ttsPlaying = false;
        });

        this.elements.audioPlayer.onended = () => {
            this.ttsPlaying = false;
            this.send({ type: 'frontend-playback-complete' });
        };
    }

    // ==================== UI Updates ====================

    addMessage(role, text, isAudio = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        // Add prefix based on role
        let displayText = text;
        if (role === 'user') {
            displayText = `User: ${text}`;
            if (isAudio) {
                messageDiv.classList.add('audio-message');
            }
        } else if (role === 'robot') {
            displayText = `Robot: ${text}`;
        }
        
        const time = new Date().toLocaleTimeString();
        messageDiv.innerHTML = `
            <div class="content">${this.escapeHtml(displayText)}</div>
            <div class="timestamp">${time}</div>
        `;

        this.elements.messages.appendChild(messageDiv);
        
        // Track last user audio message for transcription updates
        if (role === 'user' && isAudio) {
            this.lastUserAudioMessage = messageDiv;
        }
        
        this.scrollToBottom();
    }

    updateLastUserMessage(transcription) {
        // Find the last system message about speech detected and update it
        // Or just add the transcription as a user message
        const messages = this.elements.messages.querySelectorAll('.message.system');
        const lastSystemMsg = messages[messages.length - 1];
        
        if (lastSystemMsg && lastSystemMsg.querySelector('.content').textContent.includes('Speech detected')) {
            // Replace the "processing" message with the actual transcription
            lastSystemMsg.remove();
        }
        
        // Add the transcription as a user message
        this.addMessage('user', transcription);
        this.scrollToBottom();
    }

    updatePartialMessage(text) {
        // Find or create the partial message element
        let partialMsg = this.elements.messages.querySelector('.message.assistant.partial');
        
        if (!partialMsg) {
            partialMsg = document.createElement('div');
            partialMsg.className = 'message assistant partial';
            this.elements.messages.appendChild(partialMsg);
        }

        partialMsg.innerHTML = `<div class="content">${this.escapeHtml(text)}</div>`;
        this.scrollToBottom();
    }

    updateConnectionStatus(connected) {
        if (this.elements.connectionStatus) {
            if (connected) {
                this.elements.connectionStatus.classList.add('connected');
                if (this.elements.statusText) {
                    this.elements.statusText.textContent = 'Connected';
                }
            } else {
                this.elements.connectionStatus.classList.remove('connected');
                if (this.elements.statusText) {
                    this.elements.statusText.textContent = 'Disconnected';
                }
            }
        }
        this.notifyParentConnection(connected);
    }

    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    // ==================== Heartbeat ====================

    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            this.send({ type: 'heartbeat' });
        }, 30000); // Every 30 seconds
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    // ==================== Debug Logging ====================

    log(type, message) {
        const time = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `<span class="time">${time}</span>${this.escapeHtml(message)}`;
        this.elements.debugLog.appendChild(entry);
        this.elements.debugLog.scrollTop = this.elements.debugLog.scrollHeight;

        // Also log to console
        console.log(`[${type}] ${message}`);
    }

    // ==================== Utilities ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the chatbot client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.chatbot = new ChatbotClient();
});
