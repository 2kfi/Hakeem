// --- DOM ELEMENTS ---
const sendBtn = document.getElementById('send-btn');
const userInput = document.getElementById('user-input');
const messagesContainer = document.getElementById('messages-container');
const chatHistoryContainer = document.getElementById('chat-history');
const settingsModal = document.getElementById('settings-modal');
const apiProviderSelect = document.getElementById('api-provider');
const apiUrlInput = document.getElementById('api-url');
const apiKeyInput = document.getElementById('api-key');
const systemPromptInput = document.getElementById('system-prompt');
const modelInput = document.getElementById('model-input'); // For Ollama/OpenAI model names

// --- STATE MANAGEMENT ---
let chats = [];
let currentChatId = null;

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadChats();
    setupInitialView();
    addEventListeners();
});

function setupInitialView() {
    if (chats.length > 0) {
        const lastActiveId = localStorage.getItem('hakeem-last-active-chat');
        const chatToLoad = chats.find(c => c.id === parseInt(lastActiveId)) || chats[chats.length - 1];
        loadChat(chatToLoad.id);
    } else {
        createNewChat();
    }
}

function addEventListeners() {
    sendBtn.addEventListener('click', handleChat);
    userInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChat();
        }
    });
    document.querySelector('.new-chat-btn').onclick = createNewChat;
    apiProviderSelect.addEventListener('change', toggleProviderSettings);
}

// --- SETTINGS MANAGEMENT ---
function loadSettings() {
    apiProviderSelect.value = localStorage.getItem('hakeem-api-provider') || 'llama-cpp';
    apiUrlInput.value = localStorage.getItem('hakeem-api-url') || 'http://localhost:8080/v1';
    apiKeyInput.value = localStorage.getItem('hakeem-api-key') || '';
    systemPromptInput.value = localStorage.getItem('hakeem-system-prompt') || 'You are Hakeem, a wise and helpful AI assistant.';
    modelInput.value = localStorage.getItem('hakeem-model') || 'gpt-3.5-turbo';
    toggleProviderSettings();
}

function saveSettings() {
    localStorage.setItem('hakeem-api-provider', apiProviderSelect.value);
    localStorage.setItem('hakeem-api-url', apiUrlInput.value);
    localStorage.setItem('hakeem-api-key', apiKeyInput.value);
    localStorage.setItem('hakeem-system-prompt', systemPromptInput.value);
    localStorage.setItem('hakeem-model', modelInput.value);
    
    settingsModal.close();
    showToast("Settings saved successfully! 🚀");
    toggleProviderSettings(); // Update disclaimer
}

function toggleProviderSettings() {
    const provider = apiProviderSelect.value;
    const disclaimer = document.getElementById('api-disclaimer');
    
    // Hide all optional fields first
    apiUrlInput.parentElement.style.display = 'none';
    apiKeyInput.parentElement.style.display = 'none';
    modelInput.parentElement.style.display = 'none';

    if (provider === 'gemini') {
        apiKeyInput.parentElement.style.display = 'block';
        if(disclaimer) disclaimer.textContent = 'Hakeem is running on Google Gemini.';
    } else if (provider === 'openai') {
        apiKeyInput.parentElement.style.display = 'block';
        modelInput.parentElement.style.display = 'block';
        if(disclaimer) disclaimer.textContent = 'Hakeem is running on the OpenAI API.';
    } else if (provider === 'ollama') {
        apiUrlInput.parentElement.style.display = 'block';
        modelInput.parentElement.style.display = 'block';
        if(disclaimer) disclaimer.textContent = 'Hakeem is running on a local Ollama instance.';
    } else { // llama-cpp
        apiUrlInput.parentElement.style.display = 'block';
        if(disclaimer) disclaimer.textContent = 'Hakeem is running on a local Llama.cpp instance.';
    }
}


// --- CHAT DATA MANAGEMENT ---
function loadChats() {
    chats = JSON.parse(localStorage.getItem('hakeem-chats')) || [];
    renderChatHistory();
}

function saveChats() {
    localStorage.setItem('hakeem-chats', JSON.stringify(chats));
}

function createNewChat() {
    const newChat = { id: Date.now(), title: 'New Conversation', messages: [] };
    chats.push(newChat);
    saveChats();
    loadChat(newChat.id);
}

function loadChat(id) {
    currentChatId = id;
    localStorage.setItem('hakeem-last-active-chat', id);
    const chat = chats.find(c => c.id === id);
    if (chat) {
        displayChat(chat);
        renderChatHistory();
        const activeItem = chatHistoryContainer.querySelector('.history-item.active');
        if (activeItem) activeItem.scrollIntoView({ block: 'nearest' });
    }
}

