"""
Web-интерфейс для выдачи временных MTProto прокси
Минималистичный дизайн - только кнопка подключения
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import asyncio

app = FastAPI(title="MTProto Proxy Generator")

# TODO: Подключение к БД и генерация прокси


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница - минимализм"""
    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>VPN Connect</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: var(--tg-theme-bg-color, #1c1c1e);
                color: var(--tg-theme-text-color, #ffffff);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 20px;
            }
            .container { text-align: center; max-width: 400px; }
            h1 { font-size: 28px; margin-bottom: 10px; }
            p { color: var(--tg-theme-hint-color, #999); margin-bottom: 30px; }
            .btn {
                background: var(--tg-theme-button-color, #3390ec);
                color: var(--tg-theme-button-text-color, #fff);
                border: none;
                padding: 16px 40px;
                font-size: 18px;
                font-weight: 600;
                border-radius: 12px;
                cursor: pointer;
                width: 100%;
                max-width: 300px;
                transition: opacity 0.2s;
            }
            .btn:active { opacity: 0.8; }
            .btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .timer { 
                margin-top: 20px; 
                font-size: 14px; 
                color: var(--tg-theme-hint-color, #999);
                display: none;
            }
            .status {
                margin-top: 15px;
                padding: 12px;
                border-radius: 8px;
                background: var(--tg-theme-secondary-bg-color, #2c2c2e);
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 VPN Proxy</h1>
            <p>Временный прокси для Telegram<br>Действует 5 минут</p>
            
            <button class="btn" id="connectBtn" onclick="generateProxy()">
                🔌 Подключиться
            </button>
            
            <div class="timer" id="timer">⏱ Действует: <span id="timeLeft">5:00</span></div>
            
            <div class="status" id="status"></div>
        </div>

        <script>
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();

            let countdown;
            
            async function generateProxy() {
                const btn = document.getElementById('connectBtn');
                const timer = document.getElementById('timer');
                const status = document.getElementById('status');
                
                btn.disabled = true;
                btn.textContent = '⏳ Создание...';
                
                try {
                    const response = await fetch('/api/generate', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ user_id: tg.initDataUnsafe?.user?.id })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        // Открываем ссылку для подключения
                        const proxyUrl = `tg://proxy?server=${data.server}&port=${data.port}&secret=${data.secret}`;
                        
                        status.style.display = 'block';
                        status.innerHTML = '✅ <b>Готово!</b><br>Нажмите для подключения в Telegram';
                        status.onclick = () => { window.location.href = proxyUrl; };
                        
                        // Запускаем таймер
                        timer.style.display = 'block';
                        let seconds = 300; // 5 минут
                        
                        countdown = setInterval(() => {
                            seconds--;
                            const mins = Math.floor(seconds / 60);
                            const secs = seconds % 60;
                            document.getElementById('timeLeft').textContent = 
                                `${mins}:${secs.toString().padStart(2, '0')}`;
                            
                            if (seconds <= 0) {
                                clearInterval(countdown);
                                btn.disabled = false;
                                btn.textContent = '🔄 Создать новый';
                                timer.style.display = 'none';
                                status.innerHTML = '⏰ Время истекло<br>Создайте новый прокси';
                            }
                        }, 1000);
                        
                    } else {
                        throw new Error(data.error || 'Ошибка создания');
                    }
                } catch (error) {
                    status.style.display = 'block';
                    status.innerHTML = '❌ Ошибка: ' + error.message;
                    btn.disabled = false;
                    btn.textContent = '🔄 Повторить';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post('/api/generate')
async def generate_proxy(request: Request):
    """Генерация временного MTProto прокси"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        # TODO: 
        # 1. Проверка активной подписки пользователя в БД
        # 2. Генерация уникального secret для MTProto
        # 3. Сохранение в БД с expiry = now + 5 минут
        # 4. Возврат данных прокси
        
        # Пример ответа (заглушка)
        return {
            'success': True,
            'server': 'vpn.example.com',
            'port': 443,
            'secret': 'ee1234567890abcdef1234567890abcd'  # Временный
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
