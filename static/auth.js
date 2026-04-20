// auth.js - отвечает за отправку форм на сервер

// Ждем, когда загрузится страница
document.addEventListener('DOMContentLoaded', function() {
    
    // ===== ОБРАБОТКА ФОРМЫ ВХОДА =====
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            const errorDiv = document.getElementById('error');
            if (errorDiv) errorDiv.textContent = '';
            
            try {
                const response = await fetch('/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        username: username, 
                        password: password 
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    console.log('Получен токен:', data.access_token);
                    localStorage.setItem('token', data.access_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    window.location.href = '/';
                } else {
                    if (errorDiv) errorDiv.textContent = data.detail || 'Ошибка входа';
                }
            } catch (err) {
                console.error('Ошибка входа:', err);
                if (errorDiv) errorDiv.textContent = 'Ошибка соединения с сервером';
            }
        });
    }
    
    // ===== ОБРАБОТКА ФОРМЫ РЕГИСТРАЦИИ =====
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            const errorDiv = document.getElementById('error');
            const successDiv = document.getElementById('success');
            
            if (errorDiv) errorDiv.textContent = '';
            if (successDiv) successDiv.textContent = '';
            
            try {
                const response = await fetch('/auth/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        username, 
                        email, 
                        password 
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    if (successDiv) {
                        successDiv.textContent = 'Регистрация успешна! Сейчас перенаправляем на вход...';
                        successDiv.style.display = 'block';
                    }
                    
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else {
                    if (errorDiv) {
                        errorDiv.textContent = data.detail || 'Ошибка регистрации';
                        errorDiv.style.display = 'block';
                    }
                }
            } catch (err) {
                console.error('Ошибка регистрации:', err);
                if (errorDiv) {
                    errorDiv.textContent = 'Ошибка соединения с сервером';
                    errorDiv.style.display = 'block';
                }
            }
        });
    }
});


// ===== ФУНКЦИЯ ВЫХОДА =====
async function logout() {
    const token = localStorage.getItem('token');
    
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
}