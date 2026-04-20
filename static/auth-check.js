// static/auth-check.js

// Определяем переменные ДО их использования
const currentPath = window.location.pathname;
const publicPages = ['/login', '/register']; // Список публичных страниц

// Проверяем авторизацию при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    
    const token = localStorage.getItem('token');
    
    // Если мы на публичной странице - пропускаем проверку
    if (publicPages.includes(currentPath)) {
        return;
    }
    
    // Если нет токена - редирект на логин
    if (!token) {
        console.log('Нет токена, редирект на login');
        window.location.href = '/login';
        return;
    }
    
    try {
        // Проверяем токен на сервере
        const response = await fetch('/users/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const user = await response.json();
            
            // Обновляем интерфейс
            updateUserPanel(user);
            
            // Сохраняем пользователя в localStorage
            localStorage.setItem('user', JSON.stringify(user));
            
            // Инициализируем WebSocket через chat.js (если функция существует)
            if (window.initializeChat) {
                window.initializeChat();
            }
        } else {
            console.log('Токен недействителен, очищаем');
            // Токен недействителен
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
        }
    } catch (err) {
        console.error('Ошибка проверки авторизации:', err);
        // При ошибке сети оставляем на месте, но показываем сообщение
        document.body.innerHTML = '<div style="padding: 20px; text-align: center;">Ошибка соединения с сервером. <a href="/login">Попробовать снова</a></div>';
    }
});

function updateUserPanel(user) {
    const usernameSpan = document.getElementById('username');
    const logoutBtn = document.getElementById('logoutButton');
    const adminLink = document.getElementById('adminLink');
    
    if (usernameSpan) {
        usernameSpan.textContent = user.username;
    }
    
    // Показываем ссылку на админку только админам
    if (adminLink) {
        if (user.role === 'admin') {
            adminLink.style.display = 'inline-block';
        } else {
            adminLink.style.display = 'none';
        }
    }
    
    if (logoutBtn) {
        logoutBtn.onclick = async function() {
            const token = localStorage.getItem('token');
            
            if (token) {
                try {
                    await fetch('/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                } catch (e) {
                    console.error('Ошибка при выходе:', e);
                }
            }
            
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
        };
    }
}