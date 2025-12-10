const messagesDiv = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
let socket = null;

marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (err) {
                console.warn(`Ошибка подсветки для языка ${lang}:`, err);
            }
        }
        return hljs.highlightAuto(code).value;
    }
});

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '/ws';
    
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('WebSocket подключен к серверу');
        addMessage('agent', '\nПривет! Я ваш ИИ-ассистент. Чем могу помочь?\n', true);
    };

    socket.onmessage = (event) => {
        removeTyping();
        try {
            const data = JSON.parse(event.data);
            addMessage('agent', data.content, true);
        } catch (error) {
            console.error('Ошибка парсинга ответа:', error);
            addMessage('agent', '**Ошибка:** Получен некорректный ответ от сервера', true);
        }
    };

    socket.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
        removeTyping();
        addMessage('agent', '**⚠️ Ошибка соединения**\n\nНе удалось подключиться к серверу. Пожалуйста, проверьте:\n1. Запущен ли сервер\n2. Нет ли проблем с сетью', true);
    };

    socket.onclose = () => {
        console.log('WebSocket отключен от сервера');
        addMessage('agent', '**🔌 Соединение потеряно**\n\nПожалуйста, обновите страницу для восстановления связи.', true);
    };
}

messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    addMessage('user', text, false);
    messageInput.value = '';
    messageInput.style.height = '44px';
    messageInput.focus();

    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(text);
        showTyping();
    } else {
        addMessage('agent', '**❌ Нет соединения с сервером**\n\nПопробуйте обновить страницу (F5).', true);
        initWebSocket();
    }
}

sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function addMessage(sender, text, isMarkdown = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (isMarkdown && sender === 'agent') {
        contentDiv.innerHTML = marked.parse(text);
        
        setTimeout(() => {
            document.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }, 10);
    } else {
        contentDiv.textContent = text;
    }
    
    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showTyping() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message agent';
    typingDiv.id = 'typingIndicator';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'typing';
    contentDiv.innerHTML = '<span></span><span></span><span></span>';
    
    typingDiv.appendChild(contentDiv);
    messagesDiv.appendChild(typingDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTyping() {
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
}

document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
});