const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendButton");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadButton");

let socket;

// WebSocket
function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/ws`);

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        addMessage("agent", data.content, true);
    };

    socket.onclose = () => {
        addMessage("agent", "_Соединение закрыто. Обновите страницу._", true);
    };
}

// Сообщения
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

    addMessage("user", text);
    socket.send(text);

    input.value = "";
}

// Загрузка файлов
async function uploadFiles() {
    if (!fileInput || fileInput.files.length === 0) return;

    const files = Array.from(fileInput.files);

    for (const file of files) {
        const formData = new FormData();
        formData.append("user_id", "default");
        formData.append("file", file);

        addMessage("agent", `Загружаю документ: **${file.name}**...`, true);

        try {
            const resp = await fetch("/upload", {
                method: "POST",
                body: formData,
            });

            if (!resp.ok) {
                addMessage(
                    "agent",
                    `Не удалось загрузить файл ${file.name}.`,
                    false
                );
                continue;
            }

            const data = await resp.json();
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
            addMessage(
                "agent",
                `Ошибка сети при загрузке файла ${file.name}.`,
                false
            );
        }
    }

    fileInput.value = "";
}

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

document.addEventListener("DOMContentLoaded", connect);

// Кнопка выбора файлов
const selectFilesButton = document.getElementById("selectFilesButton");

if (selectFilesButton && fileInput) {
    selectFilesButton.addEventListener("click", () => {
        fileInput.click();
    });
}

// Очистка документов
const clearButton = document.getElementById("clearButton");

if (clearButton) {
    clearButton.addEventListener("click", async () => {
        const confirmClear = confirm(
            "Вы уверены, что хотите удалить все загруженные документы?\nЭто действие необратимо."
        );

        if (!confirmClear) {
            return;
        }

        try {
            const response = await fetch("/documents", {
                method: "DELETE"
            });

            const result = await response.json();

            if (result.status === "ok") {
                addMessage(
                    "agent",
                    `Все документы удалены.\n\nУдалено файлов: **${result.deleted_documents}**.`,
                    true
                );
            } else {
                addMessage(
                    "agent",
                    "Ошибка при очистке документов.",
                    false
                );
            }
        } catch (error) {
            addMessage(
                "agent",
                "Ошибка соединения с сервером при удалении документов.",
                false
            );
        }
    });
}