function deleteChat(event, id) {
    event.stopPropagation();
    chats = chats.filter(c => c.id !== id);
    saveChats();
    
    if (currentChatId === id) {
        if (chats.length > 0) {
            loadChat(chats[chats.length - 1].id);
        } else {
            createNewChat();
        }
    }
    renderChatHistory();
}

function renameChat(id, newTitle) {
    const chat = chats.find(c => c.id === id);
    if (chat && newTitle.trim()) {
        chat.title = newTitle.trim();
        saveChats();
        renderChatHistory();
    }
}

// --- UI & DISPLAY ---
function renderChatHistory() {
    chatHistoryContainer.innerHTML = '';
    if (chats.length === 0) return;
    
    const sortedChats = [...chats].reverse();
    sortedChats.forEach(chat => {
        const item = document.createElement('div');
        item.className = `history-item ${chat.id === currentChatId ? 'active' : ''}`;
        
        // Chat title
        const titleSpan = document.createElement('span');
        titleSpan.className = 'chat-title';
        titleSpan.textContent = chat.title;
        item.appendChild(titleSpan);

        // More options button and dropdown
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'chat-options';
        
        const optionsBtn = document.createElement('button');
        optionsBtn.className = 'options-btn';
        optionsBtn.innerHTML = '⋮'; // Vertical ellipsis
        optionsBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent loading chat when clicking options button
            toggleChatOptions(optionsBtn, chat.id);
        });
        optionsContainer.appendChild(optionsBtn);

        const dropdownMenu = document.createElement('div');
        dropdownMenu.className = 'chat-options-dropdown';
        dropdownMenu.innerHTML = `
            <button class="dropdown-item" data-action="rename">Rename</button>
            <button class="dropdown-item" data-action="delete">Delete</button>
        `;
        dropdownMenu.style.display = 'none'; // Hidden by default
        optionsContainer.appendChild(dropdownMenu);

        item.appendChild(optionsContainer);

        item.addEventListener('click', (e) => {
            // Load chat only if not clicking inside options menu
            if (!optionsContainer.contains(e.target)) {
                loadChat(chat.id);
            }
        });

        chatHistoryContainer.appendChild(item);
    });
}

function toggleChatOptions(button, chatId) {
    const dropdown = button.nextElementSibling;
    // Close all other open dropdowns
    document.querySelectorAll('.chat-options-dropdown').forEach(d => {
        if (d !== dropdown) d.style.display = 'none';
    });
    
    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';

    if (dropdown.style.display === 'block') {
        const renameBtn = dropdown.querySelector('[data-action="rename"]');
        const deleteBtn = dropdown.querySelector('[data-action="delete"]');
        
        renameBtn.onclick = (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            // Start rename action
            const chatItem = button.closest('.history-item');
            const titleSpan = chatItem.querySelector('.chat-title');
            const currentTitle = titleSpan.textContent;
            
            const input = document.createElement('input');
            input.type = 'text';
            input.value = currentTitle;
            input.className = 'rename-input';
            
            chatItem.replaceChild(input, titleSpan);
            input.focus();
            
            const saveRename = () => {
                renameChat(chatId, input.value);
                input.removeEventListener('blur', saveRename);
                input.removeEventListener('keydown', handleRenameKeyDown);
            };

            const handleRenameKeyDown = (e) => {
                if (e.key === 'Enter') input.blur();
                if (e.key === 'Escape') {
                    input.value = currentTitle;
                    input.blur();
                }
            };

            input.addEventListener('blur', saveRename);
            input.addEventListener('keydown', handleRenameKeyDown);
        };

        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            if (confirm('Are you sure you want to delete this conversation?')) {
                deleteChat(e, chatId);
            }
        };
    }
}

// Close dropdowns if clicked outside
document.addEventListener('click', (e) => {
    document.querySelectorAll('.chat-options-dropdown').forEach(d => {
        if (!d.previousElementSibling.contains(e.target)) { // if not clicking the options button
            d.style.display = 'none';
        }
    });
});


