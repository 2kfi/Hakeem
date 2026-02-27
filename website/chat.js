const sendBtn = document.getElementById('send-btn');
const userInput = document.getElementById('user-input');
const messagesContainer = document.getElementById('messages-container');
const welcomeScreen = document.getElementById('welcome-screen');

// Handle Textarea Auto-Resize
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

async function handleChat() {
    const text = userInput.value.trim();
    if (!text) return;

    // Hide welcome screen on first message
    if (welcomeScreen) welcomeScreen.style.display = 'none';

    // Add User Message to UI
    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto'; // Reset height

    // Prepare the AI message container
    const aiMessageDiv = appendMessage('assistant', '...');
    let fullContent = "";

    try {
        const apiUrl = document.getElementById('api-url').value;
        const systemPrompt = document.getElementById('system-prompt').value;

        const response = await fetch(`${apiUrl}/chat/completions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: "gpt-3.5-turbo", 
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: text }
                ],
                stream: true 
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        aiMessageDiv.innerText = ""; 

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                    try {
                        const data = JSON.parse(line.slice(6));
                        const content = data.choices[0].delta.content || "";
                        fullContent += content;
                        aiMessageDiv.innerText = fullContent; 
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    } catch (e) { console.error("Error parsing JSON chunk", e); }
                }
            }
        }
    } catch (error) {
        aiMessageDiv.innerText = "Error: Could not connect to llama.cpp. Make sure the server is running with --api and --cors.";
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = `<div class="message-content">${text}</div>`;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return msgDiv.querySelector('.message-content');
}

// Event Listeners
sendBtn.addEventListener('click', handleChat);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleChat();
    }
});

function showPage(pageId) {
    if (pageId === 'settings') {
        document.getElementById('settings-modal').showModal();
    }
}

function saveSettings() {
    const apiUrl = document.getElementById('api-url').value;
    const systemPrompt = document.getElementById('system-prompt').value;

    // Save to browser memory
    localStorage.setItem('hakeem-api-url', apiUrl);
    localStorage.setItem('hakeem-system-prompt', systemPrompt);

    console.log("Settings saved to local storage!");
    
    // Close the modal
    document.getElementById('settings-modal').close();
}