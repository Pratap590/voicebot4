document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const messagesContainer = document.getElementById('messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const micButton = document.getElementById('mic-button');
    const clearChatButton = document.getElementById('clear-chat');
    const soundToggle = document.getElementById('sound-toggle');
    
    // WebSocket connection
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);
    
    // State
    let isRecording = false;
    let isSoundEnabled = true;
    let mediaRecorder = null;
    let audioChunks = [];
    let conversationContext = {};
    let longPressTimer = null;
    
    // Initialize
    messageInput.focus();
    
    // Event listeners
    ws.onopen = (event) => {
        console.log('WebSocket connected');
        addBotMessage('Connection established. I can help with appointments or answer any questions you have!');
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.error) {
                console.error('Error:', data.error);
                addBotMessage('Sorry, there was an error processing your request.');
            } else if (data.response) {
                addBotMessage(data.response);
                
                // Speak the response if sound is enabled
                if (isSoundEnabled) {
                    speakText(data.response);
                }
                
                // Update conversation context if provided
                if (data.context) {
                    conversationContext = { ...conversationContext, ...data.context };
                }
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
            addBotMessage('Sorry, there was an error processing the response.');
        }
    };
    
    ws.onclose = (event) => {
        console.log('WebSocket disconnected');
        addBotMessage('Connection lost. Please refresh the page to reconnect.');
    };
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key
    messageInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Enable/disable send button based on input
    messageInput.addEventListener('input', () => {
        sendButton.disabled = messageInput.value.trim() === '';
    });
    
    // Clear chat
    clearChatButton.addEventListener('click', () => {
        // Keep only the first bot message
        const firstMessage = messagesContainer.firstElementChild;
        messagesContainer.innerHTML = '';
        messagesContainer.appendChild(firstMessage);
        
        // Reset conversation context
        conversationContext = {};
    });
    
    // Sound toggle
    soundToggle.addEventListener('click', () => {
        isSoundEnabled = !isSoundEnabled;
        soundToggle.innerHTML = isSoundEnabled ? 
            '<i class="ri-volume-up-line"></i>' : 
            '<i class="ri-volume-mute-line"></i>';
    });
    
    // Voice input - toggle on/off with click
    micButton.addEventListener('click', toggleRecording);
    micButton.addEventListener('touchend', (e) => {
        e.preventDefault(); // Prevent touch event from being treated as a mouse event too
        toggleRecording();
    });
    
    // Functions
    function sendMessage() {
        const message = messageInput.value.trim();
        if (message === '') return;
        
        // Add user message to chat
        addUserMessage(message);
        
        // Send to server without specifying mode - server will determine the intent
        ws.send(JSON.stringify({
            message: message,
            context: conversationContext
        }));
        
        // Clear input
        messageInput.value = '';
        messageInput.focus();
        
        // Show typing indicator
        addTypingIndicator();
    }
    
    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message user-message';
        messageElement.textContent = message;
        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }
    
    function addBotMessage(message) {
        // Remove typing indicator if exists
        removeTypingIndicator();
        
        const messageElement = document.createElement('div');
        messageElement.className = 'message bot-message';
        
        // Handle markdown-style content
        if (message.includes('\n')) {
            // Simple markdown parsing for line breaks
            message = message.replace(/\n/g, '<br>');
        }
        
        messageElement.innerHTML = message;
        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }
    
    function addTypingIndicator() {
        removeTypingIndicator();
        const indicator = document.createElement('div');
        indicator.className = 'message bot-message typing-indicator';
        indicator.innerHTML = '<div class="loading"><div></div><div></div><div></div><div></div></div>Thinking...';
        messagesContainer.appendChild(indicator);
        scrollToBottom();
    }
    
    function removeTypingIndicator() {
        const typingIndicator = document.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Voice recording functions
    function startRecording() {
        // Check if browser supports Web Speech API
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            addBotMessage("Your browser doesn't support voice recognition. Please try typing your message instead.");
            return;
        }
        
        // Create speech recognition object
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        // Configure recognition
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        
        // Start recording
        isRecording = true;
        micButton.classList.add('recording');
        micButton.innerHTML = '<i class="ri-record-circle-fill"></i>';
        addBotMessage('Listening... Click the mic button again when finished speaking.');
        
        recognition.start();
        
        // Recognition events
        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            messageInput.value = transcript;
            
            // Automatically send the recognized message
            setTimeout(sendMessage, 500);
        };
        
        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            addBotMessage('Sorry, there was an error with speech recognition. Please try again or type your message.');
            stopRecording();
        };
        
        recognition.onend = function() {
            stopRecording();
        };
    }
    
    function stopRecording() {
        isRecording = false;
        micButton.classList.remove('recording');
        micButton.innerHTML = '<i class="ri-mic-line"></i>';
    }
    
    function toggleRecording() {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    function speakText(text) {
        // Check if browser supports speech synthesis
        if ('speechSynthesis' in window) {
            // Remove markdown and other formatting
            const cleanText = text.replace(/<br>/g, ' ')
                                .replace(/\*\*/g, '')
                                .replace(/\*/g, '')
                                .replace(/__/g, '')
                                .replace(/```[\s\S]*?```/g, 'code block omitted')
                                .replace(/`([^`]*)`/g, '$1');
            
            // Create utterance
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.lang = 'en-US';
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            
            // Speak
            window.speechSynthesis.cancel(); // Cancel any ongoing speech
            window.speechSynthesis.speak(utterance);
        }
    }
}); 