function displayChat(chat) {
    messagesContainer.innerHTML = '';
    if (chat.messages.length === 0) {
        messagesContainer.innerHTML = `
            <div class="welcome-message" id="welcome-screen">
                <h1>How can Hakeem help you today?</h1>
                <p>Start a conversation, or adjust your settings.</p>
            </div>`;
    } else {
        chat.messages.forEach(msg => appendMessageToUI(msg.role, msg.content));
    }
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function appendMessageToUI(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = `<div class="message-content">${escapeHTML(text)}</div>`;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return msgDiv.querySelector('.message-content');
}

// --- CORE CHAT LOGIC ---
async function handleChat() {
    const text = userInput.value.trim();
    if (!text) return;

    let chat = chats.find(c => c.id === currentChatId);
    if (!chat) return;

    if (chat.messages.length === 0) {
        const newTitle = text.substring(0, 40) + (text.length > 40 ? '...' : '');
        renameChat(chat.id, newTitle);
    }

    const userMsg = { role: 'user', content: text };
    chat.messages.push(userMsg);
    appendMessageToUI(userMsg.role, userMsg.content);
    userInput.value = '';
    userInput.style.height = 'auto';
    saveChats();

    const aiMessageDiv = appendMessageToUI('assistant', '...');

    try {
        const provider = apiProviderSelect.value;
        const handlers = {
            'gemini': handleGeminiStream,
            'openai': handleOpenAIStream,
            'ollama': handleOllamaStream,
            'llama-cpp': handleLlamaCppStream,
        };
        await handlers[provider](chat, aiMessageDiv);
    } catch (error) {
        console.error("API Error:", error);
        aiMessageDiv.innerText = `Error: ${error.message}. Check settings.`;
    }
}

// --- API STREAM HANDLERS ---
async function handleLlamaCppStream(chat, aiMessageDiv) {
    const response = await fetch(`${apiUrlInput.value}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            model: modelInput.value,
            messages: [{ role: "system", content: systemPromptInput.value }, ...chat.messages],
            stream: true 
        })
    });
    if (!response.ok) throw new Error(`API call failed with status ${response.status}`);
    await processStream(response, chat, aiMessageDiv, (data) => data.choices[0].delta.content || "");
}

async function handleOpenAIStream(chat, aiMessageDiv) {
    const apiKey = apiKeyInput.value;
    if (!apiKey) throw new Error("API Key for OpenAI is required.");

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
        body: JSON.stringify({
            model: modelInput.value,
            messages: [{ role: "system", content: systemPromptInput.value }, ...chat.messages],
            stream: true 
        })
    });
    if (!response.ok) throw new Error(`API call failed with status ${response.status}`);
    await processStream(response, chat, aiMessageDiv, (data) => data.choices[0].delta.content || "");
}

async function handleOllamaStream(chat, aiMessageDiv) {
    // Note: Ollama uses a different endpoint and payload structure
    const response = await fetch(`${apiUrlInput.value}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            model: modelInput.value,
            messages: [{ role: "system", content: systemPromptInput.value }, ...chat.messages],
            stream: true
        })
    });
    if (!response.ok) throw new Error(`API call failed with status ${response.status}`);
    
    // Ollama streams JSON objects separated by newlines, not SSE
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    aiMessageDiv.innerText = "";
    let fullContent = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.trim() !== '');
        for (const line of lines) {
            const data = JSON.parse(line);
            const content = data.message.content;
            fullContent += content;
            aiMessageDiv.innerText = fullContent;
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            if (data.done) break;
        }
    }
    chat.messages.push({ role: 'assistant', content: fullContent });
    saveChats();
}

async function handleGeminiStream(chat, aiMessageDiv) {
    const apiKey = apiKeyInput.value;
    if (!apiKey) throw new Error("API Key for Gemini is required.");
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:streamGenerateContent?key=${apiKey}`;
    
    const contents = chat.messages.map(msg => ({
        role: msg.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: msg.content }]
    }));

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contents, generationConfig: {
            // Optional: Add safety settings or other configs here
        } })
    });
    if (!response.ok) throw new Error(`API call failed with status ${response.status}`);
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    aiMessageDiv.innerText = "";
    let fullContent = "";

    // Gemini response is a stream of JSON objects in an array
    const fullResponseText = await reader.read().then(r => decoder.decode(r.value));
    const jsonResponse = JSON.parse(fullResponseText.trim());

    for (const item of jsonResponse) {
        const content = item.candidates[0].content.parts[0].text;
        fullContent += content;
        aiMessageDiv.innerText = fullContent; // Update UI incrementally
        await new Promise(r => setTimeout(r, 20)); // Small delay for visual effect
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    chat.messages.push({ role: 'assistant', content: fullContent });
    saveChats();
}

// Generic stream processor for SSE formats (OpenAI, Llama.cpp)
async function processStream(response, chat, aiMessageDiv, contentExtractor) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    aiMessageDiv.innerText = "";
    let fullContent = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
            if (line.startsWith('data: ') && !line.endsWith('[DONE]')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    const content = contentExtractor(data);
                    fullContent += content;
                    aiMessageDiv.innerText = fullContent;
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                } catch(e) { /* Ignore parsing errors for incomplete chunks */ }
            }
        }
    }
    chat.messages.push({ role: 'assistant', content: fullContent });
    saveChats();
}


// --- UTILITIES ---
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'notification-bubble show';
    toast.innerHTML = `<span>${escapeHTML(message)}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

function escapeHTML(str) {
    const p = document.createElement("p");
    p.appendChild(document.createTextNode(str));
    return p.innerHTML;
}

// --- GLOBAL EVENT HANDLERS ---
function showPage(pageId) {
    if (pageId === 'settings') {
        settingsModal.showModal();
    }
}
