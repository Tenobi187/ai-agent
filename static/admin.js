// static/admin.js

// Получаем токен из localStorage
function getToken() {
    return localStorage.getItem('token');
}

// Проверяем, что пользователь админ (если нет - редирект)
async function checkAdmin() {
    const token = getToken();
    if (!token) {
        window.location.href = '/login';
        return false;
    }

    try {
        const response = await fetch('/users/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            window.location.href = '/login';
            return false;
        }

        const user = await response.json();
        
        // Обновляем имя пользователя в панели
        const usernameSpan = document.getElementById('username');
        if (usernameSpan) {
            usernameSpan.textContent = user.username;
        }

        if (user.role !== 'admin') {
            // Если не админ - отправляем на главную
            window.location.href = '/';
            return false;
        }

        return true;
    } catch (err) {
        console.error('Ошибка проверки админа:', err);
        return false;
    }
}

// Показать сообщение об ошибке
// Показать сообщение об ошибке
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    if (errorDiv && errorText) {
        errorText.textContent = message;
        errorDiv.style.display = 'flex';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

// Показать сообщение об успехе
function showSuccess(message) {
    const successDiv = document.getElementById('successMessage');
    const successText = document.getElementById('successText');
    if (successDiv && successText) {
        successText.textContent = message;
        successDiv.style.display = 'flex';
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 3000);
    }
}

// ЗАГРУЗКА ПОЛЬЗОВАТЕЛЕЙ
async function loadUsers() {
    const token = getToken();
    const tbody = document.getElementById('usersTableBody');
    
    try {
        const response = await fetch('/admin/users', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`Ошибка: ${response.status}`);
        }

        const data = await response.json();
        const users = data.users || [];

        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Нет пользователей</td></tr>';
            return;
        }

        let html = '';
        users.forEach(user => {
            // Форматируем дату
            const createdDate = new Date(user.created_at).toLocaleString('ru-RU');
            
            // Класс для бейджа роли
            const roleClass = user.role === 'admin' ? 'admin' : 'user';
            
            html += `
                <tr>
                    <td>${user.id}</td>
                    <td>${user.username}</td>
                    <td>${user.email}</td>
                    <td><span class="role-badge ${roleClass}">${user.role}</span></td>
                    <td>${user.documents_count || 0}</td>
                    <td>${createdDate}</td>
                    <td>
                        <button onclick="changeUserRole(${user.id}, '${user.role}')" class="btn btn-success" style="margin-right: 5px;">
                            ${user.role === 'admin' ? 'Сделать user' : 'Сделать admin'}
                        </button>
                        <button onclick="deleteUser(${user.id}, '${user.username}')" class="btn btn-danger">
                            Удалить
                        </button>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    } catch (err) {
        console.error('Ошибка загрузки пользователей:', err);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: red;">Ошибка загрузки</td></tr>';
        showError('Не удалось загрузить список пользователей');
    }
}

// ЗАГРУЗКА ДОКУМЕНТОВ
async function loadDocuments() {
    const token = getToken();
    const tbody = document.getElementById('documentsTableBody');
    
    try {
        const response = await fetch('/admin/documents', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`Ошибка: ${response.status}`);
        }

        const data = await response.json();
        const documents = data.documents || [];

        if (documents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Нет документов</td></tr>';
            return;
        }

        let html = '';
        documents.forEach(doc => {
            // Форматируем дату
            const createdDate = new Date(doc.created_at).toLocaleString('ru-RU');
            
            html += `
                <tr>
                    <td>${doc.id}</td>
                    <td>${doc.name}</td>
                    <td>${doc.username} (ID: ${doc.user_id})</td>
                    <td>${doc.chunks_count || 0}</td>
                    <td>${createdDate}</td>
                    <td>
                        <button onclick="deleteDocument(${doc.id}, '${doc.name}')" class="btn btn-danger">
                            Удалить
                        </button>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    } catch (err) {
        console.error('Ошибка загрузки документов:', err);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: red;">Ошибка загрузки</td></tr>';
        showError('Не удалось загрузить список документов');
    }
}

// УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
async function deleteUser(userId, username) {
    if (!confirm(`Вы уверены, что хотите удалить пользователя ${username}?\nВсе его документы будут удалены!`)) {
        return;
    }

    const token = getToken();

    try {
        const response = await fetch(`/admin/users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка удаления');
        }

        showSuccess(`Пользователь ${username} удален`);
        loadUsers(); // Перезагружаем список
        loadDocuments(); // Перезагружаем документы (на всякий случай)
    } catch (err) {
        console.error('Ошибка удаления пользователя:', err);
        showError(err.message);
    }
}

// УДАЛЕНИЕ ДОКУМЕНТА
async function deleteDocument(docId, filename) {
    if (!confirm(`Удалить документ "${filename}"?`)) {
        return;
    }

    const token = getToken();

    try {
        const response = await fetch(`/admin/documents/${docId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка удаления');
        }

        showSuccess(`Документ "${filename}" удален`);
        loadDocuments(); // Перезагружаем список документов
        loadUsers(); // Перезагружаем пользователей (обновить счетчики)
    } catch (err) {
        console.error('Ошибка удаления документа:', err);
        showError(err.message);
    }
}

// Удаление всех документов (для админа)
async function deleteAllDocuments() {
    if (!confirm('⚠️ ВНИМАНИЕ! Это действие удалит ВСЕ документы ВСЕХ пользователей!\n\nВы уверены?')) {
        return;
    }
    
    const token = getToken();
    
    try {
        // Получаем все документы
        const docsResponse = await fetch('/admin/documents', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!docsResponse.ok) {
            throw new Error('Не удалось получить список документов');
        }
        
        const data = await docsResponse.json();
        const documents = data.documents || [];
        
        if (documents.length === 0) {
            showSuccess('Нет документов для удаления');
            return;
        }
        
        let deleted = 0;
        let errors = 0;
        
        for (const doc of documents) {
            try {
                const deleteResponse = await fetch(`/admin/documents/${doc.id}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                if (deleteResponse.ok) {
                    deleted++;
                } else {
                    errors++;
                }
            } catch (err) {
                console.error('Ошибка удаления документа', doc.id, err);
                errors++;
            }
        }
        
        if (errors === 0) {
            showSuccess(`Удалено ${deleted} документов`);
        } else {
            showSuccess(`Удалено ${deleted} документов, ошибок: ${errors}`);
        }
        
        loadAllData(); // Перезагружаем всё
    } catch (err) {
        console.error('Ошибка удаления всех документов:', err);
        showError(err.message);
    }
}

// СМЕНА РОЛИ ПОЛЬЗОВАТЕЛЯ
async function changeUserRole(userId, currentRole) {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    
    if (!confirm(`Сменить роль пользователя на "${newRole}"?`)) {
        return;
    }

    const token = getToken();

    try {
        const response = await fetch(`/admin/users/${userId}/role?new_role=${newRole}`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка смены роли');
        }

        showSuccess(`Роль изменена на ${newRole}`);
        loadUsers(); // Перезагружаем список
    } catch (err) {
        console.error('Ошибка смены роли:', err);
        showError(err.message);
    }
}

// ЗАГРУЗИТЬ ВСЁ
async function loadAllData() {
    await Promise.all([loadUsers(), loadDocuments()]);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    const isAdmin = await checkAdmin();
    if (isAdmin) {
        await loadAllData();
        
        // Обновляем каждые 30 секунд
        setInterval(loadAllData, 30000);
    }
});

// Обработчик выхода
const logoutBtn = document.getElementById('logoutButton');
if (logoutBtn) {
    logoutBtn.onclick = async function() {
        const token = getToken();
        if (token) {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        }
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    };
}

