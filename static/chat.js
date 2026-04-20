const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendButton");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadButton");

let socket;

// Функция получения токена
function getToken() {
    return localStorage.getItem('token');
}

// Проверка авторизации перед действиями
function checkAuthBeforeAction() {
    const token = getToken();
    if (!token) {
        alert('Сначала войдите в систему');
        window.location.href = '/login';
        return false;
    }
    return true;
}

// Подключение WebSocket
// Подключение WebSocket
function connect() {
    const token = getToken();
    if (!token) {
        console.log('Нет токена для WebSocket');
        return;
    }
    
    // Если уже есть соединение, не создаем новое
    if (socket && socket.readyState === WebSocket.OPEN) {
        return;
    }
    
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/ws`);

    socket.onopen = function() {
        console.log('WebSocket открыт, отправляем токен');
        socket.send(JSON.stringify({ token: token }));
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.error) {
            console.error('WebSocket ошибка:', data.error);
            if (data.error.includes('Неавторизован')) {
                localStorage.removeItem('token');
                window.location.href = '/login';
            }
            addMessage("agent", `_Ошибка: ${data.error}_`, true);
            return;
        }
        
        addMessage("agent", data.content, true);
    };

    socket.onclose = (event) => {
        console.log('WebSocket закрыт, код:', event.code);
        // Не показываем сообщение при нормальном закрытии (код 1001)
        if (event.code !== 1001) {
            addMessage("agent", "_Соединение закрыто. Обновите страницу._", true);
        }
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
    };
}

// Добавление сообщения в чат
function addMessage(role, text, markdown = false) {
    const msg = document.createElement("div");
    msg.className = `message ${role}`;

    const content = document.createElement("div");
    content.className = "message-content";

    content.innerHTML = markdown ? marked.parse(text) : text;

    msg.appendChild(content);
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
}

// Отправка сообщения
function sendMessage() {
    const text = input.value.trim();
    if (!text || !socket) return;
    
    if (!checkAuthBeforeAction()) return;

    addMessage("user", text);
    socket.send(text);

    input.value = "";
}

// Загрузка файлов
async function uploadFiles() {
    console.log('uploadFiles вызван');
    
    if (!fileInput || fileInput.files.length === 0) {
        alert('Выберите файлы для загрузки');
        return;
    }
    
    const token = getToken();
    console.log('Токен для загрузки:', token ? token.substring(0, 20) + '...' : 'null');
    
    if (!token) {
        alert('Сначала войдите в систему');
        window.location.href = '/login';
        return;
    }

    const files = Array.from(fileInput.files);
    console.log('Файлы для загрузки:', files.map(f => f.name));

    for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);

        addMessage("agent", `Загружаю документ: **${file.name}**...`, true);

        try {
            const resp = await fetch("/upload", {
                method: "POST",
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData,
            });

            console.log('Ответ статус:', resp.status);
            
            if (!resp.ok) {
                const errorData = await resp.json().catch(() => ({}));
                console.error('Ошибка загрузки:', errorData);
                addMessage(
                    "agent",
                    `Не удалось загрузить файл ${file.name}: ${errorData.detail || resp.statusText}`,
                    false
                );
                continue;
            }

            const data = await resp.json();
            console.log('Успех:', data);
            
            if (data.status === "ok") {
                addMessage(
                    "agent",
                    `Документ **${data.filename}** загружен. Найдено чанков: ${data.chunks}.`,
                    true
                );
            } else {
                addMessage(
                    "agent",
                    `Ошибка при загрузке файла ${file.name}: ${data.message || "неизвестная ошибка"}.`,
                    false
                );
            }
        } catch (e) {
            console.error('Ошибка сети:', e);
            addMessage(
                "agent",
                `Ошибка сети при загрузке файла ${file.name}.`,
                false
            );
        }
    }

    fileInput.value = "";
}


// Назначение обработчиков событий
sendBtn.onclick = sendMessage;

input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

if (uploadBtn) {
    uploadBtn.onclick = uploadFiles;
}

// Кнопка выбора файлов
const selectFilesButton = document.getElementById("selectFilesButton");

if (selectFilesButton && fileInput) {
    selectFilesButton.addEventListener("click", () => {
        fileInput.click();
    });
}

// Функция инициализации чата (вызывается из auth-check.js)
window.initializeChat = function() {
    console.log('Инициализация чата...');
    if (socket) {
        socket.close();
    }
    connect();
};

