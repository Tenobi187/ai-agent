// static/my-documents.js

function getToken() {
    return localStorage.getItem('token');
}

// Проверка авторизации
async function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = '/login';
        return false;
    }
    
    try {
        const response = await fetch('/users/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            window.location.href = '/login';
            return false;
        }
        
        const user = await response.json();
        const usernameSpan = document.getElementById('username');
        if (usernameSpan) {
            usernameSpan.textContent = user.username;
        }
        
        // Показываем кнопку админки если нужно
        const adminBtn = document.getElementById('adminButton');
        if (adminBtn && user.role === 'admin') {
            adminBtn.style.display = 'inline-block';
        }
        
        return true;
    } catch (err) {
        console.error('Ошибка авторизации:', err);
        return false;
    }
}

// Показать сообщение
function showMessage(type, text) {
    const successDiv = document.getElementById('successMessage');
    const errorDiv = document.getElementById('errorMessage');
    const successText = document.getElementById('successText');
    const errorText = document.getElementById('errorText');
    
    if (type === 'success') {
        successText.textContent = text;
        successDiv.style.display = 'flex';
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 3000);
    } else {
        errorText.textContent = text;
        errorDiv.style.display = 'flex';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 3000);
    }
}

// Загрузка документов
async function loadDocuments() {
    const token = getToken();
    const tbody = document.getElementById('documentsTableBody');
    const stats = document.getElementById('stats');
    
    tbody.innerHTML = '<tr><td colspan="4" class="loading">Загрузка...</td></tr>';
    
    try {
        const response = await fetch('/documents', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки документов');
        }
        
        const data = await response.json();
        const documents = data.documents || [];
        
        // Обновляем статистику
        const totalCount = document.getElementById('totalCount');
        if (totalCount) {
            totalCount.textContent = documents.length;
        }
        stats.style.display = 'flex';
        
        if (documents.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 40px;">
                        У вас пока нет загруженных документов.<br>
                        <a href="/" style="color: #9381ff;">Загрузить документы</a>
                    </td>
                </tr>
            `;
            return;
        }
        
        let html = '';
        documents.forEach(doc => {
            const createdDate = new Date(doc.created_at).toLocaleString('ru-RU');
            html += `
                <tr>
                    <td style="word-break: break-word;">${escapeHtml(doc.name)}</td>
                    <td style="white-space: nowrap;">${createdDate}</td>
                    <td style="text-align: center;">—</td>
                    <td>
                        <button onclick="deleteDocument(${doc.id}, '${escapeHtml(doc.name)}')" class="delete-btn">
                            Удалить
                        </button>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    } catch (err) {
        console.error('Ошибка:', err);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: red;">Ошибка загрузки</td></tr>';
        showMessage('error', err.message);
    }
}

// Удаление документа
async function deleteDocument(docId, filename) {
    if (!confirm(`Удалить документ "${filename}"?`)) {
        return;
    }
    
    const token = getToken();
    
    try {
        const response = await fetch(`/documents/${docId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка удаления');
        }
        
        showMessage('success', `Документ "${filename}" удален`);
        loadDocuments(); // Перезагружаем список
    } catch (err) {
        console.error('Ошибка удаления:', err);
        showMessage('error', err.message);
    }
}

// Удаление всех документов
async function deleteAllDocuments() {
    if (!confirm(' ВНИМАНИЕ! Это действие удалит ВСЕ ваши документы без возможности восстановления.\n\nВы уверены?')) {
        return;
    }
    
    const token = getToken();
    
    try {
        const response = await fetch('/documents', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка удаления');
        }
        
        const result = await response.json();
        showMessage('success', `Удалено ${result.deleted_documents} документов`);
        loadDocuments(); // Перезагружаем список
    } catch (err) {
        console.error('Ошибка удаления всех документов:', err);
        showMessage('error', err.message);
    }
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Обработчик выхода
const logoutBtn = document.getElementById('logoutButton');
if (logoutBtn) {
    logoutBtn.onclick = async function() {
        const token = getToken();
        if (token) {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        }
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    };
}

// Инициализация
document.addEventListener('DOMContentLoaded', async function() {
    const isAuth = await checkAuth();
    if (isAuth) {
        loadDocuments();
    }
});